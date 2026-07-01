import json

import pytest

from autograde_core.rubric import RubricValidationError, load_rubric, validate_rubric


def _valid() -> dict:
    return {
        "assignment_id": "cs152-hw3",
        "title": "CPS",
        "grading_backend": "local",
        "questions": [
            {
                "question_id": "q1",
                "type": "theory",
                "weight": 10,
                "prompt": "Explain X.",
                "rubric_criteria": [
                    {"criterion": "a", "points": 4},
                    {"criterion": "b", "points": 6},
                ],
            },
            {
                "question_id": "q2",
                "type": "code",
                "weight": 20,
                "prompt": "Implement Y.",
                "test_cases": [
                    {"id": "t1", "weight": 0.4},
                    {"id": "t2", "weight": 0.6},
                ],
            },
        ],
    }


def test_valid_rubric_passes() -> None:
    rubric = validate_rubric(_valid())
    assert [q.question_id for q in rubric.questions] == ["q1", "q2"]


def _errors_for(data: dict) -> list[str]:
    with pytest.raises(RubricValidationError) as exc:
        validate_rubric(data)
    return [str(e) for e in exc.value.errors]


def test_duplicate_question_ids() -> None:
    data = _valid()
    data["questions"][1]["question_id"] = "q1"
    assert any("duplicate id 'q1'" in e for e in _errors_for(data))


def test_unknown_type_and_bad_weight() -> None:
    data = _valid()
    data["questions"][0]["type"] = "essay"
    data["questions"][0]["weight"] = 0
    errs = _errors_for(data)
    assert any("unknown type 'essay'" in e for e in errs)
    assert any("weight must be > 0" in e for e in errs)


def test_criteria_sum_mismatch() -> None:
    data = _valid()
    data["questions"][0]["rubric_criteria"][0]["points"] = 5  # 5+6 != 10
    errs = _errors_for(data)
    assert any("criteria points sum to 11" in e and "questions[0]" in e for e in errs)


def test_test_case_weights_must_sum_to_one() -> None:
    data = _valid()
    data["questions"][1]["test_cases"][1]["weight"] = 0.7
    errs = _errors_for(data)
    assert any("test case weights" in e for e in errs)


def test_structural_error_has_field_path() -> None:
    data = _valid()
    del data["questions"][0]["prompt"]
    errs = _errors_for(data)
    assert any("questions.0.prompt" in e for e in errs)


def test_empty_questions() -> None:
    data = _valid()
    data["questions"] = []
    assert any("no questions" in e for e in _errors_for(data))


def test_load_rubric_roundtrip(tmp_path) -> None:
    p = tmp_path / "rubric.json"
    p.write_text(json.dumps(_valid()))
    rubric = load_rubric(p)  # persist=False: no DB needed
    assert rubric.assignment_id == "cs152-hw3"


def test_generated_rubric_is_valid() -> None:
    # The Phase 1 generator's rubric must satisfy the validator.
    import sys

    sys.path.insert(0, "scripts")
    from seed_synthetic_data import RUBRIC

    rubric = validate_rubric(RUBRIC)
    assert len(rubric.questions) == 4
