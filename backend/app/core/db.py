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
        # SQL echo 固定关闭：服务窗口只保留 uvicorn 启动横幅与错误（用户反馈刷屏）；
        # DEBUG 开关继续用于其他调试行为
        echo=False,
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


# 老库升级：create_all 不会给已存在的表加列，这里用 PRAGMA 检查后 ALTER TABLE 补列。
# 新增列统一登记在这里（表名 → [(列名, DDL 类型), ...]），lifespan 启动时调用。
_SCHEMA_NEW_COLUMNS: dict[str, list[tuple[str, str]]] = {
    "resumes": [
        ("owner_id", "VARCHAR(64) DEFAULT 'local'"),
        ("file_path", "VARCHAR(500)"),
    ],
    "diagnosis_records": [
        ("owner_id", "VARCHAR(64) DEFAULT 'local'"),
        ("stage", "VARCHAR(32) DEFAULT ''"),
        ("progress", "INTEGER DEFAULT 0"),
        ("logs", "JSON"),
        ("questions", "JSON"),
        ("clarify_ctx", "JSON"),
        ("parent_task_id", "VARCHAR(32)"),
    ],
    "conversations": [
        ("owner_id", "VARCHAR(64) DEFAULT 'local'"),
        ("context", "TEXT"),
        ("chat_log", "TEXT"),
    ],
}


async def ensure_schema_columns() -> None:
    """老库补列 + 回填默认值（幂等，可重复执行）。"""
    from sqlalchemy import text

    async with engine.begin() as conn:
        for table, columns in _SCHEMA_NEW_COLUMNS.items():
            res = await conn.execute(text(f"PRAGMA table_info({table})"))
            existing = {row[1] for row in res.fetchall()}
            if not existing:
                continue  # 表不存在（新库由 create_all 建全）
            for col_name, col_ddl in columns:
                if col_name not in existing:
                    await conn.execute(
                        text(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_ddl}")
                    )
        # 老库已有行补默认归属
        for table in _SCHEMA_NEW_COLUMNS:
            res = await conn.execute(text(f"PRAGMA table_info({table})"))
            existing = {row[1] for row in res.fetchall()}
            if "owner_id" in existing:
                await conn.execute(
                    text(
                        f"UPDATE {table} SET owner_id = 'local' "
                        f"WHERE owner_id IS NULL OR owner_id = ''"
                    )
                )
