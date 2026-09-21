import asyncio
import time
from datetime import datetime
from uuid import uuid4

from loguru import logger
from sqlalchemy import select

from app.core.db import AsyncSessionLocal
from app.models.entities import DiagnosisRecord
from app.services.diagnosis_service import DiagnosisService, NODE_STAGES

# 内存任务表（前端轮询/SSE 用）；完成条目超过 TTL 后惰性清理
TASKS: dict[str, dict] = {}
_TASK_TTL_SECONDS = 3600

# 进度落库节流：同一 task 最多 _DB_FLUSH_DELAY 秒写一次（终态由 run() 直接落库）
_DB_FLUSH_PENDING: set[str] = set()
_DB_FLUSH_DELAY = 0.8


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
    def create_task(
        resume_id: int | None = None,
        resume_name: str = "",
        owner_id: str = "local",
        enable_refine: bool = True,
    ) -> str:
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
            "resume_id": resume_id,
            "resume_name": resume_name,
            "owner_id": owner_id,
            "refine": enable_refine,
            "result": None,
            "error": None,
        }
        return task_id

    @staticmethod
    def get_task(task_id: str) -> dict | None:
        _cleanup_expired_tasks()
        return TASKS.get(task_id)

    @staticmethod
    async def get_task_from_db(task_id: str, owner_id: str | None = None) -> dict | None:
        """内存任务过期/服务重启后，从 DB 还原进度快照（含 owner 校验）。"""
        async with AsyncSessionLocal() as session:
            res = await session.execute(
                select(DiagnosisRecord).where(DiagnosisRecord.task_id == task_id)
            )
            rec = res.scalar_one_or_none()
            if not rec or (owner_id is not None and rec.owner_id != owner_id):
                return None
            data = {
                "id": rec.task_id,
                "status": rec.status,
                "stage": rec.stage or "准备中",
                "progress": rec.progress or 0,
                "message": "",
                "logs": rec.logs or [],
                "refine": True,
            }
            if rec.status == "success":
                data["result"] = rec.result
            elif rec.status == "failed":
                data["error"] = rec.error or ""
            return data

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

        # 运行中任务节流落库进度快照（成功/失败由 run() 统一写终态）
        if TASKS[task_id].get("status") == "running":
            LivePipelineService._schedule_db_flush(task_id)

    @staticmethod
    def _schedule_db_flush(task_id: str):
        if task_id in _DB_FLUSH_PENDING:
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        _DB_FLUSH_PENDING.add(task_id)

        async def _flush():
            try:
                await asyncio.sleep(_DB_FLUSH_DELAY)
                task = TASKS.get(task_id)
                if not task:
                    return
                async with AsyncSessionLocal() as session:
                    res = await session.execute(
                        select(DiagnosisRecord).where(DiagnosisRecord.task_id == task_id)
                    )
                    rec = res.scalar_one_or_none()
                    if rec:
                        rec.stage = task.get("stage", "")
                        rec.progress = task.get("progress", 0)
                        rec.logs = task.get("logs", [])
                        await session.commit()
            except Exception as e:
                logger.warning(f"[{task_id}] 进度落库失败: {e}")
            finally:
                _DB_FLUSH_PENDING.discard(task_id)

        loop.create_task(_flush())

    @staticmethod
    async def _save_failed(task_id: str, error: str):
        task = TASKS.get(task_id) or {}
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(DiagnosisRecord).where(DiagnosisRecord.task_id == task_id)
            )
            rec = result.scalar_one_or_none()
            if rec:
                rec.status = "failed"
                rec.error = error
                rec.stage = task.get("stage", "")
                rec.progress = task.get("progress", 0)
                rec.logs = task.get("logs", [])
                await session.commit()

    @classmethod
    async def run(
        cls,
        task_id: str,
        resume_text: str,
        jd_text: str,
        city: str = "",
        llm_config: dict | None = None,
        resume_name: str = "",
        enable_refine: bool = True,
    ):
        """
        启动诊断任务：6 节点 Agent 链（解析简历 ∥ 解析岗位 → 评分 → 差距 → 动态追问 → 改写）。
        若 LLM 判定需补充信息，任务在差距分析后暂停（waiting_clarify），
        由 /live/clarify 提交回答后经 cls.resume() 恢复执行。
        """
        info = TASKS.get(task_id) or {}
        owner_id = info.get("owner_id", "local")
        resume_id = info.get("resume_id")
        resume_name = resume_name or info.get("resume_name") or "未命名简历"

        # 上下文入任务表，供恢复执行复用
        cls._update(
            task_id,
            jd_text=jd_text,
            city=city,
            llm_config=llm_config,
            enable_refine=enable_refine,
        )

        # 落库：创建记录（owner 归属 + resume 关联在创建时写入）
        async with AsyncSessionLocal() as session:
            rec = DiagnosisRecord(
                task_id=task_id,
                resume_id=resume_id,
                keyword="用户输入",
                resume_name=resume_name,
                owner_id=owner_id,
                status="running",
            )
            session.add(rec)
            await session.commit()

        await cls._flow(
            task_id, resume_text, jd_text, city, llm_config, enable_refine,
            resume_answers=None,
        )

    @classmethod
    async def resume(cls, task_id: str, answers: dict):
        """用户补充信息后恢复诊断（续跑改写/精修并完成落库）。"""
        task = TASKS.get(task_id) or {}
        if task.get("status") != "waiting_clarify":
            raise ValueError("任务当前不在等待补充信息状态")
        cls._update(
            task_id,
            status="running",
            stage="改写建议",
            message=f"已收到 {len(answers)} 条补充回答，继续诊断...",
            questions=[],
        )
        await cls._flow(
            task_id,
            resume_text="",
            jd_text=task.get("jd_text", ""),
            city=task.get("city", ""),
            llm_config=task.get("llm_config"),
            enable_refine=task.get("enable_refine", True),
            resume_answers=answers,
        )

    @classmethod
    async def _flow(
        cls,
        task_id: str,
        resume_text: str,
        jd_text: str,
        city: str,
        llm_config: dict | None,
        enable_refine: bool,
        resume_answers: dict | None,
    ):
        """诊断主流程（首次运行与恢复执行共用）。"""
        resuming = resume_answers is not None
        try:
            if not resuming:
                cls._update(task_id, status="running", stage="准备中", progress=5,
                            message="准备分析...")

            done_stages: set[str] = set()
            if resuming:
                done_stages = {"解析简历", "解析岗位", "六维评分", "差距分析", "等待补充信息"}
            stage_order = [s for s in NODE_STAGES.values()
                           if not (s == "精修优化" and not enable_refine)]
            offset = len(done_stages & set(NODE_STAGES.values())) if resuming else 0

            def on_progress(step: int, total: int, stage: str):
                pct = 10 + int(step / total * 80)  # 10% → 90%
                done_stages.add(stage)
                # 节点一完成立即把「下一阶段」置为当前：
                # 长时间 LLM 调用期间 UI 不再停留在上一个已完成节点
                remaining = [s for s in stage_order if s not in done_stages]
                if remaining:
                    cls._update(
                        task_id,
                        stage=remaining[0],
                        progress=pct,
                        message=f"🤖 Agent {step}/{total} · {stage} 完成，开始{remaining[0]}",
                    )
                else:
                    cls._update(
                        task_id,
                        stage=stage,
                        progress=pct,
                        message=f"🤖 Agent {step}/{total} · {stage} 完成",
                    )

            diagnosis_service = DiagnosisService()
            diagnosis = await diagnosis_service.diagnose(
                resume_text, jd_text,
                llm_config=llm_config,
                on_progress=on_progress,
                enable_refine=enable_refine,
                thread_id=task_id,
                resume_answers=resume_answers,
                completed_offset=offset,
            )

            # 动态追问：图在 clarify_wait interrupt 暂停，等待用户补充信息
            if diagnosis.get("waiting"):
                questions = diagnosis.get("clarify_questions") or []
                cls._update(
                    task_id,
                    status="waiting_clarify",
                    stage="等待补充信息",
                    progress=max(TASKS.get(task_id, {}).get("progress", 0), 55),
                    message=f"🤔 为让诊断更准确，需要补充 {len(questions)} 条信息",
                    questions=questions,
                )
                return

            await cls._finalize(task_id, diagnosis, city, jd_text)
        except Exception as e:
            logger.exception(f"[{task_id}] 失败: {e}")
            cls._update(task_id, status="failed", error=str(e)[:500],
                        message=f"❌ 任务失败：{str(e)[:100]}",
                        finished_at=time.time())
            await cls._save_failed(task_id, str(e)[:500])
        finally:
            # 终态（成功/失败）释放 checkpointer 快照；暂停任务保留以便恢复
            task = TASKS.get(task_id) or {}
            if task.get("status") in ("success", "failed"):
                await DiagnosisService().release_thread(task_id)

    @classmethod
    async def _finalize(cls, task_id: str, diagnosis: dict, city: str, jd_text: str):
        """诊断完成：组装结果、更新任务终态并落库。"""
        cls._update(task_id, stage="生成报告", progress=93,
                    message="📊 生成最终报告...")

        # keyword 回填岗位名：优先用 JD 解析出的一句话总结
        summary = (diagnosis.get("job_analysis") or {}).get("summary", "").strip()
        job_title = summary[:24] if summary else "用户输入"

        result_data = {
            "keyword": job_title,
            "city": city,
            # 完整 JD 持久化：chat/optimize 阶段复用，避免上下文缩水
            "jd_text": jd_text,
            "diagnosis_target": {
                "job_id": 0,
                "title": job_title,
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

        # 落库（终态含进度快照）
        async with AsyncSessionLocal() as session:
            rec_res = await session.execute(
                select(DiagnosisRecord).where(DiagnosisRecord.task_id == task_id)
            )
            rec = rec_res.scalar_one_or_none()
            if rec:
                rec.status = "success"
                rec.keyword = job_title
                rec.result = result_data
                rec.stage = "完成"
                rec.progress = 100
                rec.logs = TASKS.get(task_id, {}).get("logs", [])
                await session.commit()
