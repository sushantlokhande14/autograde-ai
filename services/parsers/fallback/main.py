"""Phase 0 health stub for the parser:fallback service."""

from autograde_core.health import create_health_app

SERVICE_NAME = "parser:fallback"
app = create_health_app(SERVICE_NAME)
