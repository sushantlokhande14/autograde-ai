"""Phase 0 health stub for the retrieval service."""

from autograde_core.health import create_health_app

SERVICE_NAME = "retrieval"
app = create_health_app(SERVICE_NAME)
