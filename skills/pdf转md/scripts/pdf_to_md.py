#!/usr/bin/env python3
"""
PDF 转 Markdown
文字层：pymupdf 直接提取，无需 AI。
扫描件：pymupdf 渲染 + tesseract OCR，无需 API Key。
"""
import argparse, tempfile
from pathlib import Path

TOOL_ROOT = Path(__file__).parent.parent.parent.parent
RAW_DIR   = TOOL_ROOT / "raw"
OUT_DIR   = TOOL_ROOT / "output"


def 提取文字层(文件路径: Path) -> str | None:
    import fitz
    文档 = fitz.open(str(文件路径))
    页面列表 = []
    for i, 页 in enumerate(文档):
        文字 = 页.get_text().strip()
        if 文字:
            页面列表.append(f"<!-- 第{i+1}页 -->\n{文字}")
    文档.close()
    结果 = "\n\n---\n\n".join(页面列表)
    return 结果 if len(结果.strip()) >= 50 else None


def 扫描件OCR(文件路径: Path) -> str:
    import fitz, pytesseract
    文档 = fitz.open(str(文件路径))
    页面列表 = []
    with tempfile.TemporaryDirectory() as 临时目录:
        for i, 页 in enumerate(文档):
            像素图 = 页.get_pixmap(dpi=150)
            临时图片 = Path(临时目录) / f"page_{i+1}.jpg"
            像素图.save(str(临时图片))
            文字 = pytesseract.image_to_string(str(临时图片), lang="chi_sim+eng").strip()
            if 文字:
                页面列表.append(f"<!-- 第{i+1}页 -->\n{文字}")
    文档.close()
    return "\n\n---\n\n".join(页面列表)


def 转换单文件(源文件: Path, 目标文件: Path) -> bool:
    文字 = 提取文字层(源文件)
    if 文字 is None:
        文字 = 扫描件OCR(源文件)
    目标文件.write_text(文字, encoding="utf-8")
    return True


def 收集文件(单文件=None):
    if 单文件:
        p = Path(单文件)
        return [p if p.is_absolute() else TOOL_ROOT / 单文件]
    return [f for f in sorted(RAW_DIR.rglob("*.pdf"))
            if f.is_file() and "output" not in f.parts]


def main():
    p = argparse.ArgumentParser(description="PDF 转 Markdown")
    p.add_argument("--file"); p.add_argument("--force", action="store_true")
    args = p.parse_args()
    文件列表 = 收集文件(args.file)
    完成数 = 跳过数 = 0
    for i, f in enumerate(文件列表, 1):
        dst = OUT_DIR / f.relative_to(RAW_DIR).with_suffix(".md")
        print(f"[{i}/{len(文件列表)}] {f.relative_to(TOOL_ROOT)}")
        if dst.exists() and not args.force:
            跳过数 += 1; print("    - 跳过"); continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        try:
            转换单文件(f, dst); 完成数 += 1; print("    ✓")
        except Exception as e:
            print(f"    ✗ {e}")
    print(f"\n完成 {完成数}，跳过 {跳过数}，共 {len(文件列表)}")

if __name__ == "__main__":
    main()
