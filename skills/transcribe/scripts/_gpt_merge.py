#!/usr/bin/env python3
"""
_gpt_merge.py  —  子进程：多段笔记 → 合并为完整文档
用法：python3 _gpt_merge.py <combined_file> <output_file> <title> <model>
"""
import sys
import subprocess
from pathlib import Path


SYSTEM_PROMPT = (
    "你是一位专业的技术文档编辑。请将多段课程笔记合并为一份完整、连贯、无重复的技术笔记文档。\n"
    "要求：\n"
    "1. 合并相同或相近的章节，消除重复内容\n"
    "2. 保持逻辑顺序，确保知识点的递进关系\n"
    "3. 输出完整的 Markdown 文档，包含所有核心内容、原理、案例和总结\n"
    "4. 文档结构建议：概述 → 核心原理 → 技术细节 → 案例分析 → 总结\n"
    "5. 使用完整段落和表格，避免过多列表\n"
    "6. 确保所有技术术语使用标准写法（自注意力、大语言模型、带掩码的多头注意力等）\n"
    "只输出合并后的笔记文档本身，不添加说明文字。"
)


def main():
    if len(sys.argv) < 5:
        sys.exit("用法: _gpt_merge.py <combined_file> <output_file> <title> <model>")

    combined_file = sys.argv[1]
    output_file   = sys.argv[2]
    title         = sys.argv[3]
    # sys.argv[4] = model (保留兼容性，不使用)

    combined = Path(combined_file).read_text(encoding="utf-8")

    user_content = (
        f"课程标题：《{title}》\n\n"
        f"以下是分段整理的笔记（用 ---PART_SEPARATOR--- 分隔），请合并为一份完整文档：\n\n"
        f"{combined}"
    )

    r = subprocess.run(
        ["claude", "-p",
         "--system-prompt", SYSTEM_PROMPT,
         "--dangerously-skip-permissions",
         user_content],
        capture_output=True, text=True, timeout=600
    )

    if r.returncode != 0:
        sys.exit(f"[merge] claude CLI 失败:\n{r.stderr[:400]}")

    result = r.stdout.strip()
    if not result:
        sys.exit(f"[merge] claude CLI 无输出，stderr: {r.stderr[:200]}")

    Path(output_file).write_text(result, encoding="utf-8")
    print(f"[merge] 合并完成，{len(result)} 字符")


if __name__ == "__main__":
    main()
