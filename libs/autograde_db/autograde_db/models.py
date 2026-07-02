"""SQLAlchemy ORM models mirroring infra/postgres/init.sql.

Two schemas: `grading` (hashed ids only) and `identity` (real names, RLS-gated).
`init.sql` is the authoritative baseline for the dev container; these models are
the app-side view and the source for Alembic's forward migrations.
"""

from __future__ import annotations

import datetime as dt
from uuid import UUID, uuid4

from sqlalchemy import Boolean, Float, ForeignKey, Integer, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, NUMERIC
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import DateTime

from autograde_db.base import Base


class Assignment(Base):
    __tablename__ = "assignments"
    __table_args__ = {"schema": "grading"}

    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid4)
    course_code: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    rubric: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    grading_config: Mapped[dict] = mapped_column(JSONB, nullable=False)


class Submission(Base):
    __tablename__ = "submissions"
    __table_args__ = (
        UniqueConstraint("assignment_id", "student_hash"),
        {"schema": "grading"},
    )

    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid4)
    assignment_id: Mapped[UUID | None] = mapped_column(ForeignKey("grading.assignments.id"))
    student_hash: Mapped[str] = mapped_column(Text, nullable=False)
    ingested_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Artifact(Base):
    __tablename__ = "artifacts"
    __table_args__ = {"schema": "grading"}

    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid4)
    submission_id: Mapped[UUID] = mapped_column(ForeignKey("grading.submissions.id"))
    source_file: Mapped[str] = mapped_column(Text, nullable=False)
    artifact_type: Mapped[str] = mapped_column(Text, nullable=False)
    question_id: Mapped[str | None] = mapped_column(Text)
    question_mapping_confidence: Mapped[float | None] = mapped_column(Float)
    content_ref: Mapped[str] = mapped_column(Text, nullable=False)
    # `metadata` is reserved on Declarative classes; map the attribute to that column.
    artifact_metadata: Mapped[dict | None] = mapped_column("metadata", JSONB)
    parsed_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Grade(Base):
    __tablename__ = "grades"
    __table_args__ = {"schema": "grading"}

    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid4)
    submission_id: Mapped[UUID] = mapped_column(ForeignKey("grading.submissions.id"))
    question_id: Mapped[str] = mapped_column(Text, nullable=False)
    grader: Mapped[str] = mapped_column(Text, nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    max_score: Mapped[float] = mapped_column(Float, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    reasoning: Mapped[str] = mapped_column(Text, nullable=False)
    rubric_breakdown: Mapped[dict] = mapped_column(JSONB, nullable=False)
    retrieval_citations: Mapped[dict | None] = mapped_column(JSONB)
    sandbox_run_id: Mapped[UUID | None] = mapped_column(PgUUID(as_uuid=True))
    llm_call_id: Mapped[UUID | None] = mapped_column(PgUUID(as_uuid=True))
    graded_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Review(Base):
    __tablename__ = "reviews"
    __table_args__ = {"schema": "grading"}

    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid4)
    submission_id: Mapped[UUID] = mapped_column(ForeignKey("grading.submissions.id"))
    question_id: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    original_score: Mapped[float] = mapped_column(Float, nullable=False)
    final_score: Mapped[float | None] = mapped_column(Float)
    reviewer_notes: Mapped[str | None] = mapped_column(Text)
    reviewed_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))


class LlmCall(Base):
    __tablename__ = "llm_calls"
    __table_args__ = {"schema": "grading"}

    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid4)
    grader: Mapped[str] = mapped_column(Text, nullable=False)
    model: Mapped[str] = mapped_column(Text, nullable=False)
    backend: Mapped[str] = mapped_column(Text, nullable=False)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    cache_hit: Mapped[bool] = mapped_column(Boolean, nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    cost_usd: Mapped[float] = mapped_column(NUMERIC(10, 6), nullable=False)
    request_payload_ref: Mapped[str | None] = mapped_column(Text)
    response_payload_ref: Mapped[str | None] = mapped_column(Text)
    called_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SandboxRun(Base):
    __tablename__ = "sandbox_runs"
    __table_args__ = {"schema": "grading"}

    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid4)
    submission_id: Mapped[UUID] = mapped_column(ForeignKey("grading.submissions.id"))
    test_case_id: Mapped[str] = mapped_column(Text, nullable=False)
    exit_code: Mapped[int | None] = mapped_column(Integer)
    stdout_ref: Mapped[str | None] = mapped_column(Text)
    stderr_ref: Mapped[str | None] = mapped_column(Text)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    timed_out: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    ran_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class StudentLookup(Base):
    __tablename__ = "student_lookup"
    __table_args__ = {"schema": "identity"}

    student_hash: Mapped[str] = mapped_column(Text, primary_key=True)
    assignment_id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    canvas_id: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
