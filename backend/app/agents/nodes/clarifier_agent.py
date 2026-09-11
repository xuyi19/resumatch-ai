from pydantic import BaseModel, Field

from app.agents.state import DiagnosisState
from app.agents.utils import call_llm_for_json


class ClarifyQuestion(BaseModel):
    id: str = Field(description="问题编号，如 q1/q2/q3")
    dimension: str = Field(description="对应维度：技能匹配/项目深度/量化成果/经验匹配/行业背景")
    question: str = Field(description="追问正文，必须具体、可回答")
    hint: str = Field(description="回答示例，降低用户门槛")
    placeholder: str = Field(default="请输入具体内容", description="输入框占位符")
    required: bool = Field(default=True, description="是否必答")


class ClarifyResult(BaseModel):
    questions: list[ClarifyQuestion] = Field(default_factory=list)
    reasoning: str = Field(default="", description="为什么问这些")


PROMPT = """你是一位资深求职顾问，正在帮候选人优化简历以匹配目标岗位。

## 原简历
{resume_text}

## 目标岗位 JD
{jd_text}

## 诊断结果
- 评分：{scores}
- 差距：{gaps}

## 你的任务
找出 3-5 个「信息缺口」，生成针对性追问。缺口来源只能是以下三类：
1. 原简历缺失：写了但不够具体（如"优化了性能"没说数字）
2. JD 要求未匹配：JD 要求某项技能，但简历未体现
3. 诊断 gap 项：差距分析里明确指出缺失的

## 追问要求
1. 必须具体：不要问"请介绍一下项目"，要问"该项目处理的数据规模有多大？用了哪些具体方法？"
2. 必须可回答：问的是用户自己知道的信息，不是让他去编
3. 每个问题给示例（hint）：如"如：处理 200 万行交易数据，用 groupby 做聚合"
4. 禁止泛问："请介绍你自己"、"你的优势是什么"这类无效问题
5. 数量控制在 3-5 个
6. 必答/选答区分：核心信息 required=true，锦上添花的 required=false

## 输出 JSON 结构
{{
  "questions": [
    {{
      "id": "q1",
      "dimension": "技能匹配",
      "question": "...",
      "hint": "...",
      "placeholder": "...",
      "required": true
    }}
  ],
  "reasoning": "简要说明为什么问这些"
}}
"""


async def run(state: DiagnosisState) -> dict:
    try:
        result = await call_llm_for_json(
            PROMPT.format(
                resume_text=state.get("resume_text", ""),
                jd_text=state.get("jd_text", "（未提供）"),
                scores=state.get("scores", {}),
                gaps=state.get("gaps", []),
            ),
            ClarifyResult,
            temperature=0.4,
            llm_config=state.get("llm_config"),
        )
        questions = [q.model_dump() for q in result.questions]
    except Exception as e:
        return {
            "error": f"生成追问失败: {e}",
            "clarify_questions": [],
            "messages": [{"role": "clarifier", "content": f"失败: {e}"}],
        }

    return {
        "clarify_questions": questions,
        "messages": [{"role": "clarifier", "content": f"生成 {len(questions)} 个追问"}],
    }