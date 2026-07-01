"""In-process embeddings via sentence-transformers.

all-MiniLM-L6-v2: 384-dim, cosine, ~90MB auto-downloaded to the local HF cache
on first use. The model is loaded lazily once per process; retrieval-path
callers therefore pay the load cost on the first query only.
"""

from __future__ import annotations

from functools import lru_cache

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
EMBEDDING_DIM = 384


def embedding_dim() -> int:
    return EMBEDDING_DIM


@lru_cache(maxsize=1)
def _model():
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(MODEL_NAME)


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a batch; normalized so dot product == cosine similarity."""
    if not texts:
        return []
    vectors = _model().encode(texts, normalize_embeddings=True, show_progress_bar=False)
    return [v.tolist() for v in vectors]
