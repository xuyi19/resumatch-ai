"""M44 简历版本链测试：v1 自动落 / save-version 增量更新 / 上限 20 删旧 / 级联清理。

用 uuid 会话（X-Session-Id 头）做 owner 隔离（web 态），固定标识数据先清理再取快照，
断言增量（跨 pytest 运行残留不可靠的既有教训）。
"""

from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.main import app


@pytest.fixture
async def client(monkeypatch):
    monkeypatch.setattr(settings, "APP_MODE", "web")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def _sid() -> dict:
    return {"X-Session-Id": f"rv-{uuid4().hex[:12]}"}


RESUME_V1 = (
    "张三，本科计算机科学专业，三年 Python 后端开发经验，熟悉 FastAPI 与 MySQL，"
    "主导过订单系统重构，接口平均响应时间下降 40%。"
)
RESUME_V2 = (
    "张三，本科计算机科学专业，四年 Python 后端开发经验，熟悉 FastAPI、MySQL 与 Redis，"
    "主导过订单系统重构与秒杀活动保障，QPS 提升 3 倍，接口平均响应时间下降 40%。"
)


async def _create(client, headers, text=RESUME_V1, filename="版本测试简历.txt"):
    resp = await client.post(
        "/api/v1/resumes/upload-text",
        json={"filename": filename, "text": text},
        headers=headers,
    )
    assert resp.status_code == 200
    return resp.json()


async def _versions(client, headers, resume_id):
    resp = await client.get(f"/api/v1/resumes/{resume_id}/versions", headers=headers)
    assert resp.status_code == 200
    return resp.json()


# ---------------------------------------------------------------- 基础链路


async def test_initial_version_created(client):
    """上传/粘贴创建简历时自动落 v1（initial 来源）。"""
    hd = _sid()
    data = await _create(client, hd)
    versions = await _versions(client, hd, data["id"])
    assert len(versions) == 1
    assert versions[0]["source"] == "initial"
    assert versions[0]["chars"] == len(RESUME_V1)
    assert versions[0]["created_at"]


async def test_save_version_and_no_change(client):
    """编辑器保存：文本变化落新版本并更新 raw_text；重复保存相同文本不落库。"""
    hd = _sid()
    data = await _create(client, hd)

    # 第一次保存：有变化 → 落 v2
    resp = await client.post(
        f"/api/v1/resumes/{data['id']}/save-version",
        json={"text": RESUME_V2},
        headers=hd,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["updated"] is True
    assert body["version_count"] == 2

    # raw_text 已更新
    detail = await client.get(f"/api/v1/resumes/{data['id']}", headers=hd)
    assert detail.json()["raw_text"] == RESUME_V2

    # 重复保存相同文本：无变化不落库
    resp = await client.post(
        f"/api/v1/resumes/{data['id']}/save-version",
        json={"text": RESUME_V2},
        headers=hd,
    )
    assert resp.status_code == 200
    assert resp.json()["updated"] is False
    assert resp.json()["version_count"] == 2

    versions = await _versions(client, hd, data["id"])
    assert len(versions) == 2
    assert versions[0]["source"] == "editor"  # 时间倒序：最新在前


async def test_version_detail_and_404(client):
    """单版本全文可取；他人会话不可见（owner 隔离）；不存在版本 404。"""
    hd = _sid()
    data = await _create(client, hd)
    versions = await _versions(client, hd, data["id"])
    vid = versions[0]["id"]

    detail = await client.get(f"/api/v1/resumes/{data['id']}/versions/{vid}", headers=hd)
    assert detail.status_code == 200
    assert detail.json()["content"] == RESUME_V1

    # 其他会话（owner 隔离）
    other = await client.get(
        f"/api/v1/resumes/{data['id']}/versions/{vid}", headers=_sid()
    )
    assert other.status_code == 404

    # 不存在的版本
    missing = await client.get(
        f"/api/v1/resumes/{data['id']}/versions/999999", headers=hd
    )
    assert missing.status_code == 404


async def test_version_cap_20(client):
    """每份简历版本上限 20：超出自动删最旧。"""
    hd = _sid()
    data = await _create(client, hd)
    for i in range(22):
        resp = await client.post(
            f"/api/v1/resumes/{data['id']}/save-version",
            json={"text": RESUME_V2 + f"补充说明第 {i} 条，负责过 {i} 个核心项目的架构设计。"},
            headers=hd,
        )
        assert resp.status_code == 200
    versions = await _versions(client, hd, data["id"])
    assert len(versions) == 20
    # 最旧的 v1(initial) 已被挤出；来源全为 editor
    assert all(v["source"] == "editor" for v in versions)


async def test_save_version_validation(client):
    """文本过短 400；简历不存在 404。"""
    hd = _sid()
    resp = await client.post(
        "/api/v1/resumes/save-version",
        json={"text": "太短"},
        headers=hd,
    )
    assert resp.status_code in (400, 404, 405)  # 无简历上下文，路径参数缺失即可

    data = await _create(client, hd)
    short = await client.post(
        f"/api/v1/resumes/{data['id']}/save-version", json={"text": "太短"}, headers=hd
    )
    assert short.status_code == 400
    missing = await client.post(
        "/api/v1/resumes/999999/save-version",
        json={"text": RESUME_V2},
        headers=hd,
    )
    assert missing.status_code == 404


async def test_delete_resume_cascades_versions(client):
    """删除简历后版本快照一并清理（不残留孤儿）。"""
    hd = _sid()
    data = await _create(client, hd)
    await client.post(
        f"/api/v1/resumes/{data['id']}/save-version", json={"text": RESUME_V2}, headers=hd
    )
    resp = await client.delete(f"/api/v1/resumes/{data['id']}", headers=hd)
    assert resp.status_code == 200
    # 简历与版本均应 404 / 空
    assert (await client.get(f"/api/v1/resumes/{data['id']}/versions", headers=hd)).status_code == 404
