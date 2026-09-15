"""Re-add legacy ``schools`` columns as DB-only compatibility storage.

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-09-15

The preceding cleanup revisions removed these columns even though production
still contains meaningful values.  This revision restores the exact nullable,
no-default production types without copying, normalising, or overwriting any
data.  The ORM deliberately remains unaware of them.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from migration_idempotent import has_column
from src.core.database.preserved_school_columns import PRESERVED_SCHOOL_COLUMNS


revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, Sequence[str], None] = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add only missing columns; never touch existing values."""

    for name, sql_type in PRESERVED_SCHOOL_COLUMNS.items():
        if not has_column("schools", name):
            # ``copy()`` prevents an Alembic operation from mutating the
            # registry's canonical type instance.  No server_default is
            # supplied: all five columns are nullable with no default.
            op.add_column(
                "schools",
                sa.Column(name, sql_type.copy(), nullable=True),
                schema="public",
            )


def downgrade() -> None:
    """Intentionally retain compatibility columns on downgrade.

    These columns may contain tenant data that predates this revision.  A
    downgrade must never turn schema rollback into irreversible data loss.
    """

    pass