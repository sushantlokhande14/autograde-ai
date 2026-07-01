"""Integration smoke: infra ports are listening.

Skipped unless AUTOGRADE_RUN_INTEGRATION=1, so `uv run pytest` stays green
without the Docker stack up. Run after `docker compose up -d`.
"""

from __future__ import annotations

import os
import socket

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("AUTOGRADE_RUN_INTEGRATION") != "1",
    reason="stack not running; set AUTOGRADE_RUN_INTEGRATION=1 to enable",
)

CORE_PORTS = {
    "postgres": 5432,
    "redis": 6379,
    "kafka": 9092,
    "minio": 9000,
    "qdrant": 6333,
    "temporal": 7233,
}


def _port_open(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(1.0)
        return sock.connect_ex((host, port)) == 0


@pytest.mark.parametrize(("name", "port"), CORE_PORTS.items())
def test_core_port_listening(name: str, port: int) -> None:
    assert _port_open("localhost", port), f"{name} not listening on :{port}"
