"""Add deleted_at column to noor_import_history for soft-delete

Revision ID: z3b4c5d6e7f8
Revises: z2a3b4c5d6e7
Create Date: 2026-05-17

Adds a nullable ``deleted_at`` timestamp to ``noor_import_history`` so
principals can hide old import records from the history tab without
losing the underlying audit row. Rows with ``deleted_at IS NOT NULL``
are excluded from the GET /noor-import/history listing.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from migration_idempotent import has_column


revision: str = "z3b4c5d6e7f8"
down_revision: Union[str, Sequence[str], None] = "z2a3b4c5d6e7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if not has_column("noor_import_history", "deleted_at"):
        op.add_column(
            "noor_import_history",
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        )
    op.create_index(
        "idx_noor_import_history_school_active",
        "noor_import_history",
        ["school_id", "committed_at"],
        postgresql_where=sa.text("deleted_at IS NULL"),
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_index(
        "idx_noor_import_history_school_active",
        table_name="noor_import_history",
    )
    op.drop_column("noor_import_history", "deleted_at")
