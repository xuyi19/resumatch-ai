import asyncio

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from app.agents.nodes import (
    clarify_agent,
    gap_agent,
    job_analyze_agent,
    optimizer_agent,
    parser_agent,
    rewriter_agent,
    scorer_agent,
)
from app.agents.state import DiagnosisState


def _sync_node(fn):
    """把 async 节点包装成同步函数（在工作线程内 asyncio.run 执行）。

    用于交互式图：interrupt() 的 runnable contextvar 在 Python 3.10 的
    async 图中不可用（langgraph 要求 3.11+），交互图必须走同步 stream()。
    """

    def _run(state):
        return asyncio.run(fn(state))

    return _run


def _build_diagnosis_wf(interactive: bool) -> StateGraph:
    """组装诊断图节点与边；interactive=True 时节点用同步包装。"""
    wrap = _sync_node if interactive else (lambda fn: fn)

    wf = StateGraph(DiagnosisState)
    wf.add_node("parser", wrap(parser_agent.run))
    wf.add_node("job_analyze", wrap(job_analyze_agent.run))
    wf.add_node("scorer", wrap(scorer_agent.run))
    wf.add_node("gap", wrap(gap_agent.run))
    wf.add_node("clarify_plan", wrap(clarify_agent.plan))
    # interrupt 所在节点必须原生同步（配合同步 stream 的 runnable context）
    wf.add_node("clarify_wait", clarify_agent.wait)
    wf.add_node("rewriter", wrap(rewriter_agent.run))

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
    wf.add_edge("gap", "clarify_plan")
    # 无问题 → 直接改写；有问题 → wait 节点 interrupt 等待用户回答（M11-B 动态追问）
    wf.add_conditional_edges(
        "clarify_plan",
        lambda s: "wait" if s.get("clarify_questions") else "continue",
        {"wait": "clarify_wait", "continue": "rewriter"},
    )
    wf.add_edge("clarify_wait", "rewriter")

    # self-refine（M6）：rewriter 后追加一轮自我批判精修，enable_refine=False 时跳过；
    # refine 自身失败只记日志不熔断，保留一轮改写结果即可
    wf.add_node("refine", wrap(rewriter_agent.refine))
    wf.add_conditional_edges(
        "rewriter",
        lambda s: "refine" if (s.get("enable_refine", True) and not s.get("error")) else "end",
        {"refine": "refine", "end": END},
    )
    wf.add_edge("refine", END)
    return wf


def build_diagnosis_graph(checkpointer: MemorySaver | None = None):
    """核心诊断：解析简历 ∥ 解析 JD（并行）→ 评分 → 差距分析 → 动态追问 → 改写建议

    checkpointer 传入时启用 interrupt 式动态追问（人在回路，M11-B）；
    None 时追问节点只记录问题不暂停（离线/测试链路）。
    """
    return _build_diagnosis_wf(interactive=False).compile(checkpointer=checkpointer)


def build_interactive_diagnosis_graph():
    """交互式诊断图：同步节点 + MemorySaver，支持 interrupt 暂停等待用户补充信息。

    调用方需在 asyncio.to_thread 中用同步 stream()/invoke() 驱动（见 diagnosis_service）。
    """
    return _build_diagnosis_wf(interactive=True).compile(checkpointer=MemorySaver())


def build_optimize_graph():
    wf = StateGraph(DiagnosisState)
    wf.add_node("optimizer", optimizer_agent.run)
    wf.add_edge(START, "optimizer")
    wf.add_edge("optimizer", END)
    return wf.compile()


diagnosis_graph = build_diagnosis_graph()
optimize_graph = build_optimize_graph()
