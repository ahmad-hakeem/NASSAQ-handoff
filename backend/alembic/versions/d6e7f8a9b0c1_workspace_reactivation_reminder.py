"""IT Phase 2 §6.8 — schools.reactivation_reminder_sent_at (Task #218)

Revision ID: d6e7f8a9b0c1
Revises: c5d6e7f8a9b0
Create Date: 2026-05-13

Adds ``schools.reactivation_reminder_sent_at`` (nullable timestamptz)
so the daily reactivation-reminder background loop can avoid sending
duplicate "your workspace is about to expire" emails. Set the moment
the reminder email is dispatched; cleared by the reactivate endpoint
so a future archive cycle gets a fresh reminder.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from migration_idempotent import has_column


revision: str = "d6e7f8a9b0c1"
down_revision: Union[str, Sequence[str], None] = "c5d6e7f8a9b0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if not has_column("schools", "reactivation_reminder_sent_at"):
        op.add_column(
            "schools",
            sa.Column(
                "reactivation_reminder_sent_at",
                sa.DateTime(timezone=True),
                nullable=True,
            ),
        )


def downgrade() -> None:
    op.drop_column("schools", "reactivation_reminder_sent_at")
