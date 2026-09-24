"""健康检查测试"""
from httpx import ASGITransport, AsyncClient
import pytest

from app.main import app


@pytest.mark.asyncio
async def test_health_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get("/api/v1/health")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        assert data["db"] == "ok"
        print(f"\n✓ health: {data}")


@pytest.mark.asyncio
async def test_root_serves_html():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get("/")
        assert r.status_code == 200
        assert "text/html" in r.headers.get("content-type", "")


@pytest.mark.asyncio
async def test_page_heartbeat():
    """页面心跳：POST 记录活跃时间，GET 查询空闲秒数（run.py 看门狗用）"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 从未心跳 → 极大值
        r = await client.get("/api/v1/meta/heartbeat")
        assert r.status_code == 200
        assert r.json()["idle_seconds"] > 1e8

        # 上报心跳 → 空闲秒数接近 0
        r = await client.post("/api/v1/meta/heartbeat")
        assert r.status_code == 200
        r = await client.get("/api/v1/meta/heartbeat")
        assert r.status_code == 200
        assert r.json()["idle_seconds"] < 5