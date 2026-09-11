from contextlib import asynccontextmanager

from fastapi import FastAPI
from loguru import logger

from app.api.v1 import health, history, job, live, match, resume
from app.core.config import settings
from app.core.db import Base, engine
from app.models import entities  # noqa: F401


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("启动中，创建数据库表...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("启动完成")
    yield
    await engine.dispose()
    logger.info("已关闭")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

# API 路由
app.include_router(health.router, prefix="/api/v1")
app.include_router(job.router, prefix="/api/v1")
app.include_router(resume.router, prefix="/api/v1")
app.include_router(match.router, prefix="/api/v1")
app.include_router(live.router, prefix="/api/v1")
app.include_router(history.router, prefix="/api/v1")


@app.get("/")
async def root():
    return {"message": f"{settings.APP_NAME} API", "docs": "/docs"}