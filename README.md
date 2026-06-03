# llm-ai-multimodal

多格式文件转 Markdown 工具，支持 .pdf .docx .jpg .png .txt。
无需 API Key，全部使用本地工具处理。

## 使用案例

> "帮我把 `raw/test` 所有文件转化为 md"
> "把 `/项目路径/raw/test` 所有文件全部转化为 md，生成后放到 `/项目路径/output/test`"

## 目录结构

```
llm-ai-multimodal/
├── raw/                    # 待转换的原始文件
├── output/                 # 转换结果 + output.log 日志
├── prompts/                # Claude 规划层（识别意图、制定计划）
├── skills/
│   ├── 批量转换/           # 调度：扫描目录、分发格式、断点续传
│   ├── pdf转md/
│   ├── 图片转md/
│   ├── word转md/
│   └── 文本转md/
├── CLAUDE.md               # 项目规则（环境、工具选型）
└── requirements.txt
```

## 环境与安装

Python 环境：conda `python311`，详见 `CLAUDE.md`。

```bash
# Python 包
/Users/mac/anaconda3/envs/python311/bin/pip install pymupdf mammoth pytesseract

# 系统工具（图片/扫描件 OCR）
brew install tesseract tesseract-lang
```

## 运行

```bash
PYTHON=/Users/mac/anaconda3/envs/python311/bin/python3

$PYTHON skills/批量转换/scripts/convert.py raw/test
$PYTHON skills/批量转换/scripts/convert.py /项目路径/raw/test
$PYTHON skills/批量转换/scripts/convert.py raw/test --force
```
