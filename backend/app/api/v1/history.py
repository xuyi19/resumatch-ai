from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.db import get_db
from app.core.deps import get_owner_id
from app.models.entities import Conversation, DiagnosisRecord, Resume
from app.utils.report_docx import generate_report_docx

router = APIRouter(prefix="/history", tags=["history"])

_ONGOING = ("pending", "running", "waiting_clarify")


def _extract_score(record: DiagnosisRecord) -> int | None:
    """从 result JSON 提取综合分（仅成功记录有值）。"""
    result = record.result or {}
    scores = (result.get("diagnosis") or {}).get("scores") or {}
    overall = scores.get("overall")
    return overall if isinstance(overall, int) else None


@router.get("/stats")
async def history_stats(
    db: AsyncSession = Depends(get_db),
    owner_id: str = Depends(get_owner_id),
):
    """M36 工作台仪表盘：一端点聚合简历 / 诊断 / 面试统计。

    注意：必须注册在 GET /{task_id} 之前，否则 "stats" 会被当 task_id 匹配。
    """
    resume_count = await db.scalar(
        select(func.count(Resume.id)).where(Resume.owner_id == owner_id))

    diag_rows = (
        await db.execute(
            select(DiagnosisRecord)
            .where(DiagnosisRecord.owner_id == owner_id)
            .order_by(desc(DiagnosisRecord.id))
            .limit(200)
        )
    ).scalars().all()
    diag_scores = [s for r in diag_rows if (s := _extract_score(r)) is not None]
    latest_diag = diag_rows[0] if diag_rows else None
    ongoing_diags = [
        {"task_id": r.task_id, "keyword": r.keyword, "status": r.status,
         "resume_name": r.resume_name, "created_at": r.created_at.isoformat() if r.created_at else ""}
        for r in diag_rows if r.status in _ONGOING
    ][:5]

    interview_total = await db.scalar(
        select(func.count(Conversation.id)).where(
            Conversation.owner_id == owner_id, Conversation.type == "interview"))
    conv_rows = (
        await db.execute(
            select(Conversation)
            .where(Conversation.owner_id == owner_id, Conversation.type == "interview")
            .order_by(desc(Conversation.id))
            .limit(50)
        )
    ).scalars().all()
    finished = [c for c in conv_rows if c.optimized_resume]
    iv_scores = [
        s for c in finished
        if isinstance(c.optimized_resume, dict)
        and (s := c.optimized_resume.get("overall_score")) is not None
    ]
    latest_iv = next((c for c in conv_rows if c.optimized_resume), None)
    latest_iv_score = (
        latest_iv.optimized_resume.get("overall_score")
        if latest_iv and isinstance(latest_iv.optimized_resume, dict) else None)
    ongoing_ivs = [
        {"task_id": c.task_id,
         "answered": len(c.answers or {}),
         "total": len(c.questions or [])}
        # M37：一题未答的空会话不进「继续进行」（多为误建/废弃会话，只会添噪）
        for c in conv_rows if c.status == "ongoing" and (c.answers or {})
    ][:5]

    return {
        "resume_count": resume_count or 0,
        "diagnosis_total": len(diag_rows),
        "diagnosis_avg_score": round(sum(diag_scores) / len(diag_scores), 1) if diag_scores else None,
        "latest_diagnosis": (
            {"task_id": latest_diag.task_id, "keyword": latest_diag.keyword,
             "score": _extract_score(latest_diag),
             "created_at": latest_diag.created_at.isoformat() if latest_diag.created_at else ""}
            if latest_diag else None),
        "ongoing_diagnoses": ongoing_diags,
        "interview_total": interview_total or 0,
        "interview_finished": len(finished),
        "interview_avg_score": round(sum(iv_scores) / len(iv_scores), 1) if iv_scores else None,
        "latest_interview_score": latest_iv_score,
        "ongoing_interviews": ongoing_ivs,
    }


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
