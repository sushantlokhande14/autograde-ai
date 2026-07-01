"""Generate a synthetic submissions zip for local testing.

Stub. The real generator — nested folders, inconsistent filenames, mixed
formats (PDF/ipynb/py/images/txt/docx) matching the messy-zip problem in
PROJECT_PLAN §3 — is implemented in Phase 1, with rubric-aware answer
generation added in Phase 6.

Usage (once implemented):
    uv run python scripts/seed_synthetic_data.py --students 25 --out data/uploads
"""

from __future__ import annotations

import argparse


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--students", type=int, default=25)
    parser.add_argument("--out", default="data/uploads")
    parser.parse_args()
    print("seed_synthetic_data is implemented in Phase 1 (Ingestion & Parsing).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
