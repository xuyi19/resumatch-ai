# -*- coding: utf-8 -*-
"""M64 刷题工坊：AI 按岗位方向出笔试题 → 作答 → 交卷判定 → 战报 + 错题本。

复用 Conversation 表（type="quiz"，M17 设计时预留）：
questions 存题目数组 [{id, qtype, stem, options, answer, analysis}]，
answers 存 [{qid, picked, correct}]（交卷后落库；correct=None 表示编程题 AI 判定不可用），
optimized_resume 复用为战报 {score, correct_count, total, wrong_ids}，
context 存 {direction, jd_text, count}，current_index 恒 0。

红线：题目只围绕岗位方向/JD 考察能力出题，不得编造具体公司内部信息；
不做任何网页爬取；LLM 失败不静默降级（出题 502 / 编程题判定单题容错）。
"""
import copy
import json
import uuid

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.utils import call_llm_for_json
from app.core.db import get_db
from app.core.deps import get_owner_id
from app.models.entities import Conversation

router = APIRouter(prefix="/quiz", tags=["quiz"])


# ---------------- Pydantic 模型 ----------------

class QuizGenerateRequest(BaseModel):
    direction: str = Field(min_length=1, max_length=40, description="岗位方向，如 Python 后端")
    jd_text: str = Field(default="", max_length=6000, description="可选绑定的岗位 JD")
    count: int = Field(default=8, ge=5, le=20, description="题数 5-20")
    # 必须允许 None：前端未配置 Key 时显式传 null（dict 严格类型会 422 拒掉整个请求）
    llm_config: dict | None = Field(default=None, description="用户 LLM 配置；空则用服务端默认")


class QuizQuestion(BaseModel):
    id: str = Field(description="题目编号 q1..qn")
    qtype: str = Field(description="题型：choice 技术选择 / logic 行测逻辑 / math 数量关系 / code 编程思路")
    stem: str = Field(description="题干")
    options: list[str] = Field(default_factory=list, description="选项；编程题为空数组")
    answer: int | str = Field(description="选择题正确选项下标（整数）；编程题为参考答案要点文本")
    analysis: str = Field(default="", description="解析")


class QuizPlan(BaseModel):
    questions: list[QuizQuestion] = Field(default_factory=list)


class QuizSubmitRequest(BaseModel):
    # 允许 None：未作答的题前端传 null（记为错误，不炸请求）
    answers: dict[str, int | str | None] = Field(default_factory=dict, description="{qid: 作答}")
    llm_config: dict | None = Field(default=None, description="用户 LLM 配置；空则用服务端默认")


class CodeJudge(BaseModel):
    """编程题 AI 判定结果：宽缓标准——覆盖主要解题思路即算对。"""

    correct: bool
    comment: str = Field(default="", description="一句话点评+关键缺失点（≤80字）")


QUIZ_PROMPT = """你是一位资深笔试出题官。请围绕岗位方向（及可选 JD）所要求的考察能力出题，共 {count} 道。

## 岗位方向
{direction}

## 岗位 JD（可选，可能为空）
{jd_text}

## 出题要求
1. 题目只围绕该岗位方向/JD 所需的通用知识与能力出题，禁止编造任何具体公司的内部信息（如内部系统、内部流程、内部数据）
2. 题型分布约：技术选择题 60%、行测逻辑题 15%、数量关系题 10%、编程思路题 15%
   - choice 技术选择题 / logic 行测逻辑题 / math 数量关系题：options 给 4 个选项，answer 为正确选项下标（0-3 的整数）
   - code 编程思路题：options 为空数组 []，answer 为参考答案要点文本（200 字内），考察解题思路而非完整可运行代码
3. 题目要具体不空泛，贴近真实笔试难度；每题给 analysis 解析（说清正确答案的道理）
4. id 依次 q1..q{count}，qtype 取值：choice / logic / math / code

## 输出 JSON
{{
  "questions": [
    {{
      "id": "q1", "qtype": "choice",
      "stem": "Python 中查找字典某个键的平均时间复杂度是？",
      "options": ["O(n)", "O(1)", "O(log n)", "O(n log n)"],
      "answer": 1,
      "analysis": "字典基于哈希表实现，键查找平均 O(1)；列表按值查找为 O(n)。"
    }},
    {{
      "id": "q4", "qtype": "code",
      "stem": "设计一个函数统计一段文本中出现次数最多的词，说明你的思路。",
      "options": [],
      "answer": "分词后用哈希表统计词频，一次遍历取最大值；提及大小写归一化与 O(n) 复杂度即可。",
      "analysis": "考察哈希计数思想与复杂度分析。"
    }}
  ]
}}
"""

JUDGE_PROMPT = """你是一位笔试编程题阅卷官。请判定候选人对编程思路题的作答是否正确。

## 题目
{stem}

## 参考答案要点
{answer}

## 候选人作答
{picked}

## 判定标准（宽缓）
- 覆盖主要解题思路即算正确，不要求代码可运行、不苛求细节完整
- 只看思路方向是否正确、与参考答案要点是否大体吻合

## 输出 JSON
{{"correct": true, "comment": "一句话点评+关键缺失点（≤80字）"}}
"""


async def _get_conv(db: AsyncSession, task_id: str, owner_id: str) -> Conversation | None:
    return (
        await db.execute(
            select(Conversation).where(
                Conversation.task_id == task_id,
                Conversation.owner_id == owner_id,
                Conversation.type == "quiz",
            )
        )
    ).scalar_one_or_none()


def _parse_ctx(conv: Conversation) -> dict:
    try:
        ctx = json.loads(conv.context) if conv.context else {}
    except (ValueError, TypeError):
        ctx = {}
    return ctx if isinstance(ctx, dict) else {}


def _strip_answer(q: dict) -> dict:
    """剥离 answer/analysis 只留题面；深拷贝避免内部对象引用外泄（防作弊）。"""
    face = copy.deepcopy(q)
    face.pop("answer", None)
    face.pop("analysis", None)
    return face


@router.post("/generate")
async def generate_quiz(
    req: QuizGenerateRequest,
    db: AsyncSession = Depends(get_db),
    owner_id: str = Depends(get_owner_id),
):
    """AI 出题开一场练习：创建 qz- 前缀会话，返回剥离答案的题面（防作弊）。"""
    direction = req.direction.strip()
    if not direction:
        raise HTTPException(400, "岗位方向不能为空")

    prompt = QUIZ_PROMPT.format(
        direction=direction, jd_text=req.jd_text.strip()[:2500] or "（未提供）", count=req.count,
    )
    try:
        plan = await call_llm_for_json(
            prompt, QuizPlan, temperature=0.5, llm_config=req.llm_config,
        )
    except Exception as e:
        logger.exception("刷题出题失败")
        raise HTTPException(502, f"出题失败: {e}") from e
    if not plan.questions:
        raise HTTPException(502, "出题失败: 生成的题目为空，请重试")

    questions = [q.model_dump() for q in plan.questions]
    task_id = f"qz-{uuid.uuid4().hex[:12]}"
    conv = Conversation(
        task_id=task_id, owner_id=owner_id, type="quiz",
        context=json.dumps(
            {"direction": direction, "jd_text": req.jd_text.strip(), "count": req.count},
            ensure_ascii=False,
        ),
        questions=questions, answers=[], current_index=0, status="ongoing",
    )
    db.add(conv)
    await db.commit()
    await db.refresh(conv)
    return {"task_id": task_id, "questions": [_strip_answer(q) for q in questions],
            "count": len(questions)}


@router.get("/sessions")
async def list_quiz_sessions(
    db: AsyncSession = Depends(get_db),
    owner_id: str = Depends(get_owner_id),
):
    """最近 20 场练习（updated_at desc）；未交卷 score=None。"""
    rows = (
        await db.execute(
            select(Conversation)
            .where(Conversation.owner_id == owner_id, Conversation.type == "quiz")
            .order_by(Conversation.updated_at.desc())
            .limit(20)
        )
    ).scalars().all()
    return [
        {
            "task_id": c.task_id,
            "direction": _parse_ctx(c).get("direction", ""),
            "status": c.status,
            "total": len(c.questions or []),
            "score": (c.optimized_resume or {}).get("score") if c.status == "finished" else None,
            "created_at": c.created_at.isoformat() if c.created_at else None,
            "updated_at": c.updated_at.isoformat() if c.updated_at else None,
        }
        for c in rows
    ]


@router.get("/wrongbook")
async def quiz_wrongbook(
    db: AsyncSession = Depends(get_db),
    owner_id: str = Depends(get_owner_id),
):
    """错题本：扫描本用户全部已交卷会话，收集 correct=False 的题，倒序上限 50 条。"""
    rows = (
        await db.execute(
            select(Conversation)
            .where(
                Conversation.owner_id == owner_id,
                Conversation.type == "quiz",
                Conversation.status == "finished",
            )
            .order_by(Conversation.updated_at.desc())
        )
    ).scalars().all()
    items: list[dict] = []
    for c in rows:
        ctx = _parse_ctx(c)
        by_qid = {
            a.get("qid"): a for a in (c.answers or []) if isinstance(a, dict)
        }
        for q in c.questions or []:
            a = by_qid.get(q.get("id"))
            if not a or a.get("correct") is not False:
                continue
            items.append({
                "task_id": c.task_id,
                "qid": q.get("id"),
                "direction": ctx.get("direction", ""),
                "qtype": q.get("qtype", "choice"),
                "stem": q.get("stem", ""),
                "options": q.get("options") or [],
                "answer": q.get("answer"),
                "analysis": q.get("analysis", ""),
                "updated_at": c.updated_at.isoformat() if c.updated_at else None,
            })
            if len(items) >= 50:
                break
        if len(items) >= 50:
            break
    return {"items": items[:50]}


@router.get("/{task_id}")
async def get_quiz(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    owner_id: str = Depends(get_owner_id),
):
    """恢复会话：进行中返回剥离答案的题面；已完成返回完整题 + 判定结果 + 战报。"""
    conv = await _get_conv(db, task_id, owner_id)
    if not conv:
        return {"exists": False}
    finished = conv.status == "finished"
    return {
        "exists": True,
        "task_id": conv.task_id,
        "status": conv.status,
        "direction": _parse_ctx(conv).get("direction", ""),
        "questions": (conv.questions or []) if finished
        else [_strip_answer(q) for q in (conv.questions or [])],
        "answers": conv.answers or [],
        "report": (conv.optimized_resume or None) if finished else None,
    }


@router.post("/{task_id}/submit")
async def submit_quiz(
    task_id: str,
    req: QuizSubmitRequest,
    db: AsyncSession = Depends(get_db),
    owner_id: str = Depends(get_owner_id),
):
    """交卷：选择题确定性判定；编程题逐题 AI 判定（单题失败不炸整体）。"""
    conv = await _get_conv(db, task_id, owner_id)
    if not conv:
        raise HTTPException(404, "刷题会话不存在")
    if conv.status == "finished":
        raise HTTPException(400, "本场已交卷，不能重复提交")
    questions = conv.questions or []
    if not questions:
        raise HTTPException(400, "会话内无题目，无法交卷")

    results: list[dict] = []
    answer_rows: list[dict] = []
    correct_count = 0
    for q in questions:
        qid = q.get("id", "")
        qtype = q.get("qtype", "choice")
        picked = (req.answers or {}).get(qid)
        comment = None
        if qtype == "code":
            try:
                verdict = await call_llm_for_json(
                    JUDGE_PROMPT.format(
                        stem=str(q.get("stem", ""))[:1500],
                        answer=str(q.get("answer", ""))[:800],
                        picked=str(picked)[:1500] if picked is not None else "（未作答）",
                    ),
                    CodeJudge, temperature=0.2, llm_config=req.llm_config,
                )
                correct = bool(verdict.correct)
                comment = (verdict.comment or "").strip()
            except Exception:
                logger.exception("编程题 AI 判定失败 qid={}", qid)
                correct = None
                comment = "AI 判定不可用，请对照解析自评"
        else:
            # 确定性判定：选项下标比较（str 归一容忍 "2" vs 2 的类型差异）
            correct = picked is not None and str(picked) == str(q.get("answer"))

        if correct is True:
            correct_count += 1
        row = {"qid": qid, "picked": picked, "correct": correct}
        if comment:
            row["comment"] = comment
        answer_rows.append(row)

        item = {
            "qid": qid, "qtype": qtype, "stem": q.get("stem", ""),
            "options": q.get("options") or [], "picked": picked, "correct": correct,
            "answer": q.get("answer"), "analysis": q.get("analysis", ""),
        }
        if comment:
            item["comment"] = comment
        results.append(item)

    total = len(questions)
    score = round(correct_count * 100 / total)
    wrong_ids = [r["qid"] for r in answer_rows if r["correct"] is False]

    conv.answers = answer_rows
    conv.optimized_resume = {
        "score": score, "correct_count": correct_count, "total": total, "wrong_ids": wrong_ids,
    }
    conv.status = "finished"
    await db.commit()
    return {
        "results": results, "score": score, "correct_count": correct_count,
        "total": total, "wrong_ids": wrong_ids,
    }


@router.delete("/sessions/{task_id}")
async def delete_quiz_session(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    owner_id: str = Depends(get_owner_id),
):
    """删除练习会话（清理废弃/误建会话）。"""
    conv = await _get_conv(db, task_id, owner_id)
    if not conv:
        raise HTTPException(404, "刷题会话不存在")
    await db.delete(conv)
    await db.commit()
    return {"ok": True}
