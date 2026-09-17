from pydantic import BaseModel, Field

from app.agents.state import DiagnosisState
from app.agents.utils import call_llm_for_json


class JobRequirement(BaseModel):
    hard_skills: list[str] = Field(default_factory=list, description="硬性技术技能")
    soft_skills: list[str] = Field(default_factory=list, description="软技能要求")
    experience_years: str = Field(default="", description="经验要求")
    education: str = Field(default="", description="学历要求")
    keywords: list[str] = Field(default_factory=list, description="核心关键词")
    responsibilities: list[str] = Field(default_factory=list, description="核心职责")


class JobAnalysis(BaseModel):
    requirements: JobRequirement = Field(default_factory=JobRequirement)
    summary: str = Field(default="", description="岗位一句话总结")


PROMPT = """你是一位资深招聘专家。请解析下面的岗位 JD，提取关键要求。

## JD 原文
{jd_text}

## 提取要求
1. hard_skills：硬性技术技能（如 Python、FastAPI、MySQL、Redis）
2. soft_skills：软技能（如沟通能力、团队协作、抗压能力）
3. experience_years：经验要求（如 "3-5年"、"经验不限"）
4. education：学历要求（如 "本科"、"硕士"）
5. keywords：核心关键词（5-10 个，覆盖技术和业务）
6. responsibilities：核心职责（3-5 条，每条一行）

## 输出 JSON
{{
  "requirements": {{
    "hard_skills": [...],
    "soft_skills": [...],
    "experience_years": "...",
    "education": "...",
    "keywords": [...],
    "responsibilities": [...]
  }},
  "summary": "一句话总结岗位核心要求"
}}
"""


async def run(state: DiagnosisState) -> dict:
    jd_text = state.get("jd_text", "")
    if not jd_text:
        return {
            "error": "JD 为空，无法解析",
            "job_analysis": {},
            "messages": [{"role": "job_analyze", "content": "JD 为空"}],
        }

    try:
        result = await call_llm_for_json(
            PROMPT.format(jd_text=jd_text),
            JobAnalysis,
            temperature=0.2,
            llm_config=state.get("llm_config"),
        )
        job_analysis = result.model_dump()
    except Exception as e:
        return {
            "error": f"JD 解析失败: {e}",
            "job_analysis": {},
            "messages": [{"role": "job_analyze", "content": f"失败: {e}"}],
        }

    return {
        "job_analysis": job_analysis,
        "messages": [{"role": "job_analyze", "content": "JD 解析完成"}],
    }