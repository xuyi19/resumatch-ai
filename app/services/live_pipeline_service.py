import asyncio
import json
from datetime import datetime
from uuid import uuid4

from loguru import logger

from app.core.db import AsyncSessionLocal
from app.crawlers.pipeline import JobPipeline
from app.crawlers.zhilian_sync import ZhilianCrawlerSync
from app.services.diagnosis_service import DiagnosisService
from app.services.match_service import MatchService

# 内存任务表
TASKS: dict[str, dict] = {}
# ★ 每个任务对应一个消息队列（用于 SSE 推送）
QUEUES: dict[str, asyncio.Queue] = {}


class LivePipelineService:

    @staticmethod
    def create_task() -> str:
        task_id = uuid4().hex[:12]
        TASKS[task_id] = {
            "id": task_id,
            "status": "pending",
            "stage": "准备中",
            "progress": 0,
            "message": "",
            "created_at": datetime.now().isoformat(),
            "result": None,
            "error": None,
        }
        QUEUES[task_id] = asyncio.Queue()
        return task_id

    @staticmethod
    def get_task(task_id: str) -> dict | None:
        return TASKS.get(task_id)

    @staticmethod
    def get_queue(task_id: str) -> asyncio.Queue | None:
        return QUEUES.get(task_id)

    @classmethod
    def _update(cls, task_id: str, **kwargs):
        """更新任务状态，同时推送给 SSE 队列"""
        if task_id not in TASKS:
            return
        TASKS[task_id].update(kwargs)

        # 推送快照到队列
        q = QUEUES.get(task_id)
        if q is not None:
            snapshot = {
                "stage": TASKS[task_id].get("stage", ""),
                "progress": TASKS[task_id].get("progress", 0),
                "message": TASKS[task_id].get("message", ""),
                "status": TASKS[task_id].get("status", "running"),
            }
            try:
                q.put_nowait(snapshot)
            except Exception:
                pass

    @classmethod
    async def run(
        cls,
        task_id: str,
        resume_text: str,
        keyword: str,
        city: str = "北京",
        top_k: int = 10,
        llm_config: dict | None = None,
    ):
        try:
            # ---------- 阶段 1：爬取 ----------
            cls._update(task_id, status="running", stage="爬取岗位", progress=5,
                        message=f"正在爬取「{keyword}」岗位...")
            logger.info(f"[{task_id}] 爬取 {keyword} @ {city}")

            crawler = ZhilianCrawlerSync()
            jobs = await asyncio.to_thread(
                crawler.fetch_job_list,
                keyword=keyword, city=city, max_pages=2,
            )

            cls._update(task_id, stage="入库", progress=30,
                        message=f"抓到 {len(jobs)} 条，正在去重入库...")

            if not jobs:
                cls._update(task_id, status="failed",
                            error="未爬取到任何岗位，请换个关键词试试")
                return

            # ---------- 阶段 2：入库 ----------
            pipeline = JobPipeline()
            inserted, skipped = await pipeline.process_with_stats(jobs)
            logger.info(f"[{task_id}] 入库 新增{inserted} 跳过{skipped}")

            cls._update(task_id, stage="匹配", progress=45,
                        message=f"入库 {inserted} 条新岗位，开始匹配...")

            # ---------- 阶段 3：匹配 ----------
            async with AsyncSessionLocal() as session:
                match_service = MatchService(session)
                top_jobs = await match_service.recommend(
                    resume_text, top_k=top_k, use_semantic=True,
                    keyword_filter=keyword,
                )

                if not top_jobs:
                    cls._update(task_id, status="failed",
                                error="没有匹配到任何岗位")
                    return

                logger.info(f"[{task_id}] 匹配 Top {len(top_jobs)}")
                cls._update(task_id, stage="诊断", progress=65,
                            message=f"匹配到 Top {len(top_jobs)}，开始多智能体诊断...")

                # ---------- 阶段 4：诊断 ----------
                from app.models.entities import Job
                target_job = await session.get(Job, top_jobs[0]["job_id"])
                if not target_job:
                    cls._update(task_id, status="failed",
                                error="目标岗位不存在")
                    return

                jd_text = f"""岗位：{target_job.title}
公司：{target_job.company}
城市：{target_job.city}
经验要求：{target_job.experience or '不限'}
学历要求：{target_job.education or '不限'}
技能标签：{', '.join(target_job.tags or [])}

岗位描述：
{target_job.description}
"""

                diagnosis_service = DiagnosisService()
                diagnosis = await diagnosis_service.diagnose(
                    resume_text, jd_text, llm_config=llm_config,
                )

            cls._update(
                task_id,
                stage="完成",
                progress=100,
                message="诊断完成",
                status="success",
                result={
                    "keyword": keyword,
                    "city": city,
                    "crawled_count": len(jobs),
                    "inserted": inserted,
                    "top_jobs": top_jobs,
                    "diagnosis_target": {
                        "job_id": target_job.id,
                        "title": target_job.title,
                        "company": target_job.company,
                        "city": target_job.city,
                    },
                    "diagnosis": diagnosis,
                },
            )

        except Exception as e:
            logger.exception(f"[{task_id}] 失败: {e}")
            cls._update(task_id, status="failed", error=str(e)[:500])