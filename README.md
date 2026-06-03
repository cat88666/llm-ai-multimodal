# llm-ai-multimodal

AI 多模态文件转 Markdown 工具，支持 .pdf .docx .jpg .png .txt。

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
│   ├── api提示词/          # 技能脚本调用 AI API 时使用的提示词
│   ├── 批量转换/           # 调度：扫描目录、分发格式、断点续传
│   ├── pdf转md/
│   ├── 图片转md/
│   ├── word转md/
│   └── 文本转md/
└── requirements.txt
```

## 安装与运行

```bash
pip install -r requirements.txt

# 批量转换（自动推导输出目录）
python3 skills/批量转换/scripts/convert.py raw/test

# 转换外部项目目录
python3 skills/批量转换/scripts/convert.py /绝对路径/raw/test

# 中断后继续（断点续传，无需额外参数）
python3 skills/批量转换/scripts/convert.py raw/test

# 强制重新转换
python3 skills/批量转换/scripts/convert.py raw/test --force
```
