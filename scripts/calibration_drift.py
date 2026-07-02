"""CalibrationDrift: re-grade a frozen gold subset and alert on drift.

``freeze`` snapshots current theory-grade scores/confidences for a fixed,
deterministic subset. ``check`` re-runs TheoryGrader on the same artifacts
with an **uncached** client (a cache hit would trivially reproduce itself)
and alerts when the mean absolute score delta crosses the threshold — the
signal that a model/prompt/retrieval change moved the grading distribution.

Usage:
    uv run python scripts/calibration_drift.py freeze
    uv run python scripts/calibration_drift.py check --threshold 1.0
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

REFERENCE = Path("tests/eval/gold_set/drift_reference.json")
SUBSET = 10  # fixed gold submissions


def _subset_artifacts() -> list[dict]:
    from sqlalchemy import select

    from autograde_core.hashing import assignment_id_for
    from autograde_db.models import Artifact, Submission
    from autograde_db.session import session_scope

    auuid = assignment_id_for("gold-theory")
    with session_scope() as s:
        rows = s.execute(
            select(Artifact).join(Submission, Artifact.submission_id == Submission.id)
            .where(Submission.assignment_id == auuid)
            .where(Artifact.artifact_type == "theory")
            .where(Artifact.question_id.is_not(None))
            .order_by(Artifact.id)).scalars().all()[:SUBSET]
        return [{"artifact_id": str(a.id), "submission_id": str(a.submission_id),
                 "question_id": a.question_id, "content_ref": a.content_ref,
                 "artifact_type": a.artifact_type} for a in rows]


def _grade_uncached(artifacts: list[dict]) -> dict[str, dict]:
    from autograde_llm.audited import AuditedLLMClient
    from autograde_llm.ollama_backend import OllamaClient
    from services.graders.theory.grader import grade

    client = AuditedLLMClient(OllamaClient(), grader="CalibrationDrift")  # no cache layer
    out = {}
    for a in artifacts:
        result = grade(a, client=client)
        out[a["artifact_id"]] = {"score": result["score"], "confidence": result["confidence"]}
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("freeze", "check"))
    parser.add_argument("--threshold", type=float, default=1.0, help="mean |Δscore| alert")
    args = parser.parse_args()

    artifacts = _subset_artifacts()
    if args.command == "freeze":
        snapshot = _grade_uncached(artifacts)
        REFERENCE.write_text(json.dumps(snapshot, indent=2))
        print(f"froze {len(snapshot)} reference grades -> {REFERENCE}")
        return 0

    reference = json.loads(REFERENCE.read_text())
    current = _grade_uncached(artifacts)
    deltas = [abs(current[k]["score"] - reference[k]["score"])
              for k in reference if k in current]
    conf_deltas = [abs(current[k]["confidence"] - reference[k]["confidence"])
                   for k in reference if k in current]
    mean_delta = sum(deltas) / max(len(deltas), 1)
    print(f"drift over {len(deltas)} items: mean |Δscore|={mean_delta:.2f} "
          f"max={max(deltas, default=0):.2f} mean |Δconf|={sum(conf_deltas)/max(len(conf_deltas),1):.3f}")
    if mean_delta > args.threshold:
        print(f"ALERT: drift {mean_delta:.2f} exceeds threshold {args.threshold}")
        return 1
    print("no significant drift")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
