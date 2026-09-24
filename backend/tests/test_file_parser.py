"""B2：扫描版/图片型 PDF 的明确引导"""
import pymupdf
import pytest

from app.utils.file_parser import parse_resume_file


def _make_scanned_pdf(path):
    """生成一页纯图片 PDF（模拟扫描件：无文本层，仅有整页图）"""
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)  # A4
    # 整页矩形图（pix 无文字，仅像素）
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 400, 500))
    pix.clear_with(90)  # 灰底
    page.insert_image(page.rect, pixmap=pix)
    doc.save(str(path))
    doc.close()


def _make_text_pdf(path):
    """正常文字版 PDF"""
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 100), "熟悉 Python 与 FastAPI，负责后端服务开发。" * 5)
    doc.save(str(path))
    doc.close()


def test_scanned_pdf_gives_specific_error(tmp_path):
    """图片型 PDF：报错文案指向扫描版而非笼统「解析后为空」"""
    pdf = tmp_path / "scanned.pdf"
    _make_scanned_pdf(pdf)
    with pytest.raises(ValueError) as exc:
        parse_resume_file(pdf)
    assert "扫描版" in str(exc.value)


def test_text_pdf_passes(tmp_path):
    """文字版 PDF 正常提取"""
    pdf = tmp_path / "normal.pdf"
    _make_text_pdf(pdf)
    text = parse_resume_file(pdf)
    assert "FastAPI" in text
