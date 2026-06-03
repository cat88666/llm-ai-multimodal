#!/usr/bin/env python3
"""
Word 转 Markdown（支持 .docx）

python-docx 提取段落和表格 → AI 格式化 → Markdown

独立运行：
  python3 skills/word转md/scripts/word_to_md.py
  python3 skills/word转md/scripts/word_to_md.py --file raw/test/测试文件.docx
  python3 skills/word转md/scripts/word_to_md.py --force
"""

import argparse
import os
import sys
import time
from pathlib import Path

import anthropic

# ── 路径 ──────────────────────────────────────────────────
TOOL_ROOT  = Path(__file__).parent.parent.parent.parent
RAW_DIR    = TOOL_ROOT / "raw"
OUT_DIR    = TOOL_ROOT / "output"
PROMPT_DIR = TOOL_ROOT / "skills" / "api提示词"

模型 = "claude-haiku-4-5-20251001"

系统提示词    = (PROMPT_DIR / "system.md").read_text(encoding="utf-8")
文字提示词模板 = (PROMPT_DIR / "text_to_md.md").read_text(encoding="utf-8")


# ── 核心提取 ──────────────────────────────────────────────

def 提取Word内容(文件路径: Path) -> str:
    """提取段落与表格，保留文档结构。"""
    import docx
    文档 = docx.Document(str(文件路径))
    内容列表 = []
    for 块 in 文档.element.body:
        标签 = 块.tag.split("}")[-1]
        if 标签 == "p":
            段落 = docx.text.paragraph.Paragraph(块, 文档)
            if 段落.text.strip():
                内容列表.append(段落.text)
        elif 标签 == "tbl":
            from docx.table import Table
            表格 = Table(块, 文档)
            行列表 = []
            for i, 行 in enumerate(表格.rows):
                单元格列表 = [单元格.text.strip().replace("\n", " ") for 单元格 in 行.cells]
                行列表.append("| " + " | ".join(单元格列表) + " |")
                if i == 0:
                    行列表.append("|" + "|".join(["---"] * len(单元格列表)) + "|")
            内容列表.append("\n".join(行列表))
    return "\n\n".join(内容列表)


def 调用文字格式化(客户端: anthropic.Anthropic, 内容: str) -> str:
    响应 = 客户端.messages.create(
        model=模型,
        max_tokens=4096,
        system=[{"type": "text", "text": 系统提示词,
                 "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": 文字提示词模板.format(content=内容)}],
    )
    return 响应.content[0].text.strip()


# ── 对外接口（供 convert.py 调用）────────────────────────

def 转换单文件(客户端: anthropic.Anthropic, 源文件: Path, 目标文件: Path) -> bool:
    """转换单个 Word 文件。目标文件父目录由调用方负责创建。"""
    try:
        文字内容 = 提取Word内容(源文件)
        md内容 = 调用文字格式化(客户端, 文字内容)
        目标文件.write_text(md内容, encoding="utf-8")
        return True
    except Exception as 错误:
        目标文件.write_text(f"**转换失败**：{错误}\n", encoding="utf-8")
        raise


# ── 独立运行入口 ──────────────────────────────────────────

def 收集文件(单文件: str = None) -> list[Path]:
    if 单文件:
        路径 = Path(单文件)
        return [路径 if 路径.is_absolute() else TOOL_ROOT / 单文件]
    return [
        文件 for 文件 in sorted(RAW_DIR.rglob("*.docx"))
        if 文件.is_file() and "output" not in 文件.parts
    ]


def main():
    解析器 = argparse.ArgumentParser(description="Word 转 Markdown")
    解析器.add_argument("--file",  help="只处理单个文件")
    解析器.add_argument("--force", action="store_true", help="强制覆盖已存在的输出文件")
    参数 = 解析器.parse_args()

    密钥 = os.environ.get("ANTHROPIC_API_KEY", "")
    if not 密钥:
        print("错误：请先设置 ANTHROPIC_API_KEY 环境变量")
        sys.exit(1)

    客户端 = anthropic.Anthropic(api_key=密钥)
    文件列表 = 收集文件(参数.file)
    总数 = len(文件列表)
    print(f"共 {总数} 个 Word 文件待处理\n")

    完成数 = 跳过数 = 0
    for i, 文件 in enumerate(文件列表, 1):
        相对路径 = 文件.relative_to(RAW_DIR)
        目标文件 = OUT_DIR / 相对路径.with_suffix(".md")
        print(f"[{i}/{总数}] {文件.relative_to(TOOL_ROOT)}")

        if 目标文件.exists() and not 参数.force:
            跳过数 += 1
            print("    - 跳过（已存在）")
            continue

        目标文件.parent.mkdir(parents=True, exist_ok=True)
        try:
            转换单文件(客户端, 文件, 目标文件)
            完成数 += 1
            print("    ✓")
            time.sleep(0.3)
        except Exception as 错误:
            print(f"    ✗ 失败：{错误}")

    print(f"\n完成 {完成数}，跳过 {跳过数}，共 {总数}")


if __name__ == "__main__":
    main()
