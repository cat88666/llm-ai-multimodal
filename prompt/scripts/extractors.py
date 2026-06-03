import base64
import io
from pathlib import Path

from PIL import Image


def extract_pdf(file_path: Path) -> str:
    import fitz
    doc = fitz.open(str(file_path))
    pages = []
    for i, page in enumerate(doc):
        text = page.get_text().strip()
        if text:
            pages.append(f"--- 第{i+1}页 ---\n{text}")
    doc.close()
    return "\n\n".join(pages) if pages else ""


def extract_docx(file_path: Path) -> str:
    import docx
    try:
        doc = docx.Document(str(file_path))
        return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    except Exception:
        # .doc 旧格式 python-docx 不支持，返回空让 caller 处理
        return f"[不支持的旧版Word格式: {file_path.name}]"


def extract_txt(file_path: Path) -> str:
    for enc in ("utf-8", "gbk", "gb2312"):
        try:
            return file_path.read_text(encoding=enc)
        except UnicodeDecodeError:
            continue
    return file_path.read_text(encoding="utf-8", errors="replace")


def extract_xlsx(file_path: Path) -> str:
    import openpyxl
    wb = openpyxl.load_workbook(str(file_path), data_only=True)
    rows = []
    for sheet in wb.worksheets:
        rows.append(f"[Sheet: {sheet.title}]")
        for row in sheet.iter_rows(values_only=True):
            vals = [str(c) if c is not None else "" for c in row]
            if any(v.strip() for v in vals):
                rows.append("\t".join(vals))
    return "\n".join(rows)


def image_to_base64(file_path: Path, max_px: int = 1568) -> tuple[str, str]:
    """返回 (media_type, base64_data)，自动压缩超大图片"""
    img = Image.open(str(file_path))
    # 转RGB避免RGBA/P模式报错
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    # 等比缩放
    w, h = img.size
    if max(w, h) > max_px:
        ratio = max_px / max(w, h)
        img = img.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    data = base64.standard_b64encode(buf.getvalue()).decode()
    return "image/jpeg", data


def extract_content(file_path: Path) -> dict:
    """
    返回 {"mode": "text"|"image", "content": str | (media_type, b64)}
    """
    suffix = file_path.suffix.lower()
    if suffix == ".pdf":
        text = extract_pdf(file_path)
        return {"mode": "text", "content": text}
    elif suffix in (".jpg", ".jpeg", ".png"):
        media_type, b64 = image_to_base64(file_path)
        return {"mode": "image", "content": (media_type, b64)}
    elif suffix in (".docx", ".doc"):
        text = extract_docx(file_path)
        return {"mode": "text", "content": text}
    elif suffix == ".txt":
        text = extract_txt(file_path)
        return {"mode": "text", "content": text}
    elif suffix == ".xlsx":
        text = extract_xlsx(file_path)
        return {"mode": "text", "content": text}
    else:
        return {"mode": "text", "content": f"[不支持的格式: {suffix}]"}
