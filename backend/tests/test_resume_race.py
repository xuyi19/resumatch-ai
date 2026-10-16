"""D2 简历版本赛马测试：分组统计口径（与 /attribution 一致）/ 未记录与简历已删除
归「未记录」组 / 样本不足 sample_ok 诚实标注 / owner 隔离。

数据构造：Resume 建两版简历，SavedJob 用 apply_resume_id 关联（首次标记 applied
时由端点写入；本测试直接落库模拟历史数据，另有一条端点写入路径用例覆盖）。
"""

from datetime import datetime
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.core.db import AsyncSessionLocal
from app.main import app
from app.models.entities import Resume, SavedJob


@pytest.fixture
async def client(monkeypatch):
    monkeypatch.setattr(settings, "APP_MODE", "web")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def _sid() -> dict:
    return {"X-Session-Id": f"race-{uuid4().hex[:12]}"}


def _resume(owner, title) -> Resume:
    return Resume(owner_id=owner, filename=title,
                  raw_text=f"{title}：负责后端服务开发与性能优化，熟悉 Python 与 Redis。",
                  created_at=datetime(2026, 9, 1))


def _job(owner, status="wish", apply_at=None, resume_id=None) -> SavedJob:
    return SavedJob(owner_id=owner, title="后端工程师", jd_text="赛马测试岗位描述。",
                    status=status, apply_at=apply_at, apply_resume_id=resume_id,
                    created_at=datetime(2026, 9, 1))


async def _seed(owner, rows):
    async with AsyncSessionLocal() as session:
        for row in rows:
            session.add(row)
        await session.commit()
        ids = [row.id for row in rows if isinstance(row, Resume)]
        return ids


async def test_grouped_rates_and_untracked(client):
    """两版简历分组统计 + 未记录组：A 版 4 投 2 进面（0.5），B 版 2 投 0 进面（0.0），
    未关联 1 条归未记录组（resume_title None）；未投岗位不参与。"""
    hd = _sid()
    owner = hd["X-Session-Id"]
    now = datetime.now()
    rid_a = await _seed(owner, [_resume(owner, "简历A版")])
    await _seed(owner, [_resume(owner, "简历B版")])
    rid_a = rid_a[0]
    await _seed(owner, [
        # A 版：4 投 2 进面
        _job(owner, "interviewing", apply_at=now, resume_id=rid_a),
        _job(owner, "offer", apply_at=now, resume_id=rid_a),
        _job(owner, "applied", apply_at=now, resume_id=rid_a),
        _job(owner, "closed", apply_at=now, resume_id=rid_a),
        # B 版：2 投 0 进面
        _job(owner, "applied", apply_at=now, resume_id=rid_a + 1),
        _job(owner, "applied", apply_at=now, resume_id=rid_a + 1),
        # 未关联：1 条（投后 closed 也计）
        _job(owner, "closed", apply_at=now),
        # 未投：不参与
        _job(owner, "wish"),
        _job(owner, "closed"),
    ])
    r = await client.get("/api/v1/jobs/resume-race", headers=hd)
    assert r.status_code == 200, r.text
    body = r.json()
    by_id = {row["resume_id"]: row for row in body["rows"]}
    assert set(by_id) == {rid_a, rid_a + 1, None}
    a = by_id[rid_a]
    assert a["resume_title"] == "简历A版"
    assert a["applied"] == 4 and a["interviewing"] == 2 and a["offer"] == 1
    assert a["interview_rate"] == 0.5
    assert a["offer_rate"] == 0.5
    b = by_id[rid_a + 1]
    assert b["applied"] == 2 and b["interviewing"] == 0
    assert b["interview_rate"] == 0.0 and b["offer_rate"] is None
    none_row = by_id[None]
    assert none_row["resume_title"] is None
    assert none_row["applied"] == 1
    assert body["untracked_applied"] == 1
    assert body["min_sample"] == 5


async def test_sample_ok_flag(client):
    """样本诚实性：A 版 5 投达标 sample_ok=True，B 版 2 投 sample_ok=False。"""
    hd = _sid()
    owner = hd["X-Session-Id"]
    now = datetime.now()
    ids = await _seed(owner, [_resume(owner, "达标版"), _resume(owner, "不足版")])
    await _seed(owner, [_job(owner, "applied", apply_at=now, resume_id=ids[0])
                        for _ in range(5)]
                + [_job(owner, "applied", apply_at=now, resume_id=ids[1])
                   for _ in range(2)])
    body = (await client.get("/api/v1/jobs/resume-race", headers=hd)).json()
    by_id = {row["resume_id"]: row for row in body["rows"]}
    assert by_id[ids[0]]["sample_ok"] is True
    assert by_id[ids[1]]["sample_ok"] is False


async def test_deleted_resume_falls_to_untracked(client):
    """简历已删除的历史关联：无法恢复标题，归「未记录」组（不编造）。"""
    hd = _sid()
    owner = hd["X-Session-Id"]
    now = datetime.now()
    # 不建 Resume，直接落库引用不存在的 resume_id
    await _seed(owner, [_job(owner, "applied", apply_at=now, resume_id=9999)])
    body = (await client.get("/api/v1/jobs/resume-race", headers=hd)).json()
    assert body["untracked_applied"] == 1
    assert [row["resume_id"] for row in body["rows"]] == [None]


async def test_status_endpoint_writes_apply_resume_id(client):
    """端点路径：首次标记 applied 带 apply_resume_id → 落库；重复标记不覆盖。"""
    hd = _sid()
    owner = hd["X-Session-Id"]
    ids = await _seed(owner, [_resume(owner, "投递用简历")])
    rid = ids[0]
    job = _job(owner)
    await _seed(owner, [job])
    async with AsyncSessionLocal() as session:
        session.add(job)
        await session.commit()
        await session.refresh(job)
        jid = job.id
    r = await client.put(f"/api/v1/jobs/library/{jid}/status",
                         json={"status": "applied", "apply_channel": "boss",
                               "apply_resume_id": rid},
                         headers=hd)
    assert r.status_code == 200, r.text
    assert r.json()["apply_resume_id"] == rid
    # 重复标记换简历：不覆盖（与 apply_at 首投不覆盖同口径）
    r2 = await client.put(f"/api/v1/jobs/library/{jid}/status",
                          json={"status": "applied", "apply_resume_id": rid + 100},
                          headers=hd)
    assert r2.status_code == 200
    assert r2.json()["apply_resume_id"] == rid


async def test_owner_isolation(client):
    """A 的赛马数据 B 看不到。"""
    ha, hb = _sid(), _sid()
    ids = await _seed(ha["X-Session-Id"], [_resume(ha["X-Session-Id"], "A的简历")])
    await _seed(ha["X-Session-Id"],
                [_job(ha["X-Session-Id"], "offer", apply_at=datetime.now(),
                      resume_id=ids[0])])
    body = (await client.get("/api/v1/jobs/resume-race", headers=hb)).json()
    assert body["rows"] == []
    assert body["untracked_applied"] == 0
