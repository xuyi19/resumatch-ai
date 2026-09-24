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

# 交互式图（带 SqliteSaver checkpointer，支持 interrupt 动态追问，M16 起跨重启可恢复）。
# 任务结束统一 delete_thread 释放快照；快照库初始化失败时图内部降级 MemorySaver。
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


class DiagnosisPartialError(Exception):
    """B1：诊断中断但已有部分结果（失败保留部分结果）。

    partial 为已完成节点的结果摘要（scores/gaps/suggestions 等非空项），
    cause 为原始异常。仅在交互模式（有 checkpointer）下产生。
    """

    def __init__(self, partial: dict, cause: Exception):
        self.partial = partial
        self.cause = cause
        super().__init__(str(cause))


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

        if thread_id:
            try:
                return await self._run_interactive(graph, graph_input, config,
                                                   base=completed_offset,
                                                   on_progress=on_progress)
            except DiagnosisPartialError:
                raise
            except Exception as e:
                # B1：图执行中断 → 从 checkpointer 快照恢复已完成节点结果
                partial = self._partial_from_snapshot(graph, config)
                raise DiagnosisPartialError(partial, e) from e

        # 离线模式（无 checkpointer）：失败无部分结果可救
        chunks = [chunk async for chunk in graph.astream(graph_input, stream_mode="updates")]
        final_state: dict = {}
        completed = 0
        for chunk in chunks:
            if "__interrupt__" in chunk:
                continue
            for node, update in chunk.items():
                if not update:
                    continue
                for key, value in update.items():
                    if key == "messages":
                        final_state.setdefault("messages", []).extend(value)
                    else:
                        final_state[key] = value
                if node in NODE_STAGES:
                    completed += 1
                    if on_progress:
                        try:
                            on_progress(completed, len(NODE_STAGES), NODE_STAGES[node])
                        except Exception:
                            pass
        return self._extract(final_state, paused=False)

    async def _run_interactive(self, graph, graph_input, config, base=0, on_progress=None) -> dict:
        """交互模式：流式收集 + 快照补全 + 组装（diagnose 与断点续跑共用）。"""
        chunks = await asyncio.to_thread(_collect_stream, graph, graph_input, config)
        completed = 0
        final_state: dict = {}
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

        # 以 checkpointer 快照为准（恢复执行时 updates 只含后半程节点）
        snapshot = graph.get_state(config)
        values = snapshot.values or {}
        for key, value in values.items():
            if key != "messages":  # messages 以流式累加为准（含暂停前后全部）
                final_state[key] = value
        final_state.setdefault("messages", [])
        paused = paused or bool(snapshot.next)  # 待执行节点非空 → 在 clarify_wait 暂停

        return self._extract(final_state, paused=paused)

    @staticmethod
    def _extract(final_state: dict, paused: bool) -> dict:
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

    def _partial_from_snapshot(self, graph, config) -> dict:
        """B1：从 checkpointer 快照提取已完成节点的非空结果。"""
        try:
            values = graph.get_state(config).values or {}
        except Exception:
            return {}
        partial = {}
        for key in ("scores", "gaps", "gap_summary", "suggestions",
                    "overall_advice", "job_analysis", "parsed"):
            value = values.get(key)
            if value:
                partial[key] = value
        return partial

    def has_checkpoint(self, thread_id: str) -> bool:
        """B1：判断该任务是否有可恢复的 graph 快照（重试前置校验）。"""
        return self.snapshot_values(thread_id) is not None

    def snapshot_values(self, thread_id: str) -> dict | None:
        """B1：取 graph 快照 values（无快照返回 None），供重试时恢复上下文。"""
        graph = _get_interactive_graph()
        try:
            snapshot = graph.get_state({"configurable": {"thread_id": thread_id}})
            return dict(snapshot.values) if snapshot.values else None
        except Exception:
            return None

    async def resume_after_error(self, thread_id: str, on_progress=None) -> dict:
        """B1：失败任务从 checkpointer 断点续跑（input=None），不重跑已完成节点。"""
        graph = _get_interactive_graph()
        config = {"configurable": {"thread_id": thread_id}}
        # 断点续跑与首跑共用收集逻辑；异常同样转 DiagnosisPartialError
        try:
            return await self._run_interactive(graph, None, config)
        except DiagnosisPartialError:
            raise
        except Exception as e:
            partial = self._partial_from_snapshot(graph, config)
            raise DiagnosisPartialError(partial, e) from e

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
