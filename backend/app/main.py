from contextlib import asynccontextmanager
from pathlib import Path
import sys

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from loguru import logger
from sqlalchemy import update

from app import __author__, __build_tag__, __email__, __github__, __version__
from app.api.v1 import chat, health, history, live, optimize, resume, settings
from app.core.config import BASE_DIR, settings as app_settings
from app.core.db import Base, engine
from app.core.watermark import get_author_fingerprint
from app.models import entities  # noqa: F401


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ★ 启动 banner
    logger.info("=" * 64)
    logger.info("  ResuMatch AI · 智能简历诊断与岗位匹配推荐系统")
    logger.info(f"  Version    : {__version__}")
    logger.info(f"  Author     : {__author__} <{__email__}>")
    logger.info(f"  Repository : {__github__}")
    logger.info(f"  Fingerprint: {get_author_fingerprint()}")
    logger.info(f"  Build Tag  : {__build_tag__}")
    logger.info("=" * 64)

    logger.info("启动中，创建数据库表...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # ★ 启动补偿：内存任务表随进程消失，残留的 running 记录标记为失败
        await conn.execute(
            update(entities.DiagnosisRecord)
            .where(entities.DiagnosisRecord.status == "running")
            .values(status="failed", error="服务重启导致任务中断，请重新发起诊断")
        )
    logger.info("启动完成")
    yield
    await engine.dispose()
    logger.info("已关闭")


app = FastAPI(
    title=app_settings.APP_NAME,
    version=app_settings.APP_VERSION,
    lifespan=lifespan,
)


# ★ 响应头注入作者标识（别人调用 API 就能看到）
@app.middleware("http")
async def add_signature_header(request, call_next):
    response = await call_next(request)
    response.headers["X-Powered-By"] = f"ResuMatch/{__version__}"
    response.headers["X-Author"] = f"{__author__}/{get_author_fingerprint()}"
    return response


app.include_router(health.router, prefix="/api/v1")
app.include_router(resume.router, prefix="/api/v1")
app.include_router(live.router, prefix="/api/v1")
app.include_router(history.router, prefix="/api/v1")
app.include_router(optimize.router, prefix="/api/v1")
app.include_router(settings.router, prefix="/api/v1")
app.include_router(chat.router, prefix="/api/v1")


def _resolve_web_dir() -> Path | None:
    """前端构建产物目录：打包后在 _MEIPASS/web，开发时在 frontend/dist。"""
    if getattr(sys, "frozen", False):
        candidate = Path(getattr(sys, "_MEIPASS", str(BASE_DIR))) / "web"
    else:
        candidate = BASE_DIR.parent / "frontend" / "dist"
    return candidate if candidate.is_dir() else None


WEB_DIR = _resolve_web_dir()
if WEB_DIR is not None:
    # ★ 必须在所有 API 路由之后挂载，否则 /api/... 会被静态目录吞掉
    app.mount("/", StaticFiles(directory=str(WEB_DIR), html=True), name="web")
    logger.info(f"已挂载前端静态资源: {WEB_DIR}")
else:
    @app.get("/")
    async def root():
        return {"hint": "未检测到前端构建产物，请先 npm run build"}