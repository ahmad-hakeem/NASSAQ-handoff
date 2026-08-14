"""SQLAlchemy ORM Entities for infrastructure domain."""
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


class RateLimitCounter(Base):
    """Shared, cross-worker counters for the auth / brute-force limiter.

    Keyed by ``<namespace>:<sha256(logical key)>:<window>:<bucket>``. Two
    adjacent buckets are read per check so the window slides instead of
    resetting on a hard boundary. Rows carry ``expires_at`` and are swept
    opportunistically, exactly like the public-Hakim counters — but in a
    separate table so neither surface can evict the other's rows.
    """

    __tablename__ = "rate_limit_counters"

    key = Column(String(200), primary_key=True)
    count = Column(Integer, nullable=False, server_default=text("0"))
    expires_at = Column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        Index("ix_rate_limit_counters_expires_at", "expires_at"),
    )

