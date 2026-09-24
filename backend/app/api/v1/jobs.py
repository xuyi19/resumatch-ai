"""M19 岗位市场 API：一键获取岗位（/jobs/search）+ 按简历智能推荐（/jobs/recommend）。

推荐链路（论文可写）：三方数据 API 拉取 → 关键词重合度粗筛 → LLM 精排（结构化输出，
池内 id 过滤防幻觉）→ LLM 不可用降级为纯关键词排序。
"""

from __future__ import annotations

import inspect
import json
import re

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
from pydantic import BaseModel, Field
from sqlalchemy import delete as sa_delete
from sqlalchemy import select, update as sa_update
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.llm import get_llm
from app.core.db import get_db
from app.core.deps import get_owner_id
from app.models.entities import Resume, SavedJob
from app.services.job_market import (
    MAX_JD_LEN,
    JobItem,
    JobProviderError,
    coarse_rank,
    create_provider,
    parse_llm_ranking,
)

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


class LibraryStatusIn(BaseModel):
    # 容忍显式 null（Pydantic 严格类型会把前端 null 422 的既有教训）
    status: str | None = None


class LibraryStatusBatchIn(BaseModel):
    ids: list[int]
    status: str | None = None


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
        "url": r.url,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }


class LibraryJobIn(BaseModel):
    # 全部容忍显式 null（前端表单空字段可能传 null），handler 统一 (x or "") 兜底
    title: str | None = Field(default=None, min_length=1, max_length=80)
    company: str | None = Field(default=None, max_length=60)
    city: str | None = Field(default=None, max_length=20)
    salary: str | None = Field(default=None, max_length=40)
    jd: str | None = Field(default=None, max_length=_LIBRARY_JD_MAX)
    url: str | None = Field(default=None, max_length=300)


class LibraryAddRequest(BaseModel):
    items: list[LibraryJobIn] = Field(min_length=1, max_length=50)
    source: str = Field(default="manual", max_length=16)
    # 批量导入用：跳过与库内「公司+岗位」重复的条目（返回 skipped 计数）
    skip_duplicates: bool = False


class LibraryUpdateRequest(BaseModel):
    # 全部可选且容忍显式 null（前端编辑框可能传 null），仅更新显式提供的字段
    title: str | None = Field(default=None, min_length=1, max_length=80)
    company: str | None = Field(default=None, max_length=60)
    city: str | None = Field(default=None, max_length=20)
    salary: str | None = Field(default=None, max_length=40)
    jd: str | None = Field(default=None, max_length=_LIBRARY_JD_MAX)
    url: str | None = Field(default=None, max_length=300)


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
    await db.commit()
    return {"updated": res.rowcount}


@router.put("/library/{job_id}/status")
async def update_library_job_status(
    job_id: int,
    req: LibraryStatusIn,
    db: AsyncSession = Depends(get_db),
    owner_id: str = Depends(get_owner_id),
):
    """M49 单条投递状态更新（岗位卡徽标切换）。"""
    status = (req.status or "").strip()
    if status not in _LIBRARY_STATUSES:
        raise HTTPException(status_code=400, detail="无效的投递状态")
    job = await db.get(SavedJob, job_id)
    if not job or job.owner_id != owner_id:
        raise HTTPException(status_code=404, detail="岗位不存在")
    job.status = status
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
    llm_config: dict | None = None


@router.post("/library-generate")
async def generate_library_jobs(
    req: LibraryGenerateRequest,
    db: AsyncSession = Depends(get_db),
    owner_id: str = Depends(get_owner_id),
):
    """AI 自动入库：按简历生成适合的目标岗位（真实公司 + 完整 JD）并直接写入岗位库。

    与库内「公司+岗位」重复的跳过；全部重复时返回空列表 + 提示。
    """
    resume_text = await _resolve_resume_text(req.resume_id, req.resume_text, db, owner_id)

    existing = (
        await db.execute(
            select(SavedJob.company, SavedJob.title).where(SavedJob.owner_id == owner_id)
        )
    ).all()
    seen = {(c.strip().lower(), t.strip().lower()) for c, t in existing}

    try:
        llm = get_llm(
            temperature=0.7,  # 生成任务比精排稍高，提升岗位多样性
            api_key=(req.llm_config or {}).get("api_key"),
            base_url=(req.llm_config or {}).get("base_url"),
            model=(req.llm_config or {}).get("model"),
        )
        prompt = (
            f"你是资深猎头。根据求职者简历，生成 {req.count} 个该候选人高概率投递且匹配的目标岗位。"
            "要求：公司用真实存在的典型企业；每条 JD 为 150-400 字完整岗位描述（工作职责+任职要求）；"
            "城市与薪资符合中国市场行情。严格输出 JSON 数组，不要任何其他内容：\n"
            '[{"title":"...","company":"...","city":"...","salary":"...","jd":"..."}]\n\n'
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
        company = str(row.get("company") or "").strip()
        key = (company.lower(), title.lower())
        if key in seen:  # 与库内已有岗位（公司+岗位名相同）去重
            continue
        seen.add(key)
        city = str(row.get("city") or "").strip()
        jd = str(row.get("jd") or "").strip()
        rec = SavedJob(
            owner_id=owner_id,
            title=title[:80],
            company=company[:60],
            city=city[:20],
            salary=str(row.get("salary") or "").strip()[:40],
            jd_text=(jd or f"{company} {title} 岗位（{city or '城市待定'}）")[:_LIBRARY_JD_MAX],
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


def _rule_parse_batch(raw_text: str) -> list[dict]:
    """无 LLM 降级：按空行拆段，每段第一行当岗位名，整段当 JD（粗但可用）。"""
    segments = [s.strip() for s in re.split(r"\n\s*\n", raw_text) if s.strip()]
    out = []
    for seg in segments[:50]:
        lines = seg.splitlines()
        title = lines[0].strip()[:60]
        out.append({"title": title, "company": "", "city": "", "salary": "", "jd": seg[:_LIBRARY_JD_MAX]})
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
            "salary(薪资)/jd(岗位描述全文，保留原文尽量完整)。文本中没有的信息留空字符串，"
            "不要编造。严格输出 JSON 数组，不要任何其他内容：\n"
            '[{"title":"...","company":"...","city":"...","salary":"...","jd":"..."}]\n\n'
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
