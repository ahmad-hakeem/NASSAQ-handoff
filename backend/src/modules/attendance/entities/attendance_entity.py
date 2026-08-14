"""SQLAlchemy ORM Entities for attendance domain."""
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

