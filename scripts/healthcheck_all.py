"""Curl every service's /healthz and report a pass/fail summary.

Part of the Phase 0 Definition of Done: with the stack up and services running,
every /healthz should return 200. Ports come from the shared service registry.

Usage:
    uv run python scripts/healthcheck_all.py
"""

from __future__ import annotations

import sys

import httpx

from autograde_core.services import iter_services

# The Next.js dashboard participates in the sweep too.
WEB_HEALTH = ("web", "http://localhost:3000/api/healthz")


def check(name: str, url: str) -> bool:
    try:
        resp = httpx.get(url, timeout=2.0)
        ok = resp.status_code == 200
        marker = "ok " if ok else "FAIL"
        print(f"  [{marker}] {name:<26} {url}  -> {resp.status_code}")
        return ok
    except httpx.HTTPError as exc:
        print(f"  [FAIL] {name:<26} {url}  -> {exc.__class__.__name__}")
        return False


def main() -> int:
    print("Health-check sweep:")
    results = [
        check(s.name, f"http://localhost:{s.port}/healthz") for s in iter_services()
    ]
    results.append(check(*WEB_HEALTH))

    passed = sum(results)
    total = len(results)
    print(f"\n{passed}/{total} healthy.")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
