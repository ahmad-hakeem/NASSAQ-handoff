"""IT Phase 2 §6.8 — workspace reactivation banner columns (Task #222)

Revision ID: e7f8a9b0c1d2
Revises: d6e7f8a9b0c1
Create Date: 2026-05-13

Adds three nullable timestamptz columns on ``schools`` so the IT
post-login dashboard can render a one-time "you just reactivated"
banner that summarises the prior archive cycle and how close the
workspace came to hard-deletion:

* ``last_reactivated_at`` — stamped by the reactivate endpoint each
  time the workspace flips ``archived → active``. Drives the "show
  the banner" gate together with ``reactivation_banner_dismissed_at``.

* ``last_archive_cycle_archived_at`` — copied from ``archived_at``
  inside the same reactivate transaction (which then nulls
  ``archived_at`` itself). The banner uses this to render the
  "your workspace was archived on X" sentence after the cycle ended.

* ``reactivation_banner_dismissed_at`` — stamped by the dedicated
  dismiss endpoint. The banner is considered "pending" while
  ``last_reactivated_at IS NOT NULL AND
  (reactivation_banner_dismissed_at IS NULL OR
  reactivation_banner_dismissed_at < last_reactivated_at)`` — so a
  fresh archive→reactivate cycle re-arms the banner without needing a
  separate boolean.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e7f8a9b0c1d2"
down_revision: Union[str, Sequence[str], None] = "d6e7f8a9b0c1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "schools",
        sa.Column("last_reactivated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "schools",
        sa.Column(
            "last_archive_cycle_archived_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        "schools",
        sa.Column(
            "reactivation_banner_dismissed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("schools", "reactivation_banner_dismissed_at")
    op.drop_column("schools", "last_archive_cycle_archived_at")
    op.drop_column("schools", "last_reactivated_at")
