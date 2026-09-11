import os

# ★ 必须在 import sentence_transformers 之前设置
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

from functools import lru_cache

from loguru import logger

MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"


@lru_cache(maxsize=1)
def _get_model():
    from sentence_transformers import SentenceTransformer
    logger.info(f"加载语义模型: {MODEL_NAME}")
    model = SentenceTransformer(MODEL_NAME)
    logger.info("语义模型加载完成")
    return model


def semantic_similarity(text_a: str, text_b: str) -> float:
    import numpy as np
    model = _get_model()
    vecs = model.encode(
        [text_a, text_b],
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    sim = float(np.dot(vecs[0], vecs[1]))
    return (sim + 1) / 2