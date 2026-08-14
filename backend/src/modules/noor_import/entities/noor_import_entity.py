"""SQLAlchemy ORM Entities for noor_import domain."""
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


class NoorImportHistory(Base):
    """Persistent record of every committed Noor import.

    Written at /noor-import/commit time (after the outer transaction
    succeeds). Never mutated after creation. Credentials CSV is stored
    here to allow re-download; it only contains one-time passwords that
    teachers must change on first login.
    """

    __tablename__ = "noor_import_history"

    id = Column(String, primary_key=True, default=_uuid)
    school_id = Column(String, nullable=False, index=True)
    actor_id = Column(String, nullable=False)
    actor_name = Column(String, nullable=True)
    detected_type = Column(String, nullable=False)  # "teachers" | "students"

    imported_count = Column(Integer, nullable=False, default=0)
    updated_count = Column(Integer, nullable=False, default=0)
    skipped_count = Column(Integer, nullable=False, default=0)
    failed_count = Column(Integer, nullable=False, default=0)
    duplicates_count = Column(Integer, nullable=False, default=0)
    unclassified_count = Column(Integer, nullable=False, default=0)

    created_ids = Column(JSONB, nullable=True)        # entity UUIDs inserted
    updated_ids = Column(JSONB, nullable=True)        # entity UUIDs updated
    created_class_ids = Column(JSONB, nullable=True)  # class UUIDs from create-missing-classes
    credentials_csv = Column(JSONB, nullable=True)    # re-downloadable teacher creds

    committed_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("idx_noor_import_history_school_committed", "school_id", "committed_at"),
        Index(
            "idx_noor_import_history_school_active",
            "school_id",
            "committed_at",
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )


class NoorImportDraft(Base):
    """Short-lived draft store for the two-step Noor importer (parse -> commit).

    Created at /noor-import/parse time and read back by /noor-import/commit
    so the server never trusts a client-supplied rows[] payload. Rows are
    purged lazily once `expires_at` has passed (1h TTL).
    """

    __tablename__ = "noor_import_drafts"

    id = Column(String, primary_key=True)
    principal_id = Column(String, nullable=False, index=True)
    school_id = Column(String, nullable=False, index=True)
    detected_type = Column(String(16), nullable=False)
    header_row = Column(Integer, nullable=False)
    payload = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    counts = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    expires_at = Column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        Index("ix_noor_import_drafts_owner", "principal_id", "school_id"),
        Index("ix_noor_import_drafts_expires_at", "expires_at"),
    )

