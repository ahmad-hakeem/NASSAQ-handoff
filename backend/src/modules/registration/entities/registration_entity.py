"""SQLAlchemy ORM Entities for registration domain."""
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

