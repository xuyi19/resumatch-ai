import asyncio
import json
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
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
    enable_refine: bool | None = None  # self-refine 开关；None 用服务端默认


class ClarifyRequest(BaseModel):
    answers: dict[str, str]  # {问题id: 回答}


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

    enable_refine = (
        req.enable_refine if req.enable_refine is not None else settings.ENABLE_SELF_REFINE
    )

    task_id = LivePipelineService.create_task(
        resume_id=resume.id,
        resume_name=req.resume_name,
        owner_id=owner_id,
        enable_refine=enable_refine,
    )
    task = asyncio.create_task(
        LivePipelineService.run(
            task_id=task_id,
            resume_text=resume.raw_text,
            jd_text=jd_text,
            llm_config=req.llm_config.model_dump() if req.llm_config else None,
            enable_refine=enable_refine,
        )
    )
    _RUNNING_TASKS.add(task)
    task.add_done_callback(_RUNNING_TASKS.discard)

    return {"task_id": task_id, "status": "pending"}


@router.post("/clarify/{task_id}")
async def submit_clarify(
    task_id: str,
    req: ClarifyRequest,
    owner_id: str = Depends(get_owner_id),
):
    """提交追问回答，恢复暂停的诊断任务（LangGraph interrupt resume）。"""
    task = LivePipelineService.get_task(task_id)
    if task is None or (task.get("owner_id") and task["owner_id"] != owner_id):
        raise HTTPException(404, "任务不存在")
    if task.get("status") != "waiting_clarify":
        raise HTTPException(409, "任务不在等待补充信息状态")

    answers = {k: str(v).strip() for k, v in (req.answers or {}).items() if str(v).strip()}
    if not answers:
        raise HTTPException(400, "回答内容不能为空")
    if len(answers) > 10:
        raise HTTPException(400, "回答条目过多")

    t = asyncio.create_task(LivePipelineService.resume(task_id, answers))
    _RUNNING_TASKS.add(t)
    t.add_done_callback(_RUNNING_TASKS.discard)
    return {"task_id": task_id, "status": "running"}


@router.get("/status/{task_id}")
async def get_task_status(task_id: str, owner_id: str = Depends(get_owner_id)):
    """任务状态：优先内存，过期/重启后回退 DB 快照（含 owner 校验）"""
    task = LivePipelineService.get_task(task_id)
    if task is None:
        task = await LivePipelineService.get_task_from_db(task_id, owner_id)
        if task:
            return task
        raise HTTPException(404, "任务不存在")
    if task.get("owner_id") and task["owner_id"] != owner_id:
        raise HTTPException(404, "任务不存在")
    return task


@router.get("/stream/{task_id}")
async def stream_task(task_id: str, owner_id: str = Depends(get_owner_id)):
    """SSE 实时推送任务进度；终态后服务端关流，前端收到 fatal 事件表示异常。"""

    async def event_gen():
        last_payload = None
        ticks = 0
        while True:
            task = LivePipelineService.get_task(task_id)
            if task is None:
                task = await LivePipelineService.get_task_from_db(task_id, owner_id)
                if not task:
                    yield _fatal("任务不存在")
                    return
            elif task.get("owner_id") and task["owner_id"] != owner_id:
                yield _fatal("任务不存在")
                return

            payload = json.dumps(
                {
                    "status": task.get("status", "pending"),
                    "stage": task.get("stage", ""),
                    "progress": task.get("progress", 0),
                    "message": task.get("message", ""),
                    "logs": task.get("logs", []),
                    "refine": task.get("refine", True),
                    "questions": task.get("questions") or [],
                    "result": task.get("result"),
                    "error": task.get("error"),
                },
                ensure_ascii=False,
            )
            if payload != last_payload:
                last_payload = payload
                yield f"data: {payload}\n\n"

            if task.get("status") in ("success", "failed"):
                return

            ticks += 1
            if ticks > 600:  # 10 分钟兜底断开，防止悬挂连接
                yield _fatal("任务超时未完成")
                return
            await asyncio.sleep(1)

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


def _fatal(detail: str) -> str:
    return f"event: fatal\ndata: {json.dumps({'detail': detail}, ensure_ascii=False)}\n\n"
