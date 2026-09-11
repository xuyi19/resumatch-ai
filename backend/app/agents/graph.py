from langgraph.graph import END, START, StateGraph

from app.agents.nodes import (
    clarifier_agent,
    gap_agent,
    optimizer_agent,
    parser_agent,
    rewriter_agent,
    scorer_agent,
)
from app.agents.state import DiagnosisState


def build_diagnosis_graph():
    """核心诊断流程：4 个 Agent"""
    wf = StateGraph(DiagnosisState)

    wf.add_node("parser", parser_agent.run)
    wf.add_node("scorer", scorer_agent.run)
    wf.add_node("gap", gap_agent.run)
    wf.add_node("rewriter", rewriter_agent.run)

    wf.add_edge(START, "parser")
    wf.add_conditional_edges(
        "parser",
        lambda s: "error" if s.get("error") else "continue",
        {"continue": "scorer", "error": END},
    )
    wf.add_edge("scorer", "gap")
    wf.add_edge("gap", "rewriter")
    wf.add_edge("rewriter", END)

    return wf.compile()


def build_clarifier_graph():
    """生成追问（独立图）"""
    wf = StateGraph(DiagnosisState)
    wf.add_node("clarifier", clarifier_agent.run)
    wf.add_edge(START, "clarifier")
    wf.add_edge("clarifier", END)
    return wf.compile()


def build_optimize_graph():
    """生成优化简历（独立图）"""
    wf = StateGraph(DiagnosisState)
    wf.add_node("optimizer", optimizer_agent.run)
    wf.add_edge(START, "optimizer")
    wf.add_edge("optimizer", END)
    return wf.compile()


diagnosis_graph = build_diagnosis_graph()
clarifier_graph = build_clarifier_graph()
optimize_graph = build_optimize_graph()