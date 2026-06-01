"""Add public_hakim_rate_counters for shared cross-worker public Hakim limits

Revision ID: e0f1a2b3c4d5
Revises: d9e0f1a2b3c4
Create Date: 2026-05-26

Creates a Postgres-backed counter table used by the public landing-page
Hakim chat endpoints (`/api/public/hakim/chat` and `.../chat/stream`) to
enforce per-IP and per-IP+UA rate limits that hold across worker
processes (the existing in-memory limiter is per-process).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from migration_idempotent import has_table


revision: str = "e0f1a2b3c4d5"
down_revision: Union[str, Sequence[str], None] = "d9e0f1a2b3c4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if not has_table("public_hakim_rate_counters"):
        op.create_table(
            "public_hakim_rate_counters",
            sa.Column("key", sa.String(length=160), primary_key=True),
            sa.Column("count", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        )
    op.create_index(
        "ix_public_hakim_rate_counters_expires_at",
        "public_hakim_rate_counters",
        ["expires_at"],
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_public_hakim_rate_counters_expires_at",
        table_name="public_hakim_rate_counters",
    )
    op.drop_table("public_hakim_rate_counters")
