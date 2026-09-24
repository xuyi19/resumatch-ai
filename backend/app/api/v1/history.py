from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.db import get_db
from app.core.deps import get_owner_id
from app.models.entities import DiagnosisRecord
from app.utils.report_docx import generate_report_docx

router = APIRouter(prefix="/history", tags=["history"])


def _extract_score(record: DiagnosisRecord) -> int | None:
    """从 result JSON 提取综合分（仅成功记录有值）。"""
    result = record.result or {}
    scores = (result.get("diagnosis") or {}).get("scores") or {}
    overall = scores.get("overall")
    return overall if isinstance(overall, int) else None


@router.get("")
async def list_records(
    limit: int = 20,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    owner_id: str = Depends(get_owner_id),
):
    """分页查询诊断历史（摘要，不含 result；按会话隔离）"""
    stmt = (
        select(DiagnosisRecord)
        .where(DiagnosisRecord.owner_id == owner_id)
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
                "status": r.status,
                "score": _extract_score(r),
                "parent_task_id": r.parent_task_id,
                "created_at": r.created_at.isoformat() if r.created_at else "",
            }
            for r in records
        ],
    }


@router.get("/{task_id}")
async def get_record(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    owner_id: str = Depends(get_owner_id),
):
    """查询单条记录（含完整结果）"""
    result = await db.execute(
        select(DiagnosisRecord).where(
            DiagnosisRecord.task_id == task_id,
            DiagnosisRecord.owner_id == owner_id,
        )
    )
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="记录不存在")

    return {
        "task_id": record.task_id,
        "keyword": record.keyword,
        "resume_name": record.resume_name,
        "resume_id": record.resume_id,
        "status": record.status,
        "score": _extract_score(record),
        "parent_task_id": record.parent_task_id,
        "result": record.result,
        "error": record.error,
        "created_at": record.created_at.isoformat() if record.created_at else "",
    }


@router.delete("/{task_id}")
async def delete_record(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    owner_id: str = Depends(get_owner_id),
):
    """删除某条记录"""
    result = await db.execute(
        select(DiagnosisRecord).where(
            DiagnosisRecord.task_id == task_id,
            DiagnosisRecord.owner_id == owner_id,
        )
    )
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="记录不存在")

    await db.delete(record)
    await db.commit()
    return {"message": "已删除"}


class ExportReportRequest(BaseModel):
    # 桌面形态专用：原生另存为对话框选定的绝对路径，服务端直写。
    # 为空时走浏览器 blob 下载（网页形态主路径）。
    save_path: str | None = None


@router.post("/{task_id}/export-report")
async def export_report(
    task_id: str,
    req: ExportReportRequest | None = None,
    db: AsyncSession = Depends(get_db),
    owner_id: str = Depends(get_owner_id),
):
    """把诊断报告导出为 Word 文档（M20 A2）：评分表格 + 差距 + 建议三段式。

    save_path 为空：浏览器 blob 下载；非空（仅桌面形态）：服务端直写该路径。
    两种方式均落 export_history（template=report）。
    """
    # FastAPI 对 body 可选模型传 None 时 req 可能为 None，统一兜底
    req = req or ExportReportRequest()
    res = await db.execute(
        select(DiagnosisRecord).where(
            DiagnosisRecord.task_id == task_id,
            DiagnosisRecord.owner_id == owner_id,
        )
    )
    record = res.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="记录不存在")
    if record.status != "success" or not record.result:
        raise HTTPException(status_code=409, detail="该任务无完整报告可导出")

    try:
        data = generate_report_docx(record.result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"生成失败: {e}")

    keyword = (record.keyword or "诊断报告").strip()[:40] or "诊断报告"
    filename = f"诊断报告_{keyword}.docx"

    # 复用简历导出的路径校验与导出历史记录（同为 .docx 产物）
    from app.api.v1.resume import _record_export, _validate_save_path

    if req.save_path:
        target = _validate_save_path(req.save_path)
        try:
            target.write_bytes(data)
        except OSError as e:
            raise HTTPException(status_code=500, detail=f"写入文件失败: {e}")
        await _record_export(db, owner_id, target.name, str(target), "report")
        return {"saved_to": str(target), "filename": target.name}

    await _record_export(db, owner_id, filename, None, "report")
    quoted = quote(filename)
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quoted}",
        },
    )
