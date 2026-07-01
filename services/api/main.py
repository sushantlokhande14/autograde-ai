"""Phase 0 health stub for the api service."""

from autograde_core.health import create_health_app

SERVICE_NAME = "api"
app = create_health_app(SERVICE_NAME)
