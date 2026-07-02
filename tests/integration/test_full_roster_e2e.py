"""Phase 4 small-batch e2e: full roster, parallel fan-out, aggregation.

Grades 3 submissions through GradeStudentWorkflow (parallel activities), runs
the cohort plagiarism scan, and asserts every applicable grader produced an
audit-linked row plus FinalAggregate / CrossChecker / FeedbackSynthesizer /
review outputs.

Opt-in:
    AUTOGRADE_RUN_INTEGRATION=1 uv run pytest tests/integration/test_full_roster_e2e.py -q
"""

from __future__ import annotations

import asyncio
import os
from uuid import UUID

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("AUTOGRADE_RUN_INTEGRATION") != "1",
    reason="stack not running; set AUTOGRADE_RUN_INTEGRATION=1 to enable",
)

BATCH = 3


def _pick_submissions() -> list[str]:
    from sqlalchemy import select

    from autograde_db.models import Artifact
    from autograde_db.session import session_scope

    with session_scope() as session:
        rows = list(session.scalars(select(Artifact).where(Artifact.question_id.is_not(None))))
    by_sub: dict[str, set[str]] = {}
    for r in rows:
        by_sub.setdefault(str(r.submission_id), set()).add(r.artifact_type)
    picks = [sid for sid, types in by_sub.items() if {"theory", "code"} <= types]
    if len(picks) < BATCH:
        pytest.skip("need >=3 mapped submissions; run scripts/ingest.py first")
    return sorted(picks)[:BATCH]


@pytest.fixture(scope="module")
def batch() -> list[str]:
    from temporalio.client import Client

    from autograde_core.config import get_settings
    from services.orchestrator.worker import create_worker
    from services.orchestrator.workflows import TASK_QUEUE, GradeStudentWorkflow

    submissions = _pick_submissions()

    async def drive() -> None:
        client = await Client.connect(get_settings().temporal_address)
        worker = await create_worker(client)
        async with worker:
            handles = []
            for sid in submissions:
                try:
                    handles.append(await client.start_workflow(
                        GradeStudentWorkflow.run, sid,
                        id=f"grade4-{sid}", task_queue=TASK_QUEUE,
                    ))
                except Exception:  # already ran in a previous session
                    handles.append(client.get_workflow_handle(f"grade4-{sid}"))
            for h in handles:
                await h.result()

    asyncio.run(drive())

    from services.graders.plagiarism.detector import detect

    detect("cs152-hw3", "q2")
    return submissions


def _grades(submission_id: str) -> dict[str, list]:
    from sqlalchemy import select

    from autograde_db.models import Grade
    from autograde_db.session import session_scope

    with session_scope() as session:
        rows = list(session.scalars(
            select(Grade).where(Grade.submission_id == UUID(submission_id))
        ))
    out: dict[str, list] = {}
    for g in rows:
        out.setdefault(g.grader, []).append(g)
    return out


def test_full_roster_rows(batch: list[str]) -> None:
    for sid in batch:
        by_grader = _grades(sid)
        assert "TheoryGrader" in by_grader or "DerivationGrader" in by_grader
        assert "CodeExecutionGrader" in by_grader
        assert "CodeStyleGrader" in by_grader
        assert "FinalAggregate" in by_grader, f"{sid}: {sorted(by_grader)}"
        assert "CrossChecker" in by_grader
        assert "FeedbackSynthesizer" in by_grader
        feedback = by_grader["FeedbackSynthesizer"][0]
        assert len(feedback.reasoning) > 50


def test_style_blend_applied(batch: list[str]) -> None:
    for sid in batch:
        by_grader = _grades(sid)
        final_q2 = next((g for g in by_grader.get("FinalAggregate", []) if g.question_id == "q2"), None)
        if final_q2 is None:
            continue
        execution = next(g for g in by_grader["CodeExecutionGrader"] if g.question_id == "q2")
        style = next(g for g in by_grader["CodeStyleGrader"] if g.question_id == "q2")
        expected = round(
            execution.max_score * (0.8 * execution.score / execution.max_score
                                   + 0.2 * style.score / style.max_score), 2)
        assert abs(final_q2.score - expected) < 0.05


def test_plagiarism_rows_exist(batch: list[str]) -> None:
    found = sum(1 for sid in batch if "PlagiarismDetector" in _grades(sid))
    assert found == len(batch)


def test_reviews_enqueued_for_flagged(batch: list[str]) -> None:
    from sqlalchemy import select

    from autograde_db.models import Review
    from autograde_db.session import session_scope

    with session_scope() as session:
        pending = list(session.scalars(select(Review).where(Review.status == "pending")))
    # synthetic cohort of 2 CPS variants: plagiarism flags fire, so reviews must exist
    assert pending, "expected pending review rows from flags/gating"
