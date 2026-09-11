from loguru import logger
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.matching.ranker import rank_jobs
from app.models.entities import Job


class MatchService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def recommend(
        self,
        resume_text: str,
        top_k: int = 10,
        use_semantic: bool = True,
        keyword_filter: str | None = None,   # ★ 新增
    ) -> list:
        stmt = select(Job)
        if keyword_filter:
            # 标题或描述命中关键词
            kw = f"%{keyword_filter}%"
            stmt = stmt.where(
                or_(Job.title.like(kw), Job.description.like(kw))
            )
        result = await self.db.execute(stmt)
        jobs = list(result.scalars().all())
        logger.info(f"从数据库加载 {len(jobs)} 条职位（筛选：{keyword_filter or '无'}）")
        return rank_jobs(resume_text, jobs, top_k=top_k,
                         use_semantic=use_semantic)