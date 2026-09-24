# -*- coding: utf-8 -*-
"""简历原文件预览（PDF/DOCX）：上传保存原件 → /file 端点 → 删除连带清理。"""
from pathlib import Path

from httpx import ASGITransport, AsyncClient
import pytest

from app.core.config import settings
from app.main import app

from tests.test_api import make_test_docx


def make_test_pdf() -> bytes:
    """用 PyMuPDF 生成一页含文字的 PDF（文字版，非扫描图）"""
    import pymupdf

    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Test Resume", fontsize=16)
    page.insert_text((72, 100), "Skills: Python, FastAPI, SQLite", fontsize=11)
    data = doc.tobytes()
    doc.close()
    return data


@pytest.mark.asyncio
async def test_pdf_upload_saves_original_and_serves():
    """PDF 上传后：list 标记 pdf + /file 返回原件 + 文本接口正常"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        files = {"file": ("我的简历.pdf", make_test_pdf(), "application/pdf")}
        r = await client.post("/api/v1/resumes/upload", files=files)
        assert r.status_code == 200
        resume_id = r.json()["id"]
        assert r.json()["text_length"] > 0

        # 列表带 file_type 标记
        r = await client.get("/api/v1/resumes/list")
        assert r.status_code == 200
        item = next(i for i in r.json()["items"] if i["id"] == resume_id)
        assert item["file_type"] == "pdf"

        # /file 端点返回原 PDF
        r = await client.get(f"/api/v1/resumes/{resume_id}/file")
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("application/pdf")
        assert r.content.startswith(b"%PDF")
        # 下载文件名用库内名称
        assert "attachment" in r.headers.get("content-disposition", "") or \
            "inline" in r.headers.get("content-disposition", "")

        # 文本接口仍可用（诊断链路不受影响）
        r = await client.get(f"/api/v1/resumes/{resume_id}")
        assert r.status_code == 200
        assert r.json()["raw_text"]


@pytest.mark.asyncio
async def test_pdf_delete_removes_original_file():
    """删除简历时连带删除落盘原文件"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        files = {"file": ("del-test.pdf", make_test_pdf(), "application/pdf")}
        r = await client.post("/api/v1/resumes/upload", files=files)
        resume_id = r.json()["id"]
        stored = Path(settings.FILES_DIR) / f"{resume_id}.pdf"
        assert stored.exists(), "上传后原文件应已落盘"

        r = await client.delete(f"/api/v1/resumes/{resume_id}")
        assert r.status_code == 200
        assert not stored.exists(), "删除简历后原文件应一并清理"


@pytest.mark.asyncio
async def test_text_resume_has_no_original_file():
    """粘贴文本简历无原文件：/file 返回 404，list 的 file_type 为空"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post("/api/v1/resumes/upload-text", json={
            "filename": "文本简历.txt",
            "text": "姓名：张三\n学历：本科\n技能：Python / FastAPI / SQL，" * 4,
        })
        assert r.status_code == 200
        resume_id = r.json()["id"]

        r = await client.get(f"/api/v1/resumes/{resume_id}/file")
        assert r.status_code == 404

        r = await client.get("/api/v1/resumes/list")
        item = next(i for i in r.json()["items"] if i["id"] == resume_id)
        assert item["file_type"] is None


@pytest.mark.asyncio
async def test_docx_upload_serves_original():
    """DOCX 上传同样保存原件（file 端点可下载）"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        files = {
            "file": ("word简历.docx", make_test_docx(),
                     "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
        }
        r = await client.post("/api/v1/resumes/upload", files=files)
        assert r.status_code == 200
        resume_id = r.json()["id"]

        r = await client.get(f"/api/v1/resumes/{resume_id}/file")
        assert r.status_code == 200
        assert "wordprocessingml" in r.headers["content-type"]
