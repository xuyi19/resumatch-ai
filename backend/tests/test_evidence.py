"""证据检索层（RAG-lite）单测：分块、关键词检索、引用校验、检索池去重。

embedding 模式无法在无 Key 环境验证（会自动降级关键词模式），这里只测降级路径，
真实 embedding 链路由配置了 LLM_API_KEY 的手工冒烟覆盖。
"""

import pytest

from app.core.evidence import (
    asearch_evidence,
    build_evidence_index,
    chunk_text,
    filter_valid_ids,
    render_pool,
    retrieval_pool,
)

RESUME = """张三
男 | 1998 年 | 本科 · 某某大学 计算机科学与技术

工作经历
某某科技有限公司 后端开发工程师 2021.07 - 至今
- 负责订单服务设计与开发，QPS 峰值 3000，接口平均耗时下降 40%
- 主导 Redis 缓存改造，命中率提升至 95%，数据库负载下降 60%

项目经历
简历诊断平台 2023.01 - 2023.06
- 基于 LangGraph 编排多智能体，实现简历评分与差距分析自动化
"""

JD = """岗位要求：
1. 熟悉 Python / FastAPI，有高并发服务设计经验
2. 熟悉 Redis、MySQL 等存储
3. 加分项：多智能体 / LLM 应用经验
"""


def test_chunk_ids_stable_and_prefixed():
    chunks = chunk_text(RESUME, "R", 80) + chunk_text(JD, "J", 40)
    r_ids = [c["id"] for c in chunks if c["id"].startswith("R")]
    j_ids = [c["id"] for c in chunks if c["id"].startswith("J")]
    assert r_ids == [f"R{i}" for i in range(1, len(r_ids) + 1)]
    assert j_ids == [f"J{i}" for i in range(1, len(j_ids) + 1)]
    assert all(c["text"].strip() for c in chunks)


def test_keyword_search_ranks_matching_first():
    index = {"chunks": chunk_text(RESUME, "R", 80), "vectors": None, "mode": "keyword"}
    hits = [
        h["id"]
        for h in asearch_sync(index, "Redis 缓存 命中率", k=2)
    ]
    assert hits, "应至少命中一块"
    assert hits[0] == "R3" or "Redis 缓存改造" in _text_of(index, hits[0])


def asearch_sync(index, query, k):
    # 同步封装：keyword 模式不涉网络
    from app.core.evidence import search_evidence

    return search_evidence(index, query, k)


def _text_of(index, chunk_id):
    return next(c["text"] for c in index["chunks"] if c["id"] == chunk_id)


@pytest.mark.asyncio
async def test_build_index_no_api_key_falls_back_to_keyword(monkeypatch):
    monkeypatch.setattr("app.core.evidence._EMBED_DISABLED", False)
    index = await build_evidence_index(RESUME, JD, llm_config={"api_key": ""})
    assert index["mode"] == "keyword"
    assert index["vectors"] is None
    assert len(index["chunks"]) > 5
    # JD 块与简历块都在索引里
    assert any(c["id"].startswith("J") for c in index["chunks"])
    # 检索可用
    hits = await asearch_evidence(index, "高并发 QPS", 2)
    assert hits and all(set(h) >= {"id", "text", "score"} for h in hits)


@pytest.mark.asyncio
async def test_retrieval_pool_dedup_and_cap(monkeypatch):
    index = await build_evidence_index(RESUME, JD, llm_config={"api_key": ""})
    queries = ["Redis 缓存", "缓存 命中率 提升", "LangGraph 多智能体"]
    pool = await retrieval_pool(index, queries, k_per_query=2, cap=3)
    assert len(pool) <= 3
    ids = [e["id"] for e in pool]
    assert len(ids) == len(set(ids)), "池内不应重复"


def test_filter_valid_ids():
    index = {"chunks": [{"id": "R1", "text": "a"}, {"id": "R2", "text": "b"}]}
    assert filter_valid_ids(index, ["R1", "R9", "r2 ", "R1"]) == ["R1", "R2"]
    assert filter_valid_ids(index, []) == []
    assert filter_valid_ids(None, ["R1"]) == []


def test_render_pool():
    pool = [{"id": "R1", "text": "负责订单服务"}]
    assert "[R1] 负责订单服务" in render_pool(pool)
    assert "未能检索到" in render_pool([])
