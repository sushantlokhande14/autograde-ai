"""Shared building blocks for every Autograde AI service."""

from autograde_core.config import Settings, get_settings
from autograde_core.events import Topic
from autograde_core.hashing import (
    artifact_id_for,
    sha256_bytes,
    student_hash,
    submission_id_for,
)
from autograde_core.health import create_health_app
from autograde_core.models import Artifact, ArtifactType, Rubric, RubricQuestion
from autograde_core.services import SERVICE_PORTS, ServiceSpec, iter_services

__all__ = [
    "Settings",
    "get_settings",
    "create_health_app",
    "SERVICE_PORTS",
    "ServiceSpec",
    "iter_services",
    "Topic",
    "Artifact",
    "ArtifactType",
    "Rubric",
    "RubricQuestion",
    "student_hash",
    "submission_id_for",
    "artifact_id_for",
    "sha256_bytes",
]
