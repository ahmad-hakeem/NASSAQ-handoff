"""SQLAlchemy ORM Entities for academics domain."""
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
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    deleted_by = Column(String, nullable=True)
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
    health_info = Column(JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))
    profile_settings = Column(JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))
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
    # Retained as nullable legacy metadata only.  Roster membership is
    # intentionally open-ended and never gated by this column.
    capacity = Column(Integer, nullable=True)
    current_students = Column(Integer, default=0)
    homeroom_teacher_id = Column(String, ForeignKey("teachers.id", ondelete="SET NULL"), nullable=True)
    homeroom_teacher_name = Column(String, nullable=True)
    classroom_id = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    deleted_by = Column(String, nullable=True)
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
    credits = Column(Integer, nullable=False, default=1, server_default="1")
    default_periods_per_week = Column(Integer, default=4)
    applicable_stages = Column(JSONB, default=list)
    is_active = Column(Boolean, default=True)
    is_global = Column(Boolean, default=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    deleted_by = Column(String, nullable=True)
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


class GradeLevel(Base):
    __tablename__ = "grade_levels"

    id = Column(String, primary_key=True, default=_uuid)
    school_id = Column(String, ForeignKey("schools.id", ondelete="CASCADE"), nullable=True, index=True)
    name = Column(String, nullable=True)
    name_ar = Column(String, nullable=True)
    name_en = Column(String, nullable=True)
    code = Column(String, nullable=True)
    stage = Column(String, nullable=True)
    order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(DateTime(timezone=True), nullable=True)
    created_by = Column(String, nullable=True)


class EducationalStage(Base):
    __tablename__ = "educational_stages"

    id = Column(String, primary_key=True, default=_uuid)
    tenant_id = Column(String, ForeignKey("schools.id", ondelete="CASCADE"), nullable=True, index=True)
    is_global = Column(Boolean, default=False, index=True)
    name_ar = Column(String, nullable=True)
    name_en = Column(String, nullable=True)
    code = Column(String, nullable=True)
    order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)

