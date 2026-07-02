# Phase 4 — Full Grader Roster + Parallelism

**Status:** plan for review (no code yet).
**Branch:** `phase-4-graders`.
**Prerequisite:** Phase 3 complete (`phase-3-complete` tag); stack + Ollama +
WSL gVisor sandbox operational.
**Open decisions:** two, listed at the end.

---

## Why this phase exists

A one-grader pipeline is a demo; six graders in parallel is a system. Phase 4
ships the remaining V1 graders (CodeStyle, Derivation, Figure, Plagiarism),
the two meta-agents (FeedbackSynthesizer, CrossChecker), parallel dispatch in
the workflow, and the latency dashboards — then proves scale with the
250-submission class benchmark. This phase also has to face the honest
arithmetic of CPU inference: the 30-minute class target was written for a
48GB-VRAM box, and every design choice below either removes LLM calls from
the hot path or makes the remaining ones cheaper.

## The throughput problem (design driver)

Naive cost: ~6 LLM calls per submission × 250 submissions × ~4–8s per 3b call
on CPU ≈ 2+ hours. The plan's target is <30 minutes. Knobs used here:

1. **Deterministic-first scoring everywhere.** Execution, style (Ruff), n-gram
   plagiarism, and cross-check flags are all deterministic. The LLM only
   writes prose or judges what static analysis cannot.
2. **Template reasoning on unambiguous outcomes.** All-tests-pass /
   all-tests-fail / timeout code results get templated reasoning — no LLM
   call. Same for empty style findings. Only ambiguous middles pay for prose.
3. **Token caps** (≤250 output tokens for style/derivation/figure calls) and
   the Phase 2 prompt cache (shared rubric prefixes).
4. **Real parallelism:** workflow fans out graders per artifact with
   `asyncio.gather`; `OLLAMA_NUM_PARALLEL` probed in P4.1; sandbox pool stays
   Redis-capped.
5. **P4.1 measures before we promise.** A microbenchmark pins per-call and
   per-submission cost first; the load test reports whatever is true.

## What "done" looks like (Definition of Done)

1. All six V1 graders + FeedbackSynthesizer + CrossChecker produce persisted,
   audit-linked grades/flags on the synthetic class.
2. `GradeStudentWorkflow` dispatches graders **in parallel** per submission;
   grader failures stay isolated (one bad artifact never kills the workflow).
3. Per-question **aggregation** writes the final score (execution/style blend
   per `grading_config`), overall confidence, and `grading.reviews` rows for
   sub-gate questions (the queue Phase 5 renders).
4. `plagiarism_corpus` populated; detector reports pairwise similarity with
   the top match cited by student hash (never name).
5. **Grafana dashboard live:** grader latency P50/P99, LLM cache-hit rate,
   sandbox duration, workflow throughput — from OTel metrics via Prometheus.
6. **Load test run and reported:** 250 submissions × 4 questions on this box,
   wall-clock measured, with the honest number (target <30 min; see decision
   2) written into `docs/EVALUATION.md` as a preliminary figure.
7. Unit tests per grader; opt-in integration test for the parallel workflow
   and a small-batch (10-submission) end-to-end.

## Grader designs (deterministic core, LLM at the edges)

| Grader | Deterministic core | LLM role | Score |
|---|---|---|---|
| **CodeStyleGrader** | Ruff (JSON output: error/warning counts by class); mypy pass measured in P4.1 and included only if <1s/file | judges idiom against `style_criteria`, ≤250 tokens | rubric-configured style points (default 20% of code weight; execution keeps 80%) scaled by findings + LLM judgment |
| **DerivationGrader** | step structure (count, ordering markers); **SymPy where possible** — steps containing parseable equations are checked for symbolic equivalence, feeding confidence | rubric judgment over the full derivation, grounded in Phase 2 retrieval | criterion scoring like theory |
| **FigureGrader** | Phase 1 artifact already carries OCR text + image metadata: axis-label keywords, image dimensions, plot-likeness | interprets OCR text against the question's expectations (see decision 1 on a vision model) | rubric weight scaled by required-element checklist |
| **PlagiarismDetector** | winnowed n-gram Jaccard across the cohort per question + MiniLM embedding cosine (pairs above threshold); populates `plagiarism_corpus` | none (deterministic report) | informational: score = top pairwise similarity, excluded from aggregation |
| **FeedbackSynthesizer** | collects all grade rows | one capped call per submission composing student-facing narrative | stored as grader row `question_id='overall'`, reasoning = narrative |
| **CrossChecker** | flags: hard-Q aced + easy-Q flunked (weight-aware z-heuristic), execution/style disagreement, plagiarism flag present | none in Phase 4 (deterministic flags only; LLM judgment is V2 CalibrationDrift territory) | no score; lowers overall confidence + annotates review rows |

## Workflow changes

- Fan-out: `asyncio.gather` over per-artifact grader activities (theory ‖ code
  exec ‖ style ‖ derivation ‖ figure), then plagiarism (cohort-level, runs
  once per class — a separate `PlagiarismWorkflow` triggered after the batch),
  then cross-check → aggregate → feedback.
- Failure isolation: each activity already has Temporal retry policy; a
  permanently-failing grader records a zero-confidence placeholder grade and
  the workflow continues (fail loud, fail isolated).
- Aggregation activity: per question, final = weighted blend per
  `grading_config` (default: execution 0.8 / style 0.2 for code; single-grader
  questions pass through); overall confidence = min over questions after
  CrossChecker adjustment; sub-gate questions get `grading.reviews` rows
  (status `pending`).

## Observability

- OTel **metrics** join the existing spans: histogram `autograde.grader.duration`
  (labels: grader), counter `autograde.llm.calls` (labels: grader, cache_hit),
  histogram `autograde.sandbox.duration`. Exported via the existing collector
  → Prometheus.
- Provisioned Grafana dashboard JSON (`infra/grafana/dashboards/graders.json`):
  P50/P99 per grader, cache-hit rate, workflow throughput/min, sandbox pool
  saturation.

## New dependencies (for approval)

| Package | For |
|---|---|
| `sympy` | derivation step equivalence checks |
| `ruff` moved to runtime deps | CodeStyleGrader invokes it programmatically |
| (decision 1) a vision model pull | FigureGrader, only if chosen |

## Checkpoint commits

| # | Commit | Contents |
|---|---|---|
| P4.1 | `perf: grading throughput microbenchmark` | per-call/per-submission cost measured; OLLAMA_NUM_PARALLEL probe; template-reasoning fast path in CodeExecutionGrader; token caps |
| P4.2 | `feat: code style grader` | Ruff JSON pass + LLM idiom judgment; unit tests |
| P4.3 | `feat: derivation grader` | structure heuristics + SymPy-where-possible + RAG-grounded LLM scoring; unit tests |
| P4.4 | `feat: figure grader` | OCR/metadata checklist + LLM interpretation; unit tests |
| P4.5 | `feat: plagiarism detector` | winnowed n-grams + embedding cosine, corpus population, cohort workflow; unit tests |
| P4.6 | `feat: aggregation and feedback synthesizer` | final-score blend, review rows, capped narrative call |
| P4.7 | `feat: cross checker flags` | deterministic inconsistency flags lowering confidence |
| P4.8 | `feat: parallel fan-out and grader dashboards` | gather-based dispatch, failure isolation, OTel metrics + provisioned dashboard |
| P4.9 | `test: class-scale load test` | 250×4 benchmark run, measured numbers into EVALUATION.md; docs close-out |

## Open decisions for this phase

1. **FigureGrader vision model.** (a) **OCR + metadata + text-LLM now
   (recommended)** — zero new pulls, fits the CPU budget; a real vision model
   (moondream ~1.7GB or llava:7b ~4.7GB) becomes the V2 upgrade alongside
   diagram understanding. (b) Pull a small vision model now — richer plot
   judgment, adds ~2–6s/figure on CPU and another model in RAM alongside 3b.
2. **Load-test target honesty.** (a) **Measure and report the true wall-clock
   (recommended)** — if CPU inference lands over 30 minutes, EVALUATION.md
   records the measured number plus the projected number on the plan's
   reference hardware (48GB VRAM), which is the honest, interviewable story.
   (b) Hard-require <30 min on this box — achievable only by cutting LLM prose
   from most of the pipeline, which guts the feedback quality the system is
   supposed to demonstrate.

## How to verify (once built)

```bash
uv run python scripts/seed_synthetic_data.py --students 250 --out data/uploads_class
uv run python scripts/ingest.py data/uploads_class/... 
uv run python -m services.orchestrator.worker &
uv run python -m services.orchestrator.starter &
uv run python scripts/load_test.py --submissions 250   # wall-clock + per-grader stats
# Grafana: localhost:3001 -> Autograde AI -> Grader dashboards
AUTOGRADE_RUN_INTEGRATION=1 uv run pytest tests/integration/test_full_roster_e2e.py -q
```
