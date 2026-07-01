"""Temporal worker: hosts the grading workflows and activities.

Run:
    uv run python -m services.orchestrator.worker
"""

from __future__ import annotations

import asyncio

import structlog
from temporalio.client import Client
from temporalio.worker import Worker

from autograde_core.config import get_settings
from services.orchestrator.workflows import TASK_QUEUE, GradeStudentWorkflow, PingWorkflow

log = structlog.get_logger()


async def create_worker(client: Client) -> Worker:
    from services.orchestrator import activities

    return Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[PingWorkflow, GradeStudentWorkflow],
        activities=[
            activities.ping,
            activities.list_gradable_artifacts,
            activities.grade_theory,
            activities.grade_code,
        ],
    )


async def main() -> None:
    from autograde_core.telemetry import configure_telemetry

    configure_telemetry("orchestrator")
    client = await Client.connect(get_settings().temporal_address)
    worker = await create_worker(client)
    log.info("temporal_worker_started", task_queue=TASK_QUEUE)
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
