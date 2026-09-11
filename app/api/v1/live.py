import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.services.live_pipeline_service import LivePipelineService
from app.services.resume_service import ResumeService

router = APIRouter(prefix="/live", tags=["live"])


class LiveAnalyzeRequest(BaseModel):
    resume_id: int
    keyword: str
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
    """查询任务状态（轮询备用）"""
    task = LivePipelineService.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    return task


@router.get("/stream/{task_id}")
async def stream_task(task_id: str):
    """
    ★ SSE 实时推送任务进度
    前端用 EventSource 订阅
    """
    task = LivePipelineService.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    queue = LivePipelineService.get_queue(task_id)
    if queue is None:
        raise HTTPException(status_code=404, detail="任务队列不存在")

    async def event_generator():
        # 先推一次当前状态（避免错过早期消息）
        current = LivePipelineService.get_task(task_id)
        if current:
            yield {
                "event": "progress",
                "data": json.dumps({
                    "stage": current.get("stage", ""),
                    "progress": current.get("progress", 0),
                    "message": current.get("message", ""),
                    "status": current.get("status", "pending"),
                }, ensure_ascii=False),
            }
            # 如果已经完成了，直接推最终结果并结束
            if current.get("status") in ("success", "failed"):
                yield {
                    "event": "done",
                    "data": json.dumps({
                        "status": current["status"],
                        "result": current.get("result"),
                        "error": current.get("error"),
                    }, ensure_ascii=False),
                }
                return

        # 循环读队列
        while True:
            try:
                msg = await asyncio.wait_for(queue.get(), timeout=30)
                yield {
                    "event": "progress",
                    "data": json.dumps(msg, ensure_ascii=False),
                }

                # 任务结束：推最终结果
                if msg.get("status") in ("success", "failed"):
                    final = LivePipelineService.get_task(task_id)
                    if final:
                        yield {
                            "event": "done",
                            "data": json.dumps({
                                "status": final["status"],
                                "result": final.get("result"),
                                "error": final.get("error"),
                            }, ensure_ascii=False),
                        }
                    return

            except asyncio.TimeoutError:
                # 30 秒无消息，发心跳保持连接
                yield {"event": "ping", "data": "1"}

    return EventSourceResponse(event_generator())