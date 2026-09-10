from langgraph.graph import END, START, StateGraph

from app.agents.nodes import (
    gap_agent,
    parser_agent,
    rewriter_agent,
    scorer_agent,
)
from app.agents.state import DiagnosisState


def build_diagnosis_graph():
    """构建多智能体诊断 StateGraph"""
    wf = StateGraph(DiagnosisState)

    wf.add_node("parser", parser_agent.run)
    wf.add_node("scorer", scorer_agent.run)
    wf.add_node("gap", gap_agent.run)
    wf.add_node("rewriter", rewriter_agent.run)

    wf.add_edge(START, "parser")

    # 解析成功才继续，否则直接结束
    wf.add_conditional_edges(
        "parser",
        lambda s: "error" if s.get("error") else "continue",
        {"continue": "scorer", "error": END},
    )

    wf.add_edge("scorer", "gap")
    wf.add_edge("gap", "rewriter")
    wf.add_edge("rewriter", END)

    return wf.compile()


diagnosis_graph = build_diagnosis_graph()