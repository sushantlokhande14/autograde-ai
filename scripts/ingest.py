"""Ingest a submissions zip end to end.

Routes the zip (identity + submissions + raw files + artifact.registered
events), then drains the ingestion worker until the queue is idle. This is the
manual driver for the Phase 1 pipeline; the dashboard upload takes over in
Phase 5.

Usage:
    uv run python scripts/ingest.py data/uploads/cs152-hw3_submissions.zip \
        --manifest data/uploads/cs152-hw3_manifest.json \
        --rubric data/uploads/cs152-hw3_rubric.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from autograde_core.models import Rubric
from services.orchestrator.ingest_worker import run as run_worker
from services.router.router import route


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("zip_path")
    parser.add_argument("--manifest", required=True, help="roster manifest json")
    parser.add_argument("--rubric", required=True, help="rubric json")
    parser.add_argument("--assignment", default=None, help="assignment key (default: rubric id)")
    args = parser.parse_args()

    rubric = Rubric.model_validate(json.loads(Path(args.rubric).read_text()))
    manifest = json.loads(Path(args.manifest).read_text())
    roster = {s["canvas_id"]: s["display_name"] for s in manifest["students"]}
    assignment_key = args.assignment or rubric.assignment_id

    result = route(
        Path(args.zip_path).read_bytes(),
        assignment_key=assignment_key,
        roster=roster,
        rubric=rubric,
        publish_events=True,
    )
    print(f"routed: {len(result.registrations)} files, {len(result.unrouted)} unrouted")

    processed = run_worker(idle_timeout_s=10.0)
    print(f"worker processed {processed} registrations")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
