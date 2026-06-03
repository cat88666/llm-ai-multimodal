#!/usr/bin/env python3
"""
图片转 Markdown（支持 .jpg .jpeg .png）

图片 → AI 图片识别 → Markdown

独立运行：
  python3 skills/图片转md/scripts/img_to_md.py
  python3 skills/图片转md/scripts/img_to_md.py --file raw/test/测试文件.jpg
  python3 skills/图片转md/scripts/img_to_md.py --force
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
TOOL_ROOT  = Path(__file__).parent.parent.parent.parent
RAW_DIR    = TOOL_ROOT / "raw"
OUT_DIR    = TOOL_ROOT / "output"
PROMPT_DIR = TOOL_ROOT / "skills" / "api提示词"

模型       = "claude-haiku-4-5-20251001"
图片最大像素 = 1568
支持格式    = {".jpg", ".jpeg", ".png"}

系统提示词 = (PROMPT_DIR / "system.md").read_text(encoding="utf-8")
图片提示词 = (PROMPT_DIR / "image_to_md.md").read_text(encoding="utf-8")


# ── 核心处理 ──────────────────────────────────────────────

def 图片转base64(文件路径: Path) -> tuple[str, str]:
    """压缩超大图片并编码为 base64。"""
    图片 = Image.open(str(文件路径))
    if 图片.mode not in ("RGB", "L"):
        图片 = 图片.convert("RGB")
    宽, 高 = 图片.size
    if max(宽, 高) > 图片最大像素:
        比例 = 图片最大像素 / max(宽, 高)
        图片 = 图片.resize((int(宽 * 比例), int(高 * 比例)), Image.LANCZOS)
    缓冲区 = io.BytesIO()
    图片.save(缓冲区, format="JPEG", quality=85)
    return "image/jpeg", base64.standard_b64encode(缓冲区.getvalue()).decode()


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


# ── 对外接口（供 convert.py 调用）────────────────────────

def 转换单文件(客户端: anthropic.Anthropic, 源文件: Path, 目标文件: Path) -> bool:
    """转换单张图片。目标文件父目录由调用方负责创建。"""
    try:
        媒体类型, 图片数据 = 图片转base64(源文件)
        md内容 = 调用图片识别(客户端, 媒体类型, 图片数据)
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
        文件 for 文件 in sorted(RAW_DIR.rglob("*"))
        if 文件.is_file()
        and 文件.suffix.lower() in 支持格式
        and "output" not in 文件.parts
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
    解析器 = argparse.ArgumentParser(description="图片转 Markdown")
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
    print(f"共 {总数} 个图片文件待处理\n")

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
