from pydantic import BaseModel, Field, field_validator

from app.agents.state import DiagnosisState
from app.agents.utils import call_llm_for_json
from app.core.evidence import (
    build_evidence_index,
    filter_valid_ids,
    render_pool,
    retrieval_pool,
)


class ScoreItem(BaseModel):
    score: int = Field(ge=0, le=100, description="0-100 分")
    comment: str = Field(description="简短评语")
    evidence_ids: list[str] = Field(
        default_factory=list, description="评语引用的证据块 id，如 ['R3']"
    )


class ResumeScores(BaseModel):
    completeness: ScoreItem = Field(description="信息完整性")
    quantification: ScoreItem = Field(description="量化成果程度")
    star_structure: ScoreItem = Field(description="STAR 结构清晰度")
    skill_match: ScoreItem = Field(description="技能含金量")
    achievement: ScoreItem = Field(description="业绩亮点")
    readability: ScoreItem = Field(description="整体可读性")
    overall: int = Field(ge=0, le=100, description="综合评分（整数，不要嵌套对象）")

    @field_validator("overall", mode="before")
    @classmethod
    def coerce_overall(cls, v):
        if isinstance(v, dict):
            return v.get("score", 0)
        return v


# 各评分维度的检索查询（RAG：按维度检索简历原文证据注入 prompt）
DIM_QUERIES = {
    "completeness": "教育 工作经历 项目经历 基本信息 联系方式",
    "quantification": "百分比 数字 提升 增长 量化 规模",
    "star_structure": "项目 背景 任务 行动 结果 职责",
    "skill_match": "技能 技术栈 要求 熟练 掌握",
    "achievement": "负责 完成 成果 获奖 业绩",
    "readability": "描述 排版 结构 条理",
}

PROMPT = """你是一位资深简历评审专家，请对下面的简历从 6 个维度打分，每项 0-100 分，并给出简短评语。

6 个维度：
1. completeness 信息完整性
2. quantification 量化成果程度
3. star_structure STAR 结构清晰度
4. skill_match 技能含金量
5. achievement 业绩亮点
6. readability 整体可读性

每个维度输出格式为 {{"score": 整数, "comment": "评语", "evidence_ids": ["R1", ...]}}。
evidence_ids 从下面的证据块中引用支持该评语的简历原文块（1-3 个）；若没有可引用的证据，
留空数组，并在评语中说明是整体印象判断。

另外单独输出 overall 综合评分，它是一个 0-100 的整数，不要嵌套对象。

返回的 JSON 结构示例：
{{
  "completeness": {{"score": 75, "comment": "...", "evidence_ids": ["R2", "R5"]}},
  "quantification": {{"score": 70, "comment": "...", "evidence_ids": []}},
  "star_structure": {{"score": 65, "comment": "...", "evidence_ids": ["R8"]}},
  "skill_match": {{"score": 85, "comment": "...", "evidence_ids": ["R4"]}},
  "achievement": {{"score": 70, "comment": "...", "evidence_ids": ["R6"]}},
  "readability": {{"score": 80, "comment": "...", "evidence_ids": []}},
  "overall": 74
}}

简历原文：
{resume_text}

候选人画像：
{summary}

{evidence_block}
"""


async def _ensure_index(state: DiagnosisState) -> dict:
    """证据索引在 scorer 构建，gap/rewriter 经 state 复用（只 embed 一次）。"""
    idx = state.get("evidence_index")
    if idx and idx.get("chunks"):
        return idx
    return await build_evidence_index(
        state["resume_text"], state.get("jd_text", ""), state.get("llm_config")
    )


async def run(state: DiagnosisState) -> dict:
    if state.get("error"):
        return {}

    summary = state.get("parsed", {}).get("summary", "")
    try:
        index = await _ensure_index(state)
        llm_config = state.get("llm_config")

        # RAG：按维度检索证据，注入 prompt
        dim_blocks: list[str] = []
        for dim, query in DIM_QUERIES.items():
            pool = await retrieval_pool(index, [query, summary], k_per_query=2, cap=3)
            dim_blocks.append(f"【{dim}】相关证据：\n{render_pool(pool)}")
        evidence_block = "各维度检索到的简历证据块（供评语引用）：\n" + "\n\n".join(dim_blocks)

        result = await call_llm_for_json(
            PROMPT.format(
                resume_text=state["resume_text"], summary=summary, evidence_block=evidence_block
            ),
            ResumeScores,
            temperature=0.2,
            llm_config=llm_config,
        )
        scores = result.model_dump()
        # 证据 id 校验 + 附原文（前端直接展示）
        for item in scores.values():
            if isinstance(item, dict) and "evidence_ids" in item:
                valid = filter_valid_ids(index, item["evidence_ids"])
                by_id = {c["id"]: c["text"] for c in index["chunks"]}
                item["evidence"] = [{"id": i, "text": by_id[i]} for i in valid]
                item["evidence_ids"] = valid
    except Exception as e:
        return {
            "error": f"评分失败: {e}",
            "messages": [{"role": "scorer", "content": f"失败: {e}"}],
        }

    return {
        "scores": scores,
        "evidence_index": index,
        "messages": [{"role": "scorer", "content": f"综合评分 {scores['overall']}"}],
    }
