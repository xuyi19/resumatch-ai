import operator
from typing import Annotated, TypedDict


class DiagnosisState(TypedDict, total=False):
    """多智能体诊断的共享状态"""
    # 输入
    resume_text: str
    jd_text: str

    # 各 Agent 输出
    parsed: dict          # 解析 Agent 输出
    scores: dict          # 评分 Agent 输出
    gaps: list            # 差距分析 Agent 输出
    suggestions: list     # 改写建议 Agent 输出

    # 控制流
    error: str
    messages: Annotated[list, operator.add]