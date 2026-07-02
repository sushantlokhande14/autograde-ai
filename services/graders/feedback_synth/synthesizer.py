"""Aggregation + FeedbackSynthesizer: the per-submission close-out.

``aggregate(submission_id)``:
  * per-question final score — execution/style blend for code questions
    (default 0.8/0.2), pass-through otherwise; persisted as 'FinalAggregate'
    grade rows;
  * CrossChecker flags persisted as an 'overall' row; each flag lowers overall
    confidence by its penalty;
  * questions whose confidence lands under the gate get pending
    ``grading.reviews`` rows — the queue Phase 5 renders;
  * one capped LLM call composes student-facing narrative feedback, stored as
    the 'FeedbackSynthesizer' overall row.
"""

from __future__ import annotations

import json
from uuid import UUID

import structlog

from autograde_core.config import get_settings
from autograde_llm import CompletionRequest, LLMClient
from autograde_llm.audited import grading_client
from services.graders.common import persist_grade
from services.graders.cross_check.checker import CONFIDENCE_PENALTY, flags_for
from services.question_mapper.mapper import CONFIDENCE_GATE

log = structlog.get_logger()

EXEC_WEIGHT, STYLE_WEIGHT = 0.8, 0.2

FEEDBACK_SYSTEM = (
    "You write concise, encouraging, specific feedback to a student from their "
    "grading results. Address the student directly. No JSON, no headers — "
    "one paragraph of 4-7 sentences."
)


def _grade_rows(submission_id: str) -> list[dict]:
    from sqlalchemy import select

    from autograde_db.models import Grade
    from autograde_db.session import session_scope

    with session_scope() as session:
        rows = session.scalars(
            select(Grade).where(Grade.submission_id == UUID(submission_id))
        )
        return [
            {"grader": g.grader, "question_id": g.question_id, "score": g.score,
             "max_score": g.max_score, "confidence": g.confidence,
             "reasoning": g.reasoning}
            for g in rows
            if g.grader not in ("FinalAggregate", "CrossChecker", "FeedbackSynthesizer")
        ]


def aggregate(submission_id: str, client: LLMClient | None = None) -> dict:
    grades = _grade_rows(submission_id)
    if not grades:
        return {"submission_id": submission_id, "questions": {}, "flags": [], "overall_confidence": 0.0}

    flags = flags_for(grades)
    artifact = {"submission_id": submission_id}

    finals: dict[str, dict] = {}
    for qid in sorted({g["question_id"] for g in grades if g["question_id"] != "overall"}):
        q_grades = [g for g in grades if g["question_id"] == qid]
        execution = next((g for g in q_grades if g["grader"] == "CodeExecutionGrader"), None)
        style = next((g for g in q_grades if g["grader"] == "CodeStyleGrader"), None)
        primary = [g for g in q_grades if g["grader"] in
                   ("TheoryGrader", "DerivationGrader", "FigureGrader")]
        if execution is not None:
            exec_frac = execution["score"] / execution["max_score"] if execution["max_score"] else 0
            style_frac = (style["score"] / style["max_score"]) if style and style["max_score"] else exec_frac
            max_score = execution["max_score"]  # question weight
            score = round(max_score * (EXEC_WEIGHT * exec_frac + STYLE_WEIGHT * style_frac), 2)
            confidence = min(execution["confidence"], style["confidence"] if style else 1.0)
        elif primary:
            g = primary[0]
            score, max_score, confidence = g["score"], g["max_score"], g["confidence"]
        else:
            continue  # plagiarism-only questions never aggregate
        finals[qid] = {"score": score, "max_score": max_score, "confidence": confidence}

    overall_confidence = min((f["confidence"] for f in finals.values()), default=0.0)
    overall_confidence = max(0.0, overall_confidence - CONFIDENCE_PENALTY * len(flags))

    persist_grade(
        grader="CrossChecker", artifact=artifact, question_id="overall",
        score=float(len(flags)), max_score=0.0, confidence=1.0,
        reasoning="; ".join(f"{f['flag']}: {f['detail']}" for f in flags) or "no inconsistencies detected",
        breakdown=flags,
    )
    for qid, final in finals.items():
        persist_grade(
            grader="FinalAggregate", artifact=artifact, question_id=qid,
            score=final["score"], max_score=final["max_score"],
            confidence=final["confidence"],
            reasoning=f"exec {EXEC_WEIGHT}/style {STYLE_WEIGHT} blend" if qid == "q2" else "single-grader pass-through",
            breakdown=[final],
        )
        if final["confidence"] < CONFIDENCE_GATE or flags:
            _enqueue_review(submission_id, qid, final["score"])

    narrative = _feedback(grades, finals, client)
    persist_grade(
        grader="FeedbackSynthesizer", artifact=artifact, question_id="overall",
        score=round(sum(f["score"] for f in finals.values()), 2),
        max_score=round(sum(f["max_score"] for f in finals.values()), 2),
        confidence=overall_confidence, reasoning=narrative, breakdown=[],
    )
    return {"submission_id": submission_id, "questions": finals, "flags": flags,
            "overall_confidence": overall_confidence}


def _enqueue_review(submission_id: str, question_id: str, score: float) -> None:
    from sqlalchemy import select

    from autograde_db.models import Review
    from autograde_db.session import session_scope

    with session_scope() as session:
        exists = session.scalars(
            select(Review)
            .where(Review.submission_id == UUID(submission_id))
            .where(Review.question_id == question_id)
            .where(Review.status == "pending")
        ).first()
        if exists is None:
            session.add(Review(
                submission_id=UUID(submission_id), question_id=question_id,
                status="pending", original_score=score,
            ))


def _feedback(grades: list[dict], finals: dict, client: LLMClient | None) -> str:
    summary = json.dumps(
        [{"q": g["question_id"], "grader": g["grader"],
          "score": f"{g['score']}/{g['max_score']}",
          "note": g["reasoning"][:150]} for g in grades],
    )
    client = client or grading_client("FeedbackSynthesizer")
    result = client.complete(CompletionRequest(
        system=FEEDBACK_SYSTEM,
        prompt=f"GRADING RESULTS:\n{summary}\n\nWrite the feedback paragraph now.",
        model=get_settings().local_model_theory, max_tokens=350, temperature=0.2,
    ))
    return result.text.strip() or "Feedback generation failed; see per-question reasoning."
