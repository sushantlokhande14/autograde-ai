"""End-to-end ingestion test against the live stack.

Drives the real pipeline — route (Kafka publish) → worker drain (parse,
persist, map) → report — over the generated 25-submission zip, and asserts the
Phase 1 Definition of Done: >=95% artifact-type accuracy and <3% fallback rate.

Opt-in (needs Docker stack + Ollama + generated data):
    AUTOGRADE_RUN_INTEGRATION=1 uv run pytest tests/integration/test_ingestion_e2e.py -q
Idempotent: deterministic ids + upserts make re-runs safe.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("AUTOGRADE_RUN_INTEGRATION") != "1",
    reason="stack not running; set AUTOGRADE_RUN_INTEGRATION=1 to enable",
)

UPLOADS = Path("data/uploads")
ZIP = UPLOADS / "cs152-hw3_submissions.zip"


@pytest.fixture(scope="module")
def ingested() -> dict:
    if not ZIP.exists():
        pytest.skip("generate data first: uv run python scripts/seed_synthetic_data.py")

    sys.path.insert(0, "scripts")
    from report_ingestion import report

    from autograde_core.models import Rubric
    from services.orchestrator.ingest_worker import run as run_worker
    from services.router.router import route

    manifest = json.loads((UPLOADS / "cs152-hw3_manifest.json").read_text())
    rubric = Rubric.model_validate(json.loads((UPLOADS / "cs152-hw3_rubric.json").read_text()))
    roster = {s["canvas_id"]: s["display_name"] for s in manifest["students"]}

    result = route(
        ZIP.read_bytes(),
        assignment_key=rubric.assignment_id,
        roster=roster,
        rubric=rubric,
        publish_events=True,
    )
    assert result.registrations, "router produced no registrations"
    assert not result.unrouted, f"unrouted files: {result.unrouted}"

    run_worker(group="e2e-test", idle_timeout_s=10.0)
    return report(UPLOADS / "cs152-hw3_manifest.json", rubric.assignment_id)


def test_all_files_ingested(ingested: dict) -> None:
    assert ingested["artifacts"] == ingested["expected_files"]


def test_type_accuracy_meets_dod(ingested: dict) -> None:
    assert ingested["type_accuracy"] >= 0.95, ingested


def test_fallback_rate_meets_dod(ingested: dict) -> None:
    assert ingested["fallback_rate"] < 0.03, ingested


def test_confidence_distribution_reported(ingested: dict) -> None:
    assert sum(ingested["confidence_histogram"].values()) == ingested["artifacts"]
    # every artifact either auto-mapped or explicitly gated for review
    assert ingested["mapped"] + ingested["gated_for_review"] == ingested["artifacts"]
