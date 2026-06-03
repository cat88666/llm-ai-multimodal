# transcribe 技能

## 核心目标

视频课程 → mlx-whisper 转录 → 领域纠错 → GPT 整理笔记 → `raw/course/`

产出双轨文件：
- 原始转录 → `raw/course/transcript/<title>_transcript.txt`
- 清洗转录 → `cleaned/course/transcript/<title>_transcript.txt`
- GPT 笔记 → `raw/course/<title>.md`

## 触发条件

- 用户要求"转录视频"、"把视频转成笔记"、"处理课程视频"

## 一次性环境安装（仅首次）

```bash
brew install ffmpeg
pip install yt-dlp mlx-whisper openai
```

mlx-whisper 首次运行会自动下载 whisper-large-v3-mlx 模型（约 3GB）。

## 使用方法

### 场景 1：从 URL 下载并转录（知乎等需要登录的平台）

```bash
python3 .claude/skills/transcribe/scripts/video_to_notes.py \
  --input "https://www.zhihu.com/xen/market/training/..." \
  --title "课程标题" \
  --source-url "https://..." \
  [--no-push]
```

**注意**：下载知乎视频前，确保 Chrome 已登录知乎。脚本通过 `--cookies-from-browser chrome` 自动读取登录态。

### 场景 2：本地视频文件

```bash
python3 .claude/skills/transcribe/scripts/video_to_notes.py \
  --input /path/to/video.mp4 \
  --title "课程标题" \
  [--no-push]
```

### 场景 3：复用已有转录（跳过 ASR）

```bash
python3 .claude/skills/transcribe/scripts/video_to_notes.py \
  --transcript raw/course/transcript/xxx_transcript.txt \
  --title "课程标题" \
  [--no-push]
```

## 核心改进（相对 Manus 原版）

| 问题 | Manus 原版 | 本版 |
|------|-----------|------|
| ASR 模型 | manus-speech-to-text（黑盒） | mlx-whisper large-v3（可控） |
| 领域词表 | 无 | initial_prompt 注入 LLM 术语 |
| 兜底纠错 | 无 | CORRECTION_MAP（自注意力等） |
| 转录验证 | 仅检查文件存在 | 长度门禁 + 残留错误警告 |
| 笔记验证 | 无 | 长度门禁 + 术语残留检查 |
| 知乎下载 | 无 cookie 支持 | --cookies-from-browser chrome |
| 音频提取 | 直接传视频给 ASR | ffmpeg → 16kHz 单声道 WAV |
| 输出路径 | notes/ | raw/course/ + cleaned/course/ |

## 常见问题

**yt-dlp 下载失败（知乎 403）**  
→ 在 Chrome 中重新登录知乎，再重试

**mlx-whisper 报错 ImportError**  
→ `pip install mlx-whisper`

**ffmpeg not found**  
→ `brew install ffmpeg`

**转录过短警告**  
→ 检查视频文件完整性，或用 ffmpeg 单独测试音频提取

**GPT 笔记过短**  
→ 检查 OPENAI_API_KEY 是否设置；可用 --model gpt-4o 提升质量
