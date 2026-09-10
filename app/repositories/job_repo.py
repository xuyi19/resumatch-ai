from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import Job


class JobRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def count(self) -> int:
        result = await self.db.execute(select(func.count()).select_from(Job))
        return result.scalar_one()

    async def list_all(self, limit: int = 20, offset: int = 0) -> list[Job]:
        result = await self.db.execute(
            select(Job).order_by(Job.id.desc()).limit(limit).offset(offset)
        )
        return list(result.scalars().all())

    async def create(self, **kwargs) -> Job:
        job = Job(**kwargs)
        self.db.add(job)
        await self.db.commit()
        await self.db.refresh(job)
        return job