from fastapi import APIRouter
from loguru import logger
from pydantic import BaseModel

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


@router.post("/test-llm")
async def test_llm(req: TestLLMRequest):
    """测试 LLM 连接：发一个最小请求验证"""
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
        return {"success": False, "error": str(e)[:200]}