"""Qdrant collections and idempotent chunk indexing.

Collections per PROJECT_PLAN §7.5. Points are keyed by the chunker's stable
uuid5 ids, so re-indexing the same material upserts in place — never
duplicates. Payloads carry everything retrieval filters or cites on.
"""

from __future__ import annotations

from functools import lru_cache

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from autograde_core.config import get_settings
from autograde_rag.chunk import Chunk
from autograde_rag.embed import embed_texts, embedding_dim

COURSE_MATERIALS = "course_materials"
RUBRIC_CONTEXT = "rubric_context"
PLAGIARISM_CORPUS = "plagiarism_corpus"

ALL_COLLECTIONS = (COURSE_MATERIALS, RUBRIC_CONTEXT, PLAGIARISM_CORPUS)


@lru_cache(maxsize=1)
def get_qdrant() -> QdrantClient:
    return QdrantClient(url=get_settings().qdrant_url)


def ensure_collections(client: QdrantClient | None = None) -> list[str]:
    """Create any missing collections (384-dim cosine). Idempotent."""
    client = client or get_qdrant()
    created: list[str] = []
    existing = {c.name for c in client.get_collections().collections}
    for name in ALL_COLLECTIONS:
        if name not in existing:
            client.create_collection(
                collection_name=name,
                vectors_config=VectorParams(size=embedding_dim(), distance=Distance.COSINE),
            )
            created.append(name)
    return created


def index_chunks(
    collection: str,
    chunks: list[Chunk],
    *,
    assignment_id: str,
    client: QdrantClient | None = None,
    batch_size: int = 64,
) -> int:
    """Embed and upsert chunks. Returns the number of points written."""
    client = client or get_qdrant()
    total = 0
    for start in range(0, len(chunks), batch_size):
        batch = chunks[start : start + batch_size]
        vectors = embed_texts([c.text for c in batch])
        points = [
            PointStruct(
                id=str(c.chunk_id),
                vector=v,
                payload={
                    "assignment_id": assignment_id,
                    "source": c.source,
                    "seq": c.seq,
                    "heading": c.heading,
                    "text": c.text,
                    "question_ids": c.metadata.get("question_ids", []),
                    "reference_answer": bool(c.metadata.get("reference_answer", False)),
                },
            )
            for c, v in zip(batch, vectors, strict=True)
        ]
        client.upsert(collection_name=collection, points=points, wait=True)
        total += len(points)
    return total
