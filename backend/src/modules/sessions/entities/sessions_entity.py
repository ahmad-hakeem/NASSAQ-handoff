"""SQLAlchemy ORM Entities for sessions domain."""
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


class SessionInteraction(Base):
    __tablename__ = "session_interactions"

    id = Column(String, primary_key=True, default=_uuid)
    session_id = Column(String, nullable=False, index=True)
    student_id = Column(String, ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)
    type = Column(String, nullable=False, index=True)
    data = Column(JSONB, default=dict)
    recorded_by = Column(String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    timestamp = Column(DateTime(timezone=True), default=_utcnow)


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


class SkillType(Base):
    __tablename__ = "skills_types"

    id = Column(String, primary_key=True, default=_uuid)
    name_ar = Column(String, nullable=True)
    name_en = Column(String, nullable=True)
    category = Column(String, nullable=True, index=True)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow)
    # NULL = global/seed skill (visible to all schools); non-NULL = school-scoped.
    school_id = Column(String, ForeignKey("schools.id", ondelete="CASCADE"), nullable=True, index=True)
    # Configured per-skill point value. NULL = no configured value, so the
    # scoring engine falls back to the global ``special_skill`` rule (keeps the
    # seed/default skills behaving as before). A stored value is authoritative:
    # the engine awards it instead of the default when the skill is recorded.
    points = Column(Integer, nullable=True)


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

