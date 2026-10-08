"""M71 统一导出目录与分类落盘测试：export-root 读写闭环 / owner 隔离 /
classify_dir 映射 / resolve_save_path 重名防覆盖 / 桌面态导出分类落盘 /
web 态导出与备份不受影响 / open-dir 仅桌面版。

用 uuid 会话（X-Session-Id 头）做 owner 隔离（同 test_backup 惯例）；
桌面态落盘测试把导出根目录指到 tmp_path，绝不写进真实 data/（conftest
已把默认 DATA_DIR 隔离到 tests/.tmp/data）。
"""

import json
from pathlib import Path
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.main import app
from app.models.entities import AppSetting
from app.utils.export_paths import (
    SETTING_KEY_EXPORT_ROOT,
    classify_dir,
    default_export_root,
    resolve_save_path,
)


@pytest.fixture
async def client(monkeypatch):
    # web 态让 X-Session-Id 头生效（桌面态 owner 恒为 local，无法测隔离）
    monkeypatch.setattr(settings, "APP_MODE", "web")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def _sid() -> dict:
    return {"X-Session-Id": f"ex-{uuid4().hex[:12]}"}


# ---------------------------------------------------------------- 设置读写


async def test_export_root_default_and_put_roundtrip(client, tmp_path):
    """默认值 data/exports → PUT 保存自定义（绝对化 + mkdir）→ 空串恢复默认删行。"""
    hd = _sid()
    r = await client.get("/api/v1/settings/export-root", headers=hd)
    assert r.status_code == 200
    body = r.json()
    assert body["is_default"] is True
    assert Path(body["export_root"]) == default_export_root()

    # PUT 保存自定义目录
    target = tmp_path / "my-exports"
    r = await client.put(
        "/api/v1/settings/export-root", json={"path": str(target)}, headers=hd
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["is_default"] is False
    assert Path(body["export_root"]) == target.resolve()
    assert body["exists"] is True
    assert target.is_dir()  # 保存后自动建目录

    # GET 回读
    r = await client.get("/api/v1/settings/export-root", headers=hd)
    assert r.json()["export_root"] == str(target.resolve())

    # 空串 = 恢复默认（删除自定义行）
    r = await client.put("/api/v1/settings/export-root", json={"path": ""}, headers=hd)
    assert r.status_code == 200
    body = r.json()
    assert body["is_default"] is True
    assert Path(body["export_root"]) == default_export_root()
    # 再 GET 仍是默认
    r = await client.get("/api/v1/settings/export-root", headers=hd)
    assert r.json()["is_default"] is True


async def test_export_root_owner_isolation(client, tmp_path):
    """A 设置的导出目录 B 看不到（owner 隔离）。"""
    ha, hb = _sid(), _sid()
    r = await client.put(
        "/api/v1/settings/export-root",
        json={"path": str(tmp_path / "a-dir")},
        headers=ha,
    )
    assert r.status_code == 200
    r = await client.get("/api/v1/settings/export-root", headers=hb)
    assert r.json()["is_default"] is True


async def test_export_root_invalid_path_422(client):
    """含非法字符的路径 422。"""
    hd = _sid()
    r = await client.put(
        "/api/v1/settings/export-root",
        json={"path": 'C:\\bad<path>"|?*'},
        headers=hd,
    )
    assert r.status_code == 422


async def test_export_root_relative_path_resolved(client, tmp_path, monkeypatch):
    """相对路径一律 resolve 成绝对路径。"""
    monkeypatch.chdir(tmp_path)
    hd = _sid()
    r = await client.put(
        "/api/v1/settings/export-root", json={"path": "rel-exports"}, headers=hd
    )
    assert r.status_code == 200
    body = r.json()
    assert Path(body["export_root"]).is_absolute()
    assert Path(body["export_root"]) == (tmp_path / "rel-exports").resolve()
    # 清理：恢复默认，避免残留行影响其他用例（owner 隔离下其实无影响，双保险）
    await client.put("/api/v1/settings/export-root", json={"path": ""}, headers=hd)


# ---------------------------------------------------------------- 分类与落盘 helper


@pytest.mark.parametrize(
    "template,expected",
    [
        ("resume", "简历"),
        ("apply", "投递材料包"),
        ("interview", "面试报告"),
        ("diagnosis", "诊断报告"),
        ("report", "诊断报告"),  # 诊断报告在 export_history 中的 template 值
        ("backup", "数据备份"),
        ("classic", "其他导出"),
        ("", "其他导出"),
    ],
)
def test_classify_dir(template, expected):
    assert classify_dir(template) == expected


async def test_resolve_save_path_dedupe(tmp_path):
    """同名文件防覆盖：第二个自动追加 _2。"""
    from app.core.db import AsyncSessionLocal

    owner = f"ex-{uuid4().hex[:12]}"
    # 该 owner 的导出根目录指到 tmp_path，避免写真实 data/
    async with AsyncSessionLocal() as db:
        db.add(AppSetting(owner_id=owner, key=SETTING_KEY_EXPORT_ROOT, value=str(tmp_path)))
        await db.commit()
    async with AsyncSessionLocal() as db:
        p1 = await resolve_save_path("resume", "同名.docx", db, owner)
    # 模拟第一次导出真实落盘后，第二次解析同名文件应避让（防覆盖在生产中
    # 依赖「上一次导出已写入磁盘」这一事实）
    p1.write_bytes(b"docx")
    async with AsyncSessionLocal() as db:
        p2 = await resolve_save_path("resume", "同名.docx", db, owner)
    assert p1 == tmp_path / "简历" / "同名.docx"
    assert p2.name == "同名_2.docx"
    assert p2.parent == p1.parent


# ---------------------------------------------------------------- 桌面态导出落盘


async def test_desktop_export_kit_lands_in_classified_dir(client, monkeypatch, tmp_path):
    """桌面态 export-kit（链路最短、零 LLM）：文件落 {export_root}/投递材料包/ 且有历史记录。"""
    monkeypatch.setattr(settings, "APP_MODE", "local")  # 桌面态
    hd = _sid()
    r = await client.put(
        "/api/v1/settings/export-root",
        json={"path": str(tmp_path / "out")},
        headers=hd,
    )
    assert r.status_code == 200

    # 建岗位（无 LLM 依赖）
    r = await client.post(
        "/api/v1/jobs/library",
        json={"items": [{"title": "后端工程师", "company": "A 科技"}]},
        headers=hd,
    )
    assert r.status_code == 200, r.text
    job_id = r.json()["items"][0]["id"]

    # 桌面态导出：save_path 仅作直写标志，服务端按分类落盘
    r = await client.post(
        f"/api/v1/jobs/library/{job_id}/export-kit",
        json={"cover_letter": "尊敬的招聘负责人，您好。" * 10, "save_path": "auto"},
        headers=hd,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    saved = Path(body["saved_to"])
    assert saved.parent == tmp_path / "out" / "投递材料包"
    assert saved.exists() and saved.stat().st_size > 0
    assert body["save_path"] == str(saved)

    # export_history 有记录（template=apply）
    r = await client.get("/api/v1/resumes/export-history", headers=hd)
    items = r.json()["items"]
    assert items and items[0]["template"] == "apply"
    assert items[0]["save_path"] == str(saved)


async def test_web_export_kit_still_blob(client):
    """web 态同端点仍返回 blob；带 save_path 时 403（不允许服务端落盘）。"""
    hd = _sid()
    r = await client.post(
        "/api/v1/jobs/library",
        json={"items": [{"title": "后端工程师"}]},
        headers=hd,
    )
    job_id = r.json()["items"][0]["id"]

    r = await client.post(
        f"/api/v1/jobs/library/{job_id}/export-kit",
        json={"cover_letter": "求职信正文内容。" * 30},
        headers=hd,
    )
    assert r.status_code == 200
    assert r.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )

    r2 = await client.post(
        f"/api/v1/jobs/library/{job_id}/export-kit",
        json={"cover_letter": "求职信正文内容。" * 30, "save_path": "auto"},
        headers=hd,
    )
    assert r2.status_code == 403


# ---------------------------------------------------------------- 备份导出 save=1


async def test_backup_save_desktop(client, monkeypatch, tmp_path):
    """桌面态 ?save=1 落「数据备份」子目录并返回 save_path；不带 save=1 仍返回 JSON body。"""
    monkeypatch.setattr(settings, "APP_MODE", "local")
    hd = _sid()
    r = await client.put(
        "/api/v1/settings/export-root",
        json={"path": str(tmp_path / "out")},
        headers=hd,
    )
    assert r.status_code == 200

    r = await client.get("/api/v1/backup/export", params={"save": 1}, headers=hd)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["save_path"]
    saved = Path(body["save_path"])
    assert saved.parent == tmp_path / "out" / "数据备份"
    assert saved.suffix == ".json" and saved.exists()
    data = json.loads(saved.read_text(encoding="utf-8"))
    assert data["app"] == "ResuMatch-AI"
    assert data["counts"] == body["counts"]

    # 桌面态不带 save=1：照旧 JSON body
    r = await client.get("/api/v1/backup/export", headers=hd)
    assert r.status_code == 200
    assert r.json()["app"] == "ResuMatch-AI"
    assert "save_path" not in r.json()


async def test_backup_web_ignores_save(client):
    """web 态带 save=1 也照旧返回 JSON body，不落盘。"""
    hd = _sid()
    r = await client.get("/api/v1/backup/export", params={"save": 1}, headers=hd)
    assert r.status_code == 200
    body = r.json()
    assert body["app"] == "ResuMatch-AI"
    assert "save_path" not in body


# ---------------------------------------------------------------- 打开目录


async def test_open_dir_web_400(client):
    """web 态 open-dir 返回 400。"""
    r = await client.post("/api/v1/settings/open-dir", json={"subdir": ""}, headers=_sid())
    assert r.status_code == 400


async def test_open_dir_invalid_subdir_desktop(client, monkeypatch, tmp_path):
    """桌面态非法子目录（路径穿越）422。"""
    monkeypatch.setattr(settings, "APP_MODE", "local")
    hd = _sid()
    r = await client.put(
        "/api/v1/settings/export-root",
        json={"path": str(tmp_path / "out")},
        headers=hd,
    )
    assert r.status_code == 200
    r = await client.post(
        "/api/v1/settings/open-dir", json={"subdir": "..\\..\\windows"}, headers=hd
    )
    assert r.status_code == 422
