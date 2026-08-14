"""SQLAlchemy ORM Entities for ai domain."""
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


class HakimInsight(Base):
    __tablename__ = "hakim_insights"

    id = Column(String, primary_key=True, default=_uuid)
    school_id = Column(String, ForeignKey("schools.id", ondelete="CASCADE"), nullable=True, index=True)
    type = Column(String, nullable=False)
    title = Column(String, nullable=True)
    content = Column(Text, nullable=True)
    severity = Column(String, default="info")
    data = Column(JSONB, default=dict)
    is_read = Column(Boolean, default=False)
    is_dismissed = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        Index("idx_pg_hakim_school_date", "school_id", "created_at"),
    )


class AIInsight(Base):
    __tablename__ = "ai_insights"

    id = Column(String, primary_key=True, default=_uuid)
    school_id = Column(String, ForeignKey("schools.id", ondelete="CASCADE"), nullable=True, index=True)
    entity_type = Column(String, nullable=True, index=True)
    entity_id = Column(String, nullable=True)
    insight_type = Column(String, nullable=False, index=True)
    title = Column(String, nullable=True)
    content = Column(Text, nullable=True)
    data = Column(JSONB, default=dict)
    severity = Column(String, default="info")
    is_actionable = Column(Boolean, default=False)
    is_dismissed = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=_utcnow, index=True)

    __table_args__ = (
        Index("idx_pg_ai_insights_school_type", "school_id", "insight_type"),
        Index("idx_pg_ai_insights_entity_type", "entity_type", "entity_id"),
    )


class AIIntervention(Base):
    __tablename__ = "ai_interventions"

    id = Column(String, primary_key=True, default=_uuid)
    school_id = Column(String, ForeignKey("schools.id", ondelete="CASCADE"), nullable=True, index=True)
    student_id = Column(String, ForeignKey("students.id", ondelete="SET NULL"), nullable=True, index=True)
    type = Column(String, nullable=False)
    status = Column(String, default="suggested", index=True)
    title = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    recommendation = Column(Text, nullable=True)
    data = Column(JSONB, default=dict)
    created_by = Column(String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_by = Column(String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow, index=True)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    __table_args__ = (
        Index("idx_pg_ai_interventions_school_status", "school_id", "status"),
        Index("idx_pg_ai_interventions_student_status", "student_id", "status"),
    )


class PublicHakimRateCounter(Base):
    """Shared, cross-worker rate-limit counters for the public landing-page
    Hakim chat endpoints. Keyed by a versioned bucket identifier
    (``v1:<scope>:<identity>:<bucket>``) where bucket is a minute or day
    epoch. Atomically incremented via ``INSERT ... ON CONFLICT DO UPDATE
    SET count = count + 1 RETURNING count``. Rows are opportunistically
    cleaned up once ``expires_at`` has passed.
    """

    __tablename__ = "public_hakim_rate_counters"

    key = Column(String(160), primary_key=True)
    count = Column(Integer, nullable=False, server_default=text("0"))
    expires_at = Column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        Index("ix_public_hakim_rate_counters_expires_at", "expires_at"),
    )

