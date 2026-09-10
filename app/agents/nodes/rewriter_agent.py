from pydantic import BaseModel, Field

from app.agents.state import DiagnosisState
from app.agents.utils import call_llm_for_json


class Suggestion(BaseModel):
    target: str = Field(description="针对哪段内容或哪个差距")
    original: str = Field(default="", description="原文（如有）")
    rewritten: str = Field(description="改写建议（STAR 结构示例）")
    reason: str = Field(description="为什么这样改")


class RewriteResult(BaseModel):
    suggestions: list[Suggestion] = Field(default_factory=list, description="改写建议列表")
    overall_advice: str = Field(default="", description="整体改进建议")


PROMPT = """你是一位简历优化专家。基于下面的简历、目标 JD、评分和差距分析，请给出 3-5 条具体的改写建议。

改写要求：
1. 使用 STAR 结构（情境-任务-行动-结果）
2. 尽量量化（数字、百分比、倍数）
3. 突出与目标岗位 JD 的匹配点

每条建议包含：target（针对哪段）、original（原文）、rewritten（改写后）、reason（为什么）。
最后用 overall_advice 给出一句话整体改进建议。

简历：
{resume_text}

目标 JD：
{jd_text}

评分：
{scores}

差距分析：
{gaps}
"""


async def run(state: DiagnosisState) -> dict:
    if state.get("error"):
        return {}

    try:
        result = await call_llm_for_json(
            PROMPT.format(
                resume_text=state["resume_text"],
                jd_text=state.get("jd_text", "（未提供）"),
                scores=state.get("scores", {}),
                gaps=state.get("gaps", []),
            ),
            RewriteResult,
            temperature=0.5,
            llm_config=state.get("llm_config"),
        )
        suggestions = [s.model_dump() for s in result.suggestions]
        suggestions.append({"overall_advice": result.overall_advice})
    except Exception as e:
        return {
            "error": f"改写建议失败: {e}",
            "messages": [{"role": "rewriter", "content": f"失败: {e}"}],
        }

    return {
        "suggestions": suggestions,
        "messages": [{"role": "rewriter", "content": f"生成 {len(suggestions) - 1} 条建议"}],
    }