from functools import lru_cache

from langchain_openai import ChatOpenAI

from app.core.config import settings


@lru_cache(maxsize=1)
def get_llm(temperature: float = 0.3) -> ChatOpenAI:
    """返回一个配置好的 ChatOpenAI 实例（走 DeepSeek/智谱的 OpenAI 兼容接口）"""
    return ChatOpenAI(
        model=settings.LLM_MODEL,
        api_key=settings.LLM_API_KEY,
        base_url=settings.LLM_BASE_URL,
        temperature=temperature,
        timeout=60,
        max_retries=2,
    )