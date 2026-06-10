"""Add credits column to subjects

Revision ID: b6c7d8e9f0a1
Revises: a5b6c7d8e9f0
Create Date: 2026-06-10

Additive, non-destructive. Adds an integer ``credits`` column to the
``subjects`` table so the generic ``/subjects`` create/update routes can
persist the credit-hours value the catalog UI already collects (the field
existed in the create/edit dialogs but was silently dropped on write).

Existing rows are backfilled to ``1`` via the column's server default, so no
subject loses data and the add operation is instant on PostgreSQL 11+.

Idempotent: the column is only added when it does not already exist. The
downgrade drops the (purely additive) column.
"""
from typing import Sequence, Union

from alembic import op, context
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "b6c7d8e9f0a1"
down_revision: Union[str, Sequence[str], None] = "a5b6c7d8e9f0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(table: str, column: str) -> bool:
    # Offline (``--sql``) mode has no live connection to introspect; emit the
    # DDL unconditionally so SQL generation still works.
    if context.is_offline_mode():
        return False
    bind = op.get_bind()
    insp = inspect(bind)
    return any(col["name"] == column for col in insp.get_columns(table))


def upgrade() -> None:
    if not _has_column("subjects", "credits"):
        op.add_column(
            "subjects",
            sa.Column("credits", sa.Integer(), nullable=False, server_default="1"),
        )


def downgrade() -> None:
    # In offline mode ``_has_column`` returns False, so the drop is skipped;
    # online it only drops when the column is actually present.
    if not context.is_offline_mode() and _has_column("subjects", "credits"):
        op.drop_column("subjects", "credits")
