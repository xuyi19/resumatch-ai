"""知识库问答智能体（考核项三核心：ReAct 工具调用 Agent + 多轮记忆 + RAG 融合）。

完整 LCEL/Agent 链路：
  用户问题 → 输入安全过滤（app/core/input_guard.py）
           → 知识库语义检索（app/core/knowledge.py，RAG 片段与提示词拼接）
           → create_react_agent 工具循环（Reason → Act → Observe）
           → 最终回答 + 工具调用轨迹（可观测）→ 消息持久化

智能体要素：
- 消息体系：langchain_core.messages（HumanMessage/AIMessage/ToolMessage），
  历史以 BaseMessage 列表回放进 create_react_agent 的输入；
- 多轮记忆：SQLite 持久化（agent_messages 表），按会话加载并裁剪最近 N 条，
  防上下文无限增长；
- 双自定义工具：calculate（AST 白名单安全数学求值，薪资/年限换算场景）+
  summarize_document（知识库文档摘要——把 RAG 检索封装成可被模型主动调用的
  工具，体现「Agent 自主决定何时检索/计算」）；
- ReAct 推理：langgraph.prebuilt.create_react_agent，模型按需在「直接回答 /
  调用工具」间自主决策，工具结果回填再推理。
"""

from __future__ import annotations

import ast
import operator
import re

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent
from loguru import logger
from sqlalchemy import delete as sa_delete
from sqlalchemy import select

from app.agents.llm import get_llm
from app.agents.utils import JD_INJECTION_GUARD
from app.core.db import AsyncSessionLocal
from app.core.input_guard import sanitize_input
from app.core.knowledge import KnowledgeError, get_knowledge_base
from app.models.entities import AgentMessage

# 上下文裁剪：仅保留最近 N 条历史消息（人机各半起步，防上下文无限增长）
MAX_HISTORY_MESSAGES = 12
# 数学求值允许的二元运算
_SAFE_OPS = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.Div: operator.truediv, ast.Pow: operator.pow, ast.Mod: operator.mod,
    ast.FloorDiv: operator.floordiv,
}


# ---------------- 工具 1：数学计算（AST 白名单安全求值） ----------------

@tool
def calculate(expression: str) -> str:
    """计算数学表达式并返回结果。当你需要做薪资换算（如年薪折合月薪）、
    工作年限累计、Offer 成本合计等数值计算时，必须使用本工具而不是心算。
    输入应为合法算术表达式，仅支持数字与 + - * / % ** 和括号，
    例如：(12000 * 13 + 5000) / 12 或 2026 - 2019。
    """
    return _safe_eval(expression)


def _safe_eval(expression: str) -> str:
    """AST 白名单求值：仅允许数字、四则/幂/模运算与括号，杜绝任意代码执行。"""

    def _eval(node: ast.AST) -> float:
        if isinstance(node, ast.Expression):
            return _eval(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return float(node.value)
        if isinstance(node, ast.BinOp) and type(node.op) in _SAFE_OPS:
            return _SAFE_OPS[type(node.op)](_eval(node.left), _eval(node.right))
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            v = _eval(node.operand)
            return v if isinstance(node.op, ast.UAdd) else -v
        raise ValueError("表达式包含不允许的字符或运算")

    expr = re.sub(r"[，,×xX]", lambda m: {"，": "", ",": "", "×": "*", "x": "*", "X": "*"}[m.group(0)], (expression or "").strip())
    if not expr:
        return "错误：表达式为空"
    try:
        val = _eval(ast.parse(expr, mode="eval"))
        if val == int(val):
            return f"{expr} = {int(val)}"
        return f"{expr} = {round(val, 6)}"
    except (ValueError, SyntaxError, ZeroDivisionError, OverflowError) as e:
        return f"计算失败：{e}（仅支持数字与 + - * / % ** 和括号）"


# ---------------- 工具 2：文档摘要（把 RAG 检索封装成可调用工具） ----------------

def build_document_summarizer(owner_id: str, llm_config: dict):
    """构造与当前用户绑定的文档摘要工具（闭包携带 owner 隔离与 LLM 配置）。"""

    @tool
    def summarize_document(topic: str) -> str:
        """按主题检索用户知识库（简历/项目材料等已入库文档）并生成摘要。
        当用户询问其简历或项目经历中的内容、或你需要引用用户材料回答时使用。
        topic 应为要查询的主题关键词（如「项目经历」「教育背景」「实习成果」）。
        """
        try:
            kb = get_knowledge_base()
            chunks = kb.search(owner_id, topic, k=6, llm_config=llm_config)
        except Exception as e:
            return f"知识库检索失败：{e}"
        if not chunks:
            return "知识库中没有相关内容（可能尚未上传简历或项目材料）。"
        joined = "\n".join(f"- {c['text'][:400]}" for c in chunks)
        # 工具内为同步调用，不做二次 LLM 摘要（避免在同步工具里嵌事件循环）；
        # 取回片段本身即结构化材料，拼接为主题聚焦的「摘要」由主模型进一步整合。
        return f"与「{topic}」相关的知识库片段：\n{joined}"

    return summarize_document


# ---------------- 记忆持久化 ----------------

async def load_history(owner_id: str, session_id: str) -> list[BaseMessage]:
    """加载会话历史并裁剪为最近 MAX_HISTORY_MESSAGES 条，转为 BaseMessage 列表。"""
    async with AsyncSessionLocal() as db:
        rows = (
            await db.execute(
                select(AgentMessage)
                .where(AgentMessage.owner_id == owner_id, AgentMessage.session_id == session_id)
                .order_by(AgentMessage.id.desc())
                .limit(MAX_HISTORY_MESSAGES)
            )
        ).scalars().all()
    rows.reverse()  # 时间升序回放
    return [
        HumanMessage(content=r.content) if r.role == "human" else AIMessage(content=r.content)
        for r in rows
    ]


async def save_turn(owner_id: str, session_id: str, question: str, answer: str) -> None:
    """持久化本轮问答（人问/答各一条），供下一轮回放。"""
    async with AsyncSessionLocal() as db:
        db.add_all([
            AgentMessage(owner_id=owner_id, session_id=session_id, role="human", content=question),
            AgentMessage(owner_id=owner_id, session_id=session_id, role="ai", content=answer),
        ])
        await db.commit()


async def clear_history(owner_id: str, session_id: str) -> int:
    """清空指定会话的记忆，返回删除条数。"""
    async with AsyncSessionLocal() as db:
        res = await db.execute(
            sa_delete(AgentMessage)
            .where(AgentMessage.owner_id == owner_id, AgentMessage.session_id == session_id)
        )
        await db.commit()
        return res.rowcount or 0


async def get_history_raw(owner_id: str, session_id: str) -> list[dict]:
    """历史原始记录（前端展示）。"""
    async with AsyncSessionLocal() as db:
        rows = (
            await db.execute(
                select(AgentMessage)
                .where(AgentMessage.owner_id == owner_id, AgentMessage.session_id == session_id)
                .order_by(AgentMessage.id.asc())
            )
        ).scalars().all()
    return [{"role": r.role, "content": r.content, "created_at": r.created_at.isoformat() if r.created_at else None}
            for r in rows]


# ---------------- ReAct 智能体主链路 ----------------

_SYSTEM_TMPL = """你是「知岗」求职助手，基于用户的个人知识库（简历/项目材料）回答求职相关问题。

回答规则：
1. 优先依据知识库片段回答；片段不足以支撑结论时如实说明，不要编造细节；
2. 涉及数值（薪资换算、年限、成本合计）时，必须调用 calculate 工具计算，禁止心算；
3. 需要引用用户简历或项目材料时，调用 summarize_document 工具检索后再回答；
4. 回答保持简洁专业，中文作答。

{rag_block}
{guard}
"""


async def answer_question(
    owner_id: str, session_id: str, question: str, llm_config: dict | None = None,
) -> dict:
    """问答主链路：过滤 → RAG 检索 → ReAct 工具循环 → 持久化。

    返回 {answer, tool_trace, rag_sources}；
    输入被拦截或未配置 Key 时抛 ValueError（端点层转 400）。
    """
    llm_config = llm_config or {}

    # 1. 输入安全过滤（提示词注入 / 违规内容拦截）
    guard = sanitize_input(question)
    if not guard.ok:
        raise ValueError(guard.reason)

    # 2. 知识库语义检索：RAG 片段与提示词拼接（检索失败不阻断，降级为无上下文回答）
    rag_block, rag_sources = "", []
    try:
        chunks = get_knowledge_base().search(owner_id, guard.cleaned, k=4, llm_config=llm_config)
    except Exception as e:
        logger.warning(f"问答前知识库检索失败（降级无上下文）：{e}")
        chunks = []
    if chunks:
        lines = [f"[片段{i + 1}·来源:{c['source'] or '未命名'}] {c['text'][:400]}"
                 for i, c in enumerate(chunks)]
        rag_block = "【知识库参考片段】\n" + "\n".join(lines)
        rag_sources = [c["source"] or "未命名" for c in chunks]

    system_prompt = _SYSTEM_TMPL.format(
        rag_block=rag_block or "（知识库暂无相关片段，请基于通用求职知识回答并说明未检索到个人材料）",
        guard=JD_INJECTION_GUARD,
    )

    # 3. 多轮记忆回放（含上下文裁剪）
    history = await load_history(owner_id, session_id)
    messages: list[BaseMessage] = [*history, HumanMessage(content=guard.cleaned)]

    # 4. ReAct 工具循环（create_react_agent：Reason → Act → Observe → ... → Final）
    llm = get_llm(
        temperature=0.3,
        api_key=llm_config.get("api_key"),
        base_url=llm_config.get("base_url"),
        model=llm_config.get("model"),
    )
    agent = create_react_agent(
        model=llm,
        tools=[calculate, build_document_summarizer(owner_id, llm_config)],
        prompt=system_prompt,
    )
    try:
        result = await agent.ainvoke({"messages": messages})
    except ValueError:
        raise  # get_llm 的无 Key 提示原样透传
    except Exception as e:
        logger.warning(f"ReAct 智能体执行失败：{e}")
        raise ValueError(f"智能体执行失败：{e}") from e

    out_msgs = result.get("messages") or []
    answer = out_msgs[-1].content if out_msgs else "（未能生成回答）"

    # 5. 工具调用轨迹提取（可观测性：前端展示「用过什么工具、工具回了什么」）
    tool_trace: list[dict] = []
    for m in out_msgs:
        if isinstance(m, AIMessage) and m.tool_calls:
            for tc in m.tool_calls:
                tool_trace.append({"tool": tc.get("name", ""), "args": tc.get("args", {})})

    # 6. 持久化本轮问答
    await save_turn(owner_id, session_id, guard.cleaned, answer)

    logger.info(f"知识库问答完成[{owner_id[:8]}/{session_id[:8]}]：工具调用 {len(tool_trace)} 次")
    return {"answer": answer, "tool_trace": tool_trace, "rag_sources": rag_sources}
