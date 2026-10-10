"""M72.1 匹配度分解引擎测试：证据接地校验（真证据保留/编造证据降级/hit 无证据降级）/
加权评分 / 无 Key 400 / 生成失败 502 / 简历缺失 400。

LLM 调用一律 monkeypatch call_llm_for_json（app.api.v1.jobs 命名空间），不触网；
uuid 会话（X-Session-Id 头）做 owner 隔离（同 test_job_attribution 惯例）。
"""

from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.v1.jobs import _MatrixRequirement, _MatchMatrix
from app.core.config import settings
from app.main import app

JD = (
    "岗位职责：负责后端服务开发，精通 Python 与 FastAPI，熟悉 MySQL 与 Redis，"
    "3 年以上后端经验，本科及以上学历，有高并发系统经验优先。"
)
RESUME = (
    "张三 ｜ Python 后端开发\n"
    "技能：Python、FastAPI、MySQL、Redis、Docker\n"
    "经历：某科技公司 后端工程师（2022-2025），使用 Python/FastAPI 开发订单服务，"
    "QPS 峰值 3000，MySQL 分库分表，Redis 缓存热点数据。\n"
    "教育：某某大学 本科 计算机科学与技术 2022 毕业"
)


@pytest.fixture
async def client(monkeypatch):
    monkeypatch.setattr(settings, "APP_MODE", "web")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def _sid() -> dict:
    return {"X-Session-Id": f"mm-{uuid4().hex[:12]}"}


def _fake_llm(requirements):
    async def fake(prompt, schema, **kw):
        return _MatchMatrix(requirements=requirements)
    return fake


async def test_evidence_kept_and_score(client, monkeypatch):
    """真证据 hit 保留（跨行空白容忍）；加权评分 = Σ(w·v)/Σw：(5·1+3·0.5+2·0)/10 = 65。"""
    reqs = [
        _MatrixRequirement(requirement="精通 Python", category="skill", weight=5,
                           verdict="hit", evidence="使用 Python/FastAPI 开发订单服务"),
        _MatrixRequirement(requirement="3 年以上后端经验", category="exp", weight=3,
                           verdict="partial", evidence="某科技公司 后端工程师（2022-2025）",
                           gap="可补充更完整的量化结果"),
        _MatrixRequirement(requirement="有高并发系统经验", category="skill", weight=2,
                           verdict="miss", gap="补一段高并发场景的量化描述"),
    ]
    monkeypatch.setattr("app.api.v1.jobs.call_llm_for_json", _fake_llm(reqs))
    r = await client.post("/api/v1/jobs/match-matrix",
                          json={"jd": JD, "resume_text": RESUME}, headers=_sid())
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["score"] == 65
    assert body["counts"] == {"hit": 1, "partial": 1, "miss": 1, "total": 3}
    assert body["rows"][0]["evidence"].startswith("使用 Python")
    assert body["rows"][1]["evidence"].startswith("某科技公司")
    assert "keywords" in body and body["keywords"]["coverage"] >= 0


async def test_fabricated_evidence_downgraded(client, monkeypatch):
    """编造证据（简历中不存在）→ 降级 partial + 证据清空 + 人工核对提示；真证据不受影响。"""
    reqs = [
        _MatrixRequirement(requirement="精通 K8s", category="skill", weight=5,
                           verdict="hit", evidence="主导 Kubernetes 集群万台规模运维"),
        _MatrixRequirement(requirement="熟悉 Redis", category="skill", weight=3,
                           verdict="hit", evidence="Redis 缓存热点数据"),
    ]
    monkeypatch.setattr("app.api.v1.jobs.call_llm_for_json", _fake_llm(reqs))
    body = (await client.post("/api/v1/jobs/match-matrix",
                              json={"jd": JD, "resume_text": RESUME}, headers=_sid())).json()
    r0, r1 = body["rows"]
    assert r0["verdict"] == "partial" and r0["evidence"] == ""
    assert "人工核对" in r0["gap"]
    assert r1["verdict"] == "hit" and r1["evidence"]


async def test_hit_without_evidence_downgraded(client, monkeypatch):
    """hit 但 evidence 留空 → 降级 partial（不给无证据的命中）。"""
    reqs = [_MatrixRequirement(requirement="本科及以上学历", category="edu", weight=3, verdict="hit")]
    monkeypatch.setattr("app.api.v1.jobs.call_llm_for_json", _fake_llm(reqs))
    body = (await client.post("/api/v1/jobs/match-matrix",
                              json={"jd": JD, "resume_text": RESUME}, headers=_sid())).json()
    row = body["rows"][0]
    assert row["verdict"] == "partial" and not row["evidence"]


async def test_no_key_400(client, monkeypatch):
    """未配置 Key（get_llm 的 ValueError）→ 400 带设置页引导文案。"""
    async def no_key(prompt, schema, **kw):
        raise ValueError("未配置 LLM API Key，请在「设置」页填写后重试")
    monkeypatch.setattr("app.api.v1.jobs.call_llm_for_json", no_key)
    r = await client.post("/api/v1/jobs/match-matrix",
                          json={"jd": JD, "resume_text": RESUME}, headers=_sid())
    assert r.status_code == 400
    assert "设置" in r.json()["detail"]


async def test_llm_failure_502(client, monkeypatch):
    async def boom(prompt, schema, **kw):
        raise RuntimeError("timeout")
    monkeypatch.setattr("app.api.v1.jobs.call_llm_for_json", boom)
    r = await client.post("/api/v1/jobs/match-matrix",
                          json={"jd": JD, "resume_text": RESUME}, headers=_sid())
    assert r.status_code == 502


async def test_missing_resume_400(client):
    """resume_id / resume_text 都缺 → 400。"""
    r = await client.post("/api/v1/jobs/match-matrix",
                          json={"jd": JD}, headers=_sid())
    assert r.status_code == 400
