"""Phase 0 health stub for the grader:code_style service."""

from autograde_core.health import create_health_app

SERVICE_NAME = "grader:code_style"
app = create_health_app(SERVICE_NAME)
