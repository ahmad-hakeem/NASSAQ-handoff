"""add missing indexes for performance

Revision ID: g1h2i3j4k5l6
Revises: a1b2c3d4e5f6
Create Date: 2026-04-06
"""
revision = "g1h2i3j4k5l6"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None

from alembic import op
from sqlalchemy import inspect


INDEXES = [
    ("ix_parents_school_id", "parents", ["school_id"]),
    ("ix_registration_requests_school_id", "registration_requests", ["school_id"]),
    ("idx_pg_requests_school_status", "registration_requests", ["school_id", "status"]),
    ("ix_lookup_options_school_id", "lookup_options", ["school_id"]),
    ("idx_pg_lookup_school", "lookup_options", ["school_id", "category"]),
    ("ix_messages_school_id", "messages", ["school_id"]),
    ("ix_student_skills_school_id", "student_skills", ["school_id"]),
    ("ix_teacher_class_assignments_school_id", "teacher_class_assignments", ["school_id"]),
    ("ix_teacher_class_assignments_teacher_id", "teacher_class_assignments", ["teacher_id"]),
    ("ix_teacher_class_assignments_class_id", "teacher_class_assignments", ["class_id"]),
    ("ix_grade_levels_school_id", "grade_levels", ["school_id"]),
    ("ix_timetable_constraints_school_id", "timetable_constraints", ["school_id"]),
    ("ix_approval_requests_school_id", "approval_requests", ["school_id"]),
    ("ix_students_grade", "students", ["grade"]),
    ("ix_schedule_sessions_day_of_week", "schedule_sessions", ["day_of_week"]),
]


def _existing(inspector, table):
    """Return the set of index names already present on a table (empty if the
    table does not exist)."""
    if not inspector.has_table(table):
        return set()
    return {ix["name"] for ix in inspector.get_indexes(table)}


def upgrade() -> None:
    inspector = inspect(op.get_bind())
    cache = {}
    for name, table, columns in INDEXES:
        if table not in cache:
            cache[table] = _existing(inspector, table)
        if not inspector.has_table(table):
            continue
        if name in cache[table]:
            continue
        op.create_index(name, table, columns, unique=False)
        cache[table].add(name)


def downgrade() -> None:
    inspector = inspect(op.get_bind())
    for name, table, _columns in reversed(INDEXES):
        if not inspector.has_table(table):
            continue
        if name in _existing(inspector, table):
            op.drop_index(name, table_name=table)
