#!/usr/bin/env python3
"""
video_to_notes.py  —  llm-wiki 版
==================================
视频课程 → 转录 → 领域纠错 → GPT笔记 → raw/course/

改进（相对 Manus 原版）：
  1. 用 mlx-whisper large-v3 替换 manus-speech-to-text（M4 Native, 快3-5x）
  2. initial_prompt 注入 LLM 领域词表，消灭同音字误识别
  3. 转录后立即执行 CORRECTION_MAP 兜底纠错
  4. 新增 validate_transcript / validate_notes 质量门禁
  5. yt-dlp 自动携带 Chrome cookie（支持知乎登录墙）
  6. 同时输出 raw transcript 和 cleaned transcript
  7. 默认输出目录对齐 raw/course/

用法：
  python3 video_to_notes.py --input <视频或URL> --title "课程标题"
  python3 video_to_notes.py --transcript <已有转录> --title "课程标题"
"""

import argparse
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

# ── 路径 ─────────────────────────────────────────────────────────────────────
_HERE        = Path(__file__).parent
WORKER_SCRIPT = _HERE / "_gpt_worker.py"
MERGE_SCRIPT  = _HERE / "_gpt_merge.py"

# 项目根目录（scripts/ → transcribe/ → skills/ → .claude/ → llm-wiki-ai/）
_WIKI_ROOT   = _HERE.parent.parent.parent.parent
DEFAULT_RAW_DIR     = str(_WIKI_ROOT / "raw" / "course")
DEFAULT_CLEANED_DIR = str(_WIKI_ROOT / "cleaned" / "course" / "transcript")

# ── 配置 ─────────────────────────────────────────────────────────────────────
DEFAULT_MODEL   = "gpt-4.1-mini"
MAX_CHUNK_CHARS = 25_000
CHUNK_OVERLAP   = 200

# Whisper 领域词表：注入 initial_prompt，解决 LLM 技术术语误识别
INITIAL_PROMPT = (
    "自注意力机制，多头注意力，大语言模型，基座模型，"
    "Transformer，Embedding，位置编码，解码器，编码器，"
    "微调，预训练，强化学习，奖励模型，KV Cache，MLA，MoE，"
    "LoRA，QLoRA，Softmax，前馈网络，残差连接，带掩码，"
    "混合专家，知识蒸馏，量化，推理模型，DeepSeek，"
    "注意力头，查询向量，键向量，值向量，层归一化，"
    "词元，词表，上下文长度，自回归，因果掩码"
)

# 兜底纠错表：Whisper 仍可能漏掉的高频误识别
CORRECTION_MAP = {
    "自助理":   "自注意力",
    "大圆模型": "大语言模型",
    "机座模型": "基座模型",
    "代研码":   "带掩码",
    "技学习":   "机器学习",
    "瓷性":     "意思",
}

# 口语噪音：重复词收缩
_NOISE_PATTERNS = [
    (r'(这个){2,}', '这个'),
    (r'(就是){2,}', '就是'),
    (r'(然后){2,}', '然后'),
    (r'(所以){2,}', '所以'),
    (r'(其实){2,}', '其实'),
    (r'(可能){2,}', '可能'),
]


# ── 工具函数 ──────────────────────────────────────────────────────────────────

def log(msg: str):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def safe_filename(title: str) -> str:
    name = re.sub(r'[\\/:*?"<>|]', '_', title)
    name = re.sub(r'\s+', '_', name.strip())
    return name[:80]


def download_video(url: str, output_dir: str) -> str:
    """下载视频：yt-dlp + Chrome cookie（支持知乎等需要登录的平台）"""
    output_path = os.path.join(output_dir, "input_video.mp4")
    log(f"下载视频: {url}")

    r = subprocess.run(
        ["yt-dlp",
         "--cookies-from-browser", "chrome",   # 携带 Chrome 登录态
         "-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
         "--merge-output-format", "mp4",
         "-o", output_path, url],
        capture_output=True, text=True
    )
    if r.returncode == 0 and os.path.exists(output_path):
        log(f"下载成功: {output_path}")
        return output_path

    # 降级：wget 直链
    log(f"yt-dlp 失败，尝试 wget 直链...")
    r2 = subprocess.run(
        ["wget", "-q", "--show-progress", "-O", output_path, url],
        capture_output=True, text=True
    )
    if r2.returncode == 0 and os.path.exists(output_path):
        log(f"wget 成功: {output_path}")
        return output_path

    raise RuntimeError(
        f"视频下载失败。\n"
        f"yt-dlp: {r.stderr[:300]}\n"
        f"wget: {r2.stderr[:300]}\n"
        f"建议：在 Chrome 中登录知乎后重试，或手动下载后用 --input 传本地路径"
    )


def extract_audio(video_path: str, output_dir: str) -> str:
    """ffmpeg：视频 → 16kHz 单声道 WAV（Whisper 标准输入格式）"""
    audio_path = os.path.join(output_dir, "audio.wav")
    log(f"提取音频: {video_path} → {audio_path}")
    r = subprocess.run(
        ["ffmpeg", "-i", video_path,
         "-vn",                   # 去视频轨
         "-acodec", "pcm_s16le", # WAV 格式
         "-ar", "16000",         # 16kHz（Whisper 要求）
         "-ac", "1",             # 单声道
         "-y",                   # 覆盖已有文件
         audio_path],
        capture_output=True, text=True
    )
    if r.returncode != 0:
        raise RuntimeError(f"ffmpeg 音频提取失败:\n{r.stderr[:500]}")
    log(f"音频提取完成")
    return audio_path


def transcribe_mlx(audio_path: str) -> str:
    """mlx-whisper large-v3：带领域词表的转录（Apple M 系列原生加速）"""
    log("启动 mlx-whisper large-v3（首次运行需下载模型约 3GB）...")
    try:
        import mlx_whisper
    except ImportError:
        raise RuntimeError(
            "缺少 mlx-whisper。请先安装：pip install mlx-whisper"
        )

    result = mlx_whisper.transcribe(
        audio_path,
        path_or_hf_repo="mlx-community/whisper-large-v3-mlx",
        language="zh",
        initial_prompt=INITIAL_PROMPT,   # ← 领域词表注入
        verbose=False,
    )
    text = result["text"].strip()
    log(f"转录完成: {len(text)} 字符")
    return text


def correct_domain_errors(text: str) -> str:
    """兜底纠错：CORRECTION_MAP + 口语噪音收缩"""
    for wrong, right in CORRECTION_MAP.items():
        text = text.replace(wrong, right)
    for pattern, repl in _NOISE_PATTERNS:
        text = re.sub(pattern, repl, text)
    return text


def validate_transcript(text: str):
    """转录质量门禁：过短说明音频有问题"""
    if len(text) < 500:
        raise RuntimeError(
            f"转录内容过短（{len(text)} 字符），疑似音频静音或下载不完整"
        )
    residual = [w for w in CORRECTION_MAP if w in text]
    if residual:
        log(f"⚠️  转录中仍有疑似 ASR 错误（已知词表外）: {residual}")


def validate_notes(text: str):
    """笔记质量门禁：过短说明 GPT 调用失败"""
    if len(text) < 300:
        raise RuntimeError(
            f"笔记内容过短（{len(text)} 字符），疑似 GPT 调用失败"
        )
    residual = [w for w in CORRECTION_MAP if w in text]
    if residual:
        log(f"⚠️  最终笔记中残留疑似 ASR 词汇: {residual}，建议人工复核")


def chunk_text(text: str, max_chars: int, overlap: int) -> list:
    if len(text) <= max_chars:
        return [text]
    chunks, start = [], 0
    while start < len(text):
        end = min(start + max_chars, len(text))
        chunks.append(text[start:end])
        if end == len(text):
            break
        start = end - overlap
    return chunks


def gpt_summarize_chunks(chunks: list, title: str, model: str,
                          work_dir: str) -> list:
    parts, total = [], len(chunks)
    for i, chunk in enumerate(chunks):
        chunk_file = os.path.join(work_dir, f"chunk_{i}.txt")
        out_file   = os.path.join(work_dir, f"part_{i}.md")
        Path(chunk_file).write_text(chunk, encoding="utf-8")

        log(f"  GPT 整理 {i+1}/{total}（{len(chunk)} 字符）...")
        r = subprocess.run(
            [sys.executable, str(WORKER_SCRIPT),
             chunk_file, out_file, title, model, str(i), str(total)],
            capture_output=True, text=True, timeout=300
        )
        if r.returncode != 0:
            raise RuntimeError(f"GPT worker 失败（块 {i+1}）:\n{r.stderr[:500]}")
        print(r.stdout.strip())
        parts.append(Path(out_file).read_text(encoding="utf-8"))
    return parts


def gpt_merge(parts: list, title: str, model: str, work_dir: str) -> str:
    if len(parts) == 1:
        return parts[0]

    log(f"合并 {len(parts)} 段笔记...")
    combined_file = os.path.join(work_dir, "combined.txt")
    merged_file   = os.path.join(work_dir, "merged.md")
    combined = "\n\n---PART_SEPARATOR---\n\n".join(
        [f"【第{i+1}段】\n{p}" for i, p in enumerate(parts)]
    )
    Path(combined_file).write_text(combined, encoding="utf-8")

    r = subprocess.run(
        [sys.executable, str(MERGE_SCRIPT),
         combined_file, merged_file, title, model],
        capture_output=True, text=True, timeout=300
    )
    if r.returncode != 0:
        log(f"合并失败，直接拼接: {r.stderr[:200]}")
        return "\n\n".join(parts)

    print(r.stdout.strip())
    return Path(merged_file).read_text(encoding="utf-8")


def build_final_doc(title: str, body: str, source_url: str = "") -> str:
    now = datetime.now().strftime("%Y-%m-%d")
    source_line = f"\n> **来源**：{source_url}" if source_url else ""
    header = (
        f"# {title}\n\n"
        f"> **整理日期**：{now}  \n"
        f"> **工具**：video_to_notes.py（mlx-whisper large-v3 + GPT 整理）"
        f"{source_line}\n\n---\n\n"
    )
    footer = (
        "\n\n---\n\n"
        "*本笔记由 `video_to_notes.py` 自动生成，"
        "基于 mlx-whisper large-v3 语音转文字后经 GPT 整理而成。*"
    )
    return header + body + footer


def git_commit_and_push(repo_path: str, file_path: str, commit_msg: str):
    rel = os.path.relpath(file_path, repo_path)
    log(f"Git 提交: {rel}")
    for cmd in [
        ["git", "-C", repo_path, "add", rel],
        ["git", "-C", repo_path, "commit", "-m", commit_msg],
        ["git", "-C", repo_path, "push"],
    ]:
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            if "nothing to commit" in r.stdout + r.stderr:
                log("无变更，跳过提交。")
                return
            raise RuntimeError(f"Git 失败: {' '.join(cmd)}\n{r.stderr[:400]}")
    log("推送成功！")


# ── 主流程 ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="视频课程笔记工具（mlx-whisper + GPT）→ raw/course/"
    )
    parser.add_argument("--input", default="",
                        help="本地视频路径 或 URL（与 --transcript 二选一）")
    parser.add_argument("--title", required=True,
                        help="课程标题")
    parser.add_argument("--repo", default=str(_WIKI_ROOT.parent),
                        help="Git 仓库路径（默认: llm-wiki 根目录）")
    parser.add_argument("--raw-dir", default=DEFAULT_RAW_DIR,
                        help=f"笔记输出目录（默认: {DEFAULT_RAW_DIR}）")
    parser.add_argument("--cleaned-dir", default=DEFAULT_CLEANED_DIR,
                        help=f"清洗转录输出目录（默认: {DEFAULT_CLEANED_DIR}）")
    parser.add_argument("--model", default=DEFAULT_MODEL,
                        help=f"GPT 模型（默认: {DEFAULT_MODEL}）")
    parser.add_argument("--source-url", default="",
                        help="课程原始链接（写入笔记元信息）")
    parser.add_argument("--no-push", action="store_true",
                        help="不推送到 GitHub")
    parser.add_argument("--transcript", default="",
                        help="已有转录文件路径（跳过语音转文字）")
    args = parser.parse_args()

    if not args.input and not args.transcript:
        sys.exit("错误：必须提供 --input 或 --transcript 之一")

    os.makedirs(args.raw_dir, exist_ok=True)
    os.makedirs(args.cleaned_dir, exist_ok=True)
    fname = safe_filename(args.title)

    with tempfile.TemporaryDirectory() as tmpdir:

        # ── Step 1: 获取转录文本 ──────────────────────────────────────────────
        if args.transcript:
            log(f"使用已有转录: {args.transcript}")
            raw_text = Path(args.transcript).read_text(encoding="utf-8")
        else:
            if args.input.startswith(("http://", "https://")):
                video_path = download_video(args.input, tmpdir)
            else:
                video_path = args.input
                if not os.path.exists(video_path):
                    sys.exit(f"错误：文件不存在: {video_path}")

            audio_path   = extract_audio(video_path, tmpdir)
            raw_text     = transcribe_mlx(audio_path)

        validate_transcript(raw_text)

        # ── Step 2: 领域纠错 → 双轨输出 ──────────────────────────────────────
        cleaned_text = correct_domain_errors(raw_text)

        # 原始转录 → raw/course/transcript/
        raw_transcript_path = os.path.join(
            args.raw_dir, "transcript", fname + "_transcript.txt"
        )
        os.makedirs(os.path.dirname(raw_transcript_path), exist_ok=True)
        Path(raw_transcript_path).write_text(raw_text, encoding="utf-8")
        log(f"原始转录已写入: {raw_transcript_path}")

        # 清洗转录 → cleaned/course/transcript/
        cleaned_transcript_path = os.path.join(
            args.cleaned_dir, fname + "_transcript.txt"
        )
        Path(cleaned_transcript_path).write_text(cleaned_text, encoding="utf-8")
        log(f"清洗转录已写入: {cleaned_transcript_path}")

        # ── Step 3: GPT 整理 ──────────────────────────────────────────────────
        log(f"GPT 整理笔记（模型: {args.model}）...")
        chunks = chunk_text(cleaned_text, MAX_CHUNK_CHARS, CHUNK_OVERLAP)
        log(f"共 {len(cleaned_text)} 字符，分 {len(chunks)} 块")

        parts      = gpt_summarize_chunks(chunks, args.title, args.model, tmpdir)
        final_body = gpt_merge(parts, args.title, args.model, tmpdir)
        validate_notes(final_body)

        full_doc   = build_final_doc(args.title, final_body, args.source_url)

        # ── Step 4: 写入笔记 → raw/course/ ───────────────────────────────────
        note_path = os.path.join(args.raw_dir, fname + ".md")
        Path(note_path).write_text(full_doc, encoding="utf-8")
        log(f"笔记已写入: {note_path}")

        # ── Step 5: 推送到 GitHub ─────────────────────────────────────────────
        if not args.no_push:
            git_commit_and_push(
                args.repo, note_path,
                f"feat: 自动生成课程笔记《{args.title}》"
            )
            for path in [raw_transcript_path, cleaned_transcript_path]:
                try:
                    git_commit_and_push(
                        args.repo, path,
                        f"chore: 转录缓存《{args.title}》"
                    )
                except Exception:
                    pass
        else:
            log("--no-push 模式，跳过推送。")

        log("=" * 50)
        log(f"完成！笔记: {note_path}")
        log("=" * 50)
        return note_path


if __name__ == "__main__":
    main()
