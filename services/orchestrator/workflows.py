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


@workflow.defn
class GradeStudentWorkflow:
    """Grade every mapped artifact of one submission. Workflow id: grade-<submission_id>."""

    @workflow.run
    async def run(self, submission_id: str) -> list[dict]:
        artifacts = await workflow.execute_activity(
            "list_gradable_artifacts",
            submission_id,
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=_RETRY,
        )

        grades: list[dict] = []
        for artifact in artifacts:  # sequential in Phase 3; parallel fan-out in Phase 4
            if artifact["artifact_type"] == "theory":
                activity = "grade_theory"
                timeout = timedelta(minutes=5)
            elif artifact["artifact_type"] == "code":
                activity = "grade_code"
                timeout = timedelta(minutes=10)
            else:
                continue  # derivation/figure graders arrive in Phase 4
            grade = await workflow.execute_activity(
                activity,
                artifact,
                start_to_close_timeout=timeout,
                retry_policy=_RETRY,
            )
            grades.append(grade)
        return grades
