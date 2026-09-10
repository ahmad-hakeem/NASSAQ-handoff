"""Add created_parent_ids and created_parent_user_ids to bulk_import_batches

Revision ID: b2c3d4e5f6a7
Revises: f4a5b6c7d8e9
Create Date: 2026-09-10
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from migration_idempotent import has_column

revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, Sequence[str], None] = "f4a5b6c7d8e9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if not has_column("bulk_import_batches", "created_parent_ids"):
        op.add_column("bulk_import_batches", sa.Column("created_parent_ids", JSONB, nullable=True, server_default="[]"))
    if not has_column("bulk_import_batches", "created_parent_user_ids"):
        op.add_column("bulk_import_batches", sa.Column("created_parent_user_ids", JSONB, nullable=True, server_default="[]"))


def downgrade() -> None:
    if has_column("bulk_import_batches", "created_parent_user_ids"):
        op.drop_column("bulk_import_batches", "created_parent_user_ids")
    if has_column("bulk_import_batches", "created_parent_ids"):
        op.drop_column("bulk_import_batches", "created_parent_ids")
