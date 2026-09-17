"""API 接口集成测试"""
import io

from docx import Document
from httpx import ASGITransport, AsyncClient
import pytest

from app.main import app


def make_test_docx() -> bytes:
    doc = Document()
    doc.add_heading("测试简历", level=1)
    doc.add_paragraph("学历：本科    工作年限：3年")
    doc.add_paragraph("技能：Python, FastAPI, MySQL")
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


@pytest.mark.asyncio
async def test_upload_resume():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        docx_bytes = make_test_docx()
        files = {
            "file": ("test.docx", docx_bytes,
                     "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
        }
        r = await client.post("/api/v1/resumes/upload", files=files)
        assert r.status_code == 200
        data = r.json()
        assert "id" in data
        assert data["text_length"] > 0
        print(f"\n✓ 简历上传成功 id={data['id']} 长度={data['text_length']}")


@pytest.mark.asyncio
async def test_upload_invalid_file():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        files = {"file": ("test.xyz", b"invalid content", "text/plain")}
        r = await client.post("/api/v1/resumes/upload", files=files)
        assert r.status_code == 400


@pytest.mark.asyncio
async def test_live_analyze_validation():
    """JD 文本过短应返回 400"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post("/api/v1/live/analyze", json={
            "resume_id": 999999,
            "jd_input_type": "text",
            "jd_text": "太短",
        })
        assert r.status_code == 400