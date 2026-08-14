"""SQLAlchemy ORM Entities for platform domain."""
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


class ProductIssue(Base):
    __tablename__ = "product_issues"

    id = Column(String, primary_key=True, default=_uuid)
    issue_number = Column(Integer, unique=True, nullable=True)
    title = Column(String, nullable=True)
    issue_type = Column(String, nullable=False, index=True)
    status = Column(String, default="new", index=True)
    priority = Column(String, nullable=True, index=True)
    ai_suggested_priority = Column(String, nullable=True)
    section = Column(String, nullable=True, index=True)
    page = Column(String, nullable=True)
    employee_name = Column(String, nullable=True, index=True)
    employee_id = Column(String, nullable=True)
    account_type = Column(String, nullable=True)
    current_behavior = Column(Text, nullable=True)
    expected_behavior = Column(Text, nullable=True)
    steps_to_reproduce = Column(Text, nullable=True)
    reproducibility = Column(String, nullable=True)
    error_message = Column(Text, nullable=True)
    error_code = Column(String, nullable=True)
    screen_area = Column(String, nullable=True)
    affected_elements = Column(String, nullable=True)
    user_journey = Column(Text, nullable=True)
    pain_point = Column(Text, nullable=True)
    load_time = Column(String, nullable=True)
    affected_operation = Column(String, nullable=True)
    content_location = Column(String, nullable=True)
    content_type_field = Column(String, nullable=True)
    use_case = Column(Text, nullable=True)
    business_value = Column(Text, nullable=True)
    improvement_area = Column(Text, nullable=True)
    expected_impact = Column(Text, nullable=True)
    affected_role = Column(String, nullable=True)
    expected_access = Column(String, nullable=True)
    workflow_name = Column(String, nullable=True)
    broken_step = Column(String, nullable=True)
    integration_name = Column(String, nullable=True)
    api_endpoint = Column(String, nullable=True)
    additional_details = Column(Text, nullable=True)
    url = Column(String, nullable=True)
    device = Column(String, nullable=True)
    browser = Column(String, nullable=True)
    context = Column(JSONB, default=dict)
    description = Column(JSONB, default=dict)
    impact = Column(JSONB, default=list)
    technical = Column(JSONB, default=dict)
    business = Column(JSONB, default=dict)
    assignment = Column(JSONB, default=dict)
    ai = Column(JSONB, default=dict)
    attachments = Column(JSONB, default=list)
    submission_metadata = Column(JSONB, default=dict)
    visibility = Column(JSONB, default=dict)
    system = Column(JSONB, default=dict)
    assigned_team = Column(String, nullable=True, index=True)
    assigned_to = Column(String, nullable=True)
    assigned_to_name = Column(String, nullable=True)
    assigned_at = Column(DateTime(timezone=True), nullable=True)
    hakim_analysis = Column(JSONB, default=dict)
    generated_prompt = Column(Text, nullable=True)
    duplicate_of = Column(String, ForeignKey("product_issues.id", ondelete="SET NULL"), nullable=True)
    sla_deadline = Column(DateTime(timezone=True), nullable=True)
    sla_status = Column(String, nullable=True)
    sla_warning_emitted = Column(Boolean, default=False)
    feedback_requested = Column(Boolean, default=False)
    feedback_response = Column(Text, nullable=True)
    is_deleted = Column(Boolean, default=False, index=True)
    created_by = Column(String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    created_by_name = Column(String, nullable=True)
    created_by_role = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)
    resolved_at = Column(DateTime(timezone=True), nullable=True)

    creator = relationship("User", foreign_keys=[created_by], lazy="selectin")
    duplicate_source = relationship("ProductIssue", remote_side="ProductIssue.id", foreign_keys=[duplicate_of], lazy="noload")
    comments = relationship("IssueComment", back_populates="issue", lazy="noload")
    activity_logs = relationship("IssueActivityLog", back_populates="issue", lazy="noload")

    __table_args__ = (
        Index("idx_pg_issues_active_status_date", "is_deleted", "status", "created_at"),
        Index("idx_pg_issues_active_creator_date", "is_deleted", "created_by", "created_at"),
        Index("idx_pg_issues_status_priority_date", "status", "priority", "created_at"),
        Index("idx_pg_issues_status_team", "status", "assigned_team"),
        Index("idx_pg_issues_created_by_date", "created_by", "created_at"),
    )


class IssueComment(Base):
    __tablename__ = "issue_comments"

    id = Column(String, primary_key=True, default=_uuid)
    issue_id = Column(String, ForeignKey("product_issues.id", ondelete="CASCADE"), nullable=False, index=True)
    content = Column(Text, nullable=False)
    comment_type = Column(String, default="general")
    mentions = Column(JSONB, default=list)
    created_by = Column(String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    created_by_name = Column(String, nullable=True)
    created_by_role = Column(String, nullable=True)
    timestamp = Column(DateTime(timezone=True), default=_utcnow)

    issue = relationship("ProductIssue", back_populates="comments", lazy="selectin")
    author = relationship("User", foreign_keys=[created_by], lazy="selectin")

    __table_args__ = (
        Index("idx_pg_comments_issue_time", "issue_id", "timestamp"),
    )


class IssueDuplicateMap(Base):
    __tablename__ = "issue_duplicates_map"

    id = Column(String, primary_key=True, default=_uuid)
    issue_id = Column(String, ForeignKey("product_issues.id", ondelete="CASCADE"), nullable=False, index=True)
    duplicate_of = Column(String, ForeignKey("product_issues.id", ondelete="CASCADE"), nullable=False, index=True)
    confidence = Column(Float, nullable=True)
    detected_by = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        Index("idx_pg_duplicates_pair", "issue_id", "duplicate_of"),
    )


class IssueActivityLog(Base):
    __tablename__ = "issue_activity_log"

    id = Column(String, primary_key=True, default=_uuid)
    issue_id = Column(String, ForeignKey("product_issues.id", ondelete="CASCADE"), nullable=False, index=True)
    action = Column(String, nullable=False, index=True)
    field = Column(String, nullable=True)
    old_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)
    performed_by = Column(String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    performed_by_name = Column(String, nullable=True)
    details = Column(JSONB, default=dict)
    timestamp = Column(DateTime(timezone=True), default=_utcnow, index=True)

    issue = relationship("ProductIssue", back_populates="activity_logs", lazy="selectin")

    __table_args__ = (
        Index("idx_pg_activity_issue_time", "issue_id", "timestamp"),
    )


class BulkActionHistory(Base):
    __tablename__ = "bulk_action_history"

    id = Column(String, primary_key=True, default=_uuid)
    action_type = Column(String, nullable=False)
    issue_ids = Column(JSONB, default=list)
    field = Column(String, nullable=True)
    old_values = Column(JSONB, default=dict)
    new_value = Column(String, nullable=True)
    performed_by = Column(String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    performed_by_name = Column(String, nullable=True)
    performed_at = Column(DateTime(timezone=True), default=_utcnow, index=True)
    is_undone = Column(Boolean, default=False)
    undone_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("idx_pg_bulk_history_user_date", "performed_by", "performed_at"),
    )


class IssueVersion(Base):
    __tablename__ = "issue_versions"

    id = Column(String, primary_key=True, default=_uuid)
    issue_id = Column(String, ForeignKey("product_issues.id", ondelete="CASCADE"), nullable=False, index=True)
    revision = Column(Integer, nullable=False, default=0)
    tenant_id = Column(String, nullable=True)
    changed_by_user_id = Column(String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    changed_by_name = Column(String, nullable=True)
    changed_at = Column(DateTime(timezone=True), default=_utcnow, index=True)
    changed_fields = Column(JSONB, default=list)
    previous_values = Column(JSONB, default=dict)
    new_values = Column(JSONB, default=dict)

    __table_args__ = (
        Index("idx_pg_versions_issue_time", "issue_id", "changed_at"),
        Index("idx_pg_versions_issue_tenant", "issue_id", "tenant_id"),
        UniqueConstraint("issue_id", "revision", name="uq_issue_versions_issue_revision"),
    )


class PlatformSettings(Base):
    __tablename__ = "platform_settings"

    id = Column(String, primary_key=True, default=_uuid)
    type = Column(String, nullable=False, unique=True, index=True)
    data = Column(JSONB, default=dict)
    updated_by = Column(String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)


class SystemSetting(Base):
    __tablename__ = "system_settings"

    id = Column(String, primary_key=True, default=_uuid)
    type = Column(String, nullable=False, unique=True, index=True)
    data = Column(JSONB, default=dict)
    updated_by = Column(String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)


class Counter(Base):
    __tablename__ = "counters"

    id = Column(String, primary_key=True)
    seq = Column(Integer, default=0)


class LookupOption(Base):
    __tablename__ = "lookup_options"

    id = Column(String, primary_key=True, default=_uuid)
    category = Column(String, nullable=False, index=True)
    key = Column(String, nullable=False)
    value_ar = Column(String, nullable=True)
    value_en = Column(String, nullable=True)
    parent_key = Column(String, nullable=True)
    order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    school_id = Column(String, ForeignKey("schools.id", ondelete="SET NULL"), nullable=True, index=True)
    is_global = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        Index("idx_pg_lookup_category_key", "category", "key"),
        Index("idx_pg_lookup_school", "school_id", "category"),
    )


class GenericDocument(Base):
    __tablename__ = "generic_documents"

    id = Column(String, primary_key=True, default=_uuid)
    _collection = Column("collection", String, nullable=False, index=True)
    data = Column(JSONB, default=dict)
    created_at = Column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        Index("idx_generic_docs_collection", "collection"),
    )

