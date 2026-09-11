import operator
from typing import Annotated, TypedDict


class DiagnosisState(TypedDict, total=False):
    # 输入
    resume_text: str
    jd_text: str
    llm_config: dict

    # 各 Agent 输出
    parsed: dict
    scores: dict
    gaps: list
    suggestions: list
    optimized_resume: dict

    # 追问相关
    clarify_questions: list
    user_answers: dict

    # 控制流
    error: str
    messages: Annotated[list, operator.add]