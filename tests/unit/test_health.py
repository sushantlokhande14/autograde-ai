from fastapi.testclient import TestClient

from autograde_core.health import create_health_app


def test_healthz_returns_ok() -> None:
    client = TestClient(create_health_app("test-service"))
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "service": "test-service"}
