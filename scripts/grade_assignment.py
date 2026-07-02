"""Grade every submission of an assignment through Temporal.

Usage:
    uv run python scripts/grade_assignment.py gold-theory gold-algo
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import time

from autograde_core.hashing import assignment_id_for
from autograde_core.telemetry import configure_telemetry


async def grade(assignments: list[str], concurrency: int) -> None:
    from sqlalchemy import select
    from temporalio.client import Client

    from autograde_core.config import get_settings
    from autograde_db.models import Submission
    from autograde_db.session import session_scope
    from services.orchestrator.worker import create_worker
    from services.orchestrator.workflows import TASK_QUEUE, GradeStudentWorkflow

    submissions: list[str] = []
    with session_scope() as s:
        for a in assignments:
            submissions += [str(x) for x in s.scalars(
                select(Submission.id).where(Submission.assignment_id == assignment_id_for(a)))]
    print(f"grading {len(submissions)} submissions from {assignments}")

    client = await Client.connect(get_settings().temporal_address)
    worker = await create_worker(client, concurrency=concurrency)
    started = time.monotonic()
    async with worker:
        handles = []
        for sid in submissions:
            try:
                handles.append(await client.start_workflow(
                    GradeStudentWorkflow.run, sid, id=f"grade-gold-{sid}",
                    task_queue=TASK_QUEUE))
            except Exception:
                handles.append(client.get_workflow_handle(f"grade-gold-{sid}"))
        for i, h in enumerate(handles, 1):
            await h.result()
            if i % 20 == 0:
                print(f"  {i}/{len(handles)}")
    print(f"graded in {(time.monotonic() - started) / 60:.1f} min")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("assignments", nargs="+")
    parser.add_argument("--concurrency", type=int, default=6)
    args = parser.parse_args()
    sys.path.insert(0, "scripts")
    configure_telemetry("gold-grading")
    asyncio.run(grade(args.assignments, args.concurrency))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
