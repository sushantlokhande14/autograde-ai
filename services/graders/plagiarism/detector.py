"""PlagiarismDetector: winnowed n-gram overlap + embedding cosine, cohort-wide.

Fully deterministic (no LLM). For each code question: normalize every
submission's source, compute winnowed k-gram fingerprints (MOSS-style) and
MiniLM embeddings, compare all pairs, and persist one informational grade row
per submission (score = top pairwise similarity in [0,1], excluded from
aggregation). Fingerprint embeddings populate the ``plagiarism_corpus``
Qdrant collection for future cross-semester checks. Names never appear —
matches cite student-hash prefixes.
"""

from __future__ import annotations

import hashlib
import re
from itertools import combinations
from uuid import UUID

import structlog

from autograde_core import storage

log = structlog.get_logger()

GRADER_NAME = "PlagiarismDetector"
K = 5          # tokens per k-gram
WINDOW = 4     # winnowing window
FLAG_JACCARD = 0.5
FLAG_COSINE = 0.95


def normalize(source: str) -> list[str]:
    """Strip comments/strings/blank lines; tokenize identifiers and operators."""
    no_comments = re.sub(r"#.*", "", source)
    no_strings = re.sub(r"(['\"])(?:\\.|(?!\1).)*\1", "STR", no_comments)
    return re.findall(r"[A-Za-z_]\w*|[^\sA-Za-z_]", no_strings)


def fingerprints(tokens: list[str]) -> set[int]:
    """Winnowing: min hash per sliding window over k-gram hashes."""
    if len(tokens) < K:
        return set()
    grams = [
        int(hashlib.md5(" ".join(tokens[i : i + K]).encode()).hexdigest()[:12], 16)
        for i in range(len(tokens) - K + 1)
    ]
    if len(grams) <= WINDOW:
        return set(grams)
    return {min(grams[i : i + WINDOW]) for i in range(len(grams) - WINDOW + 1)}


def jaccard(a: set[int], b: set[int]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _code_artifacts(assignment_key: str, question_id: str) -> list[dict]:
    from sqlalchemy import select

    from autograde_db.models import Artifact, Submission
    from autograde_db.session import session_scope

    with session_scope() as session:
        rows = session.execute(
            select(Artifact, Submission.student_hash)
            .join(Submission, Artifact.submission_id == Submission.id)
            .where(Artifact.question_id == question_id)
            .where(Artifact.artifact_type == "code")
        ).all()
    out = []
    for artifact, student_hash in rows:
        if not artifact.content_ref.startswith(f"{assignment_key}/"):
            continue
        content = storage.get_json("normalized-artifacts", artifact.content_ref)
        out.append(
            {
                "submission_id": str(artifact.submission_id),
                "student_hash": student_hash,
                "source": content.get("content", {}).get("source", ""),
            }
        )
    return out


def detect(assignment_key: str, question_id: str) -> list[dict]:
    """Run cohort comparison; persist per-submission grade rows; return the report."""
    from qdrant_client.models import PointStruct

    from autograde_rag.embed import embed_texts
    from autograde_rag.index import PLAGIARISM_CORPUS, ensure_collections, get_qdrant
    from services.graders.common import persist_grade

    entries = _code_artifacts(assignment_key, question_id)
    if len(entries) < 2:
        return []

    prints = [fingerprints(normalize(e["source"])) for e in entries]
    vectors = embed_texts([e["source"][:2000] for e in entries])

    ensure_collections()
    get_qdrant().upsert(
        collection_name=PLAGIARISM_CORPUS,
        points=[
            PointStruct(
                id=str(UUID(int=int(hashlib.md5(f"{assignment_key}:{question_id}:{e['student_hash']}".encode()).hexdigest(), 16) % (1 << 127))),
                vector=v,
                payload={"assignment_id": assignment_key, "question_id": question_id,
                         "student_hash": e["student_hash"]},
            )
            for e, v in zip(entries, vectors, strict=True)
        ],
        wait=True,
    )

    def cosine(a: list[float], b: list[float]) -> float:
        return sum(x * y for x, y in zip(a, b, strict=True))  # embeddings normalized

    top: dict[int, tuple[float, int]] = {}
    for i, j in combinations(range(len(entries)), 2):
        sim = max(jaccard(prints[i], prints[j]), cosine(vectors[i], vectors[j]))
        for a, b in ((i, j), (j, i)):
            if sim > top.get(a, (0.0, -1))[0]:
                top[a] = (sim, b)

    report = []
    for idx, entry in enumerate(entries):
        sim, peer_idx = top.get(idx, (0.0, -1))
        peer = entries[peer_idx]["student_hash"][:12] if peer_idx >= 0 else "none"
        flagged = sim >= FLAG_JACCARD
        reasoning = (
            f"Top similarity {sim:.2f} with peer {peer}… "
            f"({'flagged for review' if flagged else 'below flag threshold'}). "
            f"Winnowed {K}-gram + embedding comparison across {len(entries)} submissions."
        )
        persist_grade(
            grader=GRADER_NAME,
            artifact={"submission_id": entry["submission_id"]},
            question_id=question_id,
            score=round(sim, 4), max_score=1.0,
            confidence=0.9,  # deterministic method, known blind spots (rewrites)
            reasoning=reasoning,
            breakdown=[{"criterion": "top pairwise similarity", "awarded": round(sim, 4),
                        "max": 1.0, "peer": peer, "flagged": flagged}],
        )
        report.append({"submission_id": entry["submission_id"], "similarity": sim,
                       "peer": peer, "flagged": flagged})
    log.info("plagiarism_scan", question=question_id, cohort=len(entries),
             flagged=sum(1 for r in report if r["flagged"]))
    return report
