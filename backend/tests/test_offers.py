"""M62 Offer 比较决策器测试：CRUD + 校验 + owner 会话隔离 + compare 评分数学与结论模板。

用 uuid 会话（X-Session-Id 头）做 owner 隔离（同 test_star.py 惯例）；
评分/结论为纯本地确定性计算，score_offers / build_conclusion 从模块 import 直测，
不等价 HTTP 覆盖。
"""

from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.v1 import offers as offers_mod
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
    return {"X-Session-Id": f"offer-{uuid4().hex[:12]}"}


# ---------------------------------------------------------------- CRUD


async def test_offer_crud_flow(client):
    """建（默认值兜底）→ 列表（updated_at 倒序）→ 部分更新 → 幂等删。"""
    hd = _sid()
    # 只给必填三项，其余字段回落默认值
    resp = await client.post(
        "/api/v1/offers",
        json={"company": "甲公司", "title": "后端工程师", "monthly_salary": 20},
        headers=hd,
    )
    assert resp.status_code == 200, resp.text
    first = resp.json()
    assert first["city"] == "" and first["notes"] == ""
    assert first["salary_months"] == 12 and first["commute_minutes"] == 45
    assert first["insurance"] == 3 and first["development"] == 3 and first["stability"] == 3
    assert first["annual"] == 240  # 20K × 12

    resp2 = await client.post(
        "/api/v1/offers",
        json={"company": "乙公司", "title": "前端工程师", "monthly_salary": 25,
              "city": "上海", "salary_months": 14, "commute_minutes": 30,
              "insurance": 4, "development": 4, "stability": 5, "notes": "期权诱人"},
        headers=hd,
    )
    assert resp2.status_code == 200, resp.text
    second = resp2.json()
    assert second["annual"] == 350  # 25K × 14

    # 列表：updated_at 倒序（后建的在前）
    lst = (await client.get("/api/v1/offers", headers=hd)).json()["items"]
    assert [o["id"] for o in lst] == [second["id"], first["id"]]

    # 部分更新：仅显式提供字段动，updated_at 刷新
    resp = await client.put(
        f"/api/v1/offers/{first['id']}",
        json={"monthly_salary": 30, "city": "杭州"},
        headers=hd,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["monthly_salary"] == 30 and body["city"] == "杭州"
    assert body["annual"] == 360
    assert body["title"] == "后端工程师"          # 未提供字段不动
    assert body["salary_months"] == 12 and body["insurance"] == 3
    assert body["updated_at"] != first["updated_at"]  # 更新时间刷新

    # 被更新的排到最前
    lst = (await client.get("/api/v1/offers", headers=hd)).json()["items"]
    assert [o["id"] for o in lst] == [first["id"], second["id"]]

    # 单删 → 幂等删
    resp = await client.delete(f"/api/v1/offers/{second['id']}", headers=hd)
    assert resp.status_code == 200 and resp.json()["deleted"] == 1
    resp = await client.delete(f"/api/v1/offers/{second['id']}", headers=hd)
    assert resp.status_code == 200 and resp.json()["deleted"] == 0


async def test_offer_validations_and_null(client):
    """company/title 空白 422、monthly_salary 缺失/0/501 422、salary_months 11/19 422、
    其他越界 422；显式 null 容错回落默认值。"""
    hd = _sid()
    base = {"company": "甲公司", "title": "后端", "monthly_salary": 20}
    # 空白必填
    for field in ("company", "title"):
        bad = {**base, field: "   "}
        assert (await client.post("/api/v1/offers", json=bad, headers=hd)).status_code == 422
    # 月薪缺失 / 越界
    no_salary = {k: v for k, v in base.items() if k != "monthly_salary"}
    assert (await client.post("/api/v1/offers", json=no_salary, headers=hd)).status_code == 422
    for salary in (0, 501):
        bad = {**base, "monthly_salary": salary}
        resp = await client.post("/api/v1/offers", json=bad, headers=hd)
        assert resp.status_code == 422 and "月薪" in resp.json()["detail"]
    # salary_months 11 / 19
    for months in (11, 19):
        bad = {**base, "salary_months": months}
        resp = await client.post("/api/v1/offers", json=bad, headers=hd)
        assert resp.status_code == 422 and "年薪月数" in resp.json()["detail"]
    # 通勤 / 三档自评越界
    for field, lo, hi in (("commute_minutes", 241, None), ("insurance", 0, 6),
                          ("development", 0, 6), ("stability", 0, 6)):
        for value in ([lo] if hi is None else [lo, hi]):
            bad = {**base, field: value}
            assert (await client.post("/api/v1/offers", json=bad, headers=hd)).status_code == 422

    # PUT 传越界值同样 422
    created = (await client.post("/api/v1/offers", json=base, headers=hd)).json()
    for payload in ({"monthly_salary": 0}, {"salary_months": 11}, {"stability": 6}):
        resp = await client.put(f"/api/v1/offers/{created['id']}", json=payload, headers=hd)
        assert resp.status_code == 422
    # PUT 不存在的 id → 404
    resp = await client.put("/api/v1/offers/99999", json={"city": "北京"}, headers=hd)
    assert resp.status_code == 404

    # 显式 null 容错：可选字段 null → 默认值
    resp = await client.post(
        "/api/v1/offers",
        json={"company": "空值容错", "title": "后端", "monthly_salary": 20,
              "city": None, "salary_months": None, "commute_minutes": None,
              "insurance": None, "development": None, "stability": None, "notes": None},
        headers=hd,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["city"] == "" and body["notes"] == ""
    assert body["salary_months"] == 12 and body["commute_minutes"] == 45
    assert body["insurance"] == 3 and body["development"] == 3 and body["stability"] == 3


async def test_offer_owner_isolation(client):
    """会话 A 的 Offer，会话 B 看不见 / 改不了（404）/ 删不掉（deleted=0）/ compare 过滤掉。"""
    hd_a, hd_b = _sid(), _sid()
    offer_id = (
        await client.post(
            "/api/v1/offers",
            json={"company": "甲公司", "title": "后端", "monthly_salary": 20},
            headers=hd_a,
        )
    ).json()["id"]

    assert (await client.get("/api/v1/offers", headers=hd_b)).json()["items"] == []
    resp = await client.put(
        f"/api/v1/offers/{offer_id}", json={"title": "篡改"}, headers=hd_b
    )
    assert resp.status_code == 404
    resp = await client.delete(f"/api/v1/offers/{offer_id}", headers=hd_b)
    assert resp.status_code == 200 and resp.json()["deleted"] == 0

    # B 的 compare 只有自己的（0 个）→ 过滤后 <2 → 422
    resp = await client.post("/api/v1/offers/compare", json={"ids": [offer_id, 99999]}, headers=hd_b)
    assert resp.status_code == 422 and "无效或他人" in resp.json()["detail"]

    # A 仍能看到且未被篡改
    lst = (await client.get("/api/v1/offers", headers=hd_a)).json()["items"]
    assert len(lst) == 1 and lst[0]["title"] == "后端"


# ---------------------------------------------------------------- compare（HTTP 层）


async def _mk_offer(client, hd, **kw):
    payload = {"company": kw.pop("company"), "title": kw.pop("title", "后端"), "monthly_salary": 20}
    payload.update(kw)
    resp = await client.post("/api/v1/offers", json=payload, headers=hd)
    assert resp.status_code == 200, resp.text
    return resp.json()


async def test_compare_math_and_conclusion(client):
    """min-max 归一（60~100）、全同薪资全 100、total 降序 rank、conclusion 含总分第一公司名。"""
    hd = _sid()
    low = await _mk_offer(client, hd, company="低薪厂", monthly_salary=20,
                          commute_minutes=45, insurance=3, development=3, stability=3)
    high = await _mk_offer(client, hd, company="高薪厂", monthly_salary=30,
                           commute_minutes=45, insurance=3, development=3, stability=3)

    resp = await client.post("/api/v1/offers/compare", json={"ids": [low["id"], high["id"]]}, headers=hd)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    items = body["items"]
    assert [it["id"] for it in items] == [high["id"], low["id"]]  # total 降序
    assert items[0]["rank"] == 1 and items[1]["rank"] == 2
    # 20K×12=240 vs 30K×12=360 → salary 60 / 100
    assert items[0]["scores"]["salary"] == 100.0
    assert items[1]["scores"]["salary"] == 60.0
    # 通勤全同（45）→ 都 100 分
    assert items[0]["scores"]["commute"] == 100.0 and items[1]["scores"]["commute"] == 100.0
    # 默认权重下：0.4*score + 0.15*100 + 0.15*60 + 0.2*60 + 0.1*60
    assert items[0]["total"] == 82.0 and items[1]["total"] == 66.0
    assert items[0]["annual"] == 360 and items[1]["annual"] == 240
    # conclusion：总分第一公司名 + 年薪包 36.0 万（通勤最短/发展最高者都是第一名本人 → 不重复点名）
    assert "高薪厂" in body["conclusion"] and "82.0" in body["conclusion"]
    assert "36.0 万" in body["conclusion"]
    assert "通勤最短" not in body["conclusion"]


async def test_compare_equal_salary_all_full_score(client):
    """全同薪资 → salary 全 100（防 0 分），通勤短者领先。"""
    hd = _sid()
    near = await _mk_offer(client, hd, company="近厂", monthly_salary=20, commute_minutes=30)
    far = await _mk_offer(client, hd, company="远厂", monthly_salary=20, commute_minutes=90)

    resp = await client.post("/api/v1/offers/compare", json={"ids": [far["id"], near["id"]]}, headers=hd)
    assert resp.status_code == 200, resp.text
    items = resp.json()["items"]
    assert all(it["scores"]["salary"] == 100.0 for it in items)
    # 通勤 30 vs 90 → 100 / 60
    by_company = {it["company"]: it for it in items}
    assert by_company["近厂"]["scores"]["commute"] == 100.0
    assert by_company["远厂"]["scores"]["commute"] == 60.0
    assert items[0]["company"] == "近厂" and items[0]["rank"] == 1


async def test_compare_custom_weights_normalized(client):
    """自定义权重归一化生效：salary 80 / commute 20（其余 0）→ total = 0.8*salary + 0.2*commute。"""
    hd = _sid()
    low = await _mk_offer(client, hd, company="低薪厂", monthly_salary=20, commute_minutes=45)
    high = await _mk_offer(client, hd, company="高薪厂", monthly_salary=30, commute_minutes=45)

    resp = await client.post(
        "/api/v1/offers/compare",
        json={"ids": [low["id"], high["id"]],
              "weights": {"salary": 80, "commute": 20, "insurance": 0,
                          "development": 0, "stability": 0}},
        headers=hd,
    )
    assert resp.status_code == 200, resp.text
    items = resp.json()["items"]
    assert items[0]["total"] == 100.0  # 0.8*100 + 0.2*100
    assert items[1]["total"] == 68.0   # 0.8*60 + 0.2*100


async def test_compare_request_validations(client):
    """ids<2 / >6 / 全零权重 / 非法权重值 → 422。"""
    hd = _sid()
    a = await _mk_offer(client, hd, company="甲厂", monthly_salary=20)
    b = await _mk_offer(client, hd, company="乙厂", monthly_salary=25)

    resp = await client.post("/api/v1/offers/compare", json={"ids": [a["id"]]}, headers=hd)
    assert resp.status_code == 422 and "至少选两个 Offer" in resp.json()["detail"]
    resp = await client.post(
        "/api/v1/offers/compare", json={"ids": [1, 2, 3, 4, 5, 6, 7]}, headers=hd
    )
    assert resp.status_code == 422 and "最多支持对比 6 个" in resp.json()["detail"]
    zero = {"salary": 0, "commute": 0, "insurance": 0, "development": 0, "stability": 0}
    resp = await client.post(
        "/api/v1/offers/compare", json={"ids": [a["id"], b["id"]], "weights": zero}, headers=hd
    )
    assert resp.status_code == 422 and "权重之和" in resp.json()["detail"]
    resp = await client.post(
        "/api/v1/offers/compare",
        json={"ids": [a["id"], b["id"]], "weights": {**zero, "salary": 101}},
        headers=hd,
    )
    assert resp.status_code == 422

    # 正常对比不受影响（冒烟）
    resp = await client.post("/api/v1/offers/compare", json={"ids": [a["id"], b["id"]]}, headers=hd)
    assert resp.status_code == 200


# ---------------------------------------------------------------- 纯函数直测


def test_minmax_scores_pure():
    """60~100 归一 / 反向（通勤）/ 全同值全 100。"""
    assert offers_mod._minmax_scores([240, 360]) == [60.0, 100.0]
    assert offers_mod._minmax_scores([240, 300, 360]) == [60.0, 80.0, 100.0]
    assert offers_mod._minmax_scores([30, 90], reverse=True) == [100.0, 60.0]
    assert offers_mod._minmax_scores([45, 45]) == [100.0, 100.0]


def test_score_offers_rank_and_tiebreak():
    """rank 按 total 降序；total 相同时 annual 高者在前。"""
    base = {"title": "后端", "city": "", "salary_months": 12, "commute_minutes": 45,
            "insurance": 3, "development": 3, "stability": 3}
    offers = [
        {"id": 1, "company": "甲", "monthly_salary": 20, **base},   # annual 240
        {"id": 2, "company": "乙", "monthly_salary": 30, **base},   # annual 360
        {"id": 3, "company": "丙", "monthly_salary": 25, **base},   # annual 300
    ]
    items = offers_mod.score_offers(offers, dict(offers_mod.DEFAULT_WEIGHTS))
    assert [it["id"] for it in items] == [2, 3, 1]
    assert [it["rank"] for it in items] == [1, 2, 3]

    # total 平局（同薪资同维度）：annual 相同 → id 升序兜底
    tie = [{"id": 9, "company": "丁", "monthly_salary": 20, **base},
           {"id": 8, "company": "戊", "monthly_salary": 20, **base}]
    items = offers_mod.score_offers(tie, dict(offers_mod.DEFAULT_WEIGHTS))
    assert [it["id"] for it in items] == [8, 9]


def test_build_conclusion_elements():
    """三元素齐活：总分第一（甲）+ 通勤最短（乙）+ 非薪资最高权重维度（发展→丙）；最多三句。"""
    base = {"title": "后端", "city": "", "salary_months": 12, "commute_minutes": 60,
            "insurance": 3, "stability": 3}
    offers = [
        {"id": 1, "company": "甲", "monthly_salary": 30, "development": 3, **base},  # annual 360
        {"id": 2, "company": "乙", "monthly_salary": 20, "development": 3,
         **{**base, "commute_minutes": 30}},                                          # annual 240
        {"id": 3, "company": "丙", "monthly_salary": 20, "development": 5, **base},   # annual 240
    ]
    weights = dict(offers_mod.DEFAULT_WEIGHTS)  # 非薪资最高权重 = development(20)
    items = offers_mod.score_offers(offers, weights)
    assert items[0]["company"] == "甲"
    conclusion = offers_mod.build_conclusion(items, weights)
    assert conclusion.startswith("甲")
    assert "年薪包最高（36.0 万）" in conclusion      # 年薪最高者即第一名 → 不重复点名
    assert "通勤最短的是 乙" in conclusion
    assert "若更看重成长，丙 的发展评分最高" in conclusion
    assert conclusion.count("；") == 2 and conclusion.endswith("。")  # 恰好三句


def test_build_conclusion_annual_max_differs_from_leader():
    """年薪最高者与总分第一不是同一人 → 单独点名。"""
    base = {"title": "后端", "city": "", "salary_months": 12, "commute_minutes": 45}
    offers = [
        # 甲：薪资低但五险/发展/稳定拉满 → total 84 反超
        {"id": 1, "company": "甲", "monthly_salary": 20,
         "insurance": 5, "development": 5, "stability": 5, **base},
        # 乙：年薪包最高（360K）
        {"id": 2, "company": "乙", "monthly_salary": 30,
         "insurance": 3, "development": 3, "stability": 3, **base},
    ]
    weights = dict(offers_mod.DEFAULT_WEIGHTS)
    items = offers_mod.score_offers(offers, weights)
    assert items[0]["company"] == "甲"
    conclusion = offers_mod.build_conclusion(items, weights)
    assert "年薪包最高的是 乙" in conclusion


def test_build_conclusion_all_tied():
    """数据完全相同 → 综合接近话术。"""
    base = {"title": "后端", "city": "", "salary_months": 12, "commute_minutes": 45,
            "insurance": 3, "development": 3, "stability": 3}
    offers = [{"id": 1, "company": "甲", "monthly_salary": 20, **base},
              {"id": 2, "company": "乙", "monthly_salary": 20, **base}]
    weights = dict(offers_mod.DEFAULT_WEIGHTS)
    items = offers_mod.score_offers(offers, weights)
    conclusion = offers_mod.build_conclusion(items, weights)
    assert "综合接近" in conclusion and "现场感受" in conclusion
