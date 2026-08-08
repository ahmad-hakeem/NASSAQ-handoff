"""Add created_by column to teachers table

Revision ID: e5b9c2d7f1a3
Revises: d4f8a1c6e9b2
Create Date: 2026-07-25

The ``teachers.created_by`` column exists out-of-band on long-lived
databases (schema-drift allowlist entry "legacy column, no longer surfaced
via ORM") but was never created by any migration, so a fresh
``alembic upgrade head`` database lacks it. The Task #794 backfill
(``c9d5e3f7a2b1``) and its regression tests write ``created_by =
'backfill_794'`` on the teachers rows they create, which crashes with
UndefinedColumnError on fresh databases (CI). Additive-only: adds the
column when missing, no-op where it already exists.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e5b9c2d7f1a3"
down_revision: Union[str, Sequence[str], None] = "d4f8a1c6e9b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(table: str, column: str) -> bool:
    bind = op.get_bind()
    result = bind.execute(
        sa.text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name = :t AND column_name = :c AND table_schema = 'public'"
        ),
        {"t": table, "c": column},
    )
    return result.fetchone() is not None


def upgrade() -> None:
    if not _column_exists("teachers", "created_by"):
        op.add_column("teachers", sa.Column("created_by", sa.String(), nullable=True))


def downgrade() -> None:
    # Intentionally a no-op: dropping the column would be destructive on
    # long-lived databases where it pre-existed this migration.
    pass
