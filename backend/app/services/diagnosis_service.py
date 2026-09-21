import asyncio

from langgraph.types import Command

from app.agents.graph import build_diagnosis_graph, build_interactive_diagnosis_graph, diagnosis_graph

# 节点 → 前端展示的阶段名（与 ResultView 的 stages 对齐；refine 为 M6 self-refine 精修）
NODE_STAGES = {
    "parser": "解析简历",
    "job_analyze": "解析岗位",
    "scorer": "六维评分",
    "gap": "差距分析",
    "rewriter": "改写建议",
    "refine": "精修优化",
}

# 交互式图（带 MemorySaver checkpointer，支持 interrupt 动态追问）。
# 桌面单进程场景进程内持久化足够；任务结束统一 delete_thread 释放。
_interactive_graph = None


def _get_interactive_graph():
    global _interactive_graph
    if _interactive_graph is None:
        _interactive_graph = build_interactive_diagnosis_graph()
    return _interactive_graph


def _collect_stream(graph, graph_input, config) -> list:
    """同步流式收集（工作线程内执行）。

    ⚠ interrupt 在 Python 3.10 上只有同步 stream() 可用（async astream 的
    runnable contextvar 不传播，langgraph 要求 3.11+）；异步节点由
    RunnableCallable 在无事件循环的工作线程内自动跑 asyncio.run。
    """
    return list(graph.stream(graph_input, config, stream_mode="updates"))


class DiagnosisService:
    async def diagnose(
        self,
        resume_text: str = "",
        jd_text: str = "",
        llm_config: dict | None = None,
        on_progress=None,
        enable_refine: bool = True,
        thread_id: str | None = None,
        resume_answers: dict | None = None,
        completed_offset: int = 0,
    ) -> dict:
        """运行诊断图。

        - thread_id 为空：离线模式（无 checkpointer），追问只记录不暂停
        - thread_id 非空：交互模式；若 LLM 判定需补充信息，图在 clarify_wait
          interrupt 暂停，返回 waiting=True + questions；用 resume_answers
          （Command(resume)）恢复执行
        - completed_offset：恢复执行时已完成节点数（进度回调续算）
        """
        config = {"configurable": {"thread_id": thread_id}} if thread_id else None

        if resume_answers is not None:
            graph_input = Command(resume=resume_answers)
        else:
            graph_input = {
                "resume_text": resume_text,
                "jd_text": jd_text,
                "llm_config": llm_config or {},
                "enable_refine": enable_refine,
                "messages": [],
            }

        graph = _get_interactive_graph() if thread_id else diagnosis_graph
        base = completed_offset
        completed = 0
        final_state: dict = {}

        if thread_id:
            chunks = await asyncio.to_thread(_collect_stream, graph, graph_input, config)
        else:
            chunks = [
                chunk async for chunk in graph.astream(graph_input, stream_mode="updates")
            ]

        paused = False
        for chunk in chunks:
            if "__interrupt__" in chunk:  # clarify_wait 暂停标记，非节点更新
                paused = True
                continue
            for node, update in chunk.items():
                if not update:  # 缓存命中/空返回的节点
                    continue
                for key, value in update.items():
                    if key == "messages":  # Annotated[add] reducer，手动等价累加
                        final_state.setdefault("messages", []).extend(value)
                    else:
                        final_state[key] = value

                if node in NODE_STAGES:
                    completed += 1
                    if on_progress:
                        try:
                            on_progress(base + completed, len(NODE_STAGES), NODE_STAGES[node])
                        except Exception:
                            pass

        if thread_id:
            # 交互模式：以 checkpointer 快照为准（恢复执行时 updates 只含后半程节点）
            snapshot = graph.get_state(config)
            values = snapshot.values or {}
            for key, value in values.items():
                if key != "messages":  # messages 以流式累加为准（含暂停前后全部）
                    final_state[key] = value
            final_state.setdefault("messages", [])
            paused = paused or bool(snapshot.next)  # 待执行节点非空 → 在 clarify_wait 暂停

        questions = final_state.get("clarify_questions") or []

        return {
            "parsed": final_state.get("parsed", {}),
            "job_analysis": final_state.get("job_analysis", {}),
            "scores": final_state.get("scores", {}),
            "gaps": final_state.get("gaps", []),
            "gap_summary": final_state.get("gap_summary", ""),
            "suggestions": final_state.get("suggestions", []),
            "overall_advice": final_state.get("overall_advice", ""),
            "error": final_state.get("error", ""),
            "messages": final_state.get("messages", []),
            "waiting": paused and bool(questions),
            "clarify_questions": questions,
        }

    async def release_thread(self, thread_id: str):
        """任务终态后释放 checkpointer 内存快照。"""
        try:
            graph = _get_interactive_graph()
            cp = graph.checkpointer
            if hasattr(cp, "adelete_thread"):
                await cp.adelete_thread(thread_id)
            elif hasattr(cp, "delete_thread"):
                await asyncio.to_thread(cp.delete_thread, thread_id)
        except Exception:
            pass
