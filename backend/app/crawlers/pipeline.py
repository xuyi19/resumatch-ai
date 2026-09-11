from loguru import logger
from sqlalchemy import delete, select

from app.core.db import AsyncSessionLocal
from app.models.entities import Job


class JobPipeline:
    async def process(self, jobs_data: list[dict]):
        inserted, skipped = await self.process_with_stats(jobs_data)
        logger.info(f"入库完成: 新增 {inserted} 条, 跳过 {skipped} 条")

    async def process_with_stats(self, jobs_data: list[dict]) -> tuple[int, int]:
        if not jobs_data:
            return 0, 0

        async with AsyncSessionLocal() as session:
            inserted, skipped = 0, 0

            for job in jobs_data:
                cleaned = {k: v for k, v in job.items() if v}
                if not cleaned.get("source_id") or not cleaned.get("title"):
                    skipped += 1
                    continue

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

    async def delete_by_source_ids(self, source_ids: list[str]) -> int:
        """按 source_id 批量删除岗位"""
        if not source_ids:
            return 0

        async with AsyncSessionLocal() as session:
            stmt = delete(Job).where(Job.source_id.in_(source_ids))
            result = await session.execute(stmt)
            await session.commit()
            deleted = result.rowcount
            logger.info(f"清理岗位: 删除 {deleted} 条")
            return deleted