# 项目规则

## 运行环境

- Python 环境：**conda python311**
  - 路径：`/Users/mac/anaconda3/envs/python311/bin/python3`
  - 所有脚本必须用此环境执行，不使用系统 Python
- 无 API Key，不使用任何付费 AI API
- AI 工具通过 CLI 使用：claude cli / codex cli / gemini cli / cursor

## 文件格式转换方案

### 原则
- 文字类文件优先用**本地库**直接转换，不调用 AI
- 图片类文件用**本地 OCR**，不依赖远程 API
- 只有本地工具无法处理时，才考虑通过 CLI 调用 AI

### 各格式工具选型

| 格式 | 工具 | 安装方式 | 说明 |
|------|------|---------|------|
| `.txt` | Python 内置 | 无需安装 | 直接读取，自动检测编码 |
| `.docx` | `mammoth` | `pip install mammoth` | 高质量 docx→md，保留格式 |
| `.pdf`（文字层） | `pymupdf` | `pip install pymupdf` | 提取文字层，保留分页结构 |
| `.pdf`（扫描件） | `pymupdf` + `tesseract` | `brew install tesseract tesseract-lang` | pymupdf 渲染图片，tesseract OCR |
| `.jpg` / `.png` | `tesseract` | `brew install tesseract tesseract-lang` | 支持中文（chi_sim） |

### 备选方案（质量更高但需安装）
- `easyocr`：比 tesseract 对中文识别更准，支持复杂排版，`pip install easyocr`
- `pandoc`：docx→md 格式最完整，`brew install pandoc`

## 依赖安装

```bash
# Python 包（在 python311 环境中）
/Users/mac/anaconda3/envs/python311/bin/pip install pymupdf mammoth pytesseract

# 系统工具（Homebrew）
brew install tesseract tesseract-lang
```

## 技能脚本执行方式

```bash
/Users/mac/anaconda3/envs/python311/bin/python3 skills/批量转换/scripts/convert.py raw/test
```
