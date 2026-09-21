import json

from pydantic import BaseModel, Field

from app.agents.state import DiagnosisState
from app.agents.utils import call_llm_for_json


class Suggestion(BaseModel):
    target: str = Field(description="针对哪段内容或哪个差距")
    original: str = Field(default="", description="原文（如有）")
    rewritten: str = Field(description="改写建议（STAR 结构示例）")
    reason: str = Field(description="为什么这样改")
    evidence_ids: list[str] = Field(
        default_factory=list, description="改写所依据的证据块 id（来自差距分析引用）"
    )


class RewriteResult(BaseModel):
    suggestions: list[Suggestion] = Field(default_factory=list, description="改写建议列表")
    overall_advice: str = Field(default="", description="整体改进建议")


PROMPT = """你是一位简历优化专家。基于下面的简历、目标 JD、评分和差距分析，请给出 3-5 条具体的改写建议。

改写要求：
1. 使用 STAR 结构（情境-任务-行动-结果）
2. 尽量量化（数字、百分比、倍数）
3. 突出与目标岗位 JD 的匹配点
4. 严格忠于差距分析中引用的证据原文（evidence 字段），不得凭空编造经历或数据；
   缺少数据时给出「建议补充量化」的占位写法，并为该条建议标注依据的证据块 id

每条建议包含：target（针对哪段）、original（原文）、rewritten（改写后）、reason（为什么）、evidence_ids（依据的证据块 id）。
最后用 overall_advice 给出一句话整体改进建议。

简历：
{resume_text}

目标 JD：
{jd_text}

JD 结构化要求：
{job_analysis}

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
                job_analysis=state.get("job_analysis") or "（未提供）",
                scores=state.get("scores", {}),
                gaps=state.get("gaps", []),
            ),
            RewriteResult,
            temperature=0.5,
            llm_config=state.get("llm_config"),
        )
        suggestions = [s.model_dump() for s in result.suggestions]
        overall_advice = result.overall_advice
    except Exception as e:
        return {
            "error": f"改写建议失败: {e}",
            "messages": [{"role": "rewriter", "content": f"失败: {e}"}],
        }

    return {
        "suggestions": suggestions,
        "overall_advice": overall_advice,
        "messages": [{"role": "rewriter", "content": f"生成 {len(suggestions)} 条建议"}],
    }


# ---------------- self-refine：一轮自我批判精修（可配置开关） ----------------

REFINE_PROMPT = """你是一位严苛的简历评审专家。下面是你此前给出的简历改写建议，请逐条自我批判并修正：
1. 改写内容是否忠实于原简历事实（不得凭空编造经历或数据；缺数据时给出"建议补充量化"的占位写法）
2. 是否紧扣目标 JD 的关键要求
3. STAR 结构是否完整、表述是否简洁专业
4. 条目之间是否重复

有问题就修正该条；价值不大的条目可删除；最多保留 5 条。输出修正后的完整建议列表。

简历：
{resume_text}

目标 JD：
{jd_text}

当前建议（JSON）：
{suggestions}

整体建议：
{overall_advice}
"""


async def refine(state: DiagnosisState) -> dict:
    """对 rewriter 输出做一轮自我批判修正；失败/为空时保留原建议，不熔断主流程。"""
    if state.get("error"):
        return {}

    suggestions = state.get("suggestions") or []
    if not suggestions:
        return {}

    try:
        result = await call_llm_for_json(
            REFINE_PROMPT.format(
                resume_text=state["resume_text"],
                jd_text=state.get("jd_text", "（未提供）"),
                suggestions=json.dumps(suggestions, ensure_ascii=False, indent=2),
                overall_advice=state.get("overall_advice", ""),
            ),
            RewriteResult,
            temperature=0.3,
            llm_config=state.get("llm_config"),
        )
        refined = [s.model_dump() for s in result.suggestions]
    except Exception as e:
        return {
            "messages": [{"role": "refine", "content": f"精修失败，保留原建议: {e}"}],
        }

    if not refined:
        return {
            "messages": [{"role": "refine", "content": "精修未产出有效建议，保留原建议"}],
        }

    return {
        "suggestions": refined,
        "overall_advice": result.overall_advice or state.get("overall_advice", ""),
        "messages": [{"role": "refine", "content": f"精修后保留 {len(refined)} 条建议"}],
    }