"""Score an ingested assignment against the generator's ground-truth manifest.

Reports the Phase 1 Definition-of-Done numbers: artifact-type accuracy,
fallback rate, question-mapping accuracy, and the mapping-confidence
distribution with the review-gate split.

Usage:
    uv run python scripts/report_ingestion.py \
        --manifest data/uploads/cs152-hw3_manifest.json [--assignment cs152-hw3]
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from sqlalchemy import select

from autograde_core.hashing import student_hash
from autograde_db.models import Artifact
from autograde_db.session import session_scope
from services.question_mapper.mapper import CONFIDENCE_GATE


def build_truth(manifest: dict, assignment_key: str) -> dict[str, dict]:
    """Map DB source_file keys -> {true_type, true_question}."""
    truth: dict[str, dict] = {}
    for student in manifest["students"]:
        sh = student_hash(assignment_key, student["canvas_id"])
        for f in student["files"]:
            rel = f["path"].split("/", 1)[1]
            truth[f"{assignment_key}/{sh}/{rel}"] = f
    return truth


def report(manifest_path: Path, assignment_key: str) -> dict:
    manifest = json.loads(manifest_path.read_text())
    truth = build_truth(manifest, assignment_key)

    with session_scope() as session:
        rows = list(
            session.scalars(
                select(Artifact).where(Artifact.source_file.in_(list(truth)))
            )
        )

    total = len(rows)
    type_ok = sum(1 for r in rows if r.artifact_type == truth[r.source_file]["true_type"])
    fallback = sum(1 for r in rows if r.artifact_type == "unknown")

    mapped = [r for r in rows if r.question_id is not None]
    map_ok = sum(1 for r in mapped if r.question_id == truth[r.source_file]["true_question"])
    gated = [r for r in rows if r.question_id is None]

    buckets = Counter()
    for r in rows:
        c = r.question_mapping_confidence
        buckets["none" if c is None else f"{min(int(c * 10), 9) / 10:.1f}"] += 1

    out = {
        "artifacts": total,
        "expected_files": len(truth),
        "type_accuracy": type_ok / total if total else 0.0,
        "fallback_rate": fallback / total if total else 0.0,
        "mapped": len(mapped),
        "mapping_accuracy_on_mapped": map_ok / len(mapped) if mapped else 0.0,
        "gated_for_review": len(gated),
        "auto_mapped_rate": len(mapped) / total if total else 0.0,
        "confidence_gate": CONFIDENCE_GATE,
        "confidence_histogram": dict(sorted(buckets.items())),
    }
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", default="data/uploads/cs152-hw3_manifest.json")
    parser.add_argument("--assignment", default=None)
    args = parser.parse_args()

    manifest_path = Path(args.manifest)
    assignment_key = args.assignment or json.loads(manifest_path.read_text())["assignment_id"]
    out = report(manifest_path, assignment_key)

    print(f"artifacts ingested:       {out['artifacts']} / {out['expected_files']} files")
    print(f"type accuracy:            {out['type_accuracy']:.1%}   (target >= 95%)")
    print(f"fallback (unknown) rate:  {out['fallback_rate']:.1%}   (target < 3%)")
    print(f"auto-mapped:              {out['mapped']} ({out['auto_mapped_rate']:.1%})")
    print(f"mapping accuracy (auto):  {out['mapping_accuracy_on_mapped']:.1%}")
    print(f"gated for review (<{out['confidence_gate']}):  {out['gated_for_review']}")
    print("confidence histogram:")
    for bucket, count in out["confidence_histogram"].items():
        print(f"  {bucket:>4}: {'#' * count} {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
