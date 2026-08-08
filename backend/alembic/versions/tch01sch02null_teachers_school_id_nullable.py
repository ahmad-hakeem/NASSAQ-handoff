"""Relax teachers.school_id to NULLABLE so fresh installs match the ORM.

`teachers.school_id` was declared NOT NULL in the initial schema, but the ORM
model (`pg_models.Teacher`) declares it nullable and the long-lived dev/prod
databases have it nullable — someone dropped the constraint out of band and no
migration recorded it. Fresh installs therefore behaved differently from every
existing environment.

Nullable is the correct target, not NOT NULL: an unassigned teacher is a
first-class state in the product. The platform dashboard publishes a count of
teachers with no school, so tightening the column would break a supported flow
rather than fix one.

The concrete symptom was that approving a School Teacher registration request
raised NotNullViolationError on any freshly-migrated database while passing on
dev/prod. The approval path now always links a school, but the schema drift is
fixed here so the two stop disagreeing.

Revision ID: tch01sch02null
Revises: cm01idx02sess
Create Date: 2026-08-03
"""
from alembic import op

# revision identifiers, used by Alembic.
revision = 'tch01sch02null'
down_revision = 'cm01idx02sess'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # No-op on databases that already drifted to nullable.
    op.execute("ALTER TABLE teachers ALTER COLUMN school_id DROP NOT NULL")


def downgrade() -> None:
    # Only restore NOT NULL when the data actually allows it; unassigned
    # teachers are legitimate, so a blind re-tighten would fail.
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM teachers WHERE school_id IS NULL) THEN
                ALTER TABLE teachers ALTER COLUMN school_id SET NOT NULL;
            END IF;
        END $$;
        """
    )
