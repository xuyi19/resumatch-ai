from pathlib import Path

from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import AsyncAdaptedQueuePool

from app.core.config import settings


def _make_engine():
    """SQLite（aiosqlite）单文件库：桌面版免安装，开发与分发同一套。

    每个会话独立连接（QueuePool）+ WAL：请求会话与后台任务会话可并发读写，
    StaticPool 的共享单连接会在并发 commit 时互相 reset 游标。
    """
    url = settings.DB_URL
    db_path = url.split("///", 1)[1]
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    engine = create_async_engine(
        url,
        echo=settings.DEBUG,
        future=True,
        poolclass=AsyncAdaptedQueuePool,
        connect_args={"check_same_thread": False, "timeout": 30},
    )

    @event.listens_for(engine.sync_engine, "connect")
    def _sqlite_pragma(dbapi_connection, connection_record):
        # WAL 允许多读单写并发；busy_timeout 缓解写锁竞争
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA busy_timeout=5000")
        finally:
            cursor.close()

    return engine


engine = _make_engine()

# 异步 session 工厂
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


# 所有 ORM 模型的基类
class Base(DeclarativeBase):
    pass


# FastAPI 依赖注入用的 session 提供器
async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session
