"""Phase 0 health stub for the cross_check service."""

from autograde_core.health import create_health_app

SERVICE_NAME = "cross_check"
app = create_health_app(SERVICE_NAME)
