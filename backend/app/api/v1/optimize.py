from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.graph import clarifier_graph, optimize_graph
from app.core.db import get_db
from app.models.entities import DiagnosisRecord, Resume

router = APIRouter(prefix="/optimize", tags=["optimize"])


class LLMConfig(BaseModel):
    api_key: str | None = None
    base_url: str | None = None
    model: str | None = None


class GenerateRequest(BaseModel):
    answers: dict = {}
    llm_config: LLMConfig | None = None
    skip_clarify: bool = False


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


async def _build_state(db: AsyncSession, record: DiagnosisRecord) -> dict:
    data = record.result or {}
    diagnosis = data.get("diagnosis", {})
    target = data.get("diagnosis_target", {})

    resume = await db.get(Resume, record.resume_id) if record.resume_id else None
    resume_text = resume.raw_text if resume else _rebuild(diagnosis)

    jd_text = f"""岗位：{target.get('title', '')}
公司：{target.get('company', '')}
城市：{target.get('city', '')}"""

    return {
        "resume_text": resume_text,
        "jd_text": jd_text,
        "parsed": diagnosis.get("parsed", {}),
        "scores": diagnosis.get("scores", {}),
        "gaps": diagnosis.get("gaps", []),
        "suggestions": diagnosis.get("suggestions", []),
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


# ============ 1. 生成追问 ============
@router.post("/{task_id}/questions")
async def get_questions(
    task_id: str,
    llm_config: LLMConfig | None = None,
    db: AsyncSession = Depends(get_db),
):
    """生成 AI 追问列表"""
    record = await _load_record(db, task_id)
    state = await _build_state(db, record)
    state["llm_config"] = llm_config.model_dump() if llm_config else {}

    final = await clarifier_graph.ainvoke(state)
    questions = final.get("clarify_questions", [])

    if not questions:
        raise HTTPException(status_code=500, detail=final.get("error") or "生成追问失败")

    return {"questions": questions}


# ============ 2. 提交答案 + 生成简历 ============
@router.post("/{task_id}/generate")
async def generate_resume(
    task_id: str,
    req: GenerateRequest,
    db: AsyncSession = Depends(get_db),
):
    """用户提交答案后生成优化简历"""
    record = await _load_record(db, task_id)
    state = await _build_state(db, record)
    state["llm_config"] = req.llm_config.model_dump() if req.llm_config else {}
    state["user_answers"] = req.answers

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


# ============ 3. 快速生成（不追问）============
@router.post("/{task_id}")
async def quick_optimize(
    task_id: str,
    llm_config: LLMConfig | None = None,
    db: AsyncSession = Depends(get_db),
):
    """一键生成，不追问"""
    req = GenerateRequest(answers={}, llm_config=llm_config, skip_clarify=True)
    return await generate_resume(task_id, req, db)