"""Shared building blocks for every Autograde AI service."""

from autograde_core.config import Settings, get_settings
from autograde_core.health import create_health_app
from autograde_core.services import SERVICE_PORTS, ServiceSpec, iter_services

__all__ = [
    "Settings",
    "get_settings",
    "create_health_app",
    "SERVICE_PORTS",
    "ServiceSpec",
    "iter_services",
]
