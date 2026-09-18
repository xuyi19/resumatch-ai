from app.agents.graph import diagnosis_graph

# 节点 → 前端展示的阶段名（与 ResultView 的 stages 对齐；refine 为 M6 self-refine 精修）
NODE_STAGES = {
    "parser": "解析简历",
    "job_analyze": "解析岗位",
    "scorer": "六维评分",
    "gap": "差距分析",
    "rewriter": "改写建议",
    "refine": "精修优化",
}


class DiagnosisService:
    async def diagnose(
        self,
        resume_text: str,
        jd_text: str = "",
        llm_config: dict | None = None,
        on_progress=None,
        enable_refine: bool = True,
    ) -> dict:
        initial_state = {
            "resume_text": resume_text,
            "jd_text": jd_text,
            "llm_config": llm_config or {},
            "enable_refine": enable_refine,
            "messages": [],
        }

        total = len(NODE_STAGES)
        completed = 0
        final_state: dict = dict(initial_state)

        # updates 模式逐节点回传，并行分支出结果也会各自上报
        async for chunk in diagnosis_graph.astream(initial_state, stream_mode="updates"):
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
                            on_progress(completed, total, NODE_STAGES[node])
                        except Exception:
                            pass

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
        }
