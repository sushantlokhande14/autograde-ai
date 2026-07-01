"""Database access layer for Autograde AI.

Phase 0 provides the declarative base and an engine factory. Concrete ORM
models mirroring the `grading` / `identity` schemas (infra/postgres/init.sql)
land in Phase 1, alongside Alembic migrations.
"""

from autograde_db.base import Base, get_engine

__all__ = ["Base", "get_engine"]
