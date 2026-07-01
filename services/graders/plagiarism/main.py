"""Phase 0 health stub for the grader:plagiarism service."""

from autograde_core.health import create_health_app

SERVICE_NAME = "grader:plagiarism"
app = create_health_app(SERVICE_NAME)
