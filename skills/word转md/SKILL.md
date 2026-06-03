---
名称: word转md
描述: 将 raw/ 目录下的 Word 文件（.docx）转换为 Markdown。
user-invocable: true
---

# word转md 技能

## 核心目标

将 `raw/` 目录下的 `.docx` 文件提取段落和表格，通过 AI 格式化为 Markdown，
输出到 `output/` 下同名的 `.md` 文件。

## 触发条件

- 用户执行 `/word转md`
- 用户说"转换 Word"、"把 docx 转成 md" 等

## 执行步骤

### 第一步：检查环境

```bash
python3 -c "import anthropic, docx; print('依赖正常')"
```

如果报错：
```bash
pip install -r requirements.txt
```

### 第二步：执行转换

**转换全部 Word 文件：**
```bash
python3 skills/word转md/scripts/word_to_md.py
```

**转换单个文件：**
```bash
python3 skills/word转md/scripts/word_to_md.py --file raw/test/测试文件.docx
```

**强制覆盖：**
```bash
python3 skills/word转md/scripts/word_to_md.py --force
```

### 第三步：核查结果

```bash
find output/ -name "*.md" | sort
```

## 常见问题

**旧版 .doc 格式报错** → python-docx 不支持旧版 .doc，请先用 Word 另存为 .docx

**表格内容乱码** → 检查文件编码，确保 docx 使用 UTF-8 保存

**输出被跳过** → 加 `--force` 强制覆盖
