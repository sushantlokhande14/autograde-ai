# Autograde AI — Architecture

This is a condensed architecture reference. The authoritative and complete
design lives in [`../PROJECT_PLAN.md`](../PROJECT_PLAN.md); this document exists
so the diagrams are one click away during development.

## Component view

```mermaid
graph TB
    subgraph Frontend["Frontend"]
        UI["Next.js Dashboard"]
    end
    subgraph API["API Layer"]
        GQL["GraphQL API (Apollo on FastAPI)"]
        WS["GraphQL Subscriptions (WebSocket)"]
    end
    subgraph Orch["Orchestration"]
        TEMPORAL["Temporal Workflows"]
        KAFKA["Kafka Event Bus (Redpanda in dev)"]
    end
    subgraph Ingest["Ingestion & Parsing (gRPC)"]
        ROUTER["Router"]
        QMAP["QuestionMapper"]
        PARSERS["PDF / Notebook / Code / Image / Fallback parsers"]
    end
    subgraph Grade["Grading Agents (gRPC)"]
        GRADERS["Theory / CodeExecution / CodeStyle / Derivation / Figure / Plagiarism"]
        META["FeedbackSynthesizer / CrossChecker"]
    end
    subgraph Storage["Storage & Data"]
        PG[("Postgres 16 — grading + identity, RLS")]
        MINIO[("MinIO — raw + artifacts + logs")]
        REDIS[("Redis — cache, rate limits, locks")]
        QDRANT[("Qdrant — embeddings")]
    end
    subgraph Runtime["Runtime & Isolation"]
        LLM["vLLM / Ollama (+ Anthropic toggle)"]
        SBOX["Sandbox Pool (gVisor)"]
    end
    subgraph Obs["Observability"]
        OTEL["OpenTelemetry -> Prometheus + Loki + Tempo -> Grafana"]
    end

    UI --> GQL
    UI -.-> WS
    GQL --> KAFKA
    GQL --> PG
    KAFKA --> ROUTER
    ROUTER --> QMAP
    ROUTER --> PARSERS
    PARSERS --> KAFKA
    QMAP --> KAFKA
    KAFKA --> TEMPORAL
    TEMPORAL --> GRADERS
    TEMPORAL --> META
    GRADERS --> LLM
    GRADERS --> SBOX
    GRADERS --> QDRANT
    GRADERS --> REDIS
    TEMPORAL --> PG
    PARSERS --> MINIO
    Grade -.-> OTEL
    Ingest -.-> OTEL
```

## Sequence: submission through grade

```mermaid
sequenceDiagram
    autonumber
    participant TA as TA (Instructor)
    participant UI as Dashboard
    participant GQL as GraphQL API
    participant K as Kafka
    participant P as Parser Pool
    participant DB as Postgres
    participant T as Temporal
    participant G as Grader Pool
    participant Q as Qdrant
    participant SB as Sandbox

    TA->>UI: Upload zip + rubric
    UI->>GQL: startIngestion mutation
    GQL->>K: publish submission.uploaded
    K->>P: consume, per-file-type
    P->>DB: write submissions (student_hash only)
    P->>K: publish artifact.parsed
    K->>T: trigger GradeStudentWorkflow per student
    par Parallel grader dispatch
        T->>G: TheoryGrader (with RAG)
        G->>Q: retrieve rubric context
        Q-->>G: chunks
        G-->>T: {score, confidence, reasoning}
    and
        T->>G: CodeExecutionGrader
        G->>SB: run tests
        SB-->>G: results
        G-->>T: {score, confidence, reasoning}
    end
    T->>G: CrossChecker + FeedbackSynthesizer
    T->>DB: aggregate, write final grade
    alt confidence < threshold
        T->>DB: enqueue for review
        T-->>UI: (subscription) review needed
    else confidence >= threshold
        T->>DB: mark auto-approved
    end
    T-->>UI: (subscription) grading complete
```

## Per-student workflow states

```mermaid
stateDiagram-v2
    [*] --> Registered
    Registered --> Parsing: on artifact.registered
    Parsing --> QuestionMapping: parsers complete
    QuestionMapping --> AwaitingMapping: any mapping conf < 0.6
    QuestionMapping --> Grading: all mappings confident
    AwaitingMapping --> Grading: instructor confirms
    Grading --> CrossCheck: all graders done
    CrossCheck --> AwaitingReview: overall_confidence < threshold
    CrossCheck --> AutoApproved: overall_confidence >= threshold
    AwaitingReview --> Approved: instructor approves
    AwaitingReview --> Regrading: instructor requests regrade
    Regrading --> Grading
    AutoApproved --> Exported
    Approved --> Exported
    Exported --> [*]
```

## Local port map (dev)

| Service | Port(s) | Purpose |
|---|---|---|
| Postgres | 5432 | Primary DB |
| Redis | 6379 | Cache / locks / rate limits |
| Redpanda (Kafka API) | 9092 | Event bus |
| Redpanda Console | 8080 | Kafka topic UI |
| MinIO API / Console | 9000 / 9001 | Object store |
| Qdrant HTTP / gRPC | 6333 / 6334 | Vector store |
| Temporal | 7233 | Workflow engine |
| Temporal UI | 8233 | Workflow UI |
| OTel Collector | 4317 / 4318 | OTLP gRPC / HTTP ingest |
| Prometheus | 9090 | Metrics |
| Grafana | 3001 | Dashboards |
| Loki | 3100 | Logs |
| Tempo | 3200 | Traces |
| API (FastAPI + GraphQL) | 8000 | Gateway |
| Next.js dashboard | 3000 | Frontend |

Application service `/healthz` ports are enumerated in
[`phases/phase-0-foundation.md`](phases/phase-0-foundation.md).
