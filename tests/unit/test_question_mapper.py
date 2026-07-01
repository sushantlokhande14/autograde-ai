from autograde_core.models import ArtifactType, Rubric
from autograde_llm.client import Backend, CompletionRequest, CompletionResult, LLMClient
from services.question_mapper.mapper import (
    CONFIDENCE_GATE,
    filename_cue,
    map_artifact,
)

RUBRIC = Rubric.model_validate(
    {
        "assignment_id": "cs152-hw3",
        "title": "t",
        "questions": [
            {"question_id": "q1", "type": "theory", "prompt": "Explain call-by-name vs call-by-value."},
            {"question_id": "q2", "type": "code", "prompt": "Implement CPS transformation."},
            {"question_id": "q3", "type": "derivation", "prompt": "Derive the fixed point of factorial."},
            {"question_id": "q4", "type": "figure", "prompt": "Plot runtime versus input size."},
        ],
    }
)


class FakeClient(LLMClient):
    def __init__(self, text: str) -> None:
        self.text = text

    def complete(self, request: CompletionRequest) -> CompletionResult:
        return CompletionResult(text=self.text, model="fake", backend=Backend.LOCAL)


def test_filename_cue_variants() -> None:
    assert filename_cue("q1.pdf", RUBRIC, ArtifactType.THEORY).question_id == "q1"
    assert filename_cue("Question_2.ipynb", RUBRIC, ArtifactType.CODE).question_id == "q2"
    assert filename_cue("part3.txt", RUBRIC, ArtifactType.DERIVATION).question_id == "q3"
    assert filename_cue("writeup.pdf", RUBRIC, ArtifactType.THEORY) is None
    assert filename_cue("q9.pdf", RUBRIC, ArtifactType.THEORY) is None


def test_filename_type_mismatch_is_gated() -> None:
    m = filename_cue("q2.pdf", RUBRIC, ArtifactType.THEORY)  # q2 is code
    assert m.question_id == "q2" and m.needs_review


def test_type_unique_short_circuits_llm() -> None:
    m = map_artifact(
        filename="plot.png",
        artifact_type=ArtifactType.FIGURE,
        text_excerpt="",
        rubric=RUBRIC,
        client=FakeClient("should not be called"),
    )
    assert m.question_id == "q4" and m.method == "type-unique" and not m.needs_review


def test_llm_path_valid_json() -> None:
    m = map_artifact(
        filename="writeup.pdf",
        artifact_type=ArtifactType.DERIVATION,  # q3 or q1 -> two candidates -> LLM
        text_excerpt="Step 1: fact = fix(F)...",
        rubric=RUBRIC,
        client=FakeClient('{"question_id": "q3", "confidence": 0.88}'),
    )
    assert m.question_id == "q3" and m.method == "llm" and not m.needs_review


def test_llm_garbage_degrades_to_review() -> None:
    for bad in ("not json", '{"question_id": "q9", "confidence": 0.9}', '{"confidence": "x"}'):
        m = map_artifact(
            filename="writeup.pdf",
            artifact_type=ArtifactType.DERIVATION,
            text_excerpt="text",
            rubric=RUBRIC,
            client=FakeClient(bad),
        )
        assert m.needs_review


def test_unknown_type_has_no_candidates() -> None:
    m = map_artifact(
        filename="weird.xyz",
        artifact_type=ArtifactType.UNKNOWN,
        text_excerpt="",
        rubric=RUBRIC,
        client=FakeClient("unused"),
    )
    assert m.question_id is None and m.needs_review
    assert CONFIDENCE_GATE == 0.6
