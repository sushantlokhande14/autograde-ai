"""Phase 0 health stub for the export service."""

from autograde_core.health import create_health_app

SERVICE_NAME = "export"
app = create_health_app(SERVICE_NAME)
