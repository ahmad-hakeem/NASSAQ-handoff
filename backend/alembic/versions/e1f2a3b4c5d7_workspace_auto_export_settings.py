"""IT §6.8 — workspace auto-export settings (Task #275)

Adds five columns to ``workspace_quota`` so an Independent Teacher can
opt in to a weekly auto-export. The hourly background sweep in
``app/lifecycle.py`` reads these columns to decide which workspaces to
mint a fresh export URL for at the user's chosen day-of-week + hour.

Columns
-------
* ``auto_export_enabled``      — opt-in toggle. Default FALSE.
* ``auto_export_dow``          — day of week, 0-6, **0=Sunday** (matches
                                  JS ``Date.getDay()`` so the FE doesn't
                                  have to translate).
* ``auto_export_hour``         — hour of day in UTC, 0-23.
* ``auto_export_last_run_at``  — last successful sweep stamp (any status).
                                  Used by the 6h idempotency guard.
* ``auto_export_last_status``  — short string status: ``success``,
                                  ``email_skipped_placeholder``,
                                  ``failed``, ``failed_no_workspace``,
                                  etc. Surfaced to the FE hub.

This migration also serves as a merge of the two open heads
``a4b5c6d7e8f9`` (it_onboarding_completed_at) and ``f9a0b1c2d3e4``
(notifications_preferences_table) so ``alembic upgrade head`` resolves
to a single deterministic node again.

Revision ID: e1f2a3b4c5d7
Revises: ('a4b5c6d7e8f9', 'f9a0b1c2d3e4')
Create Date: 2026-05-13
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "e1f2a3b4c5d7"
down_revision: Union[str, Sequence[str], None] = ("a4b5c6d7e8f9", "f9a0b1c2d3e4")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "workspace_quota",
        sa.Column(
            "auto_export_enabled", sa.Boolean(),
            nullable=False, server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "workspace_quota",
        sa.Column("auto_export_dow", sa.SmallInteger(), nullable=True),
    )
    op.add_column(
        "workspace_quota",
        sa.Column("auto_export_hour", sa.SmallInteger(), nullable=True),
    )
    op.add_column(
        "workspace_quota",
        sa.Column(
            "auto_export_last_run_at", sa.DateTime(timezone=True), nullable=True,
        ),
    )
    op.add_column(
        "workspace_quota",
        sa.Column("auto_export_last_status", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("workspace_quota", "auto_export_last_status")
    op.drop_column("workspace_quota", "auto_export_last_run_at")
    op.drop_column("workspace_quota", "auto_export_hour")
    op.drop_column("workspace_quota", "auto_export_dow")
    op.drop_column("workspace_quota", "auto_export_enabled")
