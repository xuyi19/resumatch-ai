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
import re
import uuid
from datetime import datetime
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import StreamingResponse
from loguru import logger
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.llm import get_llm
from app.agents.utils import _extract_first_json, call_llm_for_json
from app.core.config import settings
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
    # M34 评分量化：旧会话无这两个字段（前端/导出均需容错缺省）
    overall_score: float | None = Field(default=None, description="总分 0-10，可一位小数")
    scores: dict[str, float] = Field(default_factory=dict, description="每题得分 {qid: 0-10}")
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
- scores：每题 0-10 分（可一位小数），评分依据：要点覆盖度、与 JD 相关性、表达结构；
  如 {{"q1": 7.5, "q2": 6}}，必须覆盖全部题目，禁止漏题
- overall_score：总分 0-10（各题加权平均即可，整体印象可微调）
- strengths/weaknesses：各 2-3 条，具体到回答内容
- suggestions：2-3 条可执行的面试准备建议

## 输出 JSON
{{"overall": "...", "overall_score": 7.2, "scores": {{"q1": 7.5, "q2": 6}}, "strengths": ["..."], "weaknesses": ["..."], "suggestions": ["..."]}}
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
                # M34 会话列表带总分（旧会话/未完成为 None）
                "overall_score": (c.optimized_resume or {}).get("overall_score"),
                "source": "独立面试" if c.context else "诊断面试",
                "first_question": (c.questions or [{}])[0].get("question", "")[:60],
                "updated_at": c.updated_at.isoformat() if c.updated_at else None,
            }
            for c in rows
        ]
    }


@router.delete("/sessions/{task_id}")
async def delete_session(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    owner_id: str = Depends(get_owner_id),
):
    """M37 删除面试会话（清理误建/废弃会话；只删 Conversation，不影响关联诊断记录）。"""
    conv = await _get_or_create_conv(db, task_id, owner_id)
    if not conv:
        raise HTTPException(404, "面试会话不存在")
    await db.delete(conv)
    await db.commit()
    return {"ok": True}


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


async def _prepare_chat(
    db: AsyncSession, task_id: str, owner_id: str, req: ChatMessage
):
    """chat 与 chat-stream 共用的前置校验 + prompt 组装（校验失败抛 HTTPException）。

    返回 (conv, log, questions, idx, prompt, resume_text, jd_text, user_content)；
    user_content 为候选人原始发言（force_advance 时仅作触发信号，不入对话流）。
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
    user_content = req.content.strip()
    if req.force_advance:
        # 「本题回答完毕」按钮：前端占位文案仅作触发信号，不落入对话流/答案
        # （否则「（本题回答完毕…）」会被合并进 answers 参与总评，污染内容）
        content = "（候选人表示本题回答完毕或跳过）"
    elif not user_content:
        raise HTTPException(400, "发言不能为空")
    else:
        content = user_content

    log = _chat_base_log(conv)
    force_note = (
        "\n【强制收尾】候选人已表示本题回答完毕或跳过，必须 advance=true。\n"
        if req.force_advance
        else ""
    )
    prompt = CHAT_PROMPT.format(
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
    ) + force_note
    return conv, log, questions, idx, prompt, resume_text, jd_text, user_content


def _apply_turn(conv: Conversation, log: list, questions: list, idx: int,
                user_content: str, turn: ChatTurn, force_advance: bool) -> tuple[dict, bool]:
    """turn 落库 + advance 推进（chat 与 chat-stream 共用）。

    返回 (payload, need_summary)。need_summary=True 表示末题收尾、总评待生成
    （流式版要先发 stage 事件再调 LLM，故拆出）。payload 结构与 /chat 回包一致；
    conv.answers / current_index / status / chat_log 已更新，commit 由调用方负责。
    """
    q = questions[idx]
    if not force_advance:
        log.append({"role": "candidate", "qid": q["id"], "content": user_content})
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
    need_summary = False

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
            conv.status = "finished"
            payload["finished"] = True
            need_summary = True
        else:
            nxt = questions[idx + 1]
            log.append({"role": "interviewer", "qid": nxt["id"], "content": nxt["question"]})

    conv.chat_log = json.dumps(log, ensure_ascii=False)
    return payload, need_summary


async def _gen_summary(conv: Conversation, payload: dict, resume_text: str,
                       jd_text: str, questions: list, llm_cfg: dict | None) -> None:
    """末题总评：生成并落 optimized_resume；失败只标 summary_error，不中断收尾。"""
    try:
        summary = await call_llm_for_json(
            SUMMARY_PROMPT.format(
                resume_text=resume_text[:4000], jd_text=jd_text[:2500],
                history=_history_text(questions, conv.answers or {}),
            ),
            InterviewSummary, temperature=0.5, llm_config=llm_cfg,
        )
        conv.optimized_resume = summary.model_dump()
        payload["summary"] = summary.model_dump()
    except Exception as e:
        logger.exception("面试总评失败")
        payload["summary_error"] = str(e)[:200]


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
    conv, log, questions, idx, prompt, resume_text, jd_text, user_content = await _prepare_chat(
        db, task_id, owner_id, req
    )
    try:
        turn = await call_llm_for_json(prompt, ChatTurn, temperature=0.7, llm_config=req.llm_config)
    except Exception as e:
        logger.exception("面试官回应失败")
        raise HTTPException(500, f"面试官回应失败: {e}")

    payload, need_summary = _apply_turn(
        conv, log, questions, idx, user_content, turn, req.force_advance
    )
    if need_summary:
        await _gen_summary(conv, payload, resume_text, jd_text, questions, req.llm_config)
    await db.commit()
    return payload


# ---------------- 优化⑩ 流式 SSE /chat-stream ----------------

def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _sse_fatal(detail: str) -> str:
    return f"event: fatal\ndata: {json.dumps({'detail': detail}, ensure_ascii=False)}\n\n"


class _JsonFieldStream:
    """从 LLM token 流中增量解码指定字符串字段的值（SSE 渐进渲染用）。

    流式 chat 要求模型输出 {"reply": "...", "advance": false}，reply 是首个键且值为
    字符串：token 到达即可边收边解码 reply。这里只做宽松的「边收边显」，不校验整体
    JSON；流结束后仍按完整文本走 _extract_first_json 严格解析（_parse_chat_turn）。
    模型跑偏（无 JSON、键序不符、```json 前缀）时安全退化：增量文本为空或不完整，
    由调用方兜底，不影响落库正确性。
    """

    _ESC = {"n": "\n", "t": "\t", "r": "\r", '"': '"',
            "\\": "\\", "/": "/", "b": "\b", "f": "\f"}

    def __init__(self, field: str):
        self._field = field
        self._chars: list[str] = []
        self._state = "before"  # before→key_open→key→colon→val_open→value→done
        self._key: list[str] = []
        self._esc = False
        self._uni = ""          # \uXXXX 四位十六进制缓冲

    @property
    def text(self) -> str:
        return "".join(self._chars)

    def feed(self, chunk: str) -> None:
        for ch in chunk:
            self._step(ch)

    def _step(self, ch: str) -> None:
        st = self._state
        if st == "before":            # 忽略 ```json 等 JSON 前缀
            if ch == "{":
                self._state = "key_open"
        elif st == "key_open":        # 等待键名起始引号（跳过空白）
            if ch == '"':
                self._state = "key"
                self._key = []
        elif st == "key":             # 读键名；非目标键即放弃增量（不影响最终解析）
            if self._esc:
                self._key.append(ch)
                self._esc = False
            elif ch == "\\":
                self._esc = True
            elif ch == '"':
                self._state = "colon" if "".join(self._key) == self._field else "done"
            else:
                self._key.append(ch)
        elif st == "colon":           # 等待冒号
            if ch == ":":
                self._state = "val_open"
            elif not ch.isspace():
                self._state = "done"
        elif st == "val_open":        # 等待值起始引号
            if ch == '"':
                self._state = "value"
            elif not ch.isspace():
                self._state = "done"
        elif st == "value":           # 流式解码字符串值
            if self._uni:
                self._uni += ch
                if len(self._uni) == 4:
                    try:
                        self._chars.append(chr(int(self._uni, 16)))
                    except ValueError:
                        pass
                    self._uni = ""
            elif self._esc:
                self._esc = False
                if ch == "u":
                    self._uni = ""
                else:
                    self._chars.append(self._ESC.get(ch, ch))
            elif ch == "\\":
                self._esc = True
            elif ch == '"':
                self._state = "done"
            else:
                self._chars.append(ch)
        # done：后续 token 不再消费


def _parse_chat_turn(raw: str, streamed_reply: str) -> ChatTurn:
    """流式结束后按完整输出严格解析为 ChatTurn。

    JSON 不合法但已有流式发言时安全降级：保留文本、advance=False 留在本题
    （候选人可点「本题回答完毕」推进）；完全无发言则抛错走非流式降级。
    """
    content = raw.strip()
    if content.startswith("```"):
        content = re.sub(r"^```(?:json)?\s*", "", content)
        content = re.sub(r"\s*```$", "", content)
    extracted = _extract_first_json(content)
    if extracted:
        try:
            return ChatTurn.model_validate(json.loads(extracted))
        except Exception as e:
            logger.warning(f"面试流式回应 JSON 校验失败: {e}")
    if streamed_reply.strip():
        return ChatTurn(reply=streamed_reply.strip(), advance=False)
    raise RuntimeError("响应中未找到合法 JSON")


@router.post("/chat-stream/{task_id}")
async def chat_reply_stream(
    task_id: str,
    req: ChatMessage,
    db: AsyncSession = Depends(get_db),
    owner_id: str = Depends(get_owner_id),
):
    """优化⑩ 流式版多轮对话：面试官回应 token 级 SSE 渐进推送（首字延迟从整段 3~8s 降至首 token）。

    事件序列（均以 data: 帧下发；异常用 event: fatal）：
    - {"type": "start", "qid": ..., "index": ...}  会话锚点（流式气泡挂到当前题）
    - {"type": "delta", "text": ...}               面试官发言增量
    - {"type": "stage", "stage": "summarizing"}    末题收尾，正在生成总评
    - {"type": "final", ...}                       与 /chat 回包结构完全一致，前端以此为准
    会话校验失败在开流前抛 HTTPException；LLM 流式失败自动降级非流式重试一次，
    仍失败才发 fatal。落库/推进逻辑与 /chat 完全一致（复用 _prepare_chat/_apply_turn）。
    """
    conv, log, questions, idx, prompt, resume_text, jd_text, user_content = await _prepare_chat(
        db, task_id, owner_id, req
    )

    async def event_gen():
        yield _sse({"type": "start", "qid": questions[idx]["id"], "index": idx})

        raw_parts: list[str] = []
        field = _JsonFieldStream("reply")
        sent = 0
        try:
            cfg = req.llm_config or {}
            llm = get_llm(temperature=0.7, api_key=cfg.get("api_key"),
                          base_url=cfg.get("base_url"), model=cfg.get("model"))
            async for chunk in llm.astream(prompt):
                piece = chunk.content if isinstance(getattr(chunk, "content", None), str) else ""
                if not piece:
                    continue
                raw_parts.append(piece)
                field.feed(piece)
                text = field.text
                if len(text) > sent:
                    yield _sse({"type": "delta", "text": text[sent:]})
                    sent = len(text)
            turn = _parse_chat_turn("".join(raw_parts), field.text)
        except Exception as e:
            # 流式失败降级：非流式重试一次（复用 call_llm_for_json 的重试与校验）
            logger.warning(f"面试流式回应失败，降级非流式: {e}")
            try:
                turn = await call_llm_for_json(
                    prompt, ChatTurn, temperature=0.7, llm_config=req.llm_config,
                )
            except Exception as e2:
                logger.exception("面试官回应失败")
                yield _sse_fatal(f"面试官回应失败: {e2}")
                return
            if len(turn.reply) > sent:  # 未流出的部分一次性补齐（已流出部分不重复）
                yield _sse({"type": "delta", "text": turn.reply[sent:]})

        payload, need_summary = _apply_turn(
            conv, log, questions, idx, user_content, turn, req.force_advance
        )
        if need_summary:
            yield _sse({"type": "stage", "stage": "summarizing"})
            await _gen_summary(conv, payload, resume_text, jd_text, questions, req.llm_config)

        try:
            await db.commit()  # 先落库再发 final，保证前端拿到 final 时状态已持久
        except Exception as e:
            logger.exception("面试对话落库失败")
            yield _sse_fatal(f"落库失败: {e}")
            return
        yield _sse({"type": "final", **payload})

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


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
    # 桌面形态专用：非空即触发服务端直写（M71 起统一写入设置的导出根目录并按类型
    # 分类落盘，本字段的路径值不再使用）；为空时走浏览器 blob 下载
    save_path: str | None = None


@router.post("/export/{task_id}")
async def export_interview_report(
    task_id: str,
    req: ExportInterviewRequest | None = None,
    db: AsyncSession = Depends(get_db),
    owner_id: str = Depends(get_owner_id),
):
    """M33 面试报告导出 Word：问答记录 + 总评 + 多轮对话全文附录（M47）。

    save_path 为空：浏览器 blob 下载；非空（仅桌面形态）：M71 统一落盘到设置的
    导出根目录「面试报告」子目录。两种方式均落 export_history（template=interview）。
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
            "chat_log": _chat_base_log(conv),  # M47 附录：完整对话流（旧会话自动合成）
        })
    except Exception as e:
        raise HTTPException(500, f"生成失败: {e}")

    filename = f"模拟面试报告_{datetime.now().strftime('%Y%m%d_%H%M')}.docx"

    # 复用简历导出的历史记录（同为 .docx 产物）
    from app.api.v1.resume import _record_export
    from app.utils.export_paths import resolve_save_path

    if req.save_path:
        # 桌面形态（M71）：save_path 仅作直写标志，按「导出位置」设置分类落盘
        if settings.APP_MODE == "web":
            raise HTTPException(status_code=403, detail="网页形态不支持服务端落盘")
        target = await resolve_save_path("interview", filename, db, owner_id)
        try:
            target.write_bytes(data)
        except OSError as e:
            raise HTTPException(500, f"写入文件失败: {e}")
        await _record_export(db, owner_id, target.name, str(target), "interview")
        return {"saved_to": str(target), "save_path": str(target), "filename": target.name}

    await _record_export(db, owner_id, filename, None, "interview")
    quoted = quote(filename)
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quoted}",
        },
    )
