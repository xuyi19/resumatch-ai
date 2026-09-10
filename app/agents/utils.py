import json
import re
from typing import Type, TypeVar

from loguru import logger
from pydantic import BaseModel

from app.agents.llm import get_llm

T = TypeVar("T", bound=BaseModel)

JSON_PATTERN = re.compile(r"\{[\s\S]*\}")


async def call_llm_for_json(
    prompt: str,
    schema: Type[T],
    temperature: float = 0.2,
    max_retries: int = 2,
) -> T:
    """
    调 LLM 并要求返回符合 schema 的 JSON。

    兼容所有 OpenAI 协议模型（DeepSeek / GLM / Ollama 等），
    不依赖 with_structured_output 的 tool calling 能力。
    """
    llm = get_llm(temperature=temperature)

    # 把 schema 描述注入 prompt
    schema_desc = json.dumps(
        schema.model_json_schema(), ensure_ascii=False, indent=2
    )

    full_prompt = f"""{prompt}

请严格返回符合下面 JSON Schema 的 JSON 对象，不要输出任何其他文字、代码块标记或解释。

JSON Schema:
{schema_desc}

直接输出 JSON："""

    last_err: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            resp = await llm.ainvoke(full_prompt)
            content = resp.content if hasattr(resp, "content") else str(resp)
            content = content.strip()

            # 去掉可能的 markdown 代码块标记
            if content.startswith("```"):
                content = re.sub(r"^```(?:json)?\s*", "", content)
                content = re.sub(r"\s*```$", "", content)

            # 用正则兜底，抓第一个完整 JSON 对象
            match = JSON_PATTERN.search(content)
            if match:
                content = match.group(0)

            data = json.loads(content)
            return schema.model_validate(data)

        except Exception as e:
            last_err = e
            logger.warning(f"LLM 返回 JSON 解析失败（第 {attempt + 1} 次）: {e}")
            if attempt < max_retries:
                full_prompt += (
                    "\n\n【重要】上次输出不是合法 JSON，请只输出 JSON，"
                    "不要任何前置说明、代码块标记或后缀解释。"
                )

    raise RuntimeError(f"LLM 结构化输出失败（{max_retries + 1} 次尝试）: {last_err}")