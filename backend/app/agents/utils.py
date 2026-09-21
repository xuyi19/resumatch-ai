import json
import re
from typing import Type, TypeVar

from loguru import logger
from pydantic import BaseModel

from app.agents.llm import get_llm

T = TypeVar("T", bound=BaseModel)


def _extract_first_json(text: str) -> str | None:
    """按括号平衡提取首个完整 JSON 对象（字符串感知），忽略前后缀说明文字。

    旧的正则贪婪匹配（首 { 到尾 }）在模型输出「JSON + 后缀解释」时会把
    解释一起吞进去导致 Extra data 解析失败并触发整轮重试。
    """
    start = text.find("{")
    while start != -1:
        depth = 0
        in_str = False
        esc = False
        for i in range(start, len(text)):
            ch = text[i]
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
            elif ch == '"':
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return text[start : i + 1]
        start = text.find("{", start + 1)
    return None


async def call_llm_for_json(
    prompt: str,
    schema: Type[T],
    temperature: float = 0.2,
    max_retries: int = 2,
    llm_config: dict | None = None,
) -> T:
    """
    调 LLM 并要求返回符合 schema 的 JSON。
    llm_config: {"api_key": ..., "base_url": ..., "model": ...}，None 表示用 .env 默认配置
    """
    llm_config = llm_config or {}
    llm = get_llm(
        temperature=temperature,
        api_key=llm_config.get("api_key"),
        base_url=llm_config.get("base_url"),
        model=llm_config.get("model"),
    )

    schema_desc = json.dumps(schema.model_json_schema(), ensure_ascii=False, indent=2)

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

            if content.startswith("```"):
                content = re.sub(r"^```(?:json)?\s*", "", content)
                content = re.sub(r"\s*```$", "", content)

            extracted = _extract_first_json(content)
            if extracted is None:
                raise ValueError("响应中未找到 JSON 对象")
            data = json.loads(extracted)
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