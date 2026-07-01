"""Grounded retrieval for graders.

Query = the rubric question's prompt (+ optional artifact excerpt). Search is
semantic over ``course_materials`` filtered to the assignment, with
reference-answer chunks excluded unless explicitly requested — the guard that
keeps the gold answer out of grader prompts. Results are cached in Redis
(``retrieval:*``, TTL 1h) and every chunk carries enough payload to be cited
in ``grading.grades.retrieval_citations``.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from qdrant_client.models import FieldCondition, Filter, MatchValue

from autograde_core.hashing import assignment_id_for
from autograde_core.models import Rubric
from autograde_rag.cache import RETRIEVAL_TTL_S, cache_get, cache_set, retrieval_key
from autograde_rag.embed import embed_texts
from autograde_rag.index import COURSE_MATERIALS, get_qdrant


@dataclass
class RetrievedChunk:
    chunk_id: str
    source: str
    text: str
    score: float
    reference_answer: bool

    def to_dict(self) -> dict:
        return {
            "chunk_id": self.chunk_id,
            "source": self.source,
            "text": self.text,
            "score": self.score,
            "reference_answer": self.reference_answer,
        }


@dataclass
class RetrievalResult:
    chunks: list[RetrievedChunk]
    cache_hit: bool
    latency_ms: int


def _question_prompt(assignment_id: str, question_id: str) -> str:
    from autograde_db.models import Assignment
    from autograde_db.session import session_scope

    with session_scope() as session:
        row = session.get(Assignment, assignment_id_for(assignment_id))
        if row is None:
            raise LookupError(f"assignment '{assignment_id}' not found")
        rubric = Rubric.model_validate(row.rubric)
    for q in rubric.questions:
        if q.question_id == question_id:
            return q.prompt
    raise LookupError(f"question '{question_id}' not in rubric '{assignment_id}'")


def retrieve(
    assignment_id: str,
    question_id: str,
    artifact_type: str,
    *,
    top_k: int = 3,
    query_hint: str = "",
    include_reference: bool = False,
    use_cache: bool = True,
    collection: str = COURSE_MATERIALS,
) -> RetrievalResult:
    started = time.monotonic()
    key = retrieval_key(
        assignment_id, question_id, artifact_type, top_k, query_hint, include_reference
    )

    if use_cache:
        cached = cache_get(key)
        if cached is not None:
            return RetrievalResult(
                chunks=[RetrievedChunk(**c) for c in cached],
                cache_hit=True,
                latency_ms=int((time.monotonic() - started) * 1000),
            )

    query = _question_prompt(assignment_id, question_id)
    if query_hint:
        query = f"{query}\n{query_hint[:500]}"
    vector = embed_texts([query])[0]

    conditions = [FieldCondition(key="assignment_id", match=MatchValue(value=assignment_id))]
    if not include_reference:
        conditions.append(
            FieldCondition(key="reference_answer", match=MatchValue(value=False))
        )

    hits = get_qdrant().query_points(
        collection_name=collection,
        query=vector,
        query_filter=Filter(must=conditions),
        limit=top_k,
        with_payload=True,
    ).points

    chunks = [
        RetrievedChunk(
            chunk_id=str(h.id),
            source=h.payload.get("source", ""),
            text=h.payload.get("text", ""),
            score=float(h.score),
            reference_answer=bool(h.payload.get("reference_answer", False)),
        )
        for h in hits
    ]

    if use_cache:
        cache_set(key, [c.to_dict() for c in chunks], RETRIEVAL_TTL_S)

    return RetrievalResult(
        chunks=chunks,
        cache_hit=False,
        latency_ms=int((time.monotonic() - started) * 1000),
    )
