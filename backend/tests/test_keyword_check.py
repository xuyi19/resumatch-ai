"""M61 关键词覆盖体检测试：纯函数提取/比对 + HTTP 端点 + jieba 缺失容错。

纯函数单测不走 HTTP；HTTP 用 uuid 会话（X-Session-Id 头）做 owner 隔离
（同 test_job_library.py 惯例）。
"""

import sys
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.main import app
from app.utils.keywords import check_coverage, extract_jd_keywords


@pytest.fixture
async def client(monkeypatch):
    # web 态让 X-Session-Id 头生效（桌面态 owner 恒为 local，无法测隔离）
    monkeypatch.setattr(settings, "APP_MODE", "web")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def _sid() -> dict:
    return {"X-Session-Id": f"kw-{uuid4().hex[:12]}"}


RESUME_TEXT = (
    "本科，三年 Python 后端开发经验，熟悉 FastAPI、MySQL、Redis，"
    "主导过高并发订单系统优化，QPS 提升 3 倍。"
)

JD_TEXT = (
    "岗位职责：负责核心后端服务研发。要求精通 Python，熟悉 Go 语言与 Kubernetes 容器编排，"
    "K8s 集群部署运维。熟悉 MySQL、Redis 与 Kafka，有高并发、分布式系统设计经验。"
    "熟悉 Python 异步编程者优先。"
)


# ---------------------------------------------------------------- 纯函数：提取


def test_extract_lexicon_hits_and_counts():
    """词库候选命中且 count 正确、按 count 降序、数量受 max_terms 约束、无停用词。"""
    kws = extract_jd_keywords(JD_TEXT, max_terms=30)
    words = {k["word"]: k["count"] for k in kws}
    assert words.get("Python") == 2      # JD 出现两次
    assert words.get("Go") == 1          # 「Go 语言」别名命中
    assert words.get("Kubernetes") == 1  # kubernetes + k8s 各 1 次，别名取最大值
    assert words.get("高并发") == 1
    assert words.get("MySQL") == 1

    counts = [k["count"] for k in kws]
    assert counts == sorted(counts, reverse=True)
    assert 0 < len(kws) <= 30
    assert all(k["count"] >= 1 for k in kws)
    # 停用词（泛化词）不进入候选
    banned = {"熟悉", "精通", "负责", "经验", "优先", "岗位职责", "任职要求"}
    assert not banned & set(words)


def test_extract_respects_max_terms():
    kws = extract_jd_keywords(JD_TEXT, max_terms=5)
    assert len(kws) <= 5


def test_alias_merge_js_to_javascript():
    """JD 写「js」→ 展示名归并为 JavaScript；resume 写「JavaScript」→ 判命中。"""
    jd = "要求熟悉 js 与前端框架，写过 js 组件，了解 css 布局，对 js 性能有要求。"
    kws = extract_jd_keywords(jd)
    words = {k["word"]: k["count"] for k in kws}
    assert words.get("JavaScript") == 3
    assert "js" not in words  # 别名不重复出现，归并进展示名

    result = check_coverage(kws, "精通 JavaScript 与 Vue，写过大量前端组件。")
    assert "JavaScript" in result["hits"]
    assert result["coverage"] == round(len(result["hits"]) * 100 / len(kws))


def test_check_coverage_math_and_order():
    """resume 含部分词 → hits/missing 分对、coverage = hits/total*100 取整、保持原顺序。"""
    kws = [
        {"word": "Python", "count": 3},
        {"word": "Go", "count": 2},
        {"word": "Kafka", "count": 1},
    ]
    resume = "三年 Python 后端经验，用过 MySQL 与 Redis。"
    result = check_coverage(kws, resume)
    assert result["hits"] == ["Python"]
    assert result["missing"] == ["Go", "Kafka"]
    assert result["coverage"] == round(1 * 100 / 3)
    # hits 保持 keywords 原顺序（count 降序）
    kws2 = [
        {"word": "Python", "count": 3},
        {"word": "Redis", "count": 2},
        {"word": "Kafka", "count": 1},
    ]
    result2 = check_coverage(kws2, resume)
    assert result2["hits"] == ["Python", "Redis"]
    assert result2["coverage"] == round(2 * 100 / 3)


def test_check_coverage_empty_inputs():
    assert check_coverage([], RESUME_TEXT) == {"coverage": 0, "hits": [], "missing": []}


# ---------------------------------------------------------------- jieba 容错


def test_extract_works_without_jieba(monkeypatch):
    """模拟打包环境 jieba.analyse 导入失败：词库 + 英文路径照常工作。"""
    monkeypatch.setitem(sys.modules, "jieba.analyse", None)
    kws = extract_jd_keywords(JD_TEXT)
    assert "Python" in {k["word"] for k in kws}
    assert "Kubernetes" in {k["word"] for k in kws}

    # 英文补充路径：非词库英文词出现 ≥2 次仍被提取
    jd_en = "负责 open api 设计，api 文档维护，api 网关接入，团队氛围好。"
    words = {k["word"]: k["count"] for k in extract_jd_keywords(jd_en)}
    assert words.get("api") == 3


# ---------------------------------------------------------------- HTTP 端点


async def test_keyword_check_with_resume_text(client):
    """resume_text 直传路径：返回 coverage/hits/missing/total 且口径自洽。"""
    resp = await client.post(
        "/api/v1/jobs/keyword-check",
        json={"jd": JD_TEXT, "resume_text": RESUME_TEXT},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert set(body) == {"coverage", "hits", "missing", "total"}
    assert body["total"] == len(body["hits"]) + len(body["missing"])
    assert 0 <= body["coverage"] <= 100
    assert "Python" in body["hits"]
    assert "Kubernetes" in body["missing"]  # 简历未提及 K8s


async def test_keyword_check_with_resume_id(client):
    """resume_id 路径：upload-text 建简历后按 id 体检。"""
    hd = _sid()
    resp = await client.post(
        "/api/v1/resumes/upload-text",
        json={"filename": "体检简历.txt", "text": RESUME_TEXT},
        headers=hd,
    )
    assert resp.status_code == 200
    resume_id = resp.json()["id"]

    resp = await client.post(
        "/api/v1/jobs/keyword-check",
        json={"jd": JD_TEXT, "resume_id": resume_id},
        headers=hd,
    )
    assert resp.status_code == 200
    assert "Python" in resp.json()["hits"]


async def test_keyword_check_validations(client):
    """缺 resume 400 / jd <30 字 422 / 简历不存在 404。"""
    hd = _sid()
    resp = await client.post("/api/v1/jobs/keyword-check", json={"jd": JD_TEXT}, headers=hd)
    assert resp.status_code == 400

    resp = await client.post(
        "/api/v1/jobs/keyword-check",
        json={"jd": "太短的JD", "resume_text": RESUME_TEXT},
        headers=hd,
    )
    assert resp.status_code == 422

    resp = await client.post(
        "/api/v1/jobs/keyword-check",
        json={"jd": JD_TEXT, "resume_id": 999999},
        headers=hd,
    )
    assert resp.status_code == 404
