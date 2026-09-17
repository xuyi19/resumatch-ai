import time
from datetime import datetime
from uuid import uuid4

from loguru import logger
from sqlalchemy import select

from app.core.db import AsyncSessionLocal
from app.models.entities import DiagnosisRecord
from app.services.diagnosis_service import DiagnosisService

# 内存任务表（前端轮询用）；完成条目超过 TTL 后惰性清理
TASKS: dict[str, dict] = {}
_TASK_TTL_SECONDS = 3600


def _cleanup_expired_tasks():
    now = time.time()
    expired = [
        tid
        for tid, t in TASKS.items()
        if t.get("finished_at") and now - t["finished_at"] > _TASK_TTL_SECONDS
    ]
    for tid in expired:
        TASKS.pop(tid, None)


class LivePipelineService:

    @staticmethod
    def create_task() -> str:
        _cleanup_expired_tasks()
        task_id = uuid4().hex[:12]
        TASKS[task_id] = {
            "id": task_id,
            "status": "pending",
            "stage": "准备中",
            "progress": 0,
            "message": "",
            "logs": [],
            "created_at": datetime.now().isoformat(),
            "result": None,
            "error": None,
        }
        return task_id

    @staticmethod
    def get_task(task_id: str) -> dict | None:
        _cleanup_expired_tasks()
        return TASKS.get(task_id)

    @staticmethod
    def _update(task_id: str, **kwargs):
        if task_id not in TASKS:
            return
        TASKS[task_id].update(kwargs)

        msg = kwargs.get("message")
        if msg:
            TASKS[task_id].setdefault("logs", []).append({
                "time": datetime.now().strftime("%H:%M:%S"),
                "stage": TASKS[task_id].get("stage", ""),
                "message": msg,
            })

    @staticmethod
    async def _save_failed(task_id: str, error: str):
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(DiagnosisRecord).where(DiagnosisRecord.task_id == task_id)
            )
            rec = result.scalar_one_or_none()
            if rec:
                rec.status = "failed"
                rec.error = error
                await session.commit()

    @classmethod
    async def run(
        cls,
        task_id: str,
        resume_text: str,
        jd_text: str,
        city: str = "北京",
        llm_config: dict | None = None,
        resume_name: str = "",
    ):
        """
        用户提供 jd_text → 5 节点 Agent 链（解析简历 ∥ 解析岗位 → 评分 → 差距 → 改写）
        每个节点完成时通过 on_progress 实时上报进度。
        """
        # 落库：创建记录
        async with AsyncSessionLocal() as session:
            rec = DiagnosisRecord(
                task_id=task_id,
                keyword="用户输入",
                city=city,
                resume_name=resume_name or "未命名简历",
                status="running",
            )
            session.add(rec)
            await session.commit()

        try:
            cls._update(task_id, status="running", stage="准备中", progress=5,
                        message="准备分析...")

            def on_progress(step: int, total: int, stage: str):
                pct = 10 + int(step / total * 80)  # 10% → 90%
                cls._update(
                    task_id,
                    stage=stage,
                    progress=pct,
                    message=f"🤖 Agent {step}/{total} · {stage}",
                )

            diagnosis_service = DiagnosisService()
            diagnosis = await diagnosis_service.diagnose(
                resume_text, jd_text,
                llm_config=llm_config,
                on_progress=on_progress,
            )

            cls._update(task_id, stage="生成报告", progress=93,
                        message="📊 生成最终报告...")

            result_data = {
                "keyword": "用户输入",
                "city": city,
                # 完整 JD 持久化：chat/optimize 阶段复用，避免上下文缩水
                "jd_text": jd_text,
                "diagnosis_target": {
                    "job_id": 0,
                    "title": "用户提供的岗位",
                    "company": "",
                    "city": city,
                },
                "diagnosis": diagnosis,
            }

            cls._update(
                task_id,
                stage="完成",
                progress=100,
                message="✅ 诊断完成",
                status="success",
                result=result_data,
                finished_at=time.time(),
            )

            # 落库
            async with AsyncSessionLocal() as session:
                rec_res = await session.execute(
                    select(DiagnosisRecord).where(DiagnosisRecord.task_id == task_id)
                )
                rec = rec_res.scalar_one_or_none()
                if rec:
                    rec.status = "success"
                    rec.result = result_data
                    await session.commit()

        except Exception as e:
            logger.exception(f"[{task_id}] 失败: {e}")
            cls._update(task_id, status="failed", error=str(e)[:500],
                        message=f"❌ 任务失败：{str(e)[:100]}",
                        finished_at=time.time())
            await cls._save_failed(task_id, str(e)[:500])
