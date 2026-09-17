import asyncio

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import Resume
from app.utils.file_parser import parse_bytes


class ResumeService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def upload_and_parse(self, filename: str, content: bytes) -> Resume:
        """上传简历 → 解析文本 → 入库"""
        logger.info(f"收到简历上传: {filename}，{len(content)} 字节")

        # PDF/DOCX 解析是 CPU 密集同步操作，放线程池避免阻塞事件循环
        raw_text = await asyncio.to_thread(parse_bytes, content, filename)

        resume = Resume(
            filename=filename,
            raw_text=raw_text,
        )
        self.db.add(resume)
        await self.db.commit()
        await self.db.refresh(resume)

        logger.info(f"简历已入库，id={resume.id}")
        return resume

    async def get_by_id(self, resume_id: int) -> Resume | None:
        result = await self.db.execute(
            select(Resume).where(Resume.id == resume_id)
        )
        return result.scalar_one_or_none()

    async def list_recent(self, limit: int = 20) -> list[Resume]:
        result = await self.db.execute(
            select(Resume).order_by(Resume.id.desc()).limit(limit)
        )
        return list(result.scalars().all())