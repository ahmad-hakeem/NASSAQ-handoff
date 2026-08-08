"""Add teachers.teacher_id and teachers.qr_code for fresh-database parity

Fresh-database resilience (same pattern as teachers.user_id in
c9d5e3f7a2b1): every long-lived environment already has
``teachers.teacher_id`` and ``teachers.qr_code`` (they predate migration
coverage), but NO migration creates them — so a clean ``alembic upgrade
head`` on an empty database makes every ORM SELECT/INSERT against
``teachers`` fail with UndefinedColumn (e.g. the teacher auto-link lookup
in ``backend/dependencies.py``). Create them idempotently here, matching
the ORM shape (pg_models.Teacher.teacher_id: VARCHAR, nullable, indexed;
pg_models.Teacher.qr_code: TEXT, nullable). These two are the ONLY
ORM-declared columns missing from a fresh ``alembic upgrade head`` schema
(verified by diffing pg_models metadata against a freshly migrated
database). On existing databases all statements are no-ops.

Revision ID: d4f8a1c6e9b2
Revises: bt1seed2glob3
Create Date: 2026-07-25
"""
import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "d4f8a1c6e9b2"
down_revision = "bt1seed2glob3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text("ALTER TABLE teachers ADD COLUMN IF NOT EXISTS teacher_id VARCHAR")
    )
    conn.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS ix_teachers_teacher_id "
            "ON teachers (teacher_id)"
        )
    )
    conn.execute(
        sa.text("ALTER TABLE teachers ADD COLUMN IF NOT EXISTS qr_code TEXT")
    )


def downgrade() -> None:
    # Intentionally a no-op: long-lived environments had this column before
    # migration coverage existed, so dropping it on downgrade would destroy
    # pre-existing data the migration never created.
    pass
