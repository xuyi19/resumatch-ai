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
async def test_match_recommend():
    """测试纯匹配接口（不用 LLM，快）"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post("/api/v1/match/recommend", json={
            "resume_text": "学历：本科 工作年限：3年 技能：Python, FastAPI, MySQL",
            "top_k": 5,
            "use_semantic": False,   # 关掉语义，加快测试
        })
        assert r.status_code == 200
        data = r.json()
        assert data["count"] <= 5
        assert isinstance(data["results"], list)