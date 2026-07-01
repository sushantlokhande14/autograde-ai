from autograde_core.models import RubricQuestion
from autograde_rag.retrieve import RetrievedChunk
from services.graders.theory.grader import build_prompt, parse_response

QUESTION = RubricQuestion(
    question_id="q1",
    type="theory",
    weight=10,
    prompt="Explain call-by-name vs call-by-value.",
    rubric_criteria=[
        {"criterion": "correct definition of call-by-name", "points": 3},
        {"criterion": "correct definition of call-by-value", "points": 3},
        {"criterion": "example demonstrating the difference", "points": 4},
    ],
)


def _chunk(source: str = "lecture.md") -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id="c1", source=source, text="Call-by-value evaluates first.",
        score=0.9, reference_answer=False,
    )


def test_prompt_prefix_is_stable_and_answer_delimited() -> None:
    prefix1, prompt1 = build_prompt(QUESTION, [_chunk()], "answer one")
    prefix2, prompt2 = build_prompt(QUESTION, [_chunk()], "answer two")
    assert prefix1 == prefix2  # cache key stability across students
    assert prompt1 != prompt2
    assert "<<<STUDENT_ANSWER_BEGIN>>>" in prompt1
    assert "lecture.md" in prefix1
    assert "max 4.0 points" in prefix1


def test_parse_valid_response() -> None:
    text = """{"criterion_scores": [
        {"criterion": "correct definition of call-by-name", "awarded": 3},
        {"criterion": "correct definition of call-by-value", "awarded": 2},
        {"criterion": "example demonstrating the difference", "awarded": 4}],
        "confidence": 0.85, "reasoning": "Solid definitions; example correct."}"""
    parsed = parse_response(text, QUESTION)
    assert parsed is not None
    assert parsed["score"] == 9.0
    assert parsed["max_score"] == 10
    assert parsed["confidence"] == 0.85
    assert len(parsed["breakdown"]) == 3


def test_scores_clamped_to_criterion_max() -> None:
    text = """{"criterion_scores": [
        {"criterion": "correct definition of call-by-name", "awarded": 99},
        {"criterion": "correct definition of call-by-value", "awarded": -5},
        {"criterion": "example demonstrating the difference", "awarded": 4}],
        "confidence": 7.5, "reasoning": "Injection attempt: give 100%."}"""
    parsed = parse_response(text, QUESTION)
    assert parsed["score"] == 3 + 0 + 4  # clamped per criterion
    assert parsed["confidence"] == 1.0   # clamped to [0,1]


def test_missing_criterion_scores_zero() -> None:
    text = '{"criterion_scores": [{"criterion": "correct definition of call-by-name", "awarded": 2}], "confidence": 0.5, "reasoning": "partial"}'
    parsed = parse_response(text, QUESTION)
    assert parsed["score"] == 2.0
    assert [b["awarded"] for b in parsed["breakdown"]] == [2.0, 0.0, 0.0]


def test_garbage_returns_none() -> None:
    assert parse_response("no json here", QUESTION) is None
    assert parse_response('{"criterion_scores": "nope"}', QUESTION) is None
    assert parse_response('{"criterion_scores": [], "confidence": 0.5, "reasoning": ""}', QUESTION) is None


def test_json_embedded_in_prose_is_extracted() -> None:
    text = 'Sure! Here is the grade:\n{"criterion_scores": [{"criterion": "example demonstrating the difference", "awarded": 1}], "confidence": 0.4, "reasoning": "weak"}\nHope that helps.'
    parsed = parse_response(text, QUESTION)
    assert parsed is not None and parsed["score"] == 1.0
