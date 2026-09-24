"""M19 岗位市场 API：一键获取岗位（/jobs/search）+ 按简历智能推荐（/jobs/recommend）。

推荐链路（论文可写）：三方数据 API 拉取 → 关键词重合度粗筛 → LLM 精排（结构化输出，
池内 id 过滤防幻觉）→ LLM 不可用降级为纯关键词排序。
"""

from __future__ import annotations

import inspect

from fastapi import APIRouter
from loguru import logger
from pydantic import BaseModel, Field

from app.agents.llm import get_llm
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
