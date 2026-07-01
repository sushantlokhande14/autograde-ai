"""Phase 0 health stub for the parser:image service."""

from autograde_core.health import create_health_app

SERVICE_NAME = "parser:image"
app = create_health_app(SERVICE_NAME)
