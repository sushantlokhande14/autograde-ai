"""Phase 0 health stub for the question_mapper service."""

from autograde_core.health import create_health_app

SERVICE_NAME = "question_mapper"
app = create_health_app(SERVICE_NAME)
