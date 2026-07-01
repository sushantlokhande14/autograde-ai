"""Chunk, embed, and index a course-materials folder into Qdrant.

Reads the folder's materials_manifest.json for per-document payload metadata
(question_ids, reference_answer). Topical + distractor docs land in
``course_materials``; reference answers additionally land in
``rubric_context``. Idempotent: stable chunk ids upsert in place.

Usage:
    uv run python scripts/index_materials.py data/materials --assignment cs152-hw3
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from autograde_rag.chunk import chunk_text
from autograde_rag.index import (
    COURSE_MATERIALS,
    RUBRIC_CONTEXT,
    ensure_collections,
    index_chunks,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("materials_dir")
    parser.add_argument("--assignment", required=True)
    args = parser.parse_args()

    folder = Path(args.materials_dir)
    manifest = json.loads((folder / "materials_manifest.json").read_text())

    created = ensure_collections()
    if created:
        print(f"created collections: {created}")

    course_total = rubric_total = 0
    for doc in manifest["documents"]:
        text = (folder / doc["source"]).read_text(encoding="utf-8")
        chunks = chunk_text(
            doc["source"],
            text,
            metadata={
                "question_ids": doc["question_ids"],
                "reference_answer": doc["reference_answer"],
            },
        )
        course_total += index_chunks(
            COURSE_MATERIALS, chunks, assignment_id=args.assignment
        )
        if doc["reference_answer"]:
            rubric_total += index_chunks(
                RUBRIC_CONTEXT, chunks, assignment_id=args.assignment
            )

    print(f"indexed {course_total} chunks -> {COURSE_MATERIALS}")
    print(f"indexed {rubric_total} chunks -> {RUBRIC_CONTEXT} (reference answers)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
