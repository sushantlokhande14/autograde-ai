"""API gateway: GraphQL (queries/mutations/subscriptions) + upload intake.

Phase 5 retires the Phase 1 REST review stubs — the review queue now lives in
the GraphQL schema. The one non-GraphQL route left is the multipart upload,
which stages the class zip and rubric and kicks the existing ingestion
pipeline.
"""

from __future__ import annotations

import json

from fastapi import File, Form, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from strawberry.fastapi import GraphQLRouter

from autograde_core.health import create_health_app
from services.api.schema import schema

SERVICE_NAME = "api"
app = create_health_app(SERVICE_NAME)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(GraphQLRouter(schema), prefix="/graphql")


@app.post("/upload")
async def upload(
    submissions: UploadFile = File(...),
    rubric: UploadFile = File(...),
    roster: UploadFile = File(...),
) -> dict:
    """Stage a class upload and route it through ingestion (Kafka-driven)."""
    import asyncio

    from autograde_core.models import Rubric
    from autograde_core.rubric import validate_rubric
    from services.orchestrator.ingest_worker import run as drain
    from services.router.router import route

    rubric_data = json.loads(await rubric.read())
    validated: Rubric = validate_rubric(rubric_data)
    roster_data = json.loads(await roster.read())
    roster_map = {s["canvas_id"]: s["display_name"] for s in roster_data["students"]}
    zip_bytes = await submissions.read()

    def _ingest() -> tuple[int, int]:
        result = route(
            zip_bytes,
            assignment_key=validated.assignment_id,
            roster=roster_map,
            rubric=validated,
            publish_events=True,
        )
        drain(group=f"upload-{validated.assignment_id}", idle_timeout_s=10.0)
        return len(result.registrations), len(result.unrouted)

    registered, unrouted = await asyncio.to_thread(_ingest)
    return {
        "assignment_id": validated.assignment_id,
        "files_registered": registered,
        "files_unrouted": unrouted,
    }
