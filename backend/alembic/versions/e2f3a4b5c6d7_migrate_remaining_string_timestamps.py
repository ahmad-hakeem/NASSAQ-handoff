"""migrate remaining string timestamps to datetime

Revision ID: e2f3a4b5c6d7
Revises: d1e2f3a4b5c6
Create Date: 2026-04-05
"""
from alembic import op
import sqlalchemy as sa

revision = "e2f3a4b5c6d7"
down_revision = "d1e2f3a4b5c6"
branch_labels = None
depends_on = None

COLUMNS_TO_MIGRATE = [
    ("approval_events", "timestamp"),
    ("approval_requests", "created_at"),
    ("approval_requests", "reviewed_at"),
    ("approval_requests", "updated_at"),
    ("attendance", "updated_at"),
    ("behaviour_types", "created_at"),
    ("generic_documents", "created_at"),
    ("issue_activity_log", "timestamp"),
    ("issue_comments", "timestamp"),
    ("issue_duplicates_map", "created_at"),
    ("physical_classrooms", "created_at"),
    ("platform_settings", "created_at"),
    ("session_event_log", "timestamp"),
    ("skills_types", "created_at"),
    ("student_skills", "created_at"),
    ("student_skills", "date"),
    ("teacher_assignments", "updated_at"),
    ("teacher_class_assignments", "created_at"),
    ("timetable_constraints", "created_at"),
]

_SAFE_CAST_FN = """
CREATE OR REPLACE FUNCTION _safe_iso_to_timestamptz(val TEXT)
RETURNS TIMESTAMPTZ AS $$
BEGIN
    IF val IS NULL OR val = '' THEN
        RETURN NULL;
    END IF;
    RETURN val::timestamptz;
EXCEPTION WHEN OTHERS THEN
    RETURN NULL;
END;
$$ LANGUAGE plpgsql IMMUTABLE;
"""

_DROP_SAFE_CAST_FN = "DROP FUNCTION IF EXISTS _safe_iso_to_timestamptz(TEXT);"


def upgrade():
    op.execute(sa.text(_SAFE_CAST_FN))
    for table, column in COLUMNS_TO_MIGRATE:
        op.execute(
            sa.text(
                f'ALTER TABLE "{table}" ALTER COLUMN "{column}" '
                f'TYPE TIMESTAMPTZ USING _safe_iso_to_timestamptz("{column}")'
            )
        )
    op.execute(sa.text(_DROP_SAFE_CAST_FN))


def downgrade():
    for table, column in COLUMNS_TO_MIGRATE:
        op.execute(
            sa.text(
                f'ALTER TABLE "{table}" ALTER COLUMN "{column}" '
                f"TYPE VARCHAR USING "
                f'CASE WHEN "{column}" IS NOT NULL '
                f"THEN \"{column}\"::text ELSE NULL END"
            )
        )
