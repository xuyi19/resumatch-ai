# -*- coding: utf-8 -*-
"""简历 PDF 导出（优化⑫）：生成器渲染 / 端点 blob / 桌面态落盘 / web 403 / 照片校验。"""
from pathlib import Path
from uuid import uuid4

import pymupdf
import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.main import app
from app.utils.pdf_generator import generate_resume_pdf


@pytest.fixture
async def client(monkeypatch):
    # web 态让 X-Session-Id 头生效（同 test_settings_export 惯例）
    monkeypatch.setattr(settings, "APP_MODE", "web")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def _sid() -> dict:
    return {"X-Session-Id": f"pdf-{uuid4().hex[:12]}"}

DATA = {
    "name": "张三",
    "job_intention": "Python 后端开发",
    "contacts": ["电话：13800000000", "邮箱：zhangsan@example.com"],
    "summary": "五年后端开发经验，熟悉高并发服务。",
    "education": ["2020-2024 某大学 计算机科学与技术 本科"],
    "experience": ["2024-至今 某公司 后端工程师", "负责核心服务开发，QPS 提升 3 倍"],
    "projects": ["知识库系统", "独立设计检索模块"],
    "skills": ["Python", "FastAPI", "MySQL"],
    "certificates": ["CET-6"],
}


def _pdf_text(data: bytes) -> str:
    doc = pymupdf.open("pdf", data)
    text = "\n".join(p.get_text() for p in doc)
    doc.close()
    return text


def test_generate_resume_pdf_basic():
    """核心数据全渲染：姓名/区块标题/正文/技能连接符均在，模板配色不报错。"""
    pdf = generate_resume_pdf(DATA, template="classic")
    assert pdf.startswith(b"%PDF")
    text = _pdf_text(pdf)
    assert "张三" in text
    assert "个人简介" in text and "工作经历" in text and "证书" in text
    assert "QPS 提升 3 倍" in text
    assert "Python · FastAPI · MySQL" in text
    assert "求职意向" in text and "zhangsan@example.com" in text


def test_generate_resume_pdf_empty_and_unknown_template():
    """空数据不崩；未知模板回落 classic；空 summary 区块跳过。"""
    pdf = generate_resume_pdf({"name": "李四"}, template="no-such")
    assert pdf.startswith(b"%PDF")
    assert "李四" in _pdf_text(pdf)

    pdf2 = generate_resume_pdf({**DATA, "summary": "", "certificates": []})
    text2 = _pdf_text(pdf2)
    assert "个人简介" not in text2 and "证书" not in text2
    assert "教育经历" in text2


def test_generate_resume_pdf_pagination():
    """长内容自动分页且不丢内容。"""
    data = {
        **DATA,
        "summary": "",
        "experience": ["2020-2024 某公司 工程师"]
        + [f"职责条目{i}：" + "详细描述内容。" * 8 for i in range(40)],
    }
    doc = pymupdf.open("pdf", generate_resume_pdf(data))
    assert doc.page_count >= 2
    full = "\n".join(p.get_text() for p in doc)
    doc.close()
    assert "职责条目39" in full


def test_generate_resume_pdf_photo(tmp_path):
    """证件照嵌入（PNG）不崩且输出合法 PDF。"""
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 60, 80))
    pix.set_rect(pix.irect, (200, 120, 60))
    photo = tmp_path / "photo.png"
    pix.save(str(photo))

    pdf = generate_resume_pdf(DATA, photo_path=str(photo))
    assert pdf.startswith(b"%PDF")
    doc = pymupdf.open("pdf", pdf)
    assert len(doc[0].get_images()) == 1
    doc.close()


# ---------- 端点 ----------


@pytest.mark.asyncio
async def test_export_pdf_blob(client):
    """网页形态主路径：application/pdf blob + 落导出历史。"""
    hd = _sid()
    r = await client.post("/api/v1/resumes/export-pdf",
                          json={"optimized_resume": DATA}, headers=hd)
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("application/pdf")
    assert r.content.startswith(b"%PDF")

    hist = (await client.get("/api/v1/resumes/export-history", headers=hd)).json()["items"]
    assert any(i["filename"] == "优化后的简历.pdf" for i in hist)


@pytest.mark.asyncio
async def test_export_pdf_photo_id_invalid(client):
    """照片 id 不合法 → 404（与 export-docx 同防线）。"""
    r = await client.post(
        "/api/v1/resumes/export-pdf",
        json={"optimized_resume": DATA, "photo_id": "not-a-valid-id"},
        headers=_sid(),
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_export_pdf_save_path_desktop(client, monkeypatch, tmp_path):
    """桌面态 save_path 直写：落 {export_root}/简历/ 子目录，历史带路径。"""
    monkeypatch.setattr(settings, "APP_MODE", "local")

    r = await client.put("/api/v1/settings/export-root",
                         json={"path": str(tmp_path / "out")})
    assert r.status_code == 200

    r = await client.post("/api/v1/resumes/export-pdf",
                          json={"optimized_resume": DATA, "save_path": "auto"})
    assert r.status_code == 200, r.text
    body = r.json()
    saved = Path(body["saved_to"])
    assert saved.parent == tmp_path / "out" / "简历"
    assert saved.exists() and saved.read_bytes().startswith(b"%PDF")

    hist = (await client.get("/api/v1/resumes/export-history")).json()["items"]
    assert any(i["template"] == "classic" and i["save_path"] == str(saved) for i in hist)


@pytest.mark.asyncio
async def test_export_pdf_web_rejects_save_path(client):
    """web 态带 save_path → 403（不允许服务端落盘）。"""
    r = await client.post("/api/v1/resumes/export-pdf",
                          json={"optimized_resume": DATA, "save_path": "auto"})
    assert r.status_code == 403
