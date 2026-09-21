from datetime import datetime

from sqlalchemy import DateTime, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class Resume(Base):
    __tablename__ = "resumes"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    filename: Mapped[str] = mapped_column(String(255))
    raw_text: Mapped[str] = mapped_column(Text)
    owner_id: Mapped[str] = mapped_column(String(64), default="local", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class DiagnosisRecord(Base):
    __tablename__ = "diagnosis_records"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    task_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    resume_id: Mapped[int | None] = mapped_column(nullable=True)
    resume_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    keyword: Mapped[str] = mapped_column(String(64), index=True)
    city: Mapped[str | None] = mapped_column(String(32), nullable=True)
    owner_id: Mapped[str] = mapped_column(String(64), default="local", index=True)
    status: Mapped[str] = mapped_column(String(16), default="running")
    # 进度快照（M6）：节流写入，服务重启后 /live/status 可回退 DB 读取
    stage: Mapped[str | None] = mapped_column(String(32), nullable=True)
    progress: Mapped[int | None] = mapped_column(nullable=True)
    logs: Mapped[list | None] = mapped_column(JSON, nullable=True)
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    # M16 跨重启恢复：waiting_clarify 任务的追问问题与恢复上下文落库
    questions: Mapped[list | None] = mapped_column(JSON, nullable=True)
    clarify_ctx: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class ExportHistory(Base):
    """导出历史：Word 导出动作记录（桌面形态含用户选择的保存路径，可再次定位文件）"""
    __tablename__ = "export_history"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    owner_id: Mapped[str] = mapped_column(String(64), default="local", index=True)
    filename: Mapped[str] = mapped_column(String(255))
    save_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    template: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Conversation(Base):
    """对话历史表：对答式优化 + 模拟面试共用"""
    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    task_id: Mapped[str] = mapped_column(String(32), index=True)
    type: Mapped[str] = mapped_column(String(16), index=True)         # optimize / interview
    owner_id: Mapped[str] = mapped_column(String(64), default="local", index=True)
    skill: Mapped[str | None] = mapped_column(String(16), nullable=True)
    questions: Mapped[list] = mapped_column(JSON, default=list)
    answers: Mapped[dict] = mapped_column(JSON, default=dict)
    current_index: Mapped[int] = mapped_column(default=0)
    status: Mapped[str] = mapped_column(String(16), default="ongoing")  # ongoing / finished
    optimized_resume: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
