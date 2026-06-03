#!/usr/bin/env python3
"""
PDF 转 Markdown

文字型 PDF：pymupdf 提取文字层 → AI 格式化
扫描型 PDF：每页渲染为图片 → AI 图片识别（自动判断）

独立运行：
  python3 skills/pdf转md/scripts/pdf_to_md.py
  python3 skills/pdf转md/scripts/pdf_to_md.py --file raw/test/测试文件.pdf
  python3 skills/pdf转md/scripts/pdf_to_md.py --force
"""

import argparse
import base64
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
图片提示词    = (PROMPT_DIR / "image_to_md.md").read_text(encoding="utf-8")
文字提示词模板 = (PROMPT_DIR / "text_to_md.md").read_text(encoding="utf-8")


# ── 核心提取 ──────────────────────────────────────────────

def 提取PDF文字(文件路径: Path) -> str | None:
    """提取文字层；文字过少则为扫描件，返回 None。"""
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


def PDF页面转图片(文件路径: Path) -> list[tuple[str, str]]:
    """扫描件：每页渲染为 base64 图片。"""
    import fitz
    文档 = fitz.open(str(文件路径))
    图片列表 = []
    for 页 in 文档:
        像素图 = 页.get_pixmap(dpi=150)
        编码数据 = base64.standard_b64encode(像素图.tobytes("jpeg")).decode()
        图片列表.append(("image/jpeg", 编码数据))
    文档.close()
    return 图片列表


def 调用图片识别(客户端: anthropic.Anthropic, 媒体类型: str, 图片数据: str) -> str:
    响应 = 客户端.messages.create(
        model=模型,
        max_tokens=4096,
        system=[{"type": "text", "text": 系统提示词,
                 "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": [
            {"type": "image", "source": {
                "type": "base64", "media_type": 媒体类型, "data": 图片数据}},
            {"type": "text", "text": 图片提示词},
        ]}],
    )
    return 响应.content[0].text.strip()


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
    """转换单个 PDF。目标文件父目录由调用方负责创建。"""
    try:
        文字内容 = 提取PDF文字(源文件)
        if 文字内容 is None:
            图片列表 = PDF页面转图片(源文件)
            页面md列表 = []
            for i, (媒体类型, 数据) in enumerate(图片列表):
                页面md列表.append(f"<!-- 第{i+1}页 -->\n\n{调用图片识别(客户端, 媒体类型, 数据)}")
                time.sleep(0.2)
            md内容 = "\n\n---\n\n".join(页面md列表)
        else:
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
        文件 for 文件 in sorted(RAW_DIR.rglob("*.pdf"))
        if 文件.is_file() and "output" not in 文件.parts
    ]



def 读取密钥() -> str:
    env文件 = TOOL_ROOT / ".env"
    if env文件.exists():
        for 行 in env文件.read_text(encoding="utf-8").splitlines():
            行 = 行.strip()
            if 行.startswith("ANTHROPIC_API_KEY="):
                return 行.split("=", 1)[1].strip()
    return ""

def main():
    解析器 = argparse.ArgumentParser(description="PDF 转 Markdown")
    解析器.add_argument("--file",  help="只处理单个文件")
    解析器.add_argument("--force", action="store_true", help="强制覆盖已存在的输出文件")
    参数 = 解析器.parse_args()

    密钥 = os.environ.get("ANTHROPIC_API_KEY", "") or 读取密钥()
    if not 密钥:
        print("错误：未找到 ANTHROPIC_API_KEY，请在项目根目录创建 .env 文件")
        sys.exit(1)

    客户端 = anthropic.Anthropic(api_key=密钥)
    文件列表 = 收集文件(参数.file)
    总数 = len(文件列表)
    print(f"共 {总数} 个 PDF 文件待处理\n")

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
