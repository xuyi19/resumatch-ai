"""M72 求职归因测试：漏斗口径（ever_applied 含投后 closed、wish/未投 closed 不计）/
转化率与 None 口径 / 规则归因触发与样本量诚实性 / owner 隔离。

uuid 会话（X-Session-Id 头）做 owner 隔离（同 test_weekly_report 惯例）；
「超 N 天未流转」用显式 apply_at 老日期构造（同库 naive datetime 口径）。
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
    monkeypatch.setattr(settings, "APP_MODE", "web")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def _sid() -> dict:
    return {"X-Session-Id": f"at-{uuid4().hex[:12]}"}


def _job(owner, status="wish", apply_at=None) -> SavedJob:
    return SavedJob(owner_id=owner, title="后端工程师", jd_text="归因测试岗位描述。",
                    status=status, apply_at=apply_at,
                    created_at=datetime(2026, 9, 1))


async def _seed(owner, rows):
    async with AsyncSessionLocal() as session:
        for row in rows:
            session.add(row)
        await session.commit()


# ---------------------------------------------------------------- 口径与转化率


async def test_empty_owner_returns_building_sample(client):
    """空数据：漏斗全 0、转化率 None、仍给积累期假设引导去投递。"""
    hd = _sid()
    r = await client.get("/api/v1/jobs/attribution", headers=hd)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["funnel"]["applied"] == 0
    assert body["rates"]["interview_rate"] is None
    assert body["rates"]["offer_rate"] is None
    assert body["hypotheses"][0]["id"] == "building_sample"


async def test_funnel_counts_and_rates(client):
    """口径：wish/未投 closed 不计；投后 closed 计投递；interviewing+offer 进面；
    停滞只算仍停留 applied 的老投递。"""
    hd = _sid()
    owner = hd["X-Session-Id"]
    old = datetime.now() - timedelta(days=30)
    await _seed(owner, [
        _job(owner, "wish"),                              # 不进漏斗
        _job(owner, "applied", apply_at=old),             # 投递 + 停滞
        _job(owner, "applied", apply_at=datetime.now()),  # 投递（新鲜）
        _job(owner, "interviewing", apply_at=old),        # 投递 + 进面
        _job(owner, "offer", apply_at=old),               # 投递 + 进面 + offer
        _job(owner, "closed", apply_at=old),              # 投后结束：计投递
        _job(owner, "closed"),                            # 没投就关：不计
    ])
    r = await client.get("/api/v1/jobs/attribution", headers=hd)
    assert r.status_code == 200, r.text
    body = r.json()
    f = body["funnel"]
    assert f["applied"] == 5
    assert f["interviewing"] == 2
    assert f["offer"] == 1
    assert f["closed_after_apply"] == 1
    assert f["wish"] == 1
    assert body["rates"]["interview_rate"] == round(2 / 5, 3)
    assert body["rates"]["offer_rate"] == round(1 / 2, 3)
    assert body["rates"]["stale_count"] == 1
    assert body["rates"]["stale_avg_days"] == 30.0
    # 有 offer：正向假设在场且排最前（severity ok 排序位于唯一假设）
    assert body["hypotheses"][0]["id"] == "positive"


# ---------------------------------------------------------------- 规则归因


async def test_resume_weak_hypothesis_high(client):
    """投 12 份仅 1 进面（约面率 8.3% < 10%）→ 简历卡点 high 排最前，带诊断深链。"""
    hd = _sid()
    owner = hd["X-Session-Id"]
    old = datetime.now() - timedelta(days=10)
    await _seed(owner, [_job(owner, "interviewing", apply_at=old)]
                + [_job(owner, "applied", apply_at=old) for _ in range(11)])
    body = (await client.get("/api/v1/jobs/attribution", headers=hd)).json()
    assert body["rates"]["interview_rate"] < 0.10
    top = body["hypotheses"][0]
    assert top["id"] == "resume_weak"
    assert top["severity"] == "high"
    assert any(a["to"] == "/app/analyze" for a in top["actions"])


async def test_interview_weak_without_resume_rule(client):
    """进面 3 家 0 offer（约面率 30% 不触发简历假设）→ 面试卡点假设，带面试/刷题深链。"""
    hd = _sid()
    owner = hd["X-Session-Id"]
    now = datetime.now()
    await _seed(owner, [_job(owner, "interviewing", apply_at=now) for _ in range(3)]
                + [_job(owner, "applied", apply_at=now) for _ in range(7)])
    body = (await client.get("/api/v1/jobs/attribution", headers=hd)).json()
    ids = [h["id"] for h in body["hypotheses"]]
    assert "resume_weak" not in ids
    assert "resume_weak_soft" not in ids
    assert "interview_weak" in ids
    iv = next(h for h in body["hypotheses"] if h["id"] == "interview_weak")
    links = {a["to"] for a in iv["actions"]}
    assert "/app/interview" in links and "/app/quiz" in links


async def test_small_sample_only_building(client):
    """投 3 份刚投的：样本 <5 不做转化归因，只有积累期提示；停滞 0（未到阈值天数）。"""
    hd = _sid()
    owner = hd["X-Session-Id"]
    now = datetime.now()
    await _seed(owner, [_job(owner, "applied", apply_at=now) for _ in range(3)])
    body = (await client.get("/api/v1/jobs/attribution", headers=hd)).json()
    assert [h["id"] for h in body["hypotheses"]] == ["building_sample"]
    assert body["rates"]["stale_count"] == 0


async def test_owner_isolation(client):
    """A 的 Offer 数据 B 看不到（uuid owner 隔离）。"""
    ha, hb = _sid(), _sid()
    await _seed(ha["X-Session-Id"], [_job(ha["X-Session-Id"], "offer",
                                          apply_at=datetime.now())])
    body = (await client.get("/api/v1/jobs/attribution", headers=hb)).json()
    assert body["funnel"]["applied"] == 0
    assert body["funnel"]["offer"] == 0
