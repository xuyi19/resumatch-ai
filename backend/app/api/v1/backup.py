# -*- coding: utf-8 -*-
"""M59 数据备份与恢复：全量 JSON 快照导出 + 合并式导入（恢复 / 换机迁移）。

零 LLM 依赖的纯本地数据操作：
- 导出：当前 owner 的简历 / 简历版本 / 岗位库 / 诊断历史 / 面试与刷题会话 / 导出记录，
  单连接多查询聚合（无 N+1）。不导：SqliteSaver checkpoints（独立 db 文件）、
  photos 目录文件、LLM 配置（Key 不落备份，安全红线）。
- 导入：合并式（不删除、不清空现有数据，全部作为新记录插入，id 重新自增）；
  ResumeVersion.resume_id / DiagnosisRecord.resume_id 经 old_id→new_id 映射重写，
  DiagnosisRecord.task_id 全局唯一、撞车时改写并同步 parent_task_id 溯源链；
  JSON 列与 TEXT 存 JSON 的列（context/chat_log）原样透传，不做二次解析，避免格式漂移。
"""

import json
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from loguru import logger
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import get_owner_id
from app.models.entities import (
    Conversation,
    DiagnosisRecord,
    ExportHistory,
    Resume,
    ResumeVersion,
    SavedJob,
)

router = APIRouter(prefix="/backup", tags=["backup"])

APP_TAG = "ResuMatch-AI"
SCHEMA_VERSION = 1
MAX_IMPORT_BYTES = 50 * 1024 * 1024  # 备份文件体上限 50MB

# conversations 的 type：optimize 对答式优化 / interview 独立面试 / quiz 刷题，
# 三类都是用户数据，统一导出不拆分
_FIELDS = {
    "resumes": ("id", "filename", "raw_text", "file_path", "created_at"),
    "resume_versions": ("id", "resume_id", "content", "source", "created_at"),
    "saved_jobs": (
        "id", "title", "company", "city", "salary", "jd_text", "source",
        "status", "apply_channel", "apply_at", "url", "created_at", "updated_at",
    ),
    "diagnoses": (
        "id", "task_id", "resume_id", "resume_name", "keyword", "city", "status",
        "stage", "progress", "logs", "result", "error", "questions", "clarify_ctx",
        "parent_task_id", "created_at", "updated_at",
    ),
    "conversations": (
        "id", "task_id", "type", "skill", "context", "questions", "answers",
        "current_index", "status", "chat_log", "optimized_resume", "created_at",
        "updated_at",
    ),
    "export_history": ("id", "filename", "save_path", "template", "created_at"),
}
_TABLE_KEYS = tuple(_FIELDS)


def _dump(row, fields: tuple) -> dict:
    """ORM 行 → 导出字典：datetime 全部 isoformat 字符串，其余原样
    （getattr 惯例容错老行缺列，如 SavedJob.url/apply_channel）。"""
    out = {}
    for f in fields:
        v = getattr(row, f, None)
        out[f] = v.isoformat() if isinstance(v, datetime) else v
    return out


def _parse_dt(value):
    """ISO 字符串 → naive datetime；解析失败返回 None（字段留空走服务端默认值）。"""
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        dt = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt.replace(tzinfo=None) if dt.tzinfo else dt


def _with_dt(rec, row: dict, *fields: str) -> None:
    """把备份行里可解析的时间字段写回新记录（解析失败不动，交由默认值）。"""
    for f in fields:
        dt = _parse_dt(row.get(f))
        if dt is not None:
            setattr(rec, f, dt)


@router.get("/export")
async def export_backup(
    db: AsyncSession = Depends(get_db),
    owner_id: str = Depends(get_owner_id),
):
    """导出当前 owner 全量数据 JSON 快照（纯本地聚合，零 LLM 依赖）。"""
    async def _all(model):
        res = await db.execute(
            select(model).where(model.owner_id == owner_id).order_by(model.id)
        )
        return res.scalars().all()

    data = {
        "resumes": [_dump(r, _FIELDS["resumes"]) for r in await _all(Resume)],
        "resume_versions": [_dump(v, _FIELDS["resume_versions"]) for v in await _all(ResumeVersion)],
        "saved_jobs": [_dump(j, _FIELDS["saved_jobs"]) for j in await _all(SavedJob)],
        "diagnoses": [_dump(d, _FIELDS["diagnoses"]) for d in await _all(DiagnosisRecord)],
        "conversations": [_dump(c, _FIELDS["conversations"]) for c in await _all(Conversation)],
        "export_history": [_dump(e, _FIELDS["export_history"]) for e in await _all(ExportHistory)],
    }
    counts = {k: len(v) for k, v in data.items()}
    logger.info(f"备份导出 owner={owner_id[:8]}…: {counts}")
    return {
        "app": APP_TAG,
        "schema_version": SCHEMA_VERSION,
        "exported_at": datetime.now().isoformat(timespec="seconds"),
        "counts": counts,
        "data": data,
    }


@router.post("/import")
async def import_backup(
    request: Request,
    db: AsyncSession = Depends(get_db),
    owner_id: str = Depends(get_owner_id),
):
    """导入备份（合并式恢复/换机迁移）：全部作为新记录插入，id 重新自增，
    父子外键引用经 old→new 映射重写到本库新 id；不覆盖、不删除现有数据。"""
    raw = await request.body()
    if len(raw) > MAX_IMPORT_BYTES:
        raise HTTPException(status_code=422, detail="备份文件过大（超过 50MB）")
    try:
        body = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError):
        raise HTTPException(status_code=422, detail="备份文件不是有效的 JSON")
    if not isinstance(body, dict) or body.get("app") != APP_TAG:
        raise HTTPException(status_code=422, detail="不是知岗备份文件")
    try:
        version = int(body.get("schema_version", SCHEMA_VERSION))
    except (TypeError, ValueError):
        version = SCHEMA_VERSION
    if version > SCHEMA_VERSION:
        raise HTTPException(
            status_code=422,
            detail=f"备份文件版本过高（schema v{version}），请先升级知岗后再导入",
        )

    data = body.get("data")
    if not isinstance(data, dict):
        raise HTTPException(status_code=422, detail="备份文件缺少 data 数据区")
    sections: dict[str, list[dict]] = {}
    for key in _TABLE_KEYS:
        rows = data.get(key) or []
        if not isinstance(rows, list):
            raise HTTPException(status_code=422, detail=f"备份 data.{key} 应为数组")
        sections[key] = [r for r in rows if isinstance(r, dict)]

    try:
        imported = await _merge_insert(db, owner_id, sections)
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.warning(f"备份导入失败 owner={owner_id[:8]}…: {e}")
        raise HTTPException(status_code=422, detail="导入失败：备份文件数据不完整或格式不正确")

    logger.info(f"备份导入完成 owner={owner_id[:8]}…: {imported}")
    return {"imported": imported}


async def _merge_insert(db: AsyncSession, owner_id: str, sections: dict[str, list[dict]]) -> dict:
    """逐表插入并建立 old→new 映射（单事务，父表先插保证可映射）。"""
    # 1) 简历（父表，映射供版本链 / 诊断引用重写）
    resume_map: dict[int, int] = {}
    resume_recs = []
    for r in sections["resumes"]:
        rec = Resume(
            owner_id=owner_id,
            filename=str(r.get("filename") or "").strip()[:255] or "未命名简历",
            raw_text=str(r.get("raw_text") or ""),
            file_path=r.get("file_path") or None,
        )
        _with_dt(rec, r, "created_at")
        db.add(rec)
        resume_recs.append(rec)
    await db.flush()
    for r, rec in zip(sections["resumes"], resume_recs):
        try:
            resume_map[int(r.get("id"))] = rec.id
        except (TypeError, ValueError):
            pass

    def _mapped_resume_id(row: dict):
        try:
            return resume_map[int(row.get("resume_id"))]
        except (KeyError, TypeError, ValueError):
            return None

    # 2) 简历版本链：resume_id 必须映射到新简历，映射不到（异常备份）则跳过防悬空
    n_versions = 0
    for r in sections["resume_versions"]:
        resume_id = _mapped_resume_id(r)
        if resume_id is None:
            continue
        rec = ResumeVersion(
            owner_id=owner_id,
            resume_id=resume_id,
            content=str(r.get("content") or ""),
            source=str(r.get("source") or "initial")[:16],
        )
        _with_dt(rec, r, "created_at")
        db.add(rec)
        n_versions += 1

    # 3) 岗位库（独立表，无父子引用；status/apply_channel/apply_at/url 原样恢复）
    n_jobs = 0
    for r in sections["saved_jobs"]:
        rec = SavedJob(
            owner_id=owner_id,
            title=str(r.get("title") or "").strip()[:80] or "未命名岗位",
            company=str(r.get("company") or ""),
            city=str(r.get("city") or ""),
            salary=str(r.get("salary") or ""),
            jd_text=str(r.get("jd_text") or ""),
            source=str(r.get("source") or "manual")[:16],
            status=str(r.get("status") or "wish")[:16],
            apply_channel=str(r.get("apply_channel"))[:16] if r.get("apply_channel") else None,
            apply_at=_parse_dt(r.get("apply_at")),
            url=str(r.get("url") or ""),
        )
        _with_dt(rec, r, "created_at", "updated_at")
        db.add(rec)
        n_jobs += 1

    # 4) 诊断历史：task_id 全局唯一，与库内或备份内撞车时改写新 id 并同步溯源链
    existing_tids = set((await db.execute(select(DiagnosisRecord.task_id))).scalars().all())
    new_tids: set[str] = set()
    tid_map: dict[str, str] = {}
    n_diags = 0
    for r in sections["diagnoses"]:
        raw_tid = str(r.get("task_id") or "").strip()
        tid = raw_tid or f"bk-{uuid.uuid4().hex[:12]}"
        if tid in existing_tids or tid in new_tids:
            tid = f"{tid[:24]}-{uuid.uuid4().hex[:6]}"
            while tid in existing_tids or tid in new_tids:  # 极小概率连续碰撞
                tid = f"{tid[:24]}-{uuid.uuid4().hex[:6]}"
        new_tids.add(tid)
        if raw_tid:
            tid_map[raw_tid] = tid
        parent = str(r.get("parent_task_id") or "").strip() or None
        if parent:
            # 溯源父诊断不在本次备份内（历史遗留）时保留原值，仅断链不报错
            parent = tid_map.get(parent, parent)
        rec = DiagnosisRecord(
            owner_id=owner_id,
            task_id=tid,
            resume_id=_mapped_resume_id(r),
            resume_name=r.get("resume_name"),
            keyword=str(r.get("keyword") or "").strip()[:64],
            city=r.get("city"),
            status=str(r.get("status") or "finished")[:16],
            stage=r.get("stage"),
            progress=r.get("progress"),
            logs=r.get("logs"),  # JSON 列原样透传，不做二次解析
            result=r.get("result"),
            error=r.get("error"),
            questions=r.get("questions"),
            clarify_ctx=r.get("clarify_ctx"),
            parent_task_id=parent,
        )
        _with_dt(rec, r, "created_at", "updated_at")
        db.add(rec)
        n_diags += 1

    # 5) 面试/刷题/对答优化会话：context/chat_log 为 TEXT 存 JSON 的原样字符串透传
    n_convs = 0
    for r in sections["conversations"]:
        questions = r.get("questions")
        answers = r.get("answers")
        rec = Conversation(
            owner_id=owner_id,
            task_id=str(r.get("task_id") or "").strip()[:32] or f"bk-{uuid.uuid4().hex[:12]}",
            type=str(r.get("type") or "interview")[:16],
            skill=str(r.get("skill"))[:16] if r.get("skill") else None,
            context=r.get("context"),
            questions=questions if isinstance(questions, list) else [],
            answers=answers if isinstance(answers, dict) else {},
            current_index=r.get("current_index") if isinstance(r.get("current_index"), int) else 0,
            status=str(r.get("status") or "finished")[:16],
            chat_log=r.get("chat_log"),
            optimized_resume=r.get("optimized_resume"),
        )
        _with_dt(rec, r, "created_at", "updated_at")
        db.add(rec)
        n_convs += 1

    # 6) 导出历史
    n_exports = 0
    for r in sections["export_history"]:
        rec = ExportHistory(
            owner_id=owner_id,
            filename=str(r.get("filename") or "").strip()[:255] or "未命名导出.docx",
            save_path=r.get("save_path"),
            template=str(r.get("template"))[:32] if r.get("template") else None,
        )
        _with_dt(rec, r, "created_at")
        db.add(rec)
        n_exports += 1
    await db.flush()

    await db.commit()
    return {
        "resumes": len(resume_recs),
        "resume_versions": n_versions,
        "saved_jobs": n_jobs,
        "diagnoses": n_diags,
        "conversations": n_convs,
        "export_history": n_exports,
    }


@router.get("/stats")
async def backup_stats(
    db: AsyncSession = Depends(get_db),
    owner_id: str = Depends(get_owner_id),
):
    """当前 owner 各表条数统计（设置页备份卡展示用）。"""
    counts = {}
    for key, model in (
        ("resumes", Resume),
        ("resume_versions", ResumeVersion),
        ("saved_jobs", SavedJob),
        ("diagnoses", DiagnosisRecord),
        ("conversations", Conversation),  # optimize/interview/quiz 三类合计
        ("export_history", ExportHistory),
    ):
        counts[key] = (
            await db.execute(
                select(func.count()).select_from(model).where(model.owner_id == owner_id)
            )
        ).scalar() or 0
    return counts
