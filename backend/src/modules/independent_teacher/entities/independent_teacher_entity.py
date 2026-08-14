"""SQLAlchemy ORM Entities for independent_teacher domain."""
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


class ParentInvitation(Base):
    """IT Phase 2 §6.2 (Task #205) — parent invitation lifecycle row.

    One row per minted invitation; a single ``(workspace_school_id,
    student_id)`` may have at most one ``status='pending'`` row at a time
    (enforced in the route layer via the composite read index, not a DB
    unique constraint, so cancelled/expired/accepted history coexists).
    """
    __tablename__ = "parent_invitations"

    id = Column(String, primary_key=True, default=_uuid)
    workspace_school_id = Column(
        String, ForeignKey("schools.id", ondelete="CASCADE"),
        nullable=False,
    )
    parent_email = Column(String, nullable=True)
    parent_phone = Column(String, nullable=True)
    student_id = Column(
        String, ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
    )
    token_hash = Column(String, nullable=False)
    sent_at = Column(DateTime(timezone=True), nullable=False)
    accepted_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    status = Column(String, nullable=False)
    created_by = Column(String, nullable=True)
    created_at = Column(
        DateTime(timezone=True), default=_utcnow, nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )
    updated_at = Column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow,
        nullable=False, server_default=text("CURRENT_TIMESTAMP"),
    )

    __table_args__ = (
        Index(
            "ix_parent_invitations_workspace_student_status",
            "workspace_school_id", "student_id", "status",
        ),
        Index("ix_parent_invitations_token_hash", "token_hash"),
    )


class WorkspaceCollaborator(Base):
    """IT Phase 2 §6.7 (Task #210) — cross-workspace co-teaching link.

    Links one host IT workspace's class to exactly one collaborator IT
    workspace. The §8 single-tenant invariant is intentionally relaxed
    only for the named ``class_id``, never the wider workspace.
    """
    __tablename__ = "workspace_collaborators"

    id = Column(String, primary_key=True, default=_uuid)
    host_school_id = Column(
        String, ForeignKey("schools.id", ondelete="CASCADE"),
        nullable=False,
    )
    collaborator_school_id = Column(
        String, ForeignKey("schools.id", ondelete="CASCADE"),
        nullable=True,
    )
    class_id = Column(
        String, ForeignKey("classes.id", ondelete="CASCADE"),
        nullable=False,
    )
    collaborator_email = Column(String, nullable=True)
    collaborator_user_id = Column(String, nullable=True)
    token_hash = Column(String, nullable=False)
    scope = Column(
        JSONB, nullable=False, default=lambda: {"mode": "read"},
        server_default=text("'{\"mode\": \"read\"}'::jsonb"),
    )
    status = Column(String, nullable=False)
    sent_at = Column(DateTime(timezone=True), nullable=False)
    accepted_at = Column(DateTime(timezone=True), nullable=True)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_by = Column(String, nullable=True)
    created_at = Column(
        DateTime(timezone=True), default=_utcnow, nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )
    updated_at = Column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow,
        nullable=False, server_default=text("CURRENT_TIMESTAMP"),
    )

    __table_args__ = (
        Index(
            "ux_workspace_collab_accepted",
            "host_school_id", "collaborator_school_id", "class_id",
            unique=True,
            postgresql_where=text("status = 'accepted'"),
        ),
        Index(
            "ux_workspace_collab_pending",
            "host_school_id", "class_id", "collaborator_email",
            unique=True,
            postgresql_where=text("status = 'pending'"),
        ),
        Index(
            "ix_workspace_collab_host_class_status",
            "host_school_id", "class_id", "status",
        ),
        Index(
            "ix_workspace_collab_collab_status",
            "collaborator_school_id", "status",
        ),
        Index("ix_workspace_collab_token_hash", "token_hash"),
    )


class WorkspaceQuota(Base):
    """IT Phase 2 §6.1 (Task #207) — per-workspace quota row.

    PK is ``workspace_school_id`` (always points at the synthetic
    ``itw_{user_id}`` schools row). Counters reset on UTC-day boundary
    in application code.
    """
    __tablename__ = "workspace_quota"

    workspace_school_id = Column(
        String, ForeignKey("schools.id", ondelete="CASCADE"),
        primary_key=True, nullable=False,
    )
    max_students = Column(Integer, nullable=False, default=200, server_default=text("200"))
    max_classes = Column(Integer, nullable=False, default=5, server_default=text("5"))
    max_imports_per_day = Column(Integer, nullable=False, default=5, server_default=text("5"))
    max_rows_per_import = Column(Integer, nullable=False, default=200, server_default=text("200"))
    imports_today = Column(Integer, nullable=False, default=0, server_default=text("0"))
    imports_today_date = Column(Date, nullable=True)
    # IT Phase 2 §6.4 (Task #209) — daily lesson-plan counter (UTC-day reset
    # in app code, mirrors imports_today).
    lesson_plans_today = Column(Integer, nullable=False, default=0, server_default=text("0"))
    lesson_plans_today_date = Column(Date, nullable=True)
    # Task #275 — opt-in weekly auto-export schedule for IT workspaces.
    auto_export_enabled = Column(Boolean, nullable=False, default=False, server_default=text("false"))
    auto_export_dow = Column(SmallInteger, nullable=True)
    auto_export_hour = Column(SmallInteger, nullable=True)
    auto_export_last_run_at = Column(DateTime(timezone=True), nullable=True)
    auto_export_last_status = Column(Text, nullable=True)
    created_at = Column(
        DateTime(timezone=True), default=_utcnow, nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )
    updated_at = Column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow,
        nullable=False, server_default=text("CURRENT_TIMESTAMP"),
    )

