"""Shared helpers for Phase 4 graders: rubric lookup, fraction-JSON parsing,
grade persistence."""

from __future__ import annotations

import json
import re
from uuid import UUID, uuid4

from autograde_core.hashing import assignment_id_for
from autograde_core.models import Rubric, RubricQuestion


def question_for(assignment_key: str, question_id: str) -> RubricQuestion:
    from autograde_db.models import Assignment
    from autograde_db.session import session_scope

    with session_scope() as session:
        row = session.get(Assignment, assignment_id_for(assignment_key))
        if row is None:
            raise LookupError(f"assignment '{assignment_key}' not found")
        rubric = Rubric.model_validate(row.rubric)
    for q in rubric.questions:
        if q.question_id == question_id:
            return q
    raise LookupError(f"question '{question_id}' not found in '{assignment_key}'")


def parse_fraction_json(text: str) -> tuple[float, float, str] | None:
    """Parse {"score_fraction": 0-1, "confidence": 0-1, "reasoning": str}, clamped."""
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        body = json.loads(match.group(0))
        fraction = min(max(float(body.get("score_fraction", 0.0)), 0.0), 1.0)
        confidence = min(max(float(body.get("confidence", 0.0)), 0.0), 1.0)
        reasoning = str(body.get("reasoning", "")).strip()
    except (json.JSONDecodeError, TypeError, ValueError):
        return None
    return (fraction, confidence, reasoning) if reasoning else None


def persist_grade(
    *,
    grader: str,
    artifact: dict,
    question_id: str,
    score: float,
    max_score: float,
    confidence: float,
    reasoning: str,
    breakdown: list[dict],
    citations: list[dict] | None = None,
    llm_call_id: str | None = None,
    sandbox_run_id: str | None = None,
) -> str:
    from autograde_db.models import Grade
    from autograde_db.session import session_scope

    grade_id = uuid4()
    with session_scope() as session:
        session.add(
            Grade(
                id=grade_id,
                submission_id=UUID(artifact["submission_id"]),
                question_id=question_id,
                grader=grader,
                score=score,
                max_score=max_score,
                confidence=confidence,
                reasoning=reasoning,
                rubric_breakdown=breakdown,
                retrieval_citations=citations,
                llm_call_id=UUID(llm_call_id) if llm_call_id else None,
                sandbox_run_id=UUID(sandbox_run_id) if sandbox_run_id else None,
            )
        )
    return str(grade_id)


def complete_with_repair(client, request):
    """One LLM call with a single JSON-format repair retry. Returns (result, parsed)."""
    result = client.complete(request)
    parsed = parse_fraction_json(result.text)
    if parsed is None:
        repair = request.model_copy(
            update={"prompt": request.prompt + "\n\nYour previous reply was not valid JSON. JSON only."}
        )
        result = client.complete(repair)
        parsed = parse_fraction_json(result.text)
    return result, parsed
