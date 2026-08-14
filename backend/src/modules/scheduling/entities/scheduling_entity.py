"""SQLAlchemy ORM Entities for scheduling domain."""
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
    is_published = Column(Boolean, default=False, nullable=True)
    total_sessions = Column(Integer, default=0)
    version = Column(Integer, default=1)
    created_at = Column(DateTime(timezone=True), default=_utcnow)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)
    published_at = Column(DateTime(timezone=True), nullable=True)
    published_by = Column(String, nullable=True)
    created_by = Column(String, nullable=True)
    updated_by = Column(String, nullable=True)


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
    # Overflow for the run/progress fields the scheduling engine writes that
    # have no dedicated column (started_at, finished_at, completion_percentage,
    # timetable_id, created_by, ...). Without it dict_to_model drops them
    # silently, which is exactly what used to happen. See migration
    # tj01runs02data.
    data = Column(JSONB, default=dict)


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

