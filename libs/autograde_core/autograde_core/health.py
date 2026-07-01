"""Shared health-check app factory.

Every Phase 0 service is a thin FastAPI app that exposes GET /healthz. The
factory keeps that surface identical across ~19 services so there is exactly one
place to evolve it (readiness probes, dependency checks) in later phases.
"""

from __future__ import annotations

from fastapi import FastAPI


def create_health_app(service_name: str) -> FastAPI:
    """Return a minimal FastAPI app exposing /healthz for ``service_name``."""
    app = FastAPI(title=f"Autograde AI — {service_name}", version="0.0.0")

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok", "service": service_name}

    return app
