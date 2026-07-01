"""API gateway.

Phase 0 gave this service /healthz; Phase 1 adds the minimal review surface for
low-confidence question mappings (list + confirm). The full GraphQL schema
replaces these REST stubs in Phase 5 — they exist so the review queue is real,
not a mock, from the first phase that produces gated artifacts.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from autograde_core.events import Topic, get_producer, publish
from autograde_core.health import create_health_app
from autograde_db import repository as repo
from autograde_db.session import session_scope
from services.question_mapper.mapper import CONFIDENCE_GATE

SERVICE_NAME = "api"
app = create_health_app(SERVICE_NAME)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class PendingMapping(BaseModel):
    artifact_id: UUID
    source_file: str
    artifact_type: str
    question_id: str | None
    confidence: float | None


class ConfirmRequest(BaseModel):
    question_id: str


@app.get("/mappings/pending")
def pending_mappings() -> list[PendingMapping]:
    """Artifacts whose question mapping is below the confidence gate."""
    with session_scope() as session:
        rows = repo.low_confidence_artifacts(session, threshold=CONFIDENCE_GATE)
        return [
            PendingMapping(
                artifact_id=r.id,
                source_file=r.source_file,
                artifact_type=r.artifact_type,
                question_id=r.question_id,
                confidence=r.question_mapping_confidence,
            )
            for r in rows
        ]


@app.post("/mappings/{artifact_id}/confirm")
def confirm_mapping(artifact_id: UUID, body: ConfirmRequest) -> dict[str, str]:
    """Instructor confirms a mapping; confidence becomes 1.0 and the event fires."""
    with session_scope() as session:
        from autograde_db.models import Artifact

        row = session.get(Artifact, artifact_id)
        if row is None:
            raise HTTPException(status_code=404, detail="artifact not found")
        repo.set_artifact_mapping(
            session, artifact_id=artifact_id, question_id=body.question_id, confidence=1.0
        )
        submission_id = str(row.submission_id)

    producer = get_producer()
    publish(
        producer,
        Topic.QUESTION_MAPPED,
        key=submission_id,
        value={
            "artifact_id": str(artifact_id),
            "question_id": body.question_id,
            "confidence": 1.0,
            "method": "instructor",
        },
    )
    producer.flush(5)
    return {"status": "confirmed", "question_id": body.question_id}
