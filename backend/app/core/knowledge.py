"""本地知识库模块（考核项二：Chroma 持久化向量库 + RAG 检索）。

面向「简历知识库问答」场景：用户把简历/项目材料/面试资料（PDF/TXT 或粘贴文本）
入库，问答智能体检索相关知识块拼接进提示词。与诊断链的任务内临时索引
（app/core/evidence.py）互补——知识库跨会话持久化，用 Chroma 落盘。

设计要点：
- 分割：自定义递归分割（段落 → 行 → 句 → 硬切），chunk/overlap 可配，避免额外
  依赖 langchain-text-splitters；
- 向量化：OpenAI 协议 /embeddings（复用用户在设置页配置的 embedding 模型）；
- 存储：Chroma PersistentClient（SQLite 落盘于 DATA_DIR/knowledge），
  每用户独立 collection（kb_{owner_id}）实现数据隔离；
- 检索：向量 top-k → 相似度阈值过滤 → 词面重叠重排（混合检索）；
  embedding 不可用时自动降级为「全量取回 + 词面打分」的词面检索模式
  （知识库为个人规模、量小可行），保证无 Key 环境功能可用。
"""

from __future__ import annotations

import re
import uuid
from pathlib import Path

from loguru import logger

from app.core.config import settings


class KnowledgeError(Exception):
    """知识库操作失败（embedding 未配置 / 解析失败等），文案可直接展示给用户。"""


# ---------------- 分割 ----------------

def split_text(text: str, chunk_size: int = 500, overlap: int = 80) -> list[str]:
    """递归字符分割：双换行段 → 单换行行 → 中文句号 → 硬切。

    相邻块保留 overlap 重叠字符，保证边界处的语义不因切断而丢失。
    """
    text = re.sub(r"\r\n?", "\n", (text or "")).strip()
    if not text:
        return []

    def _hard_cut(seg: str) -> list[str]:
        step = max(chunk_size - overlap, 1)
        return [seg[i : i + chunk_size] for i in range(0, len(seg), step)] or [""]

    def _split(seg: str, seps: list[str]) -> list[str]:
        if len(seg) <= chunk_size:
            return [seg] if seg.strip() else []
        if not seps:
            return _hard_cut(seg)
        sep, rest = seps[0], seps[1:]
        parts = [p for p in seg.split(sep) if p.strip()]
        chunks: list[str] = []
        buf = ""
        for p in parts:
            candidate = f"{buf}{sep}{p}" if buf else p
            if len(candidate) <= chunk_size:
                buf = candidate
            else:
                if buf:
                    chunks.append(buf)
                if len(p) <= chunk_size:
                    buf = p
                else:
                    chunks.extend(_split(p, rest))  # 递归下一级分隔符
                    buf = ""
        if buf:
            chunks.append(buf)
        # 相邻块重叠拼接
        if overlap > 0 and len(chunks) > 1:
            out = [chunks[0]]
            for prev, cur in zip(chunks, chunks[1:]):
                out.append(prev[-overlap:] + cur)
            return out
        return chunks

    return [c.strip() for c in _split(text, ["\n\n", "\n", "。", "；", "，"]) if c.strip()]


# ---------------- 向量化 ----------------

def _embed_texts(texts: list[str], llm_config: dict) -> list[list[float]]:
    """OpenAI 协议 /embeddings 批量向量化；未配置或失败抛 KnowledgeError。"""
    cfg = llm_config or {}
    api_key = cfg.get("api_key") or settings.LLM_API_KEY
    if not api_key:
        raise KnowledgeError("未配置 API Key，无法向量化入库；请先在「设置」页填写")
    try:
        from langchain_openai import OpenAIEmbeddings

        emb = OpenAIEmbeddings(
            model=cfg.get("embedding_model") or "text-embedding-3-small",
            api_key=api_key,
            base_url=cfg.get("base_url") or settings.LLM_BASE_URL,
            timeout=60,
        )
        return emb.embed_documents(texts)
    except KnowledgeError:
        raise
    except Exception as e:
        raise KnowledgeError(f"向量化失败：{e}") from e


# ---------------- Chroma 知识库 ----------------

class KnowledgeBase:
    """Chroma 持久化知识库。进程内单例客户端，每用户一个 collection。"""

    def __init__(self, persist_dir: str | Path | None = None):
        self._dir = Path(persist_dir or (Path(settings.DATA_DIR) / "knowledge"))
        self._client = None

    def _get_client(self):
        if self._client is None:
            import chromadb

            self._dir.mkdir(parents=True, exist_ok=True)
            self._client = chromadb.PersistentClient(path=str(self._dir))
        return self._client

    def _collection(self, owner_id: str):
        return self._get_client().get_or_create_collection(
            name=f"kb_{re.sub(r'[^a-zA-Z0-9_-]', '_', owner_id)}",
            metadata={"hnsw:space": "cosine"},
        )

    def ingest(self, owner_id: str, text: str, source: str, llm_config: dict | None = None) -> int:
        """分块 → 向量化 → 入库。返回入库块数。"""
        chunks = split_text(text)
        if not chunks:
            raise KnowledgeError("文档内容为空或无法分割")
        embeddings = _embed_texts(chunks, llm_config or {})
        col = self._collection(owner_id)
        col.upsert(
            ids=[uuid.uuid4().hex for _ in chunks],
            documents=chunks,
            embeddings=embeddings,
            metadatas=[{"source": source[:120]} for _ in chunks],
        )
        logger.info(f"知识库入库[{owner_id[:8]}]：{source} → {len(chunks)} 块")
        return len(chunks)

    def _word_score(self, query: str, doc: str) -> float:
        """词面重叠打分（CJK bigram + 英文词），用于重排与降级检索。"""
        q = re.sub(r"\s+", "", (query or "").lower())
        d = re.sub(r"\s+", "", (doc or "").lower())
        if not q or not d:
            return 0.0
        grams = {q[i : i + 2] for i in range(len(q) - 1)} if len(q) > 1 else {q}
        en_words = set(re.findall(r"[a-z0-9]{2,}", query.lower()))
        hits = sum(1 for g in grams if g in d) + sum(1 for w in en_words if w in d)
        return hits / max(len(grams) + len(en_words), 1)

    def search(
        self, owner_id: str, query: str, k: int = 4, llm_config: dict | None = None,
        min_score: float = 0.05, max_distance: float = 0.85,
    ) -> list[dict]:
        """检索相关知识块：向量 top-k → 阈值过滤 → 词面重叠重排。

        embedding 不可用（未配置/查询失败）时降级：全量取回 + 词面打分 top-k。
        返回 [{text, source, distance}]，按相关性降序。
        """
        col = self._collection(owner_id)
        if col.count() == 0:
            return []
        results: list[dict] = []
        try:
            q_emb = _embed_texts([query], llm_config or {})[0]
            res = col.query(query_embeddings=[q_emb], n_results=min(k, col.count()))
            docs = (res.get("documents") or [[]])[0]
            dists = (res.get("distances") or [[]])[0]
            metas = (res.get("metadatas") or [[]])[0]
            for doc, dist, meta in zip(docs, dists, metas):
                if dist is not None and dist <= max_distance:  # 相似度阈值过滤
                    results.append({
                        "text": doc,
                        "source": (meta or {}).get("source", ""),
                        "distance": round(float(dist), 4),
                    })
        except Exception as e:  # 向量检索失败 → 词面降级
            logger.warning(f"知识库向量检索失败，降级词面检索：{e}")
            got = col.get(include=["documents", "metadatas"])
            scored = [
                {"text": doc, "source": (m or {}).get("source", ""), "distance": None,
                 "_ws": self._word_score(query, doc)}
                for doc, m in zip(got.get("documents") or [], got.get("metadatas") or [])
            ]
            results = [r for r in scored if r.pop("_ws") >= min_score]
            results.sort(key=lambda r: self._word_score(query, r["text"]), reverse=True)

        # 词面重叠重排（向量距离与词面互补；distance=None 的降级结果同样适用）
        results.sort(key=lambda r: self._word_score(query, r["text"]), reverse=True)
        return results[:k]

    def stats(self, owner_id: str) -> dict:
        """库内块数与来源清单（前端展示用）。"""
        col = self._collection(owner_id)
        got = col.get(include=["metadatas"])
        sources = sorted({(m or {}).get("source", "未命名") for m in got.get("metadatas") or []})
        return {"chunks": col.count(), "sources": sources}

    def clear(self, owner_id: str) -> int:
        """清空该用户知识库，返回删除块数。"""
        col = self._collection(owner_id)
        n = col.count()
        if n:
            self._client.delete_collection(col.name)  # 连 collection 一并删除，下次 get_or_create 重建
        logger.info(f"知识库清空[{owner_id[:8]}]：删除 {n} 块")
        return n


# 进程级单例（Chroma 客户端重，避免每次请求重建）
_kb: KnowledgeBase | None = None


def get_knowledge_base() -> KnowledgeBase:
    global _kb
    if _kb is None:
        _kb = KnowledgeBase()
    return _kb
