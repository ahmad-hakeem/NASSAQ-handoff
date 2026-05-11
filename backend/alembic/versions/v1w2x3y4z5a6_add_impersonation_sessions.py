"""add impersonation_sessions table (audit H-2 / M-6)

Revision ID: v1w2x3y4z5a6
Revises: u1v2w3x4y5z6
Create Date: 2026-05-11
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "v1w2x3y4z5a6"
down_revision: Union[str, Sequence[str], None] = "u1v2w3x4y5z6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "impersonation_sessions",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("jti", sa.String(), nullable=False, unique=True, index=True),
        sa.Column("original_user_id", sa.String(), nullable=False, index=True),
        sa.Column("original_role", sa.String(), nullable=False),
        sa.Column("target_user_id", sa.String(), nullable=True),
        sa.Column("target_role", sa.String(), nullable=False),
        sa.Column("target_tenant_id", sa.String(), nullable=True, index=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("end_reason", sa.String(), nullable=True),
        sa.Column("ip_address", sa.String(), nullable=True),
    )
    op.create_index(
        "idx_impersonation_active",
        "impersonation_sessions",
        ["jti", "ended_at"],
    )


def downgrade() -> None:
    op.drop_index("idx_impersonation_active", table_name="impersonation_sessions")
    op.drop_table("impersonation_sessions")
