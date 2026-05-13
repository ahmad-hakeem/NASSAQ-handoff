"""IT Phase 2 §6.8 — schools.last_export_token_hash + last_export_consumed_at

Single-use enforcement for the workspace-export download token.
The signed JWT alone makes the URL replayable for the full 24h TTL;
storing the token hash on the schools row + a consumed_at timestamp
lets the public download endpoint reject replays after the first
successful download.

Revision ID: c5d6e7f8a9b0
Revises: b4c5d6e7f8a9
Create Date: 2026-05-13
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "c5d6e7f8a9b0"
down_revision = "b4c5d6e7f8a9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "schools",
        sa.Column("last_export_token_hash", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "schools",
        sa.Column("last_export_consumed_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("schools", "last_export_consumed_at")
    op.drop_column("schools", "last_export_token_hash")
