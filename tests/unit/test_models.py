from uuid import uuid4

from autograde_core.models import (
    Artifact,
    ArtifactType,
    CodeContent,
    FigureContent,
    Rubric,
    TheoryContent,
)


def test_code_artifact_roundtrips_via_discriminator() -> None:
    a = Artifact(
        artifact_id=uuid4(),
        submission_id=uuid4(),
        source_file="hw3.py",
        artifact_type=ArtifactType.CODE,
        content=CodeContent(language="python", source="x = 1", functions=["f"]),
    )
    back = Artifact.model_validate_json(a.model_dump_json())
    assert isinstance(back.content, CodeContent)
    assert back.content.functions == ["f"]


def test_theory_and_figure_discriminated() -> None:
    theory = Artifact(
        artifact_id=uuid4(),
        submission_id=uuid4(),
        source_file="q1.pdf",
        artifact_type=ArtifactType.THEORY,
        content=TheoryContent(text="an answer"),
    )
    assert isinstance(Artifact.model_validate_json(theory.model_dump_json()).content, TheoryContent)

    figure = Artifact(
        artifact_id=uuid4(),
        submission_id=uuid4(),
        source_file="plot.png",
        artifact_type=ArtifactType.FIGURE,
        content=FigureContent(image_ref="raw-submissions/x/plot.png", ocr_text="y=x"),
    )
    assert isinstance(Artifact.model_validate_json(figure.model_dump_json()).content, FigureContent)


def test_rubric_parses_project_plan_shape() -> None:
    rubric = Rubric.model_validate(
        {
            "assignment_id": "cs152-hw3",
            "title": "CPS",
            "grading_backend": "local",
            "questions": [
                {
                    "question_id": "q1",
                    "type": "theory",
                    "weight": 10,
                    "prompt": "Explain call-by-name vs call-by-value.",
                    "rubric_criteria": [{"criterion": "def", "points": 3}],
                }
            ],
        }
    )
    assert rubric.questions[0].question_id == "q1"
    assert rubric.questions[0].rubric_criteria[0].points == 3
