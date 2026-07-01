"""Eval metrics for the gold set.

These pure functions are used in Phase 6 to compute the resume numbers. They are
implemented now (they are small and standard) so the methodology is testable
before the eval set exists. See docs/EVALUATION.md.
"""

from __future__ import annotations

from collections.abc import Sequence


def agreement_within(preds: Sequence[float], golds: Sequence[float], tol: float) -> float:
    """Fraction of predictions within `tol` (absolute) of the gold score."""
    if len(preds) != len(golds):
        raise ValueError("preds and golds must be the same length")
    if not preds:
        return 0.0
    hits = sum(1 for p, g in zip(preds, golds, strict=True) if abs(p - g) <= tol)
    return hits / len(preds)


def brier_score(confidences: Sequence[float], correct: Sequence[bool]) -> float:
    """Mean squared error between confidence and correctness. Lower is better."""
    if len(confidences) != len(correct):
        raise ValueError("confidences and correct must be the same length")
    if not confidences:
        return 0.0
    return sum(
        (c - (1.0 if o else 0.0)) ** 2
        for c, o in zip(confidences, correct, strict=True)
    ) / len(confidences)
