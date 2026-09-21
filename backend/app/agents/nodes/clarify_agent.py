"""动态追问 Agent（B：人在回路，解决 I-03 固定轮次）。

拆成两个节点以配合 LangGraph interrupt 语义：
- plan：基于差距与证据覆盖情况，让 LLM 决定是否需要补充信息（0-3 问，无缺口不打断），
  结果先提交 state（interrupt 前的产出能落盘，恢复时不重复调用 LLM）
- wait：有问题时 interrupt() 暂停整图等待用户回答；恢复时本节点重入，
  interrupt() 直接返回 Command(resume) 携带的答案，无 LLM 调用
"""

from pydantic import BaseModel, Field

from langgraph.types import interrupt

from app.agents.state import DiagnosisState
from app.agents.utils import call_llm_for_json


class ClarifyQuestion(BaseModel):
    id: str = Field(description="问题编号，如 'q1'")
    gap: str = Field(description="关联的差距（简述）")
    question: str = Field(description="面向候选人的具体问题，一句话能答完")
    hint: str = Field(default="", description="为什么要问（可选）")


class ClarifyPlan(BaseModel):
    questions: list[ClarifyQuestion] = Field(
        default_factory=list, description="需要追问的问题列表；信息足够时为空"
    )


PROMPT = """你是简历诊断助手。候选人简历与目标岗位的差距分析已完成（附证据引用）。

请判断：为了让差距结论更可靠、改写建议更可落地，是否需要候选人补充信息？
- 只问「答案会改变诊断结论」的关键缺口（如某段经历的规模/成果数据、技能熟练度、离职空窗期）
- 最多 3 个问题；信息已足够时返回空列表，不要为了问而问
- 每个问题必须让候选人能用一两句话回答

差距分析：
{gaps}

简历解析：
{parsed}

岗位要求摘要：
{job_analysis}
"""


async def plan(state: DiagnosisState) -> dict:
    """生成追问计划；LLM 失败时放弃追问，不熔断主流程。"""
    if state.get("error") or not state.get("gaps"):
        return {"clarify_questions": []}

    try:
        result = await call_llm_for_json(
            PROMPT.format(
                gaps=state["gaps"],
                parsed=state.get("parsed", {}),
                job_analysis=state.get("job_analysis") or "（未提供）",
            ),
            ClarifyPlan,
            temperature=0.2,
            llm_config=state.get("llm_config"),
        )
        questions = [q.model_dump() for q in result.questions]
    except Exception as e:
        return {
            "clarify_questions": [],
            "messages": [{"role": "clarify", "content": f"追问生成失败，跳过追问: {e}"}],
        }

    if not questions:
        return {
            "clarify_questions": [],
            "messages": [{"role": "clarify", "content": "信息充分，无需追问"}],
        }
    return {"clarify_questions": questions}


def wait(state: DiagnosisState, config=None) -> dict:
    """有问题且处于交互式链路（带 thread_id）时打断等待用户回答。

    ⚠ 必须是同步函数：Python 3.10 的 async 节点里 interrupt() 依赖的
    runnable contextvar 不可用（langgraph 要求 3.11+），同步节点不受影响。
    """
    questions = state.get("clarify_questions") or []
    if not questions:
        return {"user_answers": {}}

    thread_id = (config or {}).get("configurable", {}).get("thread_id")
    if thread_id:
        # ⚠ interrupt 会抛 GraphInterrupt 实现暂停，不能包在 try/except 里
        answers = interrupt({"questions": questions})
        normalized = _normalize_answers(answers)
        return {
            "user_answers": normalized,
            "messages": [{"role": "clarify", "content": f"已收到 {len(normalized)} 条补充回答"}],
        }
    # 非交互链路（如离线 diagnose）：记录问题但不等待
    return {"user_answers": {}}


def _normalize_answers(answers) -> dict[str, str]:
    if isinstance(answers, dict):
        return {str(k): str(v) for k, v in answers.items() if str(v).strip()}
    if isinstance(answers, list):
        # 兼容按顺序列表回答
        return {f"q{i + 1}": str(a) for i, a in enumerate(answers) if str(a).strip()}
    return {}
