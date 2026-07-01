# Autograde AI

**A local-first, agent-orchestrated grading pipeline for CS coursework.**

Autograde AI ingests a disorganized zip of student submissions and a structured
rubric, normalizes seven file formats into a canonical artifact stream, and
dispatches a pool of specialized grading agents in parallel. Grades come back
scored, reasoned, and confidence-annotated; a confidence gate surfaces the least
certain grades to a human review queue with a full three-click audit trail from
grade → agent → prompt → retrieval → sandbox run.

> This is a portfolio system built to a production-grade bar. It is **not**
> deployed against live student data. It is evaluated on synthetic and
> self-generated coursework only. See [`PROJECT_PLAN.md`](PROJECT_PLAN.md) for
> the full design, which is the single source of truth for the project.

## Status

Phase 0 — Foundation & Local Setup (in progress). See
[`docs/phases/phase-0-foundation.md`](docs/phases/phase-0-foundation.md).

## Architecture at a glance

- **Frontend:** Next.js 15 + Tailwind + shadcn/ui dashboard
- **API gateway:** GraphQL (Apollo) fronting FastAPI
- **Inter-service:** gRPC + Protobuf
- **Event bus:** Kafka (Redpanda in dev) — multi-consumer replay
- **Workflow engine:** Temporal — `GradeStudentWorkflow` per student
- **Storage:** Postgres 16 (RLS-gated identity/grading split), MinIO, Redis, Qdrant
- **Runtime:** vLLM / Ollama local models, Anthropic API toggle, gVisor sandbox pool
- **Observability:** OpenTelemetry → Prometheus + Loki + Tempo → Grafana

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for diagrams.

## Local development

Requires Docker Desktop, Python 3.11+ with [`uv`](https://docs.astral.sh/uv/),
Node 20+ with [`pnpm`](https://pnpm.io/), and Git 2.40+.

```bash
git clone <repo> autograde-ai && cd autograde-ai
cp .env.example .env          # then edit .env with local secrets
docker compose up -d          # Postgres, Redis, Redpanda, MinIO, Qdrant, Temporal, observability
uv sync                       # Python workspace
pnpm install                  # Node workspace
# in separate terminals:
uv run --package api uvicorn services.api.main:app --reload
pnpm --filter web dev
```

Every service exposes `GET /healthz`. Once the stack is up, all health checks
should return `200`.

## Repository conventions

- **Local-first.** No data, real or synthetic, leaves the machine.
- **Conventional Commits**, one logical change per commit. Types: `feat`, `fix`,
  `refactor`, `perf`, `chore`, `docs`, `test`, `infra`.
- **No AI attribution on commits, ever.** Enforced by `.githooks/commit-msg`.
  After cloning, run `git config core.hooksPath .githooks` once.
- `main` is always green. Feature work happens on `phase-N-<slug>` branches.

## License

[MIT](LICENSE).
