from app.agents.graph import diagnosis_graph


class DiagnosisService:
    async def diagnose(
        self,
        resume_text: str,
        jd_text: str = "",
        llm_config: dict | None = None,
        on_progress=None,
    ) -> dict:
        initial_state = {
            "resume_text": resume_text,
            "jd_text": jd_text,
            "llm_config": llm_config or {},
            "messages": [],
        }
        final_state = await diagnosis_graph.ainvoke(initial_state)

        if on_progress:
            try:
                on_progress(4, 4, "诊断完成")
            except Exception:
                pass

        return {
            "parsed": final_state.get("parsed", {}),
            "scores": final_state.get("scores", {}),
            "gaps": final_state.get("gaps", []),
            "suggestions": final_state.get("suggestions", []),
            "error": final_state.get("error", ""),
            "messages": final_state.get("messages", []),
        }