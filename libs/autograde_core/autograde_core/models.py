"""Canonical data models for the ingestion pipeline.

The `Artifact` is the unit every grader downstream reasons about: a normalized,
type-tagged piece of a student's submission with a best-guess question mapping.
Its JSON body is stored in MinIO (`normalized-artifacts/`) and referenced from
`grading.artifacts`. Rubric models mirror design spec §7.6.
"""

from __future__ import annotations

from enum import Enum
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class ArtifactType(str, Enum):
    THEORY = "theory"
    CODE = "code"
    FIGURE = "figure"
    DERIVATION = "derivation"
    UNKNOWN = "unknown"


class TheoryContent(BaseModel):
    kind: Literal["theory"] = "theory"
    text: str


class CodeContent(BaseModel):
    kind: Literal["code"] = "code"
    language: str
    source: str
    imports: list[str] = Field(default_factory=list)
    functions: list[str] = Field(default_factory=list)
    entry_points: list[str] = Field(default_factory=list)


class FigureContent(BaseModel):
    kind: Literal["figure"] = "figure"
    image_ref: str
    ocr_text: str | None = None
    caption: str | None = None


class DerivationContent(BaseModel):
    kind: Literal["derivation"] = "derivation"
    raw_text: str
    steps: list[str] = Field(default_factory=list)


class UnknownContent(BaseModel):
    kind: Literal["unknown"] = "unknown"
    note: str = ""
    raw_ref: str | None = None


ArtifactContent = Annotated[
    TheoryContent | CodeContent | FigureContent | DerivationContent | UnknownContent,
    Field(discriminator="kind"),
]


class Artifact(BaseModel):
    """A normalized piece of a submission. Persisted body of `grading.artifacts`."""

    artifact_id: UUID
    submission_id: UUID
    source_file: str
    artifact_type: ArtifactType
    question_id: str | None = None
    question_mapping_confidence: float | None = None
    content_ref: str | None = None
    content: ArtifactContent
    metadata: dict = Field(default_factory=dict)


# --- Rubric (design spec §7.6) ---------------------------------------------


class RubricCriterion(BaseModel):
    criterion: str
    points: float


class RubricQuestion(BaseModel):
    question_id: str
    type: str
    weight: float = 0.0
    prompt: str
    reference_answer: str | None = None
    rubric_criteria: list[RubricCriterion] = Field(default_factory=list)
    grading_context: list[str] = Field(default_factory=list)
    test_cases: list[dict] = Field(default_factory=list)
    # Code questions: prelude exec'd before the student module in the sandbox
    # harness (helper functions the assignment provides).
    harness_prelude: str = ""
    style_criteria: list[str] = Field(default_factory=list)


class Rubric(BaseModel):
    assignment_id: str
    title: str
    grading_backend: str = "local"
    questions: list[RubricQuestion]
