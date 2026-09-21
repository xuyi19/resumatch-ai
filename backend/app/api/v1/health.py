from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app import __author__, __build_tag__, __email__, __github__, __version__
from app.core.config import settings
from app.core.db import get_db
from app.core.watermark import get_author_fingerprint

router = APIRouter(tags=["health"])


class HealthOut(BaseModel):
    status: str
    app: str
    version: str
    db: str


@router.get("/health", response_model=HealthOut)
async def health(db: AsyncSession = Depends(get_db)):
    db_status = "ok"
    try:
        await db.execute(text("SELECT 1"))
    except Exception as e:
        db_status = f"error: {e}"

    return HealthOut(
        status="ok",
        app=settings.APP_NAME,
        version=settings.APP_VERSION,
        db=db_status,
    )


# ★ 隐蔽端点：暴露作者信息
@router.get("/_sig")
async def signature():
    """
    签名端点（非公开文档化）
    用于溯源，别人抄走代码也可能保留此端点
    """
    return {
        "v": __version__,
        "a": __author__,
        "e": __email__,
        "g": __github__,
        "f": get_author_fingerprint(),
        "t": __build_tag__,
    }


@router.get("/meta")
async def meta():
    """运行形态元信息：前端据此切换桌面版 / 网页版界面。

    local（桌面/本机）：单用户、数据全在本机，界面走紧凑 App 风格
    web（线上网站）：匿名会话隔离 + 服务端 Key 每日配额
    """
    return {
        "app_mode": settings.APP_MODE,
        "app_name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "build_tag": __build_tag__,
        "daily_limit": settings.WEB_DAILY_LIMIT,
        # 服务端是否预置了 Key（预置才涉及配额）
        "has_server_key": bool(settings.LLM_API_KEY),
    }