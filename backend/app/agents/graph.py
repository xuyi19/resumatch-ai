from langgraph.graph import END, START, StateGraph

from app.agents.nodes import (
    gap_agent,
    job_analyze_agent,
    optimizer_agent,
    parser_agent,
    rewriter_agent,
    scorer_agent,
)
from app.agents.state import DiagnosisState


def build_diagnosis_graph():
    """核心诊断：解析简历 ∥ 解析 JD（并行）→ 评分 → 差距分析 → 改写建议"""
    wf = StateGraph(DiagnosisState)

    wf.add_node("parser", parser_agent.run)
    wf.add_node("job_analyze", job_analyze_agent.run)
    wf.add_node("scorer", scorer_agent.run)
    wf.add_node("gap", gap_agent.run)
    wf.add_node("rewriter", rewriter_agent.run)

    # parser 与 job_analyze 输入独立（简历 / JD），并行执行省一次串行等待
    wf.add_edge(START, "parser")
    wf.add_edge(START, "job_analyze")

    # 任一分支出错即熔断；两个分支写不同 state key，汇合进 scorer 无冲突
    for node in ("parser", "job_analyze"):
        wf.add_conditional_edges(
            node,
            lambda s: "error" if s.get("error") else "continue",
            {"continue": "scorer", "error": END},
        )

    wf.add_edge("scorer", "gap")
    wf.add_edge("gap", "rewriter")
    wf.add_edge("rewriter", END)

    return wf.compile()


def build_optimize_graph():
    wf = StateGraph(DiagnosisState)
    wf.add_node("optimizer", optimizer_agent.run)
    wf.add_edge(START, "optimizer")
    wf.add_edge("optimizer", END)
    return wf.compile()


diagnosis_graph = build_diagnosis_graph()
optimize_graph = build_optimize_graph()
