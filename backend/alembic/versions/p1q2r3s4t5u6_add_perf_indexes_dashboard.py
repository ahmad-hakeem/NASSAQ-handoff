"""add performance indexes for admin dashboard counts

Revision ID: p1q2r3s4t5u6
Revises: o1p2q3r4s5t6
Create Date: 2026-04-20

Targets the slow COUNT(*) queries observed in production logs from
/api/admin/command-center/stats and related dashboard endpoints. Each
count was 500-800ms; with these indexes most should drop to <50ms.

Tolerant of missing tables (different deployments may not have all of
them) by checking pg_class before each CREATE INDEX.
"""
import logging
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text


revision: str = "p1q2r3s4t5u6"
down_revision: Union[str, Sequence[str], None] = "o1p2q3r4s5t6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

log = logging.getLogger("alembic.runtime.migration")

# (index_name, table, ddl_columns_clause)
INDEXES = [
    ("idx_users_role", "users", "(role)"),
    ("idx_users_role_tenant", "users", "(role, tenant_id)"),
    ("idx_users_last_login", "users", "(last_login)"),
    ("idx_teachers_school_id", "teachers", "(school_id)"),
    ("idx_teachers_created_at", "teachers", "(created_at)"),
    ("idx_students_created_at", "students", "(created_at)"),
    ("idx_attendance_date", "attendance", "(date)"),
    ("idx_attendance_status_date", "attendance", "(status, date)"),
    ("idx_attendance_school_date", "attendance", "(school_id, date)"),
    ("idx_schools_status", "schools", "(status)"),
    ("idx_notifications_created_at", "notifications", "(created_at)"),
    ("idx_behaviour_records_date", "behaviour_records", "(date)"),
    ("idx_class_sessions_date", "class_sessions", "(date)"),
    ("idx_class_sessions_date_status", "class_sessions", "(date, status)"),
    ("idx_gd_collection_school", "generic_documents",
     "(collection, ((data->>'school_id')))"),
    ("idx_gd_collection_date", "generic_documents",
     "(collection, ((data->>'date')))"),
    # Hot path for active class sessions count: collection + date + status
    ("idx_gd_collection_date_status", "generic_documents",
     "(collection, ((data->>'date')), ((data->>'status')))"),
    # Split from a composite (type, created_at) index because some deploy
    # validators mis-infer text_ops for the timestamp column in expression
    # indexes that mix a JSON text expression with a timestamptz column.
    ("idx_events_type", "events", "(((data->>'type')))"),
    ("idx_events_created_at", "events", "(created_at)"),
    ("idx_events_status_created_at", "events", "(status, created_at)"),
]


def _table_exists(bind, table: str) -> bool:
    return bool(bind.execute(
        text("SELECT to_regclass(:t)"), {"t": f"public.{table}"}
    ).scalar())


# Indexes that earlier revisions of this migration created but that we no
# longer want. Drop them so dev/prod schemas converge and deploy validators
# don't try to re-create the bad definition.
LEGACY_INDEXES_TO_DROP = [
    "idx_events_type_created_at",
]


def upgrade() -> None:
    # CREATE INDEX CONCURRENTLY cannot run inside a transaction, so each
    # statement is wrapped in its own autocommit block. This avoids
    # blocking writes on busy production tables during the migration.
    bind = op.get_bind()
    for name in LEGACY_INDEXES_TO_DROP:
        with op.get_context().autocommit_block():
            try:
                op.execute(f"DROP INDEX CONCURRENTLY IF EXISTS {name}")
            except Exception as e:  # noqa: BLE001
                log.warning("legacy drop %s skipped: %s", name, e)
    for name, table, cols in INDEXES:
        if not _table_exists(bind, table):
            log.info("skip index %s: table %s missing", name, table)
            continue
        with op.get_context().autocommit_block():
            try:
                op.execute(
                    f"CREATE INDEX CONCURRENTLY IF NOT EXISTS {name} ON {table} {cols}"
                )
            except Exception as e:  # noqa: BLE001
                # Don't block deploy on a single index failure (e.g. JSON path
                # column missing, or an INVALID leftover from a prior aborted
                # CONCURRENTLY attempt). Operator can drop+retry manually.
                log.warning("index %s on %s skipped: %s", name, table, e)


def downgrade() -> None:
    for name, _table, _cols in reversed(INDEXES):
        with op.get_context().autocommit_block():
            try:
                op.execute(f"DROP INDEX CONCURRENTLY IF EXISTS {name}")
            except Exception as e:  # noqa: BLE001
                log.warning("drop index %s skipped: %s", name, e)
