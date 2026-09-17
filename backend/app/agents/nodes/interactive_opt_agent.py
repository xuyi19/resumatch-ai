from pydantic import BaseModel, Field

from app.agents.utils import call_llm_for_json


class InterviewQuestion(BaseModel):
    id: str = Field(description="问题编号 q1/q2/q3")
    dimension: str = Field(description="维度：量化成果/项目深度/技能匹配/经验")
    question: str = Field(description="追问内容")
    hint: str = Field(default="", description="回答示例")
    target_field: str = Field(default="", description="要修改的简历字段")


class QuestionList(BaseModel):
    questions: list[InterviewQuestion] = Field(default_factory=list)


PROMPT = """你是一位资深简历优化顾问。基于简历诊断结果，生成 3-5 个针对性追问，帮助候选人挖掘自身经历。

## 简历原文
{resume_text}

## 目标 JD
{jd_text}

## 诊断差距
{gaps}

## 追问要求
1. 针对诊断差距，找出具体信息缺口（如"缺少量化数据""项目描述太笼统"）
2. 每个问题具体、可回答，不要泛问（禁止"请介绍你自己"）
3. 每个问题给一个回答示例（hint）
4. 标记 target_field：这个答案应该补充到简历的哪个字段（experience/projects/skills/summary）
5. 数量 3-5 个

## 输出 JSON
{{
  "questions": [
    {{
      "id": "q1",
      "dimension": "量化成果",
      "question": "你的项目提到'优化了接口性能'，能补充优化前后的具体数据吗？",
      "hint": "如：响应时间从 800ms 降到 200ms，QPS 从 100 提升到 500",
      "target_field": "experience"
    }}
  ]
}}
"""


async def generate_questions(
    resume_text: str,
    jd_text: str,
    gaps: list,
    llm_config: dict | None = None,
) -> list[dict]:
    result = await call_llm_for_json(
        PROMPT.format(
            resume_text=resume_text,
            jd_text=jd_text,
            gaps=gaps,
        ),
        QuestionList,
        temperature=0.4,
        llm_config=llm_config,
    )
    return [q.model_dump() for q in result.questions]