# llm-ai-multimodal

AI 多模态文件转 Markdown 工具。将 `raw/` 目录下的文件完整转换为 Markdown，文字内容与原文件保持一致。

## 支持格式

| 格式 | 技能 | 处理方式 |
|------|------|---------|
| `.pdf` | pdf转md | pymupdf 提取文字层 → AI 格式化；扫描件自动转图片识别 |
| `.jpg` / `.png` | 图片转md | AI 图片文字识别 |
| `.docx` | word转md | python-docx 提取段落和表格 → AI 格式化 |
| `.txt` | 文本转md | 自动检测编码读取 → AI 格式化 |

## 目录结构

```
llm-ai-multimodal/
├── raw/                          # 放置待转换的原始文件
├── output/                       # 转换结果（自动创建）
├── prompts/                      # 提示词模板（四个技能共用）
│   ├── system.md
│   ├── image_to_md.md
│   └── text_to_md.md
├── skills/                       # 每种格式独立一个技能
│   ├── pdf转md/
│   │   ├── SKILL.md
│   │   └── scripts/pdf_to_md.py
│   ├── 图片转md/
│   │   ├── SKILL.md
│   │   └── scripts/img_to_md.py
│   ├── word转md/
│   │   ├── SKILL.md
│   │   └── scripts/word_to_md.py
│   └── 文本转md/
│       ├── SKILL.md
│       └── scripts/txt_to_md.py
└── requirements.txt
```

## 快速开始

```bash
# 第一步：安装依赖
pip install -r requirements.txt

# 第二步：设置 API 密钥
export ANTHROPIC_API_KEY=sk-ant-...

# 转换 PDF
python3 skills/pdf转md/scripts/pdf_to_md.py

# 转换图片
python3 skills/图片转md/scripts/img_to_md.py

# 转换 Word
python3 skills/word转md/scripts/word_to_md.py

# 转换纯文本
python3 skills/文本转md/scripts/txt_to_md.py

# 只转换单个文件
python3 skills/pdf转md/scripts/pdf_to_md.py --file raw/test/测试文件.pdf

# 强制覆盖已存在的输出文件
python3 skills/pdf转md/scripts/pdf_to_md.py --force
```

## 输出

每个输入文件在 `output/` 目录下生成同名的 `.md` 文件：

```
raw/test/测试文件.pdf   →  output/test/测试文件.md
raw/test/测试文件.jpg   →  output/test/测试文件.md
```
