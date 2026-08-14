"""SQLAlchemy ORM Entities for communication domain."""
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


class Message(Base):
    __tablename__ = "messages"

    id = Column(String, primary_key=True, default=_uuid)
    sender_id = Column(String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    recipient_id = Column(String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    school_id = Column(String, ForeignKey("schools.id", ondelete="SET NULL"), nullable=True, index=True)
    subject = Column(String, nullable=True)
    body = Column(Text, nullable=True)
    is_read = Column(Boolean, default=False)
    read_at = Column(DateTime(timezone=True), nullable=True)
    extra_data = Column("metadata", JSONB, nullable=True)
    data = Column(JSONB, nullable=True, default=dict)
    created_at = Column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        Index("idx_pg_messages_sender", "sender_id", "created_at"),
        Index("idx_pg_messages_recipient", "recipient_id", "is_read"),
    )

