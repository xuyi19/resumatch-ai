from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.graph import optimize_graph
from app.core.db import get_db
from app.models.entities import DiagnosisRecord, Resume

router = APIRouter(prefix="/optimize", tags=["optimize"])


class LLMConfig(BaseModel):
    api_key: str | None = None
    base_url: str | None = None
    model: str | None = None


class OptimizeRequest(BaseModel):
    answers: dict = {}
    llm_config: LLMConfig | None = None


async def _load_record(db: AsyncSession, task_id: str) -> DiagnosisRecord:
    result = await db.execute(
        select(DiagnosisRecord).where(DiagnosisRecord.task_id == task_id)
    )
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="诊断记录不存在")
    if record.status != "success":
        raise HTTPException(status_code=400, detail="诊断尚未完成")
    return record


async def _build_state(db: AsyncSession, record: DiagnosisRecord, llm_config) -> dict:
    data = record.result or {}
    diagnosis = data.get("diagnosis", {})
    target = data.get("diagnosis_target", {})

    resume = await db.get(Resume, record.resume_id) if record.resume_id else None
    resume_text = resume.raw_text if resume else _rebuild(diagnosis)

    # 优先用诊断阶段持久化的完整 JD；旧记录无此字段时回退到标题拼接
    jd_text = data.get("jd_text") or (
        f"岗位：{target.get('title', '')}\n"
        f"公司：{target.get('company', '')}\n"
        f"城市：{target.get('city', '')}"
    )

    return {
        "resume_text": resume_text,
        "jd_text": jd_text,
        "parsed": diagnosis.get("parsed", {}),
        "job_analysis": diagnosis.get("job_analysis", {}),
        "scores": diagnosis.get("scores", {}),
        "gaps": diagnosis.get("gaps", []),
        "suggestions": diagnosis.get("suggestions", []),
        "user_answers": {},
        "llm_config": llm_config or {},
        "messages": [],
    }


def _rebuild(diagnosis: dict) -> str:
    parsed = diagnosis.get("parsed", {})
    lines = []
    if parsed.get("summary"):
        lines.append(parsed["summary"])
    for key in ("education", "experience", "projects"):
        lines.extend(parsed.get(key, []))
    if parsed.get("skills"):
        lines.append("技能：" + ", ".join(parsed["skills"]))
    return "\n".join(lines)


def _qa_context(answers: dict) -> str:
    if not answers:
        return ""
    return "\n\n".join(f"Q: {q}\nA: {a}" for q, a in answers.items())


@router.post("/{task_id}")
async def optimize_resume(
    task_id: str,
    req: OptimizeRequest,
    db: AsyncSession = Depends(get_db),
):
    """基于诊断结果（可选携带用户补充回答）生成优化简历"""
    record = await _load_record(db, task_id)
    state = await _build_state(db, record, req.llm_config)
    state["user_answers"] = {"qa_context": _qa_context(req.answers)}

    final = await optimize_graph.ainvoke(state)
    optimized = final.get("optimized_resume", {})

    if not optimized:
        raise HTTPException(status_code=500, detail=final.get("error") or "优化失败")

    # 落库
    data = record.result or {}
    if "diagnosis" not in data:
        data["diagnosis"] = {}
    data["diagnosis"]["optimized_resume"] = optimized
    record.result = data
    await db.commit()

    return {"optimized_resume": optimized}
