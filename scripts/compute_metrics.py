"""Evaluation metrics over the gold set.

Computes everything computable from the DB now (auto-approve split, gate
stats, parse failures, cost per grade with the flagship estimate) and — once
hand-grade passes exist (import_hand_grades.py) — agreement per grader,
Brier calibration, the human ceiling, overturn rate, and the zero-shot
baseline comparison. Tolerances per design spec §12.2: ±1 point for
prose questions, ±5% of max for code.

Usage:
    uv run python scripts/compute_metrics.py --out data/gold_metrics.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from uuid import UUID

sys.path.insert(0, str(Path(__file__).parent.parent / "tests" / "eval"))
from metrics import agreement_within, brier_score  # noqa: E402

ASSIGNMENTS = ["gold-theory", "gold-algo"]
GOLD_DIR = Path("tests/eval/gold_set")
# labeled ESTIMATE: published flagship pricing per million tokens
FLAGSHIP_IN, FLAGSHIP_OUT, CACHE_DISCOUNT = 3.00, 15.00, 0.10

PROSE_TOL = 1.0          # ±1 point
CODE_TOL_FRAC = 0.05     # ±5% of max


def _db_rows():
    from sqlalchemy import select

    from autograde_core.hashing import assignment_id_for
    from autograde_db.models import Artifact, Grade, LlmCall, Review, Submission
    from autograde_db.session import session_scope

    auuids = [assignment_id_for(a) for a in ASSIGNMENTS]
    with session_scope() as s:
        sub_rows = s.execute(select(Submission.id, Submission.assignment_id).where(
            Submission.assignment_id.in_(auuids))).all()
        sub_ids = [r[0] for r in sub_rows]
        grades = [
            {"submission_id": str(g.submission_id), "question_id": g.question_id,
             "grader": g.grader, "score": g.score, "max_score": g.max_score,
             "confidence": g.confidence}
            for g in s.scalars(select(Grade).where(Grade.submission_id.in_(sub_ids)))]
        artifacts = {
            str(a.id): {"submission_id": str(a.submission_id), "question_id": a.question_id,
                        "type": a.artifact_type, "confidence": a.question_mapping_confidence}
            for a in s.scalars(select(Artifact).where(Artifact.submission_id.in_(sub_ids)))}
        pending = s.execute(select(Review).where(
            Review.submission_id.in_(sub_ids), Review.status == "pending")).scalars().all()
        pending_keys = {(str(r.submission_id), r.question_id) for r in pending}
        gold_graders = {g["grader"] for g in grades}
        llm = [(c.grader, c.input_tokens, c.output_tokens, c.cache_hit)
               for c in s.scalars(select(LlmCall)) if c.grader in gold_graders]
    return grades, artifacts, pending_keys, llm


def _hand(passes: list[int], artifacts: dict) -> dict[int, dict]:
    """pass -> {(submission_id, question_id): score}"""
    out = {}
    for n in passes:
        path = GOLD_DIR / f"hand_grades_pass{n}.json"
        if not path.exists():
            continue
        raw = json.loads(path.read_text())
        mapped = {}
        for artifact_id, entry in raw.items():
            a = artifacts.get(artifact_id)
            if a:
                mapped[(a["submission_id"], a["question_id"])] = float(entry["score"])
        out[n] = mapped
    return out


def _tol(question_id: str, max_score: float, is_code: bool) -> float:
    return max_score * CODE_TOL_FRAC if is_code else PROSE_TOL


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="data/gold_metrics.json")
    args = parser.parse_args()

    grades, artifacts, pending_keys, llm = _db_rows()
    code_questions = {(a["submission_id"], a["question_id"])
                      for a in artifacts.values() if a["type"] == "code"}

    finals = {(g["submission_id"], g["question_id"]): g
              for g in grades if g["grader"] == "FinalAggregate"}
    report: dict = {"gold_questions_graded": len(finals)}

    # always-computable
    gated = sum(1 for a in artifacts.values()
                if a["confidence"] is not None and a["confidence"] < 0.6)
    unknown = sum(1 for a in artifacts.values() if a["type"] == "unknown")
    report["mapping_gate"] = {"artifacts": len(artifacts), "below_gate": gated,
                              "gate_rate": round(gated / max(len(artifacts), 1), 3)}
    report["parse_failure_rate"] = round(unknown / max(len(artifacts), 1), 4)
    in_review = sum(1 for k in finals if k in pending_keys)
    report["review_split"] = {
        "auto_approved": len(finals) - in_review, "in_review": in_review,
        "auto_approve_rate": round((len(finals) - in_review) / max(len(finals), 1), 3)}

    tokens_in = sum(t[1] for t in llm)
    tokens_out = sum(t[2] for t in llm)
    hits = sum(1 for t in llm if t[3])
    n_grades = max(len(finals), 1)
    est = (tokens_in * FLAGSHIP_IN + tokens_out * FLAGSHIP_OUT) / 1e6
    est_cached = (tokens_in * FLAGSHIP_IN * CACHE_DISCOUNT + tokens_out * FLAGSHIP_OUT) / 1e6
    report["cost_per_grade"] = {
        "llm_calls": len(llm), "cache_hit_rate": round(hits / max(len(llm), 1), 3),
        "tokens_in": tokens_in, "tokens_out": tokens_out,
        "local_usd": 0.0,
        "flagship_estimate_usd": round(est / n_grades, 4),
        "flagship_estimate_cached_prefix_usd": round(est_cached / n_grades, 4),
        "note": "estimate = measured local token volumes x published flagship pricing"}

    # hand-grade-dependent
    hand = _hand([1, 2], artifacts)
    for n, mapped in hand.items():
        for grader in ("FinalAggregate", "ZeroShotBaseline"):
            rows = [g for g in grades if g["grader"] == grader]
            pairs = [(g, mapped[(g["submission_id"], g["question_id"])])
                     for g in rows if (g["submission_id"], g["question_id"]) in mapped]
            if not pairs:
                continue
            prose = [(g["score"], h) for g, h in pairs
                     if (g["submission_id"], g["question_id"]) not in code_questions]
            code = [(g["score"], h, g["max_score"]) for g, h in pairs
                    if (g["submission_id"], g["question_id"]) in code_questions]
            agree_prose = agreement_within([p[0] for p in prose], [p[1] for p in prose], PROSE_TOL)
            agree_code = (sum(1 for s_, h, m in code if abs(s_ - h) <= m * CODE_TOL_FRAC)
                          / len(code)) if code else 0.0
            correct = ([abs(s_ - h) <= PROSE_TOL for s_, h in prose]
                       + [abs(s_ - h) <= m * CODE_TOL_FRAC for s_, h, m in code])
            confs = ([g["confidence"] for g, _ in pairs])
            report[f"pass{n}_{grader}"] = {
                "n": len(pairs),
                "agreement_prose": round(agree_prose, 3),
                "agreement_code": round(agree_code, 3),
                "brier": round(brier_score(confs, correct), 4)}
        # overturn rate: auto-approved finals the human disagrees with
        overturn = misses = 0
        for key, g in finals.items():
            if key in mapped and key not in pending_keys:
                tol = _tol(key[1], g["max_score"], key in code_questions)
                misses += 1
                if abs(g["score"] - mapped[key]) > tol:
                    overturn += 1
        if misses:
            report[f"pass{n}_overturn_rate_on_auto_approved"] = round(overturn / misses, 3)

    if 1 in hand and 2 in hand:
        common = sorted(set(hand[1]) & set(hand[2]))
        prose = [k for k in common if k not in code_questions]
        code = [k for k in common if k in code_questions]
        ceiling_prose = agreement_within([hand[1][k] for k in prose],
                                         [hand[2][k] for k in prose], PROSE_TOL)
        code_max = {k: finals[k]["max_score"] for k in code if k in finals}
        ceiling_code = (sum(1 for k in code if abs(hand[1][k] - hand[2][k])
                            <= code_max.get(k, 0) * CODE_TOL_FRAC) / len(code)) if code else 0.0
        report["human_ceiling"] = {"n": len(common),
                                   "agreement_prose": round(ceiling_prose, 3),
                                   "agreement_code": round(ceiling_code, 3)}
    else:
        report["human_ceiling"] = "pending hand-grade passes"

    Path(args.out).parent.mkdir(exist_ok=True)
    Path(args.out).write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
