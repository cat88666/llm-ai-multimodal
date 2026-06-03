#!/usr/bin/env python3
"""
AI 多模态文件转 Markdown 工具

支持格式：.pdf  .docx  .jpg  .jpeg  .png  .txt
输出位置：output/<原始文件名>.md

用法：
  python convert.py                      # 转换 raw/ 下所有支持格式的文件
  python convert.py --file raw/xx.pdf    # 只处理单个文件
  python convert.py --force              # 强制覆盖已存在的输出文件
"""

import argparse
import base64
import io
import os
import sys
import time
from pathlib import Path

import anthropic
from PIL import Image

# ── 路径 ──────────────────────────────────────────────────
REPO_ROOT  = Path(__file__).parent
RAW_DIR    = REPO_ROOT / "raw"
OUT_DIR    = REPO_ROOT / "output"
PROMPT_DIR = REPO_ROOT / "prompts"

# ── 模型 ──────────────────────────────────────────────────
MODEL        = "claude-haiku-4-5-20251001"
IMAGE_MAX_PX = 1568

SUPPORTED_EXT = {".pdf", ".docx", ".jpg", ".jpeg", ".png", ".txt"}

# ── 提示词（启动时加载，触发提示词缓存）──────────────────────
SYSTEM_PROMPT    = (PROMPT_DIR / "system.md").read_text(encoding="utf-8")
IMAGE_PROMPT     = (PROMPT_DIR / "image_to_md.md").read_text(encoding="utf-8")
TEXT_PROMPT_TMPL = (PROMPT_DIR / "text_to_md.md").read_text(encoding="utf-8")


# ── 本地提取 ──────────────────────────────────────────────

def extract_pdf_text(path: Path) -> str | None:
    """提取 PDF 文字层；文字过少（扫描件）返回 None。"""
    import fitz
    doc = fitz.open(str(path))
    pages = []
    for i, page in enumerate(doc):
        text = page.get_text().strip()
        if text:
            pages.append(f"<!-- 第{i+1}页 -->\n{text}")
    doc.close()
    result = "\n\n---\n\n".join(pages)
    return result if len(result.strip()) >= 50 else None


def pdf_to_images(path: Path) -> list[tuple[str, str]]:
    """将 PDF 每页渲染为 base64 JPEG，用于扫描件 OCR。"""
    import fitz
    doc = fitz.open(str(path))
    images = []
    for page in doc:
        pix = page.get_pixmap(dpi=150)
        b64 = base64.standard_b64encode(pix.tobytes("jpeg")).decode()
        images.append(("image/jpeg", b64))
    doc.close()
    return images


def extract_docx(path: Path) -> str:
    """提取 docx 的段落与表格，保留结构。"""
    import docx
    doc = docx.Document(str(path))
    parts = []
    for block in doc.element.body:
        tag = block.tag.split("}")[-1]
        if tag == "p":
            para = docx.text.paragraph.Paragraph(block, doc)
            if para.text.strip():
                parts.append(para.text)
        elif tag == "tbl":
            from docx.table import Table
            table = Table(block, doc)
            rows = []
            for i, row in enumerate(table.rows):
                cells = [c.text.strip().replace("\n", " ") for c in row.cells]
                rows.append("| " + " | ".join(cells) + " |")
                if i == 0:
                    rows.append("|" + "|".join(["---"] * len(cells)) + "|")
            parts.append("\n".join(rows))
    return "\n\n".join(parts)


def read_txt(path: Path) -> str:
    """按常见编码尝试读取 txt，兜底 utf-8 replace。"""
    for enc in ("utf-8", "gbk", "gb2312"):
        try:
            return path.read_text(encoding=enc)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="replace")


def image_to_base64(path: Path) -> tuple[str, str]:
    """压缩超大图片并编码为 base64 JPEG。"""
    img = Image.open(str(path))
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    w, h = img.size
    if max(w, h) > IMAGE_MAX_PX:
        ratio = IMAGE_MAX_PX / max(w, h)
        img = img.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return "image/jpeg", base64.standard_b64encode(buf.getvalue()).decode()


# ── Claude API 调用 ───────────────────────────────────────

def call_vision(client: anthropic.Anthropic, media_type: str, b64: str) -> str:
    resp = client.messages.create(
        model=MODEL,
        max_tokens=4096,
        system=[{"type": "text", "text": SYSTEM_PROMPT,
                 "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": [
            {"type": "image", "source": {
                "type": "base64", "media_type": media_type, "data": b64}},
            {"type": "text", "text": IMAGE_PROMPT},
        ]}],
    )
    return resp.content[0].text.strip()


def call_text(client: anthropic.Anthropic, content: str) -> str:
    resp = client.messages.create(
        model=MODEL,
        max_tokens=4096,
        system=[{"type": "text", "text": SYSTEM_PROMPT,
                 "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": TEXT_PROMPT_TMPL.format(content=content)}],
    )
    return resp.content[0].text.strip()


# ── 核心转换 ──────────────────────────────────────────────

def convert_file(client: anthropic.Anthropic, src: Path, force: bool = False) -> bool:
    rel = src.relative_to(RAW_DIR)
    dst = OUT_DIR / rel.with_suffix(".md")

    if dst.exists() and not force:
        return False

    dst.parent.mkdir(parents=True, exist_ok=True)
    suffix = src.suffix.lower()

    try:
        if suffix == ".pdf":
            text = extract_pdf_text(src)
            if text is None:
                print("    [扫描件 PDF，使用 Vision OCR]")
                pages = pdf_to_images(src)
                mds = []
                for i, (mt, b64) in enumerate(pages):
                    mds.append(f"<!-- 第{i+1}页 -->\n\n{call_vision(client, mt, b64)}")
                    time.sleep(0.2)
                md_body = "\n\n---\n\n".join(mds)
            else:
                md_body = call_text(client, text)

        elif suffix in (".jpg", ".jpeg", ".png"):
            media_type, b64 = image_to_base64(src)
            md_body = call_vision(client, media_type, b64)

        elif suffix == ".docx":
            md_body = call_text(client, extract_docx(src))

        elif suffix == ".txt":
            md_body = call_text(client, read_txt(src))

        else:
            return False

        dst.write_text(md_body, encoding="utf-8")
        return True

    except Exception as e:
        print(f"    ✗ 失败: {e}")
        dst.write_text(f"**转换失败**: {e}\n", encoding="utf-8")
        return False


# ── 文件收集 ──────────────────────────────────────────────

def collect(single_file: str = None) -> list[Path]:
    if single_file:
        p = Path(single_file)
        return [p if p.is_absolute() else REPO_ROOT / single_file]
    return [
        f for f in sorted(RAW_DIR.rglob("*"))
        if f.is_file()
        and f.suffix.lower() in SUPPORTED_EXT
        and "output" not in f.parts
    ]


# ── 主入口 ────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="AI 多模态文件转 Markdown")
    parser.add_argument("--file",  help="只处理单个文件（调试用）")
    parser.add_argument("--force", action="store_true", help="强制覆盖已存在的输出文件")
    args = parser.parse_args()

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        print("错误：请先设置 ANTHROPIC_API_KEY 环境变量")
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)
    files  = collect(args.file)
    total  = len(files)
    print(f"共 {total} 个文件待处理，输出到 output/\n")

    done = skipped = 0
    for i, f in enumerate(files, 1):
        print(f"[{i}/{total}] {f.relative_to(REPO_ROOT)}")
        result = convert_file(client, f, force=args.force)
        if result:
            done += 1
            print("    ✓")
            time.sleep(0.3)
        else:
            skipped += 1
            print("    - 跳过（已存在）")

    print(f"\n完成 {done}，跳过 {skipped}，共 {total}")


if __name__ == "__main__":
    main()
