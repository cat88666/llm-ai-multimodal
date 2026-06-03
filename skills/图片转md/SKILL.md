---
名称: 图片转md
描述: 将 raw/ 目录下的图片文件（.jpg .jpeg .png）转换为 Markdown。
user-invocable: true
---

# 图片转md 技能

## 核心目标

将 `raw/` 目录下的 `.jpg`、`.jpeg`、`.png` 图片通过 AI 识别全部文字，
输出到 `output/` 下同名的 `.md` 文件。

## 触发条件

- 用户执行 `/图片转md`
- 用户说"识别图片文字"、"图片转 md" 等

## 执行步骤

### 第一步：检查环境

```bash
python3 -c "import anthropic, PIL; print('依赖正常')"
```

如果报错：
```bash
pip install -r requirements.txt
```

### 第二步：执行转换

**转换全部图片：**
```bash
python3 skills/图片转md/scripts/img_to_md.py
```

**转换单个文件：**
```bash
python3 skills/图片转md/scripts/img_to_md.py --file raw/test/测试文件.jpg
```

**强制覆盖：**
```bash
python3 skills/图片转md/scripts/img_to_md.py --force
```

### 第三步：核查结果

```bash
find output/ -name "*.md" | sort
```

## 常见问题

**识别结果不完整** → 图片分辨率过低或文字模糊，提升原图质量后重试

**图片太大报错** → 脚本已自动压缩到 1568px 以内，如仍报错检查图片格式是否损坏

**输出被跳过** → 加 `--force` 强制覆盖
