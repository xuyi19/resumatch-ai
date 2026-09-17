from pydantic import BaseModel, Field

from app.agents.state import DiagnosisState
from app.agents.utils import call_llm_for_json


class OptimizedResume(BaseModel):
    name: str = Field(default="", description="姓名")
    contact: str = Field(default="", description="联系方式")
    summary: str = Field(default="", description="个人简介，3-5 行")
    education: list[str] = Field(default_factory=list, description="教育经历")
    experience: list[str] = Field(default_factory=list, description="工作经历")
    projects: list[str] = Field(default_factory=list, description="项目经历")
    skills: list[str] = Field(default_factory=list, description="技能列表")


PROMPT = """你是一位资深简历优化专家。基于原简历、诊断报告、改写建议、以及用户回答的追问，生成优化后的完整简历。

⚠️ 硬约束（必须遵守）：
1. 只能使用以下来源的信息：原简历内容、用户追问的回答、目标 JD
2. 禁止编造任何数据、项目、公司、技能（如用户没说"提升 60%"，绝对不能写）
3. 每条工作经历/项目经历用 STAR 结构，尽量量化
4. 针对目标岗位突出匹配的技能和经历
5. 个人简介 3-5 行，突出核心亮点

## 用户追问回答（最重要！优先使用这些信息）
{qa_context}

## 原简历
{resume_text}

## 目标岗位
{jd_text}

## 岗位结构化要求
{job_analysis}

## 诊断评分
{scores}

## 差距分析
{gaps}

## 改写建议
{suggestions}

输出字段：name, contact, summary, education, experience, projects, skills
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
                suggestions=state.get("suggestions", []),
                qa_context=(state.get("user_answers") or {}).get("qa_context", "（无追问）"),
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