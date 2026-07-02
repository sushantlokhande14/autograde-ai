"""Class-scale load test: ingest and grade a full synthetic class.

Measures wall-clock for ingestion and grading separately, reports per-grader
latency from the audit tables, and writes a JSON summary. Per the resolved
Phase 4 decision the measured number is reported honestly against the
30-minute target.

Usage:
    uv run python scripts/load_test.py --students 250 --seed 777
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import time
from pathlib import Path

from autograde_core.models import Rubric
from autograde_core.telemetry import configure_telemetry


def _pctl(samples: list, q: float) -> float:
    if not samples:
        return 0.0
    return sorted(samples)[min(len(samples) - 1, int(len(samples) * q))]


def ingest(students: int, seed: int, out: str) -> list[str]:
    from seed_synthetic_data import build

    from services.orchestrator.ingest_worker import run as drain
    from services.router.router import route

    out_dir = Path(out)
    manifest = build(students, seed, out_dir)
    zip_bytes = (out_dir / "cs152-hw3_submissions.zip").read_bytes()
    rubric = Rubric.model_validate(
        json.loads((out_dir / "cs152-hw3_rubric.json").read_text())
    )
    roster = {s["canvas_id"]: s["display_name"] for s in manifest["students"]}
    result = route(zip_bytes, assignment_key=rubric.assignment_id, roster=roster,
                   rubric=rubric, publish_events=True)
    drain(group=f"load-ingest-{seed}", idle_timeout_s=15.0)
    return sorted({str(r.submission_id) for r in result.registrations})


async def grade_all(submissions: list[str], concurrency: int) -> None:
    from temporalio.client import Client

    from autograde_core.config import get_settings
    from services.orchestrator.worker import create_worker
    from services.orchestrator.workflows import TASK_QUEUE, GradeStudentWorkflow

    client = await Client.connect(get_settings().temporal_address)
    worker = await create_worker(client, concurrency=concurrency)
    async with worker:
        handles = []
        for sid in submissions:
            try:
                handles.append(await client.start_workflow(
                    GradeStudentWorkflow.run, sid,
                    id=f"grade-load-{sid}", task_queue=TASK_QUEUE,
                ))
            except Exception:
                handles.append(client.get_workflow_handle(f"grade-load-{sid}"))
        done = 0
        for h in handles:
            await h.result()
            done += 1
            if done % 25 == 0:
                print(f"  graded {done}/{len(handles)}")


def report(submissions: list[str]) -> dict:
    from sqlalchemy import select

    from autograde_db.models import Grade, LlmCall, SandboxRun
    from autograde_db.session import session_scope

    with session_scope() as session:
        llm = [(c.grader, c.latency_ms, c.cache_hit) for c in session.scalars(select(LlmCall))]
        sandbox = [r.duration_ms for r in session.scalars(select(SandboxRun)) if r.duration_ms]
        graders = sorted({g for g, _, _ in llm})
        grades = len(list(session.scalars(select(Grade.id))))

    per_grader = {}
    for name in graders:
        lat = [ms for g, ms, hit in llm if g == name and not hit]
        hits = sum(1 for g, _, hit in llm if g == name and hit)
        per_grader[name] = {
            "llm_calls": len(lat) + hits, "cache_hits": hits,
            "p50_ms": _pctl(lat, 0.5), "p99_ms": _pctl(lat, 0.99),
        }
    return {
        "grade_rows": grades,
        "llm": per_grader,
        "sandbox": {"runs": len(sandbox), "p50_ms": _pctl(sandbox, 0.5), "p99_ms": _pctl(sandbox, 0.99)},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--students", type=int, default=250)
    parser.add_argument("--seed", type=int, default=777)
    parser.add_argument("--out", default="data/uploads_class")
    parser.add_argument("--concurrency", type=int, default=8)
    parser.add_argument("--skip-ingest", action="store_true")
    args = parser.parse_args()

    import sys

    sys.path.insert(0, "scripts")
    configure_telemetry("load-test")

    t0 = time.monotonic()
    if args.skip_ingest:
        from sqlalchemy import select

        from autograde_db.models import Submission
        from autograde_db.session import session_scope

        with session_scope() as session:
            submissions = [str(s) for s in session.scalars(select(Submission.id))]
    else:
        submissions = ingest(args.students, args.seed, args.out)
    t_ingest = time.monotonic() - t0
    print(f"ingested {len(submissions)} submissions in {t_ingest/60:.1f} min")

    t1 = time.monotonic()
    asyncio.run(grade_all(submissions, args.concurrency))
    from services.graders.plagiarism.detector import detect

    flagged = detect("cs152-hw3", "q2")
    t_grade = time.monotonic() - t1

    stats = report(submissions)
    summary = {
        "submissions": len(submissions),
        "ingest_min": round(t_ingest / 60, 1),
        "grade_min": round(t_grade / 60, 1),
        "total_min": round((t_ingest + t_grade) / 60, 1),
        "sec_per_submission": round(t_grade / max(len(submissions), 1), 1),
        "plagiarism_pairs_flagged": sum(1 for r in flagged if r["flagged"]),
        **stats,
    }
    Path("data/load_test_summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))
    target = "PASS (<30 min)" if t_grade / 60 < 30 else "OVER TARGET (reported honestly)"
    print(f"grading wall-clock: {t_grade/60:.1f} min -> {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
