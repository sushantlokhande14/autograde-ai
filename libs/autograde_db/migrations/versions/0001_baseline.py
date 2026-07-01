"""baseline: adopt the grading/identity schema

`infra/postgres/init.sql` is authoritative for the dev container. This baseline
creates the schemas and tables on a fresh database (checkfirst) so
`alembic upgrade head` can bootstrap a non-container Postgres; on the container
it is a safe no-op because the objects already exist. Role and RLS setup remain
in init.sql and are not duplicated here.

Revision ID: 0001_baseline
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

import autograde_db.models  # noqa: F401  (populate Base.metadata)
from autograde_db.base import Base

revision: str = "0001_baseline"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    op.execute("CREATE SCHEMA IF NOT EXISTS grading")
    op.execute("CREATE SCHEMA IF NOT EXISTS identity")
    Base.metadata.create_all(bind=bind, checkfirst=True)


def downgrade() -> None:
    Base.metadata.drop_all(bind=op.get_bind())
