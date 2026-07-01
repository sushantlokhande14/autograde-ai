# Autograde AI — Evaluation

> **Status: placeholder.** This document is written for real in Phase 6
> (Evaluation & Hardening). It is stubbed here so the methodology is designed
> before the features are built, per the plan's "design the evals first" rule.

## Gold eval set

- 100 synthetic student submissions across two assignments (one algorithms-heavy,
  one theory-heavy).
- Mix of correct, partially correct, wrong, and creatively-wrong answers.
- Hand-graded twice, one week apart, with the same rubric.
- Inter-rater agreement between the two passes is reported as the human ceiling.
- Stored in `tests/eval/gold_set/`. Never committed if it contains real work.

## Metrics (targets)

| Metric | Definition | Target |
|---|---|---|
| Agreement (theory) | Score within ±1 point of gold on 10-point questions | > 90% |
| Agreement (code) | Score within ±5% of gold on execution grading | > 95% |
| Calibration (Brier) | Brier score of confidence vs. correctness | < 0.15 |
| Time per submission | End-to-end wall clock, median | < 8 min |
| Time per class | Full 250-submission batch | < 30 min |
| Cost per grade (paid) | Anthropic tokens × price | < $0.05 |
| Cost per grade (local) | Amortized compute + electricity | < $0.01 |
| Auto-approve rate | Grades above confidence threshold | 70–80% |
| Overturn rate on auto-approved | % an instructor would have overturned | < 5% |
| Ingestion parse-failure rate | Files landing in fallback bucket | < 3% |

## Baseline

Every metric is reported against a **zero-shot baseline**: one model call per
submission with rubric + answer, no agents, no retrieval, no confidence gate. If
the multi-agent architecture does not beat the baseline on agreement,
calibration, or cost, that is reported honestly as a finding.

_Numbers land here in Phase 6._
