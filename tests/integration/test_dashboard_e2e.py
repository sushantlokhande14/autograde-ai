"""Phase 5 e2e: the instructor loop through the GraphQL API.

Progress → review queue → approve/edit → audit trail → rubric validate →
preview-grade, all against the live stack and graded class data. (The Next.js
views call exactly these operations.)

Opt-in:
    AUTOGRADE_RUN_INTEGRATION=1 uv run pytest tests/integration/test_dashboard_e2e.py -q
"""

from __future__ import annotations

import json
import os
from uuid import UUID

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("AUTOGRADE_RUN_INTEGRATION") != "1",
    reason="stack not running; set AUTOGRADE_RUN_INTEGRATION=1 to enable",
)


@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient

    from services.api.main import app

    return TestClient(app)


def gql(client, query: str, variables: dict | None = None) -> dict:
    resp = client.post("/graphql", json={"query": query, "variables": variables or {}})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert not body.get("errors"), body["errors"]
    return body["data"]


def test_progress_reflects_graded_class(client) -> None:
    data = gql(client, '{ progress(assignmentId: "cs152-hw3") { submissions gradedSubmissions pendingReviews } }')
    p = data["progress"]
    assert p["submissions"] >= 250
    assert p["gradedSubmissions"] >= 250
    assert p["pendingReviews"] > 0


def test_review_queue_sorted_by_confidence(client) -> None:
    rows = gql(client, "{ pendingReviews(limit: 50) { reviewId confidence } }")["pendingReviews"]
    assert rows
    confidences = [r["confidence"] or 0.0 for r in rows]
    assert confidences == sorted(confidences)


def test_approve_and_edit_persist(client) -> None:
    from autograde_db.models import Review
    from autograde_db.session import session_scope

    rows = gql(client, "{ pendingReviews(limit: 2) { reviewId originalScore } }")["pendingReviews"]
    target = rows[0]

    gql(client, """
        mutation($id: String!, $score: Float) {
          approveReview(reviewId: $id, finalScore: $score, notes: "e2e edit") { status }
        }""", {"id": target["reviewId"], "score": target["originalScore"] + 1.0})

    with session_scope() as s:
        row = s.get(Review, UUID(target["reviewId"]))
        assert row.status == "edited"
        assert row.final_score == target["originalScore"] + 1.0
        # restore so reruns stay stable
        row.status = "pending"
        row.final_score = None
        row.reviewed_at = None


def test_audit_trail_three_clicks(client) -> None:
    from sqlalchemy import select

    from autograde_db.models import Grade
    from autograde_db.session import session_scope

    with session_scope() as s:
        grade = s.scalars(select(Grade).where(
            Grade.grader == "TheoryGrader", Grade.llm_call_id.is_not(None)).limit(1)).first()
    data = gql(client, """
        query($id: String!) { audit(gradeId: $id) {
          grade { grader reasoning } model prompt citationsJson } }""",
        {"id": str(grade.id)})
    audit = data["audit"]
    assert audit["grade"]["reasoning"]
    assert audit["model"]
    assert audit["prompt"] and "STUDENT_ANSWER_BEGIN" in audit["prompt"]
    assert json.loads(audit["citationsJson"])


def test_rubric_validate_surfaces_errors(client) -> None:
    bad = json.dumps({"assignment_id": "x", "title": "t", "questions": [
        {"question_id": "q1", "type": "essay", "weight": 0, "prompt": "p"}]})
    check = gql(client, """
        mutation($r: String!) { validateRubric(rubricJson: $r) { valid errors } }""",
        {"r": bad})["validateRubric"]
    assert not check["valid"]
    assert any("unknown type" in e for e in check["errors"])
    assert any("weight" in e for e in check["errors"])


def test_preview_grade_runs_model(client) -> None:
    rubric = json.dumps({
        "assignment_id": "preview-test", "title": "t", "questions": [{
            "question_id": "q1", "type": "theory", "weight": 10,
            "prompt": "Explain call-by-name vs call-by-value.",
            "rubric_criteria": [
                {"criterion": "definitions", "points": 6},
                {"criterion": "example", "points": 4}]}]})
    grade = gql(client, """
        mutation($r: String!, $q: String!, $a: String!) {
          previewGrade(rubricJson: $r, questionId: $q, sampleAnswer: $a) {
            score maxScore confidence reasoning } }""",
        {"r": rubric, "q": "q1",
         "a": "Call-by-value evaluates arguments before the call; call-by-name "
              "substitutes them unevaluated, e.g. const(1, loop()) terminates."},
    )["previewGrade"]
    assert 0 <= grade["score"] <= grade["maxScore"] == 10
    assert grade["reasoning"]
