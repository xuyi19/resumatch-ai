"""M65 项目素材库测试：STAR 卡片 CRUD + 校验 + owner 会话隔离 + AI 生成草稿。

用 uuid 会话（X-Session-Id 头）做 owner 隔离（同 test_job_library.py 惯例）；
generate 场景 monkeypatch star 模块命名空间的 call_llm_for_json
（from-import 直引必须 setattr 模块，同 test_jobs.py 惯例）。
"""

from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.main import app


@pytest.fixture
async def client(monkeypatch):
    # web 态让 X-Session-Id 头生效（桌面态 owner 恒为 local，无法测隔离）
    monkeypatch.setattr(settings, "APP_MODE", "web")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def _sid() -> dict:
    return {"X-Session-Id": f"star-{uuid4().hex[:12]}"}


CARD = {
    "title": "高并发订单系统优化",
    "role": "后端负责人",
    "tags": "Python,FastAPI,MySQL",
    "situation": "订单峰值流量激增，核心接口 P99 超过 800ms。",
    "task": "在不改变业务逻辑的前提下把 P99 降到 200ms 以内。",
    "action": "引入本地缓存与读写分离，治理慢 SQL，热点接口批量合并。",
    "result": "P99 从 800ms 降至 120ms，故障率下降 90%。",
}


# ---------------------------------------------------------------- CRUD


async def test_star_crud_flow(client):
    """建 → 列表（updated_at 倒序）→ 部分更新（未提供字段不动 + updated_at 变化）→ 单删 → 幂等删。"""
    hd = _sid()
    resp = await client.post("/api/v1/star/cards", json=CARD, headers=hd)
    assert resp.status_code == 200, resp.text
    first = resp.json()
    assert first["title"] == CARD["title"]
    assert first["tags"] == "Python,FastAPI,MySQL"
    assert first["result"].startswith("P99")

    resp2 = await client.post("/api/v1/star/cards", json={"title": "第二张卡"}, headers=hd)
    assert resp2.status_code == 200
    second = resp2.json()

    # 列表：updated_at 倒序（后建的在前）
    lst = (await client.get("/api/v1/star/cards", headers=hd)).json()["items"]
    assert [c["id"] for c in lst] == [second["id"], first["id"]]

    # 部分更新：仅显式提供字段动，updated_at 刷新
    resp = await client.put(
        f"/api/v1/star/cards/{first['id']}",
        json={"result": "P99 降至 100ms，QPS 提升 3 倍。"},
        headers=hd,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["result"].startswith("P99 降至 100ms")
    assert body["title"] == CARD["title"]        # 未提供字段不动
    assert body["situation"] == CARD["situation"]
    assert body["tags"] == CARD["tags"]
    assert body["updated_at"] != first["updated_at"]  # 更新时间刷新

    # 被更新的卡排到最前（updated_at 倒序）
    lst = (await client.get("/api/v1/star/cards", headers=hd)).json()["items"]
    assert [c["id"] for c in lst] == [first["id"], second["id"]]

    # 单删 → 幂等删
    resp = await client.delete(f"/api/v1/star/cards/{second['id']}", headers=hd)
    assert resp.status_code == 200 and resp.json()["deleted"] == 1
    resp = await client.delete(f"/api/v1/star/cards/{second['id']}", headers=hd)
    assert resp.status_code == 200 and resp.json()["deleted"] == 0
    lst = (await client.get("/api/v1/star/cards", headers=hd)).json()["items"]
    assert [c["id"] for c in lst] == [first["id"]]


async def test_star_validates_title_and_null(client):
    """title 缺失/空白 → 422；显式 null 字段转空串不炸。"""
    hd = _sid()
    resp = await client.post("/api/v1/star/cards", json={"title": "   "}, headers=hd)
    assert resp.status_code == 422
    resp = await client.post("/api/v1/star/cards", json={}, headers=hd)
    assert resp.status_code == 422

    resp = await client.post(
        "/api/v1/star/cards",
        json={"title": "空值容错卡", "role": None, "tags": None, "situation": None,
              "task": None, "action": None, "result": None},
        headers=hd,
    )
    assert resp.status_code == 200, resp.text
    card = resp.json()
    assert card["role"] == "" and card["tags"] == "" and card["situation"] == ""
    assert card["task"] == "" and card["action"] == "" and card["result"] == ""


async def test_star_owner_isolation(client):
    """会话 A 的素材卡，会话 B 看不见 / 改不了（404）/ 删不掉（deleted=0）。"""
    hd_a, hd_b = _sid(), _sid()
    card_id = (await client.post("/api/v1/star/cards", json=CARD, headers=hd_a)).json()["id"]

    assert (await client.get("/api/v1/star/cards", headers=hd_b)).json()["items"] == []
    resp = await client.put(
        f"/api/v1/star/cards/{card_id}", json={"title": "篡改"}, headers=hd_b
    )
    assert resp.status_code == 404
    resp = await client.delete(f"/api/v1/star/cards/{card_id}", headers=hd_b)
    assert resp.status_code == 200 and resp.json()["deleted"] == 0

    # A 仍能看到且未被篡改
    lst = (await client.get("/api/v1/star/cards", headers=hd_a)).json()["items"]
    assert len(lst) == 1 and lst[0]["title"] == CARD["title"]


# ---------------------------------------------------------------- AI 生成


async def test_star_generate_success(client, monkeypatch):
    """mock call_llm_for_json → draft 正常返回、tags 数组转逗号串；<30 字 422；LLM 异常 502。"""
    import app.api.v1.star as star_mod

    async def _fake(prompt, schema, **kw):
        return star_mod.StarDraft(
            title="订单系统性能优化", role="后端负责人",
            tags=["Python", "高并发", "MySQL"],
            situation="峰值流量激增", task="降低 P99",
            action="缓存 + 读写分离", result="P99 下降 85%",
        )

    monkeypatch.setattr(star_mod, "call_llm_for_json", _fake)
    hd = _sid()
    resp = await client.post(
        "/api/v1/star/generate",
        json={"text": "我负责订单系统的性能优化，大促峰值流量激增导致核心接口 P99 超标，"
                      "通过引入缓存与读写分离、治理慢 SQL，最终 P99 下降 85%。",
              "llm_config": {}},
        headers=hd,
    )
    assert resp.status_code == 200, resp.text
    draft = resp.json()["draft"]
    assert draft["title"] == "订单系统性能优化"
    assert draft["tags"] == "Python,高并发,MySQL"  # 数组 → 逗号串
    assert draft["result"] == "P99 下降 85%"

    # 输入 <30 字 → 422 项目描述太短
    resp = await client.post(
        "/api/v1/star/generate", json={"text": "太短的描述"}, headers=hd
    )
    assert resp.status_code == 422
    assert "项目描述太短" in resp.json()["detail"]

    # LLM 异常 → 502 附原因，不降级
    async def _boom(*args, **kwargs):
        raise RuntimeError("llm unavailable")

    monkeypatch.setattr(star_mod, "call_llm_for_json", _boom)
    resp = await client.post(
        "/api/v1/star/generate",
        json={"text": "足够长的项目描述文本，用于触发 LLM 异常路径的验证，"
                      "包含性能优化、缓存设计与读写分离等内容。"},
        headers=hd,
    )
    assert resp.status_code == 502
    assert "llm unavailable" in resp.json()["detail"]


async def test_star_generate_tolerates_missing_fields(client, monkeypatch):
    """LLM 输出缺键容错：缺 result/tags 等键 → 对应字段为空串，不炸。"""
    import app.api.v1.star as star_mod

    async def _fake(prompt, schema, **kw):
        # 只给 title/situation，其余键全缺
        return star_mod.StarDraft(title="缺字段卡", situation="只有情境段")

    monkeypatch.setattr(star_mod, "call_llm_for_json", _fake)
    hd = _sid()
    resp = await client.post(
        "/api/v1/star/generate",
        json={"text": "一段超过三十字的项目描述文本，用于验证 AI 输出缺字段时的容错"
                      "处理逻辑是否正常，不会因为缺少键而报错。"},
        headers=hd,
    )
    assert resp.status_code == 200, resp.text
    draft = resp.json()["draft"]
    assert draft["title"] == "缺字段卡"
    assert draft["situation"] == "只有情境段"
    assert draft["result"] == "" and draft["tags"] == "" and draft["role"] == ""
