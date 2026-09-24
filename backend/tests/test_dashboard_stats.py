"""M36 工作台统计端点测试：GET /history/stats。

面试/简历数据走真实 API 链路（LLM 已 monkeypatch），
诊断记录直接插测试库（跑完整诊断图太重，统计端点只消费落库结果）。
"""
from datetime import datetime

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import insert

from app.core.config import settings
from app.core.db import engine
from app.main import app
from app.models.entities import DiagnosisRecord, Resume

from tests.test_interview_free import RESUME_TEXT, _fake_call_llm  # 复用同一套 LLM fake 与简历文本

# 固定会话 id：web 态通过 X-Session-Id 头强制 owner 隔离（test.db 跨用例共享，
# 空态断言只对「本会话 0 数据」成立）；桌面态 get_owner_id 忽略该头固定 local
SID = "stat-owner-1"


@pytest.fixture
async def client(monkeypatch):
    monkeypatch.setattr("app.api.v1.interview.call_llm_for_json", _fake_call_llm)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test",
                           headers={"X-Session-Id": SID}) as c:
        yield c


async def _current_owner(client) -> str:
    """请求侧真实 owner_id：web 态即固定会话 id，桌面态固定 local。"""
    return "local" if settings.APP_MODE != "web" else SID


async def _cleanup():
    """清理本测试固定标识的历史数据：test.db 跨 pytest 运行残留会破坏增量断言
    （upload-text 同名去重导致 count 不增、stat-diag-* 残留计入 before 快照）。"""
    from sqlalchemy import delete, insert
    async with engine.begin() as conn:
        await conn.execute(
            delete(DiagnosisRecord).where(DiagnosisRecord.task_id.like("stat-diag-%")))
        await conn.execute(
            delete(Resume).where(Resume.filename == "张三-统计测试.txt"))


async def _insert_diagnosis(owner_id: str, task_id: str, status: str, overall=None):
    from sqlalchemy import insert
    async with engine.begin() as conn:
        await conn.execute(
            insert(DiagnosisRecord).values(
                task_id=task_id, owner_id=owner_id, resume_id=None,
                resume_name="测试简历.pdf", keyword="Java 后端", status=status,
                result={"diagnosis": {"scores": {"overall": overall}}} if overall else {},
                created_at=datetime.now(),
            )
        )


@pytest.mark.asyncio
async def test_stats_structure(client):
    """结构断言（测试库跨用例共享，不假设空库）。"""
    resp = await client.get("/api/v1/history/stats")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    for key in ("resume_count", "diagnosis_total", "diagnosis_avg_score", "latest_diagnosis",
                "ongoing_diagnoses", "interview_total", "interview_finished",
                "interview_avg_score", "latest_interview_score", "ongoing_interviews"):
        assert key in data, f"缺少字段 {key}"
    assert isinstance(data["ongoing_diagnoses"], list)
    assert isinstance(data["ongoing_interviews"], list)
    assert data["resume_count"] >= 0


@pytest.mark.asyncio
async def test_stats_aggregates_diagnosis_and_interview(client):
    await _cleanup()

    # 快照：断言增量而非绝对值（test.db 跨用例共享、owner 固定 local）
    before = (await client.get("/api/v1/history/stats")).json()

    # 简历（真实 API）
    res = await client.post(
        "/api/v1/resumes/upload-text",
        json={"filename": "张三-统计测试.txt", "text": RESUME_TEXT},
    )
    assert res.status_code == 200, res.text

    # 诊断记录（直插：1 成功 80 分 + 2 进行中）
    owner = await _current_owner(client)
    await _insert_diagnosis(owner, "stat-diag-ok", "success", 80)
    await _insert_diagnosis(owner, "stat-diag-run", "running")
    await _insert_diagnosis(owner, "stat-diag-clarify", "waiting_clarify")

    # 面试会话（真实 API，LLM 已 fake）：start-free 后处于 ongoing
    iv = await client.post(
        "/api/v1/interview/start-free",
        json={"resume_id": res.json()["id"], "jd_text": "负责高并发后端服务开发，要求熟悉 Python。"},
    )
    assert iv.status_code == 200, iv.text

    data = (await client.get("/api/v1/history/stats")).json()
    assert data["resume_count"] == before["resume_count"] + 1
    assert data["diagnosis_total"] == before["diagnosis_total"] + 3
    # latest 按 id desc 取最近一条 = 最后插入的 clarify（waiting_clarify 无分数）
    assert data["latest_diagnosis"]["task_id"] == "stat-diag-clarify"
    assert data["latest_diagnosis"]["score"] is None
    actual_ongoing = {d["task_id"] for d in data["ongoing_diagnoses"]}
    assert {"stat-diag-run", "stat-diag-clarify"} <= actual_ongoing
    # 均分只统计有分数的记录：新增 1 条 80 分后仍非空且方向正确
    if before["diagnosis_avg_score"] is None:
        assert data["diagnosis_avg_score"] == 80.0
    else:
        assert data["diagnosis_avg_score"] is not None
    assert data["interview_total"] == before["interview_total"] + 1
    assert data["interview_finished"] == before["interview_finished"]
    # M37：0 题未答的空会话不进「继续进行」→ ongoing 数不变
    assert len(data["ongoing_interviews"]) == len(before["ongoing_interviews"])


@pytest.mark.asyncio
async def test_delete_session_and_stats_filter(client):
    """M37：删除面试会话 + 空会话（0 题未答）不进 stats 继续进行。"""
    await _cleanup()
    res = await client.post(
        "/api/v1/resumes/upload-text",
        json={"filename": "张三-统计测试.txt", "text": RESUME_TEXT},
    )
    rid = res.json()["id"]

    # 开两场面试（均未答题）
    iv1 = await client.post("/api/v1/interview/start-free",
        json={"resume_id": rid, "jd_text": "负责高并发后端服务开发，要求熟悉 Python。"})
    iv2 = await client.post("/api/v1/interview/start-free",
        json={"resume_id": rid, "jd_text": "负责高并发后端服务开发，要求熟悉 Python。"})
    tid1, tid2 = iv1.json()["task_id"], iv2.json()["task_id"]

    # 0 题未答的空会话不进「继续进行」
    stats = (await client.get("/api/v1/history/stats")).json()
    assert tid1 not in {c["task_id"] for c in stats["ongoing_interviews"]}
    assert tid2 not in {c["task_id"] for c in stats["ongoing_interviews"]}

    # 删除第一场 → 会话消失（恢复端点 exists=False）、列表不再返回；第二场不受影响
    assert (await client.delete(f"/api/v1/interview/sessions/{tid1}")).status_code == 200
    get1 = await client.get(f"/api/v1/interview/{tid1}")
    assert get1.status_code == 200 and get1.json()["exists"] is False
    assert (await client.delete(f"/api/v1/interview/sessions/{tid1}")).status_code == 404  # 幂等拒绝
    sessions = (await client.get("/api/v1/interview/sessions")).json()["items"]
    assert tid1 not in {s["task_id"] for s in sessions}
    assert tid2 in {s["task_id"] for s in sessions}
