"""SQLAlchemy ORM Entities for calendar domain."""
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

