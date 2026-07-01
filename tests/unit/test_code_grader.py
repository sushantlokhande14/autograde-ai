from uuid import uuid4

from autograde_core.models import RubricQuestion
from services.graders.code_execution.grader import (
    deterministic_score,
    parse_interpretation,
)
from services.graders.code_execution.sandbox import SandboxResult

QUESTION = RubricQuestion(
    question_id="q2",
    type="code",
    weight=20,
    prompt="Implement CPS.",
    harness_prelude="def apply(op,a,b): ...",
    test_cases=[
        {"id": "t1", "weight": 0.2, "expr": "cps(5, lambda v: v)", "expected": 5},
        {"id": "t2", "weight": 0.4, "expr": "cps(('+',2,3), lambda v: v)", "expected": 5},
        {"id": "t3", "weight": 0.4, "expr": "cps(('*',1,4), lambda v: v)", "expected": 4},
    ],
)


def _result(cases: list[dict], timed_out: bool = False) -> SandboxResult:
    return SandboxResult(
        run_id=uuid4(), exit_code=0 if not timed_out else None, timed_out=timed_out,
        duration_ms=500, case_results=cases, fatal_error=None,
        stdout_ref="x/stdout.log", stderr_ref="x/stderr.log",
    )


def test_all_pass_full_score() -> None:
    score, breakdown = deterministic_score(
        QUESTION,
        _result([{"id": "t1", "ok": True}, {"id": "t2", "ok": True}, {"id": "t3", "ok": True}]),
    )
    assert score == 20.0
    assert sum(b["awarded"] for b in breakdown) == 20.0


def test_partial_pass_weighted() -> None:
    score, breakdown = deterministic_score(
        QUESTION,
        _result([{"id": "t1", "ok": True}, {"id": "t2", "ok": False, "error": "AssertionError"},
                 {"id": "t3", "ok": True}]),
    )
    assert score == (0.2 + 0.4) * 20
    assert breakdown[1]["awarded"] == 0.0 and breakdown[1]["error"] == "AssertionError"


def test_missing_results_score_zero() -> None:
    # timeout/fatal: no case results at all -> 0, injection-proof default
    score, breakdown = deterministic_score(QUESTION, _result([], timed_out=True))
    assert score == 0.0
    assert all(b["awarded"] == 0.0 for b in breakdown)


def test_parse_interpretation_valid_and_clamped() -> None:
    assert parse_interpretation('{"confidence": 0.9, "reasoning": "t2 fails on nesting."}') == (
        0.9, "t2 fails on nesting.",
    )
    conf, _ = parse_interpretation('{"confidence": 99, "reasoning": "x"}')
    assert conf == 1.0


def test_parse_interpretation_garbage() -> None:
    assert parse_interpretation("not json") is None
    assert parse_interpretation('{"confidence": 0.5, "reasoning": ""}') is None
