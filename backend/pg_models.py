"""
NASSAQ PostgreSQL ORM Models
All SQLAlchemy table definitions for the NASSAQ platform.

Lazy Loading Strategy:
  - "selectin": Used for parent/single-object FK references (e.g., Student.school,
    Class.homeroom_teacher). Batched IN-clause loading avoids N+1 queries.
  - "noload": Used for large one-to-many collections (e.g., School.teachers,
    User.audit_logs, ProductIssue.comments). These are never accessed via ORM
    relationship traversal — all data access goes through the repository layer which
    queries tables directly. Prevents accidental fan-out of thousands of rows.
    If a future consumer needs these, use explicit selectinload() at query time.
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, Integer, SmallInteger, Float, Boolean, Date, DateTime, Text,
    Enum as SAEnum, ForeignKey, Index, JSON, LargeBinary, UniqueConstraint,
    Sequence, text
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
    phone = Column(String, nullable=True, index=True)
    national_id = Column(String, nullable=True, index=True)
    full_name = Column(String, nullable=False)
    full_name_en = Column(String, nullable=True)
    title = Column(String, nullable=True)
    password_hash = Column(String, nullable=False)
    must_change_password = Column(Boolean, default=True)
    last_password_change = Column(DateTime(timezone=True), nullable=True)
    reset_token_hash = Column(String, nullable=True)
    reset_token_created_at = Column(DateTime(timezone=True), nullable=True)
    failed_login_attempts = Column(Integer, default=0)
    locked_until = Column(DateTime(timezone=True), nullable=True)
    status = Column(String, default="active")
    is_active = Column(Boolean, default=True)
    role = Column(String, nullable=False, index=True)
    linked_roles = Column(JSONB, default=list)
    preferred_language = Column(String, default="ar")
    preferred_theme = Column(String, default="light")
    avatar_url = Column(String, nullable=True)
    tenant_id = Column(String, ForeignKey("schools.id", ondelete="SET NULL"), nullable=True, index=True)
    primary_tenant_id = Column(String, nullable=True)
    has_generic_name = Column(Boolean, default=False)
    email_verified = Column(Boolean, default=False)
    phone_verified = Column(Boolean, default=False)
    teacher_id = Column(String, nullable=True)
    student_id = Column(String, nullable=True)
    parent_id = Column(String, nullable=True)
    created_by = Column(String, nullable=True)
    last_login = Column(DateTime(timezone=True), nullable=True)
    region = Column(String, nullable=True)
    city = Column(String, nullable=True)
    educational_department = Column(String, nullable=True)
    school_name_ar = Column(String, nullable=True)
    school_name_en = Column(String, nullable=True)
    permissions = Column(JSONB, default=list)
    notification_settings = Column(JSONB, nullable=True)

    # MFA (Task #169) — denormalised flags read by the policy helper and
    # the recovery-code lifecycle. ``mfa_required`` is a cache of
    # ``mfa_policy.required_for(user) is not None`` for fast filtering;
    # ``mfa_policy`` remains the source of truth at request time.
    mfa_required = Column(Boolean, nullable=False, default=False)
    mfa_enrolled_at = Column(DateTime(timezone=True), nullable=True)
    # Set true when a recovery code is consumed; cleared by a successful
    # passkey/TOTP re-enrolment. Read by ``require_recent_mfa`` to refuse
    # Tier A sensitive routes with MFA_RESTORE_REQUIRED while true.
    mfa_must_restore_factor = Column(Boolean, nullable=False, default=False)
    mfa_recovery_codes_generated_at = Column(DateTime(timezone=True), nullable=True)
    # Flips true once the user has clicked the "I have saved my recovery
    # codes in a safe place" checkbox in the forced presentation modal.
    mfa_recovery_codes_acknowledged = Column(Boolean, nullable=False, default=False)

    # Task #250 — IT first-login onboarding tour. NULL means "show the
    # welcome card next time this user lands on their IT dashboard";
    # non-IT roles always carry NULL here (the trigger surfaces are
    # IT-only).
    it_onboarding_completed_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), default=_utcnow)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    tenant = relationship("School", foreign_keys=[tenant_id], lazy="selectin")
    audit_logs = relationship("AuditLog", back_populates="user", foreign_keys="AuditLog.performed_by", lazy="noload")
    notifications = relationship("Notification", back_populates="user", foreign_keys="Notification.user_id", lazy="noload")

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
    principal_id = Column(String, nullable=True)
    principal_name = Column(String, nullable=True)
    principal_email = Column(String, nullable=True)
    principal_phone = Column(String, nullable=True)
    principal_mobile = Column(String, nullable=True)
    educational_pathway = Column(String, nullable=True)
    configuration = Column(JSONB, default=dict)
    location = Column(JSONB, default=dict)
    ministry_id = Column(String, nullable=True)
    license_number = Column(String, nullable=True)
    tenant_type = Column(String, default="production")
    setup_completed = Column(Boolean, default=False)
    setup_steps_completed = Column(JSONB, default=list)
    health_score = Column(Float, nullable=True)
    last_health_check = Column(DateTime(timezone=True), nullable=True)
    subscription_start = Column(DateTime(timezone=True), nullable=True)
    subscription_end = Column(DateTime(timezone=True), nullable=True)
    trial_end = Column(DateTime(timezone=True), nullable=True)
    website = Column(String, nullable=True)
    created_by = Column(String, nullable=True)
    archived_at = Column(DateTime(timezone=True), nullable=True, index=True)
    pending_hard_delete = Column(Boolean, nullable=False, server_default=text("false"), index=True)
    last_export_at = Column(DateTime(timezone=True), nullable=True)
    # IT §6.8 single-use export token state.
    last_export_token_hash = Column(String, nullable=True)
    last_export_consumed_at = Column(DateTime(timezone=True), nullable=True)
    # IT §6.8 reactivation reminder + banner state.
    reactivation_reminder_sent_at = Column(DateTime(timezone=True), nullable=True)
    last_reactivated_at = Column(DateTime(timezone=True), nullable=True)
    last_archive_cycle_archived_at = Column(DateTime(timezone=True), nullable=True)
    reactivation_banner_dismissed_at = Column(DateTime(timezone=True), nullable=True)
    # Task #276 — IT account-erasure (GDPR) state. ``erasure_requested_at``
    # is stamped at request time; the daily sweep purges the workspace
    # once ``erasure_window_days`` has elapsed. Reactivation 410s while
    # ``erasure_requested_at IS NOT NULL``.
    erasure_requested_at = Column(DateTime(timezone=True), nullable=True)
    erasure_window_days = Column(SmallInteger, nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    teachers = relationship("Teacher", back_populates="school", lazy="noload")
    students = relationship("Student", back_populates="school", lazy="noload")
    classes = relationship("Class", back_populates="school", lazy="noload")
    subjects = relationship("Subject", back_populates="school", lazy="noload")
    settings = relationship("SchoolSettings", back_populates="school", lazy="selectin")


class Teacher(Base):
    __tablename__ = "teachers"

    id = Column(String, primary_key=True, default=_uuid)
    full_name = Column(String, nullable=False)
    full_name_en = Column(String, nullable=True)
    email = Column(String, nullable=True, index=True)
    phone = Column(String, nullable=True)
    school_id = Column(String, ForeignKey("schools.id", ondelete="CASCADE"), nullable=True, index=True)
    specialization = Column(String, nullable=True)
    rank = Column(String, nullable=True)
    subject = Column(String, nullable=True)
    qualification = Column(String, nullable=True)
    years_of_experience = Column(Integer, default=0)
    gender = Column(String, nullable=True)
    national_id = Column(String, nullable=True, index=True)
    weekly_periods = Column(Integer, nullable=True)
    max_daily_periods = Column(Integer, nullable=True)
    preferences = Column(JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))
    constraints = Column(JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))
    user_id = Column(String, nullable=True, index=True)
    teacher_id = Column(String, nullable=True, index=True)
    qr_code = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    school = relationship("School", back_populates="teachers", lazy="selectin")
    assignments = relationship("TeacherAssignment", back_populates="teacher", lazy="selectin")

    __table_args__ = (
        Index("idx_pg_teachers_school_active", "school_id", "is_active"),
        UniqueConstraint("national_id", "school_id", name="uq_teachers_national_id_school"),
    )


class Student(Base):
    __tablename__ = "students"

    id = Column(String, primary_key=True, default=_uuid)
    full_name = Column(String, nullable=False)
    full_name_en = Column(String, nullable=True)
    email = Column(String, nullable=True, index=True)
    phone = Column(String, nullable=True)
    school_id = Column(String, ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True)
    class_id = Column(String, ForeignKey("classes.id", ondelete="SET NULL"), nullable=True, index=True)
    student_number = Column(String, nullable=True)
    grade = Column(String, nullable=True, index=True)
    date_of_birth = Column(String, nullable=True)
    gender = Column(String, nullable=True)
    national_id = Column(String, nullable=True, index=True)
    parent_phone = Column(String, nullable=True)
    parent_email = Column(String, nullable=True)
    parent_name = Column(String, nullable=True)
    parent_id = Column(String, ForeignKey("parents.id", ondelete="SET NULL"), nullable=True, index=True)
    pending_parent_name = Column(Text, nullable=True)
    pending_parent_phone = Column(String, nullable=True)
    pending_parent_email = Column(String, nullable=True)
    qr_code = Column(Text, nullable=True)
    talents = Column(JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb"))
    character_traits = Column(JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb"))
    is_gifted = Column(Boolean, nullable=False, default=False, server_default=text("false"))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    school = relationship("School", back_populates="students", lazy="selectin")
    class_ = relationship("Class", back_populates="students", foreign_keys=[class_id], lazy="selectin")
    parent = relationship("Parent", back_populates="students", foreign_keys=[parent_id], lazy="selectin")
    attendance_records = relationship("Attendance", back_populates="student", lazy="noload")

    __table_args__ = (
        Index("idx_pg_students_school_class", "school_id", "class_id"),
        Index("idx_pg_students_school_active", "school_id", "is_active"),
        Index("idx_pg_students_number_school", "student_number", "school_id"),
        UniqueConstraint("student_number", "school_id", name="uq_students_number_school"),
        UniqueConstraint("national_id", "school_id", name="uq_students_national_id_school"),
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
    school_id = Column(String, ForeignKey("schools.id", ondelete="SET NULL"), nullable=True, index=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    students = relationship("Student", back_populates="parent", foreign_keys="Student.parent_id", lazy="noload")


class Class(Base):
    __tablename__ = "classes"

    id = Column(String, primary_key=True, default=_uuid)
    name = Column(String, nullable=False)
    name_en = Column(String, nullable=True)
    school_id = Column(String, ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True)
    grade_id = Column(String, nullable=True)
    grade_level = Column(String, nullable=True)
    section = Column(String, nullable=True)
    capacity = Column(Integer, default=30)
    current_students = Column(Integer, default=0)
    homeroom_teacher_id = Column(String, ForeignKey("teachers.id", ondelete="SET NULL"), nullable=True)
    homeroom_teacher_name = Column(String, nullable=True)
    classroom_id = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    school = relationship("School", back_populates="classes", lazy="selectin")
    homeroom_teacher = relationship("Teacher", foreign_keys=[homeroom_teacher_id], lazy="selectin")
    students = relationship("Student", back_populates="class_", foreign_keys="Student.class_id", lazy="noload")

    __table_args__ = (
        Index("idx_pg_classes_school_active", "school_id", "is_active"),
        Index("idx_pg_classes_school_grade", "school_id", "grade_id"),
    )


class Subject(Base):
    __tablename__ = "subjects"

    id = Column(String, primary_key=True, default=_uuid)
    name = Column(String, nullable=False)
    name_ar = Column(String, nullable=True)
    name_en = Column(String, nullable=True)
    code = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    school_id = Column(String, ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True)
    category = Column(String, default="core")
    default_periods_per_week = Column(Integer, default=4)
    applicable_stages = Column(JSONB, default=list)
    is_active = Column(Boolean, default=True)
    is_global = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=_utcnow)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    school = relationship("School", back_populates="subjects", lazy="selectin")


class TeacherAssignment(Base):
    __tablename__ = "teacher_assignments"

    id = Column(String, primary_key=True, default=_uuid)
    school_id = Column(String, ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True)
    teacher_id = Column(String, ForeignKey("teachers.id", ondelete="CASCADE"), nullable=False, index=True)
    class_id = Column(String, ForeignKey("classes.id", ondelete="CASCADE"), nullable=True)
    subject_id = Column(String, ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False)
    weekly_sessions = Column(Integer, default=4)
    periods_per_week = Column(Integer, default=4)
    academic_year = Column(String, default="2026-2027")
    semester = Column(Integer, default=1)
    priority = Column(String, default="primary")
    teacher_name = Column(String, nullable=True)
    class_name = Column(String, nullable=True)
    subject_name = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    teacher = relationship("Teacher", back_populates="assignments", lazy="selectin")
    school_rel = relationship("School", lazy="selectin")
    class_rel = relationship("Class", lazy="selectin")
    subject_rel = relationship("Subject", lazy="selectin")

    __table_args__ = (
        Index("idx_pg_assigns_school_teacher", "school_id", "teacher_id"),
        Index("idx_pg_assigns_school_class", "school_id", "class_id"),
    )


class TimeSlot(Base):
    __tablename__ = "time_slots"

    id = Column(String, primary_key=True, default=_uuid)
    school_id = Column(String, ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String, nullable=False)
    name_en = Column(String, nullable=True)
    start_time = Column(String, nullable=False)
    end_time = Column(String, nullable=False)
    slot_number = Column(Integer, nullable=False)
    duration_minutes = Column(Integer, default=45)
    is_break = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow)


class Timetable(Base):
    __tablename__ = "timetables"

    id = Column(String, primary_key=True, default=_uuid)
    school_id = Column(String, ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True)
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
    created_at = Column(DateTime(timezone=True), default=_utcnow)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)


class TimetableRun(Base):
    __tablename__ = "timetable_runs"

    id = Column(String, primary_key=True, default=_uuid)
    school_id = Column(String, ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True)
    schedule_id = Column(String, nullable=True)
    status = Column(String, default="pending")
    config = Column(JSONB, default=dict)
    result = Column(JSONB, default=dict)
    sessions_created = Column(Integer, default=0)
    conflicts = Column(JSONB, default=list)
    warnings = Column(JSONB, default=list)
    generation_summary = Column(JSONB, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow)
    completed_at = Column(DateTime(timezone=True), nullable=True)


class ScheduleSession(Base):
    __tablename__ = "schedule_sessions"

    id = Column(String, primary_key=True, default=_uuid)
    school_id = Column(String, ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True)
    schedule_id = Column(String, nullable=False, index=True)
    assignment_id = Column(String, ForeignKey("teacher_assignments.id", ondelete="SET NULL"), nullable=True)
    teacher_id = Column(String, ForeignKey("teachers.id", ondelete="SET NULL"), nullable=True, index=True)
    class_id = Column(String, ForeignKey("classes.id", ondelete="SET NULL"), nullable=True, index=True)
    subject_id = Column(String, ForeignKey("subjects.id", ondelete="SET NULL"), nullable=True)
    day_of_week = Column(String, nullable=False, index=True)
    day = Column(String, nullable=True)
    time_slot_id = Column(String, ForeignKey("time_slots.id", ondelete="SET NULL"), nullable=True)
    slot_number = Column(Integer, nullable=True)
    room_id = Column(String, nullable=True)
    status = Column(String, default="scheduled")
    teacher_name = Column(String, nullable=True)
    class_name = Column(String, nullable=True)
    subject_name = Column(String, nullable=True)
    time_slot_name = Column(String, nullable=True)
    start_time = Column(String, nullable=True)
    end_time = Column(String, nullable=True)
    version = Column(Integer, nullable=False, server_default=text("1"))
    created_at = Column(DateTime(timezone=True), default=_utcnow)

    teacher = relationship("Teacher", foreign_keys=[teacher_id], lazy="selectin")
    class_ = relationship("Class", foreign_keys=[class_id], lazy="selectin")
    subject = relationship("Subject", foreign_keys=[subject_id], lazy="selectin")
    time_slot = relationship("TimeSlot", foreign_keys=[time_slot_id], lazy="selectin")

    __table_args__ = (
        Index("idx_pg_sessions_school_sched_day", "school_id", "schedule_id", "day_of_week"),
        Index("idx_pg_sessions_teacher_day", "teacher_id", "day_of_week"),
        Index("idx_pg_sessions_class_day", "class_id", "day_of_week"),
    )


class Attendance(Base):
    __tablename__ = "attendance"

    id = Column(String, primary_key=True, default=_uuid)
    school_id = Column(String, ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True)
    class_id = Column(String, ForeignKey("classes.id", ondelete="SET NULL"), nullable=True, index=True)
    student_id = Column(String, ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)
    session_id = Column(String, nullable=True, index=True)
    date = Column(DateTime(timezone=True), nullable=False)
    status = Column(String, nullable=False)
    recorded_by = Column(String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    notes = Column(Text, nullable=True)
    is_excused = Column(Boolean, default=False)
    excuse_reason = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    student = relationship("Student", back_populates="attendance_records", lazy="selectin")

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
    assigned_at = Column(DateTime(timezone=True), nullable=True)
    hakim_analysis = Column(JSONB, default=dict)
    generated_prompt = Column(Text, nullable=True)
    duplicate_of = Column(String, ForeignKey("product_issues.id", ondelete="SET NULL"), nullable=True)
    sla_deadline = Column(DateTime(timezone=True), nullable=True)
    sla_status = Column(String, nullable=True)
    sla_warning_emitted = Column(Boolean, default=False)
    feedback_requested = Column(Boolean, default=False)
    feedback_response = Column(Text, nullable=True)
    is_deleted = Column(Boolean, default=False, index=True)
    created_by = Column(String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    created_by_name = Column(String, nullable=True)
    created_by_role = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)
    resolved_at = Column(DateTime(timezone=True), nullable=True)

    creator = relationship("User", foreign_keys=[created_by], lazy="selectin")
    duplicate_source = relationship("ProductIssue", remote_side="ProductIssue.id", foreign_keys=[duplicate_of], lazy="noload")
    comments = relationship("IssueComment", back_populates="issue", lazy="noload")
    activity_logs = relationship("IssueActivityLog", back_populates="issue", lazy="noload")

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
    issue_id = Column(String, ForeignKey("product_issues.id", ondelete="CASCADE"), nullable=False, index=True)
    content = Column(Text, nullable=False)
    comment_type = Column(String, default="general")
    mentions = Column(JSONB, default=list)
    created_by = Column(String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    created_by_name = Column(String, nullable=True)
    created_by_role = Column(String, nullable=True)
    timestamp = Column(DateTime(timezone=True), default=_utcnow)

    issue = relationship("ProductIssue", back_populates="comments", lazy="selectin")
    author = relationship("User", foreign_keys=[created_by], lazy="selectin")

    __table_args__ = (
        Index("idx_pg_comments_issue_time", "issue_id", "timestamp"),
    )


class IssueDuplicateMap(Base):
    __tablename__ = "issue_duplicates_map"

    id = Column(String, primary_key=True, default=_uuid)
    issue_id = Column(String, ForeignKey("product_issues.id", ondelete="CASCADE"), nullable=False, index=True)
    duplicate_of = Column(String, ForeignKey("product_issues.id", ondelete="CASCADE"), nullable=False, index=True)
    confidence = Column(Float, nullable=True)
    detected_by = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        Index("idx_pg_duplicates_pair", "issue_id", "duplicate_of"),
    )


class IssueActivityLog(Base):
    __tablename__ = "issue_activity_log"

    id = Column(String, primary_key=True, default=_uuid)
    issue_id = Column(String, ForeignKey("product_issues.id", ondelete="CASCADE"), nullable=False, index=True)
    action = Column(String, nullable=False, index=True)
    field = Column(String, nullable=True)
    old_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)
    performed_by = Column(String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    performed_by_name = Column(String, nullable=True)
    details = Column(JSONB, default=dict)
    timestamp = Column(DateTime(timezone=True), default=_utcnow, index=True)

    issue = relationship("ProductIssue", back_populates="activity_logs", lazy="selectin")

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
    performed_by = Column(String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    performed_by_name = Column(String, nullable=True)
    performed_at = Column(DateTime(timezone=True), default=_utcnow, index=True)
    is_undone = Column(Boolean, default=False)
    undone_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("idx_pg_bulk_history_user_date", "performed_by", "performed_at"),
    )


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(String, primary_key=True, default=_uuid)
    school_id = Column(String, ForeignKey("schools.id", ondelete="SET NULL"), nullable=True, index=True)
    action = Column(String, nullable=False, index=True)
    severity = Column(String, nullable=True, default="low", index=True)
    entity_type = Column(String, nullable=True, index=True)
    entity_id = Column(String, nullable=True)
    performed_by = Column(String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    actor_name = Column(String, nullable=True)
    actor_role = Column(String, nullable=True)
    actor_email = Column(String, nullable=True)
    target_id = Column(String, nullable=True, index=True)
    target_type = Column(String, nullable=True)
    target_name = Column(String, nullable=True)
    device_info = Column(JSONB, nullable=True)
    previous_state = Column(JSONB, nullable=True)
    new_state = Column(JSONB, nullable=True)
    details = Column(JSONB, nullable=True)
    ip_address = Column(String, nullable=True)
    user_agent = Column(String, nullable=True)
    status = Column(String, nullable=True, default="success")
    timestamp = Column(DateTime(timezone=True), default=_utcnow, index=True)
    # MFA (Task #169) — per-tenant tamper-evident hash chain, scoped to
    # rows whose action starts with ``mfa.``. NULL for non-MFA rows.
    prev_hash = Column(String(64), nullable=True)
    row_hash = Column(String(64), nullable=True)

    user = relationship("User", back_populates="audit_logs", foreign_keys=[performed_by], lazy="selectin")

    __table_args__ = (
        Index("idx_pg_audit_school_time", "school_id", "timestamp"),
        Index("idx_pg_audit_entity", "entity_type", "entity_id"),
        Index("idx_pg_audit_user_time", "performed_by", "timestamp"),
    )


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id = Column(String, ForeignKey("schools.id", ondelete="SET NULL"), nullable=True, index=True)
    title = Column(String, nullable=True)
    message = Column(Text, nullable=True)
    type = Column(String, nullable=True)
    priority = Column(String, default="normal")
    is_read = Column(Boolean, default=False)
    read_at = Column(DateTime(timezone=True), nullable=True)
    action_url = Column(String, nullable=True)
    extra_data = Column("metadata", JSONB, nullable=True)
    data = Column(JSONB, nullable=True, default=dict)
    # Task #249 — coarse-grained bucket for the IT inbox + per-category
    # channel preferences. Defaults to 'general' so legacy callsites
    # that don't pass a category still render in the catch-all bucket.
    category = Column(String, nullable=False, default="general", server_default="general")
    cta_url = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow)

    user = relationship("User", back_populates="notifications", foreign_keys=[user_id], lazy="selectin")

    __table_args__ = (
        Index("idx_pg_notifications_user_read_date", "user_id", "is_read", "created_at"),
        Index("idx_pg_notifications_tenant_date", "tenant_id", "created_at"),
        Index("idx_pg_notifications_user_category_date", "user_id", "category", "created_at"),
    )


class NotificationPreference(Base):
    """Task #249 — per-user, per-category channel preferences for the
    Independent-Teacher inbox. One row per (user_id, category)."""
    __tablename__ = "notifications_preferences"

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"),
                     nullable=False, index=True)
    category = Column(String(64), nullable=False)
    in_app = Column(Boolean, nullable=False, default=True, server_default="true")
    email = Column(Boolean, nullable=False, default=True, server_default="true")
    created_at = Column(DateTime(timezone=True), default=_utcnow,
                        server_default=text("CURRENT_TIMESTAMP"), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=_utcnow,
                        server_default=text("CURRENT_TIMESTAMP"), nullable=False)

    __table_args__ = (
        UniqueConstraint("user_id", "category", name="uq_notif_prefs_user_category"),
    )


class Assessment(Base):
    __tablename__ = "assessments"

    id = Column(String, primary_key=True, default=_uuid)
    school_id = Column(String, ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True)
    class_id = Column(String, ForeignKey("classes.id", ondelete="SET NULL"), nullable=True, index=True)
    subject_id = Column(String, ForeignKey("subjects.id", ondelete="SET NULL"), nullable=True)
    teacher_id = Column(String, ForeignKey("teachers.id", ondelete="SET NULL"), nullable=True, index=True)
    name = Column(String, nullable=False)
    name_en = Column(String, nullable=True)
    type = Column(String, nullable=True)
    max_score = Column(Float, default=100)
    weight = Column(Float, nullable=True)
    due_date = Column(DateTime(timezone=True), nullable=True)
    status = Column(String, default="draft")
    description = Column(Text, nullable=True)
    grading_criteria = Column(JSONB, default=dict)
    created_at = Column(DateTime(timezone=True), default=_utcnow)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    __table_args__ = (
        Index("idx_pg_assessments_school_class", "school_id", "class_id"),
    )


class AssessmentSubmission(Base):
    __tablename__ = "assessment_submissions"

    id = Column(String, primary_key=True, default=_uuid)
    assessment_id = Column(String, ForeignKey("assessments.id", ondelete="CASCADE"), nullable=False, index=True)
    student_id = Column(String, ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)
    score = Column(Float, nullable=True)
    grade = Column(String, nullable=True)
    feedback = Column(Text, nullable=True)
    status = Column(String, default="pending")
    submitted_at = Column(DateTime(timezone=True), nullable=True)
    graded_at = Column(DateTime(timezone=True), nullable=True)
    graded_by = Column(String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    data = Column(JSONB, default=dict)
    created_at = Column(DateTime(timezone=True), default=_utcnow)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    __table_args__ = (
        Index("idx_pg_submissions_assessment_student", "assessment_id", "student_id"),
    )


class BehaviourRecord(Base):
    __tablename__ = "behaviour_records"

    id = Column(String, primary_key=True, default=_uuid)
    school_id = Column(String, ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True)
    student_id = Column(String, ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)
    class_id = Column(String, ForeignKey("classes.id", ondelete="SET NULL"), nullable=True)
    teacher_id = Column(String, ForeignKey("teachers.id", ondelete="SET NULL"), nullable=True)
    type = Column(String, nullable=False)
    category = Column(String, nullable=True)
    severity = Column(String, nullable=True)
    points = Column(Integer, default=0)
    description = Column(Text, nullable=True)
    date = Column(DateTime(timezone=True), nullable=True)
    action_taken = Column(Text, nullable=True)
    parent_notified = Column(Boolean, default=False)
    created_by = Column(String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    __table_args__ = (
        Index("idx_pg_behaviour_school_student", "school_id", "student_id"),
        Index("idx_pg_behaviour_school_date", "school_id", "date"),
    )


class SchoolSettings(Base):
    __tablename__ = "school_settings"

    id = Column(String, primary_key=True, default=_uuid)
    school_id = Column(String, ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    working_days = Column(JSONB, default=list)
    periods_per_day = Column(Integer, default=7)
    period_duration = Column(Integer, default=45)
    break_duration = Column(Integer, default=15)
    start_time = Column(String, default="07:00")
    end_time = Column(String, default="14:00")
    grading_system = Column(String, default="percentage")
    language = Column(String, default="ar")
    calendar = Column(String, default="hijri_gregorian")
    notification_preferences = Column(JSONB, default=dict)
    features = Column(JSONB, default=dict)
    custom_settings = Column(JSONB, default=dict)
    created_at = Column(DateTime(timezone=True), default=_utcnow)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    school = relationship("School", back_populates="settings", lazy="selectin")


class RegistrationRequest(Base):
    __tablename__ = "registration_requests"

    id = Column(String, primary_key=True, default=_uuid)
    type = Column(String, nullable=False)
    name = Column(String, nullable=True)
    email = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    school_name = Column(String, nullable=True)
    school_id = Column(String, ForeignKey("schools.id", ondelete="SET NULL"), nullable=True, index=True)
    data = Column(JSONB, default=dict)
    status = Column(String, default="pending", index=True)
    reviewed_by = Column(String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    review_note = Column(Text, nullable=True)
    source = Column(String, nullable=True)
    payload_snapshot = Column(JSONB, nullable=True)
    linked_entity_type = Column(String, nullable=True)
    linked_entity_id = Column(String, nullable=True)
    review_notes = Column(JSONB, default=list)
    priority_field = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    __table_args__ = (
        Index("idx_pg_requests_status_date", "status", "created_at"),
        Index("idx_pg_requests_school_status", "school_id", "status"),
    )


class TeacherSession(Base):
    __tablename__ = "teacher_sessions"

    id = Column(String, primary_key=True, default=_uuid)
    school_id = Column(String, ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True)
    teacher_id = Column(String, ForeignKey("teachers.id", ondelete="CASCADE"), nullable=False, index=True)
    class_id = Column(String, ForeignKey("classes.id", ondelete="SET NULL"), nullable=True, index=True)
    subject_id = Column(String, ForeignKey("subjects.id", ondelete="SET NULL"), nullable=True)
    date = Column(DateTime(timezone=True), nullable=False)
    start_time = Column(String, nullable=True)
    end_time = Column(String, nullable=True)
    status = Column(String, default="scheduled")
    topic = Column(String, nullable=True)
    objectives = Column(JSONB, default=list)
    notes = Column(Text, nullable=True)
    attendance_taken = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=_utcnow)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    __table_args__ = (
        Index("idx_pg_tsessions_school_date", "school_id", "date"),
        Index("idx_pg_tsessions_teacher_date", "teacher_id", "date"),
        Index("idx_pg_tsessions_class_date", "class_id", "date"),
    )


class HakimInsight(Base):
    __tablename__ = "hakim_insights"

    id = Column(String, primary_key=True, default=_uuid)
    school_id = Column(String, ForeignKey("schools.id", ondelete="CASCADE"), nullable=True, index=True)
    type = Column(String, nullable=False)
    title = Column(String, nullable=True)
    content = Column(Text, nullable=True)
    severity = Column(String, default="info")
    data = Column(JSONB, default=dict)
    is_read = Column(Boolean, default=False)
    is_dismissed = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        Index("idx_pg_hakim_school_date", "school_id", "created_at"),
    )


class PlatformSettings(Base):
    __tablename__ = "platform_settings"

    id = Column(String, primary_key=True, default=_uuid)
    type = Column(String, nullable=False, unique=True, index=True)
    data = Column(JSONB, default=dict)
    updated_by = Column(String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)


class AcademicYear(Base):
    __tablename__ = "academic_years"

    id = Column(String, primary_key=True, default=_uuid)
    school_id = Column(String, ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String, nullable=False)
    name_en = Column(String, nullable=True)
    start_date = Column(DateTime(timezone=True), nullable=True)
    end_date = Column(DateTime(timezone=True), nullable=True)
    is_current = Column(Boolean, default=False)
    status = Column(String, default="active")
    created_at = Column(DateTime(timezone=True), default=_utcnow)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)


class AcademicTerm(Base):
    __tablename__ = "academic_terms"

    id = Column(String, primary_key=True, default=_uuid)
    school_id = Column(String, ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True)
    academic_year_id = Column(String, ForeignKey("academic_years.id", ondelete="CASCADE"), nullable=True)
    name = Column(String, nullable=False)
    name_en = Column(String, nullable=True)
    start_date = Column(DateTime(timezone=True), nullable=True)
    end_date = Column(DateTime(timezone=True), nullable=True)
    term_number = Column(Integer, default=1)
    is_current = Column(Boolean, default=False)
    status = Column(String, default="active")
    created_at = Column(DateTime(timezone=True), default=_utcnow)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    __table_args__ = (
        Index("idx_pg_terms_school_year", "school_id", "academic_year_id"),
    )


class Counter(Base):
    __tablename__ = "counters"

    id = Column(String, primary_key=True)
    seq = Column(Integer, default=0)


class LookupOption(Base):
    __tablename__ = "lookup_options"

    id = Column(String, primary_key=True, default=_uuid)
    category = Column(String, nullable=False, index=True)
    key = Column(String, nullable=False)
    value_ar = Column(String, nullable=True)
    value_en = Column(String, nullable=True)
    parent_key = Column(String, nullable=True)
    order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    school_id = Column(String, ForeignKey("schools.id", ondelete="SET NULL"), nullable=True, index=True)
    is_global = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        Index("idx_pg_lookup_category_key", "category", "key"),
        Index("idx_pg_lookup_school", "school_id", "category"),
    )


class Message(Base):
    __tablename__ = "messages"

    id = Column(String, primary_key=True, default=_uuid)
    sender_id = Column(String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    recipient_id = Column(String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    school_id = Column(String, ForeignKey("schools.id", ondelete="SET NULL"), nullable=True, index=True)
    subject = Column(String, nullable=True)
    body = Column(Text, nullable=True)
    is_read = Column(Boolean, default=False)
    read_at = Column(DateTime(timezone=True), nullable=True)
    extra_data = Column("metadata", JSONB, nullable=True)
    data = Column(JSONB, nullable=True, default=dict)
    created_at = Column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        Index("idx_pg_messages_sender", "sender_id", "created_at"),
        Index("idx_pg_messages_recipient", "recipient_id", "is_read"),
    )


class ApprovalEvent(Base):
    __tablename__ = "approval_events"

    id = Column(String, primary_key=True, default=_uuid)
    request_id = Column(String, ForeignKey("registration_requests.id", ondelete="CASCADE"), nullable=False, index=True)
    event_type = Column(String, nullable=False)
    from_status = Column(String, nullable=True)
    to_status = Column(String, nullable=True)
    performed_by = Column(String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    notes = Column(Text, nullable=True)
    data = Column(JSONB, nullable=True)
    timestamp = Column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        Index("idx_pg_approval_events_request", "request_id", "timestamp"),
    )


class SkillType(Base):
    __tablename__ = "skills_types"

    id = Column(String, primary_key=True, default=_uuid)
    name_ar = Column(String, nullable=True)
    name_en = Column(String, nullable=True)
    category = Column(String, nullable=True, index=True)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow)


class StudentSkill(Base):
    __tablename__ = "student_skills"

    id = Column(String, primary_key=True, default=_uuid)
    student_id = Column(String, ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)
    skill_type_id = Column(String, ForeignKey("skills_types.id", ondelete="CASCADE"), nullable=True, index=True)
    session_id = Column(String, nullable=True, index=True)
    class_id = Column(String, ForeignKey("classes.id", ondelete="SET NULL"), nullable=True, index=True)
    school_id = Column(String, ForeignKey("schools.id", ondelete="CASCADE"), nullable=True, index=True)
    level = Column(String, nullable=True)
    score = Column(Float, nullable=True)
    notes = Column(Text, nullable=True)
    assessed_by = Column(String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    date = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow)


class SessionInteraction(Base):
    __tablename__ = "session_interactions"

    id = Column(String, primary_key=True, default=_uuid)
    session_id = Column(String, nullable=False, index=True)
    student_id = Column(String, ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)
    type = Column(String, nullable=False, index=True)
    data = Column(JSONB, default=dict)
    recorded_by = Column(String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    timestamp = Column(DateTime(timezone=True), default=_utcnow)


class AIInsight(Base):
    __tablename__ = "ai_insights"

    id = Column(String, primary_key=True, default=_uuid)
    school_id = Column(String, ForeignKey("schools.id", ondelete="CASCADE"), nullable=True, index=True)
    entity_type = Column(String, nullable=True, index=True)
    entity_id = Column(String, nullable=True)
    insight_type = Column(String, nullable=False, index=True)
    title = Column(String, nullable=True)
    content = Column(Text, nullable=True)
    data = Column(JSONB, default=dict)
    severity = Column(String, default="info")
    is_actionable = Column(Boolean, default=False)
    is_dismissed = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=_utcnow, index=True)

    __table_args__ = (
        Index("idx_pg_ai_insights_school_type", "school_id", "insight_type"),
        Index("idx_pg_ai_insights_entity_type", "entity_type", "entity_id"),
    )


class AIIntervention(Base):
    __tablename__ = "ai_interventions"

    id = Column(String, primary_key=True, default=_uuid)
    school_id = Column(String, ForeignKey("schools.id", ondelete="CASCADE"), nullable=True, index=True)
    student_id = Column(String, ForeignKey("students.id", ondelete="SET NULL"), nullable=True, index=True)
    type = Column(String, nullable=False)
    status = Column(String, default="suggested", index=True)
    title = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    recommendation = Column(Text, nullable=True)
    data = Column(JSONB, default=dict)
    created_by = Column(String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_by = Column(String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow, index=True)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    __table_args__ = (
        Index("idx_pg_ai_interventions_school_status", "school_id", "status"),
        Index("idx_pg_ai_interventions_student_status", "student_id", "status"),
    )


class SessionNote(Base):
    __tablename__ = "session_notes"

    id = Column(String, primary_key=True, default=_uuid)
    session_id = Column(String, nullable=False, index=True)
    teacher_id = Column(String, ForeignKey("teachers.id", ondelete="SET NULL"), nullable=True, index=True)
    student_id = Column(String, ForeignKey("students.id", ondelete="SET NULL"), nullable=True, index=True)
    note = Column(Text, nullable=True)
    type = Column(String, default="general")
    created_at = Column(DateTime(timezone=True), default=_utcnow)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)


class SessionEventLog(Base):
    __tablename__ = "session_event_log"

    id = Column(String, primary_key=True, default=_uuid)
    session_id = Column(String, nullable=False, index=True)
    event_type = Column(String, nullable=False, index=True)
    data = Column(JSONB, default=dict)
    performed_by = Column(String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    timestamp = Column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        Index("idx_pg_session_events_session_time", "session_id", "timestamp"),
    )


class TeacherClassAssignment(Base):
    __tablename__ = "teacher_class_assignments"

    id = Column(String, primary_key=True, default=_uuid)
    school_id = Column(String, ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True)
    teacher_id = Column(String, ForeignKey("teachers.id", ondelete="CASCADE"), nullable=False, index=True)
    class_id = Column(String, ForeignKey("classes.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String, default="teacher")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        UniqueConstraint("school_id", "teacher_id", "class_id", name="uq_tca_school_teacher_class"),
    )


class GradeLevel(Base):
    __tablename__ = "grade_levels"

    id = Column(String, primary_key=True, default=_uuid)
    school_id = Column(String, ForeignKey("schools.id", ondelete="CASCADE"), nullable=True, index=True)
    name_ar = Column(String, nullable=True)
    name_en = Column(String, nullable=True)
    code = Column(String, nullable=True)
    stage = Column(String, nullable=True)
    order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)


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
    tenant_id = Column(String, ForeignKey("schools.id", ondelete="CASCADE"), nullable=True)
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
    created_at = Column(DateTime(timezone=True), default=_utcnow)


class BehaviourType(Base):
    __tablename__ = "behaviour_types"

    id = Column(String, primary_key=True, default=_uuid)
    tenant_id = Column(String, ForeignKey("schools.id", ondelete="CASCADE"), nullable=True)
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
    created_at = Column(DateTime(timezone=True), default=_utcnow)


class TimetableConstraint(Base):
    __tablename__ = "timetable_constraints"

    id = Column(String, primary_key=True, default=_uuid)
    school_id = Column(String, ForeignKey("schools.id", ondelete="SET NULL"), nullable=True, index=True)
    type = Column(String, nullable=True)
    category = Column(String, default="hard")
    name = Column(String, nullable=True)
    name_en = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    config = Column(JSONB, default=dict)
    is_active = Column(Boolean, default=True)
    is_global = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow)


class ApprovalRequest(Base):
    __tablename__ = "approval_requests"

    id = Column(String, primary_key=True, default=_uuid)
    type = Column(String, nullable=False)
    entity_id = Column(String, nullable=True)
    entity_type = Column(String, nullable=True)
    status = Column(String, default="pending")
    requested_by = Column(String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    requested_by_name = Column(String, nullable=True)
    school_id = Column(String, ForeignKey("schools.id", ondelete="SET NULL"), nullable=True, index=True)
    data = Column(JSONB, default=dict)
    result = Column(JSONB, nullable=True)
    reviewed_by = Column(String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    review_note = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)


class Event(Base):
    __tablename__ = "events"

    id = Column(String, primary_key=True, default=_uuid)
    tenant_id = Column(String, ForeignKey("schools.id", ondelete="CASCADE"), nullable=True, index=True)
    type = Column(String, nullable=False, index=True)
    status = Column(String, nullable=True)
    student_id = Column(String, ForeignKey("students.id", ondelete="SET NULL"), nullable=True, index=True)
    class_id = Column(String, ForeignKey("classes.id", ondelete="SET NULL"), nullable=True, index=True)
    recorded_by = Column(String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    date = Column(String, nullable=True)
    data = Column(JSONB, default=dict)
    created_at = Column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        Index("idx_events_tenant_type", "tenant_id", "type"),
        Index("idx_events_tenant_date", "tenant_id", "created_at"),
    )


class CalendarEvent(Base):
    __tablename__ = "calendar_events"

    id = Column(String, primary_key=True, default=_uuid)
    tenant_id = Column(String, ForeignKey("schools.id", ondelete="CASCADE"), nullable=True, index=True)
    title_ar = Column(String, nullable=False)
    title_en = Column(String, nullable=True)
    type = Column(String, nullable=False, default="meeting", index=True)
    date = Column(String, nullable=False, index=True)
    details_ar = Column(Text, nullable=True)
    details_en = Column(Text, nullable=True)
    created_by = Column(String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    # IT Phase 2 §6.3 (Task #208) — personal-event flag. NULL/false on
    # legacy school-wide rows; true only for IT-authored personal events.
    is_personal = Column(Boolean, nullable=True, default=False, server_default=text("false"))
    created_at = Column(DateTime(timezone=True), default=_utcnow)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    __table_args__ = (
        Index("idx_calendar_events_tenant_date", "tenant_id", "date"),
        Index("ix_calendar_events_tenant_personal_creator", "tenant_id", "is_personal", "created_by"),
    )


class DailyTask(Base):
    __tablename__ = "daily_tasks"

    id = Column(String, primary_key=True, default=_uuid)
    tenant_id = Column(String, ForeignKey("schools.id", ondelete="CASCADE"), nullable=True, index=True)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    title = Column(String, nullable=False)
    details = Column(Text, nullable=True)
    priority = Column(String, nullable=False, default="normal", index=True)
    status = Column(String, nullable=False, default="active", index=True)
    source = Column(String, nullable=False, default="manual", index=True)
    task_date = Column(String, nullable=False, index=True)
    ai_meta = Column(JSONB, nullable=True)
    created_by = Column(String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    __table_args__ = (
        Index("idx_daily_tasks_user_date", "user_id", "task_date"),
        Index("idx_daily_tasks_tenant_date", "tenant_id", "task_date"),
        Index("idx_daily_tasks_user_status", "user_id", "status"),
    )


class SystemSetting(Base):
    __tablename__ = "system_settings"

    id = Column(String, primary_key=True, default=_uuid)
    type = Column(String, nullable=False, unique=True, index=True)
    data = Column(JSONB, default=dict)
    updated_by = Column(String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)


class LessonPlan(Base):
    """IT Phase 2 §6.4 (Task #209) — saved AI lesson-plan generations.

    One row per saved generation. Always pinned to the synthetic
    ``itw_{user_id}`` workspace tenant via ``workspace_school_id`` and
    authored by the IT user. Generated payload lives in JSONB so the
    LLM schema can evolve without a migration.
    """
    __tablename__ = "lesson_plans"

    id = Column(String, primary_key=True, default=_uuid)
    workspace_school_id = Column(
        String, ForeignKey("schools.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    created_by = Column(
        String, ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    subject = Column(String(200), nullable=True)
    grade_level = Column(String(200), nullable=True)
    topic = Column(String(500), nullable=False)
    duration_minutes = Column(Integer, nullable=True)
    language = Column(String(8), nullable=False, default="ar")
    prompt = Column(Text, nullable=True)
    plan = Column(JSONB, nullable=False, default=dict)
    class_id = Column(
        String, ForeignKey("classes.id", ondelete="SET NULL"), nullable=True,
    )
    is_saved = Column(Boolean, nullable=False, default=False, server_default=text("false"))
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at = Column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False,
    )

    __table_args__ = (
        Index("ix_lesson_plans_ws_created", "workspace_school_id", "created_at"),
        Index("ix_lesson_plans_ws_author", "workspace_school_id", "created_by"),
    )


class ParentInvitation(Base):
    """IT Phase 2 §6.2 (Task #205) — parent invitation lifecycle row.

    One row per minted invitation; a single ``(workspace_school_id,
    student_id)`` may have at most one ``status='pending'`` row at a time
    (enforced in the route layer via the composite read index, not a DB
    unique constraint, so cancelled/expired/accepted history coexists).
    """
    __tablename__ = "parent_invitations"

    id = Column(String, primary_key=True, default=_uuid)
    workspace_school_id = Column(
        String, ForeignKey("schools.id", ondelete="CASCADE"),
        nullable=False,
    )
    parent_email = Column(String, nullable=True)
    parent_phone = Column(String, nullable=True)
    student_id = Column(
        String, ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
    )
    token_hash = Column(String, nullable=False)
    sent_at = Column(DateTime(timezone=True), nullable=False)
    accepted_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    status = Column(String, nullable=False)
    created_by = Column(String, nullable=True)
    created_at = Column(
        DateTime(timezone=True), default=_utcnow, nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )
    updated_at = Column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow,
        nullable=False, server_default=text("CURRENT_TIMESTAMP"),
    )

    __table_args__ = (
        Index(
            "ix_parent_invitations_workspace_student_status",
            "workspace_school_id", "student_id", "status",
        ),
        Index("ix_parent_invitations_token_hash", "token_hash"),
    )


class WorkspaceCollaborator(Base):
    """IT Phase 2 §6.7 (Task #210) — cross-workspace co-teaching link.

    Links one host IT workspace's class to exactly one collaborator IT
    workspace. The §8 single-tenant invariant is intentionally relaxed
    only for the named ``class_id``, never the wider workspace.
    """
    __tablename__ = "workspace_collaborators"

    id = Column(String, primary_key=True, default=_uuid)
    host_school_id = Column(
        String, ForeignKey("schools.id", ondelete="CASCADE"),
        nullable=False,
    )
    collaborator_school_id = Column(
        String, ForeignKey("schools.id", ondelete="CASCADE"),
        nullable=True,
    )
    class_id = Column(
        String, ForeignKey("classes.id", ondelete="CASCADE"),
        nullable=False,
    )
    collaborator_email = Column(String, nullable=True)
    collaborator_user_id = Column(String, nullable=True)
    token_hash = Column(String, nullable=False)
    scope = Column(
        JSONB, nullable=False, default=lambda: {"mode": "read"},
        server_default=text("'{\"mode\": \"read\"}'::jsonb"),
    )
    status = Column(String, nullable=False)
    sent_at = Column(DateTime(timezone=True), nullable=False)
    accepted_at = Column(DateTime(timezone=True), nullable=True)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_by = Column(String, nullable=True)
    created_at = Column(
        DateTime(timezone=True), default=_utcnow, nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )
    updated_at = Column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow,
        nullable=False, server_default=text("CURRENT_TIMESTAMP"),
    )

    __table_args__ = (
        Index(
            "ux_workspace_collab_accepted",
            "host_school_id", "collaborator_school_id", "class_id",
            unique=True,
            postgresql_where=text("status = 'accepted'"),
        ),
        Index(
            "ux_workspace_collab_pending",
            "host_school_id", "class_id", "collaborator_email",
            unique=True,
            postgresql_where=text("status = 'pending'"),
        ),
        Index(
            "ix_workspace_collab_host_class_status",
            "host_school_id", "class_id", "status",
        ),
        Index(
            "ix_workspace_collab_collab_status",
            "collaborator_school_id", "status",
        ),
        Index("ix_workspace_collab_token_hash", "token_hash"),
    )


class WorkspaceQuota(Base):
    """IT Phase 2 §6.1 (Task #207) — per-workspace quota row.

    PK is ``workspace_school_id`` (always points at the synthetic
    ``itw_{user_id}`` schools row). Counters reset on UTC-day boundary
    in application code.
    """
    __tablename__ = "workspace_quota"

    workspace_school_id = Column(
        String, ForeignKey("schools.id", ondelete="CASCADE"),
        primary_key=True, nullable=False,
    )
    max_students = Column(Integer, nullable=False, default=200, server_default=text("200"))
    max_classes = Column(Integer, nullable=False, default=5, server_default=text("5"))
    max_imports_per_day = Column(Integer, nullable=False, default=5, server_default=text("5"))
    max_rows_per_import = Column(Integer, nullable=False, default=200, server_default=text("200"))
    imports_today = Column(Integer, nullable=False, default=0, server_default=text("0"))
    imports_today_date = Column(Date, nullable=True)
    # IT Phase 2 §6.4 (Task #209) — daily lesson-plan counter (UTC-day reset
    # in app code, mirrors imports_today).
    lesson_plans_today = Column(Integer, nullable=False, default=0, server_default=text("0"))
    lesson_plans_today_date = Column(Date, nullable=True)
    # Task #275 — opt-in weekly auto-export schedule for IT workspaces.
    auto_export_enabled = Column(Boolean, nullable=False, default=False, server_default=text("false"))
    auto_export_dow = Column(SmallInteger, nullable=True)
    auto_export_hour = Column(SmallInteger, nullable=True)
    auto_export_last_run_at = Column(DateTime(timezone=True), nullable=True)
    auto_export_last_status = Column(Text, nullable=True)
    created_at = Column(
        DateTime(timezone=True), default=_utcnow, nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )
    updated_at = Column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow,
        nullable=False, server_default=text("CURRENT_TIMESTAMP"),
    )


class GenericDocument(Base):
    __tablename__ = "generic_documents"

    id = Column(String, primary_key=True, default=_uuid)
    _collection = Column("collection", String, nullable=False, index=True)
    data = Column(JSONB, default=dict)
    created_at = Column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        Index("idx_generic_docs_collection", "collection"),
    )


issue_number_seq = Sequence("issue_number_seq", start=1, increment=1)


class RevokedToken(Base):
    __tablename__ = "revoked_tokens"

    jti = Column(String(36), primary_key=True, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    revoked_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)

    __table_args__ = (
        Index("ix_revoked_tokens_expires_at", "expires_at"),
    )


class UserSession(Base):
    __tablename__ = "user_sessions"

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, nullable=False, index=True)
    jti = Column(String(64), nullable=False, unique=True, index=True)
    device = Column(String(128), nullable=True)
    browser = Column(String(64), nullable=True)
    os = Column(String(64), nullable=True)
    ip_address = Column(String(64), nullable=True)
    user_agent = Column(Text, nullable=True)
    location = Column(String(128), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    last_seen_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    revoked_at = Column(DateTime(timezone=True), nullable=True, index=True)
    # Task #374 — refresh token jti + family id paired with this session's
    # access jti. Required so single-session and end-all revocation can
    # block the refresh path too (otherwise the device silently revives
    # on /auth/refresh after its short-lived access token expires).
    refresh_jti = Column(String(64), nullable=True, index=True)
    refresh_family_id = Column(String(64), nullable=True, index=True)
    # Task #374 follow-up — refresh token's own ``exp``. Used by
    # settings_routes._revoke_session_refresh_chain so the revoked
    # refresh JTI lives in revoked_tokens until the refresh token
    # actually expires (not the access token's ~15 min lifetime, which
    # would let the cleanup loop purge the revocation early).
    refresh_expires_at = Column(DateTime(timezone=True), nullable=True)


# ============================================================================
# MFA (Task #169) — role-tiered second factor
# ============================================================================

class MfaFactor(Base):
    """One enrolled second factor on a user.

    The same user may have many active rows (e.g. one ``webauthn`` row per
    registered device, plus one ``totp`` row). ``recovery_code`` rows are
    tracked separately in :class:`MfaRecoveryCode` — this table covers the
    "interactive" factors only.
    """
    __tablename__ = "mfa_factors"

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    kind = Column(String, nullable=False)  # totp | webauthn
    label = Column(String, nullable=True)
    is_primary = Column(Boolean, nullable=False, default=False)
    is_active = Column(Boolean, nullable=False, default=False)

    # TOTP — null for non-TOTP rows. Stored as PostgreSQL ``BYTEA`` because
    # Fernet ciphertext is binary and round-trips cleanly via asyncpg as
    # ``bytes`` / ``memoryview``.
    totp_secret_encrypted = Column(LargeBinary, nullable=True)

    # WebAuthn — null for non-WebAuthn rows. Credential ID + public key are
    # raw CBOR/COSE bytes; storing as ``BYTEA`` avoids any base64-roundtrip
    # ambiguity at compare time.
    webauthn_credential_id = Column(LargeBinary, nullable=True)
    webauthn_public_key = Column(LargeBinary, nullable=True)
    webauthn_sign_count = Column(Integer, nullable=True)
    webauthn_aaguid = Column(String, nullable=True)
    webauthn_attachment = Column(String, nullable=True)  # 'platform' | 'cross-platform'

    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    verified_at = Column(DateTime(timezone=True), nullable=True)
    last_used_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("idx_mfa_factors_user_kind", "user_id", "kind"),
        Index("idx_mfa_factors_user_active", "user_id", "is_active"),
        UniqueConstraint("webauthn_credential_id", name="uq_mfa_factors_webauthn_credential_id"),
    )


class MfaRecoveryCode(Base):
    """One single-use bcrypt-hashed recovery code. ``consumed_at`` is set on
    use; the row is kept so the hash chain in audit logs remains verifiable."""
    __tablename__ = "mfa_recovery_codes"

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    code_hash = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    consumed_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("idx_mfa_recovery_user_unused", "user_id", "consumed_at"),
    )


class MfaPendingChallenge(Base):
    """Short-lived row representing the "password OK, waiting for second
    factor" state. The login route inserts this and returns a JWT whose
    ``jti`` matches ``challenge_token_jti``; ``/auth/mfa/verify`` consumes
    it on success and deletes/marks it on completion. Capped TTL ≤ 10 min."""
    __tablename__ = "mfa_pending_challenges"

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    challenge_token_jti = Column(String, nullable=False, unique=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    attempts = Column(Integer, nullable=False, default=0)
    consumed_at = Column(DateTime(timezone=True), nullable=True)
    ip = Column(String, nullable=True)
    user_agent = Column(String, nullable=True)
    remember_me = Column(Boolean, nullable=False, default=False)

    __table_args__ = (
        Index("idx_mfa_pending_expires", "expires_at"),
    )


class MfaEmailOtp(Base):
    """One emailed 6-digit OTP for Tier B/C login. Stored as salted-sha256;
    the salt lives on the same row so verify can recompute without
    decrypting anything."""
    __tablename__ = "mfa_email_otps"

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    code_hash = Column(String, nullable=False)
    code_salt = Column(String, nullable=False)
    challenge_id = Column(String, ForeignKey("mfa_pending_challenges.id", ondelete="CASCADE"), nullable=False)
    sent_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    attempts = Column(Integer, nullable=False, default=0)
    consumed_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("idx_mfa_email_otps_challenge", "challenge_id"),
    )


class MfaWebauthnChallenge(Base):
    """Random bytes used as the WebAuthn ceremony challenge for either an
    enrol (``purpose='enroll'``) or verify (``purpose='verify'``) flow.
    Short TTL (≤ 5 min)."""
    __tablename__ = "mfa_webauthn_challenges"

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    purpose = Column(String, nullable=False)  # 'enroll' | 'verify'
    challenge = Column(LargeBinary, nullable=False)  # raw random bytes
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        Index("idx_mfa_webauthn_challenges_expires", "expires_at"),
    )
