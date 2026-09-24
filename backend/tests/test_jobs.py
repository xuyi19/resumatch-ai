"""M19/M30 岗位市场测试：数据源适配层 + /jobs API + 数据源测试端点 + 手动导入比对。

外部 HTTP 全部走 MockProvider（测试不访问真实三方 API）；
LLM 精排失败场景用 monkeypatch 模拟。
"""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services.job_market import (
    JobProviderError,
    MockProvider,
    coarse_rank,
    create_provider,
    jaccard,
    parse_llm_ranking,
)


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# ---------------------------------------------------------------- 适配层


def test_mock_search_filters_by_keyword():
    items, fallback = MockProvider().search("Python 后端", page=1)
    assert items and not fallback
    assert all("python" in (j.title + j.jd_text).lower() or "后端" in j.title for j in items)


def test_mock_search_fallback_when_no_hit():
    items, fallback = MockProvider().search("绝不存在的关键词xyzzy", page=1)
    assert fallback and len(items) == 12


def test_mock_pagination():
    p = MockProvider()
    page1, _ = p.search("", page=1, page_size=5)
    page2, _ = p.search("", page=2, page_size=5)
    assert len(page1) == 5 and len(page2) == 5
    assert page1[0].id != page2[0].id


def test_create_provider_unknown_falls_back_to_mock():
    assert create_provider("no-such-provider").name == "mock"
    # 已删除的海外数据源标识也回退 mock（M30 清理后的兼容行为）
    assert create_provider("jsearch").name == "mock"
    assert create_provider("adzuna").name == "mock"


def test_jaccard_and_coarse_rank():
    assert jaccard(["a", "b"], ["b", "a"]) == 1.0
    assert jaccard(["a"], ["b"]) == 0.0
    jobs, _ = MockProvider().search("", page=1, page_size=100)
    ranked = coarse_rank(
        "熟悉 Python FastAPI MySQL Redis，做过后端开发与高并发服务优化",
        jobs,
    )
    assert ranked[0][1] >= ranked[-1][1]
    assert ranked[0][0].title == "Python 后端开发工程师"


def test_parse_llm_ranking_filters_invalid_ids():
    content = '```json\n[{"id":"mock-1","score":88,"reason":"对口"},{"id":"fake-99","score":99,"reason":"幻觉"}]\n```'
    out = parse_llm_ranking(content, ["mock-1", "mock-2"])
    assert out is not None and len(out) == 1
    assert out[0]["id"] == "mock-1" and out[0]["score"] == 88
    assert parse_llm_ranking("not json at all", ["mock-1"]) is None


# ---------------------------------------------------------------- API


async def test_api_jobs_search_mock(client):
    resp = await client.post(
        "/api/v1/jobs/search",
        json={"provider": "mock", "keyword": "前端", "page": 1},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["items"] and not body["fallback"]
    assert body["items"][0]["title"]


async def test_api_jobs_import_match_degrades_without_llm(client, monkeypatch):
    """M30 手动导入比对：LLM 不可用 → 降级关键词排序；来源标记「手动导入」。"""
    import app.api.v1.jobs as jobs_mod

    def _boom(*args, **kwargs):
        raise RuntimeError("llm unavailable")

    monkeypatch.setattr(jobs_mod, "get_llm", _boom)
    resp = await client.post(
        "/api/v1/jobs/import-match",
        json={
            "resume_text": "本科，熟悉 Python FastAPI MySQL Redis，做过后端开发与高并发服务优化",
            "items": [
                {"company": "字节跳动", "title": "前端工程师", "city": "北京"},
                {"company": "某银行科技", "title": "Python 后端工程师", "city": "杭州",
                 "salary": "25-40K", "jd": "负责核心系统研发，要求熟悉 Python、FastAPI、MySQL、Redis。"},
            ],
            "llm_config": {},
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["degraded"] is True
    assert len(body["items"]) == 2
    assert all(j["source"] == "手动导入" for j in body["items"])
    # Python 后端岗位 JD 与简历重合度高，应排在纯标题占位的前端岗之前
    assert body["items"][0]["title"] == "Python 后端工程师"
    scores = [j["score"] for j in body["items"]]
    assert scores == sorted(scores, reverse=True)


async def test_api_jobs_import_match_validates(client):
    """items 为空 / 简历过短 → 422"""
    resp = await client.post(
        "/api/v1/jobs/import-match", json={"resume_text": "太短", "items": []}
    )
    assert resp.status_code == 422


async def test_api_jobs_recommend_degrades_without_llm(client, monkeypatch):
    """LLM 不可用 → 自动降级为关键词排序，接口不失败。"""
    import app.api.v1.jobs as jobs_mod

    def _boom(*args, **kwargs):
        raise RuntimeError("llm unavailable")

    monkeypatch.setattr(jobs_mod, "get_llm", _boom)
    resp = await client.post(
        "/api/v1/jobs/recommend",
        json={
            "provider": "mock",
            "keyword": "",
            "resume_text": "本科，熟悉 Python FastAPI MySQL Redis，做过后端开发与高并发服务",
            "top_n": 5,
            "llm_config": {},
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["items"]) == 5
    assert body["degraded"] is True
    assert body["items"][0]["title"] == "Python 后端开发工程师"
    assert 0 <= body["items"][0]["score"] <= 100


async def test_api_jobs_recommend_validates_resume(client):
    resp = await client.post(
        "/api/v1/jobs/recommend",
        json={"provider": "mock", "keyword": "", "resume_text": "太短"},
    )
    assert resp.status_code == 422


async def test_api_settings_test_job_mock(client):
    resp = await client.post("/api/v1/settings/test-job", json={"provider": "mock"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True and body["provider"] == "mock"
