"""Phase 0 health stub for the parser:notebook service."""

from autograde_core.health import create_health_app

SERVICE_NAME = "parser:notebook"
app = create_health_app(SERVICE_NAME)
