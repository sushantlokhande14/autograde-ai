# Phase 0 — Foundation & Local Setup

**Status:** complete — all DoD items verified (2026-06-30).
**Branch:** `main` (Phase 0 is foundational; feature branches start Phase 1).
**Owner decisions in effect:** repo name `autograde-ai`; build target **native
Windows** with Docker Desktop backing the Linux containers; Python packages
`autograde_core` / `autograde_db` / `autograde_llm`; env prefix `AUTOGRADE_`;
license MIT; Ruff + mypy strict; no AI attribution on commits (hook-enforced).

---

## Why this phase exists

You cannot build anything until you can run something. Phase 0 stands up the
local environment, the repo conventions, and an empty-but-wired pipeline so that
every later phase drops into a working skeleton instead of fighting tooling.
Getting the commit hook and line-ending policy right now prevents painful
cleanup downstream.

## What "done" looks like (Definition of Done)

1. `docker compose up -d` brings the full infra stack up cleanly.
2. `GET /healthz` returns `200` for every application service.
3. An empty-pipeline event round-trip works: publish to Kafka → a no-op worker
   consumes → logs it. Replaying the event does not double-process.
4. `uv sync` and `pnpm install` both succeed from a clean checkout.
5. The commit-msg hook strips AI attribution (verified with a probe commit).

**All five DoD items are verified** (bring-up run on native Windows / Docker
Desktop, engine 27.3.1):

1. `docker compose up -d` — 13/13 containers up; Postgres, Redis, Redpanda,
   MinIO, Qdrant, Temporal, Prometheus, Grafana report healthy.
2. `/healthz` — 19/19 backend services + the web dashboard all return `200`.
3. Kafka round-trip — event produced, consumed by one group, replayed by a
   fresh group, and deduped on `event_id` (multi-consumer replay + idempotency).
4. `uv sync` (exit 0) and `pnpm install` (exit 0, native builds approved) both
   succeed; `uv run pytest` reports 9 passed / 6 skipped, and 6/6 with the
   integration stack running.
5. The commit-msg hook strips every attribution form while keeping real content;
   no commit in the history carries attribution.

## Checkpoint commits

| # | Commit | Contents | State |
|---|---|---|---|
| C0.1 | `chore: initialize repo ...` | git init, MIT license, .gitignore, commit-msg hook | done |
| C0.2 | `chore: enforce LF line endings ...` | `.gitattributes` | done |
| C0.3 | `docs: add plan, architecture, phase-0 plan` | design docs | done |
| C0.4 | `infra: add docker-compose stack and service configs` | compose files, `.env.example`, `infra/` | done |
| C0.5 | `feat: add proto contracts and python workspace with health stubs` | `proto/`, `pyproject.toml`, `libs/`, 19 service `/healthz` stubs | done |
| C0.6 | `feat: scaffold next.js dashboard and pnpm workspace` | `web/`, `package.json`, `pnpm-workspace.yaml` | done |
| C0.7 | `chore: add scripts and test scaffolding` | `scripts/`, `tests/` | done |
| C0.8 | (verification) bring stack up, prove healthz + Kafka round-trip | — | done — all DoD items pass |

## Infrastructure stack (docker-compose)

Runs as containers; application code runs locally via `uv` / `pnpm` in dev.

| Service | Image | Ports | Notes |
|---|---|---|---|
| Postgres | `postgres:16` | 5432 | `grading` + `identity` schemas via `infra/postgres/init.sql` |
| Redis | `redis:7` | 6379 | cache / locks / rate limits |
| Redpanda | `redpandadata/redpanda` | 9092, 9644 | Kafka API in dev |
| Redpanda Console | `redpandadata/console` | 8080 | topic browser |
| MinIO | `minio/minio` | 9000, 9001 | S3 object store |
| Qdrant | `qdrant/qdrant` | 6333, 6334 | vector store |
| Temporal | `temporalio/auto-setup` | 7233 | workflow engine |
| Temporal UI | `temporalio/ui` | 8233 | workflow browser |
| OTel Collector | `otel/opentelemetry-collector-contrib` | 4317, 4318 | OTLP ingest → Prometheus/Loki/Tempo |
| Prometheus | `prom/prometheus` | 9090 | metrics scrape |
| Grafana | `grafana/grafana` | 3001 | dashboards (datasources auto-provisioned) |
| Loki | `grafana/loki` | 3100 | logs |
| Tempo | `grafana/tempo` | 3200 | traces |

Kafka topics are created by `infra/kafka/topics.sh` (run against Redpanda after
it is healthy). Topic list matches design spec §7.2.

## Application services (modules under the root package)

The three shared libs are the `uv` workspace members; the services live under
the root `autograde-ai` package as the `services.*` namespace, so they share one
resolved environment. Each service is a minimal FastAPI app exposing
`GET /healthz` in Phase 0. gRPC servers replace/augment these starting Phase 1.
Run one with `uv run uvicorn services.<path>.main:app --port <port>`. `/healthz`
ports:

| Service | Path | Port |
|---|---|---|
| api (gateway) | `services/api` | 8000 |
| router | `services/router` | 8010 |
| parser: pdf | `services/parsers/pdf` | 8021 |
| parser: notebook | `services/parsers/notebook` | 8022 |
| parser: code | `services/parsers/code` | 8023 |
| parser: image | `services/parsers/image` | 8024 |
| parser: fallback | `services/parsers/fallback` | 8025 |
| question_mapper | `services/question_mapper` | 8030 |
| grader: theory | `services/graders/theory` | 8041 |
| grader: code_execution | `services/graders/code_execution` | 8042 |
| grader: code_style | `services/graders/code_style` | 8043 |
| grader: derivation | `services/graders/derivation` | 8044 |
| grader: figure | `services/graders/figure` | 8045 |
| grader: plagiarism | `services/graders/plagiarism` | 8046 |
| feedback_synth | `services/graders/feedback_synth` | 8047 |
| cross_check | `services/graders/cross_check` | 8048 |
| retrieval | `services/retrieval` | 8050 |
| orchestrator | `services/orchestrator` | 8060 |
| export | `services/export` | 8070 |

The `/healthz` handler is a single shared factory in `autograde_core.health`;
each service is a thin `main.py` that imports it and sets its service name.

## Shared libraries

- `autograde_core` — settings (pydantic-settings, `AUTOGRADE_`-prefixed), the
  `/healthz` app factory, and a telemetry bootstrap stub.
- `autograde_db` — SQLAlchemy base + placeholder for models/migrations.
- `autograde_llm` — unified local/API LLM client interface (stub in Phase 0).

## proto contracts

`proto/router.proto`, `proto/parser.proto`, `proto/grader.proto` define the
service interfaces referenced in the architecture. Phase 0 locks the message
shapes; codegen and real servers arrive in Phase 1. Generated `*_pb2*` files are
gitignored.

## Out of scope for Phase 0

- Any real parsing, retrieval, grading, or LLM calls.
- gRPC servers (interfaces only).
- Sandbox execution (Phase 3).
- Auth (deferred; local dev bypass).

## How to verify once approved

```bash
cd "autograde-ai"
cp .env.example .env            # fill local secrets
docker compose up -d
bash infra/kafka/topics.sh      # create topics
uv sync
uv run python scripts/healthcheck_all.py   # curls every /healthz
uv run python scripts/replay_kafka.py --smoke   # publish + consume round-trip
```
