from pydantic import BaseModel, Field

from app.agents.state import DiagnosisState
from app.agents.utils import call_llm_for_json


class OptimizedResume(BaseModel):
    name: str = Field(default="", description="姓名")
    contact: str = Field(default="", description="联系方式（邮箱/电话）")
    summary: str = Field(default="", description="个人简介，3-5 行")
    education: list[str] = Field(default_factory=list, description="教育经历")
    experience: list[str] = Field(default_factory=list, description="工作经历")
    projects: list[str] = Field(default_factory=list, description="项目经历")
    skills: list[str] = Field(default_factory=list, description="技能列表")


PROMPT = """你是一位资深简历优化专家。基于原简历、诊断报告和改写建议，请生成一份优化后的完整简历。

要求：
1. 保持候选人真实经历，不要编造虚假信息
2. 每条工作经历/项目经历用 STAR 结构（情境-任务-行动-结果），尽量量化
3. 针对目标岗位突出匹配的技能和经历
4. 个人简介 3-5 行，突出核心亮点

输出字段：
- name: 姓名（从原简历提取，没有就留空）
- contact: 联系方式（邮箱/电话，从原简历提取）
- summary: 个人简介（3-5 行）
- education: 教育经历（数组，每项一行）
- experience: 工作经历（数组，每项一行，STAR 结构）
- projects: 项目经历（数组，每项一行，STAR 结构）
- skills: 技能列表（数组，每项一个技能）

原简历：
{resume_text}

目标岗位：
{jd_text}

诊断评分：
{scores}

差距分析：
{gaps}

改写建议：
{suggestions}
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
                suggestions=state.get("suggestions", []),
            ),
            OptimizedResume,
            temperature=0.5,
            llm_config=state.get("llm_config"),
        )
        optimized = result.model_dump()
    except Exception as e:
        return {
            "error": f"简历优化失败: {e}",
            "messages": [{"role": "optimizer", "content": f"失败: {e}"}],
        }

    return {
        "optimized_resume": optimized,
        "messages": [{"role": "optimizer", "content": "优化完成"}],
    }