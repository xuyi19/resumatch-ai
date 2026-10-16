"""M19 岗位市场 API：一键获取岗位（/jobs/search）+ 按简历智能推荐（/jobs/recommend）。

推荐链路（论文可写）：三方数据 API 拉取 → 关键词重合度粗筛 → LLM 精排（结构化输出，
池内 id 过滤防幻觉）→ LLM 不可用降级为纯关键词排序。
"""

from __future__ import annotations

import inspect
import json
import re
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Response
from loguru import logger
from pydantic import BaseModel, Field
from sqlalchemy import delete as sa_delete
from sqlalchemy import select, update as sa_update
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.llm import get_llm
from app.agents.utils import call_llm_for_json
from app.api.v1.settings import get_followup_days
from app.core.config import settings
from app.core.db import get_db
from app.core.deps import get_owner_id
from app.models.entities import Resume, SavedJob, StarCard
from app.services.job_market import (
    MAX_JD_LEN,
    JobItem,
    JobProviderError,
    coarse_rank,
    create_provider,
    parse_llm_ranking,
)
from app.utils.job_links import build_apply_links
from app.utils.keywords import check_coverage, extract_jd_keywords
from app.utils.report_docx import generate_apply_docx


router = APIRouter(prefix="/jobs", tags=["jobs"])


class JobSourceConfig(BaseModel):
    """招聘数据源配置（前端 localStorage 传入，Key 仅存本机）。"""

    provider: str = "mock"
    api_key: str = ""
    api_id: str = ""
    llm_config: dict = Field(default_factory=dict)  # ai 数据源生成岗位画像用


class JobSearchRequest(JobSourceConfig):
    keyword: str = Field(min_length=1, max_length=80)
    city: str = ""
    page: int = Field(default=1, ge=1, le=20)


class JobRecommendRequest(JobSearchRequest):
    # 推荐允许空关键词（仅按简历匹配；外部数据源空关键词时由其报错归因）
    keyword: str = Field(default="", max_length=80)
    resume_text: str = Field(min_length=30, max_length=8000)
    top_n: int = Field(default=10, ge=3, le=30)


async def _provider_search(provider, keyword: str, city: str, page: int):
    """统一调用 Provider.search：同步/异步实现均兼容（AI 数据源为异步）。"""
    result = provider.search(keyword, city, page)
    if inspect.isawaitable(result):
        result = await result
    return result


async def _rank_for_resume(resume_text: str, pool: list, llm_cfg: dict) -> tuple[list[dict], bool]:
    """候选岗位与简历匹配排序：粗筛兜底 + LLM 精排（匹配分 0-100 + 一句话理由）。

    返回 (result, degraded)；LLM 失败/未配置时 degraded=True（关键词重合度排序）。
    """
    ranked = coarse_rank(resume_text, pool)
    result = [
        {**j.to_dict(), "score": round(s * 100), "reason": "关键词重合度排序"}
        for j, s in ranked
    ]

    try:
        llm = get_llm(
            temperature=0.2,
            api_key=llm_cfg.get("api_key"),
            base_url=llm_cfg.get("base_url"),
            model=llm_cfg.get("model"),
        )
        job_lines = "\n".join(
            f'{{"id":"{j.id}","title":"{j.title}","company":"{j.company}",'
            f'"city":"{j.city}","jd":"{j.jd_text[:600]}"}}'
            for j in pool
        )
        prompt = (
            "你是岗位匹配助手。根据求职者简历与候选岗位，为每个岗位打匹配分(0-100整数)"
            "并给一句话推荐理由(≤30字)。只依据文本事实，不要编造。"
            "严格输出 JSON 数组，不要任何其他内容：\n"
            '[{"id":"...","score":85,"reason":"..."}]\n\n'
            f"求职者简历摘要：\n{resume_text[:1500]}\n\n候选岗位：\n{job_lines}"
        )
        resp = await llm.ainvoke(prompt)
        parsed = parse_llm_ranking(resp.content, [j.id for j in pool])
        if parsed:
            score_map = {p["id"]: p for p in parsed}
            result = [
                {
                    **j.to_dict(),
                    "score": score_map[j.id]["score"],
                    "reason": score_map[j.id]["reason"] or "综合匹配",
                }
                for j in pool
                if j.id in score_map
            ]
            result.sort(key=lambda r: r["score"], reverse=True)
            logger.info(f"LLM 精排完成：{len(result)} 个岗位")
            return result, False
    except Exception as e:
        logger.warning(f"LLM 精排失败，降级为关键词排序：{e}")
    return result, True


@router.post("/search")
async def search_jobs(req: JobSearchRequest):
    """按关键词+城市检索岗位（归一化输出）。"""
    try:
        provider = create_provider(req.provider, req.api_key, req.api_id, req.llm_config)
        items, fallback = await _provider_search(provider, req.keyword, req.city, req.page)
        return {"items": [j.to_dict() for j in items], "fallback": fallback}
    except JobProviderError as e:
        logger.warning(f"岗位检索失败[{e.error_type}]：{e}")
        return {"items": [], "fallback": False, "error": e.error_type, "message": str(e)}


@router.post("/recommend")
async def recommend_jobs(req: JobRecommendRequest):
    """按简历推荐：拉取 → 粗筛 → LLM 精排（附匹配分与理由），失败自动降级。"""
    try:
        provider = create_provider(req.provider, req.api_key, req.api_id, req.llm_config)
        items, fallback = await _provider_search(provider, req.keyword, req.city, req.page)
    except JobProviderError as e:
        logger.warning(f"岗位检索失败[{e.error_type}]：{e}")
        return {"items": [], "degraded": False, "error": e.error_type, "message": str(e)}

    if not items:
        return {"items": [], "degraded": False, "message": "未找到匹配岗位，试试更宽泛的关键词"}

    result, degraded = await _rank_for_resume(req.resume_text, items, req.llm_config or {})
    return {
        "items": result[: req.top_n],
        "degraded": degraded,
        "degraded_reason": "AI 精排不可用，已按关键词重合度排序" if degraded else "",
    }


class ImportedJobItem(BaseModel):
    """手动导入的目标公司/岗位（用户自己录入，非外部数据源拉取）。"""

    company: str = Field(min_length=1, max_length=60)
    title: str = Field(min_length=1, max_length=60)
    city: str = Field(default="", max_length=20)
    salary: str = Field(default="", max_length=40)
    jd: str = Field(default="", max_length=2000)


class JobImportMatchRequest(BaseModel):
    """手动导入比对推荐：用户录入公司列表 + 简历 → 匹配排序。"""

    resume_text: str = Field(min_length=30, max_length=8000)
    items: list[ImportedJobItem] = Field(min_length=1, max_length=20)
    llm_config: dict = Field(default_factory=dict)
    top_n: int = Field(default=10, ge=3, le=30)


@router.post("/import-match")
async def import_match_jobs(req: JobImportMatchRequest):
    """手动导入公司比对推荐：用户自己录入的目标公司与岗位，与简历做匹配排序。

    与 /recommend 的区别：候选不来自数据源检索，而是用户逐条录入（仅存本机）；
    JD 缺失时用公司+岗位名拼占位文本，保证粗筛有内容可比。
    """
    items = [
        JobItem(
            id=f"imp-{i}",
            title=it.title,
            company=it.company,
            salary=it.salary,
            city=it.city,
            source="手动导入",
            jd_text=(it.jd.strip() or f"{it.company} {it.title} 岗位（{it.city or '城市待定'}）")[:MAX_JD_LEN],
            url="",
        )
        for i, it in enumerate(req.items)
    ]
    result, degraded = await _rank_for_resume(req.resume_text, items, req.llm_config or {})
    return {
        "items": result[: req.top_n],
        "degraded": degraded,
        "degraded_reason": "AI 精排不可用，已按关键词重合度排序" if degraded else "",
    }


# ============================ M45 岗位库 ============================

_LIBRARY_JD_MAX = 20000
_LIBRARY_SOURCES = ("manual", "ai", "ai_gen", "sample", "favorite")  # M51 favorite=收藏迁移/♡入库
# M49 投递状态机
_LIBRARY_STATUSES = ("wish", "applied", "interviewing", "offer", "closed")
# M56.4 投递台账渠道
_LIBRARY_CHANNELS = ("boss", "zhilian", "liepin", "nowcoder", "email", "other")


class LibraryStatusIn(BaseModel):
    # 容忍显式 null（Pydantic 严格类型会把前端 null 422 的既有教训）
    status: str | None = None
    apply_channel: str | None = None  # M56.4 标记已投递时可附渠道
    apply_resume_id: int | None = None  # D2 版本赛马：首次标记已投递时关联的简历版本


class LibraryStatusBatchIn(BaseModel):
    ids: list[int]
    status: str | None = None


def _parse_dt(value: str | None) -> datetime | None:
    """ISO 字符串 → naive datetime；空/解析失败返回 None（同 backup.py 口径）。"""
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        dt = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt.replace(tzinfo=None) if dt.tzinfo else dt


def _job_dict(r: SavedJob) -> dict:
    return {
        "id": r.id,
        "title": r.title,
        "company": r.company,
        "city": r.city,
        "salary": r.salary,
        "jd": r.jd_text,
        "source": r.source,
        "status": getattr(r, "status", None) or "wish",  # M49 老行缺列时兜底
        # M56.4 投递台账
        "apply_channel": getattr(r, "apply_channel", None),
        "apply_at": r.apply_at.isoformat() if getattr(r, "apply_at", None) else None,
        # D2 版本赛马：投递关联的简历版本
        "apply_resume_id": getattr(r, "apply_resume_id", None),
        # M60 面试日程（编辑弹窗维护；followups 工作台提醒数据源）
        "next_interview_at": (
            r.next_interview_at.isoformat() if getattr(r, "next_interview_at", None) else None
        ),
        "url": r.url,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }


class LibraryJobIn(BaseModel):
    # 全部容忍显式 null（前端表单空字段可能传 null），handler 统一 (x or "") 兜底；
    # 不设 max_length——Boss 等平台链接带 securityId 等参数动辄超 300 字符，
    # 模型层约束会 422 掉整批导入，长度截断由 handler 统一做
    title: str | None = Field(default=None, min_length=1)
    company: str | None = None
    city: str | None = None
    salary: str | None = None
    jd: str | None = None
    url: str | None = None


class LibraryAddRequest(BaseModel):
    items: list[LibraryJobIn] = Field(min_length=1, max_length=50)
    source: str = Field(default="manual", max_length=16)
    # 批量导入用：跳过与库内「公司+岗位」重复的条目（返回 skipped 计数）
    skip_duplicates: bool = False


class LibraryUpdateRequest(BaseModel):
    # 全部可选且容忍显式 null（前端编辑框可能传 null），仅更新显式提供的字段；
    # 长度截断同 LibraryJobIn 由 handler 统一做
    title: str | None = Field(default=None, min_length=1)
    company: str | None = None
    city: str | None = None
    salary: str | None = None
    jd: str | None = None
    url: str | None = None
    # M60 面试日程：ISO 字符串；显式传 null = 清除，不提供 = 不动。null 会被下方
    # exclude_none 丢弃，handler 按 model_fields_set 单独判断「是否提供」
    next_interview_at: str | None = None


class LibraryBatchDeleteRequest(BaseModel):
    ids: list[int]


class LibraryMatchRequest(BaseModel):
    resume_id: int | None = None
    resume_text: str | None = Field(default=None, min_length=30, max_length=8000)
    job_ids: list[int] = Field(default_factory=list)  # 空则全库参与匹配
    top_n: int = Field(default=20, ge=1, le=50)
    llm_config: dict | None = None


@router.get("/library")
async def list_library_jobs(
    db: AsyncSession = Depends(get_db),
    owner_id: str = Depends(get_owner_id),
):
    """岗位库列表（owner 隔离，最新在前，上限 200）。"""
    res = await db.execute(
        select(SavedJob)
        .where(SavedJob.owner_id == owner_id)
        .order_by(SavedJob.id.desc())
        .limit(200)
    )
    return {"items": [_job_dict(r) for r in res.scalars().all()]}


@router.post("/library")
async def add_library_jobs(
    req: LibraryAddRequest,
    db: AsyncSession = Depends(get_db),
    owner_id: str = Depends(get_owner_id),
):
    """添加岗位到库（支持批量；jd 缺失时用公司+岗位占位，保证后续粗筛有内容可比）。"""
    # 批量导入去重：与库内已有「公司+岗位」相同的条目跳过
    existing: set = set()
    if req.skip_duplicates:
        rows = (
            await db.execute(
                select(SavedJob.company, SavedJob.title).where(SavedJob.owner_id == owner_id)
            )
        ).all()
        existing = {(c.strip().lower(), t.strip().lower()) for c, t in rows}

    saved: list[SavedJob] = []
    skipped = 0
    for it in req.items:
        title = (it.title or "").strip()
        if not title:
            raise HTTPException(status_code=422, detail="岗位名不能为空")
        company = (it.company or "").strip()[:60]
        if req.skip_duplicates:
            key = (company.lower(), title.lower())
            if key in existing:
                skipped += 1
                continue
            existing.add(key)
        city = (it.city or "").strip()[:20]
        jd_clean = (it.jd or "").strip()
        rec = SavedJob(
            owner_id=owner_id,
            title=title[:80],
            company=company,
            city=city,
            salary=(it.salary or "").strip()[:40],
            # jd 缺失时用公司+岗位占位，保证后续匹配粗筛有内容可比（同 import-match 惯例）
            jd_text=(jd_clean or f"{company} {title} 岗位（{city or '城市待定'}）")[:_LIBRARY_JD_MAX],
            source=req.source if req.source in _LIBRARY_SOURCES else "manual",
            url=(it.url or "").strip()[:300],
        )
        db.add(rec)
        saved.append(rec)
    if not saved:
        return {"items": [], "skipped": skipped, "message": "导入的岗位均已在库中，未新增"}
    await db.commit()
    for r in saved:
        await db.refresh(r)
    return {"items": [_job_dict(r) for r in saved], "skipped": skipped}


@router.post("/library/batch-delete")
async def delete_library_jobs_batch(
    req: LibraryBatchDeleteRequest,
    db: AsyncSession = Depends(get_db),
    owner_id: str = Depends(get_owner_id),
):
    """批量删除（owner 隔离，幂等）。"""
    if not req.ids:
        return {"deleted": 0}
    res = await db.execute(
        sa_delete(SavedJob).where(SavedJob.id.in_(req.ids), SavedJob.owner_id == owner_id)
    )
    await db.commit()
    return {"deleted": res.rowcount}


@router.put("/library/status-batch")
async def update_library_status_batch(
    req: LibraryStatusBatchIn,
    db: AsyncSession = Depends(get_db),
    owner_id: str = Depends(get_owner_id),
):
    """M49 管理模式批量设置投递状态（owner 隔离）。

    字面路径 /library/status-batch 必须注册在参数路由 /library/{job_id} 之前，
    否则会被 {job_id} 吞掉导致 422（M36 既有教训）。
    """
    status = (req.status or "").strip()
    if status not in _LIBRARY_STATUSES:
        raise HTTPException(status_code=400, detail="无效的投递状态")
    if not req.ids:
        return {"updated": 0}
    res = await db.execute(
        sa_update(SavedJob)
        .where(SavedJob.id.in_(req.ids), SavedJob.owner_id == owner_id)
        .values(status=status)
    )
    if status == "applied":
        # M56.4 批量标记已投递：只为从未投过的岗位落首次投递时间（历史事实不覆盖）
        await db.execute(
            sa_update(SavedJob)
            .where(
                SavedJob.id.in_(req.ids),
                SavedJob.owner_id == owner_id,
                SavedJob.apply_at.is_(None),
            )
            .values(apply_at=datetime.now())
        )
    await db.commit()
    return {"updated": res.rowcount}


@router.put("/library/{job_id}/status")
async def update_library_job_status(
    job_id: int,
    req: LibraryStatusIn,
    db: AsyncSession = Depends(get_db),
    owner_id: str = Depends(get_owner_id),
):
    """M49 单条投递状态更新（岗位卡徽标切换）。M56.4 支持附投递渠道。"""
    status = (req.status or "").strip()
    if status not in _LIBRARY_STATUSES:
        raise HTTPException(status_code=400, detail="无效的投递状态")
    channel = (req.apply_channel or "").strip().lower() or None
    if channel and channel not in _LIBRARY_CHANNELS:
        raise HTTPException(status_code=400, detail="无效的投递渠道")
    job = await db.get(SavedJob, job_id)
    if not job or job.owner_id != owner_id:
        raise HTTPException(status_code=404, detail="岗位不存在")
    job.status = status
    if channel:
        job.apply_channel = channel
    # M56.4 首次标记已投递落时间；转走状态不抹历史，重复标记不覆盖
    if status == "applied" and not job.apply_at:
        job.apply_at = datetime.now()
        # D2 版本赛马：首次投递时关联简历版本（与 apply_at 同口径，不覆盖）
        if req.apply_resume_id:
            job.apply_resume_id = req.apply_resume_id
    await db.commit()
    await db.refresh(job)
    return _job_dict(job)


async def _resolve_resume_text(req_resume_id: int | None, req_resume_text: str | None,
                               db: AsyncSession, owner_id: str) -> str:
    """匹配/生成共用：优先显式 resume_text，否则按 resume_id 查库（owner 校验 404）。"""
    resume_text = (req_resume_text or "").strip()
    if resume_text:
        return resume_text
    if not req_resume_id:
        raise HTTPException(status_code=400, detail="需要 resume_id 或 resume_text 之一")
    res = await db.execute(
        select(Resume).where(Resume.id == req_resume_id, Resume.owner_id == owner_id)
    )
    resume = res.scalars().first()
    if not resume:
        raise HTTPException(status_code=404, detail="简历不存在")
    return resume.raw_text


@router.post("/library-match")
async def match_library_jobs(
    req: LibraryMatchRequest,
    db: AsyncSession = Depends(get_db),
    owner_id: str = Depends(get_owner_id),
):
    """岗位库 × 简历批量匹配推荐：库内岗位（可指定 job_ids）构造候选池，复用 _rank_for_resume 精排。"""
    resume_text = await _resolve_resume_text(req.resume_id, req.resume_text, db, owner_id)

    q = select(SavedJob).where(SavedJob.owner_id == owner_id)
    if req.job_ids:
        q = q.where(SavedJob.id.in_(req.job_ids))
    q = q.order_by(SavedJob.id.desc()).limit(50)
    jobs = (await db.execute(q)).scalars().all()
    if not jobs:
        return {"items": [], "degraded": False, "message": "岗位库为空或未选中岗位，先添加岗位"}

    pool = [
        JobItem(
            id=str(j.id),
            title=j.title,
            company=j.company,
            salary=j.salary,
            city=j.city,
            source=j.source,
            jd_text=(j.jd_text or f"{j.company} {j.title} 岗位（{j.city or '城市待定'}）")[:MAX_JD_LEN],
            url=j.url,
        )
        for j in jobs
    ]
    result, degraded = await _rank_for_resume(resume_text, pool, req.llm_config or {})
    for r in result:
        r["id"] = int(r["id"])  # 池 id 来自库表主键，转回 int 便于前端定位
    return {
        "items": result[: req.top_n],
        "degraded": degraded,
        "degraded_reason": "AI 精排不可用，已按关键词重合度排序" if degraded else "",
    }


def _parse_llm_jobs(content: str, count: int) -> list[dict]:
    """解析生成型 LLM 输出（同 parse_llm_ranking 的围栏剥离 + 截取容错）。"""
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", content.strip(), flags=re.S)
    start, end = text.find("["), text.rfind("]")
    if start == -1 or end == -1:
        return []
    try:
        arr = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return []
    if not isinstance(arr, list):
        return []
    return [r for r in arr if isinstance(r, dict)][:count]


class LibraryGenerateRequest(BaseModel):
    resume_id: int | None = None
    resume_text: str | None = Field(default=None, min_length=30, max_length=8000)
    count: int = Field(default=5, ge=1, le=10)
    city: str | None = Field(default=None, max_length=20)  # 期望城市：传入则统一使用
    llm_config: dict | None = None


@router.post("/library-generate")
async def generate_library_jobs(
    req: LibraryGenerateRequest,
    db: AsyncSession = Depends(get_db),
    owner_id: str = Depends(get_owner_id),
):
    """AI 自动入库：按简历生成适合的目标岗位（岗位名 + 完整 JD）并直接写入岗位库。

    M56 后按用户实测反馈调整：不编造公司名（与实际投递脱节，公司留空由用户
    从真实渠道补填）；城市优先用请求传入的期望城市。与库内同岗位名重复的跳过。
    """
    resume_text = await _resolve_resume_text(req.resume_id, req.resume_text, db, owner_id)

    existing = (
        await db.execute(
            select(SavedJob.company, SavedJob.title).where(SavedJob.owner_id == owner_id)
        )
    ).all()
    seen = {(c.strip().lower(), t.strip().lower()) for c, t in existing}

    want_city = (req.city or "").strip()
    city_rule = f"所有岗位的城市一律使用「{want_city}」" if want_city else (
        "城市取简历中的期望工作城市（未提及则留空字符串）"
    )
    try:
        llm = get_llm(
            temperature=0.7,  # 生成任务比精排稍高，提升岗位多样性
            api_key=(req.llm_config or {}).get("api_key"),
            base_url=(req.llm_config or {}).get("base_url"),
            model=(req.llm_config or {}).get("model"),
        )
        prompt = (
            f"你是资深猎头。根据求职者简历，生成 {req.count} 个该候选人高概率投递且匹配的目标岗位。"
            "要求：\n"
            "1. company 一律输出空字符串（不要编造公司名，真实公司由求职者自行查找填写）；\n"
            f"2. {city_rule}；\n"
            "3. 每条 JD 为 150-400 字完整岗位描述（工作职责+任职要求），岗位方向彼此有差异；\n"
            "4. 薪资符合中国市场行情。\n"
            "严格输出 JSON 数组，不要任何其他内容：\n"
            '[{"title":"...","company":"","city":"...","salary":"...","jd":"..."}]\n\n'
            f"求职者简历：\n{resume_text[:3000]}"
        )
        resp = await llm.ainvoke(prompt)
        rows = _parse_llm_jobs(resp.content, req.count)
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"岗位库 AI 生成失败: {e}")
        raise HTTPException(status_code=502, detail="AI 生成失败，请检查模型配置后重试")
    if not rows:
        raise HTTPException(status_code=502, detail="AI 未返回有效岗位，请重试")

    saved: list[SavedJob] = []
    for row in rows:
        title = str(row.get("title") or "").strip()
        if not title:
            continue
        # 不编造公司（prompt 禁止 + 代码强制清空双保险，LLM 偶尔不听话）；真实公司用户自补
        company = ""
        key = (company.lower(), title.lower())
        if key in seen:  # 与库内已有岗位（公司+岗位名相同）去重
            continue
        seen.add(key)
        # 期望城市硬覆盖（LLM 偶尔不听话输出其他城市）；未传则采信 LLM（取自简历期望城市）
        city = want_city or str(row.get("city") or "").strip()
        jd = str(row.get("jd") or "").strip()
        rec = SavedJob(
            owner_id=owner_id,
            title=title[:80],
            company=company[:60],
            city=city[:20],
            salary=str(row.get("salary") or "").strip()[:40],
            jd_text=(jd or f"{title}（{city or '城市待定'}）")[:_LIBRARY_JD_MAX],
            source="ai_gen",  # 独立于面板入库 'ai'，供前端来源筛选
        )
        db.add(rec)
        saved.append(rec)

    if not saved:
        return {"items": [], "message": "AI 生成的岗位均已在库中，无需重复入库"}
    await db.commit()
    for r in saved:
        await db.refresh(r)
    return {"items": [_job_dict(r) for r in saved]}


_URL_PLATFORMS = [
    ("zhipin.com", "BOSS直聘"),
    ("zhaopin.com", "智联招聘"),
    ("liepin.com", "猎聘"),
    ("nowcoder.com", "牛客"),
]
_URL_RE = re.compile(r"https?://\S+")


def _url_platform(url: str) -> str:
    for domain, name in _URL_PLATFORMS:
        if domain in (url or "").lower():
            return name
    return "岗位链接"


def _rule_parse_batch(raw_text: str) -> list[dict]:
    """无 LLM 降级：按空行拆段，每段第一行当岗位名，整段当 JD（粗但可用）。

    链接感知（M70 配套）：段内含 http(s) 链接时提取到 url 字段（书签采集文本
    的「链接：…」行因此不会污染标题）；文本扣除链接后过短（纯链接粘贴）时，
    尝试从 URL query 参数（query/kw/key）或平台名兜底标题。
    """
    segments = [s.strip() for s in re.split(r"\n\s*\n", raw_text) if s.strip()]
    out = []
    for seg in segments[:50]:
        url = ""
        m = _URL_RE.search(seg)
        if m:
            url = m.group(0).rstrip(")，。、；")
            # 去掉链接所在行（常见「链接：https://...」），余下文本作为标题/JD
            seg = "\n".join(
                ln for ln in seg.splitlines() if not _URL_RE.search(ln)
            ).strip()
        title = seg.splitlines()[0].strip()[:60] if seg else ""
        if not title and url:
            # 纯链接粘贴：尝试 query/kw/key 参数当标题，再退平台名
            fallback = ""
            try:
                from urllib.parse import parse_qs, urlparse

                qs = parse_qs(urlparse(url).query)
                for k in ("query", "kw", "key"):
                    if qs.get(k):
                        fallback = qs[k][0].strip()[:60]
                        break
            except Exception:
                fallback = ""
            title = fallback or f"{_url_platform(url)}岗位（信息待补）"
        if not title:
            continue
        out.append({
            "title": title,
            "company": "",
            "city": "",
            "salary": "",
            "jd": seg[:_LIBRARY_JD_MAX],
            "url": url[:300],
        })
    return out


class LibraryParseRequest(BaseModel):
    raw_text: str = Field(min_length=30, max_length=60000)
    llm_config: dict | None = None


@router.post("/library/parse-batch")
async def parse_library_batch(
    req: LibraryParseRequest,
):
    """批量导入解析：把粘贴的多岗位混排文本交给 LLM 提取为结构化岗位数组（不入库，仅预览）。

    LLM 不可用时降级为按空行拆段（degraded=True 提示前端）。
    """
    try:
        llm = get_llm(
            temperature=0.2,
            api_key=(req.llm_config or {}).get("api_key"),
            base_url=(req.llm_config or {}).get("base_url"),
            model=(req.llm_config or {}).get("model"),
        )
        prompt = (
            "你是岗位信息提取助手。下面的文本里混排了一个或多个招聘岗位（来自招聘网站复制、"
            "JD 列表等）。提取出所有岗位，每条包含 title(岗位名)/company(公司)/city(城市)/"
            "salary(薪资)/jd(岗位描述全文，保留原文尽量完整)/url(文本中出现的 http(s) 岗位链接，"
            "没有则空字符串)。文本中没有的信息留空字符串，"
            "不要编造。严格输出 JSON 数组，不要任何其他内容：\n"
            '[{"title":"...","company":"...","city":"...","salary":"...","jd":"...","url":"..."}]\n\n'
            f"待提取文本：\n{req.raw_text[:15000]}"
        )
        resp = await llm.ainvoke(prompt)
        items = _parse_llm_jobs(resp.content, 50)
        if items:
            return {"items": items, "degraded": False, "degraded_reason": ""}
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"岗位库批量导入 AI 解析失败，降级段落拆分: {e}")

    items = _rule_parse_batch(req.raw_text)
    if not items:
        return {"items": [], "degraded": False, "message": "没有解析出任何内容"}
    return {
        "items": items,
        "degraded": True,
        "degraded_reason": "AI 解析不可用，已按空行段落粗略拆分（第一行作为岗位名）——配置模型后可获得精准解析",
    }


@router.put("/library/{job_id}")
async def update_library_job(
    job_id: int,
    req: LibraryUpdateRequest,
    db: AsyncSession = Depends(get_db),
    owner_id: str = Depends(get_owner_id),
):
    """编辑岗位（仅更新显式提供的字段；清空内容请传空字符串而非 null）。"""
    res = await db.execute(
        select(SavedJob).where(SavedJob.id == job_id, SavedJob.owner_id == owner_id)
    )
    rec = res.scalars().first()
    if not rec:
        raise HTTPException(status_code=404, detail="岗位不存在")

    data = req.model_dump(exclude_none=True)
    if "jd" in data:
        rec.jd_text = data.pop("jd").strip()[:_LIBRARY_JD_MAX]
    limits = {"title": 80, "company": 60, "city": 20, "salary": 40, "url": 300}
    for field, limit in limits.items():
        if field in data:
            setattr(rec, field, data[field].strip()[:limit])
    # M60 面试日程：显式提供才生效（null/空串/非法串 = 清除，ISO 串 = 解析落库）
    if "next_interview_at" in req.model_fields_set:
        rec.next_interview_at = _parse_dt(req.next_interview_at)
    await db.commit()
    await db.refresh(rec)
    return _job_dict(rec)


@router.delete("/library/{job_id}")
async def delete_library_job(
    job_id: int,
    db: AsyncSession = Depends(get_db),
    owner_id: str = Depends(get_owner_id),
):
    """删除单个岗位（owner 隔离）。"""
    res = await db.execute(
        sa_delete(SavedJob).where(SavedJob.id == job_id, SavedJob.owner_id == owner_id)
    )
    await db.commit()
    if res.rowcount == 0:
        raise HTTPException(status_code=404, detail="岗位不存在")
    return {"deleted": res.rowcount}


# ============================ M60 求职跟进 ============================

# 提醒列表上限（工作台卡片空间有限，全量去岗位库看）
_FOLLOWUP_CAP = 10
# 月历全量日程上限（优化⑪）：正常求职远达不到，纯防御
_FOLLOWUP_ALL_CAP = 100


@router.get("/followups")
async def list_followups(
    db: AsyncSession = Depends(get_db),
    owner_id: str = Depends(get_owner_id),
):
    """M60 求职跟进聚合：applied 超 N 天未流转 + 面试日程（工作台「该跟进」卡数据源）。

    状态机驱动：岗位流转到 interviewing/offer/closed 后提醒自然消失，不做 dismiss。
    字面路径 /followups：/jobs 顶层没有参数路由（参数路由都在 /library/ 下，
    /history/stats 吃过的亏这里不存在），注册位置安全。
    """
    days = await get_followup_days(db, owner_id)
    today = datetime.now().date()
    rows = (
        await db.execute(
            select(SavedJob).where(SavedJob.owner_id == owner_id).order_by(SavedJob.id.desc())
        )
    ).scalars().all()

    stale_applies: list[dict] = []
    upcoming: list[dict] = []
    for r in rows:
        # 逾期未流转：仍停留 applied 且距首次投递 >= N 天
        if r.status == "applied" and r.apply_at:
            stale_days = (today - r.apply_at.date()).days
            if stale_days >= days:
                stale_applies.append({
                    "id": r.id,
                    "title": r.title,
                    "company": r.company,
                    "apply_at": r.apply_at.isoformat(),
                    "days": stale_days,
                    "url": r.url,
                    "city": r.city,
                    "salary": r.salary,
                })
        # 面试日程：有安排且未到终态（offer/closed 不再提醒）
        if r.next_interview_at and r.status not in ("offer", "closed"):
            upcoming.append({
                "id": r.id,
                "title": r.title,
                "company": r.company,
                "next_interview_at": r.next_interview_at.isoformat(),
                "status": r.status or "wish",
                "days_left": (r.next_interview_at.date() - today).days,
            })

    stale_applies.sort(key=lambda x: x["days"], reverse=True)  # 最久未流转在前
    upcoming.sort(key=lambda x: x["next_interview_at"])  # 时间正序：逾期最久在最前
    return {
        "days": days,
        "stale_applies": stale_applies[:_FOLLOWUP_CAP],
        "upcoming_interviews": upcoming[:_FOLLOWUP_CAP],
        # 面试日程月历（优化⑪）需要全量日程不被 10 条截断；防御性上限防极端数据撑爆响应
        "upcoming_interviews_all": upcoming[:_FOLLOWUP_ALL_CAP],
    }


# ============================ M72 求职归因 ============================

# 归因最低样本：投递数低于此只给「积累期」提示，不做转化率归因（单用户噪声大，诚实优先）
_ATTR_SAMPLE_MIN = 5
_SEVERITY_RANK = {"high": 0, "medium": 1, "info": 2, "ok": 3}


@router.get("/attribution")
async def job_attribution(
    db: AsyncSession = Depends(get_db),
    owner_id: str = Depends(get_owner_id),
):
    """M72 求职归因：投递漏斗转化率 + 规则归因假设（工作台「🧭 求职归因」卡数据源）。

    口径（在响应与假设文案中如实标注，不做玄学预测）：
    - 已投递 = 曾投过：apply_at 落过时间，或当前状态在 applied/interviewing/offer；
      含投后已结束（closed）——被拒也是投递事实；wish→closed 未投不计；
    - 进入面试 = 当前状态在 interviewing/offer（状态机只存现值，closed 岗位是否
      面过无从回溯，不计数，面试卡点假设文案里如实说明）；
    - 约面率 = 进入面试 / 已投递；Offer 率 = offer / (interviewing + offer)；
    - 停滞 = 仍停留 applied 且距首次投递 >= N 天（与 /followups 同口径，M60）；
    - 归因只产「假设 + 建议动作」，按严重度排序最多 4 条。
    """
    days = await get_followup_days(db, owner_id)
    today = datetime.now().date()
    rows = (
        await db.execute(select(SavedJob).where(SavedJob.owner_id == owner_id))
    ).scalars().all()

    applied = interviewing = offer = closed_after_apply = wish = 0
    stale_days: list[int] = []
    for r in rows:
        st = r.status or "wish"
        if st == "wish":
            wish += 1
        # 曾投过：apply_at 落过时间（历史事实），或状态仍在投递后链路里
        if not (r.apply_at or st in ("applied", "interviewing", "offer")):
            continue
        applied += 1
        if st == "closed":
            closed_after_apply += 1
        elif st in ("interviewing", "offer"):
            interviewing += 1
            if st == "offer":
                offer += 1
        elif st == "applied" and r.apply_at:
            d = (today - r.apply_at.date()).days
            if d >= days:
                stale_days.append(d)

    interview_pool = interviewing  # 含 offer（offer 也曾进面）
    interview_rate = round(interview_pool / applied, 3) if applied else None
    offer_rate = round(offer / interview_pool, 3) if interview_pool else None
    stale_count = len(stale_days)
    stale_avg = round(sum(stale_days) / stale_count, 1) if stale_count else None

    hypotheses: list[dict] = []

    def _add(hid: str, severity: str, title: str, detail: str, *actions: tuple[str, str]):
        hypotheses.append({
            "id": hid,
            "severity": severity,
            "title": title,
            "detail": detail,
            "actions": [{"label": label, "to": to} for label, to in actions],
        })

    def _pct(v: float | None) -> str:
        return f"{round(v * 100)}%" if v is not None else "—"

    if applied < _ATTR_SAMPLE_MIN:
        _add(
            "building_sample", "info", "样本积累期",
            f"已投递 {applied} 份，这个量级的转化率波动很大，归因暂不可靠——先把岗位库投起来，攒够 {_ATTR_SAMPLE_MIN} 份再看诊断。",
            ("去岗位库投递", "/app/jobs"),
        )
    else:
        if interview_rate < 0.10:
            _add(
                "resume_weak", "high", "简历/匹配卡点（强信号）",
                f"投出 {applied} 份仅 {interview_pool} 份进面（约面率 {_pct(interview_rate)}），问题更可能出在简历与岗位的匹配上，而不是面试表现——优先打磨简历与投递针对性。",
                ("做一次简历诊断", "/app/analyze"), ("对照 JD 看差距", "/app/jobs"),
            )
        elif interview_rate < 0.25:
            _add(
                "resume_weak_soft", "medium", "简历还有打磨空间",
                f"约面率 {_pct(interview_rate)} 处于偏下水平（常见水平约 25%+），可针对高频投递方向做一次定向诊断与关键词补齐。",
                ("做一次简历诊断", "/app/analyze"), ("投递前体检", "/app/jobs"),
            )
    if interview_pool >= 3 and offer == 0:
        _add(
            "interview_weak", "high", "面试环节卡点",
            f"进入面试 {interview_pool} 家暂未转化 Offer（已结束岗位是否面过无法回溯，未计入）——投递端反而不差，把精力放在面试准备与复盘上。",
            ("模拟面试复盘", "/app/interview"), ("刷题补短板", "/app/quiz"),
        )
    if stale_count >= 3:
        _add(
            "stale_followup", "medium", "投递跟进掉队",
            f"{stale_count} 条投递超 {days} 天无流转（平均 {stale_avg} 天）——在途的先推进一步，比新增投递更划算。",
            ("去岗位库跟进", "/app/jobs"),
        )
    if wish >= 10 and applied < wish * 0.3:
        _add(
            "wish_hoard", "info", "只收藏不投递",
            f"岗位库躺着 {wish} 个「想投」，实际只投出 {applied} 份——用投递前体检筛一遍，把收藏变成动作。",
            ("去岗位库筛选", "/app/jobs"),
        )
    if offer >= 1:
        _add(
            "positive", "ok", "已有 Offer 入袋",
            f"恭喜，已拿到 {offer} 个 Offer——把成功路径沉淀下来（哪类岗位、哪版简历、哪轮面试），下一个 Offer 复制它。",
            ("复盘成功路径", "/app/history"), ("Offer 比一比", "/app/offers"),
        )

    hypotheses.sort(key=lambda h: _SEVERITY_RANK.get(h["severity"], 9))
    return {
        "days": days,
        "funnel": {
            "applied": applied,
            "interviewing": interviewing,
            "offer": offer,
            "closed_after_apply": closed_after_apply,
            "wish": wish,
        },
        "rates": {
            "interview_rate": interview_rate,
            "offer_rate": offer_rate,
            "stale_count": stale_count,
            "stale_avg_days": stale_avg,
        },
        "hypotheses": hypotheses[:4],
    }


@router.get("/resume-race")
async def resume_race(
    db: AsyncSession = Depends(get_db),
    owner_id: str = Depends(get_owner_id),
):
    """D2 简历版本赛马：按投递时关联的简历分组统计转化，回答「哪版简历更有效」。

    口径与 /attribution 完全一致（曾投 = apply_at 落过时间或状态在投递后链路；
    进面 = interviewing+offer；约面率 = 进面/投递；Offer 率 = offer/进面）。
    诚实原则：未关联简历的投递归「未记录」组如实展示；简历被删除的历史关联
    也归入未记录（无法恢复标题，不编造）；每组投递数低于 _ATTR_SAMPLE_MIN
    标注 sample_ok=False，前端提示样本不足不做结论。
    """
    job_rows = (
        await db.execute(select(SavedJob).where(SavedJob.owner_id == owner_id))
    ).scalars().all()
    resume_rows = (
        await db.execute(select(Resume).where(Resume.owner_id == owner_id))
    ).scalars().all()
    title_map = {r.id: r.filename for r in resume_rows}

    # rid=None 组即「未记录简历」组（含简历已删除的历史关联）
    groups: dict[int | None, dict] = {}
    for r in job_rows:
        st = r.status or "wish"
        if not (r.apply_at or st in ("applied", "interviewing", "offer")):
            continue  # 未投过不参与赛马
        rid = getattr(r, "apply_resume_id", None)
        if rid is not None and rid not in title_map:
            rid = None
        g = groups.setdefault(rid, {"applied": 0, "interviewing": 0, "offer": 0})
        g["applied"] += 1
        if st in ("interviewing", "offer"):
            g["interviewing"] += 1
        if st == "offer":
            g["offer"] += 1

    rows = []
    for rid, g in groups.items():
        rows.append({
            "resume_id": rid,
            "resume_title": title_map.get(rid) if rid is not None else None,
            **g,
            "interview_rate": round(g["interviewing"] / g["applied"], 3) if g["applied"] else None,
            "offer_rate": round(g["offer"] / g["interviewing"], 3) if g["interviewing"] else None,
            "sample_ok": g["applied"] >= _ATTR_SAMPLE_MIN,
        })
    rows.sort(key=lambda x: (x["resume_id"] is not None, -(x["resume_id"] or 0)))
    return {
        "rows": rows,
        "untracked_applied": groups.get(None, {}).get("applied", 0),
        "min_sample": _ATTR_SAMPLE_MIN,
    }


# ============================ M56 投递直达 ============================


@router.get("/library/{job_id}/apply-links")
async def get_apply_links(
    job_id: int,
    db: AsyncSession = Depends(get_db),
    owner_id: str = Depends(get_owner_id),
):
    """M56.1 平台搜索深链：生成 Boss/智联/猎聘/牛客官方搜索页 URL（不抓取数据、不代提交）。"""
    job = await db.get(SavedJob, job_id)
    if not job or job.owner_id != owner_id:
        raise HTTPException(status_code=404, detail="岗位不存在")
    return {"job": _job_dict(job), "links": build_apply_links(job.title, job.company, job.city)}


class ApplyKit(BaseModel):
    """call_llm_for_json 结构化输出契约：仅依据简历与档案生成，禁止编造。"""

    greeting: str = Field(description="BOSS 直聘风格招呼语，不超过 100 字")
    cover_letter: str = Field(description="求职信，300~500 字")
    intro_points: list[str] = Field(default_factory=list, description="自我介绍要点，3~6 条")


class ApplyKitRequest(BaseModel):
    """M56.2 投递材料包请求：resume_id/resume_text 二选一；profile 为统一投递档案（前端本地存储）。

    M65 star_ids：可选引用素材卡（最多 5 张），求职信生成时作为事实依据注入 prompt。
    """

    resume_id: int | None = None
    resume_text: str | None = Field(default=None, min_length=30, max_length=8000)
    profile: str | None = Field(default=None, max_length=1000)
    star_ids: list[int] = Field(default_factory=list, max_length=5)
    llm_config: dict | None = None


@router.post("/library/{job_id}/apply-kit")
async def make_apply_kit(
    job_id: int,
    req: ApplyKitRequest,
    db: AsyncSession = Depends(get_db),
    owner_id: str = Depends(get_owner_id),
):
    """M56.2 AI 投递材料包：按简历+JD 生成招呼语 / 求职信 / 自我介绍要点。

    LLM 失败直接报错不降级（半自动辅助材料宁缺毋假，禁止编造兜底）。
    """
    job = await db.get(SavedJob, job_id)
    if not job or job.owner_id != owner_id:
        raise HTTPException(status_code=404, detail="岗位不存在")
    resume_text = await _resolve_resume_text(req.resume_id, req.resume_text, db, owner_id)

    # M65 素材卡引用：按 owner 过滤查卡（部分无效 id 用命中的卡，全无效 → 404），
    # 拼成事实依据块只供 cover_letter 引用（greeting/intro_points 口径不变）
    star_block = ""
    if req.star_ids:
        cards = (
            await db.execute(
                select(StarCard).where(
                    StarCard.id.in_(req.star_ids), StarCard.owner_id == owner_id
                )
            )
        ).scalars().all()
        if not cards:
            raise HTTPException(status_code=404, detail="引用的素材卡不存在")
        lines = []
        for c in cards:
            segs = [
                f"{label}：{getattr(c, field)}"
                for field, label in (("role", "角色"), ("situation", "情境"),
                                     ("task", "任务"), ("action", "行动"), ("result", "结果"))
                if getattr(c, field)
            ]
            lines.append(f"【{c.title}】" + "；".join(segs))
        star_block = (
            "\n我的项目素材（事实依据，只能引用这些内容，不得扩写编造）：\n"
            + "\n".join(lines) + "\n"
        )

    profile_block = (
        f"\n候选人投递档案（本人真实填写，优先采用）：\n{req.profile.strip()[:1000]}\n"
        if (req.profile or "").strip()
        else ""
    )
    # 素材卡仅影响求职信中段的论证素材来源（禁编造红线不变，强调按素材原文引用）
    cover_letter_req = (
        "cover_letter（求职信 300~500 字：开头点明应聘意向，"
        "中段用简历中的真实事实论证与岗位的匹配度"
        + ("，可引用「我的项目素材」中素材卡的真实项目细节" if star_block else "")
        + "，结尾表达期待面试）；"
    )
    prompt = (
        "你是求职辅导助手。根据候选人简历与目标岗位 JD 生成一份投递材料包。"
        "硬性要求：只使用简历与档案中真实存在的信息，禁止编造任何经历、技能、数字或公司。\n"
        f"内容为三部分：greeting（BOSS 直聘风格招呼语，不超过 100 字，突出与岗位最相关的"
        f"亮点，语气自然不卑不亢）；{cover_letter_req}"
        f"intro_points（自我介绍要点 3~6 条，每条不超过 40 字的短语）。"
        f"{profile_block}{star_block}\n目标岗位：{job.title}（{job.company or '公司未知'}，{job.city or '城市未知'}）\n"
        f"岗位 JD：\n{(job.jd_text or '')[:3000]}\n\n候选人简历：\n{resume_text[:3000]}"
    )
    try:
        kit = await call_llm_for_json(prompt, ApplyKit, temperature=0.5, llm_config=req.llm_config)
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"投递材料包生成失败: {e}")
        raise HTTPException(status_code=502, detail="AI 生成失败，请检查模型配置后重试")

    return {
        "greeting": kit.greeting.strip()[:200],
        "cover_letter": kit.cover_letter.strip()[:2500],
        "intro_points": [p.strip()[:80] for p in kit.intro_points if p.strip()][:6],
    }


class ApplyKitExportRequest(BaseModel):
    """M56.3 材料包导出：内容为材料包区当前展示文本（LLM 结果或用户手改）；resume_id 可选附带简历附录。"""

    greeting: str | None = None
    cover_letter: str | None = None
    intro_points: list[str] | None = None
    resume_id: int | None = None
    # 桌面形态专用：非空即触发服务端直写（M71 起统一写入设置的导出根目录并按类型
    # 分类落盘，本字段的路径值不再使用）；为空走 blob 下载
    save_path: str | None = None


@router.post("/library/{job_id}/export-kit")
async def export_apply_kit(
    job_id: int,
    req: ApplyKitExportRequest,
    db: AsyncSession = Depends(get_db),
    owner_id: str = Depends(get_owner_id),
):
    """M56.3 简历+求职信一键导出材料包 Word（复用导出基建，落 export_history template=apply）。

    save_path 为空：浏览器 blob 下载；非空（仅桌面形态）：M71 统一落盘到设置的
    导出根目录「投递材料包」子目录。
    """
    job = await db.get(SavedJob, job_id)
    if not job or job.owner_id != owner_id:
        raise HTTPException(status_code=404, detail="岗位不存在")
    cover_letter = (req.cover_letter or "").strip()
    if not cover_letter:
        raise HTTPException(status_code=422, detail="求职信内容为空，请先生成材料包")

    resume_text = None
    if req.resume_id:
        resume = (
            await db.execute(
                select(Resume).where(Resume.id == req.resume_id, Resume.owner_id == owner_id)
            )
        ).scalars().first()
        if not resume:
            raise HTTPException(status_code=404, detail="简历不存在")
        resume_text = resume.raw_text

    try:
        data = generate_apply_docx({
            "job": {"title": job.title, "company": job.company,
                    "city": job.city, "salary": job.salary},
            "kit": {"greeting": req.greeting, "cover_letter": cover_letter,
                    "intro_points": req.intro_points or []},
            "resume_text": resume_text,
        })
    except Exception as e:
        logger.warning(f"投递材料包导出失败: {e}")
        raise HTTPException(status_code=500, detail=f"生成失败: {e}")

    safe_title = re.sub(r'[\\/:*?"<>|]', "", job.title).strip()[:30] or "岗位"
    filename = f"投递材料包_{safe_title}_{datetime.now().strftime('%Y%m%d_%H%M')}.docx"

    # 复用简历导出的导出历史记录（同为 .docx 产物）
    from app.api.v1.resume import _record_export
    from app.utils.export_paths import resolve_save_path

    if req.save_path:
        # 桌面形态（M71）：save_path 仅作直写标志，按「导出位置」设置分类落盘
        if settings.APP_MODE == "web":
            raise HTTPException(status_code=403, detail="网页形态不支持服务端落盘")
        target = await resolve_save_path("apply", filename, db, owner_id)
        try:
            target.write_bytes(data)
        except OSError as e:
            raise HTTPException(status_code=500, detail=f"写入文件失败: {e}")
        await _record_export(db, owner_id, target.name, str(target), "apply")
        return {"saved_to": str(target), "save_path": str(target), "filename": target.name}

    await _record_export(db, owner_id, filename, None, "apply")
    from urllib.parse import quote as _quote

    quoted = _quote(filename)
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quoted}",
        },
    )


# ============================ M61 关键词覆盖体检 ============================


class KeywordCheckRequest(BaseModel):
    """M61 投递前体检请求：JD + 简历（resume_id/resume_text 二选一）。

    纯本地词库计算、零 LLM 调用；jd 长度口径与库内 JD 一致（30~20000）。
    """

    jd: str = Field(min_length=30, max_length=20000)
    resume_id: int | None = None
    resume_text: str | None = Field(default=None, min_length=30, max_length=8000)


@router.post("/keyword-check")
async def keyword_check(
    req: KeywordCheckRequest,
    db: AsyncSession = Depends(get_db),
    owner_id: str = Depends(get_owner_id),
):
    """M61 投递前轻量体检：提取 JD 高频技能词，比对简历命中/缺失（纯本地，无 LLM）。

    /jobs 顶层字面路径，无参数路由冲突（参数路由都在 /library/ 下）。
    """
    keywords = extract_jd_keywords(req.jd)
    resume_text = await _resolve_resume_text(req.resume_id, req.resume_text, db, owner_id)
    result = check_coverage(keywords, resume_text)
    return {**result, "total": len(keywords)}


# ============================ M72.1 匹配度分解引擎 ============================


class _MatrixRequirement(BaseModel):
    """单条岗位要求 × 简历证据的匹配判定。证据必须逐字摘自简历原文，禁止编造。"""

    requirement: str = Field(description="岗位要求的一句话概括，不超过 40 字")
    category: str = Field(description="类型：skill(硬技能)|domain(领域/业务)|exp(经验/年限)|edu(学历)|other")
    weight: int = Field(description="重要度 1~5：5=精通/必须/明确年限，3=熟悉/优先，1~2=加分项")
    verdict: str = Field(description="匹配判定：hit(简历有直接证据)|partial(相关但不足)|miss(简历无证据)")
    evidence: str = Field(default="", description="简历原文逐字摘录（不超过 80 字）；miss 时留空")
    gap: str = Field(default="", description="差距说明或一句补强动作建议（不超过 60 字），hit 可留空")


class _MatchMatrix(BaseModel):
    requirements: list[_MatrixRequirement] = Field(description="6~12 条，按 JD 表述重要度排列")


class MatchMatrixRequest(BaseModel):
    """M72.1 匹配矩阵请求：JD + 简历（与 keyword-check 同口径二选一）+ 可选 llm_config。"""

    jd: str = Field(min_length=30, max_length=20000)
    resume_id: int | None = None
    resume_text: str | None = Field(default=None, min_length=30, max_length=8000)
    llm_config: dict | None = None


def _quote_in_text(quote: str, text: str) -> bool:
    """证据回贴校验：归一化全部空白 + 小写后做子串匹配（容忍换行/空格差异，不容忍改写）。"""
    q = re.sub(r"\s+", "", quote or "").lower()
    t = re.sub(r"\s+", "", text or "").lower()
    return bool(q) and q in t


@router.post("/match-matrix")
async def match_matrix(
    req: MatchMatrixRequest,
    db: AsyncSession = Depends(get_db),
    owner_id: str = Depends(get_owner_id),
):
    """M72.1 匹配度分解引擎：LLM 把 JD 拆成逐条要求并在简历中定位证据（可解释矩阵），
    合并 M61 确定性关键词覆盖；纯计算视图零落库。

    防幻觉（对齐诊断链证据接地思路）：LLM 返回的 evidence 逐字回贴简历原文校验，
    校验不过或 hit 无证据 → verdict 降级 partial 并清空证据、标注需人工核对——宁可降级，
    不让编造的证据进矩阵。
    """
    resume_text = await _resolve_resume_text(req.resume_id, req.resume_text, db, owner_id)
    prompt = (
        "你是求职匹配分析引擎。把目标岗位 JD 拆解为具体要求，并逐条在候选人简历中查找证据，"
        "输出可解释的匹配矩阵。硬性规则：\n"
        "1. requirements 拆 6~12 条，覆盖硬技能/领域知识/经验年限/学历等维度；\n"
        "2. weight 按 JD 表述强度给 1~5：「精通/必须/3年以上」=5，「熟悉/了解/优先」=3，「加分项」=1~2；\n"
        "3. evidence 必须是简历原文的逐字摘录（不超过 80 字），禁止改写、概括或编造；"
        "简历中找不到证据就 verdict=miss 且 evidence 留空；\n"
        "4. verdict 三档：hit=简历有直接证据；partial=有相关内容但明显不足；miss=完全无证据；\n"
        "5. gap 用一句话给补强动作建议（如「补充 X 的量化结果」），hit 可留空。\n"
        f"目标岗位 JD：\n{req.jd[:4000]}\n\n候选人简历：\n{resume_text[:4000]}"
    )
    try:
        matrix = await call_llm_for_json(
            prompt, _MatchMatrix, temperature=0.1, llm_config=req.llm_config
        )
    except ValueError as e:  # get_llm：未配置 Key 等配置类错误
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"匹配矩阵生成失败: {e}")
        raise HTTPException(status_code=502, detail="AI 生成失败，请检查模型配置后重试")

    rows: list[dict] = []
    w_sum = 0.0
    v_sum = 0.0
    for r in matrix.requirements[:12]:
        verdict = r.verdict if r.verdict in ("hit", "partial", "miss") else "partial"
        evidence = (r.evidence or "").strip()[:200]
        # 证据接地校验：hit/partial 必须有可回溯的原文证据
        if verdict in ("hit", "partial"):
            if not evidence or not _quote_in_text(evidence, resume_text):
                verdict = "partial"
                evidence = ""
                gap = (r.gap or "").strip() or "证据未能回溯到简历原文，请人工核对"
            else:
                gap = (r.gap or "").strip()
        else:
            gap = (r.gap or "").strip()
        weight = min(max(int(r.weight or 1), 1), 5)
        w_sum += weight
        v_sum += weight * {"hit": 1.0, "partial": 0.5, "miss": 0.0}[verdict]
        rows.append({
            "requirement": (r.requirement or "").strip()[:80],
            "category": (r.category or "other").strip()[:16],
            "weight": weight,
            "verdict": verdict,
            "evidence": evidence,
            "gap": gap[:100],
        })

    if not rows:
        raise HTTPException(status_code=502, detail="AI 未返回有效的匹配矩阵，请重试")

    counts = {
        "hit": sum(1 for x in rows if x["verdict"] == "hit"),
        "partial": sum(1 for x in rows if x["verdict"] == "partial"),
        "miss": sum(1 for x in rows if x["verdict"] == "miss"),
        "total": len(rows),
    }
    keywords = check_coverage(extract_jd_keywords(req.jd), resume_text)
    return {
        "score": round(v_sum / w_sum * 100) if w_sum else 0,
        "counts": counts,
        "rows": rows,
        "keywords": keywords,
    }
