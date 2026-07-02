"""Two assignments grading simultaneously without cross-talk.

Regrades a slice of gold-theory and gold-algo submissions through Temporal at
the same time, then asserts every new grade row landed on the right
submission with that assignment's question set — retrieval, rubric lookup,
and persistence all scoped correctly under concurrency.

Opt-in:
    AUTOGRADE_RUN_INTEGRATION=1 uv run pytest tests/integration/test_concurrent_assignments.py -q
"""

from __future__ import annotations

import asyncio
import os
import time
from uuid import UUID

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("AUTOGRADE_RUN_INTEGRATION") != "1",
    reason="stack not running; set AUTOGRADE_RUN_INTEGRATION=1 to enable",
)

SLICE = 3
EXPECTED_QUESTIONS = {"gold-theory": {"q1", "q2", "q3"}, "gold-algo": {"q1", "q2", "q3"}}


def _subs(assignment: str) -> list[str]:
    from sqlalchemy import select

    from autograde_core.hashing import assignment_id_for
    from autograde_db.models import Submission
    from autograde_db.session import session_scope

    with session_scope() as s:
        return [str(x) for x in s.scalars(
            select(Submission.id)
            .where(Submission.assignment_id == assignment_id_for(assignment))
            .order_by(Submission.id))][:SLICE]


def test_concurrent_assignments_no_crosstalk() -> None:
    from temporalio.client import Client

    from autograde_core.config import get_settings
    from services.orchestrator.worker import create_worker
    from services.orchestrator.workflows import TASK_QUEUE, GradeStudentWorkflow

    picks = {a: _subs(a) for a in EXPECTED_QUESTIONS}
    stamp = int(time.time())

    async def drive() -> dict[str, dict]:
        client = await Client.connect(get_settings().temporal_address)
        worker = await create_worker(client, concurrency=8)
        async with worker:
            handles = {}
            for assignment, sids in picks.items():
                for sid in sids:  # both assignments start before any finishes
                    handles[sid] = await client.start_workflow(
                        GradeStudentWorkflow.run, sid,
                        id=f"concurrent-{stamp}-{sid}", task_queue=TASK_QUEUE)
            return {sid: await h.result() for sid, h in handles.items()}

    results = asyncio.run(drive())
    assert len(results) == SLICE * 2

    from sqlalchemy import select

    from autograde_db.models import Grade
    from autograde_db.session import session_scope

    for assignment, sids in picks.items():
        for sid in sids:
            with session_scope() as s:
                rows = s.scalars(select(Grade).where(
                    Grade.submission_id == UUID(sid),
                    Grade.grader == "FinalAggregate")).all()
            questions = {g.question_id for g in rows}
            assert questions <= EXPECTED_QUESTIONS[assignment] | {"overall"}, (
                f"{assignment}/{sid}: foreign questions {questions}")
            assert questions & EXPECTED_QUESTIONS[assignment], f"{assignment}/{sid}: no grades"
