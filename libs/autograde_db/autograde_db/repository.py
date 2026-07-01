"""Idempotent writes for the ingestion pipeline.

Inserts target the table objects (not the ORM entity) so the reserved
`metadata` column is addressed by its real name. All writes are upserts keyed on
deterministic ids, so Kafka replay never double-creates rows.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from autograde_db.models import Artifact, Assignment, StudentLookup, Submission


def upsert_assignment(
    session: Session,
    *,
    assignment_uuid: UUID,
    course_code: str,
    title: str,
    rubric: dict,
    grading_config: dict,
) -> None:
    stmt = pg_insert(Assignment.__table__).values(
        id=assignment_uuid,
        course_code=course_code,
        title=title,
        rubric=rubric,
        grading_config=grading_config,
    )
    session.execute(stmt.on_conflict_do_nothing(index_elements=["id"]))


def upsert_submission(
    session: Session, *, submission_id: UUID, assignment_uuid: UUID, student_hash: str
) -> None:
    stmt = pg_insert(Submission.__table__).values(
        id=submission_id, assignment_id=assignment_uuid, student_hash=student_hash
    )
    session.execute(
        stmt.on_conflict_do_nothing(index_elements=["assignment_id", "student_hash"])
    )


def upsert_identity(
    session: Session,
    *,
    student_hash: str,
    assignment_uuid: UUID,
    display_name: str,
    canvas_id: str | None,
) -> None:
    stmt = pg_insert(StudentLookup.__table__).values(
        student_hash=student_hash,
        assignment_id=assignment_uuid,
        display_name=display_name,
        canvas_id=canvas_id,
    )
    session.execute(stmt.on_conflict_do_nothing(index_elements=["student_hash"]))


def upsert_artifact(
    session: Session,
    *,
    artifact_id: UUID,
    submission_id: UUID,
    source_file: str,
    artifact_type: str,
    content_ref: str,
    question_id: str | None = None,
    confidence: float | None = None,
    metadata: dict | None = None,
) -> None:
    stmt = pg_insert(Artifact.__table__).values(
        id=artifact_id,
        submission_id=submission_id,
        source_file=source_file,
        artifact_type=artifact_type,
        content_ref=content_ref,
        question_id=question_id,
        question_mapping_confidence=confidence,
        metadata=metadata,
    )
    session.execute(
        stmt.on_conflict_do_update(
            index_elements=["id"],
            set_={
                "artifact_type": stmt.excluded.artifact_type,
                "content_ref": stmt.excluded.content_ref,
                "question_id": stmt.excluded.question_id,
                "question_mapping_confidence": stmt.excluded.question_mapping_confidence,
                "metadata": stmt.excluded.metadata,
            },
        )
    )


def set_artifact_mapping(
    session: Session, *, artifact_id: UUID, question_id: str | None, confidence: float
) -> None:
    obj = session.get(Artifact, artifact_id)
    if obj is not None:
        obj.question_id = question_id
        obj.question_mapping_confidence = confidence


def low_confidence_artifacts(session: Session, threshold: float = 0.6) -> list[Artifact]:
    stmt = (
        select(Artifact)
        .where(Artifact.question_mapping_confidence.is_not(None))
        .where(Artifact.question_mapping_confidence < threshold)
        .order_by(Artifact.question_mapping_confidence)
    )
    return list(session.scalars(stmt))
