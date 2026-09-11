from pydantic import BaseModel, Field, field_validator

from app.agents.state import DiagnosisState
from app.agents.utils import call_llm_for_json


class ScoreItem(BaseModel):
    score: int = Field(ge=0, le=100, description="0-100 分")
    comment: str = Field(description="简短评语")


class ResumeScores(BaseModel):
    completeness: ScoreItem = Field(description="信息完整性")
    quantification: ScoreItem = Field(description="量化成果程度")
    star_structure: ScoreItem = Field(description="STAR 结构清晰度")
    skill_match: ScoreItem = Field(description="技能含金量")
    achievement: ScoreItem = Field(description="业绩亮点")
    readability: ScoreItem = Field(description="整体可读性")
    overall: int = Field(ge=0, le=100, description="综合评分（整数，不要嵌套对象）")

    @field_validator("overall", mode="before")
    @classmethod
    def coerce_overall(cls, v):
        if isinstance(v, dict):
            return v.get("score", 0)
        return v


PROMPT = """你是一位资深简历评审专家，请对下面的简历从 6 个维度打分，每项 0-100 分，并给出简短评语。

6 个维度：
1. completeness 信息完整性
2. quantification 量化成果程度
3. star_structure STAR 结构清晰度
4. skill_match 技能含金量
5. achievement 业绩亮点
6. readability 整体可读性

每个维度输出格式为 {{"score": 整数, "comment": "评语"}}。

另外单独输出 overall 综合评分，它是一个 0-100 的整数，不要嵌套对象。

返回的 JSON 结构示例：
{{
  "completeness": {{"score": 75, "comment": "..."}},
  "quantification": {{"score": 70, "comment": "..."}},
  "star_structure": {{"score": 65, "comment": "..."}},
  "skill_match": {{"score": 85, "comment": "..."}},
  "achievement": {{"score": 70, "comment": "..."}},
  "readability": {{"score": 80, "comment": "..."}},
  "overall": 74
}}

简历原文：
{resume_text}

候选人画像：
{summary}
"""


async def run(state: DiagnosisState) -> dict:
    if state.get("error"):
        return {}

    summary = state.get("parsed", {}).get("summary", "")
    try:
        result = await call_llm_for_json(
            PROMPT.format(resume_text=state["resume_text"], summary=summary),
            ResumeScores,
            temperature=0.2,
            llm_config=state.get("llm_config"),
        )
        scores = result.model_dump()
    except Exception as e:
        return {
            "error": f"评分失败: {e}",
            "messages": [{"role": "scorer", "content": f"失败: {e}"}],
        }

    return {
        "scores": scores,
        "messages": [{"role": "scorer", "content": f"综合评分 {scores['overall']}"}],
    }