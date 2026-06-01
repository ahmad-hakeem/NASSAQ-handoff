"""IT Phase 1 — students.pending_parent_* columns + clear-on-link trigger

Revision ID: z1a2b3c4d5e6
Revises: y1z2a3b4c5d6
Create Date: 2026-05-12

Adds three nullable text columns to ``students`` to hold the pre-link parent
contact strings captured inline by an Independent Teacher (IT) at student-
create time:

    * ``pending_parent_name``
    * ``pending_parent_phone``
    * ``pending_parent_email``

Per spec §5.6 ("Canonical parent-contact ownership (frozen)") these columns
are the single canonical source for parent contact while a student is in the
**Pending** state — i.e. before any ``parents`` row exists for them. They
are never read by the parent portal and never treated as a verified
identity.

Also installs a back-compat ``BEFORE UPDATE`` trigger
``students_clear_pending_parent_on_link_trg`` that, on any UPDATE where
``parent_id`` transitions from NULL to a non-NULL value, clears the three
pending columns in the same row write. This guarantees stale pending
contact strings can never linger after an Invite Parent action links the
student to a real ``parents`` row, even if a future code path forgets to
null them explicitly. The trigger is a no-op when ``parent_id`` is
unchanged or being cleared (NEW.parent_id NULL → NULL or non-NULL → *).

Postgres requires a trigger to invoke a function; the function body is
deliberately a tiny three-assignment block so the behaviour is trivially
inspectable in ``pg_proc`` / ``pg_trigger`` and the migration is cleanly
reversible. The WHEN clause carries the actual condition so the function
itself is a no-op stub doing only the column clears.

This revision is Alembic-only — no business logic, no Pydantic, no route
changes. Existing ``students`` rows in real schools are unaffected (NULL
columns, no row rewrites).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from migration_idempotent import has_column


revision: str = "z1a2b3c4d5e6"
down_revision: Union[str, Sequence[str], None] = "y1z2a3b4c5d6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if not has_column("students", "pending_parent_name"):
        op.add_column(
            "students",
            sa.Column("pending_parent_name", sa.Text(), nullable=True),
        )
    if not has_column("students", "pending_parent_phone"):
        op.add_column(
            "students",
            sa.Column("pending_parent_phone", sa.Text(), nullable=True),
        )
    if not has_column("students", "pending_parent_email"):
        op.add_column(
            "students",
            sa.Column("pending_parent_email", sa.Text(), nullable=True),
        )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION students_clear_pending_parent_on_link_fn()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
          NEW.pending_parent_name  := NULL;
          NEW.pending_parent_phone := NULL;
          NEW.pending_parent_email := NULL;
          RETURN NEW;
        END;
        $$;
        """
    )

    op.execute(
        "DROP TRIGGER IF EXISTS students_clear_pending_parent_on_link_trg ON students;"
    )
    op.execute(
        """
        CREATE TRIGGER students_clear_pending_parent_on_link_trg
        BEFORE UPDATE ON students
        FOR EACH ROW
        WHEN (OLD.parent_id IS NULL AND NEW.parent_id IS NOT NULL)
        EXECUTE FUNCTION students_clear_pending_parent_on_link_fn();
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS students_clear_pending_parent_on_link_trg ON students;"
    )
    op.execute(
        "DROP FUNCTION IF EXISTS students_clear_pending_parent_on_link_fn();"
    )
    op.drop_column("students", "pending_parent_email")
    op.drop_column("students", "pending_parent_phone")
    op.drop_column("students", "pending_parent_name")
