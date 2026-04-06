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


def upgrade() -> None:
    op.create_index("ix_parents_school_id", "parents", ["school_id"], unique=False)
    op.create_index("ix_registration_requests_school_id", "registration_requests", ["school_id"], unique=False)
    op.create_index("idx_pg_requests_school_status", "registration_requests", ["school_id", "status"], unique=False)
    op.create_index("ix_lookup_options_school_id", "lookup_options", ["school_id"], unique=False)
    op.create_index("idx_pg_lookup_school", "lookup_options", ["school_id", "category"], unique=False)
    op.create_index("ix_messages_school_id", "messages", ["school_id"], unique=False)
    op.create_index("ix_student_skills_school_id", "student_skills", ["school_id"], unique=False)
    op.create_index("ix_teacher_class_assignments_school_id", "teacher_class_assignments", ["school_id"], unique=False)
    op.create_index("ix_teacher_class_assignments_teacher_id", "teacher_class_assignments", ["teacher_id"], unique=False)
    op.create_index("ix_teacher_class_assignments_class_id", "teacher_class_assignments", ["class_id"], unique=False)
    op.create_index("ix_grade_levels_school_id", "grade_levels", ["school_id"], unique=False)
    op.create_index("ix_timetable_constraints_school_id", "timetable_constraints", ["school_id"], unique=False)
    op.create_index("ix_approval_requests_school_id", "approval_requests", ["school_id"], unique=False)
    op.create_index("ix_students_grade", "students", ["grade"], unique=False)
    op.create_index("ix_schedule_sessions_day_of_week", "schedule_sessions", ["day_of_week"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_schedule_sessions_day_of_week", table_name="schedule_sessions")
    op.drop_index("ix_students_grade", table_name="students")
    op.drop_index("ix_approval_requests_school_id", table_name="approval_requests")
    op.drop_index("ix_timetable_constraints_school_id", table_name="timetable_constraints")
    op.drop_index("ix_grade_levels_school_id", table_name="grade_levels")
    op.drop_index("ix_teacher_class_assignments_class_id", table_name="teacher_class_assignments")
    op.drop_index("ix_teacher_class_assignments_teacher_id", table_name="teacher_class_assignments")
    op.drop_index("ix_teacher_class_assignments_school_id", table_name="teacher_class_assignments")
    op.drop_index("ix_student_skills_school_id", table_name="student_skills")
    op.drop_index("ix_messages_school_id", table_name="messages")
    op.drop_index("idx_pg_lookup_school", table_name="lookup_options")
    op.drop_index("ix_lookup_options_school_id", table_name="lookup_options")
    op.drop_index("idx_pg_requests_school_status", table_name="registration_requests")
    op.drop_index("ix_registration_requests_school_id", table_name="registration_requests")
    op.drop_index("ix_parents_school_id", table_name="parents")
