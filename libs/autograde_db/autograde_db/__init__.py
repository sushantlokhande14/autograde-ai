"""Database access layer for Autograde AI.

ORM models mirror the `grading` / `identity` schemas in
infra/postgres/init.sql. Alembic (see migrations/) manages forward evolution.
"""

from autograde_db.base import Base, get_engine
from autograde_db.session import session_scope

__all__ = ["Base", "get_engine", "session_scope"]
