"""Add bulk_import_batches table

Revision ID: f4a5b6c7d8e9
Revises: e3f4a5b6c7d8
Create Date: 2026-09-09
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from migration_idempotent import has_table

revision: str = "f4a5b6c7d8e9"
down_revision: Union[str, Sequence[str], None] = "e3f4a5b6c7d8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if not has_table("bulk_import_batches"):
        op.create_table(
            "bulk_import_batches",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("school_id", sa.String(), sa.ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("actor_id", sa.String(), nullable=True),
            sa.Column("actor_name", sa.String(), nullable=True),
            sa.Column("import_type", sa.String(), nullable=False, default="students"),
            sa.Column("file_name", sa.String(), nullable=True),
            sa.Column("imported_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("student_ids", JSONB, nullable=True),
            sa.Column("created_class_ids", JSONB, nullable=True),
            sa.Column("status", sa.String(), nullable=False, server_default="active"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
        op.create_index("idx_bulk_import_batches_school_status", "bulk_import_batches", ["school_id", "status"])


def downgrade() -> None:
    if has_table("bulk_import_batches"):
        op.drop_index("idx_bulk_import_batches_school_status", table_name="bulk_import_batches")
        op.drop_table("bulk_import_batches")
