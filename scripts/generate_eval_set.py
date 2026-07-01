"""Build the 100-submission gold eval set.

Stub. Implemented in Phase 6 (Evaluation & Hardening): a mix of correct,
partially correct, wrong, and creatively-wrong answers across two assignments,
hand-graded twice for the human-ceiling agreement number. See docs/EVALUATION.md.

Usage (once implemented):
    uv run python scripts/generate_eval_set.py --out tests/eval/gold_set
"""

from __future__ import annotations

import argparse


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="tests/eval/gold_set")
    parser.parse_args()
    print("generate_eval_set is implemented in Phase 6 (Evaluation & Hardening).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
