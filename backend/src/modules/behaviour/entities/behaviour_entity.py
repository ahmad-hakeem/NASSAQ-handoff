"""SQLAlchemy ORM Entities for behaviour domain."""
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

