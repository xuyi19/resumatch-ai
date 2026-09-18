import asyncio
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.db import get_db
from app.core.deps import get_owner_id
from app.models.entities import DiagnosisRecord
from app.services.live_pipeline_service import LivePipelineService
from app.services.resume_service import ResumeService

router = APIRouter(prefix="/live", tags=["live"])

# 持有后台任务引用，避免 asyncio 弱引用导致任务被 GC 静默回收（表现为卡在 pending）
_RUNNING_TASKS: set[asyncio.Task] = set()


class LLMConfig(BaseModel):
    api_key: str | None = None
    base_url: str | None = None
    model: str | None = None


class AnalyzeRequest(BaseModel):
    resume_id: int
    jd_text: str = ""
    llm_config: LLMConfig | None = None
    resume_name: str = ""


async def _check_web_quota(db: AsyncSession, owner_id: str, llm_config: LLMConfig | None):
    """web 态使用服务端 Key 时按每日配额限流（用户自带 Key 不限）"""
    if settings.APP_MODE != "web":
        return
    uses_server_key = not (llm_config and llm_config.api_key)
    if not uses_server_key or not settings.LLM_API_KEY:
        return

    # SQLite 存 UTC naive 时间，按 UTC 日界统计
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    cnt_res = await db.execute(
        select(func.count(DiagnosisRecord.id)).where(
            DiagnosisRecord.owner_id == owner_id,
            DiagnosisRecord.created_at >= today_start,
        )
    )
    used = cnt_res.scalar() or 0
    if used >= settings.WEB_DAILY_LIMIT:
        raise HTTPException(
            429,
            f"今日免费诊断次数已用完（{settings.WEB_DAILY_LIMIT} 次/天），"
            f"可在设置中填写自己的 API Key 继续使用",
        )


@router.post("/analyze")
async def start_analyze(
    req: AnalyzeRequest,
    db: AsyncSession = Depends(get_db),
    owner_id: str = Depends(get_owner_id),
):
    """启动诊断任务（JD 由用户粘贴文本提供）"""
    jd_text = (req.jd_text or "").strip()
    if len(jd_text) < 20:
        raise HTTPException(400, "JD 文本过短，请至少粘贴 20 个字")

    await _check_web_quota(db, owner_id, req.llm_config)

    resume_service = ResumeService(db)
    resume = await resume_service.get_by_id(req.resume_id, owner_id)
    if not resume:
        raise HTTPException(404, "简历不存在")

    logger.info(f"JD 已解析，长度 {len(jd_text)} 字")

    task_id = LivePipelineService.create_task(
        resume_id=resume.id,
        resume_name=req.resume_name,
        owner_id=owner_id,
    )
    task = asyncio.create_task(
        LivePipelineService.run(
            task_id=task_id,
            resume_text=resume.raw_text,
            jd_text=jd_text,
            llm_config=req.llm_config.model_dump() if req.llm_config else None,
        )
    )
    _RUNNING_TASKS.add(task)
    task.add_done_callback(_RUNNING_TASKS.discard)

    return {"task_id": task_id, "status": "pending"}


@router.get("/status/{task_id}")
async def get_task_status(task_id: str):
    task = LivePipelineService.get_task(task_id)
    if not task:
        raise HTTPException(404, "任务不存在")
    return task
