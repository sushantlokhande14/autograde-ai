"""Phase 0 health stub for the router service."""

from autograde_core.health import create_health_app

SERVICE_NAME = "router"
app = create_health_app(SERVICE_NAME)
