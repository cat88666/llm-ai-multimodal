#!/usr/bin/env python3
"""
图片转 Markdown（支持 .jpg .jpeg .png）
tesseract OCR 本地识别，支持中文，无需 API Key。
"""
import argparse
from pathlib import Path

TOOL_ROOT = Path(__file__).parent.parent.parent.parent
RAW_DIR   = TOOL_ROOT / "raw"
OUT_DIR   = TOOL_ROOT / "output"
支持格式  = {".jpg", ".jpeg", ".png"}


def 转换单文件(源文件: Path, 目标文件: Path) -> bool:
    import pytesseract
    文字 = pytesseract.image_to_string(str(源文件), lang="chi_sim+eng").strip()
    目标文件.write_text(文字, encoding="utf-8")
    return True


def 收集文件(单文件=None):
    if 单文件:
        p = Path(单文件)
        return [p if p.is_absolute() else TOOL_ROOT / 单文件]
    return [f for f in sorted(RAW_DIR.rglob("*"))
            if f.is_file() and f.suffix.lower() in 支持格式
            and "output" not in f.parts]


def main():
    p = argparse.ArgumentParser(description="图片转 Markdown")
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
