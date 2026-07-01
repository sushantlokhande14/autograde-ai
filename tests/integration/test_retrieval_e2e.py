"""Retrieval-layer integration tests against live Qdrant + Redis + Postgres.

Covers the Phase 2 DoD: correctness (top-3 hit rate >= 90% against the corpus
ground truth), the reference-answer exclusion guard, cache behavior, latency
targets, and the gRPC path.

Opt-in:
    AUTOGRADE_RUN_INTEGRATION=1 uv run pytest tests/integration/test_retrieval_e2e.py -q
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("AUTOGRADE_RUN_INTEGRATION") != "1",
    reason="stack not running; set AUTOGRADE_RUN_INTEGRATION=1 to enable",
)

ASSIGNMENT = "cs152-hw3"
MATERIALS = Path("data/materials")
QUESTION_TYPES = {"q1": "theory", "q2": "code", "q3": "derivation", "q4": "figure"}


@pytest.fixture(scope="module")
def indexed() -> dict:
    """Seed + index the corpus (idempotent) and persist the rubric; return ground truth."""
    subprocess.run(
        [sys.executable, "scripts/seed_course_materials.py", "--out", str(MATERIALS)],
        check=True,
    )
    subprocess.run(
        [
            sys.executable,
            "scripts/index_materials.py",
            str(MATERIALS),
            "--assignment",
            ASSIGNMENT,
        ],
        check=True,
    )
    from autograde_core.rubric import load_rubric

    load_rubric(Path("data/uploads") / f"{ASSIGNMENT}_rubric.json", persist=True)

    manifest = json.loads((MATERIALS / "materials_manifest.json").read_text())
    truth: dict[str, set[str]] = {q: set() for q in QUESTION_TYPES}
    ref_sources: set[str] = set()
    for doc in manifest["documents"]:
        if doc["reference_answer"]:
            ref_sources.add(doc["source"])
            continue
        for q in doc["question_ids"]:
            truth[q].add(doc["source"])
    return {"truth": truth, "ref_sources": ref_sources}


def test_top3_hit_rate(indexed: dict) -> None:
    from autograde_rag.retrieve import retrieve

    hits = 0
    detail = {}
    for q, atype in QUESTION_TYPES.items():
        result = retrieve(ASSIGNMENT, q, atype, top_k=3, use_cache=False)
        sources = [c.source for c in result.chunks]
        hit = any(s in indexed["truth"][q] for s in sources)
        hits += hit
        detail[q] = sources
    rate = hits / len(QUESTION_TYPES)
    assert rate >= 0.9, f"hit rate {rate:.0%}; retrieved {detail}"


def test_reference_answers_excluded_by_default(indexed: dict) -> None:
    from autograde_rag.retrieve import retrieve

    for q, atype in QUESTION_TYPES.items():
        result = retrieve(ASSIGNMENT, q, atype, top_k=5, use_cache=False)
        leaked = [c.source for c in result.chunks if c.reference_answer]
        assert not leaked, f"{q}: reference answers leaked: {leaked}"
        assert not any(c.source in indexed["ref_sources"] for c in result.chunks)


def test_reference_answers_available_on_optin(indexed: dict) -> None:
    from autograde_rag.retrieve import retrieve

    found = False
    for q, atype in QUESTION_TYPES.items():
        result = retrieve(
            ASSIGNMENT, q, atype, top_k=5, use_cache=False, include_reference=True
        )
        found = found or any(c.reference_answer for c in result.chunks)
    assert found, "opt-in retrieval never surfaced a reference-answer chunk"


def test_cache_roundtrip(indexed: dict) -> None:
    from autograde_rag.retrieve import retrieve

    cold = retrieve(ASSIGNMENT, "q1", "theory", top_k=3, use_cache=True)
    warm = retrieve(ASSIGNMENT, "q1", "theory", top_k=3, use_cache=True)
    assert warm.cache_hit
    assert [c.chunk_id for c in warm.chunks] == [c.chunk_id for c in cold.chunks]


def test_latency_targets(indexed: dict) -> None:
    from autograde_rag.embed import embed_texts
    from autograde_rag.retrieve import retrieve

    embed_texts(["warmup"])
    cold = [
        retrieve(ASSIGNMENT, q, t, use_cache=False).latency_ms
        for q, t in QUESTION_TYPES.items()
        for _ in range(3)
    ]
    for q, t in QUESTION_TYPES.items():
        retrieve(ASSIGNMENT, q, t, use_cache=True)
    cached = [
        retrieve(ASSIGNMENT, q, t, use_cache=True).latency_ms
        for q, t in QUESTION_TYPES.items()
        for _ in range(3)
    ]
    assert max(cold) < 200, f"cold latencies {cold}"
    assert max(cached) < 50, f"cached latencies {cached}"


def test_grpc_path(indexed: dict) -> None:
    import grpc

    from autograde_core.pb import retrieval_pb2, retrieval_pb2_grpc
    from services.retrieval.server import serve

    server = serve(port=50097)
    try:
        with grpc.insecure_channel("localhost:50097") as channel:
            stub = retrieval_pb2_grpc.RetrievalServiceStub(channel)
            resp = stub.Retrieve(
                retrieval_pb2.RetrieveRequest(
                    assignment_id=ASSIGNMENT,
                    question_id="q2",
                    artifact_type="code",
                    top_k=3,
                )
            )
        assert len(resp.chunks) == 3
        assert all(not c.reference_answer for c in resp.chunks)
    finally:
        server.stop(grace=None)
