"""Temporal activities for the grading workflow.

Activities are thin: they deserialize inputs, delegate to the grader/repo
modules (imported lazily so the workflow sandbox never loads them), and return
JSON-safe dicts. Temporal owns retries and timeouts.
"""

from __future__ import annotations

from temporalio import activity


@activity.defn
async def ping(message: str) -> str:
    """Onboarding round-trip activity."""
    return f"pong: {message}"


@activity.defn
async def list_gradable_artifacts(submission_id: str) -> list[dict]:
    """Mapped artifacts of a submission that Phase 3 graders can handle."""
    from uuid import UUID

    from sqlalchemy import select

    from autograde_db.models import Artifact
    from autograde_db.session import session_scope

    with session_scope() as session:
        rows = session.scalars(
            select(Artifact)
            .where(Artifact.submission_id == UUID(submission_id))
            .where(Artifact.question_id.is_not(None))
            .order_by(Artifact.artifact_type)
        )
        return [
            {
                "artifact_id": str(r.id),
                "submission_id": submission_id,
                "artifact_type": r.artifact_type,
                "question_id": r.question_id,
                "content_ref": r.content_ref,
            }
            for r in rows
        ]


@activity.defn
async def grade_theory(artifact: dict) -> dict:
    import asyncio

    from services.graders.theory.grader import grade as _grade

    return await asyncio.to_thread(_grade, artifact)


@activity.defn
async def grade_code(artifact: dict) -> dict:
    import asyncio

    from services.graders.code_execution.grader import grade as _grade

    return await asyncio.to_thread(_grade, artifact)
