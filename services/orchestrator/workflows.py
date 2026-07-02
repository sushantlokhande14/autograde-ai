"""Temporal workflow definitions.

``PingWorkflow`` is the onboarding round-trip (P3.1). ``GradeStudentWorkflow``
(P3.6) grades one submission: theory artifacts through TheoryGrader, code
artifacts through CodeExecutionGrader, each as an activity with Temporal-owned
retries and timeouts. Phase 3 dispatches sequentially; Phase 4 fans out.
"""

from __future__ import annotations

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

TASK_QUEUE = "grading"

_RETRY = RetryPolicy(
    initial_interval=timedelta(seconds=2),
    backoff_coefficient=2.0,
    maximum_attempts=3,
)


@workflow.defn
class PingWorkflow:
    """Onboarding round-trip: proves worker, task queue, and activity wiring."""

    @workflow.run
    async def run(self, message: str) -> str:
        return await workflow.execute_activity(
            "ping",
            message,
            start_to_close_timeout=timedelta(seconds=10),
            retry_policy=_RETRY,
        )


# artifact type -> grader activities dispatched for it
_DISPATCH: dict[str, list[tuple[str, int]]] = {
    "theory": [("grade_theory", 5)],
    "code": [("grade_code", 10), ("grade_style", 5)],
    "derivation": [("grade_derivation", 5)],
    "figure": [("grade_figure", 5)],
}


@workflow.defn
class GradeStudentWorkflow:
    """Grade every mapped artifact of one submission, graders fanned out in
    parallel. A permanently-failing grader yields a zero-confidence placeholder
    and never kills the workflow (fail loud, fail isolated).
    Workflow id: grade-<submission_id>."""

    @workflow.run
    async def run(self, submission_id: str) -> dict:
        import asyncio

        artifacts = await workflow.execute_activity(
            "list_gradable_artifacts",
            submission_id,
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=_RETRY,
        )

        async def run_one(activity: str, artifact: dict, minutes: int) -> dict:
            try:
                return await workflow.execute_activity(
                    activity,
                    artifact,
                    start_to_close_timeout=timedelta(minutes=minutes),
                    retry_policy=_RETRY,
                )
            except Exception:  # placeholder grade; aggregation gates it to review
                return {
                    "grader": activity, "question_id": artifact.get("question_id"),
                    "score": 0.0, "max_score": 0.0, "confidence": 0.0,
                    "reasoning": "grader failed after retries", "failed": True,
                }

        tasks = [
            run_one(activity, artifact, minutes)
            for artifact in artifacts
            for activity, minutes in _DISPATCH.get(artifact["artifact_type"], [])
        ]
        grades = list(await asyncio.gather(*tasks))

        summary = await workflow.execute_activity(
            "aggregate_submission",
            submission_id,
            start_to_close_timeout=timedelta(minutes=5),
            retry_policy=_RETRY,
        )
        return {"grades": grades, "summary": summary}


@workflow.defn
class PlagiarismWorkflow:
    """Cohort-level scan for one (assignment, question); run after a batch."""

    @workflow.run
    async def run(self, params: dict) -> int:
        report = await workflow.execute_activity(
            "detect_plagiarism",
            params,
            start_to_close_timeout=timedelta(minutes=15),
            retry_policy=_RETRY,
        )
        return len(report)
