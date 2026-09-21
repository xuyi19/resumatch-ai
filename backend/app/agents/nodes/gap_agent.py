from pydantic import BaseModel, Field

from app.agents.state import DiagnosisState
from app.agents.utils import call_llm_for_json
from app.core.evidence import filter_valid_ids, render_pool, retrieval_pool


class GapItem(BaseModel):
    dimension: str = Field(description="差距维度，如'技能'、'经验'、'量化'")
    description: str = Field(description="具体差距描述")
    severity: str = Field(description="严重程度：high/medium/low")
    evidence_ids: list[str] = Field(
        default_factory=list,
        description="支撑该差距判断的证据块 id（来自证据池）；无从引用则留空",
    )
    is_inferred: bool = Field(
        default=False, description="true 表示该差距为无证据支撑的推断"
    )


class GapAnalysis(BaseModel):
    gaps: list[GapItem] = Field(default_factory=list, description="差距列表")
    summary: str = Field(default="", description="整体差距总结")


PROMPT = """你是资深技术面试官。下面是候选人简历和一份目标岗位 JD，请对比分析候选人与该岗位的差距。

请从技能、经验年限、项目深度、学历、行业背景、量化成果等维度，找出至少 3 条、最多 6 条差距。
每条差距包含：
- dimension（维度）、description（具体描述）、severity（严重程度 high/medium/low）
- evidence_ids：从下方证据池中引用与该差距判断相关的证据块 id（1-3 个）。
  例：「缺少量化数据」这类差距应引用最能体现该问题的证据块；完全找不到可引用的证据时留空数组并置 is_inferred=true
- is_inferred：判断是否为缺乏证据支撑的推断
- 严禁编造证据 id：只能引用证据池中真实存在的 id；证据池为空或没有相关证据时，
  evidence_ids 一律留空数组且 is_inferred=true

最后用 summary 给出一句话整体差距总结。

简历：
{resume_text}

目标岗位 JD：
{jd_text}

JD 结构化要求：
{job_analysis}

简历解析：
{parsed}

简历评分：
{scores}

证据池（简历/JD 原文块，按与岗位要求的相关度检索）：
{evidence_pool}
"""


async def run(state: DiagnosisState) -> dict:
    if state.get("error"):
        return {}

    index = state.get("evidence_index") or {"chunks": []}
    try:
        # RAG：以 JD 原文块为查询，交叉检索简历相关证据，构成差距分析证据池
        jd_queries = [c["text"] for c in index.get("chunks", []) if c["id"].startswith("J")]
        pool = await retrieval_pool(index, jd_queries, k_per_query=2, cap=10)

        result = await call_llm_for_json(
            PROMPT.format(
                resume_text=state["resume_text"],
                jd_text=state.get("jd_text", "（未提供）"),
                job_analysis=state.get("job_analysis") or "（未提供）",
                parsed=state.get("parsed", {}),
                scores=state.get("scores", {}),
                evidence_pool=render_pool(pool),
            ),
            GapAnalysis,
            temperature=0.3,
            llm_config=state.get("llm_config"),
        )
        by_id = {c["id"]: c["text"] for c in index.get("chunks", [])}
        gaps = []
        for g in result.gaps:
            item = g.model_dump()
            valid = filter_valid_ids(index, item.get("evidence_ids") or [])
            item["evidence"] = [{"id": i, "text": by_id[i]} for i in valid]
            item["evidence_ids"] = valid
            if not valid:
                item["is_inferred"] = True
            gaps.append(item)
        gap_summary = result.summary
    except Exception as e:
        return {
            "error": f"差距分析失败: {e}",
            "messages": [{"role": "gap", "content": f"失败: {e}"}],
        }

    cited = sum(1 for g in gaps if g["evidence"])
    return {
        "gaps": gaps,
        "gap_summary": gap_summary,
        "messages": [
            {"role": "gap", "content": f"发现 {len(gaps)} 条差距（{cited} 条有证据引用）"}
        ],
    }
