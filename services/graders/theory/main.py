"""Phase 0 health stub for the grader:theory service."""

from autograde_core.health import create_health_app

SERVICE_NAME = "grader:theory"
app = create_health_app(SERVICE_NAME)
