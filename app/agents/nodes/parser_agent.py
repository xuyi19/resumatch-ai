from pydantic import BaseModel, Field

from app.agents.state import DiagnosisState
from app.agents.utils import call_llm_for_json


class ParsedResume(BaseModel):
    education: list[str] = Field(default_factory=list, description="教育经历列表")
    experience: list[str] = Field(default_factory=list, description="工作经历列表")
    projects: list[str] = Field(default_factory=list, description="项目经历列表")
    skills: list[str] = Field(default_factory=list, description="技能列表")
    summary: str = Field(default="", description="一句话总结候选人画像")


PROMPT = """你是一位资深 HR，负责解析简历结构。

请从下面的简历原文里，提取出：
- education: 教育经历（数组，每项一句话）
- experience: 工作经历（数组，每项一句话）
- projects: 项目经历（数组，每项一句话）
- skills: 技能列表（数组，每项一个技能名）
- summary: 一句话总结候选人画像

简历原文：
{resume_text}
"""


async def run(state: DiagnosisState) -> dict:
    try:
        result = await call_llm_for_json(
            PROMPT.format(resume_text=state["resume_text"]),
            ParsedResume,
            temperature=0.1,
        )
        parsed = result.model_dump()
    except Exception as e:
        return {
            "error": f"解析失败: {e}",
            "parsed": {},
            "messages": [{"role": "parser", "content": f"失败: {e}"}],
        }

    return {
        "parsed": parsed,
        "messages": [{"role": "parser", "content": "解析完成"}],
    }