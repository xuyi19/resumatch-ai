# -*- coding: utf-8 -*-
"""M62 Offer 比较决策器：手握多个 Offer 时的加权量化对比。

求职漏斗终点：五维（薪资/通勤/五险/发展/稳定）加权打分 + 排名 + 一句话结论。
红线：纯本地确定性计算，零 LLM 调用——评分与结论全部由模板拼装，不编造任何数据。
"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import delete as sa_delete
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import get_owner_id
from app.models.entities import Offer

router = APIRouter(prefix="/offers", tags=["offers"])

_COMPANY_MAX = 60
_TITLE_MAX = 60
_CITY_MAX = 20
_NOTES_MAX = 500

# 五维评分键与结论用维度名（顺序即平局判定顺序）
SCORE_KEYS = ("salary", "commute", "insurance", "development", "stability")
DIM_NAMES = {
    "salary": "薪资",
    "commute": "通勤",
    "insurance": "五险",
    "development": "发展",
    "stability": "稳定",
}
DEFAULT_WEIGHTS = {"salary": 40, "commute": 15, "insurance": 15, "development": 20, "stability": 10}


# ---------------- Pydantic 模型 ----------------

class OfferPayload(BaseModel):
    """全部容忍显式 null（前端表单空字段可能传 null），handler 统一兜底默认值。

    更新时仅显式提供的字段生效（按 model_fields_set 判定，同 star.py / jobs.py 惯例）。
    """
    company: str | None = None
    title: str | None = None
    city: str | None = None
    monthly_salary: int | None = None
    salary_months: int | None = None
    commute_minutes: int | None = None
    insurance: int | None = None
    development: int | None = None
    stability: int | None = None
    notes: str | None = None


class CompareWeights(BaseModel):
    """对比权重（0~100，不必精确 100，后端归一化）；部分提供时其余项沿用默认值。"""
    salary: int = Field(default=DEFAULT_WEIGHTS["salary"], ge=0, le=100)
    commute: int = Field(default=DEFAULT_WEIGHTS["commute"], ge=0, le=100)
    insurance: int = Field(default=DEFAULT_WEIGHTS["insurance"], ge=0, le=100)
    development: int = Field(default=DEFAULT_WEIGHTS["development"], ge=0, le=100)
    stability: int = Field(default=DEFAULT_WEIGHTS["stability"], ge=0, le=100)


class CompareRequest(BaseModel):
    ids: list[int]
    weights: CompareWeights | None = None


# ---------------- 纯计算函数（便于直测，不等价 HTTP 覆盖） ----------------

def _minmax_scores(values: list[int], reverse: bool = False) -> list[float]:
    """min-max 归一化到 60~100（60 底分防止垫底者显得一无是处）。

    max==min（全同值）时全部 100 分，防止全同薪资时出现 0 分；
    reverse=True 表示值越小分越高（通勤分钟数）。
    """
    lo, hi = min(values), max(values)
    if hi == lo:
        return [100.0] * len(values)

    def _one(v: int) -> float:
        t = (hi - v) / (hi - lo) if reverse else (v - lo) / (hi - lo)
        return round(60 + t * 40, 1)

    return [_one(v) for v in values]


def score_offers(offers: list[dict], weights: dict[str, int | float]) -> list[dict]:
    """五维打分 + 加权总分 + 排名（纯函数）。

    - annual = monthly_salary * salary_months（K 元）
    - salary/commute：参比集内 min-max 归一化到 60~100（commute 反向）
    - insurance/development/stability：(v/5)*100
    - total = Σ(weight_norm * score)，保留 1 位小数，按 total 降序；
      平局时按 annual 降序、id 升序保证确定性
    """
    annuals = [o["monthly_salary"] * o["salary_months"] for o in offers]
    col_scores = {
        "salary": _minmax_scores(annuals),
        "commute": _minmax_scores([o["commute_minutes"] for o in offers], reverse=True),
        "insurance": [round(o["insurance"] / 5 * 100, 1) for o in offers],
        "development": [round(o["development"] / 5 * 100, 1) for o in offers],
        "stability": [round(o["stability"] / 5 * 100, 1) for o in offers],
    }
    total_weight = sum(weights[k] for k in SCORE_KEYS)
    w_norm = {k: weights[k] / total_weight for k in SCORE_KEYS}

    items = []
    for i, o in enumerate(offers):
        scores = {k: col_scores[k][i] for k in SCORE_KEYS}
        total = round(sum(w_norm[k] * scores[k] for k in SCORE_KEYS), 1)
        items.append({
            "id": o["id"],
            "company": o["company"],
            "title": o["title"],
            "city": o["city"],
            "annual": annuals[i],
            "scores": scores,
            "total": total,
        })
    items.sort(key=lambda x: (-x["total"], -x["annual"], x["id"]))
    for rank, it in enumerate(items, 1):
        it["rank"] = rank
    return items


def build_conclusion(items: list[dict], weights: dict[str, int | float]) -> str:
    """结论模板（确定性，禁 LLM）：总分第一 + 年薪最高 + 通勤最短 + 非薪资最高权重维度的最高分者。

    元素按实际数据拼：同一 Offer 不重复点名；数据全同时给综合接近话术；最多三句。
    """
    leader = items[0]

    def _wan(annual_k: int) -> str:
        return f"{annual_k / 10:.1f}"

    # 全部 Offer 的年薪与五维分数完全一致 → 综合接近话术
    if all(
        it["annual"] == leader["annual"]
        and all(it["scores"][k] == leader["scores"][k] for k in SCORE_KEYS)
        for it in items[1:]
    ):
        return f"{len(items)} 个 Offer 综合接近，建议结合团队与业务前景现场感受判断"

    s1 = f"{leader['company']}·{leader['title']} 综合领先（{leader['total']} 分）"
    annual_max = max(items, key=lambda x: (x["annual"], -x["rank"]))
    if annual_max["id"] != leader["id"]:
        s1 += (f"；年薪包最高的是 {annual_max['company']}·{annual_max['title']}"
               f"（{_wan(annual_max['annual'])} 万）")
    else:
        s1 += f"，年薪包最高（{_wan(leader['annual'])} 万）"
    sentences = [s1]

    mentioned = {leader["id"], annual_max["id"]}

    commute_best = max(items, key=lambda x: (x["scores"]["commute"], -x["rank"]))
    if commute_best["id"] not in mentioned:
        sentences.append(f"通勤最短的是 {commute_best['company']}")
        mentioned.add(commute_best["id"])

    non_salary = [k for k in SCORE_KEYS if k != "salary"]
    top_dim = max(non_salary, key=lambda k: weights[k])
    dim_best = max(items, key=lambda x: (x["scores"][top_dim], -x["rank"]))
    if dim_best["id"] not in mentioned:
        name = DIM_NAMES[top_dim]
        care = "成长" if top_dim == "development" else name
        sentences.append(f"若更看重{care}，{dim_best['company']} 的{name}评分最高")

    return "；".join(sentences) + "。"


# ---------------- 序列化 ----------------

def _offer_dict(r: Offer) -> dict:
    return {
        "id": r.id,
        "company": r.company,
        "title": r.title,
        "city": r.city,
        "monthly_salary": r.monthly_salary,
        "salary_months": r.salary_months,
        "commute_minutes": r.commute_minutes,
        "insurance": r.insurance,
        "development": r.development,
        "stability": r.stability,
        "notes": r.notes,
        # 顺手给出年薪包（K 元），前端大数字直接用
        "annual": r.monthly_salary * r.salary_months,
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "updated_at": r.updated_at.isoformat() if r.updated_at else None,
    }


def _int_or_default(value: int | None, default: int, lo: int, hi: int, label: str) -> int:
    """可选整型字段：null → 默认值；越界 422。"""
    if value is None:
        return default
    if not lo <= value <= hi:
        raise HTTPException(status_code=422, detail=f"{label}需在 {lo}~{hi} 之间")
    return value


@router.get("")
async def list_offers(
    db: AsyncSession = Depends(get_db),
    owner_id: str = Depends(get_owner_id),
):
    """Offer 列表（owner 隔离，最近更新在前）。"""
    res = await db.execute(
        select(Offer)
        .where(Offer.owner_id == owner_id)
        .order_by(Offer.updated_at.desc(), Offer.id.desc())
        .limit(200)
    )
    return {"items": [_offer_dict(r) for r in res.scalars().all()]}


@router.post("")
async def create_offer(
    req: OfferPayload,
    db: AsyncSession = Depends(get_db),
    owner_id: str = Depends(get_owner_id),
):
    """新建 Offer（company/title/monthly_salary 必填，其余可选 null → 默认值）。"""
    company = (req.company or "").strip()
    if not company:
        raise HTTPException(status_code=422, detail="公司名称不能为空")
    title = (req.title or "").strip()
    if not title:
        raise HTTPException(status_code=422, detail="岗位名称不能为空")
    monthly = req.monthly_salary
    if monthly is None:
        raise HTTPException(status_code=422, detail="月薪不能为空")
    if not 1 <= monthly <= 500:
        raise HTTPException(status_code=422, detail="月薪需在 1~500 K 之间")

    rec = Offer(
        owner_id=owner_id,
        company=company[:_COMPANY_MAX],
        title=title[:_TITLE_MAX],
        city=(req.city or "").strip()[:_CITY_MAX],
        monthly_salary=monthly,
        salary_months=_int_or_default(req.salary_months, 12, 12, 18, "年薪月数"),
        commute_minutes=_int_or_default(req.commute_minutes, 45, 0, 240, "通勤时间"),
        insurance=_int_or_default(req.insurance, 3, 1, 5, "五险一金评分"),
        development=_int_or_default(req.development, 3, 1, 5, "发展评分"),
        stability=_int_or_default(req.stability, 3, 1, 5, "稳定性评分"),
        notes=(req.notes or "").strip()[:_NOTES_MAX],
    )
    db.add(rec)
    await db.commit()
    await db.refresh(rec)
    return _offer_dict(rec)


@router.put("/{offer_id}")
async def update_offer(
    offer_id: int,
    req: OfferPayload,
    db: AsyncSession = Depends(get_db),
    owner_id: str = Depends(get_owner_id),
):
    """编辑 Offer（仅更新显式提供的字段；显式 null 的可选字段回落默认值）。"""
    res = await db.execute(
        select(Offer).where(Offer.id == offer_id, Offer.owner_id == owner_id)
    )
    rec = res.scalars().first()
    if not rec:
        raise HTTPException(status_code=404, detail="Offer 不存在")

    fields = req.model_fields_set
    if "company" in fields:
        company = (req.company or "").strip()
        if not company:
            raise HTTPException(status_code=422, detail="公司名称不能为空")
        rec.company = company[:_COMPANY_MAX]
    if "title" in fields:
        title = (req.title or "").strip()
        if not title:
            raise HTTPException(status_code=422, detail="岗位名称不能为空")
        rec.title = title[:_TITLE_MAX]
    if "monthly_salary" in fields:
        if req.monthly_salary is None or not 1 <= req.monthly_salary <= 500:
            raise HTTPException(status_code=422, detail="月薪需在 1~500 K 之间")
        rec.monthly_salary = req.monthly_salary
    if "city" in fields:
        rec.city = (req.city or "").strip()[:_CITY_MAX]
    for field, default, lo, hi, label in (
        ("salary_months", 12, 12, 18, "年薪月数"),
        ("commute_minutes", 45, 0, 240, "通勤时间"),
        ("insurance", 3, 1, 5, "五险一金评分"),
        ("development", 3, 1, 5, "发展评分"),
        ("stability", 3, 1, 5, "稳定性评分"),
    ):
        if field in fields:
            setattr(rec, field, _int_or_default(getattr(req, field), default, lo, hi, label))
    if "notes" in fields:
        rec.notes = (req.notes or "").strip()[:_NOTES_MAX]
    # 显式刷 updated_at：server_default 的 CURRENT_TIMESTAMP 只有秒级精度（同 star.py）
    rec.updated_at = datetime.now()
    await db.commit()
    await db.refresh(rec)
    return _offer_dict(rec)


@router.delete("/{offer_id}")
async def delete_offer(
    offer_id: int,
    db: AsyncSession = Depends(get_db),
    owner_id: str = Depends(get_owner_id),
):
    """删除 Offer（owner 隔离；不存在也是 200 deleted=0，幂等惯例）。"""
    res = await db.execute(
        sa_delete(Offer).where(Offer.id == offer_id, Offer.owner_id == owner_id)
    )
    await db.commit()
    return {"deleted": res.rowcount}


@router.post("/compare")
async def compare_offers(
    req: CompareRequest,
    db: AsyncSession = Depends(get_db),
    owner_id: str = Depends(get_owner_id),
):
    """加权对比所选 Offer（2~6 个）：打分 + 排名 + 一句话结论，纯本地计算。"""
    ids = list(dict.fromkeys(req.ids))  # 去重保持顺序
    if len(ids) < 2:
        raise HTTPException(status_code=422, detail="至少选两个 Offer")
    if len(ids) > 6:
        raise HTTPException(status_code=422, detail="最多支持对比 6 个 Offer")

    weights = req.weights.model_dump() if req.weights else dict(DEFAULT_WEIGHTS)
    if sum(weights[k] for k in SCORE_KEYS) <= 0:
        raise HTTPException(status_code=422, detail="权重之和必须大于 0")

    res = await db.execute(
        select(Offer)
        .where(Offer.owner_id == owner_id, Offer.id.in_(ids))
        .order_by(Offer.id)
    )
    offers = [_offer_dict(r) for r in res.scalars().all()]
    if len(offers) < 2:
        raise HTTPException(status_code=422, detail="包含无效或他人 Offer")

    items = score_offers(offers, weights)
    conclusion = build_conclusion(items, weights)
    return {"items": items, "conclusion": conclusion}
