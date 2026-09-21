"""证据检索层（RAG-lite）。

诊断链路的评分 / 差距 / 改写 Agent 不再只看整段简历原文，而是基于
「结构化分块 + 向量检索」引用简历原文证据，支撑可解释性与抗幻觉。

设计要点：
- 分块：按空行/行长度做条目级分块（教育/工作/项目条目天然成块），id 稳定（R1/J1…），
  便于 LLM 输出结构化引用与前端回链原文。
- 向量化：OpenAI 协议 /embeddings（复用用户 LLM 配置）；进程内纯 Python 余弦，
  不引入 numpy / 向量库（桌面打包零负担，简历规模 <100 块完全够用）。
- 降级：未配置 embedding 模型或调用失败时，自动切换 CJK bigram 关键词重叠检索
  （hybrid 叙事：embedding 不可用仍有可用基线）。
"""

import asyncio
import math
import re

from loguru import logger

from app.core.config import settings

# 全进程 embedding 可用性：一旦失败不再重试，避免每个任务都白等一次超时
_EMBED_DISABLED = False

_CHUNK_TARGET = 200  # 单块目标长度（字符）
_MIN_CHUNK = 12  # 短于此并入前块
_MAX_RESUME_CHUNKS = 80
_MAX_JD_CHUNKS = 40
_TIMEOUT = 30

_CJK_RE = re.compile(r"[\u4e00-\u9fff]")
_WORD_RE = re.compile(r"[a-zA-Z0-9]+")

_EMBEDDINGS_CACHE: dict[tuple, object] = {}


def _tokenize(text: str) -> list[str]:
    """CJK bigram + ASCII 词，用于关键词重叠检索。"""
    tokens: list[str] = []
    # CJK bigram
    i = 0
    chars = text
    while i < len(chars):
        if _CJK_RE.match(chars[i]):
            j = i
            while j < len(chars) and _CJK_RE.match(chars[j]):
                j += 1
            seg = chars[i:j]
            tokens.extend(seg[k : k + 2] for k in range(len(seg) - 1))
            i = j
        else:
            i += 1
    tokens.extend(w.lower() for w in _WORD_RE.findall(text))
    return tokens


def chunk_text(text: str, prefix: str, max_chunks: int) -> list[dict]:
    """把整段文本切成条目级证据块。prefix: 'R'（简历）/ 'J'（JD）。"""
    lines = [ln.strip() for ln in (text or "").splitlines()]
    chunks: list[str] = []
    buf = ""
    for ln in lines:
        if not ln:
            if buf:
                chunks.append(buf)
                buf = ""
            continue
        # 条目符号行独立成块（每条经历/成果单独一块，便于精确引用）
        starts_bullet = ln[0] in "-•·*▪"
        if not buf or starts_bullet or len(buf) + len(ln) > _CHUNK_TARGET:
            if buf:
                chunks.append(buf)
            buf = ln
        else:
            buf += f" {ln}"
        while len(buf) >= _CHUNK_TARGET * 1.5:  # 超长行硬切
            chunks.append(buf[:_CHUNK_TARGET])
            buf = buf[_CHUNK_TARGET:]
    if buf:
        chunks.append(buf)

    merged: list[str] = []
    for c in chunks:
        if merged and len(c) < _MIN_CHUNK:
            merged[-1] += f" {c}"
        else:
            merged.append(c)

    return [{"id": f"{prefix}{i + 1}", "text": c} for i, c in enumerate(merged[:max_chunks])]


def _get_embeddings(api_key: str | None, base_url: str | None, model: str):
    from langchain_openai import OpenAIEmbeddings

    cache_key = (api_key, base_url, model)
    if cache_key not in _EMBEDDINGS_CACHE:
        _EMBEDDINGS_CACHE[cache_key] = OpenAIEmbeddings(
            model=model,
            api_key=api_key,
            base_url=base_url,
            chunk_size=32,
            timeout=_TIMEOUT,
            max_retries=1,
        )
    return _EMBEDDINGS_CACHE[cache_key]


def _ensure_df(index: dict) -> dict:
    """文档频率表（缓存在 index 上，供 IDF 加权）。"""
    df = index.get("_df")
    if df is None:
        df = {}
        for ch in index["chunks"]:
            ch.setdefault("_tokens", set(_tokenize(ch["text"])))
            for t in ch["_tokens"]:
                df[t] = df.get(t, 0) + 1
        index["_df"] = df
    return df


def _keyword_search(index: dict, query: str, k: int) -> list[dict]:
    """IDF 加权重叠 + 查询覆盖度奖励的关键词检索。

    旧实现用纯重叠计数：'负责/项目/熟悉' 等高频词与区分词（如 Kubernetes）
    同权，导致常见词淹没真正相关的块。改进：
    - IDF 权重：块越少包含该词权重越高（log(1 + N/df)）
    - 覆盖度因子：命中查询中更多不同词的块排前（√ 阻尼防止单点独大）
    - 长度归一：除以 √块词数，避免长块天然占优
    """
    chunks = index.get("chunks") or []
    q_set = set(_tokenize(query))
    if not q_set or not chunks:
        return []
    df = _ensure_df(index)
    n_docs = len(chunks)
    scored = []
    for ch in chunks:
        c_tokens = ch.get("_tokens") or set(_tokenize(ch["text"]))
        ch["_tokens"] = c_tokens
        overlap = q_set & c_tokens
        if not overlap:
            continue
        idf_sum = sum(math.log(1 + n_docs / df.get(t, 1)) for t in overlap)
        coverage = len(overlap) / len(q_set)
        score = idf_sum * (coverage**0.5) / math.sqrt(len(c_tokens))
        scored.append({"id": ch["id"], "text": ch["text"], "score": score})
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:k]


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    return dot / (na * nb) if na and nb else 0.0


def search_evidence(index: dict, query: str, k: int = 3) -> list[dict]:
    """关键词模式检索（同步）。向量模式统一走 asearch_evidence。"""
    if not index or not index.get("chunks"):
        return []
    return _keyword_search(index, query, k)


async def asearch_evidence(index: dict, query: str, k: int = 3) -> list[dict]:
    vectors = index.get("vectors") if index else None
    if not vectors:
        return _keyword_search(index, query, k) if index else []
    emb = index["embedder"]
    try:
        qv = (await asyncio.wait_for(emb.aembed_query(query), _TIMEOUT)) or []
    except Exception as e:
        logger.warning(f"embedding 查询失败，本次转关键词检索: {e}")
        return _keyword_search(index, query, k)
    scored = [
        {"id": ch["id"], "text": ch["text"], "score": _cosine(qv, vec)}
        for ch, vec in zip(index["chunks"], vectors)
    ]
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:k]


async def retrieval_pool(
    index: dict, queries: list[str], k_per_query: int = 2, cap: int = 10
) -> list[dict]:
    """多查询检索合并去重，按分数取前 cap 条，构成 prompt 证据池。"""
    seen: dict[str, dict] = {}
    for q in queries:
        if not q:
            continue
        for e in await asearch_evidence(index, q, k_per_query):
            if e["id"] not in seen or e["score"] > seen[e["id"]]["score"]:
                seen[e["id"]] = e
    pool = sorted(seen.values(), key=lambda x: x["score"], reverse=True)
    return pool[:cap]


async def build_evidence_index(
    resume_text: str,
    jd_text: str,
    llm_config: dict | None = None,
) -> dict:
    """构建 task 内证据索引：分块 → 尝试向量化 → 失败降级关键词模式。"""
    global _EMBED_DISABLED
    llm_config = llm_config or {}
    chunks = chunk_text(resume_text, "R", _MAX_RESUME_CHUNKS) + chunk_text(
        jd_text, "J", _MAX_JD_CHUNKS
    )
    index: dict = {"chunks": chunks, "vectors": None, "mode": "keyword"}

    if _EMBED_DISABLED:
        return index

    model = (
        llm_config.get("embedding_model")
        or settings.LLM_EMBEDDING_MODEL
        or "text-embedding-3-small"
    )
    api_key = llm_config.get("api_key") or settings.LLM_API_KEY
    base_url = llm_config.get("base_url") or settings.LLM_BASE_URL or None
    if not api_key:
        return index

    try:
        emb = _get_embeddings(api_key, base_url, model)
        texts = [c["text"] for c in chunks]
        vecs = await asyncio.wait_for(emb.aembed_documents(texts), _TIMEOUT)
        if vecs and len(vecs) == len(chunks):
            index["vectors"] = [list(map(float, v)) for v in vecs]
            index["mode"] = "embedding"
            index["embedder"] = emb
            logger.info(f"证据索引向量化完成（{len(chunks)} 块, model={model}）")
    except Exception as e:
        _EMBED_DISABLED = True
        logger.warning(f"embedding 不可用（{e}），证据检索降级为关键词模式")
    return index


def filter_valid_ids(index: dict, ids: list) -> list[str]:
    """LLM 引用的证据 id 校验：仅保留真实存在的块 id。"""
    known = {c["id"] for c in (index or {}).get("chunks", [])}
    out = []
    for i in ids or []:
        s = str(i).strip().upper()
        if s in known and s not in out:
            out.append(s)
    return out


def render_pool(evidences: list[dict]) -> str:
    """把检索结果渲染成 prompt 里的证据池文本。"""
    if not evidences:
        return "（未能检索到相关证据）"
    return "\n".join(f"[{e['id']}] {e['text']}" for e in evidences)
