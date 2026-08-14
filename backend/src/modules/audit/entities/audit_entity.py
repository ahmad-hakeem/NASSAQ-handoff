"""SQLAlchemy ORM Entities for audit domain."""
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


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(String, primary_key=True, default=_uuid)
    school_id = Column(String, ForeignKey("schools.id", ondelete="SET NULL"), nullable=True, index=True)
    action = Column(String, nullable=False, index=True)
    severity = Column(String, nullable=True, default="low", index=True)
    entity_type = Column(String, nullable=True, index=True)
    entity_id = Column(String, nullable=True)
    performed_by = Column(String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    actor_name = Column(String, nullable=True)
    actor_role = Column(String, nullable=True)
    actor_email = Column(String, nullable=True)
    target_id = Column(String, nullable=True, index=True)
    target_type = Column(String, nullable=True)
    target_name = Column(String, nullable=True)
    device_info = Column(JSONB, nullable=True)
    previous_state = Column(JSONB, nullable=True)
    new_state = Column(JSONB, nullable=True)
    details = Column(JSONB, nullable=True)
    ip_address = Column(String, nullable=True)
    user_agent = Column(String, nullable=True)
    status = Column(String, nullable=True, default="success")
    timestamp = Column(DateTime(timezone=True), default=_utcnow, index=True)
    # MFA (Task #169) — per-tenant tamper-evident hash chain, scoped to
    # rows whose action starts with ``mfa.``. NULL for non-MFA rows.
    prev_hash = Column(String(64), nullable=True)
    row_hash = Column(String(64), nullable=True)

    user = relationship("User", back_populates="audit_logs", foreign_keys=[performed_by], lazy="selectin")

    __table_args__ = (
        Index("idx_pg_audit_school_time", "school_id", "timestamp"),
        Index("idx_pg_audit_entity", "entity_type", "entity_id"),
        Index("idx_pg_audit_user_time", "performed_by", "timestamp"),
    )

