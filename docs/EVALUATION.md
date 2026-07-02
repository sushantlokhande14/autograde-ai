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

## Preliminary results (Phase 4 class-scale benchmark)

250-submission benchmark class (931 artifacts, 4-question rubric), CPU-only
inference (qwen2.5:3b via Ollama), single dev box, worker concurrency 6:

| Measure | Result |
|---|---|
| Ingestion (route + parse + map) | 7.8 min |
| Grading (full roster, parallel) | **9.2 min** (target <30) |
| Per-submission grading | 2.2 s median |
| Sandbox runs | 323, p50 1.05s / p99 2.05s under gVisor |
| Grade rows written | 2,841 |
| Feedback narratives | 250 (p50 9.7s per uncached call) |
| Uncached LLM latency | theory p50 17.3s · code-interpret 7.6s · style 7.3s · derivation 5.6s · figure 4.4s |

**Honest read of the 9.2-minute number.** The benchmark corpus intentionally
reuses a small set of answer variants, so the Redis prompt cache absorbed the
large majority of grading calls (269 theory grades from ~14 uncached
completions). Real classes have unique answers: projecting 0% prompt-cache
hits at the measured uncached latencies gives **~90–120 minutes** for 250
submissions on this CPU-only box, or **inside the 30-minute target** on the
design spec's reference hardware (GPU-served models at ≥10× token
throughput). Both numbers are reported; neither is hidden behind the other.
The template-reasoning fast path (no LLM call on unambiguous test outcomes)
and deterministic-first grader cores are what keep the unique-answer
projection within an overnight-batch envelope even on CPU.

_Final metrics (agreement, Brier calibration, overturn rate) land in Phase 6
against the hand-graded gold set._
