from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.services.live_pipeline_service import LivePipelineService
from app.services.resume_service import ResumeService

router = APIRouter(prefix="/live", tags=["live"])


class LiveAnalyzeRequest(BaseModel):
    resume_id: int
    keyword: str            # 意向职位关键词，如 "Python 后端"
    city: str = "北京"
    top_k: int = 10
    llm_config: dict | None = None


@router.post("/analyze")
async def start_live_analyze(
    req: LiveAnalyzeRequest,
    db: AsyncSession = Depends(get_db),
):
    """启动完整流水线（后台异步执行），返回 task_id"""
    resume_service = ResumeService(db)
    resume = await resume_service.get_by_id(req.resume_id)
    if not resume:
        raise HTTPException(status_code=404, detail="简历不存在")

    task_id = LivePipelineService.create_task()

    # 后台异步执行
    import asyncio
    asyncio.create_task(
        LivePipelineService.run(
            task_id=task_id,
            resume_text=resume.raw_text,
            keyword=req.keyword,
            city=req.city,
            top_k=req.top_k,
            llm_config=req.llm_config,
        )
    )

    return {"task_id": task_id, "status": "pending"}


@router.get("/status/{task_id}")
async def get_task_status(task_id: str):
    """查询任务状态和结果"""
    task = LivePipelineService.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    return task