# -*- coding: utf-8 -*-
"""M23 面试功能：面试准备（AI 生成题单）+ 模拟面试（AI 面试官多轮自由对话）。

复用 Conversation 表（type="interview"，M17 设计时预留）：
questions 存题单，answers 存 {qid: {answer, feedback}}（advance 收尾时落），
optimized_resume 复用为总评，chat_log（M32）存完整对话流 JSON 文本。

M31 独立面试：两种会话来源——
- 诊断内嵌：task_id 即诊断任务 id，上下文取 DiagnosisRecord（简历/JD/诊断差距）
- 独立会话：task_id 为生成的 `iv-` 前缀 id，上下文（resume_id/jd_text）存 Conversation.context

M32 多轮自由对话：/interview/chat 让候选人围绕当前题随时发言，面试官自然回应
（可追问/可补充），LLM 判断 advance 收尾进下一题，末题出总评。
M33 报告导出：/interview/export 把问答记录 + 总评导出 Word（复用诊断报告导出模式）。
"""
import json
import uuid
from datetime import datetime
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Response
from loguru import logger
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.utils import call_llm_for_json
from app.core.db import get_db
from app.core.deps import get_owner_id
from app.models.entities import Conversation, DiagnosisRecord, Resume
from app.utils.report_docx import generate_interview_docx

router = APIRouter(prefix="/interview", tags=["interview"])


class LLMConfig(BaseModel):
    api_key: str | None = None
    base_url: str | None = None
    model: str | None = None


class ChatMessage(BaseModel):
    """M32 多轮自由对话：候选人在当前题内随时发言，面试官自然回应。"""

    content: str = Field(min_length=1, max_length=4000, description="候选人发言")
    # 「结束本题/跳过」按钮用：prompt 加强制收尾标注，确保 advance=true
    force_advance: bool = Field(default=False, description="候选人已表示回答完毕或跳过")
    # 与 start/start-free 一致：回应/总评也透传用户 LLM 配置
    llm_config: dict | None = Field(default=None, description="用户 LLM 配置；空则用服务端默认")


class FreeStartRequest(BaseModel):
    """M31 独立面试启动：用户选简历 + 粘贴意向岗位 JD，无需先跑诊断。"""

    resume_id: int = Field(description="简历库中的简历 id")
    jd_text: str = Field(min_length=20, max_length=6000, description="意向岗位 JD")
    # 必须允许 None：前端未配置 Key 时显式传 null（dict 严格类型会 422 拒掉整个请求）
    llm_config: dict | None = Field(default=None, description="用户 LLM 配置；空则用服务端默认")


# ---------------- Pydantic 模型 ----------------

class InterviewQuestion(BaseModel):
    id: str = Field(description="问题编号 q1..q6")
    category: str = Field(description="分类：技术基础/项目深挖/情景行为/岗位匹配")
    question: str = Field(description="面试官提问")
    focus: str = Field(default="", description="考察点")
    hint: str = Field(default="", description="回答思路提示")


class InterviewPlan(BaseModel):
    questions: list[InterviewQuestion] = Field(default_factory=list)


class ChatTurn(BaseModel):
    """M32 面试官一轮回应：reply 为面试官发言，advance 标记本题是否收尾。"""

    reply: str = Field(description="面试官回应（1-3 句，口吻自然，可追问可点评）")
    advance: bool = Field(default=False, description="本题回答是否充分，true 进入下一题")


class InterviewSummary(BaseModel):
    overall: str = Field(description="整体表现总评（3-4 句）")
    strengths: list[str] = Field(default_factory=list, description="亮点")
    weaknesses: list[str] = Field(default_factory=list, description="待改进")
    suggestions: list[str] = Field(default_factory=list, description="针对性建议")


PLAN_PROMPT = """你是一位资深技术面试官。基于候选人简历、目标岗位 JD 与诊断出的差距，生成 6 道面试题。

## 简历
{resume_text}

## 目标 JD
{jd_text}

## 诊断差距（重点考察）
{gaps}

## 出题要求
1. 覆盖四类：技术基础 2 题、项目深挖 2 题、岗位匹配 1 题、情景行为 1 题
2. 题目具体（结合简历中真实项目/技能与 JD 要求），禁止泛泛的"介绍一下自己"
3. 每题给考察点 focus 与回答思路 hint
4. id 依次 q1..q6

## 输出 JSON
{{
  "questions": [
    {{
      "id": "q1", "category": "技术基础",
      "question": "简历提到使用 Redis 缓存，讲一下缓存穿透、击穿、雪崩的区别与应对方案？",
      "focus": "缓存中间件原理深度",
      "hint": "从三者定义、发生场景、常用解决方案（布隆过滤器/互斥锁/过期时间打散）作答"
    }}
  ]
}}
"""

CHAT_PROMPT = """你是一位资深技术面试官，正在对候选人进行模拟面试，采用真实面试的多轮对话方式。

## 简历
{resume_text}

## 目标 JD
{jd_text}

## 题目列表（共 {total} 题，当前第 {idx} 题 · {category}）
{questions}

当前题目：{question}
考察点：{focus}
回答思路（仅作你内部参考，不要直接念给候选人）：{hint}

## 对话记录（本场面试的完整往来）
{chat_history}

## 候选人最新发言
{content}

## 回应要求
- reply：用面试官口吻自然回应，1-3 句。可肯定亮点、追问细节、指出需要补充之处；禁止一次性灌输完整标准答案
- advance 判断本题是否可以结束：
  - true：回答已基本覆盖考察点、或候选人明确表示答完/不会/跳过、或已来回多轮无新增信息。此时 reply 先给一句简短收尾点评
  - false：还需要继续交流（追问或等待候选人补充）
- 若下方标注了强制收尾，必须 advance=true

## 输出 JSON
{{"reply": "...", "advance": false}}
"""

SUMMARY_PROMPT = """你是一位资深技术面试官，模拟面试结束，请给出总评。

## 简历
{resume_text}

## 目标 JD
{jd_text}

## 完整问答记录
{history}

## 要求
- overall：3-4 句整体评价（含与岗位匹配度的判断）
- strengths/weaknesses：各 2-3 条，具体到回答内容
- suggestions：2-3 条可执行的面试准备建议

## 输出 JSON
{{"overall": "...", "strengths": ["..."], "weaknesses": ["..."], "suggestions": ["..."]}}
"""


async def _load_context(task_id: str, db: AsyncSession, owner_id: str):
    """加载面试上下文（简历全文 / JD / 差距）。

    优先按诊断任务（DiagnosisRecord）取；无诊断记录时按独立会话处理，
    从 Conversation.context JSON 读取 resume_id/jd_text（M31）。
    返回 (rec_or_None, resume_text, jd_text, diagnosis_dict)。
    """
    rec = (
        await db.execute(
            select(DiagnosisRecord).where(
                DiagnosisRecord.task_id == task_id,
                DiagnosisRecord.owner_id == owner_id,
            )
        )
    ).scalar_one_or_none()

    if rec:
        if rec.status != "success":
            raise HTTPException(400, "诊断尚未完成，无法开始面试")
        resume = await db.get(Resume, rec.resume_id) if rec.resume_id else None
        resume_text = resume.raw_text if resume else ""
        data = rec.result or {}
        jd_text = data.get("jd_text", "")
        diagnosis = data.get("diagnosis", {})
        if not jd_text:
            target = data.get("diagnosis_target", {})
            jd_text = f"岗位:{target.get('title', '')} 公司:{target.get('company', '')}"
        return rec, resume_text, jd_text, diagnosis

    # ---- 独立会话（M31）：上下文存在 Conversation.context ----
    conv = (
        await db.execute(
            select(Conversation).where(
                Conversation.task_id == task_id,
                Conversation.owner_id == owner_id,
                Conversation.type == "interview",
            )
        )
    ).scalar_one_or_none()
    if not conv or not conv.context:
        raise HTTPException(404, "面试会话不存在")
    try:
        ctx = json.loads(conv.context)
    except (ValueError, TypeError) as e:
        raise HTTPException(500, "面试会话上下文损坏") from e
    resume = await db.get(Resume, ctx.get("resume_id")) if ctx.get("resume_id") else None
    if not resume:
        raise HTTPException(404, "面试关联的简历已不存在，请重新发起")
    return None, resume.raw_text, ctx.get("jd_text", ""), {}


async def _get_or_create_conv(db: AsyncSession, task_id: str, owner_id: str) -> Conversation:
    return (
        await db.execute(
            select(Conversation).where(
                Conversation.task_id == task_id,
                Conversation.owner_id == owner_id,
                Conversation.type == "interview",
            )
        )
    ).scalar_one_or_none()


async def _ensure_plan(db: AsyncSession, conv: Conversation, resume_text: str,
                       jd_text: str, gaps: list, llm_cfg: dict | None) -> Conversation:
    """已有题单直接返回；否则生成并落库（两种启动方式共用）。"""
    if conv.questions:
        return conv

    gap_lines = "\n".join(f"- {g.get('dimension', '')}: {g.get('summary', '')}" for g in gaps) or "无"
    try:
        plan = await call_llm_for_json(
            PLAN_PROMPT.format(resume_text=resume_text[:4000], jd_text=jd_text[:2500],
                               gaps=gap_lines),
            InterviewPlan, temperature=0.5, llm_config=llm_cfg,
        )
    except Exception as e:
        logger.exception("生成面试题失败")
        raise HTTPException(500, f"生成面试题失败: {e}")

    if not plan.questions:
        raise HTTPException(500, "生成的面试题为空，请重试")

    conv.questions = [q.model_dump() for q in plan.questions]
    conv.answers = {}
    conv.current_index = 0
    conv.status = "ongoing"
    await db.commit()
    await db.refresh(conv)
    return conv


@router.post("/start/{task_id}")
async def start_interview(
    task_id: str,
    req: dict | None = None,
    db: AsyncSession = Depends(get_db),
    owner_id: str = Depends(get_owner_id),
):
    """生成面试题单（诊断内嵌 + 独立会话共用）。已有题单直接返回；regenerate=True 强制重出。"""
    llm_cfg = (req or {}).get("llm_config")
    regenerate = bool((req or {}).get("regenerate"))
    rec, resume_text, jd_text, diagnosis = await _load_context(task_id, db, owner_id)

    conv = await _get_or_create_conv(db, task_id, owner_id)
    if conv is None:
        raise HTTPException(404, "面试会话不存在")
    if regenerate and conv.questions:
        conv.questions = []
        conv.answers = {}
        conv.current_index = 0
        conv.status = "ongoing"
        conv.optimized_resume = None
        conv.chat_log = None

    conv = await _ensure_plan(db, conv, resume_text, jd_text, diagnosis.get("gaps", []), llm_cfg)
    return _plan_payload(conv)


@router.post("/start-free")
async def start_free_interview(
    req: FreeStartRequest,
    db: AsyncSession = Depends(get_db),
    owner_id: str = Depends(get_owner_id),
):
    """M31 独立面试：按「简历 + 意向岗位 JD」直接开一场面试，不依赖诊断任务。

    创建独立会话（iv- 前缀 task_id，上下文存 Conversation.context）并生成题单。
    """
    resume = await db.get(Resume, req.resume_id)
    if not resume or (resume.owner_id and resume.owner_id != owner_id):
        raise HTTPException(404, "简历不存在")

    task_id = f"iv-{uuid.uuid4().hex[:12]}"
    conv = Conversation(
        task_id=task_id, owner_id=owner_id, type="interview",
        context=json.dumps({"resume_id": req.resume_id, "jd_text": req.jd_text},
                           ensure_ascii=False),
        questions=[], answers={}, current_index=0, status="ongoing",
    )
    db.add(conv)
    await db.commit()
    await db.refresh(conv)

    conv = await _ensure_plan(db, conv, resume.raw_text, req.jd_text, [], req.llm_config)
    return {"task_id": task_id, **_plan_payload(conv)}


@router.get("/sessions")
async def list_sessions(
    db: AsyncSession = Depends(get_db),
    owner_id: str = Depends(get_owner_id),
):
    """M31 面试会话列表（独立 + 诊断内嵌），供「继续面试 / 历史回看」。"""
    rows = (
        await db.execute(
            select(Conversation)
            .where(Conversation.owner_id == owner_id, Conversation.type == "interview")
            .order_by(Conversation.updated_at.desc())
            .limit(20)
        )
    ).scalars().all()
    return {
        "items": [
            {
                "task_id": c.task_id,
                "status": c.status,
                "total": len(c.questions or []),
                "answered": len(c.answers or {}),
                "current_index": c.current_index,
                "summary": bool(c.optimized_resume),
                "source": "独立面试" if c.context else "诊断面试",
                "first_question": (c.questions or [{}])[0].get("question", "")[:60],
                "updated_at": c.updated_at.isoformat() if c.updated_at else None,
            }
            for c in rows
        ]
    }


def _plan_payload(conv: Conversation) -> dict:
    return {
        "questions": conv.questions,
        "current_index": conv.current_index,
        "total": len(conv.questions),
        "status": conv.status,
        "chat_log": _chat_base_log(conv),
        "summary": conv.optimized_resume or None,
    }


@router.get("/{task_id}")
async def get_interview(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    owner_id: str = Depends(get_owner_id),
):
    """恢复面试会话（题目/进度/点评记录/总评）。"""
    conv = (
        await db.execute(
            select(Conversation).where(
                Conversation.task_id == task_id,
                Conversation.owner_id == owner_id,
                Conversation.type == "interview",
            )
        )
    ).scalar_one_or_none()
    if not conv:
        return {"exists": False}
    return {"exists": True, **_plan_payload(conv)}


def _chat_base_log(conv: Conversation) -> list:
    """M32 完整对话流：chat_log 优先；旧会话（无 chat_log）从 questions/answers 合成。

    合成规则：已到达的每题输出 题干 → 候选人回答 → 面试官点评，
    保证进行中的会话末尾总是「面试官题干、等待候选人发言」的状态。
    """
    if conv.chat_log:
        try:
            log = json.loads(conv.chat_log)
            if isinstance(log, list) and log:
                return log
        except (ValueError, TypeError):
            pass
    questions = conv.questions or []
    answers = conv.answers or {}
    idx = conv.current_index if isinstance(conv.current_index, int) else 0
    idx = max(0, min(idx, len(questions)))
    log: list = []
    for i, q in enumerate(questions):
        if i > idx:
            break
        log.append({"role": "interviewer", "qid": q["id"], "content": q["question"]})
        item = answers.get(q["id"]) or {}
        if item.get("answer"):
            log.append({"role": "candidate", "qid": q["id"], "content": item["answer"]})
        if item.get("feedback"):
            log.append({"role": "interviewer", "qid": q["id"], "content": item["feedback"]})
    return log


def _chat_history_text(log: list, limit: int = 40) -> str:
    """对话流转 LLM 文本（每条截断，防上下文爆炸）。"""
    msgs = log[-limit:]
    return "\n".join(
        f"{'面试官' if m.get('role') == 'interviewer' else '候选人'}："
        f"{str(m.get('content', ''))[:500]}"
        for m in msgs
    ) or "（对话刚开始）"


@router.post("/chat/{task_id}")
async def chat_reply(
    task_id: str,
    req: ChatMessage,
    db: AsyncSession = Depends(get_db),
    owner_id: str = Depends(get_owner_id),
):
    """M32 多轮自由对话：候选人围绕当前题自由发言，面试官自然回应（可追问/可补充）。

    LLM 判断 advance：本题回答充分则推进 current_index（末题出总评），否则留在本题继续聊。
    本题全部候选人发言在收尾时合并落入 answers[qid]。
    """
    _rec, resume_text, jd_text, _diag = await _load_context(task_id, db, owner_id)

    conv = (
        await db.execute(
            select(Conversation).where(
                Conversation.task_id == task_id,
                Conversation.owner_id == owner_id,
                Conversation.type == "interview",
            )
        )
    ).scalar_one_or_none()
    if not conv or not conv.questions:
        raise HTTPException(400, "请先在「面试准备」生成题单")
    if conv.status == "finished":
        raise HTTPException(400, "本场面试已结束，总评已生成")

    questions = conv.questions
    idx = conv.current_index if isinstance(conv.current_index, int) else 0
    idx = max(0, min(idx, len(questions) - 1))
    q = questions[idx]
    content = req.content.strip()
    if req.force_advance:
        # 「本题回答完毕」按钮：前端占位文案仅作触发信号，不落入对话流/答案
        # （否则「（本题回答完毕…）」会被合并进 answers 参与总评，污染内容）
        content = "（候选人表示本题回答完毕或跳过）"
    elif not content:
        raise HTTPException(400, "发言不能为空")

    log = _chat_base_log(conv)
    force_note = (
        "\n【强制收尾】候选人已表示本题回答完毕或跳过，必须 advance=true。\n"
        if req.force_advance
        else ""
    )
    try:
        turn = await call_llm_for_json(
            CHAT_PROMPT.format(
                resume_text=resume_text[:4000], jd_text=jd_text[:2500],
                total=len(questions), idx=idx + 1, category=q["category"],
                questions="\n".join(
                    f"{i + 1}. [{x['category']}] {x['question']}"
                    for i, x in enumerate(questions)
                ),
                question=q["question"], focus=q.get("focus") or "综合能力",
                hint=q.get("hint") or "无",
                chat_history=_chat_history_text(log),
                content=content[:2000],
            ) + force_note,
            ChatTurn, temperature=0.7, llm_config=req.llm_config,
        )
    except Exception as e:
        logger.exception("面试官回应失败")
        raise HTTPException(500, f"面试官回应失败: {e}")

    if not req.force_advance:
        log.append({"role": "candidate", "qid": q["id"], "content": content})
    log.append({"role": "interviewer", "qid": q["id"], "content": turn.reply})

    payload = {
        "reply": turn.reply,
        "advance": turn.advance,
        "next_index": idx,
        "total": len(questions),
        "finished": False,
        "summary": None,
        "chat_log": log,
    }

    if turn.advance:
        # 本题收尾：本题内候选人全部发言合并为该题作答记录（供总评/历史摘要用）
        merged = "；".join(
            m["content"] for m in log
            if m["role"] == "candidate" and m["qid"] == q["id"]
        )
        answers = dict(conv.answers or {})
        answers[q["id"]] = {"answer": merged[:4000], "feedback": turn.reply}
        conv.answers = answers
        conv.current_index = idx + 1
        payload["next_index"] = idx + 1

        if idx + 1 >= len(questions):
            try:
                summary = await call_llm_for_json(
                    SUMMARY_PROMPT.format(
                        resume_text=resume_text[:4000], jd_text=jd_text[:2500],
                        history=_history_text(questions, answers),
                    ),
                    InterviewSummary, temperature=0.5, llm_config=req.llm_config,
                )
                conv.optimized_resume = summary.model_dump()
                payload["summary"] = summary.model_dump()
            except Exception as e:
                logger.exception("面试总评失败")
                payload["summary_error"] = str(e)[:200]
            conv.status = "finished"
            payload["finished"] = True
        else:
            nxt = questions[idx + 1]
            log.append({"role": "interviewer", "qid": nxt["id"], "content": nxt["question"]})

    conv.chat_log = json.dumps(log, ensure_ascii=False)
    await db.commit()
    return payload


def _history_text(questions: list, answers: dict) -> str:
    lines = []
    for i, q in enumerate(questions):
        item = answers.get(q["id"]) or {}
        if not item:
            continue
        lines.append(f"Q{i + 1}（{q['category']}）：{q['question']}\n"
                     f"回答：{item.get('answer', '')}\n"
                     f"面试官点评：{item.get('feedback', '')}")
    return "\n\n".join(lines)


class ExportInterviewRequest(BaseModel):
    # 桌面形态专用：服务端直写该绝对路径；为空时走浏览器 blob 下载
    save_path: str | None = None


@router.post("/export/{task_id}")
async def export_interview_report(
    task_id: str,
    req: ExportInterviewRequest | None = None,
    db: AsyncSession = Depends(get_db),
    owner_id: str = Depends(get_owner_id),
):
    """M33 面试报告导出 Word：问答记录 + 总评。

    save_path 为空：浏览器 blob 下载；非空（仅桌面形态）：服务端直写该路径。
    两种方式均落 export_history（template=interview）。
    """
    req = req or ExportInterviewRequest()
    conv = (
        await db.execute(
            select(Conversation).where(
                Conversation.task_id == task_id,
                Conversation.owner_id == owner_id,
                Conversation.type == "interview",
            )
        )
    ).scalar_one_or_none()
    if not conv:
        raise HTTPException(404, "面试会话不存在")
    # 总评复用 optimized_resume 字段（M23 设计约定），无总评 = 面试未完成
    if not conv.optimized_resume:
        raise HTTPException(409, "面试尚未完成（无总评），完成后可导出")

    try:
        data = generate_interview_docx({
            "questions": conv.questions or [],
            "answers": conv.answers or {},
            "summary": conv.optimized_resume or {},
        })
    except Exception as e:
        raise HTTPException(500, f"生成失败: {e}")

    filename = f"模拟面试报告_{datetime.now().strftime('%Y%m%d_%H%M')}.docx"

    # 复用简历导出的路径校验与导出历史记录（同为 .docx 产物）
    from app.api.v1.resume import _record_export, _validate_save_path

    if req.save_path:
        target = _validate_save_path(req.save_path)
        try:
            target.write_bytes(data)
        except OSError as e:
            raise HTTPException(500, f"写入文件失败: {e}")
        await _record_export(db, owner_id, target.name, str(target), "interview")
        return {"saved_to": str(target), "filename": target.name}

    await _record_export(db, owner_id, filename, None, "interview")
    quoted = quote(filename)
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quoted}",
        },
    )
