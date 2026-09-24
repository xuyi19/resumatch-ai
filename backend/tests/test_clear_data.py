"""M22 C1：一键清空数据"""
import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_clear_all_data():
    """清空后：历史为空；再清一次幂等不报错"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 先造点数据（同测试库已有历史记录）
        r1 = await client.delete("/api/v1/data")
        assert r1.status_code == 200
        assert "deleted" in r1.json()

        # 历史应为空
        r2 = await client.get("/api/v1/history", params={"limit": 50})
        assert r2.json()["items"] == []

        # 幂等
        r3 = await client.delete("/api/v1/data")
        assert r3.status_code == 200
