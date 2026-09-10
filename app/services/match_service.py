from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.matching.ranker import rank_jobs
from app.models.entities import Job


class MatchService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def recommend(self, resume_text: str, top_k: int = 10,
                        use_semantic: bool = True) -> list:
        result = await self.db.execute(select(Job))
        jobs = list(result.scalars().all())
        logger.info(f"从数据库加载 {len(jobs)} 条职位")
        return rank_jobs(resume_text, jobs, top_k=top_k,
                         use_semantic=use_semantic)