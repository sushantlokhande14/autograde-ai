"""Grading-call microbenchmark: the numbers behind Phase 4 throughput.

Measures a representative rubric-grading call at grading token caps, and
whether the Ollama server executes concurrent requests in parallel
(OLLAMA_NUM_PARALLEL) or serializes them.

Usage:
    uv run python scripts/bench_llm.py [--rounds 3]
"""

from __future__ import annotations

import argparse
import statistics
import time
from concurrent.futures import ThreadPoolExecutor

from autograde_core.config import get_settings
from autograde_llm import CompletionRequest
from autograde_llm.ollama_backend import OllamaClient

PROMPT = (
    "QUESTION (q1, worth 10 points): Explain call-by-name vs call-by-value.\n"
    "RUBRIC:\n- definition of call-by-name (3)\n- definition of call-by-value (3)\n"
    "- discriminating example (4)\n\n"
    "STUDENT ANSWER:\nCall-by-value computes the argument first. Call-by-name "
    "substitutes the expression and evaluates on use; unused arguments are never "
    "evaluated, e.g. const(1, loop()) terminates.\n\nScore each criterion. JSON only."
)
SYSTEM = "You are a strict TA. Respond with only JSON: {\"criterion_scores\": [...], \"confidence\": <0-1>, \"reasoning\": \"...\"}"


def one_call(max_tokens: int) -> int:
    client = OllamaClient()
    result = client.complete(
        CompletionRequest(
            system=SYSTEM, prompt=PROMPT, model=get_settings().local_model_theory,
            max_tokens=max_tokens, temperature=0.0,
        )
    )
    return result.latency_ms


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rounds", type=int, default=3)
    args = parser.parse_args()

    one_call(50)  # warm the model into memory

    for cap in (250, 600):
        samples = [one_call(cap) for _ in range(args.rounds)]
        print(f"max_tokens={cap}: p50={statistics.median(samples):.0f}ms samples={samples}")

    # concurrency probe: two simultaneous calls
    start = time.monotonic()
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(lambda _: one_call(250), range(2)))
    pair_ms = (time.monotonic() - start) * 1000
    solo = statistics.median([one_call(250) for _ in range(2)])
    ratio = pair_ms / solo if solo else 0
    verdict = "parallel" if ratio < 1.5 else "serialized"
    print(f"2 concurrent: {pair_ms:.0f}ms vs solo {solo:.0f}ms -> {verdict} (ratio {ratio:.2f})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
