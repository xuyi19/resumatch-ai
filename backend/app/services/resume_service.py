import asyncio
from pathlib import Path

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.entities import Resume
from app.utils.file_parser import parse_bytes

# 需要保留原文件做浏览器预览的扩展名（pdf 可 iframe 直渲；docx 提供下载）
_STORE_EXTS = {".pdf", ".docx"}


class ResumeService:
    def __init__(self, db: AsyncSession):
        self.db = db

    def _save_original(self, resume_id: int, filename: str, content: bytes) -> str | None:
        """原文件落盘到 FILES_DIR/{resume_id}{ext}，返回路径；不支持的类型返回 None。

        落盘失败不阻塞入库（预览是增强能力，文本已在库中），仅记日志。
        """
        ext = Path(filename).suffix.lower()
        if ext not in _STORE_EXTS:
            return None
        try:
            files_dir = Path(settings.FILES_DIR)
            files_dir.mkdir(parents=True, exist_ok=True)
            target = files_dir / f"{resume_id}{ext}"
            target.write_bytes(content)
            return str(target)
        except OSError as e:
            logger.warning(f"原文件保存失败（不影响入库）: {e}")
            return None

    async def upload_and_parse(self, filename: str, content: bytes, owner_id: str = "local") -> Resume:
        """上传简历 → 解析文本 → 入库（pdf/docx 同时保存原件供预览）"""
        logger.info(f"收到简历上传: {filename}，{len(content)} 字节")

        # PDF/DOCX 解析是 CPU 密集同步操作，放线程池避免阻塞事件循环
        raw_text = await asyncio.to_thread(parse_bytes, content, filename)

        resume = Resume(
            filename=filename,
            raw_text=raw_text,
            owner_id=owner_id,
        )
        self.db.add(resume)
        await self.db.flush()  # 先拿 id，用于原文件命名

        resume.file_path = self._save_original(resume.id, filename, content)

        await self.db.commit()
        await self.db.refresh(resume)

        logger.info(f"简历已入库，id={resume.id}，原文件={'有' if resume.file_path else '无'}")
        return resume

    async def save_text(self, filename: str, text: str, owner_id: str = "local") -> Resume:
        """粘贴文本简历直接入库（A1，跳过文件解析）"""
        resume = Resume(filename=filename, raw_text=text, owner_id=owner_id)
        self.db.add(resume)
        await self.db.commit()
        await self.db.refresh(resume)
        logger.info(f"文本简历已入库，id={resume.id}，{len(text)} 字")
        return resume

    @staticmethod
    def remove_original_file(file_path: str | None) -> None:
        """删除简历对应的原文件（尽力而为，不存在/失败均忽略）"""
        if not file_path:
            return
        try:
            Path(file_path).unlink(missing_ok=True)
        except OSError as e:
            logger.warning(f"原文件删除失败（忽略）: {e}")

    async def get_by_id(self, resume_id: int, owner_id: str = "local") -> Resume | None:
        result = await self.db.execute(
            select(Resume).where(Resume.id == resume_id, Resume.owner_id == owner_id)
        )
        return result.scalar_one_or_none()

    async def find_duplicate(self, text: str, owner_id: str) -> Resume | None:
        """重复上传拦截：同 owner 下完全相同的文本已存在则返回该记录"""
        result = await self.db.execute(
            select(Resume)
            .where(Resume.owner_id == owner_id, Resume.raw_text == text)
            .order_by(Resume.id.desc())
            .limit(1)
        )
        return result.scalars().first()

    async def list_recent(self, limit: int = 20, owner_id: str = "local") -> list[Resume]:
        result = await self.db.execute(
            select(Resume)
            .where(Resume.owner_id == owner_id)
            .order_by(Resume.id.desc())
            .limit(limit)
        )
        return list(result.scalars().all())