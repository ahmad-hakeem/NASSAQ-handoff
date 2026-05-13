"""Task #249 — IT Notifications Inbox: notifications.category + cta_url

Adds two nullable columns on the existing ``notifications`` table:
  * ``category`` (string, indexed) — coarse-grained bucket used by the
    Independent-Teacher inbox + per-category channel preferences:
    ``collab_invite | parent_accept | workspace_lifecycle | quota |
     lesson_plan | general``. Default 'general' for safety; existing
    rows backfilled to 'general' so the IT inbox can render them.
  * ``cta_url`` (string, nullable) — workspace-relative deep-link the
    inbox row uses for "open" navigation. Distinct from ``action_url``
    (kept for legacy school-tenant flows) so the IT surface doesn't
    collide with the existing notification UIs.

Revision ID: d1e2f3a4b5c6
Revises: f1a2b3c4d5e7
Create Date: 2026-05-13
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "e8f9a0b1c2d3"
down_revision: Union[str, Sequence[str], None] = "f1a2b3c4d5e7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "notifications",
        sa.Column(
            "category",
            sa.String(length=64),
            nullable=False,
            server_default=sa.text("'general'"),
        ),
    )
    op.add_column(
        "notifications",
        sa.Column("cta_url", sa.String(length=512), nullable=True),
    )
    op.create_index(
        "idx_pg_notifications_user_category_date",
        "notifications",
        ["user_id", "category", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "idx_pg_notifications_user_category_date",
        table_name="notifications",
    )
    op.drop_column("notifications", "cta_url")
    op.drop_column("notifications", "category")
