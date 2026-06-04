"""Backfill drifted schools.current_students / current_teachers (Task #826)

Revision ID: c8d7e6f5a4b3
Revises: c9d5e3f7a2b1
Create Date: 2026-06-04

One-off, NON-DESTRUCTIVE data migration. The denormalized
``schools.current_students`` / ``schools.current_teachers`` columns drifted
away from the real row counts because they were only nudged by scattered
``±1`` increments in the student/teacher create/delete/restore routes and were
never recomputed. The application now *reconciles* (recomputes) these columns
on every such write via ``engines.entity_counts.reconcile_school_counts``; this
migration performs the one-time backfill so existing rows are correct
immediately rather than only after the next write.

The predicates below MUST stay byte-for-byte identical to the canonical ones in
``engines.entity_counts`` (and the in-school ``GET /students`` / ``GET
/teachers`` endpoints), or the stored columns will disagree with the live
counts the platform list shows:

  * Students — ``is_active <> false`` (excludes both FALSE and NULL rows).
  * Teachers — ``NOT (is_active = false AND deleted_at IS NOT NULL)`` (keeps
    everything except soft-deleted rows).

``upgrade()`` runs only UPDATE statements (no DDL, no drops/deletes), so it is
non-destructive and idempotent. ``downgrade()`` is intentionally a no-op: the
columns are derived aggregates, so there is nothing meaningful to restore.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c8d7e6f5a4b3"
down_revision: Union[str, Sequence[str], None] = "c9d5e3f7a2b1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    conn.execute(
        sa.text(
            """
            UPDATE schools s
            SET current_students = COALESCE((
                SELECT count(*)
                FROM students st
                WHERE st.school_id = s.id
                  AND st.is_active <> false
            ), 0)
            """
        )
    )

    conn.execute(
        sa.text(
            """
            UPDATE schools s
            SET current_teachers = COALESCE((
                SELECT count(*)
                FROM teachers t
                WHERE t.school_id = s.id
                  AND NOT (t.is_active = false AND t.deleted_at IS NOT NULL)
            ), 0)
            """
        )
    )


def downgrade() -> None:
    # Derived aggregates — nothing meaningful to roll back to.
    pass
