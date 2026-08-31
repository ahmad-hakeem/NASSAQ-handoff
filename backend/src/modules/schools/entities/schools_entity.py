"""SQLAlchemy ORM Entities for schools domain."""
import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, Integer, SmallInteger, Float, Boolean, Date, DateTime, Text,
    Enum as SAEnum, ForeignKey, Index, JSON, LargeBinary, UniqueConstraint,
    Sequence, text
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB
from sqlalchemy.orm import relationship, validates
from src.core.database.db import Base


def _uuid():
    return str(uuid.uuid4())


def _utcnow():
    return datetime.now(timezone.utc)


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

    @validates("logo_url")
    def _validate_logo_url_bounded(self, key, value):
        # ORM-level chokepoint mirroring User.avatar_url — see utils.avatar_image.
        from src.common.utils.avatar_image import assert_stored_image_bounded
        assert_stored_image_bounded("schools", key, value)
        return value
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
    educational_pathway = Column(String, nullable=True)
    ministry_id = Column(String, nullable=True)
    license_number = Column(String, nullable=True)
    tenant_type = Column(String, default="production")
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
    # Task #450 — bind the export download to the bearer-token JTI that
    # minted it.  Only that exact session may bypass the is_active /
    # last_password_change checks on the public download endpoint; any
    # other bearer token (including stolen sessions whose JTI differs)
    # must pass full session-invalidation checks and will be rejected
    # after archive/erasure.
    last_export_initiator_jti = Column(String, nullable=True)
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

