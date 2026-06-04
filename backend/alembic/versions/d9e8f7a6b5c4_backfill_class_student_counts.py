"""Backfill drifted classes.current_students (Task #829)

Revision ID: d9e8f7a6b5c4
Revises: c8d7e6f5a4b3
Create Date: 2026-06-04

One-off, NON-DESTRUCTIVE data migration. The denormalized
``classes.current_students`` column drifted away from the real roster because
it was only nudged by scattered ``±1`` increments in the student
create/delete/transfer routes and was never recomputed. The application now
*reconciles* (recomputes) this column on every such write via
``engines.entity_counts.reconcile_class_counts``; this migration performs the
one-time backfill so existing rows are correct immediately rather than only
after the next write.

The predicate below MUST stay byte-for-byte identical to the canonical one in
``engines.entity_counts._class_student_active_predicate`` (and the class
list / detail readers in ``academics_class_routes.py``), or the stored column
will disagree with the live counts the class pages show:

  * Students — ``is_active = true`` (active students assigned to the class).
    This is intentionally stricter than the school-level student predicate
    (``is_active <> false``): the class readers exclude ``NULL`` rows too.

``upgrade()`` runs only a single UPDATE statement (no DDL, no drops/deletes),
so it is non-destructive and idempotent. ``downgrade()`` is intentionally a
no-op: the column is a derived aggregate, so there is nothing meaningful to
restore.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d9e8f7a6b5c4"
down_revision: Union[str, Sequence[str], None] = "c8d7e6f5a4b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    conn.execute(
        sa.text(
            """
            UPDATE classes c
            SET current_students = COALESCE((
                SELECT count(*)
                FROM students st
                WHERE st.class_id = c.id
                  AND st.school_id = c.school_id
                  AND st.is_active = true
            ), 0)
            """
        )
    )


def downgrade() -> None:
    # Derived aggregate — nothing meaningful to roll back to.
    pass
