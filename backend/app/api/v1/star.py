# -*- coding: utf-8 -*-
"""M65 项目素材库（STAR 卡片）：项目/成就统一建档，情境-任务-行动-结果结构化卡片。

一站式素材中枢：后续简历优化 / 面试答题 / 求职信生成将复用引用（本版仅档案本体）。

红线：AI 生成草稿必须严格基于用户输入文本，禁止编造输入中不存在的项目细节/数据/公司；
LLM 失败不静默降级（502 附原因，宁缺毋假）。
"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
from pydantic import BaseModel, Field
from sqlalchemy import delete as sa_delete
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.utils import call_llm_for_json
from app.core.db import get_db
from app.core.deps import get_owner_id
from app.models.entities import StarCard

router = APIRouter(prefix="/star", tags=["star"])

_TITLE_MAX = 60
_ROLE_MAX = 40
_TAGS_MAX = 200
_STAR_TEXT_MAX = 2000


# ---------------- Pydantic 模型 ----------------

class StarCardPayload(BaseModel):
    """全部容忍显式 null（前端表单空字段可能传 null），handler 统一 (x or "") 兜底。

    更新时仅显式提供的字段生效（按 model_fields_set 判定，同 jobs.py LibraryUpdateRequest）。
    """
    title: str | None = Field(default=None, min_length=1)
    role: str | None = None
    tags: str | None = None
    situation: str | None = None
    task: str | None = None
    action: str | None = None
    result: str | None = None


class StarGenerateRequest(BaseModel):
    text: str = Field(max_length=4000, description="项目描述/经历文本（30~4000 字）")
    # 必须允许 None：前端未配置 Key 时显式传 null（dict 严格类型会 422 拒掉整个请求）
    llm_config: dict | None = Field(default=None, description="用户 LLM 配置；空则用服务端默认")


class StarDraft(BaseModel):
    """AI 提炼的 STAR 草稿：全字段带默认值，LLM 输出缺键不炸（缺什么空什么）。"""
    title: str = ""
    role: str = ""
    tags: list[str] = Field(default_factory=list)
    situation: str = ""
    task: str = ""
    action: str = ""
    result: str = ""


STAR_PROMPT = """你是一位资深面试教练。请从用户提供的项目描述/经历文本中提炼一张 STAR 结构化素材卡。

## 用户文本
{text}

## 提炼要求
1. 严格基于用户文本提炼，禁止编造文本中不存在的项目细节、数据指标、公司名称（红线）；文本没覆盖的字段一律留空字符串，不要脑补
2. title：项目/成就的一句话标题（20 字内，如「高并发订单系统性能优化」）
3. role：用户在该项目中担任的角色（如「后端负责人」），文本没提则留空字符串
4. tags：从文本提取的技术栈/能力标签（字符串数组，最多 5 个，如 ["Python", "高并发"]），文本没有则给空数组 []
5. situation / task / action / result：按「情境-任务-行动-结果」四段忠实转述用户文本，中文，可沿用文本原话与数据，不要扩写编造

## 输出 JSON
{{"title": "...", "role": "...", "tags": ["..."], "situation": "...", "task": "...", "action": "...", "result": "..."}}
"""


def _card_dict(r: StarCard) -> dict:
    return {
        "id": r.id,
        "title": r.title,
        "role": r.role,
        "tags": r.tags,
        "situation": r.situation,
        "task": r.task,
        "action": r.action,
        "result": r.result,
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "updated_at": r.updated_at.isoformat() if r.updated_at else None,
    }


@router.get("/cards")
async def list_star_cards(
    db: AsyncSession = Depends(get_db),
    owner_id: str = Depends(get_owner_id),
):
    """素材卡列表（owner 隔离，最近更新在前）。"""
    res = await db.execute(
        select(StarCard)
        .where(StarCard.owner_id == owner_id)
        .order_by(StarCard.updated_at.desc(), StarCard.id.desc())
        .limit(200)
    )
    return {"items": [_card_dict(r) for r in res.scalars().all()]}


@router.post("/cards")
async def create_star_card(
    req: StarCardPayload,
    db: AsyncSession = Depends(get_db),
    owner_id: str = Depends(get_owner_id),
):
    """新建素材卡（title 必填，其余可选；显式 null 一律转空串）。"""
    title = (req.title or "").strip()
    if not title:
        raise HTTPException(status_code=422, detail="标题不能为空")
    rec = StarCard(
        owner_id=owner_id,
        title=title[:_TITLE_MAX],
        role=(req.role or "").strip()[:_ROLE_MAX],
        tags=(req.tags or "").strip()[:_TAGS_MAX],
        situation=(req.situation or "").strip()[:_STAR_TEXT_MAX],
        task=(req.task or "").strip()[:_STAR_TEXT_MAX],
        action=(req.action or "").strip()[:_STAR_TEXT_MAX],
        result=(req.result or "").strip()[:_STAR_TEXT_MAX],
    )
    db.add(rec)
    await db.commit()
    await db.refresh(rec)
    return _card_dict(rec)


@router.put("/cards/{card_id}")
async def update_star_card(
    card_id: int,
    req: StarCardPayload,
    db: AsyncSession = Depends(get_db),
    owner_id: str = Depends(get_owner_id),
):
    """编辑素材卡（仅更新显式提供的字段；清空内容请传空字符串而非 null）。"""
    res = await db.execute(
        select(StarCard).where(StarCard.id == card_id, StarCard.owner_id == owner_id)
    )
    rec = res.scalars().first()
    if not rec:
        raise HTTPException(status_code=404, detail="素材卡不存在")

    fields = req.model_fields_set
    if "title" in fields:
        title = (req.title or "").strip()
        if not title:
            raise HTTPException(status_code=422, detail="标题不能为空")
        rec.title = title[:_TITLE_MAX]
    if "role" in fields:
        rec.role = (req.role or "").strip()[:_ROLE_MAX]
    if "tags" in fields:
        rec.tags = (req.tags or "").strip()[:_TAGS_MAX]
    for field in ("situation", "task", "action", "result"):
        if field in fields:
            setattr(rec, field, (getattr(req, field) or "").strip()[:_STAR_TEXT_MAX])
    # 显式刷 updated_at：server_default 的 CURRENT_TIMESTAMP 只有秒级精度，
    # 同秒内的创建+更新会看不出变化（列表倒序与测试都依赖可观测的更新时间）
    rec.updated_at = datetime.now()
    await db.commit()
    await db.refresh(rec)
    return _card_dict(rec)


@router.delete("/cards/{card_id}")
async def delete_star_card(
    card_id: int,
    db: AsyncSession = Depends(get_db),
    owner_id: str = Depends(get_owner_id),
):
    """删除素材卡（owner 隔离；不存在也是 200 deleted=0，幂等惯例）。"""
    res = await db.execute(
        sa_delete(StarCard).where(StarCard.id == card_id, StarCard.owner_id == owner_id)
    )
    await db.commit()
    return {"deleted": res.rowcount}


@router.post("/generate")
async def generate_star_draft(
    req: StarGenerateRequest,
    owner_id: str = Depends(get_owner_id),
):
    """AI 辅助生成 STAR 草稿（不入库）：从粘贴的项目描述提炼四段结构，前端核对后保存。"""
    text = (req.text or "").strip()
    if len(text) < 30:
        raise HTTPException(status_code=422, detail="项目描述太短，请至少输入 30 字")

    try:
        draft = await call_llm_for_json(
            STAR_PROMPT.format(text=text[:4000]), StarDraft,
            temperature=0.3, llm_config=req.llm_config,
        )
    except Exception as e:
        logger.exception("STAR 草稿生成失败")
        raise HTTPException(502, f"生成失败: {e}") from e

    return {
        "draft": {
            "title": draft.title or "",
            "role": draft.role or "",
            # tags 数组 join 成逗号串，前端直接填表单
            "tags": ",".join(t.strip() for t in (draft.tags or []) if t and t.strip())[:_TAGS_MAX],
            "situation": draft.situation or "",
            "task": draft.task or "",
            "action": draft.action or "",
            "result": draft.result or "",
        }
    }
