import asyncio
from datetime import datetime
from uuid import uuid4

from loguru import logger
from sqlalchemy import select

from app.core.db import AsyncSessionLocal
from app.crawlers.pipeline import JobPipeline
from app.crawlers.zhilian_sync import ZhilianCrawlerSync
from app.models.entities import DiagnosisRecord, Job
from app.services.diagnosis_service import DiagnosisService
from app.services.match_service import MatchService

# 内存任务表
TASKS: dict[str, dict] = {}


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
            "logs": [],
            "created_at": datetime.now().isoformat(),
            "result": None,
            "error": None,
        }
        return task_id

    @staticmethod
    def get_task(task_id: str) -> dict | None:
        return TASKS.get(task_id)

    @staticmethod
    def _update(task_id: str, **kwargs):
        """更新任务状态，同时追加日志"""
        if task_id not in TASKS:
            return
        TASKS[task_id].update(kwargs)

        # 有 message 时追加一条日志
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
        keyword: str,
        city: str = "北京",
        top_k: int = 10,
        llm_config: dict | None = None,
        resume_name: str = "",
    ):
        # 落库：创建记录
        async with AsyncSessionLocal() as session:
            rec = DiagnosisRecord(
                task_id=task_id,
                keyword=keyword,
                city=city,
                resume_name=resume_name or "未命名简历",
                status="running",
            )
            session.add(rec)
            await session.commit()

        crawled_source_ids: list[str] = []

        try:
            # ========== 阶段 1：爬取 ==========
            cls._update(task_id, status="running", stage="爬取岗位", progress=5,
                        message=f"开始爬取「{keyword}」· 城市 {city}")

            crawler = ZhilianCrawlerSync()
            logger.info(f"[{task_id}] 爬取 {keyword} @ {city}")

            cls._update(task_id, stage="爬取岗位", progress=10,
                        message="启动无头浏览器（Playwright）")

            jobs = await asyncio.to_thread(
                crawler.fetch_job_list,
                keyword=keyword, city=city, max_pages=2,
            )

            crawled_source_ids = [j["source_id"] for j in jobs if j.get("source_id")]

            cls._update(task_id, stage="入库", progress=30,
                        message=f"抓取到 {len(jobs)} 条原始岗位")

            if not jobs:
                cls._update(task_id, status="failed",
                            error="未爬取到任何岗位，请换个关键词试试")
                await cls._save_failed(task_id, "未爬取到任何岗位")
                return

            # ========== 阶段 2：入库 ==========
            pipeline = JobPipeline()

            cls._update(task_id, stage="入库", progress=35,
                        message="正在去重、写入数据库...")

            inserted, skipped = await pipeline.process_with_stats(jobs)
            logger.info(f"[{task_id}] 入库 新增{inserted} 跳过{skipped}")

            cls._update(task_id, stage="入库", progress=45,
                        message=f"入库完成 · 新增 {inserted} · 跳过 {skipped}")

            # ========== 阶段 3：匹配 ==========
            cls._update(task_id, stage="匹配", progress=50,
                        message="加载语义向量模型...")

            async with AsyncSessionLocal() as session:
                match_service = MatchService(session)

                cls._update(task_id, stage="匹配", progress=55,
                            message=f"计算简历与 {len(jobs)} 条岗位的匹配度...")

                top_jobs = await match_service.recommend(
                    resume_text, top_k=top_k, use_semantic=True,
                    keyword_filter=keyword,
                )

                if not top_jobs:
                    cls._update(task_id, status="failed", error="没有匹配到任何岗位")
                    await cls._save_failed(task_id, "没有匹配到任何岗位")
                    await pipeline.delete_by_source_ids(crawled_source_ids)
                    return

                logger.info(f"[{task_id}] 匹配 Top {len(top_jobs)}")
                cls._update(task_id, stage="匹配", progress=60,
                            message=f"匹配完成 · Top {len(top_jobs)} 岗位已排序")

                # ========== 阶段 4：诊断 ==========
                target_job = await session.get(Job, top_jobs[0]["job_id"])
                if not target_job:
                    cls._update(task_id, status="failed", error="目标岗位不存在")
                    await cls._save_failed(task_id, "目标岗位不存在")
                    await pipeline.delete_by_source_ids(crawled_source_ids)
                    return

                cls._update(task_id, stage="诊断", progress=65,
                            message=f"诊断目标：{target_job.title} @ {target_job.company}")

                jd_text = f"""岗位：{target_job.title}
公司：{target_job.company}
城市：{target_job.city}
经验要求：{target_job.experience or '不限'}
学历要求：{target_job.education or '不限'}
技能标签：{', '.join(target_job.tags or [])}

岗位描述：
{target_job.description}
"""

                # 逐条 Agent 日志
                cls._update(task_id, stage="诊断", progress=68,
                            message="🤖 Agent 1/4 · 解析简历结构")
                cls._update(task_id, stage="诊断", progress=71,
                            message="🤖 Agent 2/4 · 六维评分")
                cls._update(task_id, stage="诊断", progress=74,
                            message="🤖 Agent 3/4 · 差距分析")
                cls._update(task_id, stage="诊断", progress=78,
                            message="🤖 Agent 4/4 · 改写建议")
                cls._update(task_id, stage="诊断", progress=82,
                            message="⏳ 调用大模型中，预计 60 秒...")

                diagnosis_service = DiagnosisService()
                diagnosis = await diagnosis_service.diagnose(
                    resume_text, jd_text,
                    llm_config=llm_config,
                )

            cls._update(task_id, stage="诊断", progress=95,
                        message="📊 生成最终报告...")

            result_data = {
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
            }

            cls._update(
                task_id,
                stage="完成",
                progress=98,
                message="✅ 诊断完成",
                status="success",
                result=result_data,
            )

            # 落库：成功结果
            async with AsyncSessionLocal() as session:
                rec_res = await session.execute(
                    select(DiagnosisRecord).where(DiagnosisRecord.task_id == task_id)
                )
                rec = rec_res.scalar_one_or_none()
                if rec:
                    rec.status = "success"
                    rec.result = result_data
                    await session.commit()

            # 清理本次爬取的岗位
            cls._update(task_id, stage="完成", progress=99,
                        message="🧹 清理临时岗位数据...")
            deleted = await pipeline.delete_by_source_ids(crawled_source_ids)
            logger.info(f"[{task_id}] 任务完成，已清理 {deleted} 条岗位数据")

            cls._update(task_id, stage="完成", progress=100,
                        message=f"✨ 全部完成 · 已清理 {deleted} 条临时数据")

        except Exception as e:
            logger.exception(f"[{task_id}] 失败: {e}")
            cls._update(task_id, status="failed", error=str(e)[:500],
                        message=f"❌ 任务失败：{str(e)[:100]}")
            await cls._save_failed(task_id, str(e)[:500])

            try:
                pipeline = JobPipeline()
                await pipeline.delete_by_source_ids(crawled_source_ids)
            except Exception as cleanup_err:
                logger.error(f"清理失败: {cleanup_err}")