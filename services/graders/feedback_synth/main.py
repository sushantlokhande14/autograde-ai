"""Phase 0 health stub for the feedback_synth service."""

from autograde_core.health import create_health_app

SERVICE_NAME = "feedback_synth"
app = create_health_app(SERVICE_NAME)
