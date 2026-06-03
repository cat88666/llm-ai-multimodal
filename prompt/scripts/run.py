#!/usr/bin/env python3
"""
主入口：遍历 raw/，提取每个文件，写入 wiki/summaries/<相对路径>.json
用法：
  python run.py                  # 处理全部文件
  python run.py --ext pdf        # 只处理 PDF
  python run.py --dir 三审       # 只处理某个子目录
  python run.py --file raw/三审/民申559.pdf   # 单文件调试
"""

import argparse
import json
import sys
import time
from pathlib import Path

import anthropic

sys.path.insert(0, str(Path(__file__).parent))
from config import (ANTHROPIC_API_KEY, EXTRACT_MODEL, IMAGE_MAX_PX,
                    RAW_DIR, SUMMARIES_DIR, SKIP_EXT, SUPPORTED_EXT)
from extractors import extract_content
from prompts import PROMPTS, SYSTEM, route


def build_messages(prompt_type: str, file_path: Path, extracted: dict) -> list:
    dir_name = file_path.parent.name
    rel_path = str(file_path.relative_to(RAW_DIR))
    tmpl = PROMPTS[prompt_type]["user_tmpl"]

    if extracted["mode"] == "text":
        content_str = extracted["content"] or "[文件内容为空]"
        user_text = tmpl.format(path=rel_path, dir_name=dir_name, content=content_str)
        return [{"role": "user", "content": user_text}]
    else:
        # 图片模式
        media_type, b64 = extracted["content"]
        # 图片 prompt 不注入 {content}，直接附图
        user_text = tmpl.format(path=rel_path, dir_name=dir_name, content="[见图片]")
        return [{"role": "user", "content": [
            {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": b64}},
            {"type": "text", "text": user_text},
        ]}]


def call_api(client: anthropic.Anthropic, messages: list) -> str:
    resp = client.messages.create(
        model=EXTRACT_MODEL,
        max_tokens=2048,
        system=[{
            "type": "text",
            "text": SYSTEM,
            "cache_control": {"type": "ephemeral"},  # prompt cache
        }],
        messages=messages,
    )
    return resp.content[0].text.strip()


def parse_json_safe(text: str) -> dict:
    # 去掉可能的 markdown 代码块包裹
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1])
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"raw_text": text, "_parse_error": True}


def output_path(file_path: Path) -> Path:
    rel = file_path.relative_to(RAW_DIR)
    out = SUMMARIES_DIR / rel.with_suffix(".json")
    out.parent.mkdir(parents=True, exist_ok=True)
    return out


def process_file(client: anthropic.Anthropic, file_path: Path, force: bool = False) -> bool:
    out = output_path(file_path)
    if out.exists() and not force:
        return False  # 已处理，跳过

    suffix = file_path.suffix.lower()
    if suffix in SKIP_EXT or suffix not in SUPPORTED_EXT:
        return False

    print(f"  处理: {file_path.relative_to(RAW_DIR)}")
    try:
        extracted = extract_content(file_path)
        prompt_type = route(str(file_path), file_path.parent.name)
        messages = build_messages(prompt_type, file_path, extracted)
        raw_response = call_api(client, messages)
        result = parse_json_safe(raw_response)
        result["_meta"] = {
            "source": str(file_path.relative_to(RAW_DIR)),
            "prompt_type": prompt_type,
            "model": EXTRACT_MODEL,
        }
        out.write_text(json.dumps(result, ensure_ascii=False, indent=2))
        print(f"    ✓ -> {out.relative_to(SUMMARIES_DIR)}")
        return True
    except Exception as e:
        print(f"    ✗ 失败: {e}")
        err_out = out.with_suffix(".error.json")
        err_out.write_text(json.dumps({"error": str(e), "file": str(file_path)}, ensure_ascii=False))
        return False


def collect_files(ext_filter: str = None, dir_filter: str = None, single_file: str = None):
    if single_file:
        p = Path(single_file)
        if not p.is_absolute():
            p = Path(__file__).parent.parent.parent / single_file
        return [p]

    files = []
    for f in sorted(RAW_DIR.rglob("*")):
        if not f.is_file():
            continue
        if f.suffix.lower() in SKIP_EXT:
            continue
        if f.suffix.lower() not in SUPPORTED_EXT:
            continue
        if ext_filter and f.suffix.lower().lstrip(".") != ext_filter.lower():
            continue
        if dir_filter and dir_filter not in str(f):
            continue
        files.append(f)
    return files


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ext", help="只处理指定扩展名，如 pdf/jpg/docx")
    parser.add_argument("--dir", help="只处理包含此字符串的路径")
    parser.add_argument("--file", help="处理单个文件（调试用）")
    parser.add_argument("--force", action="store_true", help="强制重新处理已完成文件")
    args = parser.parse_args()

    if not ANTHROPIC_API_KEY:
        print("错误：未设置 ANTHROPIC_API_KEY 环境变量")
        sys.exit(1)

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    files = collect_files(args.ext, args.dir, args.file)
    print(f"共找到 {len(files)} 个文件待处理\n")

    done, skipped, failed = 0, 0, 0
    for i, f in enumerate(files, 1):
        print(f"[{i}/{len(files)}]", end=" ")
        result = process_file(client, f, force=args.force)
        if result:
            done += 1
        else:
            skipped += 1
        # 避免触发 API 速率限制
        if result:
            time.sleep(0.3)

    print(f"\n完成: {done}  跳过: {skipped}  失败: {failed}")


if __name__ == "__main__":
    main()
