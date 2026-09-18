"""pytest 共享夹具：ASGITransport 不触发 lifespan，测试前手动建表 + 老库补列"""
import pytest
import pytest_asyncio

from app.core.db import Base, ensure_schema_columns, engine
from app.models import entities  # noqa: F401 注册 ORM 模型


@pytest_asyncio.fixture(autouse=True)
async def _create_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await ensure_schema_columns()
    yield
