from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.models.entities import DiagnosisRecord

router = APIRouter(prefix="/history", tags=["history"])


@router.get("")
async def list_records(
    limit: int = 20,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    """分页查询诊断历史（摘要，不含 result）"""
    stmt = (
        select(DiagnosisRecord)
        .order_by(desc(DiagnosisRecord.id))
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    records = result.scalars().all()

    return {
        "total": len(records),
        "items": [
            {
                "id": r.id,
                "task_id": r.task_id,
                "resume_name": r.resume_name,
                "keyword": r.keyword,
                "city": r.city,
                "status": r.status,
                "created_at": r.created_at.isoformat() if r.created_at else "",
            }
            for r in records
        ],
    }


@router.get("/{task_id}")
async def get_record(task_id: str, db: AsyncSession = Depends(get_db)):
    """查询单条记录（含完整结果）"""
    result = await db.execute(
        select(DiagnosisRecord).where(DiagnosisRecord.task_id == task_id)
    )
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="记录不存在")

    return {
        "task_id": record.task_id,
        "keyword": record.keyword,
        "city": record.city,
        "resume_name": record.resume_name,
        "status": record.status,
        "result": record.result,
        "error": record.error,
        "created_at": record.created_at.isoformat() if record.created_at else "",
    }


@router.delete("/{task_id}")
async def delete_record(task_id: str, db: AsyncSession = Depends(get_db)):
    """删除某条记录"""
    result = await db.execute(
        select(DiagnosisRecord).where(DiagnosisRecord.task_id == task_id)
    )
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="记录不存在")

    await db.delete(record)
    await db.commit()
    return {"message": "已删除"}