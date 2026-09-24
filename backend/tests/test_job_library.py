"""M45 岗位库测试：saved_jobs CRUD + owner 会话隔离 + 库×简历批量匹配（降级路径）。

用 uuid 会话（X-Session-Id 头）做 owner 隔离，天然不与跨 pytest 运行的残留数据冲突；
LLM 精排失败场景 monkeypatch get_llm 模拟（同 test_jobs.py 惯例）。
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
    return {"X-Session-Id": f"lib-{uuid4().hex[:12]}"}


RESUME_TEXT = (
    "本科，三年 Python 后端开发经验，熟悉 FastAPI、MySQL、Redis，"
    "主导过高并发订单系统优化，QPS 提升 3 倍。"
)


async def _add(client, headers, items, source="manual"):
    return await client.post(
        "/api/v1/jobs/library", json={"items": items, "source": source}, headers=headers
    )


# ---------------------------------------------------------------- CRUD


async def test_library_crud_flow(client):
    """批量添加 → 列表 → 编辑 → 单删 → 批删幂等 全链路。"""
    hd = _sid()
    resp = await _add(client, hd, [
        {"title": "Python 后端工程师", "company": "A 科技", "city": "杭州",
         "salary": "25-40K", "jd": "负责核心系统研发，要求熟悉 Python、FastAPI、MySQL、Redis。"},
        {"title": "前端工程师", "company": "B 网络", "city": "北京"},
    ])
    assert resp.status_code == 200
    added = resp.json()["items"]
    assert [j["title"] for j in added] == ["Python 后端工程师", "前端工程师"]
    assert added[0]["jd"].startswith("负责核心系统")
    assert added[0]["source"] == "manual"
    # jd 缺失 → 公司+岗位占位文本
    assert "B 网络" in added[1]["jd"] and "前端工程师" in added[1]["jd"]

    lst = (await client.get("/api/v1/jobs/library", headers=hd)).json()["items"]
    assert len(lst) == 2 and lst[0]["id"] > lst[1]["id"]  # 最新在前

    # 编辑（部分字段；未提供字段不动）——按 title 定位，列表最新在前
    jid = next(j["id"] for j in lst if j["title"] == "Python 后端工程师")
    resp = await client.put(
        f"/api/v1/jobs/library/{jid}", json={"salary": "30-50K", "city": "上海"}, headers=hd
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["salary"] == "30-50K" and body["city"] == "上海"
    assert body["title"] == "Python 后端工程师"  # 未提供字段不动

    # 单删
    resp = await client.delete(f"/api/v1/jobs/library/{jid}", headers=hd)
    assert resp.status_code == 200 and resp.json()["deleted"] == 1
    lst = (await client.get("/api/v1/jobs/library", headers=hd)).json()["items"]
    assert len(lst) == 1

    # 批删（含不存在 id）→ 幂等
    other_id = lst[0]["id"]
    resp = await client.post(
        "/api/v1/jobs/library/batch-delete", json={"ids": [other_id, 999999]}, headers=hd
    )
    assert resp.json()["deleted"] == 1
    resp = await client.post(
        "/api/v1/jobs/library/batch-delete", json={"ids": [other_id, 999999]}, headers=hd
    )
    assert resp.json()["deleted"] == 0
    assert (await client.get("/api/v1/jobs/library", headers=hd)).json()["items"] == []


async def test_library_validates_title(client):
    """title 缺失/空白 → 422；空字段传显式 null 不炸（容忍 null）。"""
    hd = _sid()
    resp = await _add(client, hd, [{"company": "无名的岗位"}])
    assert resp.status_code == 422
    resp = await _add(client, hd, [{"title": "数据分析师", "city": None, "salary": None}])
    assert resp.status_code == 200
    assert resp.json()["items"][0]["city"] == ""


async def test_library_owner_isolation(client):
    """会话 A 添加的岗位，会话 B 看不见也删不掉。"""
    hd_a, hd_b = _sid(), _sid()
    resp = await _add(client, hd_a, [{"title": "算法工程师", "company": "C 智能"}])
    job_id = resp.json()["items"][0]["id"]

    lst_b = (await client.get("/api/v1/jobs/library", headers=hd_b)).json()["items"]
    assert lst_b == []

    resp = await client.delete(f"/api/v1/jobs/library/{job_id}", headers=hd_b)
    assert resp.status_code == 404
    resp = await client.put(f"/api/v1/jobs/library/{job_id}", json={"title": "篡改"}, headers=hd_b)
    assert resp.status_code == 404

    # A 仍能看到且未被篡改
    lst_a = (await client.get("/api/v1/jobs/library", headers=hd_a)).json()["items"]
    assert len(lst_a) == 1 and lst_a[0]["title"] == "算法工程师"


# ---------------------------------------------------------------- 匹配


async def test_library_match_degrades_without_llm(client, monkeypatch):
    """LLM 不可用 → coarse_rank 关键词降级排序；分数与理由齐全且降序。"""
    import app.api.v1.jobs as jobs_mod

    def _boom(*args, **kwargs):
        raise RuntimeError("llm unavailable")

    monkeypatch.setattr(jobs_mod, "get_llm", _boom)
    hd = _sid()
    await _add(client, hd, [
        {"title": "Python 后端工程师", "company": "A 科技", "city": "杭州",
         "jd": "负责后端服务研发，要求熟悉 Python、FastAPI、MySQL、Redis，有高并发经验。"},
        {"title": "新媒体运营", "company": "B 文化", "city": "北京",
         "jd": "负责短视频内容策划与账号运营，撰写爆款文案。"},
    ])
    resp = await client.post(
        "/api/v1/jobs/library-match",
        json={"resume_text": RESUME_TEXT, "llm_config": {}},
        headers=hd,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["degraded"] is True
    assert body["items"][0]["title"] == "Python 后端工程师"
    scores = [j["score"] for j in body["items"]]
    assert scores == sorted(scores, reverse=True)
    assert all(isinstance(j["id"], int) and j["reason"] for j in body["items"])


async def test_library_match_by_resume_id(client, monkeypatch):
    """resume_id 路径：粘贴文本建简历 → 库内匹配；job_ids 过滤生效。"""

    def _boom(*args, **kwargs):
        raise RuntimeError("llm unavailable")

    from app.api.v1 import jobs as jobs_mod
    monkeypatch.setattr(jobs_mod, "get_llm", _boom)

    hd = _sid()
    resp = await client.post(
        "/api/v1/resumes/upload-text",
        json={"filename": "匹配测试简历.txt", "text": RESUME_TEXT},
        headers=hd,
    )
    assert resp.status_code == 200
    resume_id = resp.json()["id"]

    await _add(client, hd, [
        {"title": "Python 后端工程师", "company": "A 科技", "jd": "熟悉 Python FastAPI MySQL Redis 高并发"},
        {"title": "前端工程师", "company": "B 网络", "jd": "Vue React 前端页面开发"},
    ])
    lst = (await client.get("/api/v1/jobs/library", headers=hd)).json()["items"]
    py_id = next(j["id"] for j in lst if j["title"] == "Python 后端工程师")

    resp = await client.post(
        "/api/v1/jobs/library-match",
        json={"resume_id": resume_id, "job_ids": [py_id], "llm_config": {}},
        headers=hd,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["items"]) == 1 and body["items"][0]["title"] == "Python 后端工程师"

    # job_ids 含他人/不存在 id → 只匹配命中的（这里过滤到空池）
    resp = await client.post(
        "/api/v1/jobs/library-match",
        json={"resume_id": resume_id, "job_ids": [999999], "llm_config": {}},
        headers=hd,
    )
    assert resp.status_code == 200 and resp.json()["items"] == []


async def test_library_match_resume_not_found(client):
    hd = _sid()
    resp = await client.post(
        "/api/v1/jobs/library-match", json={"resume_id": 999999}, headers=hd
    )
    assert resp.status_code == 404


async def test_library_match_empty_library(client, monkeypatch):
    """空库 → 200 空池 + 引导文案（不报错）；mock LLM 避免真实调用。"""
    import app.api.v1.jobs as jobs_mod

    def _boom(*args, **kwargs):
        raise RuntimeError("llm unavailable")

    monkeypatch.setattr(jobs_mod, "get_llm", _boom)
    hd = _sid()
    resp = await client.post(
        "/api/v1/jobs/library-match", json={"resume_text": RESUME_TEXT}, headers=hd
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["items"] == [] and "岗位库" in body["message"]


async def test_library_match_requires_resume(client):
    hd = _sid()
    resp = await client.post("/api/v1/jobs/library-match", json={}, headers=hd)
    assert resp.status_code == 400


# ---------------------------------------------------------------- AI 自动入库


class _MockLLM:
    """get_llm 替身：ainvoke 返回预置 content（可带 ```json 围栏，测解析容错）。"""

    def __init__(self, content):
        self._content = content

    async def ainvoke(self, prompt):
        from types import SimpleNamespace

        return SimpleNamespace(content=self._content)


GEN_JSON = """```json
[
  {"title": "资深 Python 开发工程师", "company": "字节跳动", "city": "北京",
   "salary": "30-50K", "jd": "负责内容平台后端服务研发，要求精通 Python 与高并发架构。"},
  {"title": "数据平台工程师", "company": "阿里巴巴", "city": "杭州",
   "salary": "25-45K", "jd": "负责数据 pipelines 建设与治理，熟悉 Spark 与数仓建模。"}
]
```"""


async def test_library_generate_dedupes(client, monkeypatch):
    """AI 生成入库：围栏 JSON 正常解析；与库内「公司+岗位」重复的跳过。"""
    import app.api.v1.jobs as jobs_mod

    monkeypatch.setattr(jobs_mod, "get_llm", lambda **kw: _MockLLM(GEN_JSON))
    hd = _sid()
    # 预置一条与生成结果重复的岗位（字节跳动 / 资深 Python 开发工程师）
    await _add(client, hd, [{"title": "资深 Python 开发工程师", "company": "字节跳动",
                             "jd": "已有岗位描述内容足够长用于匹配测试。"}])

    resp = await client.post(
        "/api/v1/jobs/library-generate",
        json={"resume_text": RESUME_TEXT, "llm_config": {}},
        headers=hd,
    )
    assert resp.status_code == 200
    added = resp.json()["items"]
    assert len(added) == 1  # 重复的「字节跳动/资深 Python 开发工程师」被跳过
    assert added[0]["source"] == "ai_gen"
    assert added[0]["title"] == "数据平台工程师"

    # 再生成一次：两条都已存在 → 空列表 + 提示（不报错）
    resp = await client.post(
        "/api/v1/jobs/library-generate",
        json={"resume_text": RESUME_TEXT, "llm_config": {}},
        headers=hd,
    )
    assert resp.status_code == 200
    assert resp.json()["items"] == []
    assert "已在库中" in resp.json()["message"]


async def test_library_generate_llm_failure(client, monkeypatch):
    """LLM 异常 → 502 带可读 detail；输出无 JSON → 502。"""
    import app.api.v1.jobs as jobs_mod

    def _boom(**kw):
        raise RuntimeError("llm unavailable")

    monkeypatch.setattr(jobs_mod, "get_llm", _boom)
    hd = _sid()
    resp = await client.post(
        "/api/v1/jobs/library-generate", json={"resume_text": RESUME_TEXT}, headers=hd
    )
    assert resp.status_code == 502

    monkeypatch.setattr(jobs_mod, "get_llm", lambda **kw: _MockLLM("抱歉，我无法输出该内容"))
    resp = await client.post(
        "/api/v1/jobs/library-generate", json={"resume_text": RESUME_TEXT}, headers=hd
    )
    assert resp.status_code == 502


async def test_library_generate_requires_resume(client):
    hd = _sid()
    resp = await client.post("/api/v1/jobs/library-generate", json={}, headers=hd)
    assert resp.status_code == 400


# ---------------------------------------------------------------- 批量导入


async def test_parse_batch_via_llm(client, monkeypatch):
    """AI 解析：混排文本 → 结构化岗位数组；仅预览不入库。"""
    import app.api.v1.jobs as jobs_mod

    monkeypatch.setattr(jobs_mod, "get_llm", lambda **kw: _MockLLM(GEN_JSON))
    hd = _sid()
    resp = await client.post(
        "/api/v1/jobs/library/parse-batch",
        json={"raw_text": "字节跳动 资深Python开发工程师 北京 30-50K 负责内容平台后端研发…\n\n"
               "阿里巴巴 数据平台工程师 杭州 25-45K 负责数据 pipelines 建设治理…"},
        headers=hd,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["degraded"] is False
    assert [j["title"] for j in body["items"]] == ["资深 Python 开发工程师", "数据平台工程师"]
    # 仅解析预览：库不受影响
    assert (await client.get("/api/v1/jobs/library", headers=hd)).json()["items"] == []


async def test_parse_batch_degrades_to_rules(client, monkeypatch):
    """LLM 不可用 → 按空行段落拆分（第一行做岗位名），degraded 提示。"""
    import app.api.v1.jobs as jobs_mod

    def _boom(**kw):
        raise RuntimeError("llm unavailable")

    monkeypatch.setattr(jobs_mod, "get_llm", _boom)
    hd = _sid()
    resp = await client.post(
        "/api/v1/jobs/library/parse-batch",
        json={"raw_text": "Golang 开发工程师\n负责支付网关研发，要求熟悉 Go 与微服务。\n\n"
               "测试开发工程师\n负责自动化测试平台建设，熟悉 Python pytest。"},
        headers=hd,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["degraded"] is True
    assert [j["title"] for j in body["items"]] == ["Golang 开发工程师", "测试开发工程师"]
    assert "Golang" in body["items"][0]["jd"]


async def test_library_add_skip_duplicates(client):
    """批量导入去重：skip_duplicates=true 跳过库内已有「公司+岗位」。"""
    hd = _sid()
    await _add(client, hd, [{"title": "数据分析师", "company": "E 数科", "jd": "已有岗位，用于验证导入去重逻辑。"}])

    resp = await client.post(
        "/api/v1/jobs/library",
        json={
            "items": [
                {"title": "数据分析师", "company": "E 数科", "jd": "重复岗位的描述，应被跳过不重复入库。"},
                {"title": "数据分析师", "company": "F 信息", "jd": "不同公司的同名岗位，不算重复。"},
            ],
            "skip_duplicates": True,
        },
        headers=hd,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["skipped"] == 1
    assert len(body["items"]) == 1 and body["items"][0]["company"] == "F 信息"


# ---------------------------------------------------------------- 收藏迁移（M51）


async def test_library_favorite_source_and_stats(client):
    """M51 收藏迁移：favorite 来源入库 + 重复迁移跳过 + /history/stats 增量计数。"""
    hd = _sid()
    before = (await client.get("/api/v1/history/stats", headers=hd)).json()["saved_jobs_count"]

    resp = await _add(client, hd, [
        {"title": "测试工程师", "company": "C 公司", "jd": "负责功能测试与自动化用例维护。"},
    ], source="favorite")
    assert resp.status_code == 200
    assert resp.json()["items"][0]["source"] == "favorite"

    # 同一批收藏重复迁移 → skip_duplicates 全部跳过，不重复入库
    resp2 = await client.post(
        "/api/v1/jobs/library",
        json={"items": [{"title": "测试工程师", "company": "C 公司"}],
              "source": "favorite", "skip_duplicates": True},
        headers=hd,
    )
    assert resp2.status_code == 200 and resp2.json()["items"] == []

    after = (await client.get("/api/v1/history/stats", headers=hd)).json()["saved_jobs_count"]
    assert after - before == 1


# ---------------------------------------------------------------- 投递状态（M49）


async def test_job_status_flow(client):
    """新建默认 wish → 单条改状态 → 列表带 status → 非法值 400 → 不存在 404。"""
    hd = _sid()
    added = (await _add(client, hd, [{"title": "测试岗", "company": "G 测", "jd": "投递状态全链路验证用岗位描述。"}])).json()["items"][0]
    jid = added["id"]
    assert added["status"] == "wish"

    # 单条更新
    resp = await client.put(
        f"/api/v1/jobs/library/{jid}/status", json={"status": "interviewing"}, headers=hd
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "interviewing"

    # 列表返回状态
    lst = (await client.get("/api/v1/jobs/library", headers=hd)).json()["items"]
    assert lst[0]["status"] == "interviewing"

    # 非法值 400
    bad = await client.put(
        f"/api/v1/jobs/library/{jid}/status", json={"status": "hired???"}, headers=hd
    )
    assert bad.status_code == 400

    # 不存在 404
    missing = await client.put(
        "/api/v1/jobs/library/999999/status", json={"status": "offer"}, headers=hd
    )
    assert missing.status_code == 404


async def test_job_status_batch(client):
    """批量设置状态：只影响本会话岗位，空列表幂等。"""
    hd = _sid()
    items = (await _add(client, hd, [
        {"title": "批量岗 A", "company": "H 批", "jd": "批量状态测试岗位 A 的描述内容。"},
        {"title": "批量岗 B", "company": "I 批", "jd": "批量状态测试岗位 B 的描述内容。"},
    ])).json()["items"]
    ids = [j["id"] for j in items]

    resp = await client.put(
        "/api/v1/jobs/library/status-batch", json={"ids": ids, "status": "offer"}, headers=hd
    )
    assert resp.status_code == 200
    assert resp.json()["updated"] == 2
    lst = (await client.get("/api/v1/jobs/library", headers=hd)).json()["items"]
    assert all(j["status"] == "offer" for j in lst)

    # 非法值 400 / 空列表幂等
    assert (await client.put(
        "/api/v1/jobs/library/status-batch", json={"ids": ids, "status": "x"}, headers=hd
    )).status_code == 400
    assert (await client.put(
        "/api/v1/jobs/library/status-batch", json={"ids": [], "status": "offer"}, headers=hd
    )).json()["updated"] == 0


async def test_job_status_owner_isolation(client):
    """他人会话不能改我的岗位状态。"""
    hd = _sid()
    added = (await _add(client, hd, [{"title": "隔离岗", "company": "J 隔", "jd": "状态隔离验证岗位描述。"}])).json()["items"][0]
    other = await client.put(
        f"/api/v1/jobs/library/{added['id']}/status", json={"status": "offer"}, headers=_sid()
    )
    assert other.status_code == 404
    mine = (await client.get("/api/v1/jobs/library", headers=hd)).json()["items"]
    assert mine[0]["status"] == "wish"  # 未被他人改动
