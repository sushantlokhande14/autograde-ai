"""GraphQL schema for the instructor dashboard.

Strawberry on FastAPI. Resolvers reuse the repository/session layer and MinIO
helpers; the audit query stitches the full evidence chain (grade → prompt →
citations → sandbox logs) so the UI is never more than three clicks from why.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncGenerator
from uuid import UUID

import strawberry

from autograde_core import storage
from autograde_core.hashing import assignment_id_for


# --- types -------------------------------------------------------------------


@strawberry.type
class QuestionProgress:
    question_id: str
    graded: int
    pending_review: int


@strawberry.type
class Progress:
    assignment_id: str
    submissions: int
    graded_submissions: int
    pending_reviews: int
    auto_approved: int
    questions: list[QuestionProgress]


@strawberry.type
class GradeRow:
    grade_id: str
    submission_id: str
    question_id: str
    grader: str
    score: float
    max_score: float
    confidence: float
    reasoning: str
    llm_call_id: str | None
    sandbox_run_id: str | None
    breakdown_json: str


@strawberry.type
class ReviewItem:
    review_id: str
    submission_id: str
    student_hash: str
    question_id: str
    status: str
    original_score: float
    final_score: float | None
    confidence: float | None
    flags: str


@strawberry.type
class AuditTrail:
    grade: GradeRow
    prompt: str | None
    response: str | None
    model: str | None
    cache_hit: bool | None
    citations_json: str
    sandbox_stdout: str | None
    sandbox_stderr: str | None


@strawberry.type
class RubricCheck:
    valid: bool
    errors: list[str]


@strawberry.type
class PreviewGrade:
    score: float
    max_score: float
    confidence: float
    reasoning: str


# --- helpers -----------------------------------------------------------------


def _session():
    from autograde_db.session import session_scope

    return session_scope()


def _grade_row(g) -> GradeRow:
    return GradeRow(
        grade_id=str(g.id), submission_id=str(g.submission_id),
        question_id=g.question_id, grader=g.grader, score=g.score,
        max_score=g.max_score, confidence=g.confidence, reasoning=g.reasoning,
        llm_call_id=str(g.llm_call_id) if g.llm_call_id else None,
        sandbox_run_id=str(g.sandbox_run_id) if g.sandbox_run_id else None,
        breakdown_json=json.dumps(g.rubric_breakdown or []),
    )


def _progress(assignment_key: str) -> Progress:
    from sqlalchemy import func, select

    from autograde_db.models import Grade, Review, Submission

    auuid = assignment_id_for(assignment_key)
    with _session() as s:
        subs = s.scalar(select(func.count()).select_from(Submission).where(
            Submission.assignment_id == auuid))
        sub_ids = select(Submission.id).where(Submission.assignment_id == auuid)
        graded = s.scalar(select(func.count(func.distinct(Grade.submission_id))).where(
            Grade.grader == "FinalAggregate", Grade.submission_id.in_(sub_ids)))
        pending = s.scalar(select(func.count()).select_from(Review).where(
            Review.status == "pending", Review.submission_id.in_(sub_ids)))
        q_rows = s.execute(
            select(Grade.question_id, func.count()).where(
                Grade.grader == "FinalAggregate", Grade.submission_id.in_(sub_ids)
            ).group_by(Grade.question_id)).all()
        q_pending = dict(s.execute(
            select(Review.question_id, func.count()).where(
                Review.status == "pending", Review.submission_id.in_(sub_ids)
            ).group_by(Review.question_id)).all())
    return Progress(
        assignment_id=assignment_key, submissions=subs or 0,
        graded_submissions=graded or 0, pending_reviews=pending or 0,
        auto_approved=max((graded or 0) - (pending or 0), 0),
        questions=[QuestionProgress(question_id=q, graded=c,
                                    pending_review=q_pending.get(q, 0))
                   for q, c in sorted(q_rows)],
    )


# --- query / mutation / subscription -----------------------------------------


@strawberry.type
class Query:
    @strawberry.field
    def progress(self, assignment_id: str) -> Progress:
        return _progress(assignment_id)

    @strawberry.field
    def pending_reviews(self, limit: int = 100) -> list[ReviewItem]:
        from sqlalchemy import select

        from autograde_db.models import Grade, Review, Submission

        with _session() as s:
            rows = s.execute(
                select(Review, Submission.student_hash)
                .join(Submission, Review.submission_id == Submission.id)
                .where(Review.status == "pending").limit(limit)).all()
            items = []
            for review, student_hash in rows:
                final = s.execute(
                    select(Grade).where(
                        Grade.submission_id == review.submission_id,
                        Grade.question_id == review.question_id,
                        Grade.grader == "FinalAggregate")).scalars().first()
                checker = s.execute(
                    select(Grade).where(
                        Grade.submission_id == review.submission_id,
                        Grade.grader == "CrossChecker")).scalars().first()
                items.append(ReviewItem(
                    review_id=str(review.id), submission_id=str(review.submission_id),
                    student_hash=student_hash[:12], question_id=review.question_id,
                    status=review.status, original_score=review.original_score,
                    final_score=review.final_score,
                    confidence=final.confidence if final else None,
                    flags=checker.reasoning if checker else ""))
        items.sort(key=lambda i: (i.confidence if i.confidence is not None else 0.0))
        return items

    @strawberry.field
    def grades(self, submission_id: str) -> list[GradeRow]:
        from sqlalchemy import select

        from autograde_db.models import Grade

        with _session() as s:
            rows = s.scalars(select(Grade).where(
                Grade.submission_id == UUID(submission_id))).all()
        return [_grade_row(g) for g in rows]

    @strawberry.field
    def audit(self, grade_id: str) -> AuditTrail | None:
        from sqlalchemy import select

        from autograde_db.models import Grade, LlmCall, SandboxRun

        with _session() as s:
            grade = s.get(Grade, UUID(grade_id))
            if grade is None:
                return None
            call = s.get(LlmCall, grade.llm_call_id) if grade.llm_call_id else None
            run = s.get(SandboxRun, grade.sandbox_run_id) if grade.sandbox_run_id else None
            row = _grade_row(grade)
            citations = json.dumps(grade.retrieval_citations or [])

        prompt = response = None
        if call is not None and call.request_payload_ref:
            try:
                prompt = json.dumps(storage.get_json("llm-payloads", call.request_payload_ref), indent=2)
                response = json.dumps(storage.get_json("llm-payloads", call.response_payload_ref), indent=2)
            except Exception:  # noqa: BLE001 — payload eviction must not 500 the audit
                pass
        stdout = stderr = None
        if run is not None:
            try:
                stdout = storage.get_bytes("sandbox-logs", run.stdout_ref).decode(errors="replace")[-4000:]
                stderr = storage.get_bytes("sandbox-logs", run.stderr_ref).decode(errors="replace")[-4000:]
            except Exception:  # noqa: BLE001
                pass
        return AuditTrail(
            grade=row, prompt=prompt, response=response,
            model=call.model if call else None,
            cache_hit=call.cache_hit if call else None,
            citations_json=citations, sandbox_stdout=stdout, sandbox_stderr=stderr)


@strawberry.type
class Mutation:
    @strawberry.mutation
    def approve_review(self, review_id: str, final_score: float | None = None,
                       notes: str | None = None) -> ReviewItem | None:
        from datetime import UTC, datetime

        from autograde_db.models import Review

        with _session() as s:
            review = s.get(Review, UUID(review_id))
            if review is None:
                return None
            review.status = "edited" if final_score is not None else "approved"
            review.final_score = final_score if final_score is not None else review.original_score
            review.reviewer_notes = notes
            review.reviewed_at = datetime.now(UTC)
            return ReviewItem(
                review_id=str(review.id), submission_id=str(review.submission_id),
                student_hash="", question_id=review.question_id, status=review.status,
                original_score=review.original_score, final_score=review.final_score,
                confidence=None, flags="")

    @strawberry.mutation
    async def regrade_submission(self, submission_id: str) -> str:
        import time

        from temporalio.client import Client

        from autograde_core.config import get_settings

        client = await Client.connect(get_settings().temporal_address)
        workflow_id = f"regrade-{submission_id}-{int(time.time())}"
        await client.start_workflow(
            "GradeStudentWorkflow", submission_id,
            id=workflow_id, task_queue="grading")
        return workflow_id

    @strawberry.mutation
    def validate_rubric(self, rubric_json: str) -> RubricCheck:
        from autograde_core.rubric import RubricValidationError, validate_rubric

        try:
            validate_rubric(json.loads(rubric_json))
            return RubricCheck(valid=True, errors=[])
        except json.JSONDecodeError as exc:
            return RubricCheck(valid=False, errors=[f"not valid JSON: {exc}"])
        except RubricValidationError as exc:
            return RubricCheck(valid=False, errors=[str(e) for e in exc.errors])

    @strawberry.mutation
    def preview_grade(self, rubric_json: str, question_id: str, sample_answer: str) -> PreviewGrade:
        """Grade a pasted sample answer against one rubric question, without
        touching the database — the rubric-authoring feedback loop."""
        from autograde_core.models import Rubric
        from autograde_llm.audited import grading_client
        from services.graders.theory.grader import SYSTEM, build_prompt, parse_response

        rubric = Rubric.model_validate(json.loads(rubric_json))
        question = next(q for q in rubric.questions if q.question_id == question_id)
        _, prompt = build_prompt(question, [], sample_answer)

        from autograde_core.config import get_settings
        from autograde_llm import CompletionRequest

        result = grading_client("PreviewGrader").complete(CompletionRequest(
            system=SYSTEM, prompt=prompt, model=get_settings().local_model_theory,
            max_tokens=400, temperature=0.0))
        parsed = parse_response(result.text, question)
        if parsed is None:
            return PreviewGrade(score=0, max_score=question.weight, confidence=0,
                                reasoning="model returned unparseable output; try again")
        return PreviewGrade(score=parsed["score"], max_score=parsed["max_score"],
                            confidence=parsed["confidence"], reasoning=parsed["reasoning"])


@strawberry.type
class Subscription:
    @strawberry.subscription
    async def progress(
        self, assignment_id: str, interval_s: float = 2.0
    ) -> AsyncGenerator[Progress, None]:
        """Live progress: DB-backed watch at dev scale (Kafka push is an
        internal swap later). Emits only on change."""
        last = None
        while True:
            current = await asyncio.to_thread(_progress, assignment_id)
            snapshot = (current.submissions, current.graded_submissions,
                        current.pending_reviews)
            if snapshot != last:
                last = snapshot
                yield current
            await asyncio.sleep(interval_s)


schema = strawberry.Schema(query=Query, mutation=Mutation, subscription=Subscription)
