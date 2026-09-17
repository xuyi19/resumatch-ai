import operator
from typing import Annotated, TypedDict


def _merge_error(existing: str | None, new: str | None) -> str | None:
    """并行分支可能同一步各写一次 error（如 LLM 同时挂掉），保留首个非空值"""
    return existing or new


class DiagnosisState(TypedDict, total=False):
    # 输入
    resume_text: str
    jd_text: str
    llm_config: dict

    # 各 Agent 输出
    parsed: dict
    job_analysis: dict
    scores: dict
    gaps: list
    gap_summary: str
    suggestions: list
    overall_advice: str
    optimized_resume: dict

    # 追问相关
    clarify_questions: list
    user_answers: dict

    # 控制流
    error: Annotated[str | None, _merge_error]
    messages: Annotated[list, operator.add]
