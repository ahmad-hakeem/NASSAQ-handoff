"""SQLAlchemy ORM Entities for bulk_import domain."""
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import JSONB
from src.core.database.db import Base


def _uuid():
    return str(uuid.uuid4())


def _utcnow():
    return datetime.now(timezone.utc)


class BulkImportBatch(Base):
    """Persistent record of a bulk import batch (e.g. students from Excel)."""

    __tablename__ = "bulk_import_batches"

    id = Column(String, primary_key=True, default=_uuid)
    school_id = Column(String, ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True)
    actor_id = Column(String, nullable=True)
    actor_name = Column(String, nullable=True)
    import_type = Column(String, nullable=False, default="students")
    file_name = Column(String, nullable=True)
    imported_count = Column(Integer, nullable=False, default=0)
    student_ids = Column(JSONB, nullable=True, default=list)
    created_class_ids = Column(JSONB, nullable=True, default=list)
    created_parent_ids = Column(JSONB, nullable=True, default=list)
    created_parent_user_ids = Column(JSONB, nullable=True, default=list)
    status = Column(String, nullable=False, default="active")
    created_at = Column(DateTime(timezone=True), default=_utcnow)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    __table_args__ = (
        Index("idx_bulk_import_batches_school_status", "school_id", "status"),
    )
