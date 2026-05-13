"""Task #249 — IT Notifications Inbox: notifications_preferences table

Per-user, per-category channel preferences for the Independent-Teacher
inbox. One row per (user_id, category); ``in_app`` is stored but the
route forces it to True on read so the inbox surface can never be
silenced (it is the source of truth).

Revision ID: f9a0b1c2d3e4
Revises: e8f9a0b1c2d3
Create Date: 2026-05-13
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "f9a0b1c2d3e4"
down_revision: Union[str, Sequence[str], None] = "e8f9a0b1c2d3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "notifications_preferences",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("category", sa.String(length=64), nullable=False),
        sa.Column("in_app", sa.Boolean(), nullable=False, server_default=sa.text("TRUE")),
        sa.Column("email", sa.Boolean(), nullable=False, server_default=sa.text("TRUE")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("user_id", "category", name="uq_notif_prefs_user_category"),
    )
    op.create_index(
        "idx_notif_prefs_user",
        "notifications_preferences",
        ["user_id"],
    )


def downgrade() -> None:
    op.drop_index("idx_notif_prefs_user", table_name="notifications_preferences")
    op.drop_table("notifications_preferences")
