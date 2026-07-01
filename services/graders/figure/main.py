"""Phase 0 health stub for the grader:figure service."""

from autograde_core.health import create_health_app

SERVICE_NAME = "grader:figure"
app = create_health_app(SERVICE_NAME)
