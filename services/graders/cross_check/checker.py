"""CrossChecker: deterministic inconsistency flags across one student's grades.

Flags (Phase 4, no LLM):
  hard_easy_inversion — near-perfect on the heaviest question but near-zero on
                        the lightest (weight-aware);
  exec_style_gap      — execution and style disagree by more than 0.6 fraction;
  plagiarism          — detector similarity above its flag threshold.

Each flag subtracts CONFIDENCE_PENALTY from the submission's overall
confidence during aggregation. Persisted as an 'overall' grade row so the
audit trail shows what fired and why.
"""

from __future__ import annotations

CONFIDENCE_PENALTY = 0.15
FLAG_PLAGIARISM_AT = 0.5


def flags_for(grades: list[dict]) -> list[dict]:
    """grades: [{grader, question_id, score, max_score, ...}] for one submission."""
    flags: list[dict] = []
    finals = {
        g["question_id"]: g for g in grades
        if g["grader"] in ("TheoryGrader", "CodeExecutionGrader", "DerivationGrader", "FigureGrader")
    }
    if len(finals) >= 2:
        weighted = sorted(finals.values(), key=lambda g: g["max_score"])
        light, heavy = weighted[0], weighted[-1]
        if heavy["max_score"] > light["max_score"]:
            heavy_frac = heavy["score"] / heavy["max_score"] if heavy["max_score"] else 0
            light_frac = light["score"] / light["max_score"] if light["max_score"] else 0
            if heavy_frac >= 0.9 and light_frac <= 0.1:
                flags.append({
                    "flag": "hard_easy_inversion",
                    "detail": f"{heavy['question_id']} at {heavy_frac:.0%} but "
                              f"{light['question_id']} at {light_frac:.0%}",
                })

    execution = next((g for g in grades if g["grader"] == "CodeExecutionGrader"), None)
    style = next((g for g in grades if g["grader"] == "CodeStyleGrader"), None)
    if execution and style and execution["max_score"] and style["max_score"]:
        gap = abs(execution["score"] / execution["max_score"] - style["score"] / style["max_score"])
        if gap > 0.6:
            flags.append({
                "flag": "exec_style_gap",
                "detail": f"execution {execution['score']}/{execution['max_score']} vs "
                          f"style {style['score']}/{style['max_score']} (gap {gap:.0%})",
            })

    plag = next((g for g in grades if g["grader"] == "PlagiarismDetector"), None)
    if plag and plag["score"] >= FLAG_PLAGIARISM_AT:
        flags.append({
            "flag": "plagiarism",
            "detail": f"top similarity {plag['score']:.2f} — see detector reasoning",
        })
    return flags
