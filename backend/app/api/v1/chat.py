from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.graph import optimize_graph
from app.agents.nodes.interactive_opt_agent import generate_questions
from app.core.db import get_db
from app.models.entities import Conversation, DiagnosisRecord, Resume

router = APIRouter(prefix="/chat", tags=["chat"])


class LLMConfig(BaseModel):
    api_key: str | None = None
    base_url: str | None = None
    model: str | None = None


class StartRequest(BaseModel):
    llm_config: LLMConfig | None = None


class ReplyRequest(BaseModel):
    question_id: str
    answer: str


class FinishRequest(BaseModel):
    llm_config: LLMConfig | None = None


async def _load_context(task_id: str, db: AsyncSession):
    rec_res = await db.execute(
        select(DiagnosisRecord).where(DiagnosisRecord.task_id == task_id)
    )
    record = rec_res.scalar_one_or_none()
    if not record:
        raise HTTPException(404, "诊断记录不存在")
    if record.status != "success":
        raise HTTPException(400, "诊断尚未完成")

    resume = await db.get(Resume, record.resume_id) if record.resume_id else None
    resume_text = resume.raw_text if resume else ""

    data = record.result or {}
    diagnosis = data.get("diagnosis", {})
    target = data.get("diagnosis_target", {})
    # 优先用诊断阶段持久化的完整 JD；旧记录无此字段时回退到标题拼接
    jd_text = data.get("jd_text") or (
        f"岗位：{target.get('title', '')}\n公司：{target.get('company', '')}"
    )

    return record, resume_text, jd_text, diagnosis


@router.post("/start/{task_id}")
async def start_chat(
    task_id: str,
    req: StartRequest,
    db: AsyncSession = Depends(get_db),
):
    record, resume_text, jd_text, diagnosis = await _load_context(task_id, db)

    existing = await db.execute(
        select(Conversation).where(
            Conversation.task_id == task_id,
            Conversation.type == "optimize",
        )
    )
    conv = existing.scalar_one_or_none()

    llm_config = req.llm_config.model_dump() if req.llm_config else None

    if not conv:
        gaps = [g for g in diagnosis.get("gaps", []) if not g.get("summary")]
        try:
            questions = await generate_questions(resume_text, jd_text, gaps, llm_config)
        except Exception as e:
            logger.exception("生成问题失败")
            raise HTTPException(500, f"生成问题失败: {e}")

        if not questions:
            raise HTTPException(500, "生成问题为空")

        conv = Conversation(
            task_id=task_id,
            type="optimize",
            questions=questions,
            answers={},
            current_index=0,
            status="ongoing",
        )
        db.add(conv)
        await db.commit()
        await db.refresh(conv)

    idx = conv.current_index
    if idx >= len(conv.questions):
        return {
            "status": "finished",
            "message": "所有问题已答完",
            "questions_total": len(conv.questions),
        }

    return {
        "status": "ongoing",
        "conversation_id": conv.id,
        "current_index": idx,
        "total": len(conv.questions),
        "question": conv.questions[idx],
    }


@router.post("/reply/{task_id}")
async def reply_chat(
    task_id: str,
    req: ReplyRequest,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Conversation).where(
            Conversation.task_id == task_id,
            Conversation.type == "optimize",
        )
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(404, "对话不存在，请先开始")

    answers = dict(conv.answers or {})
    answers[req.question_id] = req.answer
    conv.answers = answers
    conv.current_index += 1

    if conv.current_index >= len(conv.questions):
        conv.status = "finished"
        await db.commit()
        return {
            "status": "finished",
            "message": "所有问题已答完",
            "total": len(conv.questions),
        }

    await db.commit()
    return {
        "status": "ongoing",
        "current_index": conv.current_index,
        "total": len(conv.questions),
        "question": conv.questions[conv.current_index],
    }


@router.post("/finish/{task_id}")
async def finish_chat(
    task_id: str,
    req: FinishRequest,
    db: AsyncSession = Depends(get_db),
):
    record, resume_text, jd_text, diagnosis = await _load_context(task_id, db)

    result = await db.execute(
        select(Conversation).where(
            Conversation.task_id == task_id,
            Conversation.type == "optimize",
        )
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(404, "对话不存在")

    qa_context = "\n\n".join([
        f"Q: {q['question']}\nA: {conv.answers.get(q['id'], '（未回答）')}"
        for q in conv.questions
    ])

    llm_config = req.llm_config.model_dump() if req.llm_config else None

    state = {
        "resume_text": resume_text,
        "jd_text": jd_text,
        "parsed": diagnosis.get("parsed", {}),
        "job_analysis": diagnosis.get("job_analysis", {}),
        "scores": diagnosis.get("scores", {}),
        "gaps": diagnosis.get("gaps", []),
        "suggestions": diagnosis.get("suggestions", []),
        "user_answers": {"qa_context": qa_context},
        "llm_config": llm_config or {},
        "messages": [],
    }

    try:
        final = await optimize_graph.ainvoke(state)
    except Exception as e:
        logger.exception("生成优化简历失败")
        raise HTTPException(500, f"生成失败: {e}")

    optimized = final.get("optimized_resume", {})
    if not optimized:
        raise HTTPException(500, final.get("error") or "生成失败")

    conv.optimized_resume = optimized
    conv.status = "finished"
    await db.commit()

    data = record.result or {}
    data.setdefault("diagnosis", {})["optimized_resume"] = optimized
    record.result = data
    await db.commit()

    diff = _build_diff(diagnosis.get("parsed", {}), optimized)

    return {"optimized_resume": optimized, "diff": diff}


@router.get("/history/{task_id}")
async def get_chat_history(task_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Conversation).where(
            Conversation.task_id == task_id,
            Conversation.type == "optimize",
        )
    )
    conv = result.scalar_one_or_none()
    if not conv:
        return {"exists": False}

    return {
        "exists": True,
        "questions": conv.questions,
        "answers": conv.answers,
        "current_index": conv.current_index,
        "status": conv.status,
        "optimized_resume": conv.optimized_resume,
    }


def _build_diff(original: dict, optimized: dict) -> dict:
    def join_lines(lst):
        if not lst:
            return ""
        return "\n".join(str(x) for x in lst)

    return {
        "summary": {
            "original": original.get("summary", ""),
            "optimized": optimized.get("summary", ""),
        },
        "experience": {
            "original": join_lines(original.get("experience", [])),
            "optimized": join_lines(optimized.get("experience", [])),
        },
        "projects": {
            "original": join_lines(original.get("projects", [])),
            "optimized": join_lines(optimized.get("projects", [])),
        },
        "skills": {
            "original": ", ".join(original.get("skills", [])),
            "optimized": ", ".join(optimized.get("skills", [])),
        },
    }