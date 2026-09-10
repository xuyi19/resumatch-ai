from loguru import logger
from sqlalchemy import select

from app.core.db import AsyncSessionLocal
from app.models.entities import Job


class JobPipeline:
    """负责将爬取的数据清洗并入库"""

    async def process(self, jobs_data: list[dict]):
        """兼容旧接口，只打印日志"""
        inserted, skipped = await self.process_with_stats(jobs_data)
        logger.info(f"入库完成: 新增 {inserted} 条, 跳过 {skipped} 条")

    async def process_with_stats(self, jobs_data: list[dict]) -> tuple[int, int]:
        """返回 (新增, 跳过) 二元组"""
        if not jobs_data:
            logger.warning("没有可入库的职位数据")
            return 0, 0

        async with AsyncSessionLocal() as session:
            inserted, skipped = 0, 0

            for job in jobs_data:
                cleaned = {k: v for k, v in job.items() if v}
                if not cleaned.get("source_id") or not cleaned.get("title"):
                    skipped += 1
                    continue

                # 先查重
                exists = await session.execute(
                    select(Job.id).where(Job.source_id == cleaned["source_id"])
                )
                if exists.scalar_one_or_none() is not None:
                    skipped += 1
                    continue

                try:
                    session.add(Job(**cleaned))
                    await session.flush()
                    inserted += 1
                except Exception as e:
                    await session.rollback()
                    logger.debug(f"插入失败 {cleaned.get('title')}: {e}")
                    skipped += 1

            await session.commit()

        return inserted, skipped