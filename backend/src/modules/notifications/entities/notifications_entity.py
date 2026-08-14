"""SQLAlchemy ORM Entities for notifications domain."""
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
    # Task #1006 — optional student reference so parents can filter their
    # notification inbox by child. Nullable and SET NULL on student delete
    # so notification history is preserved even when a student is removed.
    student_id = Column(String, ForeignKey("students.id", ondelete="SET NULL"), nullable=True, index=True)
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

