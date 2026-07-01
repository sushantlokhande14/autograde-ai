import pytest

from metrics import agreement_within, brier_score


def test_agreement_within_tolerance() -> None:
    preds = [9.0, 8.0, 5.0, 10.0]
    gold = [9.5, 7.0, 5.0, 8.0]
    # diffs: 0.5, 1.0, 0.0, 2.0 -> within 1.0 (inclusive): q1, q2, q3 -> 3/4
    assert agreement_within(preds, gold, tol=1.0) == 0.75


def test_brier_perfect_and_worst() -> None:
    assert brier_score([1.0, 0.0], [True, False]) == 0.0
    assert brier_score([0.0, 1.0], [True, False]) == 1.0


def test_length_mismatch_raises() -> None:
    with pytest.raises(ValueError):
        agreement_within([1.0], [1.0, 2.0], tol=1.0)
