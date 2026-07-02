"""Unit tests for the Phase 4 deterministic cores."""

from autograde_core.models import RubricQuestion
from services.graders.code_style.grader import lint_factor
from services.graders.common import parse_fraction_json
from services.graders.cross_check.checker import flags_for
from services.graders.derivation.grader import sympy_verified_steps
from services.graders.figure.grader import checklist
from services.graders.plagiarism.detector import fingerprints, jaccard, normalize


def test_parse_fraction_json() -> None:
    assert parse_fraction_json('{"score_fraction": 0.7, "confidence": 0.8, "reasoning": "ok"}') == (0.7, 0.8, "ok")
    frac, conf, _ = parse_fraction_json('{"score_fraction": 5, "confidence": -1, "reasoning": "x"}')
    assert frac == 1.0 and conf == 0.0
    assert parse_fraction_json("garbage") is None
    assert parse_fraction_json('{"score_fraction": 0.5, "confidence": 0.5, "reasoning": ""}') is None


def test_lint_factor_decays_with_density() -> None:
    clean = lint_factor([], "x = 1\n" * 20)
    dirty = lint_factor([{"code": "E501"}] * 10, "x = 1\n" * 20)
    assert clean == 1.0 and dirty < clean
    assert lint_factor([{"code": "E"}] * 100, "x=1") == 0.0  # floor


def test_sympy_verifies_parseable_equations() -> None:
    verified, attempted = sympy_verified_steps(
        ["Step 1: 2*x + x = 3*x", "Step 2: fact = fix(F)", "Step 3: (x+1)**2 = x**2 + 2*x + 1"]
    )
    # both real equations verify; the symbolic-definition step parses but
    # cannot be confirmed (attempted, unverified); true prose is skipped
    assert (verified, attempted) == (2, 3)
    assert sympy_verified_steps(["Step 1: if n = 0 then 1 else n * f(n-1)"]) == (0, 0)


def test_sympy_catches_wrong_equation() -> None:
    verified, attempted = sympy_verified_steps(["Step 1: 2*x = 3*x"])
    assert attempted == 1 and verified == 0


def test_figure_checklist() -> None:
    frac, items = checklist(
        "Plot measured runtime versus input size for your implementation.",
        "runtime (ms) input size 10 100 1000", {"size": [400, 300]},
    )
    assert frac == 1.0
    frac_bad, _ = checklist("Plot runtime versus input size.", "", {"size": [50, 40]})
    assert frac_bad == 0.0


def test_plagiarism_fingerprints() -> None:
    a = "def cps(ast, k):\n    return k(ast)  # comment\n"
    b = "def cps(ast, k):\n    return k(ast)\n"
    c = "class Totally:\n    def different(self, x):\n        return x * 99\n"
    fa, fb, fc = (fingerprints(normalize(s)) for s in (a, b, c))
    assert jaccard(fa, fb) == 1.0  # comments stripped -> identical
    assert jaccard(fa, fc) < 0.3


def _g(grader, qid, score, max_score, conf=0.9):
    return {"grader": grader, "question_id": qid, "score": score,
            "max_score": max_score, "confidence": conf, "reasoning": "r"}


def test_crosschecker_flags() -> None:
    inversion = flags_for([
        _g("CodeExecutionGrader", "q2", 20, 20), _g("TheoryGrader", "q1", 0, 10),
    ])
    assert any(f["flag"] == "hard_easy_inversion" for f in inversion)

    gap = flags_for([
        _g("CodeExecutionGrader", "q2", 20, 20), _g("CodeStyleGrader", "q2", 0.4, 4),
    ])
    assert any(f["flag"] == "exec_style_gap" for f in gap)

    plag = flags_for([_g("PlagiarismDetector", "q2", 0.92, 1.0)])
    assert any(f["flag"] == "plagiarism" for f in plag)

    assert flags_for([_g("TheoryGrader", "q1", 8, 10)]) == []


def test_style_fraction_of_weight() -> None:
    q = RubricQuestion(question_id="q2", type="code", weight=20, prompt="p")
    from services.graders.code_style.grader import STYLE_FRACTION

    assert q.weight * STYLE_FRACTION == 4.0
