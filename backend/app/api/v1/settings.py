import inspect

from fastapi import APIRouter
from loguru import logger
from pydantic import BaseModel, Field

from app.agents.llm import get_llm
from app.core.config import settings

router = APIRouter(prefix="/settings", tags=["settings"])


class TestLLMRequest(BaseModel):
    api_key: str
    base_url: str
    model: str


@router.get("/llm-default")
async def llm_default():
    """返回服务端是否已通过 config.json 预置 Key（零配置分发用）。"""
    return {
        "server_key_configured": bool(settings.LLM_API_KEY),
        "base_url": settings.LLM_BASE_URL,
        "model": settings.LLM_MODEL,
    }


def _classify_llm_error(e: Exception) -> str:
    """A6：按错误类型归因为用户可读文案（Key 无效/余额不足/模型名错/网络不通）"""
    s = str(e).lower()
    if "401" in s or "unauthorized" in s or ("invalid" in s and "key" in s):
        return "API Key 无效或已过期，请检查是否复制完整"
    if "402" in s or "insufficient" in s or "balance" in s or "arrears" in s or "余额" in s:
        return "账户余额或免费额度不足，请前往厂商控制台充值后重试"
    if "429" in s or "rate limit" in s:
        return "请求过于频繁或触发限流，请稍后重试"
    if "404" in s or "not found" in s or "not_exist" in s:
        return "Base URL 不正确或模型名不存在，请核对后重试"
    if (
        "timeout" in s
        or "timed out" in s
        or "connection" in s
        or "ssl" in s
        or "network" in s
        or "getaddrinfo" in s
    ):
        return "网络连接失败：请检查网络与代理设置，以及 Base URL 是否可达"
    return f"连接失败：{str(e)[:160]}"


@router.post("/test-llm")
async def test_llm(req: TestLLMRequest):
    """测试 LLM 连接：发一个最小请求验证，按错误类型返回明确文案"""
    if not req.api_key:
        return {"success": False, "error": "缺少 API Key"}

    try:
        llm = get_llm(
            temperature=0,
            api_key=req.api_key,
            base_url=req.base_url,
            model=req.model,
        )
        resp = await llm.ainvoke("回复 OK 两个字母，不要任何其他内容")
        content = resp.content.strip()[:50]
        logger.info(f"LLM 测试成功：{req.model} → {content}")
        return {"success": True, "model": req.model, "response": content}
    except Exception as e:
        logger.warning(f"LLM 测试失败：{e}")
        return {"success": False, "error": _classify_llm_error(e), "raw": str(e)[:200]}


# ================================ M19：招聘数据源测试 ================================


class TestJobRequest(BaseModel):
    provider: str
    api_key: str = ""
    api_id: str = ""
    llm_config: dict = Field(default_factory=dict)  # ai 数据源需要用户模型配置


_JOB_ERROR_TEXT = {
    "invalid_key": "API Key 无效或未授权，请检查 Key 是否复制完整、是否已订阅对应接口",
    "quota": "免费配额已用尽或请求过快，请稍后再试，或前往厂商控制台查看用量",
    "network": "网络连接失败：请检查网络与代理设置",
    "maintenance": "该数据源暂时维护中，请稍后再试或换用其他数据源",
}


@router.post("/test-job")
async def test_job(req: TestJobRequest):
    """测试招聘数据源连接：发一个最小检索请求验证，按错误类型归因"""
    from app.services.job_market import JobProviderError, create_provider

    try:
        provider = create_provider(req.provider, req.api_key, req.api_id, req.llm_config)
        result = provider.search("test", page=1, page_size=3)
        if inspect.isawaitable(result):
            result = await result
        items, _ = result
        return {
            "success": True,
            "provider": provider.name,
            "sample_count": len(items),
            "note": ("示例数据源无需测试" if provider.name == "mock"
                     else "AI 生成数据为岗位参考画像，非实时在招岗位" if provider.name == "ai" else ""),
        }
    except JobProviderError as e:
        logger.warning(f"招聘数据源测试失败[{e.error_type}]：{e}")
        return {
            "success": False,
            "error": _JOB_ERROR_TEXT.get(e.error_type, f"请求失败：{str(e)[:160]}"),
            "raw": str(e)[:200],
        }