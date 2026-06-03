# llm-ai-multimodal

AI 多模态文件转 Markdown 工具。将 `raw/` 目录下的文件完整转换为 Markdown，文字内容与原文件保持一致。

## 支持格式

| 格式 | 处理方式 |
|------|---------|
| `.txt` | 本地读取 → AI 格式化为 Markdown |
| `.docx` | 本地提取段落和表格 → AI 格式化为 Markdown |
| `.pdf` | 本地提取文字层 → AI 格式化为 Markdown；扫描件自动识别并转图片识别 |
| `.jpg` / `.png` | AI 图片文字识别 → Markdown |

## 目录结构

```
llm-ai-multimodal/
├── raw/           # 放置待转换的原始文件
├── output/        # 转换结果（自动创建，与 raw/ 目录结构一致）
├── prompts/       # 提示词模板
│   ├── system.md        # 系统提示词
│   ├── image_to_md.md   # 图片识别提示词
│   └── text_to_md.md    # 文字格式化提示词
├── convert.py     # 主入口
└── requirements.txt
```

## 快速开始

```bash
# 第一步：安装依赖
pip install -r requirements.txt

# 第二步：设置 API 密钥
export ANTHROPIC_API_KEY=sk-ant-...

# 第三步：转换 raw/ 下所有文件
python convert.py

# 只转换单个文件（调试用）
python convert.py --file raw/测试文件.pdf

# 强制覆盖已存在的输出文件
python convert.py --force
```

## 输出

每个输入文件在 `output/` 目录下生成同名的 `.md` 文件：

```
raw/测试文件.pdf   →  output/测试文件.md
raw/测试文件.jpg   →  output/测试文件.md
```
