#!/usr/bin/env python3
"""
_gpt_worker.py  —  子进程：单块转录文本 → Claude 整理笔记
用法：python3 _gpt_worker.py <input> <output> <title> <model> <idx> <total>
注：model 参数保留兼容性，实际使用 claude CLI（无需 API key）
"""
import sys
import subprocess
from pathlib import Path


SYSTEM_PROMPT = (
    "你是一位专业的 LLM 应用领域博士级技术笔记整理专家。\n"
    "请将提供的课程转录文本整理为高质量的技术笔记，要求：\n"
    "1. 使用 Markdown 格式，包含清晰的层级标题（##、###）\n"
    "2. 核心概念和原理用完整段落阐述，避免过多列表\n"
    "3. 技术对比使用 Markdown 表格\n"
    "4. 保留所有具体案例、数字和类比\n"
    "5. 用**加粗**标注关键术语\n"
    "6. 如有公式，使用 LaTeX 行内格式 $...$ 表示\n"
    "7. 语言精炼专业，去除口语化表达和重复内容\n"
    "8. 技术术语使用标准写法：自注意力机制、多头注意力、大语言模型、"
    "带掩码的多头注意力、混合专家模型等；"
    "如发现疑似语音识别错误（如'自助理'应为'自注意力'），请主动纠正\n"
    "只输出笔记内容本身，不引用外部知识库，不添加额外说明。"
)


def main():
    if len(sys.argv) < 7:
        sys.exit("用法: _gpt_worker.py <input> <output> <title> <model> <idx> <total>")

    input_file  = sys.argv[1]
    output_file = sys.argv[2]
    title       = sys.argv[3]
    # sys.argv[4] = model (保留兼容性，不使用)
    chunk_index = int(sys.argv[5])
    total       = int(sys.argv[6])

    chunk = Path(input_file).read_text(encoding="utf-8")
    position_hint = f"（第 {chunk_index+1}/{total} 段）" if total > 1 else ""

    user_content = (
        f"课程标题：《{title}》{position_hint}\n\n"
        f"以下是课程转录文本，请整理为技术笔记：\n\n"
        f"```\n{chunk}\n```"
    )

    r = subprocess.run(
        ["claude", "-p",
         "--system-prompt", SYSTEM_PROMPT,
         "--dangerously-skip-permissions",
         user_content],
        capture_output=True, text=True, timeout=300
    )

    if r.returncode != 0:
        sys.exit(f"[worker] claude CLI 失败:\n{r.stderr[:400]}")

    result = r.stdout.strip()
    if not result:
        sys.exit(f"[worker] claude CLI 无输出，stderr: {r.stderr[:200]}")

    Path(output_file).write_text(result, encoding="utf-8")
    print(f"[worker] 块 {chunk_index+1}/{total} 完成，{len(result)} 字符")


if __name__ == "__main__":
    main()
