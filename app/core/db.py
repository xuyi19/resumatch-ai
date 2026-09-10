from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import AsyncAdaptedQueuePool

from app.core.config import settings

# 创建异步引擎
engine = create_async_engine(
    settings.DB_URL,
    echo=settings.DEBUG,              # 开发时打印 SQL，生产环境关掉
    future=True,
    poolclass=AsyncAdaptedQueuePool,  # 异步专用连接池
    pool_size=10,                     # 池中常驻连接数
    max_overflow=20,                  # 峰值时最多额外创建的连接数
    pool_recycle=1800,                # 30分钟回收，避免 MySQL 空闲断连
    pool_pre_ping=True,               # 取连接前先 ping，自动重连
)

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