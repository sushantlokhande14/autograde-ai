"""SQLAlchemy declarative base and engine factory."""

from __future__ import annotations

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase

from autograde_core.config import get_settings


class Base(DeclarativeBase):
    """Declarative base for all Autograde AI ORM models."""


def get_engine(echo: bool = False) -> Engine:
    """Create a SQLAlchemy engine from application settings."""
    return create_engine(get_settings().postgres_dsn, echo=echo, pool_pre_ping=True)
