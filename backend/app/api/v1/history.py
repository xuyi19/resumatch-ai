from urllib.parse import quote

from datetime import date, datetime, time, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.db import get_db
from app.core.deps import get_owner_id
from app.models.entities import Conversation, DiagnosisRecord, Offer, Resume, SavedJob
from app.utils.export_paths import resolve_save_path
from app.utils.report_docx import generate_report_docx, generate_weekly_docx

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
    # M51 收藏并入岗位库：工作台「岗位库」统计卡数据源
    saved_jobs_count = await db.scalar(
        select(func.count(SavedJob.id)).where(SavedJob.owner_id == owner_id))
    # M56.4 投递漏斗：岗位库五档状态分布（wish→applied→interviewing→offer→closed）
    funnel_rows = (
        await db.execute(
            select(SavedJob.status, func.count(SavedJob.id))
            .where(SavedJob.owner_id == owner_id)
            .group_by(SavedJob.status)
        )
    ).all()
    status_counts = {s: c for s, c in funnel_rows}
    apply_funnel = {
        k: status_counts.get(k, 0)
        for k in ("wish", "applied", "interviewing", "offer", "closed")
    }
    # M53 活跃热力图：近 90 天每日活跃次数（诊断发起 + 面试会话 + 岗位投递）
    start_day = date.today() - timedelta(days=89)
    heat = {(start_day + timedelta(days=i)).isoformat(): 0 for i in range(90)}
    heat_queries = (
        select(func.date(DiagnosisRecord.created_at), func.count(DiagnosisRecord.id))
        .where(DiagnosisRecord.owner_id == owner_id)
        .group_by(func.date(DiagnosisRecord.created_at)),
        select(func.date(Conversation.created_at), func.count(Conversation.id))
        .where(
            Conversation.owner_id == owner_id,
            Conversation.type == "interview",
        )
        .group_by(func.date(Conversation.created_at)),
        select(func.date(SavedJob.apply_at), func.count(SavedJob.id))
        .where(
            SavedJob.owner_id == owner_id,
            SavedJob.apply_at.is_not(None),
        )
        .group_by(func.date(SavedJob.apply_at)),
    )
    for q in heat_queries:
        for d, c in (await db.execute(q)).all():
            if d and d in heat:
                heat[d] += c
    activity_heatmap = [
        {"date": d, "count": heat[d]} for d in sorted(heat)
    ]

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
        "saved_jobs_count": saved_jobs_count or 0,
        "apply_funnel": apply_funnel,  # M56.4 投递漏斗
        "activity_heatmap": activity_heatmap,  # M53 近 90 天每日活跃
        "diagnosis_total": len(diag_rows),
        "diagnosis_avg_score": round(sum(diag_scores) / len(diag_scores), 1) if diag_scores else None,
        # M38 趋势：最近 10 次有分数的记录，时间正序（折线图数据源）
        "diagnosis_trend": [
            {"score": s, "date": r.created_at.strftime("%m-%d") if r.created_at else ""}
            for r in reversed(diag_rows)
            if (s := _extract_score(r)) is not None
        ][-10:],
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
        "interview_trend": [
            {"score": s, "date": (c.updated_at or c.created_at).strftime("%m-%d")
             if (c.updated_at or c.created_at) else ""}
            for c in reversed(finished)
            if isinstance(c.optimized_resume, dict)
            and (s := c.optimized_resume.get("overall_score")) is not None
        ][-10:],
        "ongoing_interviews": ongoing_ivs,
    }


# ---------- M63 求职周报（零 LLM：确定性聚合 + 模板文案） ----------

# 六个 count 指标（active_days 单独返回，不在此列）
_WEEKLY_METRICS = ("applications", "jobs_added", "interviews", "quizzes", "diagnoses", "offers")

# 亮点模板：按优先级取有内容的最多 4 条（有内容 = 本周值 > 0）
_HIGHLIGHT_TPL = (
    ("applications", "📮 本周投递 {value} 次"),
    ("interviews", "🎤 完成 {value} 场模拟面试"),
    ("quizzes", "🧠 刷题 {value} 场"),
    ("diagnoses", "📄 诊断 {value} 次"),
    ("active_days", "🗓 活跃 {value} 天"),
    ("offers", "🎉 新增 {value} 个 Offer 记录"),
)

_WEEKLY_FALLBACK = "本周还没有记录，从投出一份简历开始吧"


def _triplet(value: int, prev: int) -> dict:
    """单指标环比三元组：本周 / 上周 / 变化（加减差值，不用百分比避免除零）。"""
    return {"value": value, "prev": prev, "delta": value - prev}


def _weekly_highlights(metrics: dict, active_days: dict) -> list[str]:
    pool = {**metrics, "active_days": active_days}
    lines: list[str] = []
    for key, tpl in _HIGHLIGHT_TPL:
        item = pool[key]
        if item["value"] <= 0:
            continue
        line = tpl.format(value=item["value"])
        if item["prev"] > 0:
            # prev=0 时不写环比（上周 0 无对比基准），非 0 带符号；0 差值写持平
            line += "（与上周持平）" if item["delta"] == 0 else f"（环比 {item['delta']:+d}）"
        lines.append(line)
        if len(lines) == 4:
            break
    return lines or [_WEEKLY_FALLBACK]


async def _week_counts(db: AsyncSession, owner_id: str, start: datetime, end: datetime) -> dict:
    """单周窗口聚合：六源计数 + 活跃日期并集（数据源与热力图同构 + 刷题 / Offer）。"""
    applications = await db.scalar(
        select(func.count(SavedJob.id)).where(
            SavedJob.owner_id == owner_id,
            SavedJob.apply_at.is_not(None),
            SavedJob.apply_at >= start,
            SavedJob.apply_at < end,
        )) or 0
    jobs_added = await db.scalar(
        select(func.count(SavedJob.id)).where(
            SavedJob.owner_id == owner_id,
            SavedJob.created_at >= start,
            SavedJob.created_at < end,
        )) or 0
    interviews = await db.scalar(
        select(func.count(Conversation.id)).where(
            Conversation.owner_id == owner_id,
            Conversation.type == "interview",
            Conversation.created_at >= start,
            Conversation.created_at < end,
        )) or 0
    quizzes = await db.scalar(
        select(func.count(Conversation.id)).where(
            Conversation.owner_id == owner_id,
            Conversation.type == "quiz",
            Conversation.created_at >= start,
            Conversation.created_at < end,
        )) or 0
    diagnoses = await db.scalar(
        select(func.count(DiagnosisRecord.id)).where(
            DiagnosisRecord.owner_id == owner_id,
            DiagnosisRecord.created_at >= start,
            DiagnosisRecord.created_at < end,
        )) or 0
    offers = await db.scalar(
        select(func.count(Offer.id)).where(
            Offer.owner_id == owner_id,
            Offer.created_at >= start,
            Offer.created_at < end,
        )) or 0

    # 活跃天数：六源日期并集去重（0~7）
    day_queries = (
        select(func.date(SavedJob.apply_at)).where(
            SavedJob.owner_id == owner_id,
            SavedJob.apply_at.is_not(None),
            SavedJob.apply_at >= start, SavedJob.apply_at < end),
        select(func.date(SavedJob.created_at)).where(
            SavedJob.owner_id == owner_id,
            SavedJob.created_at >= start, SavedJob.created_at < end),
        select(func.date(Conversation.created_at)).where(
            Conversation.owner_id == owner_id,
            Conversation.type.in_(("interview", "quiz")),
            Conversation.created_at >= start, Conversation.created_at < end),
        select(func.date(DiagnosisRecord.created_at)).where(
            DiagnosisRecord.owner_id == owner_id,
            DiagnosisRecord.created_at >= start, DiagnosisRecord.created_at < end),
        select(func.date(Offer.created_at)).where(
            Offer.owner_id == owner_id,
            Offer.created_at >= start, Offer.created_at < end),
    )
    days: set = set()
    for q in day_queries:
        days |= {d for d in (await db.execute(q)).scalars().all() if d}

    return {
        "applications": applications,
        "jobs_added": jobs_added,
        "interviews": interviews,
        "quizzes": quizzes,
        "diagnoses": diagnoses,
        "offers": offers,
        "active_days": len(days),
    }


async def _weekly_aggregate(db: AsyncSession, owner_id: str, week_offset: int) -> dict:
    """周报聚合（weekly-report 与 weekly-export 共用）。

    周窗口：本地时区今天往前推 week_offset 周的那一周，周一 00:00 至下周一 00:00
    （左闭右开）；对比上周同口径算环比。
    """
    today = date.today()
    week_start = today - timedelta(days=today.weekday(), weeks=week_offset)
    start = datetime.combine(week_start, time.min)
    end = start + timedelta(days=7)
    cur = await _week_counts(db, owner_id, start, end)
    prev = await _week_counts(db, owner_id, start - timedelta(days=7), end - timedelta(days=7))
    metrics = {k: _triplet(cur[k], prev[k]) for k in _WEEKLY_METRICS}
    active_days = _triplet(cur["active_days"], prev["active_days"])
    return {
        "week_start": week_start.strftime("%m-%d"),
        "week_end": (week_start + timedelta(days=6)).strftime("%m-%d"),
        "metrics": metrics,
        "active_days": active_days,
        "highlights": _weekly_highlights(metrics, active_days),
    }


@router.get("/weekly-report")
async def weekly_report(
    week_offset: int = Query(0, ge=0, le=8),
    db: AsyncSession = Depends(get_db),
    owner_id: str = Depends(get_owner_id),
):
    """M63 求职周报：本周（week_offset 0）或往前最多 8 周的六源聚合 + 环比 + 模板亮点。

    必须注册在 GET /{task_id} 之前（同 /stats，否则 "weekly-report" 被当 task_id 匹配）。
    """
    return await _weekly_aggregate(db, owner_id, week_offset)


class WeeklyExportRequest(BaseModel):
    week_offset: int = 0
    # 桌面形态专用：非空即触发服务端直写（M71 分类落盘「周报」子目录，路径值不使用）；
    # 为空走浏览器 blob 下载
    save_path: str | None = None


@router.post("/weekly-export")
async def weekly_export(
    req: WeeklyExportRequest,
    db: AsyncSession = Depends(get_db),
    owner_id: str = Depends(get_owner_id),
):
    """M63 周报导出 Word：亮点 + 六指标（本周/上周/变化）表格，零 LLM 确定性模板。

    save_path 为空：浏览器 blob 下载；非空（仅桌面形态）：统一落盘到设置的导出根
    目录「周报」子目录。两种方式均落 export_history（template=weekly）。
    """
    report = await _weekly_aggregate(db, owner_id, req.week_offset)
    try:
        data = generate_weekly_docx(
            report["week_start"], report["week_end"],
            report["highlights"],
            {**report["metrics"], "active_days": report["active_days"]},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"生成失败: {e}")

    filename = f"求职周报_{report['week_start']}_{report['week_end']}.docx"

    # 复用简历导出的历史记录（同为 .docx 产物）
    from app.api.v1.resume import _record_export

    if req.save_path:
        # 桌面形态（M71）：save_path 仅作直写标志，按「导出位置」设置分类落盘
        if settings.APP_MODE == "web":
            raise HTTPException(status_code=403, detail="网页形态不支持服务端落盘")
        target = await resolve_save_path("weekly", filename, db, owner_id)
        try:
            target.write_bytes(data)
        except OSError as e:
            raise HTTPException(status_code=500, detail=f"写入文件失败: {e}")
        await _record_export(db, owner_id, target.name, str(target), "weekly")
        return {"saved_to": str(target), "save_path": str(target), "filename": target.name}

    await _record_export(db, owner_id, filename, None, "weekly")
    quoted = quote(filename)
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quoted}",
        },
    )


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
    # 桌面形态专用：非空即触发服务端直写（M71 起统一写入设置的导出根目录并按类型
    # 分类落盘，本字段的路径值不再使用）；为空时走浏览器 blob 下载。
    save_path: str | None = None


@router.post("/{task_id}/export-report")
async def export_report(
    task_id: str,
    req: ExportReportRequest | None = None,
    db: AsyncSession = Depends(get_db),
    owner_id: str = Depends(get_owner_id),
):
    """把诊断报告导出为 Word 文档（M20 A2）：评分表格 + 差距 + 建议三段式。

    save_path 为空：浏览器 blob 下载；非空（仅桌面形态）：M71 统一落盘到设置的
    导出根目录「诊断报告」子目录。两种方式均落 export_history（template=report）。
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

    # 复用简历导出的历史记录（同为 .docx 产物）
    from app.api.v1.resume import _record_export

    if req.save_path:
        # 桌面形态（M71）：save_path 仅作直写标志，按「导出位置」设置分类落盘
        if settings.APP_MODE == "web":
            raise HTTPException(status_code=403, detail="网页形态不支持服务端落盘")
        target = await resolve_save_path("report", filename, db, owner_id)
        try:
            target.write_bytes(data)
        except OSError as e:
            raise HTTPException(status_code=500, detail=f"写入文件失败: {e}")
        await _record_export(db, owner_id, target.name, str(target), "report")
        return {"saved_to": str(target), "save_path": str(target), "filename": target.name}

    await _record_export(db, owner_id, filename, None, "report")
    quoted = quote(filename)
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quoted}",
        },
    )
