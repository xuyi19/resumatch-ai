from langchain_openai import ChatOpenAI

from app.core.config import settings


def get_llm(
    temperature: float = 0.3,
    api_key: str | None = None,
    base_url: str | None = None,
    model: str | None = None,
) -> ChatOpenAI:
    """
    返回 ChatOpenAI 实例。
    优先使用传入的参数（用户自定义配置），未提供则回退到 .env 里的全局配置。
    """
    final_key = api_key or settings.LLM_API_KEY
    final_base = base_url or settings.LLM_BASE_URL
    final_model = model or settings.LLM_MODEL

    if not final_key:
        raise ValueError("未配置 LLM API Key，请在设置中填写，或联系管理员")

    return ChatOpenAI(
        model=final_model,
        api_key=final_key,
        base_url=final_base,
        temperature=temperature,
        timeout=60,
        max_retries=2,
    )