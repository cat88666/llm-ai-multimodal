#!/usr/bin/env python3
"""
将 raw/ 下所有文件转换为 markdown，输出到 raw/sources/，目录结构一一对应。

用法：
  python to_markdown.py                    # 转换全部
  python to_markdown.py --dir 三审         # 只转某目录
  python to_markdown.py --file raw/三审/民申559.pdf  # 单文件调试
  python to_markdown.py --force            # 强制覆盖已存在的文件
"""

import argparse
import base64
import io
import sys
import time
from pathlib import Path

import anthropic
from PIL import Image

# ── 路径配置 ──────────────────────────────────────────────
REPO_ROOT = Path(__file__).parent.parent.parent
RAW_DIR   = REPO_ROOT / "raw"
OUT_DIR   = RAW_DIR / "sources"

# ── 模型配置 ──────────────────────────────────────────────
VISION_MODEL = "claude-haiku-4-5-20251001"   # 图片 OCR
TEXT_MODEL   = "claude-haiku-4-5-20251001"   # 文字润色（通常直接用提取结果）
IMAGE_MAX_PX = 1568

SKIP_EXT = {".mp4", ".MP4", ".ds_store", ".DS_Store"}
SUPPORT_EXT = {".pdf", ".jpg", ".jpeg", ".png", ".docx", ".txt"}

PROMPT_DIR = REPO_ROOT / "prompt"

# ── 从文件加载 Prompt ─────────────────────────────────────
SYSTEM_PROMPT     = (PROMPT_DIR / "system.md").read_text(encoding="utf-8")
IMAGE_USER_PROMPT = (PROMPT_DIR / "image_to_md.md").read_text(encoding="utf-8")
TEXT_USER_TMPL    = (PROMPT_DIR / "text_to_md.md").read_text(encoding="utf-8")


# ── 内容提取 ──────────────────────────────────────────────

def extract_pdf_text(path: Path) -> str:
    import fitz
    doc = fitz.open(str(path))
    pages = []
    for i, page in enumerate(doc):
        text = page.get_text().strip()
        if text:
            pages.append(f"<!-- 第{i+1}页 -->\n{text}")
    doc.close()
    return "\n\n---\n\n".join(pages)


def extract_docx_text(path: Path) -> str:
    import docx
    doc = docx.Document(str(path))
    parts = []
    for block in doc.element.body:
        tag = block.tag.split("}")[-1]
        if tag == "p":
            from docx.oxml.ns import qn
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


def image_to_base64(path: Path) -> tuple[str, str]:
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


# ── API 调用 ──────────────────────────────────────────────

def call_vision(client: anthropic.Anthropic, media_type: str, b64: str) -> str:
    resp = client.messages.create(
        model=VISION_MODEL,
        max_tokens=4096,
        system=[{"type": "text", "text": SYSTEM_PROMPT,
                 "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": [
            {"type": "image", "source": {
                "type": "base64", "media_type": media_type, "data": b64}},
            {"type": "text", "text": IMAGE_USER_PROMPT},
        ]}],
    )
    return resp.content[0].text.strip()


def call_text(client: anthropic.Anthropic, content: str) -> str:
    """PDF/DOCX/TXT 文字已由本地库提取，直接返回，不调模型节省 token。
    如需模型格式化，取消注释下方代码。"""
    return content
    # resp = client.messages.create(
    #     model=TEXT_MODEL,
    #     max_tokens=4096,
    #     system=[{"type": "text", "text": SYSTEM_PROMPT,
    #              "cache_control": {"type": "ephemeral"}}],
    #     messages=[{"role": "user", "content": TEXT_USER_TMPL.format(content=content)}],
    # )
    # return resp.content[0].text.strip()


# ── 核心转换逻辑 ──────────────────────────────────────────

def convert_file(client: anthropic.Anthropic, src: Path, force: bool = False) -> bool:
    rel = src.relative_to(RAW_DIR)
    dst = OUT_DIR / rel.with_suffix(".md")

    if dst.exists() and not force:
        return False  # 已处理，跳过

    dst.parent.mkdir(parents=True, exist_ok=True)
    suffix = src.suffix.lower()

    header = f"# {src.name}\n\n> 源文件：`{rel}`\n\n---\n\n"

    try:
        if suffix == ".pdf":
            raw_text = extract_pdf_text(src)
            if len(raw_text.strip()) < 50:
                # 扫描件 PDF，文字提取失败，转 Vision
                print(f"    [扫描件，转Vision] {src.name}")
                # 用 pymupdf 渲染每页为图片
                import fitz
                doc = fitz.open(str(src))
                page_mds = []
                for i, page in enumerate(doc):
                    pix = page.get_pixmap(dpi=150)
                    img_data = pix.tobytes("jpeg")
                    b64 = base64.standard_b64encode(img_data).decode()
                    page_md = call_vision(client, "image/jpeg", b64)
                    page_mds.append(f"<!-- 第{i+1}页 -->\n\n{page_md}")
                    time.sleep(0.2)
                doc.close()
                md_body = "\n\n---\n\n".join(page_mds)
            else:
                md_body = raw_text

        elif suffix in (".jpg", ".jpeg", ".png"):
            media_type, b64 = image_to_base64(src)
            md_body = call_vision(client, media_type, b64)

        elif suffix == ".docx":
            md_body = extract_docx_text(src)

        elif suffix == ".txt":
            for enc in ("utf-8", "gbk", "gb2312"):
                try:
                    md_body = src.read_text(encoding=enc)
                    break
                except UnicodeDecodeError:
                    continue
            else:
                md_body = src.read_text(encoding="utf-8", errors="replace")

        else:
            return False

        dst.write_text(header + md_body, encoding="utf-8")
        return True

    except Exception as e:
        print(f"    ✗ 失败: {e}")
        dst.write_text(header + f"**转换失败**: {e}\n", encoding="utf-8")
        return False


# ── 主入口 ────────────────────────────────────────────────

def collect(dir_filter=None, single_file=None):
    if single_file:
        p = Path(single_file)
        if not p.is_absolute():
            p = REPO_ROOT / single_file
        return [p]
    files = []
    for f in sorted(RAW_DIR.rglob("*")):
        if not f.is_file():
            continue
        if f.suffix in SKIP_EXT or f.suffix.lower() in SKIP_EXT:
            continue
        if f.suffix.lower() not in SUPPORT_EXT:
            continue
        if "sources" in f.parts:
            continue  # 不递归处理输出目录
        if dir_filter and dir_filter not in str(f):
            continue
        files.append(f)
    return files


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir",   help="只处理包含此字符串的路径")
    parser.add_argument("--file",  help="单文件处理（调试用）")
    parser.add_argument("--force", action="store_true", help="强制覆盖已完成文件")
    args = parser.parse_args()

    import os
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        print("错误：请先设置 ANTHROPIC_API_KEY 环境变量")
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)
    files  = collect(args.dir, args.file)
    total  = len(files)
    print(f"共 {total} 个文件待处理，输出到 raw/sources/\n")

    done = skipped = 0
    for i, f in enumerate(files, 1):
        suffix = f.suffix.lower()
        needs_api = suffix in (".jpg", ".jpeg", ".png") or suffix == ".pdf"
        print(f"[{i}/{total}] {f.relative_to(RAW_DIR)}")

        result = convert_file(client, f, force=args.force)
        if result:
            done += 1
            print(f"    ✓")
            if needs_api:
                time.sleep(0.3)  # 避免触发速率限制
        else:
            skipped += 1
            print(f"    - 跳过（已存在）")

    print(f"\n完成 {done}，跳过 {skipped}，共 {total}")


if __name__ == "__main__":
    main()
