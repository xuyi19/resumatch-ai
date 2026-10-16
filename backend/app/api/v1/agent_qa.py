"""知识库问答智能体 API（考核模块）：文档入库 / 多轮问答 / 会话记忆管理。

与项目其他 LLM 端点同一套错误分流：
- ValueError（输入被安全过滤拦截 / 未配置 Key）→ 400，文案直接展示；
- KnowledgeError（向量化失败等）→ 400（用户可操作的配置问题）；
- 其他异常 → 502。
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from loguru import logger
from pydantic import BaseModel, Field

from app.agents.qa_agent import (
    answer_question,
    clear_history,
    get_history_raw,
)
from app.core.db import get_db
from app.core.deps import get_owner_id
from app.core.knowledge import KnowledgeError, get_knowledge_base
from app.utils.file_parser import parse_pdf

router = APIRouter(prefix="/agent", tags=["agent-qa"])

# 知识库文档大小上限（字符）——个人材料规模，防超长文档拖垮入库
_MAX_DOC_CHARS = 200_000
_ALLOWED_SUFFIXES = {".pdf", ".txt", ".md"}


class KnowledgeIngestRequest(BaseModel):
    """粘贴文本入库（前端 textarea / 结构化材料）。"""

    text: str = Field(min_length=10, max_length=_MAX_DOC_CHARS)
    source: str = Field(default="粘贴文本", max_length=120)
    llm_config: dict | None = None


class QaRequest(BaseModel):
    """多轮问答请求：session_id 由前端生成并保持（同会话共享记忆）。"""

    session_id: str = Field(min_length=4, max_length=64)
    question: str = Field(min_length=1, max_length=8000)
    llm_config: dict | None = None


# ---------------- 知识库 ----------------


@router.post("/knowledge/ingest")
async def knowledge_ingest(req: KnowledgeIngestRequest, owner_id: str = Depends(get_owner_id)):
    """粘贴文本入库：分块 → 向量化 → Chroma 持久化。"""
    kb = get_knowledge_base()
    try:
        chunks = kb.ingest(owner_id, req.text, req.source, req.llm_config)
    except KnowledgeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"chunks": chunks, **kb.stats(owner_id)}


@router.post("/knowledge/upload")
async def knowledge_upload(
    file: UploadFile,
    llm_config: dict | None = None,
    owner_id: str = Depends(get_owner_id),
):
    """上传 PDF/TXT/MD 文档入库：解析提取文本后走同一条入库链路。"""
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in _ALLOWED_SUFFIXES:
        raise HTTPException(status_code=400, detail="仅支持 PDF / TXT / MD 文档")
    raw = await file.read()
    if len(raw) > 20 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="文件超过 20MB 上限")
    tmp = Path("data/_kb_upload_tmp") / f"{owner_id[:16]}_{file.filename}"
    tmp.parent.mkdir(parents=True, exist_ok=True)
    tmp.write_bytes(raw)
    try:
        if suffix == ".pdf":
            text, img_pages, pages = parse_pdf(tmp)
            if img_pages and len(text) < 50:
                raise HTTPException(status_code=400, detail="疑似扫描版 PDF（无文本层），请先转文字版")
        else:
            text = tmp.read_text("utf-8", errors="ignore")
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"知识库文档解析失败[{file.filename}]：{e}")
        raise HTTPException(status_code=400, detail=f"文档解析失败：{e}")
    finally:
        tmp.unlink(missing_ok=True)

    if not text or len(text.strip()) < 10:
        raise HTTPException(status_code=400, detail="文档未提取到有效文本")
    kb = get_knowledge_base()
    try:
        chunks = kb.ingest(owner_id, text[:_MAX_DOC_CHARS], file.filename, llm_config)
    except KnowledgeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"chunks": chunks, **kb.stats(owner_id)}


@router.get("/knowledge/stats")
async def knowledge_stats(owner_id: str = Depends(get_owner_id)):
    """库内块数与来源清单。"""
    return get_knowledge_base().stats(owner_id)


@router.post("/knowledge/clear")
async def knowledge_clear(owner_id: str = Depends(get_owner_id)):
    """清空当前用户知识库。"""
    removed = get_knowledge_base().clear(owner_id)
    return {"removed": removed}


# ---------------- 多轮问答 ----------------


@router.post("/qa")
async def agent_qa(req: QaRequest, owner_id: str = Depends(get_owner_id)):
    """ReAct 智能体问答：安全过滤 → RAG → 工具循环 → 记忆持久化。"""
    try:
        return await answer_question(owner_id, req.session_id, req.question, req.llm_config)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"知识库问答异常：{e}")
        raise HTTPException(status_code=502, detail="AI 服务异常，请检查模型配置后重试")


@router.get("/history")
async def agent_history(session_id: str, owner_id: str = Depends(get_owner_id)):
    """会话历史（时间升序）。"""
    return {"items": await get_history_raw(owner_id, session_id)}


@router.delete("/history")
async def agent_history_clear(session_id: str, owner_id: str = Depends(get_owner_id)):
    """清空指定会话记忆（开始新一轮对话前调用）。"""
    removed = await clear_history(owner_id, session_id)
    return {"removed": removed}
