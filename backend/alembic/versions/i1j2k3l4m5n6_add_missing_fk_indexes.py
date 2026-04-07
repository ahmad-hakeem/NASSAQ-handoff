"""add missing FK indexes for performance

Revision ID: i1j2k3l4m5n6
Revises: h1i2j3k4l5m6
Create Date: 2026-04-07
"""
from typing import Sequence, Union

from alembic import op

revision: str = 'i1j2k3l4m5n6'
down_revision: Union[str, Sequence[str], None] = 'h1i2j3k4l5m6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

INDEXES = [
    ("ix_behaviour_types_tenant_id", "behaviour_types", ["tenant_id"]),
    ("ix_physical_classrooms_tenant_id", "physical_classrooms", ["tenant_id"]),
    ("ix_approval_requests_requested_by", "approval_requests", ["requested_by"]),
    ("ix_approval_requests_reviewed_by", "approval_requests", ["reviewed_by"]),
    ("ix_classes_homeroom_teacher_id", "classes", ["homeroom_teacher_id"]),
    ("ix_platform_settings_updated_by", "platform_settings", ["updated_by"]),
    ("ix_product_issues_duplicate_of", "product_issues", ["duplicate_of"]),
    ("ix_registration_requests_reviewed_by", "registration_requests", ["reviewed_by"]),
    ("ix_session_event_log_performed_by", "session_event_log", ["performed_by"]),
    ("ix_approval_events_performed_by", "approval_events", ["performed_by"]),
    ("ix_assessments_subject_id", "assessments", ["subject_id"]),
    ("ix_teacher_assignments_subject_id", "teacher_assignments", ["subject_id"]),
    ("ix_teacher_sessions_subject_id", "teacher_sessions", ["subject_id"]),
    ("ix_ai_interventions_approved_by", "ai_interventions", ["approved_by"]),
    ("ix_ai_interventions_created_by", "ai_interventions", ["created_by"]),
    ("ix_assessment_submissions_graded_by", "assessment_submissions", ["graded_by"]),
    ("ix_attendance_recorded_by", "attendance", ["recorded_by"]),
    ("ix_behaviour_records_class_id", "behaviour_records", ["class_id"]),
    ("ix_behaviour_records_created_by", "behaviour_records", ["created_by"]),
    ("ix_behaviour_records_teacher_id", "behaviour_records", ["teacher_id"]),
    ("ix_schedule_sessions_assignment_id", "schedule_sessions", ["assignment_id"]),
    ("ix_schedule_sessions_subject_id", "schedule_sessions", ["subject_id"]),
    ("ix_schedule_sessions_time_slot_id", "schedule_sessions", ["time_slot_id"]),
    ("ix_session_interactions_recorded_by", "session_interactions", ["recorded_by"]),
    ("ix_student_skills_assessed_by", "student_skills", ["assessed_by"]),
    ("ix_events_recorded_by", "events", ["recorded_by"]),
    ("ix_system_settings_updated_by", "system_settings", ["updated_by"]),
]


def upgrade() -> None:
    for name, table, columns in INDEXES:
        op.create_index(name, table, columns, if_not_exists=True)


def downgrade() -> None:
    for name, table, _ in reversed(INDEXES):
        op.drop_index(name, table_name=table, if_exists=True)
