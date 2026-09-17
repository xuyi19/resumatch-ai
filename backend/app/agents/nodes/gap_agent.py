from pydantic import BaseModel, Field

from app.agents.state import DiagnosisState
from app.agents.utils import call_llm_for_json


class GapItem(BaseModel):
    dimension: str = Field(description="差距维度，如'技能'、'经验'、'量化'")
    description: str = Field(description="具体差距描述")
    severity: str = Field(description="严重程度：high/medium/low")


class GapAnalysis(BaseModel):
    gaps: list[GapItem] = Field(default_factory=list, description="差距列表")
    summary: str = Field(default="", description="整体差距总结")


PROMPT = """你是资深技术面试官。下面是候选人简历和一份目标岗位 JD，请对比分析候选人与该岗位的差距。

请从技能、经验年限、项目深度、学历、行业背景、量化成果等维度，找出至少 3 条、最多 6 条差距。
每条差距包含：dimension（维度）、description（具体描述）、severity（严重程度 high/medium/low）。
最后用 summary 给出一句话整体差距总结。

简历：
{resume_text}

目标岗位 JD：
{jd_text}

JD 结构化要求：
{job_analysis}

简历解析：
{parsed}

简历评分：
{scores}
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
                parsed=state.get("parsed", {}),
                scores=state.get("scores", {}),
            ),
            GapAnalysis,
            temperature=0.3,
            llm_config=state.get("llm_config"),
        )
        gaps = [g.model_dump() for g in result.gaps]
        gap_summary = result.summary
    except Exception as e:
        return {
            "error": f"差距分析失败: {e}",
            "messages": [{"role": "gap", "content": f"失败: {e}"}],
        }

    return {
        "gaps": gaps,
        "gap_summary": gap_summary,
        "messages": [{"role": "gap", "content": f"发现 {len(gaps)} 条差距"}],
    }