# Phase 5 — Dashboard & GraphQL

**Status:** plan for review (no code yet).
**Branch:** `phase-5-dashboard`.
**Prerequisite:** Phase 4 complete (`phase-4-complete` tag); graded class data
in the stack makes every view demonstrable with real rows.
**Open decisions:** three, listed at the end.

---

## Why this phase exists

Without the dashboard, the system is a batch job an engineer drives from a
terminal. With it, it's a product an instructor drives alone. Phase 5 locks
the GraphQL schema, builds the five views, and closes the loop the data model
has been waiting for: the pending review rows Phase 4 writes become a queue a
human works through, and every grade becomes three clicks from its evidence.

## What "done" looks like (Definition of Done, per design spec §9)

1. **GraphQL schema locked** — queries, mutations, and subscriptions typed
   end to end; the REST review stubs from Phase 1 are retired.
2. **Five views live** with real data:
   - *Assignment overview* — per-assignment progress (submissions, graded,
     awaiting review, auto-approved) updating live via subscription;
   - *Rubric authoring* — edit rubric JSON with validator errors surfaced
     inline, plus **preview-grade-on-sample** (runs TheoryGrader against a
     pasted sample answer, shows score/reasoning before any batch runs);
   - *Review queue* — pending reviews sorted by confidence ascending, with
     approve / edit-score / regrade actions;
   - *Grade audit* — grade → per-criterion breakdown → reasoning → LLM prompt
     and response payloads → retrieval citations → sandbox logs, three clicks
     deep;
   - *System health* — embedded Grafana grader dashboard + stack status.
3. **Approve / edit / regrade persist and act:** approve/edit update the
   review row and final grade; regrade re-runs the graders for that
   submission through Temporal and refreshes the queue when done.
4. **An instructor can drive the whole system without touching the terminal:**
   upload zip + rubric → watch progress → work the queue → audit any grade.
5. Uploads accepted through the dashboard (zip + rubric + roster), feeding the
   existing ingestion pipeline.
6. Component/unit tests for schema resolvers and review actions; an opt-in
   integration test drives upload → grade → review → audit through the API.

## Architecture

```mermaid
graph LR
    UI["Next.js 15 dashboard<br/>Apollo Client"] -->|queries/mutations| GQL["GraphQL on FastAPI<br/>(api service :8000)"]
    UI -.->|subscriptions (WebSocket)| GQL
    GQL --> PG[(Postgres)]
    GQL --> MINIO[(MinIO payloads/logs)]
    GQL -->|start ingestion| K[Kafka]
    GQL -->|regrade workflows| T[Temporal]
    UI -->|iframe embed| GRAF[Grafana]
```

- The **api service** grows the GraphQL endpoint (`/graphql`) plus a multipart
  upload route; resolvers reuse the existing repository/session layer and the
  MinIO helpers. Live progress is a subscription that watches grading state
  (DB-backed at dev scale; the Kafka-push upgrade is an internal swap).
- **Regrade** starts a fresh `GradeStudentWorkflow` run for the submission
  (`regrade-<submission>-<n>`); completed workflows stay immutable history.
- **Auth:** local dev bypass per the design spec's open decision #11 — a
  single-instructor deployment posture; Auth0 is the documented multi-tenant
  upgrade.

## Checkpoint commits

| # | Commit | Contents |
|---|---|---|
| P5.1 | `feat: graphql schema and server` | Strawberry-on-FastAPI schema (assignments, submissions, grades, reviews, artifacts, audit links), review mutations, progress subscription; REST stubs retired |
| P5.2 | `feat: dashboard shell with apollo client` | Apollo Client + WebSocket link, nav layout, view routing |
| P5.3 | `feat: assignment overview with live progress` | subscription-driven counts, per-question breakdown |
| P5.4 | `feat: review queue` | confidence-ascending queue, approve/edit/regrade wired to mutations + Temporal |
| P5.5 | `feat: grade audit trail` | grade → breakdown → prompt/response payloads → citations → sandbox logs |
| P5.6 | `feat: rubric authoring with preview grade` | JSON editor, inline validator errors, preview-grade-on-sample mutation |
| P5.7 | `feat: upload flow and system health view` | zip/rubric/roster upload → ingestion, Grafana embed |
| P5.8 | `test: instructor end-to-end without terminal` | integration test through the API; DoD verification; docs close-out |

## New dependencies (for approval)

| Package | For |
|---|---|
| `strawberry-graphql[fastapi]` | GraphQL schema/server with subscriptions |
| `python-multipart` | dashboard uploads |
| `@apollo/client`, `graphql`, `graphql-ws` (web) | typed client + subscriptions |

## Open decisions for this phase

1. **GraphQL server: Strawberry-on-FastAPI (recommended) vs Apollo Server
   gateway.** The design spec's stack table says "Apollo Server fronting
   FastAPI," which literally means a second Node service proxying every query.
   Strawberry serves the same schema + WebSocket subscriptions natively inside
   the existing FastAPI api service — one service, one deploy, same
   Apollo-Client-compatible contract. Apollo stays in the stack on the client
   side either way.
2. **Review-resume semantics: fresh regrade workflow (recommended) vs
   long-running workflows awaiting signals.** The spec's state machine has
   workflows pausing at AwaitingReview. Keeping workflows open for
   hours-to-days of human review means heartbeats, timeouts, and versioning
   pain; the recommended shape lets grading workflows complete, and regrade
   starts a new run with full audit lineage. Functionally identical for the
   instructor.
3. **Styling: continue hand-rolled Tailwind (recommended) vs adopt shadcn/ui
   now.** The spec names shadcn/ui; the existing views are already clean
   Tailwind. Adopting shadcn mid-project buys component polish at the cost of
   a scaffold-and-migrate detour. Recommend deferring to a polish pass.

## How to verify (once built)

```bash
uv run uvicorn services.api.main:app --port 8000   # GraphQL at /graphql
pnpm --filter web dev                               # dashboard at :3000
# instructor flow: upload class zip + rubric on /, watch overview fill,
# work /review, audit a grade from /audit, check /health
AUTOGRADE_RUN_INTEGRATION=1 uv run pytest tests/integration/test_dashboard_e2e.py -q
```
