from loguru import logger
from sqlalchemy import select

from app.core.db import AsyncSessionLocal
from app.models.entities import Job


class JobPipeline:
    """负责将爬取的数据清洗并入库"""

    async def process(self, jobs_data: list[dict]):
        if not jobs_data:
            logger.warning("没有可入库的职位数据")
            return

        async with AsyncSessionLocal() as session:
            inserted, skipped = 0, 0

            for job in jobs_data:
                # 简单清洗：去除空值字段
                cleaned = {k: v for k, v in job.items() if v}
                if not cleaned.get("source_id") or not cleaned.get("title"):
                    skipped += 1
                    continue

                # ★ 关键改动：先查再插，避免触发 IntegrityError 污染 session
                exists = await session.execute(
                    select(Job.id).where(Job.source_id == cleaned["source_id"])
                )
                if exists.scalar_one_or_none() is not None:
                    skipped += 1
                    continue

                try:
                    session.add(Job(**cleaned))
                    await session.flush()   # 只 flush 不 commit，批量提交
                    inserted += 1
                except Exception as e:
                    # 出错了回滚当前事务，重新开一个
                    await session.rollback()
                    logger.debug(f"插入失败 {cleaned.get('title')}: {e}")
                    skipped += 1

            await session.commit()

        logger.info(f"入库完成: 新增 {inserted} 条, 跳过 {skipped} 条")