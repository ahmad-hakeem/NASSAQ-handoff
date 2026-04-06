"""migrate string timestamps to datetime

Revision ID: c8d9e0f1a2b3
Revises: b7e52689a1ad
Create Date: 2026-04-05
"""
from alembic import op
import sqlalchemy as sa

revision = "c8d9e0f1a2b3"
down_revision = "b7e52689a1ad"
branch_labels = None
depends_on = None

COLUMNS_TO_MIGRATE = [
    ("users", "last_password_change"),
    ("users", "locked_until"),
    ("users", "last_login"),
    ("users", "created_at"),
    ("users", "updated_at"),
    ("schools", "last_health_check"),
    ("schools", "subscription_start"),
    ("schools", "subscription_end"),
    ("schools", "trial_end"),
    ("schools", "created_at"),
    ("schools", "updated_at"),
    ("teachers", "created_at"),
    ("teachers", "updated_at"),
    ("students", "created_at"),
    ("students", "updated_at"),
    ("parents", "created_at"),
    ("parents", "updated_at"),
    ("classes", "created_at"),
    ("classes", "updated_at"),
    ("subjects", "created_at"),
    ("teacher_assignments", "created_at"),
    ("time_slots", "created_at"),
    ("timetables", "created_at"),
    ("timetables", "updated_at"),
    ("timetable_runs", "created_at"),
    ("timetable_runs", "completed_at"),
    ("schedule_sessions", "created_at"),
    ("attendance", "date"),
    ("attendance", "created_at"),
    ("product_issues", "assigned_at"),
    ("product_issues", "sla_deadline"),
    ("product_issues", "created_at"),
    ("product_issues", "updated_at"),
    ("product_issues", "resolved_at"),
    ("bulk_action_history", "performed_at"),
    ("bulk_action_history", "undone_at"),
    ("audit_logs", "timestamp"),
    ("school_settings", "created_at"),
    ("school_settings", "updated_at"),
    ("notifications", "read_at"),
    ("notifications", "created_at"),
    ("assessments", "due_date"),
    ("assessments", "created_at"),
    ("assessments", "updated_at"),
    ("assessment_submissions", "submitted_at"),
    ("assessment_submissions", "graded_at"),
    ("assessment_submissions", "created_at"),
    ("assessment_submissions", "updated_at"),
    ("behaviour_records", "date"),
    ("behaviour_records", "created_at"),
    ("behaviour_records", "updated_at"),
    ("registration_requests", "reviewed_at"),
    ("registration_requests", "created_at"),
    ("registration_requests", "updated_at"),
    ("teacher_sessions", "date"),
    ("teacher_sessions", "created_at"),
    ("teacher_sessions", "updated_at"),
    ("hakim_insights", "created_at"),
    ("platform_settings", "updated_at"),
    ("academic_years", "start_date"),
    ("academic_years", "end_date"),
    ("academic_years", "created_at"),
    ("academic_years", "updated_at"),
    ("academic_terms", "start_date"),
    ("academic_terms", "end_date"),
    ("academic_terms", "created_at"),
    ("academic_terms", "updated_at"),
    ("lookup_options", "created_at"),
    ("messages", "created_at"),
    ("messages", "read_at"),
    ("session_interactions", "timestamp"),
    ("ai_insights", "created_at"),
    ("ai_interventions", "created_at"),
    ("ai_interventions", "updated_at"),
    ("session_notes", "created_at"),
]

COLUMNS_TO_ADD = [
    ("subjects", "updated_at"),
    ("session_notes", "updated_at"),
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
    RAISE WARNING 'Malformed timestamp value "%" in migration, setting to NULL', val;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql IMMUTABLE;
"""

_DROP_SAFE_CAST_FN = "DROP FUNCTION IF EXISTS _safe_iso_to_timestamptz(TEXT);"


def _column_exists(conn, table, column):
    result = conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_schema='public' AND table_name=:t AND column_name=:c"
        ),
        {"t": table, "c": column}
    )
    return result.scalar() is not None


def _column_is_varchar(conn, table, column):
    result = conn.execute(
        sa.text(
            "SELECT data_type FROM information_schema.columns "
            "WHERE table_schema='public' AND table_name=:t AND column_name=:c"
        ),
        {"t": table, "c": column}
    )
    row = result.fetchone()
    return row is not None and row[0] == "character varying"


def upgrade():
    conn = op.get_bind()
    op.execute(sa.text(_SAFE_CAST_FN))

    for table, column in COLUMNS_TO_MIGRATE:
        if _column_exists(conn, table, column) and _column_is_varchar(conn, table, column):
            op.execute(
                sa.text(
                    f'ALTER TABLE "{table}" ALTER COLUMN "{column}" '
                    f'TYPE TIMESTAMPTZ USING _safe_iso_to_timestamptz("{column}")'
                )
            )

    for table, column in COLUMNS_TO_ADD:
        if not _column_exists(conn, table, column):
            op.add_column(table, sa.Column(column, sa.DateTime(timezone=True), nullable=True))

    op.execute(sa.text(_DROP_SAFE_CAST_FN))


def downgrade():
    conn = op.get_bind()
    for table, column in COLUMNS_TO_ADD:
        if _column_exists(conn, table, column):
            op.drop_column(table, column)
    for table, column in COLUMNS_TO_MIGRATE:
        if _column_exists(conn, table, column):
            op.execute(
                sa.text(
                    f'ALTER TABLE "{table}" ALTER COLUMN "{column}" '
                    f"TYPE VARCHAR USING "
                    f'CASE WHEN "{column}" IS NOT NULL '
                    f"THEN \"{column}\"::text ELSE NULL END"
                )
            )
