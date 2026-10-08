"""M59 数据备份与恢复测试：导出全链路 / 合并式导入（old→new 映射）/ owner 隔离 /
非法文件 422 / stats / 会话 JSON 原样往返。

用 uuid 会话（X-Session-Id 头）做 owner 隔离（同 test_job_library 惯例），
每个会话的库内数据从零开始，counts 可精确断言。
"""

import json
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.core.config import settings
from app.core.db import AsyncSessionLocal
from app.main import app
from app.models.entities import Conversation, Resume, ResumeVersion, SavedJob


@pytest.fixture
async def client(monkeypatch):
    # web 态让 X-Session-Id 头生效（桌面态 owner 恒为 local，无法测隔离）
    monkeypatch.setattr(settings, "APP_MODE", "web")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def _sid() -> dict:
    return {"X-Session-Id": f"bk-{uuid4().hex[:12]}"}


RESUME_TEXT = (
    "本科，三年 Python 后端开发经验，熟悉 FastAPI、MySQL、Redis，"
    "主导过高并发订单系统优化，QPS 提升 3 倍。"
)

_STAT_KEYS = {
    "resumes", "resume_versions", "saved_jobs",
    "diagnoses", "conversations", "export_history",
}


# ---------------------------------------------------------------- 导出


async def test_export_full_chain(client):
    """建简历（upload-text）+ 岗位（library），空表为 0 → export 结构齐全、counts 对得上。"""
    hd = _sid()
    up = await client.post(
        "/api/v1/resumes/upload-text",
        json={"filename": "备份测试.txt", "text": RESUME_TEXT},
        headers=hd,
    )
    assert up.status_code == 200, up.text
    lib = await client.post(
        "/api/v1/jobs/library",
        json={"items": [{"title": "后端工程师", "company": "A 科技", "city": "杭州",
                          "salary": "25-40K"}]},
        headers=hd,
    )
    assert lib.status_code == 200, lib.text

    resp = await client.get("/api/v1/backup/export", headers=hd)
    assert resp.status_code == 200
    body = resp.json()
    assert body["app"] == "ResuMatch-AI"
    assert body["schema_version"] == 1
    assert body["exported_at"]  # ISO 时间字符串
    assert body["counts"] == {
        "resumes": 1,
        "resume_versions": 1,  # upload-text 自动落 v1 版本链
        "saved_jobs": 1,
        "diagnoses": 0,
        "conversations": 0,
        "export_history": 0,
    }
    assert set(body["data"]) == _STAT_KEYS

    resume_row = body["data"]["resumes"][0]
    assert resume_row["filename"] == "备份测试.txt"
    assert resume_row["raw_text"] == RESUME_TEXT
    assert resume_row["id"]  # 导出行带原 id 字段
    assert "T" in resume_row["created_at"]  # datetime → isoformat 字符串

    version_row = body["data"]["resume_versions"][0]
    assert version_row["resume_id"] == resume_row["id"]
    assert version_row["source"] == "initial"

    job_row = body["data"]["saved_jobs"][0]
    assert job_row["title"] == "后端工程师"
    assert job_row["status"] == "wish"
    assert job_row["url"] == ""


# ---------------------------------------------------------------- 导入（合并式 + 映射）


async def test_import_merges_and_maps(client):
    """A 导出 → A 再次导入：imported counts 与导出一致；合并式条数翻倍；
    ResumeVersion.resume_id 重映射到新简历 id；岗位 status/url/渠道/时间完整保留。"""
    hd = _sid()
    up = await client.post(
        "/api/v1/resumes/upload-text",
        json={"filename": "导入映射.txt", "text": RESUME_TEXT}, headers=hd,
    )
    resume_id = up.json()["id"]
    lib = await client.post(
        "/api/v1/jobs/library",
        json={"items": [{"title": "Go 工程师", "company": "B 公司", "city": "北京",
                          "url": "https://www.zhipin.com/job_detail/abc.html?securityId=x"}]},
        headers=hd,
    )
    jid = lib.json()["items"][0]["id"]
    st = await client.put(
        f"/api/v1/jobs/library/{jid}/status",
        json={"status": "applied", "apply_channel": "boss"}, headers=hd,
    )
    assert st.status_code == 200

    exported = (await client.get("/api/v1/backup/export", headers=hd)).json()

    resp = await client.post("/api/v1/backup/import", json=exported, headers=hd)
    assert resp.status_code == 200, resp.text
    imported = resp.json()["imported"]
    assert imported == exported["counts"]

    # 合并式：导入不删除原有数据，条数翻倍
    stats = (await client.get("/api/v1/backup/stats", headers=hd)).json()
    assert stats["resumes"] == 2
    assert stats["resume_versions"] == 2
    assert stats["saved_jobs"] == 2

    # ResumeVersion 父子映射：两条版本各自挂在两条简历上，无悬空引用
    sid = hd["X-Session-Id"]
    async with AsyncSessionLocal() as session:
        resumes = (await session.execute(
            select(Resume).where(Resume.owner_id == sid))).scalars().all()
        versions = (await session.execute(
            select(ResumeVersion).where(ResumeVersion.owner_id == sid))).scalars().all()
        assert len(resumes) == 2 and len(versions) == 2
        rid_set = {r.id for r in resumes}
        assert {v.resume_id for v in versions} == rid_set
        assert {v.source for v in versions} == {"initial"}

        # 岗位字段完整保留（status/url/渠道/投递时间），导入副本 id 更新
        jobs = (await session.execute(
            select(SavedJob).where(SavedJob.owner_id == sid)
            .order_by(SavedJob.id.desc()))).scalars().all()
        new_job = jobs[0]  # 最新插入的即导入副本
        assert new_job.id > jid
        assert new_job.title == "Go 工程师"
        assert new_job.status == "applied"
        assert new_job.apply_channel == "boss"
        assert new_job.apply_at is not None
        assert new_job.url.startswith("https://www.zhipin.com")


# ---------------------------------------------------------------- owner 隔离


async def test_import_owner_isolation(client):
    """A 导出的数据 B 导入后归 B（owner 重写），A 原数据不变、互不串扰。"""
    hd_a, hd_b = _sid(), _sid()
    sid_a, sid_b = hd_a["X-Session-Id"], hd_b["X-Session-Id"]
    await client.post(
        "/api/v1/jobs/library",
        json={"items": [{"title": "隔离岗位", "company": "A 公司"}]}, headers=hd_a,
    )
    exported = (await client.get("/api/v1/backup/export", headers=hd_a)).json()

    resp = await client.post("/api/v1/backup/import", json=exported, headers=hd_b)
    assert resp.status_code == 200, resp.text
    assert resp.json()["imported"]["saved_jobs"] == 1

    # 导入行 owner 归 B
    async with AsyncSessionLocal() as session:
        jobs_b = (await session.execute(
            select(SavedJob).where(SavedJob.owner_id == sid_b))).scalars().all()
        assert len(jobs_b) == 1 and jobs_b[0].title == "隔离岗位"

    # B 的 export 只含自己的数据（导入副本），不含 A 的其他内容
    exported_b = (await client.get("/api/v1/backup/export", headers=hd_b)).json()
    assert exported_b["counts"]["saved_jobs"] == 1
    assert exported_b["counts"]["resumes"] == 0

    # A 原数据不变：B 的导入不会写进 A，A 的岗位库仍是自己那一条
    stats_a = (await client.get("/api/v1/backup/stats", headers=hd_a)).json()
    assert stats_a["saved_jobs"] == 1 and stats_a["resumes"] == 0
    lib_a = (await client.get("/api/v1/jobs/library", headers=hd_a)).json()["items"]
    assert len(lib_a) == 1


# ---------------------------------------------------------------- 非法文件


async def test_import_rejects_invalid(client):
    """非知岗 JSON / 坏 JSON / 版本过高 → 全部 422，绝不 500。"""
    hd = _sid()

    resp = await client.post("/api/v1/backup/import", json={"foo": 1}, headers=hd)
    assert resp.status_code == 422
    assert "不是知岗备份" in resp.json()["detail"]

    resp = await client.post(
        "/api/v1/backup/import",
        content=b"{oops-not-json",
        headers={**hd, "Content-Type": "application/json"},
    )
    assert resp.status_code == 422
    assert "JSON" in resp.json()["detail"]

    resp = await client.post(
        "/api/v1/backup/import",
        json={"app": "ResuMatch-AI", "schema_version": 99, "data": {}}, headers=hd,
    )
    assert resp.status_code == 422
    assert "升级" in resp.json()["detail"]

    # 合法壳但缺 data 区
    resp = await client.post(
        "/api/v1/backup/import",
        json={"app": "ResuMatch-AI", "schema_version": 1}, headers=hd,
    )
    assert resp.status_code == 422

    # 确认以上失败导入没有写入任何数据
    stats = (await client.get("/api/v1/backup/stats", headers=hd)).json()
    assert all(v == 0 for v in stats.values())


# ---------------------------------------------------------------- stats


async def test_backup_stats(client):
    """stats 条数与库内一致：空会话全 0，建简历+岗位后精确 +1。"""
    hd = _sid()
    base = (await client.get("/api/v1/backup/stats", headers=hd)).json()
    assert set(base) == _STAT_KEYS
    assert all(v == 0 for v in base.values())

    await client.post(
        "/api/v1/resumes/upload-text",
        json={"filename": "统计.txt", "text": RESUME_TEXT}, headers=hd,
    )
    await client.post(
        "/api/v1/jobs/library",
        json={"items": [{"title": "统计岗"}]}, headers=hd,
    )
    after = (await client.get("/api/v1/backup/stats", headers=hd)).json()
    assert after["resumes"] == 1
    assert after["resume_versions"] == 1
    assert after["saved_jobs"] == 1
    assert after["diagnoses"] == 0
    assert after["conversations"] == 0
    assert after["export_history"] == 0


# ---------------------------------------------------------------- 会话 JSON 原样往返


async def test_conversation_json_roundtrip(client):
    """已完成刷题会话（含 questions/answers JSON 列 + context/chat_log TEXT 存 JSON）
    导出原样、导入后回读逐字一致，不做二次解析。"""
    hd_a, hd_b = _sid(), _sid()
    sid_b = hd_b["X-Session-Id"]
    questions = [{"id": "q1", "stem": "介绍一个你主导的项目", "options": [], "answer": "略"}]
    answers = {"q1": {"content": "高并发订单系统", "correct": True}}
    context = json.dumps({"direction": "后端", "jd_text": "Java 高级工程师", "count": 5},
                         ensure_ascii=False)
    chat_log = json.dumps(
        [{"role": "interviewer", "qid": "q1", "content": "介绍一个你主导的项目"}],
        ensure_ascii=False,
    )
    task_id = f"qz-{uuid4().hex[:12]}"
    async with AsyncSessionLocal() as session:
        session.add(Conversation(
            task_id=task_id, owner_id=hd_a["X-Session-Id"], type="quiz",
            context=context, questions=questions, answers=answers,
            current_index=1, status="finished", chat_log=chat_log,
        ))
        await session.commit()

    exported = (await client.get("/api/v1/backup/export", headers=hd_a)).json()
    assert exported["counts"]["conversations"] == 1
    row = exported["data"]["conversations"][0]
    assert row["task_id"] == task_id and row["type"] == "quiz"
    assert row["questions"] == questions  # JSON 列原样
    assert row["answers"] == answers
    assert row["context"] == context      # TEXT 存 JSON：原样字符串
    assert row["chat_log"] == chat_log

    resp = await client.post("/api/v1/backup/import", json=exported, headers=hd_b)
    assert resp.status_code == 200, resp.text
    assert resp.json()["imported"]["conversations"] == 1

    # B 侧回读：逐字段一致
    async with AsyncSessionLocal() as session:
        convs = (await session.execute(
            select(Conversation).where(Conversation.owner_id == sid_b))).scalars().all()
        assert len(convs) == 1
        c = convs[0]
        assert c.task_id == task_id and c.type == "quiz"
        assert c.questions == questions and c.answers == answers
        assert c.context == context and c.chat_log == chat_log
        assert c.current_index == 1 and c.status == "finished"
