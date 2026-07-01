"""Retrieval latency benchmark: cached vs cold, against the DoD targets.

Warms the embedding model first (its one-time load is not a retrieval cost),
then measures cold (cache bypassed) and cached paths per rubric question.

Usage:
    uv run python scripts/bench_retrieval.py --assignment cs152-hw3 --rounds 10
"""

from __future__ import annotations

import argparse
import statistics

from autograde_rag.embed import embed_texts
from autograde_rag.retrieve import retrieve

QUESTIONS = ["q1", "q2", "q3", "q4"]
TYPES = {"q1": "theory", "q2": "code", "q3": "derivation", "q4": "figure"}


def percentiles(samples: list[int]) -> str:
    p50 = statistics.median(samples)
    p95 = sorted(samples)[max(0, int(len(samples) * 0.95) - 1)]
    return f"p50={p50:.0f}ms p95={p95:.0f}ms max={max(samples)}ms"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--assignment", default="cs152-hw3")
    parser.add_argument("--rounds", type=int, default=10)
    args = parser.parse_args()

    embed_texts(["warmup"])  # load the model outside the timed region

    cold: list[int] = []
    cached: list[int] = []
    for _ in range(args.rounds):
        for q in QUESTIONS:
            r = retrieve(args.assignment, q, TYPES[q], use_cache=False)
            cold.append(r.latency_ms)
            retrieve(args.assignment, q, TYPES[q], use_cache=True)  # prime
            r2 = retrieve(args.assignment, q, TYPES[q], use_cache=True)
            assert r2.cache_hit, "expected a cache hit on the primed key"
            cached.append(r2.latency_ms)

    print(f"cold   ({len(cold)} calls): {percentiles(cold)}   target p95 < 200ms")
    print(f"cached ({len(cached)} calls): {percentiles(cached)}   target p95 < 50ms")

    ok = sorted(cold)[int(len(cold) * 0.95) - 1] < 200 and sorted(cached)[
        int(len(cached) * 0.95) - 1
    ] < 50
    print("PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
