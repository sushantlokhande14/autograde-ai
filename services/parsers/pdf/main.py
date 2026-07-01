"""Phase 0 health stub for the parser:pdf service."""

from autograde_core.health import create_health_app

SERVICE_NAME = "parser:pdf"
app = create_health_app(SERVICE_NAME)
