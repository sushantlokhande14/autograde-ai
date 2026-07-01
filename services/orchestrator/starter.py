"""Kafka → Temporal workflow starter.

Consumes ``question.mapped``; when every artifact of a submission has been
through the mapper (confidence recorded — gated artifacts simply are not
graded), starts ``GradeStudentWorkflow`` with the deterministic workflow id
``grade-<submission_id>``, so replays and duplicate events can never start a
second workflow for the same submission.

Run:
    uv run python -m services.orchestrator.starter
"""

from __future__ import annotations

import asyncio
from uuid import UUID

import structlog
from temporalio.client import Client
from temporalio.exceptions import WorkflowAlreadyStartedError

from autograde_core.config import get_settings
from autograde_core.events import Topic, consume, get_consumer
from services.orchestrator.workflows import TASK_QUEUE, GradeStudentWorkflow

log = structlog.get_logger()


def submission_ready(submission_id: UUID) -> bool:
    """True when the mapper has finished with every artifact of the submission."""
    from sqlalchemy import func, select

    from autograde_db.models import Artifact
    from autograde_db.session import session_scope

    with session_scope() as session:
        total = session.scalar(
            select(func.count()).select_from(Artifact).where(Artifact.submission_id == submission_id)
        )
        mapped = session.scalar(
            select(func.count())
            .select_from(Artifact)
            .where(Artifact.submission_id == submission_id)
            .where(Artifact.question_mapping_confidence.is_not(None))
        )
    return bool(total) and total == mapped


async def start_grading(client: Client, submission_id: str) -> bool:
    """Idempotent workflow start. Returns True if newly started."""
    try:
        await client.start_workflow(
            GradeStudentWorkflow.run,
            submission_id,
            id=f"grade-{submission_id}",
            task_queue=TASK_QUEUE,
        )
        log.info("workflow_started", submission_id=submission_id)
        return True
    except WorkflowAlreadyStartedError:
        return False


async def run(group: str = "workflow-starter", idle_timeout_s: float | None = None) -> int:
    client = await Client.connect(get_settings().temporal_address)
    consumer = get_consumer(group, [Topic.QUESTION_MAPPED])
    started = 0
    try:
        for event in consume(consumer, timeout=1.0, idle_timeout=idle_timeout_s):
            artifact_id = event.get("artifact_id", "?")
            submission_id = await _submission_for(artifact_id)
            if submission_id is None:
                continue
            if submission_ready(UUID(submission_id)) and await start_grading(client, submission_id):
                started += 1
    finally:
        consumer.close()
    return started


async def _submission_for(artifact_id: str) -> str | None:
    from uuid import UUID as _UUID

    from autograde_db.models import Artifact
    from autograde_db.session import session_scope

    def _query() -> str | None:
        with session_scope() as session:
            row = session.get(Artifact, _UUID(artifact_id))
            return str(row.submission_id) if row else None

    return await asyncio.to_thread(_query)


if __name__ == "__main__":
    asyncio.run(run())
