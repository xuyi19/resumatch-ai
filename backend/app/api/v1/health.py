from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app import __author__, __build_tag__, __email__, __github__, __version__
from app.core.config import settings
from app.core.db import get_db
from app.core.watermark import get_author_fingerprint
from app.models.schemas import HealthOut

router = APIRouter(tags=["health"])


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