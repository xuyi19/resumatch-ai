import asyncio
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
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

    # ★ JD 两种输入方式
    jd_input_type: Literal["text", "url"] = "text"
    jd_text: str | None = None       # 方式 A：粘贴文本
    jd_url: str | None = None        # 方式 B：粘贴链接

    city: str = "北京"
    llm_config: LLMConfig | None = None
    resume_name: str = ""


async def _resolve_jd_text(req: AnalyzeRequest) -> str:
    """根据用户选择的输入方式，解析出统一的 JD 文本"""
    if req.jd_input_type == "text":
        text = (req.jd_text or "").strip()
        if len(text) < 20:
            raise HTTPException(400, "JD 文本过短，请至少粘贴 20 个字")
        return text

    if req.jd_input_type == "url":
        url = (req.jd_url or "").strip()
        if not url.startswith("http"):
            raise HTTPException(400, "请提供合法的 JD 链接")
        try:
            # 惰性加载：桌面版未打包 Playwright/Chromium 时不影响其它入口
            from app.crawlers.jd_fetcher import fetch_jd_from_url

            text = await fetch_jd_from_url(url)
            if len(text) < 20:
                raise RuntimeError("抓取内容过短")
            return text
        except Exception as e:
            logger.warning(f"JD 链接抓取失败: {e}")
            raise HTTPException(
                400,
                f"链接抓取失败（{str(e)[:80]}）。建议改用「粘贴 JD 文本」方式",
            )

    raise HTTPException(400, f"不支持的输入方式: {req.jd_input_type}")


@router.post("/analyze")
async def start_analyze(req: AnalyzeRequest, db: AsyncSession = Depends(get_db)):
    """启动分析任务（支持两种 JD 输入方式）"""
    jd_text = await _resolve_jd_text(req)

    resume_service = ResumeService(db)
    resume = await resume_service.get_by_id(req.resume_id)
    if not resume:
        raise HTTPException(404, "简历不存在")

    logger.info(f"JD 已解析，长度 {len(jd_text)} 字")

    task_id = LivePipelineService.create_task()
    task = asyncio.create_task(
        LivePipelineService.run(
            task_id=task_id,
            resume_text=resume.raw_text,
            jd_text=jd_text,
            city=req.city,
            llm_config=req.llm_config.model_dump() if req.llm_config else None,
            resume_name=req.resume_name,
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
