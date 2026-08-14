"""SQLAlchemy ORM Entities for assessment domain."""
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

