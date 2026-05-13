"""IT analytics dashboard — covering indexes for time-series aggregation (Task #273).

Revision ID: h2i3j4k5l6m7
Revises: a4b5c6d7e8f9, f9a0b1c2d3e4
Create Date: 2026-05-13

Merges the two outstanding heads (`a4b5c6d7e8f9`, `f9a0b1c2d3e4`) and
adds a covering index on ``behaviour_records (school_id, created_at)``
backing the IT analytics dashboard's weekly behaviour-by-category
roll-up. ``attendance (school_id, date)`` already exists as
``idx_pg_attendance_school_date``; ``lesson_plans
(workspace_school_id, created_at)`` already exists as
``ix_lesson_plans_ws_created``. Only the missing one is created here.
"""
from typing import Sequence, Union

from alembic import op


revision: str = "h2i3j4k5l6m7"
down_revision: Union[str, Sequence[str], None] = ("a4b5c6d7e8f9", "f9a0b1c2d3e4")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_behaviour_records_school_created_at "
        "ON behaviour_records (school_id, created_at)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_behaviour_records_school_created_at")
