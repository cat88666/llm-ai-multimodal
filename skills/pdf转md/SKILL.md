---
名称: pdf转md
描述: 将 raw/ 目录下的 PDF 文件转换为 Markdown。支持文字型和扫描型 PDF。
user-invocable: true
---

# pdf转md 技能

## 核心目标

将 `raw/` 目录下的 `.pdf` 文件完整转换为 Markdown，输出到 `output/`。

- 文字型 PDF：pymupdf 提取文字层 → AI 格式化
- 扫描型 PDF：每页渲染为图片 → AI 图片识别（自动判断，无需手动切换）

## 触发条件

- 用户执行 `/pdf转md`
- 用户说"转换 PDF"、"把 PDF 转成 md" 等

## 执行步骤

### 第一步：检查环境

```bash
python3 -c "import anthropic, fitz; print('依赖正常')"
```

如果报错：
```bash
pip install -r requirements.txt
```

### 第二步：执行转换

**转换全部 PDF：**
```bash
python3 skills/pdf转md/scripts/pdf_to_md.py
```

**转换单个文件：**
```bash
python3 skills/pdf转md/scripts/pdf_to_md.py --file raw/test/测试文件.pdf
```

**强制覆盖：**
```bash
python3 skills/pdf转md/scripts/pdf_to_md.py --force
```

### 第三步：核查结果

```bash
find output/ -name "*.md" | sort
```

## 常见问题

**文字识别为空** → 可能是加密 PDF，先解密再转换

**扫描件识别不准** → 原图分辨率过低，建议 150dpi 以上

**输出被跳过** → 加 `--force` 强制覆盖
