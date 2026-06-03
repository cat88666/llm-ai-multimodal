---
名称: 文本转md
描述: 将 raw/ 目录下的纯文本文件（.txt）转换为 Markdown。
user-invocable: true
---

# 文本转md 技能

## 核心目标

将 `raw/` 目录下的 `.txt` 文件自动检测编码并读取，通过 AI 格式化为 Markdown，
输出到 `output/` 下同名的 `.md` 文件。

## 触发条件

- 用户执行 `/文本转md`
- 用户说"转换文本文件"、"把 txt 转成 md" 等

## 执行步骤

### 第一步：检查环境

```bash
python3 -c "import anthropic; print('依赖正常')"
```

如果报错：
```bash
pip install -r requirements.txt
```

### 第二步：执行转换

**转换全部 txt 文件：**
```bash
python3 skills/文本转md/scripts/txt_to_md.py
```

**转换单个文件：**
```bash
python3 skills/文本转md/scripts/txt_to_md.py --file raw/test/测试文件.txt
```

**强制覆盖：**
```bash
python3 skills/文本转md/scripts/txt_to_md.py --force
```

### 第三步：核查结果

```bash
find output/ -name "*.md" | sort
```

## 常见问题

**乱码** → 脚本依次尝试 utf-8、gbk、gb2312，如仍乱码说明文件使用了其他编码，
可手动在脚本 `读取文本` 函数中添加对应编码

**输出被跳过** → 加 `--force` 强制覆盖
