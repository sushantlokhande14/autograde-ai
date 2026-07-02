# Phase 6 — Evaluation & Hardening

**Status:** plan for review (no code yet).
**Branch:** `phase-6-evaluation`.
**Prerequisite:** Phase 5 complete (`phase-5-complete` tag).
**Structural difference from every prior phase:** the headline metrics require
**hand-graded ground truth** — two human grading passes over the gold set.
Everything else is automatable; the phase closes only when the human grades
exist.

---

## Why this phase exists

Every number the system claims — agreement rate, calibration, auto-approve
split, cost per grade — is only as good as its ground truth. Phase 6 builds a
gold eval set with a real difficulty spread (fixing the Phase 1 caveat that
nothing ever fell below the confidence gate), collects double-pass human
grades, and reports the system against them **and against a zero-shot
baseline** — if six agents don't beat one prompt, that's a finding, not a
secret.

## What "done" looks like (Definition of Done, per design spec §9/§12)

1. **Gold set:** 100 submissions across two assignments (one theory-heavy,
   one algorithms-heavy) with a controlled spread — correct, partial, wrong,
   creatively-wrong, ambiguous-mapping, and prompt-injection attempts.
2. **Two blinded hand-grading passes** captured (machine scores hidden);
   inter-rater agreement between passes reported as the human ceiling.
3. **Metrics computed and written into EVALUATION.md:** agreement per grader
   (±1pt theory / ±5% code), Brier calibration, auto-approve vs review split,
   estimated overturn rate on auto-approved, cost per grade (tokens ×
   pricing; electricity-amortized local figure), ingestion parse-failure rate
   — each against its target and against the human ceiling.
4. **Zero-shot baseline:** one call per submission (same model, rubric +
   answers, no retrieval, no agents, no gate) scored on the same gold set;
   the delta reported honestly either way.
5. **CalibrationDrift agent:** re-grades a fixed gold subset on demand or
   schedule, compares to the frozen reference run, and alerts past a drift
   threshold.
6. **Concurrent-assignments load test:** two assignments grading
   simultaneously without cross-talk (grades, reviews, retrieval scoped
   correctly).
7. All prior suites stay green; the final EVALUATION.md is defensible line by
   line.

## The human-in-the-loop protocol

1. I generate the gold set and machine-grade it (P6.1).
2. You grade **pass 1** from a blinded workbook (per-criterion scores; no
   machine numbers visible) — ~100 submissions × 4 questions; expect several
   hours.
3. After the chosen gap (decision 1), you grade **pass 2** from a freshly
   shuffled blinded workbook.
4. I import both passes, compute the ceiling, and finalize every metric.

## Checkpoint commits

| # | Commit | Contents |
|---|---|---|
| P6.1 | `feat: gold eval set generator` | two-assignment generator with graded difficulty tiers, ambiguous filenames/content (exercises the mapping gate), injection samples; ingest + machine-grade both assignments |
| P6.2 | `feat: blinded hand-grading workbook` | xlsx export (shuffled, machine scores withheld) + import/validation tool |
| P6.3 | `feat: zero-shot baseline runner` | one-prompt-per-submission grader, same model/gold set, persisted separately |
| P6.4 | `feat: evaluation metrics pipeline` | agreement/Brier/split/overturn/cost from DB + hand grades; human ceiling; extends tests/eval/metrics.py |
| P6.5 | `feat: calibration drift agent and concurrent load test` | drift re-grade vs frozen reference + alert; two-assignment concurrency test |
| P6.6 | `docs: final evaluation write-up` | EVALUATION.md with all numbers, methodology, and honest caveats (blocked on your grading passes) |

## Open decisions for this phase

1. **Gap between your two grading passes.** The spec says one week (best
   inter-rater hygiene). Options: **(a) one week** — phase stays open,
   everything else finishes meanwhile; **(b) 1–2 days (recommended)** —
   documented deviation, phase closes this week; **(c) single pass** — no
   human ceiling, weakest claim.
2. **Paid-tier cost metric.** The $/grade (paid) target needs real Anthropic
   API calls on a gold subset. **(a) Local-only now (recommended)** — report
   local cost; paid-tier measured if/when you add a key; **(b) you provide
   ANTHROPIC_API_KEY** and I measure a 20-submission paid sample (~$1–3).

## How to verify (once built)

```bash
uv run python scripts/generate_eval_set.py --out tests/eval/gold_set
uv run python scripts/ingest.py ... (both gold assignments)
uv run python scripts/export_grading_workbook.py --pass 1
# (human grades pass 1, then pass 2)
uv run python scripts/import_hand_grades.py pass1.xlsx pass2.xlsx
uv run python scripts/run_baseline.py && uv run python scripts/compute_metrics.py
AUTOGRADE_RUN_INTEGRATION=1 uv run pytest tests/integration/test_concurrent_assignments.py -q
```
