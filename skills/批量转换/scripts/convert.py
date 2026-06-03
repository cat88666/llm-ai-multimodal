#!/usr/bin/env python3
"""
批量转换 — 将指定目录下所有文件转换为 Markdown

特性：
  - 自动识别文件格式，调用对应技能脚本
  - 实时写入 output/output.log
  - 中断后再次运行自动跳过已完成文件（断点续传）
  - --force 忽略日志记录，强制重新转换所有文件

用法：
  python3 skills/批量转换/scripts/convert.py raw/test
  python3 skills/批量转换/scripts/convert.py /Users/mac/ai/llm-ai/llm-ai-qingan/raw/一审
  python3 skills/批量转换/scripts/convert.py raw/test --force
  python3 skills/批量转换/scripts/convert.py raw/test --output /自定义/输出目录

输出目录推导规则（未指定 --output 时）：
  raw/test                            →  <本项目>/output/test
  /path/to/其他项目/raw/一审           →  /path/to/其他项目/output/一审
"""

import argparse
import importlib.util
import logging
import os
import sys
import time
from pathlib import Path

import anthropic

# ── 路径（脚本位于 skills/批量转换/scripts/，项目根向上四级）──
TOOL_ROOT = Path(__file__).parent.parent.parent.parent
LOG_FILE  = TOOL_ROOT / "output" / "output.log"

支持格式 = {
    ".pdf":  ("pdf转md",  "pdf_to_md.py"),
    ".docx": ("word转md", "word_to_md.py"),
    ".jpg":  ("图片转md", "img_to_md.py"),
    ".jpeg": ("图片转md", "img_to_md.py"),
    ".png":  ("图片转md", "img_to_md.py"),
    ".txt":  ("文本转md", "txt_to_md.py"),
}

格式标签 = {
    ".pdf":  "PDF ",
    ".docx": "Word",
    ".jpg":  "图片",
    ".jpeg": "图片",
    ".png":  "图片",
    ".txt":  "文本",
}


# ── 日志 ──────────────────────────────────────────────────

def 初始化日志() -> logging.Logger:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    记录器 = logging.getLogger("批量转换")
    记录器.setLevel(logging.INFO)
    记录器.handlers.clear()
    格式器 = logging.Formatter("[%(asctime)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    文件处理器 = logging.FileHandler(LOG_FILE, encoding="utf-8", mode="a")
    文件处理器.setFormatter(格式器)
    终端处理器 = logging.StreamHandler(sys.stdout)
    终端处理器.setFormatter(格式器)
    记录器.addHandler(文件处理器)
    记录器.addHandler(终端处理器)
    return 记录器


# ── 断点续传：从日志读取已完成文件 ───────────────────────

def 读取已完成文件(日志文件: Path) -> set[Path]:
    """
    解析日志，返回已成功转换的源文件绝对路径集合。
    日志中成功行格式：... → 成功 | /绝对路径/文件名
    """
    已完成: set[Path] = set()
    if not 日志文件.exists():
        return 已完成
    for 行 in 日志文件.read_text(encoding="utf-8").splitlines():
        if "→ 成功" in 行 and " | " in 行:
            try:
                路径字符串 = 行.split(" | ", 1)[-1].strip()
                已完成.add(Path(路径字符串).resolve())
            except Exception:
                pass
    return 已完成


# ── 技能动态加载 ──────────────────────────────────────────

_技能函数缓存: dict = {}

def 获取技能函数(后缀: str):
    if 后缀 not in _技能函数缓存:
        技能目录名, 脚本名 = 支持格式[后缀]
        脚本路径 = TOOL_ROOT / "skills" / 技能目录名 / "scripts" / 脚本名
        spec = importlib.util.spec_from_file_location(脚本名, str(脚本路径))
        模块 = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(模块)
        _技能函数缓存[后缀] = 模块.转换单文件
    return _技能函数缓存[后缀]


# ── 输出目录推导 ──────────────────────────────────────────

def 推导输出目录(输入目录: Path) -> Path:
    路径 = str(输入目录.resolve())
    if "/raw/" in 路径:
        return Path(路径.replace("/raw/", "/output/", 1))
    if 路径.endswith("/raw"):
        return Path(路径[:-3] + "output")
    return 输入目录.resolve().parent / "output" / 输入目录.resolve().name


# ── 主转换流程 ────────────────────────────────────────────

def 执行转换(输入目录: Path, 输出目录: Path, 强制覆盖: bool, 记录器: logging.Logger):
    密钥 = os.environ.get("ANTHROPIC_API_KEY", "")
    if not 密钥:
        记录器.error("错误：请先设置 ANTHROPIC_API_KEY 环境变量")
        sys.exit(1)

    客户端 = anthropic.Anthropic(api_key=密钥)

    # 收集待处理文件
    文件列表 = sorted([
        文件 for 文件 in 输入目录.rglob("*")
        if 文件.is_file() and 文件.suffix.lower() in 支持格式
    ])
    总数 = len(文件列表)

    # 断点续传：读取已完成记录
    已完成文件集 = set() if 强制覆盖 else 读取已完成文件(LOG_FILE)
    待处理文件 = [f for f in 文件列表 if f.resolve() not in 已完成文件集]
    已跳过数 = 总数 - len(待处理文件)

    开始时间 = time.time()
    记录器.info("=" * 55)
    记录器.info(f"输入目录：{输入目录.resolve()}")
    记录器.info(f"输出目录：{输出目录}")
    if 已跳过数 > 0:
        记录器.info(f"共 {总数} 个文件，已完成 {已跳过数} 个，本次处理 {len(待处理文件)} 个")
    else:
        记录器.info(f"共 {总数} 个文件待处理")
    记录器.info("-" * 55)

    完成数 = 失败数 = 0

    for i, 源文件 in enumerate(待处理文件, 1):
        后缀 = 源文件.suffix.lower()
        标签 = 格式标签[后缀]
        相对路径 = 源文件.relative_to(输入目录)
        目标文件 = 输出目录 / 相对路径.with_suffix(".md")
        前缀 = f"[{已跳过数 + i}/{总数}][{标签}] {源文件.name}"

        目标文件.parent.mkdir(parents=True, exist_ok=True)

        try:
            转换函数 = 获取技能函数(后缀)
            转换函数(客户端, 源文件, 目标文件)
            完成数 += 1
            # 日志末尾附绝对路径，供下次断点续传解析
            记录器.info(f"{前缀} → 成功 | {源文件.resolve()}")
            time.sleep(0.3)
        except Exception as 错误:
            失败数 += 1
            记录器.error(f"{前缀} → 失败：{错误} | {源文件.resolve()}")

    耗时 = time.time() - 开始时间
    记录器.info("-" * 55)
    记录器.info(
        f"本次完成 {完成数}  失败 {失败数}  历史跳过 {已跳过数}  "
        f"总计 {总数}  耗时 {耗时:.1f} 秒"
    )
    记录器.info("=" * 55)


# ── 入口 ──────────────────────────────────────────────────

def main():
    解析器 = argparse.ArgumentParser(
        description="批量转换目录下所有文件为 Markdown（支持断点续传）"
    )
    解析器.add_argument("输入目录", help="待转换的目录路径（相对或绝对路径均可）")
    解析器.add_argument("--output", help="自定义输出目录（默认根据输入路径自动推导）")
    解析器.add_argument(
        "--force", action="store_true",
        help="忽略日志，强制重新转换所有文件"
    )
    参数 = 解析器.parse_args()

    输入目录 = Path(参数.输入目录)
    if not 输入目录.is_absolute():
        输入目录 = TOOL_ROOT / 输入目录
    输入目录 = 输入目录.resolve()

    if not 输入目录.exists():
        print(f"错误：目录不存在 → {输入目录}")
        sys.exit(1)

    输出目录 = Path(参数.output).resolve() if 参数.output else 推导输出目录(输入目录)
    记录器 = 初始化日志()
    执行转换(输入目录, 输出目录, 参数.force, 记录器)


if __name__ == "__main__":
    main()
