"""M60 投递跟进提醒测试：next_interview_at 编辑回读 / followups 聚合（stale 阈值、
面试日程、状态机流转消失）/ 跟进天数设置校验 / owner 隔离。

uuid 会话（X-Session-Id 头）做 owner 隔离（同 test_job_library 惯例）；
逾期/日程的历史时间无法经 API 回填，直接塞库造数据（naive datetime，同库内口径）。
"""

from datetime import datetime, timedelta
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.core.db import AsyncSessionLocal
from app.main import app
from app.models.entities import SavedJob


@pytest.fixture
async def client(monkeypatch):
    # web 态让 X-Session-Id 头生效（桌面态 owner 恒为 local，无法测隔离）
    monkeypatch.setattr(settings, "APP_MODE", "web")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def _sid() -> dict:
    return {"X-Session-Id": f"fu-{uuid4().hex[:12]}"}


async def _add(client, headers, items):
    return await client.post("/api/v1/jobs/library", json={"items": items}, headers=headers)


async def _seed(owner_id: str, **kw) -> int:
    """直接塞库造数据：apply_at / next_interview_at 历史时间 API 造不出来。"""
    async with AsyncSessionLocal() as session:
        rec = SavedJob(
            owner_id=owner_id,
            title=kw.pop("title", "跟进测试岗"),
            company=kw.pop("company", "跟进公司"),
            jd_text=kw.pop("jd_text", "跟进提醒测试岗位描述，用于直接塞库。"),
            **kw,
        )
        session.add(rec)
        await session.commit()
        await session.refresh(rec)
        return rec.id


# ---------------------------------------------------------------- 面试日程字段


async def test_put_next_interview_at_roundtrip(client):
    """PUT 设日程 → 列表 isoformat 回读；未提供不动；null/非法串清除。"""
    hd = _sid()
    jid = (await _add(client, hd, [{"title": "日程岗", "company": "A 公司",
                                    "jd": "面试日程回读验证岗位描述。"}])).json()["items"][0]["id"]

    resp = await client.put(
        f"/api/v1/jobs/library/{jid}", json={"next_interview_at": "2026-10-15T14:30"}, headers=hd
    )
    assert resp.status_code == 200
    assert resp.json()["next_interview_at"] == "2026-10-15T14:30:00"

    lst = (await client.get("/api/v1/jobs/library", headers=hd)).json()["items"]
    assert lst[0]["id"] == jid and lst[0]["next_interview_at"] == "2026-10-15T14:30:00"

    # 未提供该字段的其他编辑不动日程
    resp = await client.put(f"/api/v1/jobs/library/{jid}", json={"salary": "20-30K"}, headers=hd)
    assert resp.json()["next_interview_at"] == "2026-10-15T14:30:00"

    # 显式 null = 清除
    resp = await client.put(
        f"/api/v1/jobs/library/{jid}", json={"next_interview_at": None}, headers=hd
    )
    assert resp.status_code == 200 and resp.json()["next_interview_at"] is None

    # 非法串容错：不炸、按清除处理（同 backup._parse_dt 口径）
    resp = await client.put(
        f"/api/v1/jobs/library/{jid}", json={"next_interview_at": "not-a-date"}, headers=hd
    )
    assert resp.status_code == 200 and resp.json()["next_interview_at"] is None


# ---------------------------------------------------------------- followups 空态


async def test_followups_empty(client):
    """新建 owner 无数据 → days 默认 7、两个列表全空。"""
    hd = _sid()
    resp = await client.get("/api/v1/jobs/followups", headers=hd)
    assert resp.status_code == 200
    body = resp.json()
    assert body["days"] == 7
    assert body["stale_applies"] == []
    assert body["upcoming_interviews"] == []


# ---------------------------------------------------------------- stale 判定


async def test_stale_applies_lifecycle(client):
    """applied 8 天前 → 出现且 days=8；流转 interviewing → 消失（状态机驱动）。"""
    hd = _sid()
    owner = hd["X-Session-Id"]
    jid = await _seed(owner, status="applied", apply_at=datetime.now() - timedelta(days=8))
    # 非 applied 状态不进 stale（即使 apply_at 更早）
    await _seed(owner, title="未投岗", status="wish", apply_at=datetime.now() - timedelta(days=10))

    body = (await client.get("/api/v1/jobs/followups", headers=hd)).json()
    assert [s["id"] for s in body["stale_applies"]] == [jid]
    item = body["stale_applies"][0]
    assert item["days"] == 8 and item["title"] == "跟进测试岗"
    assert item["apply_at"]  # isoformat 字符串

    # 状态流转 interviewing → 提醒自然消失，无 dismiss
    resp = await client.put(
        f"/api/v1/jobs/library/{jid}/status", json={"status": "interviewing"}, headers=hd
    )
    assert resp.status_code == 200
    body = (await client.get("/api/v1/jobs/followups", headers=hd)).json()
    assert body["stale_applies"] == []


async def test_followup_threshold(client):
    """阈值判定：默认 7 天时 5 天前不出现；调低到 3 出现；0/31/abc → 422。"""
    hd = _sid()
    owner = hd["X-Session-Id"]
    jid = await _seed(owner, status="applied", apply_at=datetime.now() - timedelta(days=5))

    # 默认 7 天：5 天前不提醒
    body = (await client.get("/api/v1/jobs/followups", headers=hd)).json()
    assert body["days"] == 7 and body["stale_applies"] == []

    # 调低到 3 天 → 出现；GET 回读一致
    resp = await client.put("/api/v1/settings/followup-days", json={"days": 3}, headers=hd)
    assert resp.status_code == 200 and resp.json()["days"] == 3
    assert (await client.get("/api/v1/settings/followup-days", headers=hd)).json()["days"] == 3
    body = (await client.get("/api/v1/jobs/followups", headers=hd)).json()
    assert [s["id"] for s in body["stale_applies"]] == [jid] and body["days"] == 3

    # 边界校验：0 / 31 越界 422；非整数 pydantic 422
    for bad in (0, 31, "abc"):
        resp = await client.put("/api/v1/settings/followup-days", json={"days": bad}, headers=hd)
        assert resp.status_code == 422, f"days={bad} 应 422"


# ---------------------------------------------------------------- 面试日程


async def test_upcoming_interviews(client):
    """明天面试 → days_left=1；closed/offer 终态不出现；逾期按时间正序排最前。"""
    hd = _sid()
    owner = hd["X-Session-Id"]
    jid = await _seed(owner, status="applied",
                      next_interview_at=datetime.now() + timedelta(days=1))
    past_id = await _seed(owner, title="逾期面试岗", status="interviewing",
                          next_interview_at=datetime.now() - timedelta(days=2))
    closed_id = await _seed(owner, title="已结束岗", status="closed",
                            next_interview_at=datetime.now() + timedelta(days=2))

    body = (await client.get("/api/v1/jobs/followups", headers=hd)).json()
    items = body["upcoming_interviews"]
    ids = [u["id"] for u in items]
    assert jid in ids and past_id in ids and closed_id not in ids
    # 时间正序：逾期最久的排最前；days_left 按日期差计算
    assert ids.index(past_id) < ids.index(jid)
    past = next(u for u in items if u["id"] == past_id)
    assert past["days_left"] == -2 and past["status"] == "interviewing"
    item = next(u for u in items if u["id"] == jid)
    assert item["days_left"] == 1 and item["status"] == "applied"

    # 优化⑪ 月历全量字段：与列表同源同序，只是不吃 10 条截断
    all_ids = [u["id"] for u in body["upcoming_interviews_all"]]
    assert all_ids == ids


async def test_upcoming_interviews_cap(client):
    """列表字段 cap 10；月历全量字段 11 条不截断（优化⑪）。"""
    hd = _sid()
    owner = hd["X-Session-Id"]
    for i in range(11):
        await _seed(owner, title=f"日程岗{i}", status="interviewing",
                    next_interview_at=datetime.now() + timedelta(days=i + 1))

    body = (await client.get("/api/v1/jobs/followups", headers=hd)).json()
    assert len(body["upcoming_interviews"]) == 10
    assert len(body["upcoming_interviews_all"]) == 11


# ---------------------------------------------------------------- owner 隔离


async def test_followups_owner_isolation(client):
    """A 的逾期岗位与面试日程不出现在 B 的 followups。"""
    hd_a, hd_b = _sid(), _sid()
    owner_a = hd_a["X-Session-Id"]
    jid = await _seed(owner_a, status="applied", apply_at=datetime.now() - timedelta(days=9),
                      next_interview_at=datetime.now() + timedelta(days=3))

    body_b = (await client.get("/api/v1/jobs/followups", headers=hd_b)).json()
    assert body_b["stale_applies"] == [] and body_b["upcoming_interviews"] == []

    body_a = (await client.get("/api/v1/jobs/followups", headers=hd_a)).json()
    assert [s["id"] for s in body_a["stale_applies"]] == [jid]
    assert [u["id"] for u in body_a["upcoming_interviews"]] == [jid]
