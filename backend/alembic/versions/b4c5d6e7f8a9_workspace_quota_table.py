"""IT Phase 2 §6.1 — workspace_quota table (Task #207)

Revision ID: b4c5d6e7f8a9
Revises: a3b4c5d6e7f8
Create Date: 2026-05-12

Adds the ``workspace_quota`` row that backs the workspace-aware bulk
student import flow for Independent Teachers. One row per IT
workspace (PK == ``schools.id`` for the synthetic ``itw_{user_id}``
row). Counters reset on a UTC-day boundary in application code.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b4c5d6e7f8a9"
down_revision: Union[str, Sequence[str], None] = "a3b4c5d6e7f8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "workspace_quota",
        sa.Column("workspace_school_id", sa.String(), nullable=False),
        sa.Column("max_students", sa.Integer(), nullable=False, server_default="200"),
        sa.Column("max_classes", sa.Integer(), nullable=False, server_default="5"),
        sa.Column(
            "max_imports_per_day", sa.Integer(), nullable=False, server_default="5",
        ),
        sa.Column(
            "max_rows_per_import", sa.Integer(), nullable=False, server_default="200",
        ),
        sa.Column("imports_today", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("imports_today_date", sa.Date(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(
            ["workspace_school_id"], ["schools.id"], ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("workspace_school_id"),
    )

    # Backfill existing IT workspaces with default quota rows so the
    # bulk-import endpoints work for accounts bootstrapped before this
    # revision shipped.
    op.execute(
        """
        INSERT INTO workspace_quota (workspace_school_id)
        SELECT id FROM schools
        WHERE school_type IN ('independent_teacher', 'independent_teacher_workspace')
        ON CONFLICT (workspace_school_id) DO NOTHING
        """
    )


def downgrade() -> None:
    op.drop_table("workspace_quota")
