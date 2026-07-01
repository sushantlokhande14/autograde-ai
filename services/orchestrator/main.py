"""Phase 0 health stub for the orchestrator service."""

from autograde_core.health import create_health_app

SERVICE_NAME = "orchestrator"
app = create_health_app(SERVICE_NAME)
