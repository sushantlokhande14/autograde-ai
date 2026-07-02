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

    from opentelemetry import trace

    from services.graders.theory.grader import grade as _grade

    tracer = trace.get_tracer("autograde.orchestrator")
    with tracer.start_as_current_span(
        "grade_theory",
        attributes={
            "autograde.artifact_id": artifact["artifact_id"],
            "autograde.question_id": artifact["question_id"],
        },
    ):
        return await asyncio.to_thread(_grade, artifact)


@activity.defn
async def grade_code(artifact: dict) -> dict:
    import asyncio

    from opentelemetry import trace

    from services.graders.code_execution.grader import grade as _grade

    tracer = trace.get_tracer("autograde.orchestrator")
    with tracer.start_as_current_span(
        "grade_code",
        attributes={
            "autograde.artifact_id": artifact["artifact_id"],
            "autograde.question_id": artifact["question_id"],
        },
    ):
        return await asyncio.to_thread(_grade, artifact)


def _spanned(name: str, loader):
    """Build a grader activity: lazy import, thread offload, OTel span, metric."""

    @activity.defn(name=name)
    async def _run(artifact: dict) -> dict:
        import asyncio
        import time

        from opentelemetry import trace

        from autograde_core.telemetry import grader_duration_histogram

        tracer = trace.get_tracer("autograde.orchestrator")
        with tracer.start_as_current_span(
            name, attributes={"autograde.artifact_id": artifact.get("artifact_id", "")}
        ):
            started = time.monotonic()
            result = await asyncio.to_thread(loader(), artifact)
            grader_duration_histogram().record(
                (time.monotonic() - started) * 1000, {"grader": name}
            )
            return result

    return _run


grade_style = _spanned(
    "grade_style", lambda: __import__(
        "services.graders.code_style.grader", fromlist=["grade"]).grade
)
grade_derivation = _spanned(
    "grade_derivation", lambda: __import__(
        "services.graders.derivation.grader", fromlist=["grade"]).grade
)
grade_figure = _spanned(
    "grade_figure", lambda: __import__(
        "services.graders.figure.grader", fromlist=["grade"]).grade
)


@activity.defn
async def aggregate_submission(submission_id: str) -> dict:
    import asyncio

    from services.graders.feedback_synth.synthesizer import aggregate

    return await asyncio.to_thread(aggregate, submission_id)


@activity.defn
async def detect_plagiarism(params: dict) -> list[dict]:
    import asyncio

    from services.graders.plagiarism.detector import detect

    return await asyncio.to_thread(detect, params["assignment_id"], params["question_id"])
