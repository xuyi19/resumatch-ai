from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger

from app.api.v1 import health, job, live, match, resume
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


# 禁止缓存 HTML
@app.middleware("http")
async def no_cache_html(request: Request, call_next):
    response = await call_next(request)
    path = request.url.path
    if path == "/" or path.endswith(".html"):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


# API 路由
app.include_router(health.router, prefix="/api/v1")
app.include_router(job.router, prefix="/api/v1")
app.include_router(resume.router, prefix="/api/v1")
app.include_router(match.router, prefix="/api/v1")
app.include_router(live.router, prefix="/api/v1")


# 前端托管
@app.get("/")
async def serve_index():
    return FileResponse(
        "frontend/index.html",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


app.mount("/frontend", StaticFiles(directory="frontend", html=True), name="frontend")