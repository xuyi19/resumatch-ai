import asyncio
import time
from datetime import datetime
from uuid import uuid4

from loguru import logger
from sqlalchemy import select

from app.core.db import AsyncSessionLocal
from app.models.entities import DiagnosisRecord
from app.services.diagnosis_service import (
    DiagnosisPartialError,
    DiagnosisService,
    NODE_STAGES,
)

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
        parent_task_id: str | None = None,
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
            "parent_task_id": parent_task_id,
            "result": None,
            "error": None,
        }
        return task_id

    @staticmethod
    def get_task(task_id: str) -> dict | None:
        _cleanup_expired_tasks()
        return TASKS.get(task_id)

    # 视为「进行中」的状态：新诊断发起前用于重复防护
    _ACTIVE_STATUSES = ("pending", "running", "waiting_clarify")
    # waiting_clarify 超过该时长视为废弃（用户不会回来回答了），不再阻塞新诊断
    _WAITING_STALE_SECONDS = 24 * 3600

    @classmethod
    def get_active_task(cls, owner_id: str) -> dict | None:
        """该用户当前未完成的任务（409 响应带出 id，前端可引导跳转/放弃）。"""
        _cleanup_expired_tasks()
        for t in TASKS.values():
            if t.get("owner_id") == owner_id and t.get("status") in cls._ACTIVE_STATUSES:
                return t
        return None

    @classmethod
    def has_active_task(cls, owner_id: str) -> bool:
        """该用户是否已有未完成的诊断任务（防重复发起浪费 LLM 调用）。"""
        return cls.get_active_task(owner_id) is not None

    @classmethod
    async def expire_stale_waiting(cls) -> int:
        """启动补偿补充：长时间无人应答的 waiting_clarify 自动作废（DB + 内存），
        避免旧追问永久占用「进行中」名额导致无法发起新诊断。"""
        now = time.time()
        stale_ids = []
        for tid, t in TASKS.items():
            if t.get("status") != "waiting_clarify":
                continue
            try:
                age = now - datetime.fromisoformat(t.get("created_at") or "").timestamp()
            except (ValueError, TypeError):
                continue
            if age > cls._WAITING_STALE_SECONDS:
                stale_ids.append(tid)
        for tid in stale_ids:
            TASKS.pop(tid, None)
            await cls._save_failed(tid, "追问超过 24 小时未回答，任务已自动作废")
        return len(stale_ids)

    @classmethod
    async def abandon_task(cls, task_id: str, owner_id: str) -> bool:
        """用户主动放弃未完成任务：内存 + DB 双清，立即释放「进行中」名额。

        任务刚创建还在 pending（DB 记录由 run() 落库，可能尚未写入）时也允许放弃：
        以内存任务为准，同时用 abandoned 标记阻断 run() 的后续落库（防复活）。
        """
        task = TASKS.get(task_id)
        if task and task.get("owner_id") and task["owner_id"] != owner_id:
            return False
        if task and task.get("status") not in cls._ACTIVE_STATUSES:
            return False  # 已终态（成功/失败/已放弃）的任务无需重复放弃
        if task is None:
            # 内存无快照（服务重启过）：只能依据 DB 记录判断
            async with AsyncSessionLocal() as session:
                res = await session.execute(
                    select(DiagnosisRecord).where(DiagnosisRecord.task_id == task_id)
                )
                rec = res.scalar_one_or_none()
                if rec is None:
                    return False
                if rec.owner_id and rec.owner_id != owner_id:
                    return False
                if rec.status not in cls._ACTIVE_STATUSES:
                    return False  # 已终态的任务无需放弃
                rec.status = "failed"
                rec.error = "用户主动放弃该任务"
                rec.finished_at = datetime.now()
                await session.commit()
            return True

        task.update({
            "status": "failed",
            "error": "用户主动放弃该任务",
            "finished_at": time.time(),
            "abandoned": True,
        })
        # DB 已有记录则同步终态（run() 尚未落库时跳过，run() 被 abandoned 标记阻断）
        async with AsyncSessionLocal() as session:
            res = await session.execute(
                select(DiagnosisRecord).where(DiagnosisRecord.task_id == task_id)
            )
            rec = res.scalar_one_or_none()
            if rec and rec.status in cls._ACTIVE_STATUSES:
                if rec.owner_id and rec.owner_id != owner_id:
                    return False
                rec.status = "failed"
                rec.error = "用户主动放弃该任务"
                rec.finished_at = datetime.now()
                await session.commit()
        return True

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
                # M20：前端重诊/增量对比需要简历 id 与来源任务链
                "resume_id": rec.resume_id,
                "resume_name": rec.resume_name or "",
                "parent_task_id": rec.parent_task_id,
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
        # 用户已放弃的任务：不再接受任何状态/进度更新（防止 run() 在途时复活任务）
        if TASKS[task_id].get("abandoned"):
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
    async def _save_failed(task_id: str, error: str,
                           partial: dict | None = None,
                           city: str = "", jd_text: str = ""):
        """失败落库。partial 非空时（B1）把已完成节点的部分结果与 error 并存落库。"""
        task = TASKS.get(task_id) or {}
        if task.get("abandoned"):
            return  # 用户已放弃，DB 终态已写，不覆写
        partial_result = None
        if partial:
            summary = (partial.get("job_analysis") or {}).get("summary", "").strip()
            job_title = summary[:24] if summary else "用户输入"
            partial_result = {
                "keyword": job_title,
                "city": city,
                "jd_text": jd_text,
                "diagnosis_target": {
                    "job_id": 0, "title": job_title, "company": "", "city": city,
                },
                "diagnosis": partial,
                "partial": True,  # 前端识别：这是失败任务的部分结果
            }
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
                if partial_result:
                    rec.result = partial_result
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
        # 用户在任务启动瞬间放弃：直接终止，不创建 DB 记录、不跑 LLM
        if info.get("abandoned"):
            logger.info(f"[{task_id}] 任务已被用户放弃，跳过执行")
            return
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
                parent_task_id=info.get("parent_task_id"),
            )
            session.add(rec)
            await session.commit()

        await cls._flow(
            task_id, resume_text, jd_text, city, llm_config, enable_refine,
            resume_answers=None,
        )

    @staticmethod
    async def _save_waiting(task_id: str, questions: list):
        """waiting_clarify 终态快照落库：问题列表 + 恢复上下文（M16）。"""
        task = TASKS.get(task_id) or {}
        ctx = {
            "jd_text": task.get("jd_text", ""),
            "city": task.get("city", ""),
            "llm_config": task.get("llm_config"),
            "enable_refine": task.get("enable_refine", True),
            "resume_name": task.get("resume_name", ""),
            "resume_id": task.get("resume_id"),
        }
        async with AsyncSessionLocal() as session:
            res = await session.execute(
                select(DiagnosisRecord).where(DiagnosisRecord.task_id == task_id)
            )
            rec = res.scalar_one_or_none()
            if rec:
                rec.status = "waiting_clarify"
                rec.questions = questions
                rec.clarify_ctx = ctx
                rec.stage = "等待补充信息"
                rec.logs = task.get("logs", [])
                await session.commit()

    @classmethod
    async def resume(cls, task_id: str, answers: dict):
        """用户补充信息后恢复诊断（续跑改写/精修并完成落库）。

        M16：服务重启后 TASKS 内存条目丢失，可从 DB 的 waiting 快照重建
        （图状态由 SqliteSaver 文件快照提供，Command(resume) 直接续跑）。
        """
        task = TASKS.get(task_id) or {}
        if task.get("status") != "waiting_clarify":
            restored = await cls._restore_waiting_task(task_id)
            if not restored:
                raise ValueError("任务当前不在等待补充信息状态")
            task = restored
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
    async def _restore_waiting_task(cls, task_id: str) -> dict | None:
        """从 DB 的 waiting 快照重建内存任务条目（owner 校验沿用记录归属）。"""
        async with AsyncSessionLocal() as session:
            res = await session.execute(
                select(DiagnosisRecord).where(DiagnosisRecord.task_id == task_id)
            )
            rec = res.scalar_one_or_none()
        if not rec or rec.status != "waiting_clarify" or not rec.clarify_ctx:
            return None
        ctx = rec.clarify_ctx
        task = {
            "id": task_id,
            "status": "waiting_clarify",
            "stage": "等待补充信息",
            "progress": rec.progress or 55,
            "message": "",
            "logs": rec.logs or [],
            "created_at": rec.created_at.isoformat() if rec.created_at else "",
            "resume_id": ctx.get("resume_id"),
            "resume_name": ctx.get("resume_name", ""),
            "owner_id": rec.owner_id or "local",
            "refine": ctx.get("enable_refine", True),
            "jd_text": ctx.get("jd_text", ""),
            "city": ctx.get("city", ""),
            "llm_config": ctx.get("llm_config"),
            "enable_refine": ctx.get("enable_refine", True),
            "questions": rec.questions or [],
            "result": None,
            "error": None,
        }
        TASKS[task_id] = task
        return task

    @classmethod
    async def recover_waiting_tasks(cls):
        """启动补偿（M16）：把 DB 中 waiting_clarify 的任务重建进内存任务表，
        用户提交回答后可跨重启续跑；无快照上下文的老任务标记失败。"""
        async with AsyncSessionLocal() as session:
            res = await session.execute(
                select(DiagnosisRecord).where(DiagnosisRecord.status == "waiting_clarify")
            )
            recs = res.scalars().all()
        restored = 0
        for rec in recs:
            if rec.clarify_ctx is not None:
                task = await cls._restore_waiting_task(rec.task_id)
                if task:
                    restored += 1
                    continue
            await cls._save_failed(
                rec.task_id, "服务重启导致追问上下文丢失，请重新发起诊断"
            )
        if restored:
            logger.info(f"启动补偿：恢复 {restored} 个等待补充信息的诊断任务")
        return restored

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
                # M16 跨重启恢复：问题与恢复上下文落库（graph 快照已在 SqliteSaver 文件）
                await cls._save_waiting(task_id, questions)
                return

            await cls._finalize(task_id, diagnosis, city, jd_text)
        except DiagnosisPartialError as e:
            # B1：中断但有部分结果——result 与 error 并存落库，快照保留供断点重试
            partial = e.partial or {}
            err_text = str(e.cause or e)[:500]
            logger.exception(f"[{task_id}] 失败（保留部分结果 {len(partial)} 项）: {e.cause}")
            partial_result = None
            if partial:
                summary = (partial.get("job_analysis") or {}).get("summary", "").strip()
                job_title = summary[:24] if summary else "用户输入"
                partial_result = {
                    "keyword": job_title, "city": city, "jd_text": jd_text,
                    "diagnosis_target": {"job_id": 0, "title": job_title,
                                         "company": "", "city": city},
                    "diagnosis": partial, "partial": True,
                }
            cls._update(task_id, status="failed", error=err_text,
                        result=partial_result,
                        message=f"❌ 任务失败：{err_text[:100]}（已保留部分结果）",
                        finished_at=time.time())
            await cls._save_failed(task_id, err_text, partial=partial,
                                   city=city, jd_text=jd_text)
        except Exception as e:
            logger.exception(f"[{task_id}] 失败: {e}")
            cls._update(task_id, status="failed", error=str(e)[:500],
                        message=f"❌ 任务失败：{str(e)[:100]}",
                        finished_at=time.time())
            await cls._save_failed(task_id, str(e)[:500])
        finally:
            # 终态释放快照：成功释放；失败保留（B1 断点重试），重新发起走新 thread_id
            task = TASKS.get(task_id) or {}
            if task.get("status") == "success":
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

        # 落库（终态含进度快照）；已放弃任务不覆写 DB（防复活）
        if not (TASKS.get(task_id) or {}).get("abandoned"):
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

    @classmethod
    async def retry(cls, task_id: str, owner_id: str = "local") -> str:
        """B1：失败任务重试——从 checkpointer 断点续跑，沿用原简历/JD/LLM 配置，
        已完成节点不重跑（不重复消耗 API 费用）。"""
        _cleanup_expired_tasks()
        async with AsyncSessionLocal() as session:
            res = await session.execute(
                select(DiagnosisRecord).where(
                    DiagnosisRecord.task_id == task_id,
                    DiagnosisRecord.owner_id == owner_id,
                )
            )
            rec = res.scalar_one_or_none()
        if not rec:
            raise ValueError("任务不存在")
        if rec.status != "failed":
            raise ValueError("仅失败任务可重试")

        svc = DiagnosisService()
        values = svc.snapshot_values(task_id)
        if not values:
            raise ValueError("无可恢复的断点（快照已释放），请重新发起诊断")

        # 重置任务态进入续跑
        cls._update(task_id, status="running", stage="重新诊断", progress=55,
                    error=None, message="🔁 从上次失败处继续（已完成节点不重跑）...")
        asyncio.create_task(cls._retry_run(task_id))
        return task_id

    @classmethod
    async def _retry_run(cls, task_id: str):
        """断点续跑执行体：复用交互图收集逻辑，终态处理与 run() 一致。"""
        svc = DiagnosisService()

        def on_progress(step: int, total: int, stage: str):
            pct = 55 + int(step / total * 35)  # 续跑从 55% 起步（粗略）
            cls._update(task_id, stage=stage, progress=pct,
                        message=f"🤖 续跑 · {stage} 完成")

        try:
            diagnosis = await svc.resume_after_error(task_id, on_progress=on_progress)

            # 防御：断点恰好停在 clarify interrupt（正常不应发生）
            if diagnosis.get("waiting"):
                questions = diagnosis.get("clarify_questions") or []
                cls._update(task_id, status="waiting_clarify", stage="等待补充信息",
                            message=f"🤔 需要补充 {len(questions)} 条信息",
                            questions=questions)
                await cls._save_waiting(task_id, questions)
                return

            # city/jd_text 从落库的部分结果恢复（jd_text 兜底取 graph 快照）
            city, jd_text = "", ""
            async with AsyncSessionLocal() as session:
                res = await session.execute(
                    select(DiagnosisRecord).where(DiagnosisRecord.task_id == task_id)
                )
                rec = res.scalar_one_or_none()
                if rec and rec.result:
                    city = rec.result.get("city", "")
                    jd_text = rec.result.get("jd_text", "")
            if not jd_text:
                values = svc.snapshot_values(task_id) or {}
                jd_text = values.get("jd_text", "")

            await cls._finalize(task_id, diagnosis, city, jd_text)
        except DiagnosisPartialError as e:
            partial = e.partial or {}
            err_text = str(e.cause or e)[:500]
            logger.exception(f"[{task_id}] 续跑仍失败（保留部分结果 {len(partial)} 项）: {e.cause}")
            cls._update(task_id, status="failed", error=err_text,
                        message=f"❌ 续跑失败：{err_text[:100]}",
                        finished_at=time.time())
            await cls._save_failed(task_id, err_text, partial=partial)
        except Exception as e:
            logger.exception(f"[{task_id}] 续跑失败: {e}")
            cls._update(task_id, status="failed", error=str(e)[:500],
                        message=f"❌ 续跑失败：{str(e)[:100]}",
                        finished_at=time.time())
            await cls._save_failed(task_id, str(e)[:500])
