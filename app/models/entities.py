from datetime import datetime

from sqlalchemy import DateTime, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class Job(Base):
    """岗位表：存爬取的 JD"""
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(32), index=True)          # boss / zhilian
    source_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(128), index=True)
    company: Mapped[str] = mapped_column(String(128), index=True)
    city: Mapped[str] = mapped_column(String(32), index=True)
    salary: Mapped[str | None] = mapped_column(String(64), nullable=True)
    experience: Mapped[str | None] = mapped_column(String(32), nullable=True)
    education: Mapped[str | None] = mapped_column(String(32), nullable=True)
    tags: Mapped[list] = mapped_column(JSON, default=list)               # 技能标签
    description: Mapped[str] = mapped_column(Text)                       # JD 全文
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )


class Resume(Base):
    """简历表：存上传的简历和解析结果"""
    __tablename__ = "resumes"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    filename: Mapped[str] = mapped_column(String(255))
    raw_text: Mapped[str] = mapped_column(Text)                          # 原始文本
    parsed: Mapped[dict] = mapped_column(JSON, default=dict)             # 结构化解析结果
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )