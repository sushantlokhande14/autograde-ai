"""Rubric validation and loading.

The pydantic models in ``autograde_core.models`` accept anything structurally
sound; this module adds the semantic rules a rubric must satisfy before an
assignment can be graded against it, with error messages an instructor can act
on (field path + what is wrong). ``load_rubric`` is the one path from a JSON
file to a validated ``Rubric`` and an ``grading.assignments`` upsert.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError

from autograde_core.models import Rubric

KNOWN_QUESTION_TYPES = {"theory", "code", "derivation", "figure"}


@dataclass
class RubricError:
    path: str      # e.g. "questions[2].rubric_criteria"
    message: str

    def __str__(self) -> str:
        return f"{self.path}: {self.message}"


class RubricValidationError(ValueError):
    def __init__(self, errors: list[RubricError]) -> None:
        self.errors = errors
        super().__init__("invalid rubric:\n" + "\n".join(f"  - {e}" for e in errors))


def validate_rubric(data: dict) -> Rubric:
    """Structural (pydantic) + semantic validation. Raises RubricValidationError."""
    try:
        rubric = Rubric.model_validate(data)
    except ValidationError as exc:
        errors = [
            RubricError(
                path=".".join(str(loc) for loc in err["loc"]) or "<root>",
                message=err["msg"],
            )
            for err in exc.errors()
        ]
        raise RubricValidationError(errors) from exc

    errors: list[RubricError] = []
    if not rubric.assignment_id.strip():
        errors.append(RubricError("assignment_id", "must be non-empty"))
    if not rubric.questions:
        errors.append(RubricError("questions", "rubric has no questions"))

    seen: set[str] = set()
    for i, q in enumerate(rubric.questions):
        path = f"questions[{i}]"
        if q.question_id in seen:
            errors.append(RubricError(f"{path}.question_id", f"duplicate id '{q.question_id}'"))
        seen.add(q.question_id)

        if q.type not in KNOWN_QUESTION_TYPES:
            errors.append(
                RubricError(
                    f"{path}.type",
                    f"unknown type '{q.type}' (expected one of {sorted(KNOWN_QUESTION_TYPES)})",
                )
            )
        if q.weight <= 0:
            errors.append(RubricError(f"{path}.weight", f"weight must be > 0, got {q.weight}"))
        if not q.prompt.strip():
            errors.append(RubricError(f"{path}.prompt", "must be non-empty"))

        if q.rubric_criteria:
            total = sum(c.points for c in q.rubric_criteria)
            if any(c.points <= 0 for c in q.rubric_criteria):
                errors.append(
                    RubricError(f"{path}.rubric_criteria", "criterion points must be > 0")
                )
            if abs(total - q.weight) > 1e-9:
                errors.append(
                    RubricError(
                        f"{path}.rubric_criteria",
                        f"criteria points sum to {total}, but weight is {q.weight}",
                    )
                )
        if q.type == "code":
            weights = [tc.get("weight") for tc in q.test_cases]
            if q.test_cases and any(w is None for w in weights):
                errors.append(
                    RubricError(f"{path}.test_cases", "every test case needs a weight")
                )
            elif q.test_cases:
                total_w = sum(float(w) for w in weights)
                if abs(total_w - 1.0) > 1e-9:
                    errors.append(
                        RubricError(
                            f"{path}.test_cases",
                            f"test case weights sum to {total_w}, expected 1.0",
                        )
                    )

    if errors:
        raise RubricValidationError(errors)
    return rubric


def load_rubric(path: str | Path, *, persist: bool = False) -> Rubric:
    """File → validated Rubric; optionally upsert grading.assignments."""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    rubric = validate_rubric(raw)

    if persist:
        from autograde_core.hashing import assignment_id_for
        from autograde_db import repository as repo
        from autograde_db.session import session_scope

        with session_scope() as session:
            repo.upsert_assignment(
                session,
                assignment_uuid=assignment_id_for(rubric.assignment_id),
                course_code=rubric.assignment_id.split("-")[0],
                title=rubric.title,
                rubric=rubric.model_dump(),
                grading_config={"grading_backend": rubric.grading_backend},
            )
    return rubric
