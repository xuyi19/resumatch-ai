from langgraph.graph import END, START, StateGraph

from app.agents.nodes import (
    gap_agent,
    optimizer_agent,
    parser_agent,
    rewriter_agent,
    scorer_agent,
)
from app.agents.state import DiagnosisState


def build_diagnosis_graph():
    wf = StateGraph(DiagnosisState)

    wf.add_node("parser", parser_agent.run)
    wf.add_node("scorer", scorer_agent.run)
    wf.add_node("gap", gap_agent.run)
    wf.add_node("rewriter", rewriter_agent.run)
    wf.add_node("optimizer", optimizer_agent.run)

    wf.add_edge(START, "parser")
    wf.add_conditional_edges(
        "parser",
        lambda s: "error" if s.get("error") else "continue",
        {"continue": "scorer", "error": END},
    )
    wf.add_edge("scorer", "gap")
    wf.add_edge("gap", "rewriter")
    wf.add_edge("rewriter", "optimizer")
    wf.add_edge("optimizer", END)

    return wf.compile()


diagnosis_graph = build_diagnosis_graph()