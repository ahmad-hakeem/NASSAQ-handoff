"""Add ownership manifest version to bulk_import_batches.

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-09-15
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from migration_idempotent import has_column


revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, Sequence[str], None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # NULL is deliberate: pre-versioned batches must remain rollbackable for
    # their students/classes only, never for parent or user rows.
    if not has_column("bulk_import_batches", "ownership_version"):
        op.add_column(
            "bulk_import_batches",
            sa.Column("ownership_version", sa.Integer(), nullable=True),
        )


def downgrade() -> None:
    if has_column("bulk_import_batches", "ownership_version"):
        op.drop_column("bulk_import_batches", "ownership_version")