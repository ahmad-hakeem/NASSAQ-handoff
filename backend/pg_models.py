"""
NASSAQ PostgreSQL ORM Models
All SQLAlchemy table definitions for the NASSAQ platform.
Maps every MongoDB collection to a PostgreSQL table.
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, Integer, Float, Boolean, DateTime, Text, Enum as SAEnum,
    ForeignKey, Index, JSON, UniqueConstraint, Sequence
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB
from sqlalchemy.orm import relationship
from db import Base


def _uuid():
    return str(uuid.uuid4())


def _utcnow():
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=_uuid)
    email = Column(String, unique=True, nullable=False, index=True)
    phone = Column(String, nullable=True)
    national_id = Column(String, nullable=True)
    full_name = Column(String, nullable=False)
    full_name_en = Column(String, nullable=True)
    title = Column(String, nullable=True)
    password_hash = Column(String, nullable=False)
    must_change_password = Column(Boolean, default=True)
    last_password_change = Column(String, nullable=True)
    failed_login_attempts = Column(Integer, default=0)
    locked_until = Column(String, nullable=True)
    status = Column(String, default="active")
    is_active = Column(Boolean, default=True)
    role = Column(String, nullable=False, index=True)
    linked_roles = Column(JSONB, default=list)
    preferred_language = Column(String, default="ar")
    preferred_theme = Column(String, default="light")
    avatar_url = Column(String, nullable=True)
    tenant_id = Column(String, nullable=True, index=True)
    primary_tenant_id = Column(String, nullable=True)
    has_generic_name = Column(Boolean, default=False)
    email_verified = Column(Boolean, default=False)
    phone_verified = Column(Boolean, default=False)
    teacher_id = Column(String, nullable=True)
    student_id = Column(String, nullable=True)
    parent_id = Column(String, nullable=True)
    created_by = Column(String, nullable=True)
    last_login = Column(String, nullable=True)
    region = Column(String, nullable=True)
    city = Column(String, nullable=True)
    educational_department = Column(String, nullable=True)
    school_name_ar = Column(String, nullable=True)
    school_name_en = Column(String, nullable=True)
    permissions = Column(JSONB, default=list)
    notification_settings = Column(JSONB, nullable=True)
    created_at = Column(String, default=lambda: _utcnow().isoformat())
    updated_at = Column(String, default=lambda: _utcnow().isoformat())

    __table_args__ = (
        Index("idx_pg_users_role_tenant", "role", "tenant_id"),
        Index("idx_pg_users_tenant_active", "tenant_id", "is_active"),
    )


class School(Base):
    __tablename__ = "schools"

    id = Column(String, primary_key=True, default=_uuid)
    name = Column(String, nullable=False)
    name_en = Column(String, nullable=True)
    code = Column(String, unique=True, nullable=False, index=True)
    email = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    address = Column(String, nullable=True)
    city = Column(String, nullable=True, index=True)
    region = Column(String, nullable=True)
    district = Column(String, nullable=True)
    country = Column(String, default="SA")
    logo_url = Column(String, nullable=True)
    status = Column(String, default="pending", index=True)
    school_type = Column(String, default="public")
    stage = Column(String, nullable=True)
    gender = Column(String, nullable=True)
    language = Column(String, default="ar")
    calendar_system = Column(String, default="hijri_gregorian")
    student_capacity = Column(Integer, default=0)
    current_students = Column(Integer, default=0)
    current_teachers = Column(Integer, default=0)
    current_student_count = Column(Integer, default=0)
    current_teacher_count = Column(Integer, default=0)
    principal_id = Column(String, nullable=True)
    principal_name = Column(String, nullable=True)
    principal_email = Column(String, nullable=True)
    principal_phone = Column(String, nullable=True)
    configuration = Column(JSONB, default=dict)
    location = Column(JSONB, default=dict)
    ministry_id = Column(String, nullable=True)
    license_number = Column(String, nullable=True)
    tenant_type = Column(String, default="production")
    setup_completed = Column(Boolean, default=False)
    setup_steps_completed = Column(JSONB, default=list)
    health_score = Column(Float, nullable=True)
    last_health_check = Column(String, nullable=True)
    subscription_start = Column(String, nullable=True)
    subscription_end = Column(String, nullable=True)
    trial_end = Column(String, nullable=True)
    website = Column(String, nullable=True)
    created_by = Column(String, nullable=True)
    created_at = Column(String, default=lambda: _utcnow().isoformat())
    updated_at = Column(String, default=lambda: _utcnow().isoformat())


class Teacher(Base):
    __tablename__ = "teachers"

    id = Column(String, primary_key=True, default=_uuid)
    full_name = Column(String, nullable=False)
    full_name_en = Column(String, nullable=True)
    email = Column(String, nullable=True, index=True)
    phone = Column(String, nullable=True)
    school_id = Column(String, nullable=False, index=True)
    specialization = Column(String, nullable=True)
    rank = Column(String, nullable=True)
    subject = Column(String, nullable=True)
    qualification = Column(String, nullable=True)
    years_of_experience = Column(Integer, default=0)
    gender = Column(String, nullable=True)
    national_id = Column(String, nullable=True)
    weekly_periods = Column(Integer, nullable=True)
    max_daily_periods = Column(Integer, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(String, default=lambda: _utcnow().isoformat())
    updated_at = Column(String, default=lambda: _utcnow().isoformat())

    __table_args__ = (
        Index("idx_pg_teachers_school_active", "school_id", "is_active"),
    )


class Student(Base):
    __tablename__ = "students"

    id = Column(String, primary_key=True, default=_uuid)
    full_name = Column(String, nullable=False)
    full_name_en = Column(String, nullable=True)
    email = Column(String, nullable=True, index=True)
    phone = Column(String, nullable=True)
    school_id = Column(String, nullable=False, index=True)
    class_id = Column(String, nullable=True, index=True)
    student_number = Column(String, nullable=True)
    grade = Column(String, nullable=True)
    date_of_birth = Column(String, nullable=True)
    gender = Column(String, nullable=True)
    national_id = Column(String, nullable=True)
    parent_phone = Column(String, nullable=True)
    parent_email = Column(String, nullable=True)
    parent_name = Column(String, nullable=True)
    parent_id = Column(String, nullable=True)
    qr_code = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(String, default=lambda: _utcnow().isoformat())
    updated_at = Column(String, default=lambda: _utcnow().isoformat())

    __table_args__ = (
        Index("idx_pg_students_school_class", "school_id", "class_id"),
        Index("idx_pg_students_school_active", "school_id", "is_active"),
        Index("idx_pg_students_number_school", "student_number", "school_id"),
    )


class Parent(Base):
    __tablename__ = "parents"

    id = Column(String, primary_key=True, default=_uuid)
    full_name = Column(String, nullable=False)
    full_name_en = Column(String, nullable=True)
    email = Column(String, nullable=True, index=True)
    phone = Column(String, nullable=True)
    national_id = Column(String, nullable=True)
    student_ids = Column(JSONB, default=list)
    school_id = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(String, default=lambda: _utcnow().isoformat())
    updated_at = Column(String, default=lambda: _utcnow().isoformat())


class Class(Base):
    __tablename__ = "classes"

    id = Column(String, primary_key=True, default=_uuid)
    name = Column(String, nullable=False)
    name_en = Column(String, nullable=True)
    school_id = Column(String, nullable=False, index=True)
    grade_id = Column(String, nullable=True)
    grade_level = Column(String, nullable=True)
    section = Column(String, nullable=True)
    capacity = Column(Integer, default=30)
    current_count = Column(Integer, default=0)
    current_students = Column(Integer, default=0)
    homeroom_teacher_id = Column(String, nullable=True)
    homeroom_teacher_name = Column(String, nullable=True)
    classroom_id = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(String, default=lambda: _utcnow().isoformat())
    updated_at = Column(String, default=lambda: _utcnow().isoformat())

    __table_args__ = (
        Index("idx_pg_classes_school_active", "school_id", "is_active"),
        Index("idx_pg_classes_school_grade", "school_id", "grade_id"),
    )


class Subject(Base):
    __tablename__ = "subjects"

    id = Column(String, primary_key=True, default=_uuid)
    name = Column(String, nullable=True)
    name_ar = Column(String, nullable=True)
    name_en = Column(String, nullable=True)
    code = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    school_id = Column(String, nullable=True, index=True)
    tenant_id = Column(String, nullable=True)
    category = Column(String, default="core")
    default_periods_per_week = Column(Integer, default=4)
    applicable_stages = Column(JSONB, default=list)
    is_active = Column(Boolean, default=True)
    is_global = Column(Boolean, default=False)
    created_at = Column(String, default=lambda: _utcnow().isoformat())


class TeacherAssignment(Base):
    __tablename__ = "teacher_assignments"

    id = Column(String, primary_key=True, default=_uuid)
    school_id = Column(String, nullable=False, index=True)
    teacher_id = Column(String, nullable=False, index=True)
    class_id = Column(String, nullable=False)
    subject_id = Column(String, nullable=False)
    weekly_sessions = Column(Integer, default=4)
    periods_per_week = Column(Integer, default=4)
    academic_year = Column(String, default="2026-2027")
    semester = Column(Integer, default=1)
    priority = Column(String, default="primary")
    teacher_name = Column(String, nullable=True)
    class_name = Column(String, nullable=True)
    subject_name = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(String, default=lambda: _utcnow().isoformat())
    updated_at = Column(String, default=lambda: _utcnow().isoformat())

    __table_args__ = (
        Index("idx_pg_assigns_school_teacher", "school_id", "teacher_id"),
        Index("idx_pg_assigns_school_class", "school_id", "class_id"),
    )


class TimeSlot(Base):
    __tablename__ = "time_slots"

    id = Column(String, primary_key=True, default=_uuid)
    school_id = Column(String, nullable=False, index=True)
    name = Column(String, nullable=False)
    name_en = Column(String, nullable=True)
    start_time = Column(String, nullable=False)
    end_time = Column(String, nullable=False)
    slot_number = Column(Integer, nullable=False)
    duration_minutes = Column(Integer, default=45)
    is_break = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(String, default=lambda: _utcnow().isoformat())


class Timetable(Base):
    __tablename__ = "timetables"

    id = Column(String, primary_key=True, default=_uuid)
    school_id = Column(String, nullable=False, index=True)
    name = Column(String, nullable=False)
    name_en = Column(String, nullable=True)
    academic_year = Column(String, default="2026-2027")
    semester = Column(Integer, default=1)
    effective_from = Column(String, nullable=True)
    effective_to = Column(String, nullable=True)
    working_days = Column(JSONB, default=list)
    status = Column(String, default="draft")
    total_sessions = Column(Integer, default=0)
    version = Column(Integer, default=1)
    created_at = Column(String, default=lambda: _utcnow().isoformat())
    updated_at = Column(String, default=lambda: _utcnow().isoformat())


class TimetableRun(Base):
    __tablename__ = "timetable_runs"

    id = Column(String, primary_key=True, default=_uuid)
    school_id = Column(String, nullable=False, index=True)
    schedule_id = Column(String, nullable=True)
    status = Column(String, default="pending")
    config = Column(JSONB, default=dict)
    result = Column(JSONB, default=dict)
    sessions_created = Column(Integer, default=0)
    conflicts = Column(JSONB, default=list)
    warnings = Column(JSONB, default=list)
    error_message = Column(Text, nullable=True)
    created_at = Column(String, default=lambda: _utcnow().isoformat())
    completed_at = Column(String, nullable=True)


class ScheduleSession(Base):
    __tablename__ = "schedule_sessions"

    id = Column(String, primary_key=True, default=_uuid)
    school_id = Column(String, nullable=False, index=True)
    schedule_id = Column(String, nullable=False)
    assignment_id = Column(String, nullable=True)
    teacher_id = Column(String, nullable=True, index=True)
    class_id = Column(String, nullable=True, index=True)
    subject_id = Column(String, nullable=True)
    day_of_week = Column(String, nullable=False)
    day = Column(String, nullable=True)
    time_slot_id = Column(String, nullable=True)
    slot_number = Column(Integer, nullable=True)
    room_id = Column(String, nullable=True)
    status = Column(String, default="scheduled")
    teacher_name = Column(String, nullable=True)
    class_name = Column(String, nullable=True)
    subject_name = Column(String, nullable=True)
    time_slot_name = Column(String, nullable=True)
    start_time = Column(String, nullable=True)
    end_time = Column(String, nullable=True)
    created_at = Column(String, default=lambda: _utcnow().isoformat())

    __table_args__ = (
        Index("idx_pg_sessions_school_sched_day", "school_id", "schedule_id", "day_of_week"),
        Index("idx_pg_sessions_teacher_day", "teacher_id", "day_of_week"),
        Index("idx_pg_sessions_class_day", "class_id", "day_of_week"),
    )


class Attendance(Base):
    __tablename__ = "attendance"

    id = Column(String, primary_key=True, default=_uuid)
    school_id = Column(String, nullable=False, index=True)
    class_id = Column(String, nullable=True, index=True)
    student_id = Column(String, nullable=False, index=True)
    session_id = Column(String, nullable=True)
    date = Column(String, nullable=False)
    status = Column(String, nullable=False)
    recorded_by = Column(String, nullable=True)
    notes = Column(Text, nullable=True)
    is_excused = Column(Boolean, default=False)
    excuse_reason = Column(String, nullable=True)
    created_at = Column(String, default=lambda: _utcnow().isoformat())
    updated_at = Column(String, default=lambda: _utcnow().isoformat())

    __table_args__ = (
        Index("idx_pg_attendance_school_date", "school_id", "date"),
        Index("idx_pg_attendance_student_date", "student_id", "date"),
        Index("idx_pg_attendance_class_date", "class_id", "date"),
        Index("idx_pg_attendance_school_class_date", "school_id", "class_id", "date"),
    )


class ProductIssue(Base):
    __tablename__ = "product_issues"

    id = Column(String, primary_key=True, default=_uuid)
    issue_number = Column(Integer, unique=True, nullable=True)
    title = Column(String, nullable=True)
    type = Column(String, nullable=True)
    issue_type = Column(String, nullable=False, index=True)
    status = Column(String, default="new", index=True)
    priority = Column(String, nullable=True, index=True)
    ai_suggested_priority = Column(String, nullable=True)
    section = Column(String, nullable=True, index=True)
    page = Column(String, nullable=True)
    employee_name = Column(String, nullable=True, index=True)
    employee_id = Column(String, nullable=True)
    account_type = Column(String, nullable=True)
    current_behavior = Column(Text, nullable=True)
    expected_behavior = Column(Text, nullable=True)
    steps_to_reproduce = Column(Text, nullable=True)
    reproducibility = Column(String, nullable=True)
    error_message = Column(Text, nullable=True)
    error_code = Column(String, nullable=True)
    screen_area = Column(String, nullable=True)
    affected_elements = Column(String, nullable=True)
    user_journey = Column(Text, nullable=True)
    pain_point = Column(Text, nullable=True)
    load_time = Column(String, nullable=True)
    affected_operation = Column(String, nullable=True)
    content_location = Column(String, nullable=True)
    content_type_field = Column(String, nullable=True)
    use_case = Column(Text, nullable=True)
    business_value = Column(Text, nullable=True)
    improvement_area = Column(Text, nullable=True)
    expected_impact = Column(Text, nullable=True)
    affected_role = Column(String, nullable=True)
    expected_access = Column(String, nullable=True)
    workflow_name = Column(String, nullable=True)
    broken_step = Column(String, nullable=True)
    integration_name = Column(String, nullable=True)
    api_endpoint = Column(String, nullable=True)
    additional_details = Column(Text, nullable=True)
    url = Column(String, nullable=True)
    device = Column(String, nullable=True)
    browser = Column(String, nullable=True)
    context = Column(JSONB, default=dict)
    description = Column(JSONB, default=dict)
    impact = Column(JSONB, default=list)
    technical = Column(JSONB, default=dict)
    business = Column(JSONB, default=dict)
    assignment = Column(JSONB, default=dict)
    ai = Column(JSONB, default=dict)
    attachments = Column(JSONB, default=list)
    submission_metadata = Column(JSONB, default=dict)
    visibility = Column(JSONB, default=dict)
    system = Column(JSONB, default=dict)
    assigned_team = Column(String, nullable=True, index=True)
    assigned_to = Column(String, nullable=True)
    assigned_to_name = Column(String, nullable=True)
    assigned_at = Column(String, nullable=True)
    hakim_analysis = Column(JSONB, default=dict)
    generated_prompt = Column(Text, nullable=True)
    duplicate_of = Column(String, nullable=True)
    sla_deadline = Column(String, nullable=True)
    sla_status = Column(String, nullable=True)
    sla_warning_emitted = Column(Boolean, default=False)
    feedback_requested = Column(Boolean, default=False)
    feedback_response = Column(Text, nullable=True)
    is_deleted = Column(Boolean, default=False, index=True)
    created_by = Column(String, nullable=True, index=True)
    created_by_name = Column(String, nullable=True)
    created_by_role = Column(String, nullable=True)
    created_at = Column(String, default=lambda: _utcnow().isoformat())
    updated_at = Column(String, default=lambda: _utcnow().isoformat())
    resolved_at = Column(String, nullable=True)

    __table_args__ = (
        Index("idx_pg_issues_active_status_date", "is_deleted", "status", "created_at"),
        Index("idx_pg_issues_active_creator_date", "is_deleted", "created_by", "created_at"),
        Index("idx_pg_issues_status_priority_date", "status", "priority", "created_at"),
        Index("idx_pg_issues_status_team", "status", "assigned_team"),
        Index("idx_pg_issues_created_by_date", "created_by", "created_at"),
    )


class IssueComment(Base):
    __tablename__ = "issue_comments"

    id = Column(String, primary_key=True, default=_uuid)
    issue_id = Column(String, nullable=False, index=True)
    content = Column(Text, nullable=False)
    comment_type = Column(String, default="general")
    mentions = Column(JSONB, default=list)
    created_by = Column(String, nullable=True, index=True)
    created_by_name = Column(String, nullable=True)
    created_by_role = Column(String, nullable=True)
    timestamp = Column(String, default=lambda: _utcnow().isoformat())

    __table_args__ = (
        Index("idx_pg_comments_issue_time", "issue_id", "timestamp"),
    )


class IssueDuplicateMap(Base):
    __tablename__ = "issue_duplicates_map"

    id = Column(String, primary_key=True, default=_uuid)
    issue_id = Column(String, nullable=False, index=True)
    duplicate_of = Column(String, nullable=False, index=True)
    confidence = Column(Float, nullable=True)
    detected_by = Column(String, nullable=True)
    created_at = Column(String, default=lambda: _utcnow().isoformat())

    __table_args__ = (
        Index("idx_pg_duplicates_pair", "issue_id", "duplicate_of"),
    )


class IssueActivityLog(Base):
    __tablename__ = "issue_activity_log"

    id = Column(String, primary_key=True, default=_uuid)
    issue_id = Column(String, nullable=False, index=True)
    action = Column(String, nullable=False, index=True)
    field = Column(String, nullable=True)
    old_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)
    performed_by = Column(String, nullable=True, index=True)
    performed_by_name = Column(String, nullable=True)
    details = Column(JSONB, default=dict)
    timestamp = Column(String, default=lambda: _utcnow().isoformat(), index=True)

    __table_args__ = (
        Index("idx_pg_activity_issue_time", "issue_id", "timestamp"),
    )


class BulkActionHistory(Base):
    __tablename__ = "bulk_action_history"

    id = Column(String, primary_key=True, default=_uuid)
    action_type = Column(String, nullable=False)
    issue_ids = Column(JSONB, default=list)
    field = Column(String, nullable=True)
    old_values = Column(JSONB, default=dict)
    new_value = Column(String, nullable=True)
    performed_by = Column(String, nullable=True)
    performed_by_name = Column(String, nullable=True)
    performed_at = Column(String, default=lambda: _utcnow().isoformat(), index=True)
    is_undone = Column(Boolean, default=False)
    undone_at = Column(String, nullable=True)

    __table_args__ = (
        Index("idx_pg_bulk_history_user_date", "performed_by", "performed_at"),
    )


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(String, primary_key=True, default=_uuid)
    school_id = Column(String, nullable=True, index=True)
    tenant_id = Column(String, nullable=True)
    action = Column(String, nullable=False, index=True)
    entity_type = Column(String, nullable=True)
    entity_id = Column(String, nullable=True)
    performed_by = Column(String, nullable=True, index=True)
    actor_name = Column(String, nullable=True)
    actor_role = Column(String, nullable=True)
    target_id = Column(String, nullable=True)
    target_type = Column(String, nullable=True)
    previous_state = Column(JSONB, nullable=True)
    new_state = Column(JSONB, nullable=True)
    details = Column(JSONB, nullable=True)
    ip_address = Column(String, nullable=True)
    user_agent = Column(String, nullable=True)
    severity = Column(String, default="info")
    timestamp = Column(String, default=lambda: _utcnow().isoformat(), index=True)

    __table_args__ = (
        Index("idx_pg_audit_school_time", "school_id", "timestamp"),
        Index("idx_pg_audit_entity", "entity_type", "entity_id"),
        Index("idx_pg_audit_user_time", "performed_by", "timestamp"),
    )


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, nullable=False, index=True)
    tenant_id = Column(String, nullable=True, index=True)
    title = Column(String, nullable=True)
    title_en = Column(String, nullable=True)
    message = Column(Text, nullable=True)
    message_en = Column(Text, nullable=True)
    type = Column(String, nullable=True)
    priority = Column(String, default="normal")
    is_read = Column(Boolean, default=False)
    is_seen = Column(Boolean, default=False)
    link = Column(String, nullable=True)
    extra_data = Column("metadata", JSONB, nullable=True)
    created_at = Column(String, default=lambda: _utcnow().isoformat(), index=True)

    __table_args__ = (
        Index("idx_pg_notif_user_read_date", "user_id", "is_read", "created_at"),
        Index("idx_pg_notif_tenant_date", "tenant_id", "created_at"),
    )


class Message(Base):
    __tablename__ = "messages"

    id = Column(String, primary_key=True, default=_uuid)
    school_id = Column(String, nullable=True, index=True)
    tenant_id = Column(String, nullable=True)
    sender_id = Column(String, nullable=True)
    sender_name = Column(String, nullable=True)
    recipient_ids = Column(JSONB, default=list)
    recipient_type = Column(String, nullable=True)
    subject = Column(String, nullable=True)
    body = Column(Text, nullable=True)
    channel = Column(String, default="internal")
    status = Column(String, default="sent")
    is_read = Column(Boolean, default=False)
    scheduled_at = Column(String, nullable=True)
    sent_at = Column(String, nullable=True)
    extra_data = Column("metadata", JSONB, nullable=True)
    created_at = Column(String, default=lambda: _utcnow().isoformat())
    updated_at = Column(String, default=lambda: _utcnow().isoformat())


class RegistrationRequest(Base):
    __tablename__ = "registration_requests"

    id = Column(String, primary_key=True, default=_uuid)
    full_name = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    account_type = Column(String, nullable=True)
    email = Column(String, nullable=True)
    national_id = Column(String, nullable=True)
    school_name = Column(String, nullable=True)
    school_name_en = Column(String, nullable=True)
    school_email = Column(String, nullable=True)
    school_phone = Column(String, nullable=True)
    school_city = Column(String, nullable=True)
    school_address = Column(String, nullable=True)
    student_capacity = Column(String, nullable=True)
    school_code = Column(String, nullable=True)
    school_type = Column(String, nullable=True)
    education_level = Column(String, nullable=True)
    region = Column(String, nullable=True)
    city = Column(String, nullable=True)
    address = Column(String, nullable=True)
    postal_code = Column(String, nullable=True)
    principal_name = Column(String, nullable=True)
    principal_email = Column(String, nullable=True)
    principal_phone = Column(String, nullable=True)
    education_license_number = Column(String, nullable=True)
    commercial_registration = Column(String, nullable=True)
    student_count = Column(Integer, default=0)
    teacher_count = Column(Integer, default=0)
    specialization = Column(String, nullable=True)
    subject = Column(String, nullable=True)
    educational_level = Column(String, nullable=True)
    school_mentioned = Column(String, nullable=True)
    country = Column(String, nullable=True)
    years_of_experience = Column(String, nullable=True)
    status = Column(String, default="pending", index=True)
    rejection_reason = Column(Text, nullable=True)
    additional_info_request = Column(Text, nullable=True)
    additional_info = Column(Text, nullable=True)
    assigned_to = Column(String, nullable=True)
    reviewed_by = Column(String, nullable=True)
    reviewed_at = Column(String, nullable=True)
    review_note = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(String, default=lambda: _utcnow().isoformat(), index=True)
    updated_at = Column(String, default=lambda: _utcnow().isoformat())

    __table_args__ = (
        Index("idx_pg_requests_status_date", "status", "created_at"),
    )


class BehaviourRecord(Base):
    __tablename__ = "behaviour_records"

    id = Column(String, primary_key=True, default=_uuid)
    school_id = Column(String, nullable=False, index=True)
    tenant_id = Column(String, nullable=True)
    student_id = Column(String, nullable=False, index=True)
    class_id = Column(String, nullable=True)
    behaviour_type_id = Column(String, nullable=True)
    category = Column(String, nullable=True)
    severity = Column(String, nullable=True)
    points = Column(Integer, default=0)
    description = Column(Text, nullable=True)
    action_taken = Column(Text, nullable=True)
    status = Column(String, default="pending")
    recorded_by = Column(String, nullable=True)
    recorded_by_name = Column(String, nullable=True)
    reviewed_by = Column(String, nullable=True)
    parent_notified = Column(Boolean, default=False)
    created_at = Column(String, default=lambda: _utcnow().isoformat(), index=True)
    updated_at = Column(String, default=lambda: _utcnow().isoformat())

    __table_args__ = (
        Index("idx_pg_behaviour_school_student", "school_id", "student_id"),
        Index("idx_pg_behaviour_school_date", "school_id", "created_at"),
    )


class Assessment(Base):
    __tablename__ = "assessments"

    id = Column(String, primary_key=True, default=_uuid)
    school_id = Column(String, nullable=False, index=True)
    tenant_id = Column(String, nullable=True)
    class_id = Column(String, nullable=True, index=True)
    subject_id = Column(String, nullable=True)
    teacher_id = Column(String, nullable=True, index=True)
    title = Column(String, nullable=True)
    type = Column(String, nullable=True)
    max_score = Column(Float, default=100)
    weight = Column(Float, default=1.0)
    date = Column(String, nullable=True)
    term = Column(String, nullable=True)
    academic_year = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    status = Column(String, default="draft")
    created_at = Column(String, default=lambda: _utcnow().isoformat())
    updated_at = Column(String, default=lambda: _utcnow().isoformat())

    __table_args__ = (
        Index("idx_pg_assessments_school_class", "school_id", "class_id"),
    )


class AssessmentSubmission(Base):
    __tablename__ = "assessment_submissions"

    id = Column(String, primary_key=True, default=_uuid)
    assessment_id = Column(String, nullable=False, index=True)
    student_id = Column(String, nullable=False, index=True)
    score = Column(Float, nullable=True)
    grade = Column(String, nullable=True)
    feedback = Column(Text, nullable=True)
    submitted_at = Column(String, nullable=True)
    graded_by = Column(String, nullable=True)
    graded_at = Column(String, nullable=True)
    created_at = Column(String, default=lambda: _utcnow().isoformat())

    __table_args__ = (
        Index("idx_pg_submissions_assessment_student", "assessment_id", "student_id"),
    )


class SchoolSetting(Base):
    __tablename__ = "school_settings"

    id = Column(String, primary_key=True, default=_uuid)
    school_id = Column(String, unique=True, nullable=False, index=True)
    settings = Column(JSONB, default=dict)
    working_days = Column(JSONB, default=list)
    periods_per_day = Column(Integer, default=7)
    academic_year = Column(String, nullable=True)
    semester = Column(Integer, nullable=True)
    created_at = Column(String, default=lambda: _utcnow().isoformat())
    updated_at = Column(String, default=lambda: _utcnow().isoformat())


class HakimInsight(Base):
    __tablename__ = "hakim_insights"

    id = Column(String, primary_key=True, default=_uuid)
    school_id = Column(String, nullable=True, index=True)
    tenant_id = Column(String, nullable=True)
    type = Column(String, nullable=True)
    category = Column(String, nullable=True)
    title = Column(String, nullable=True)
    title_en = Column(String, nullable=True)
    content = Column(Text, nullable=True)
    content_en = Column(Text, nullable=True)
    severity = Column(String, nullable=True)
    score = Column(Float, nullable=True)
    recommendations = Column(JSONB, default=list)
    data = Column(JSONB, default=dict)
    status = Column(String, default="active")
    created_at = Column(String, default=lambda: _utcnow().isoformat(), index=True)


class TeacherSession(Base):
    __tablename__ = "teacher_sessions"

    id = Column(String, primary_key=True, default=_uuid)
    school_id = Column(String, nullable=False, index=True)
    teacher_id = Column(String, nullable=False, index=True)
    class_id = Column(String, nullable=True, index=True)
    subject_id = Column(String, nullable=True)
    session_date = Column(String, nullable=True, index=True)
    slot_number = Column(Integer, nullable=True)
    status = Column(String, default="pending")
    topic = Column(String, nullable=True)
    notes = Column(Text, nullable=True)
    attendance_taken = Column(Boolean, default=False)
    objectives = Column(JSONB, default=list)
    materials = Column(JSONB, default=list)
    started_at = Column(String, nullable=True)
    ended_at = Column(String, nullable=True)
    created_at = Column(String, default=lambda: _utcnow().isoformat())
    updated_at = Column(String, default=lambda: _utcnow().isoformat())

    __table_args__ = (
        Index("idx_pg_tsessions_school_date", "school_id", "session_date"),
        Index("idx_pg_tsessions_teacher_date", "teacher_id", "session_date"),
        Index("idx_pg_tsessions_class_date", "class_id", "session_date"),
    )


class PlatformSetting(Base):
    __tablename__ = "platform_settings"

    id = Column(String, primary_key=True, default=_uuid)
    type = Column(String, unique=True, nullable=False, index=True)
    value = Column(JSONB, default=dict)
    created_at = Column(String, default=lambda: _utcnow().isoformat())
    updated_at = Column(String, default=lambda: _utcnow().isoformat())


class AcademicYear(Base):
    __tablename__ = "academic_years"

    id = Column(String, primary_key=True, default=_uuid)
    school_id = Column(String, nullable=False, index=True)
    name = Column(String, nullable=True)
    start_date = Column(String, nullable=True)
    end_date = Column(String, nullable=True)
    is_current = Column(Boolean, default=False)
    created_at = Column(String, default=lambda: _utcnow().isoformat())


class AcademicTerm(Base):
    __tablename__ = "academic_terms"

    id = Column(String, primary_key=True, default=_uuid)
    school_id = Column(String, nullable=False, index=True)
    academic_year_id = Column(String, nullable=True)
    name = Column(String, nullable=True)
    term_number = Column(Integer, nullable=True)
    start_date = Column(String, nullable=True)
    end_date = Column(String, nullable=True)
    is_current = Column(Boolean, default=False)
    created_at = Column(String, default=lambda: _utcnow().isoformat())


class SkillType(Base):
    __tablename__ = "skills_types"

    id = Column(String, primary_key=True, default=_uuid)
    name = Column(String, nullable=True)
    name_en = Column(String, nullable=True)
    category = Column(String, nullable=True, index=True)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(String, default=lambda: _utcnow().isoformat())


class StudentSkill(Base):
    __tablename__ = "student_skills"

    id = Column(String, primary_key=True, default=_uuid)
    student_id = Column(String, nullable=False, index=True)
    skill_type_id = Column(String, nullable=True, index=True)
    session_id = Column(String, nullable=True, index=True)
    class_id = Column(String, nullable=True, index=True)
    school_id = Column(String, nullable=True)
    score = Column(Float, nullable=True)
    level = Column(String, nullable=True)
    notes = Column(Text, nullable=True)
    assessed_by = Column(String, nullable=True)
    timestamp = Column(String, default=lambda: _utcnow().isoformat(), index=True)


class SessionInteraction(Base):
    __tablename__ = "session_interactions"

    id = Column(String, primary_key=True, default=_uuid)
    session_id = Column(String, nullable=False, index=True)
    student_id = Column(String, nullable=True, index=True)
    interaction_type = Column(String, nullable=True, index=True)
    details = Column(JSONB, default=dict)
    score = Column(Float, nullable=True)
    timestamp = Column(String, default=lambda: _utcnow().isoformat())


class AIInsight(Base):
    __tablename__ = "ai_insights"

    id = Column(String, primary_key=True, default=_uuid)
    school_id = Column(String, nullable=True, index=True)
    entity_id = Column(String, nullable=True, index=True)
    type = Column(String, nullable=True, index=True)
    category = Column(String, nullable=True)
    title = Column(String, nullable=True)
    content = Column(Text, nullable=True)
    severity = Column(String, nullable=True)
    score = Column(Float, nullable=True)
    data = Column(JSONB, default=dict)
    recommendations = Column(JSONB, default=list)
    status = Column(String, default="active")
    created_at = Column(String, default=lambda: _utcnow().isoformat(), index=True)

    __table_args__ = (
        Index("idx_pg_ai_insights_school_type", "school_id", "type"),
        Index("idx_pg_ai_insights_entity_type", "entity_id", "type"),
    )


class AIIntervention(Base):
    __tablename__ = "ai_interventions"

    id = Column(String, primary_key=True, default=_uuid)
    school_id = Column(String, nullable=True, index=True)
    student_id = Column(String, nullable=True, index=True)
    type = Column(String, nullable=True)
    title = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    status = Column(String, default="pending", index=True)
    priority = Column(String, nullable=True)
    assigned_to = Column(String, nullable=True)
    outcome = Column(Text, nullable=True)
    data = Column(JSONB, default=dict)
    created_at = Column(String, default=lambda: _utcnow().isoformat(), index=True)
    updated_at = Column(String, default=lambda: _utcnow().isoformat())

    __table_args__ = (
        Index("idx_pg_interventions_school_status", "school_id", "status"),
        Index("idx_pg_interventions_student_status", "student_id", "status"),
    )


class SessionNote(Base):
    __tablename__ = "session_notes"

    id = Column(String, primary_key=True, default=_uuid)
    session_id = Column(String, nullable=False, index=True)
    teacher_id = Column(String, nullable=True, index=True)
    student_id = Column(String, nullable=True, index=True)
    content = Column(Text, nullable=True)
    type = Column(String, nullable=True)
    is_private = Column(Boolean, default=False)
    created_at = Column(String, default=lambda: _utcnow().isoformat())


class SessionEventLog(Base):
    __tablename__ = "session_event_log"

    id = Column(String, primary_key=True, default=_uuid)
    session_id = Column(String, nullable=False, index=True)
    event_type = Column(String, nullable=True, index=True)
    details = Column(JSONB, default=dict)
    performed_by = Column(String, nullable=True)
    timestamp = Column(String, default=lambda: _utcnow().isoformat(), index=True)

    __table_args__ = (
        Index("idx_pg_session_events_session_time", "session_id", "timestamp"),
    )


class TeacherClassAssignment(Base):
    __tablename__ = "teacher_class_assignments"

    id = Column(String, primary_key=True, default=_uuid)
    school_id = Column(String, nullable=False)
    teacher_id = Column(String, nullable=False)
    class_id = Column(String, nullable=False)
    is_homeroom = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(String, default=lambda: _utcnow().isoformat())

    __table_args__ = (
        UniqueConstraint("school_id", "teacher_id", "class_id", name="uq_tca_school_teacher_class"),
    )


class UserRelationship(Base):
    __tablename__ = "user_relationships"

    id = Column(String, primary_key=True, default=_uuid)
    relationship_type = Column(String, nullable=False)
    user_id_1 = Column(String, nullable=False, index=True)
    user_id_2 = Column(String, nullable=False, index=True)
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    detected_automatically = Column(Boolean, default=False)
    detection_method = Column(String, nullable=True)
    detection_confidence = Column(Float, nullable=True)
    created_at = Column(String, default=lambda: _utcnow().isoformat())
    created_by = Column(String, nullable=True)
    verified_by = Column(String, nullable=True)
    verified_at = Column(String, nullable=True)


class GuardianLink(Base):
    __tablename__ = "guardian_links"

    id = Column(String, primary_key=True, default=_uuid)
    parent_ref = Column(String, nullable=False, index=True)
    student_id = Column(String, nullable=False, index=True)
    relationship = Column(String, default="parent")
    is_active = Column(Boolean, default=True)
    created_at = Column(String, default=lambda: _utcnow().isoformat())


class Grade(Base):
    __tablename__ = "grades"

    id = Column(String, primary_key=True, default=_uuid)
    tenant_id = Column(String, nullable=True, index=True)
    school_id = Column(String, nullable=True)
    stage = Column(String, nullable=True)
    grade_number = Column(Integer, nullable=True)
    name_ar = Column(String, nullable=True)
    name_en = Column(String, nullable=True)
    display_order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(String, default=lambda: _utcnow().isoformat())


class EducationalStage(Base):
    __tablename__ = "educational_stages"

    id = Column(String, primary_key=True, default=_uuid)
    name_ar = Column(String, nullable=True)
    name_en = Column(String, nullable=True)
    code = Column(String, nullable=True)
    order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)


class PhysicalClassroom(Base):
    __tablename__ = "physical_classrooms"

    id = Column(String, primary_key=True, default=_uuid)
    tenant_id = Column(String, nullable=True)
    name = Column(String, nullable=True)
    building = Column(String, nullable=True)
    floor = Column(Integer, nullable=True)
    room_type = Column(String, default="classroom")
    capacity = Column(Integer, default=30)
    has_projector = Column(Boolean, default=False)
    has_smartboard = Column(Boolean, default=False)
    has_ac = Column(Boolean, default=True)
    is_available = Column(Boolean, default=True)
    notes = Column(Text, nullable=True)
    created_at = Column(String, default=lambda: _utcnow().isoformat())


class BehaviourType(Base):
    __tablename__ = "behaviour_types"

    id = Column(String, primary_key=True, default=_uuid)
    tenant_id = Column(String, nullable=True)
    name_ar = Column(String, nullable=True)
    name_en = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    category = Column(String, nullable=True)
    default_severity = Column(String, nullable=True)
    default_points = Column(Integer, default=0)
    auto_escalate = Column(Boolean, default=False)
    escalation_threshold = Column(Integer, nullable=True)
    is_active = Column(Boolean, default=True)
    is_global = Column(Boolean, default=False)
    created_at = Column(String, default=lambda: _utcnow().isoformat())


class TimetableConstraint(Base):
    __tablename__ = "timetable_constraints"

    id = Column(String, primary_key=True, default=_uuid)
    school_id = Column(String, nullable=True)
    type = Column(String, nullable=False)
    category = Column(String, default="hard")
    name = Column(String, nullable=True)
    name_en = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    config = Column(JSONB, default=dict)
    is_active = Column(Boolean, default=True)
    is_global = Column(Boolean, default=True)
    created_at = Column(String, default=lambda: _utcnow().isoformat())


class ApprovalRequest(Base):
    __tablename__ = "approval_requests"

    id = Column(String, primary_key=True, default=_uuid)
    type = Column(String, nullable=False)
    entity_id = Column(String, nullable=True)
    entity_type = Column(String, nullable=True)
    status = Column(String, default="pending")
    requested_by = Column(String, nullable=True)
    requested_by_name = Column(String, nullable=True)
    school_id = Column(String, nullable=True)
    data = Column(JSONB, default=dict)
    result = Column(JSONB, nullable=True)
    reviewed_by = Column(String, nullable=True)
    reviewed_at = Column(String, nullable=True)
    review_note = Column(Text, nullable=True)
    created_at = Column(String, default=lambda: _utcnow().isoformat())
    updated_at = Column(String, default=lambda: _utcnow().isoformat())


issue_number_seq = Sequence("issue_number_seq", start=1, increment=1)
