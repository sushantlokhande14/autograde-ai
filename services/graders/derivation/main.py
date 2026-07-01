"""Phase 0 health stub for the grader:derivation service."""

from autograde_core.health import create_health_app

SERVICE_NAME = "grader:derivation"
app = create_health_app(SERVICE_NAME)
