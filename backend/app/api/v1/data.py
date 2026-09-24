# -*- coding: utf-8 -*-
"""数据与隐私（M22 C1）：一键清空本用户的全部诊断数据。"""
import shutil
from pathlib import Path

from fastapi import APIRouter, Depends
from sqlalchemy import bindparam, delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.db import get_db
from app.core.deps import get_owner_id
from app.models.entities import Conversation, DiagnosisRecord, ExportHistory, Resume

router = APIRouter(prefix="/data", tags=["data"])

# SqliteSaver 快照库（thread_id = task_id，按用户任务清空）
CHECKPOINTS_DB = Path(settings.DB_URL.replace("sqlite:///", "").replace("sqlite://", ""))
_CHECKPOINT_TABLES = ("checkpoints", "checkpoint_writes")


@router.delete("")
async def clear_all_data(
    db: AsyncSession = Depends(get_db),
    owner_id: str = Depends(get_owner_id),
):
    """清空当前用户的全部数据：诊断记录 / 简历 / 导出历史 / 会话 / 证件照 / graph 快照。

    二次确认由前端完成；仅 local 模式（owner_id=local）清理共享 photos 目录，
    web 多用户时不删公共目录，避免误删他人文件。
    """
    # 1) 先收集本用户简历原文件路径（删除记录前），DB 记录按 owner 隔离删除
    file_res = await db.execute(
        select(Resume.file_path).where(
            Resume.owner_id == owner_id, Resume.file_path.isnot(None)
        )
    )
    original_files = [fp for (fp,) in file_res.all()]

    counts = {}
    for model in (DiagnosisRecord, Resume, ExportHistory, Conversation):
        res = await db.execute(
            delete(model).where(model.owner_id == owner_id)
        )
        counts[model.__tablename__] = res.rowcount

    # 2) graph 快照：按本用户任务 thread_id 清空 checkpoints
    task_res = await db.execute(
        select(DiagnosisRecord.task_id).where(
            DiagnosisRecord.owner_id == owner_id
        )
    )
    thread_ids = [tid for (tid,) in task_res.all()]
    if thread_ids:
        for table in _CHECKPOINT_TABLES:
            try:
                stmt = text(
                    f"DELETE FROM {table} WHERE thread_id IN :tids"  # noqa: S608
                ).bindparams(bindparam("tids", expanding=True))
                await db.execute(stmt, {"tids": thread_ids})
            except Exception:
                pass  # 表不存在（如未启用快照）时静默跳过

    # 3) 简历原文件：按 file_path 精确删除（local/web 形态均安全，只删自己的）
    files_removed = 0
    for fp in original_files:
        try:
            Path(fp).unlink(missing_ok=True)
            files_removed += 1
        except OSError:
            pass

    # 4) 证件照目录（仅 local 单用户形态清空；web 用户文件不共享目录结构，跳过）
    photos_removed = 0
    if owner_id == "local":
        photos_dir = Path(settings.PHOTOS_DIR)
        if photos_dir.exists():
            for child in photos_dir.iterdir():
                if child.is_file():
                    child.unlink(missing_ok=True)
                    photos_removed += 1
                elif child.is_dir():
                    shutil.rmtree(child, ignore_errors=True)

    await db.commit()
    return {
        "message": "已清空全部数据",
        "deleted": {**counts, "photos": photos_removed, "files": files_removed,
                    "checkpoints": len(thread_ids)},
    }
