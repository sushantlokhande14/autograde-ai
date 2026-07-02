# Autograde AI

**A local-first, multi-agent grading platform for CS coursework.**

Autograde AI takes the worst part of teaching at scale — a disorganized zip of
hundreds of student submissions — and turns it into reviewed, auditable
grades. It normalizes seven file formats into a canonical artifact stream,
dispatches a roster of specialized grading agents in parallel, and routes only
the grades the system is least sure about to a human review queue. Every grade
traces back to the exact prompt, retrieval context, and sandbox execution that
produced it — three clicks from number to evidence.

All inference runs on local models by default. Student work never leaves the
machine, and real identities never enter the grading pipeline: the grading
schema sees only HMAC-hashed identifiers, with the identity mapping isolated
behind row-level security.

## How it works

```
zip + rubric ──▶ Router ──▶ Parser pool ──▶ QuestionMapper ──▶ Temporal workflows
                (per-student   (PDF, notebook,   (LLM-assisted,      │
                 grouping,      code, image,      confidence-gated)  ▼
                 identity       fallback)                    Grading agents (parallel)
                 hashing)                                    theory · code execution · style
                                                             derivation · figure · plagiarism
                                                                     │
                                              CrossChecker ◀─────────┘
                                              aggregation → feedback synthesis
                                                     │
                            auto-approve ◀── confidence gate ──▶ human review queue
```

- **Ingestion** — deterministic routing groups a messy upload by student,
  hashes identities, and normalizes PDFs, notebooks, source files, images
  (with OCR), and documents into typed artifacts. Replay-safe end to end:
  deterministic ids and upserts make re-ingestion a no-op.
- **Question mapping** — a local LLM classifies each artifact against the
  rubric with deterministic filename and type signals; mappings below the
  confidence gate stop and ask the instructor instead of guessing.
- **Grounded grading** — TheoryGrader and DerivationGrader score against
  rubric criteria with retrieval-augmented context from the course materials
  (Qdrant + MiniLM embeddings). Reference answers are indexed but excluded
  from grader-facing retrieval, so the gold answer can never leak into a
  prompt.
- **Sandboxed execution** — student code runs under **gVisor** with no
  network, capped memory/CPU/pids, a read-only filesystem, and an external
  wall-clock kill. Test-case scores are fully deterministic; the LLM explains
  results but can never move a number. Hostile submissions (infinite loops,
  network attempts, fork bombs) are contained, scored zero, and recorded.
- **Defense in depth against prompt injection** — student content is
  delimited as untrusted data, outputs are schema-validated, and scores are
  clamped server-side to rubric maxima.
- **Meta-agents** — a CrossChecker flags inconsistencies (aced the hard
  question, flunked the easy one; execution/style disagreement; plagiarism
  signals) and lowers confidence accordingly; a FeedbackSynthesizer composes
  student-facing narrative feedback from the per-criterion results.
- **Plagiarism detection** — MOSS-style winnowed n-gram fingerprints plus
  embedding similarity across the cohort, reported per submission with
  hash-anonymized matches.
- **Human-in-the-loop** — per-question confidence drives an auto-approve /
  review split; flagged and low-confidence grades land in a pending review
  queue with approve/edit/regrade semantics.

## Benchmarks

Measured on the reference test corpus (messy multi-format class upload,
4-question rubric spanning theory, code, derivation, and plotting):

| Metric | Result |
|---|---|
| Artifact-type classification | **100%** across 80 files (target ≥95%) |
| Parse failures (fallback bucket) | **0%** (target <3%) |
| Question-mapping accuracy | **100%** on auto-mapped artifacts |
| RAG retrieval, top-3 hit rate | **100%** against corpus ground truth |
| Retrieval latency | cold p95 **32ms**, cached p95 **<1ms** |
| Sandbox containment | infinite-loop kill, network block, crash isolation — all verified |
| End-to-end audit chain | grade → LLM call → payloads → citations → sandbox logs, verified live |

Grading throughput scales with the model server; per-grader latency P50/P99,
cache-hit rate, and workflow throughput ship on a provisioned Grafana
dashboard.

## Architecture

| Layer | Technology |
|---|---|
| Orchestration | **Temporal** — one durable workflow per submission, per-agent retries/timeouts, parallel fan-out with failure isolation |
| Event bus | **Kafka** (Redpanda in dev) — multi-consumer replay; re-grade a batch through a new agent version without re-ingesting |
| Inter-service | **gRPC + Protobuf** contracts |
| Storage | **Postgres 16** (grading + identity schemas, RLS), **MinIO** (immutable artifacts, payloads, logs), **Redis** (prompt/retrieval caches, rate limits, sandbox locks), **Qdrant** (course materials, rubric context, plagiarism corpus) |
| Inference | **Ollama**-served local models with per-agent model selection; optional hosted-API toggle with prompt caching |
| Sandboxing | **Docker + gVisor (runsc)**; Firecracker as the hardened deployment target |
| Observability | **OpenTelemetry → Prometheus + Loki + Tempo → Grafana**; every LLM call is an audited span with tokens, latency, and cache status |
| Frontend | **Next.js 15** dashboard: rubric authoring, live progress, review queue, grade audit |

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for component, sequence,
and state diagrams, and [`docs/EVALUATION.md`](docs/EVALUATION.md) for the
evaluation methodology.

## Getting started

Requires Docker, Python 3.11+ with [`uv`](https://docs.astral.sh/uv/), Node
20+ with [`pnpm`](https://pnpm.io/), [Ollama](https://ollama.com), and
Tesseract OCR.

```bash
git clone <repo> autograde-ai && cd autograde-ai
cp .env.example .env                    # set local secrets
docker compose up -d                    # Postgres, Redis, Redpanda, MinIO, Qdrant, Temporal, observability
bash infra/kafka/topics.sh              # create the event topics
ollama pull qwen2.5:3b                  # default local model
uv sync && pnpm install
uv run python scripts/gen_proto.py      # generate gRPC stubs

# run the pipeline
uv run python -m services.orchestrator.worker    # Temporal worker
uv run python -m services.orchestrator.starter   # Kafka → workflow starter
uv run python scripts/ingest.py <submissions.zip> --manifest <roster.json> --rubric <rubric.json>
```

Dashboards: Temporal UI `:8233`, Grafana `:3001`, Redpanda console `:8080`,
MinIO console `:9001`. The web dashboard (`pnpm --filter web dev`) serves the
review queue at `:3000`.

## Development

- `uv run pytest tests/unit` — fast suite, no services required.
- `AUTOGRADE_RUN_INTEGRATION=1 uv run pytest tests/integration` — end-to-end
  suites against the live stack (ingestion, retrieval, grading, full roster).
- `uv run python scripts/load_test.py --students 250` — class-scale benchmark
  with per-grader latency reporting.
- Conventional Commits; `main` stays green; feature branches per phase.

## License

[MIT](LICENSE).
