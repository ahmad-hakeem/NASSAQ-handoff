"""IT Phase 2 — workspace erasure (GDPR right-to-be-forgotten) columns (Task #276)

Revision ID: g1h2i3j4k5l6
Revises: f1a2b3c4d5e7
Create Date: 2026-05-13

Adds two columns on ``schools`` so the IT account-erasure flow has a
durable per-row state:

* ``erasure_requested_at`` — stamped by the
  ``POST /independent-teacher/workspace/request-erasure`` endpoint at
  the moment the IT user confirms the GDPR-style erasure request.
  Once non-NULL the workspace is in the erasure grace period; the
  reactivate endpoint 410s and the daily sweep purges the row once
  the configured window has elapsed.

* ``erasure_window_days`` — copies the configured grace window (env
  ``WORKSPACE_ERASURE_WINDOW_DAYS``, default 7) at request time so
  changing the env later does not retroactively shorten an open
  erasure request.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "erw1x2y3z4a5"
down_revision: Union[str, Sequence[str], None] = (
    "a4b5c6d7e8f9",
    "f9a0b1c2d3e4",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "schools",
        sa.Column(
            "erasure_requested_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        "schools",
        sa.Column(
            "erasure_window_days",
            sa.SmallInteger(),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("schools", "erasure_window_days")
    op.drop_column("schools", "erasure_requested_at")
