"""Phase 0 health stub for the parser:code service."""

from autograde_core.health import create_health_app

SERVICE_NAME = "parser:code"
app = create_health_app(SERVICE_NAME)
