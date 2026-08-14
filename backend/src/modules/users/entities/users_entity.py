"""SQLAlchemy ORM Entities for users domain."""
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


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=_uuid)
    email = Column(String, unique=True, nullable=False, index=True)
    phone = Column(String, nullable=True, index=True)
    national_id = Column(String, nullable=True, index=True)
    full_name = Column(String, nullable=False)
    full_name_en = Column(String, nullable=True)
    title = Column(String, nullable=True)
    password_hash = Column(String, nullable=False)
    must_change_password = Column(Boolean, default=True)
    last_password_change = Column(DateTime(timezone=True), nullable=True)
    reset_token_hash = Column(String, nullable=True)
    reset_token_created_at = Column(DateTime(timezone=True), nullable=True)
    failed_login_attempts = Column(Integer, default=0)
    locked_until = Column(DateTime(timezone=True), nullable=True)
    status = Column(String, default="active")
    is_active = Column(Boolean, default=True)
    role = Column(String, nullable=False, index=True)
    linked_roles = Column(JSONB, default=list)
    preferred_language = Column(String, default="ar")
    preferred_theme = Column(String, default="light")
    # User-configurable display preferences (persisted via PUT /users/me/preferences).
    # These three columns were missing, causing the preferences endpoint to
    # silently drop saves and always return the hardcoded defaults.
    time_format = Column(String, default="12h")
    date_format = Column(String, default="dd/mm/yyyy")
    first_day_of_week = Column(String, default="sunday")
    avatar_url = Column(String, nullable=True)

    @validates("avatar_url")
    def _validate_avatar_url_bounded(self, key, value):
        # ORM-level chokepoint: no write path (gd_* helpers, engines
        # constructing User(...) directly, attribute assignment) may persist
        # an unnormalised inline image. See utils.avatar_image.
        from src.common.utils.avatar_image import assert_stored_image_bounded
        assert_stored_image_bounded("users", key, value)
        return value

    tenant_id = Column(String, ForeignKey("schools.id", ondelete="SET NULL"), nullable=True, index=True)
    primary_tenant_id = Column(String, nullable=True)
    has_generic_name = Column(Boolean, default=False)
    email_verified = Column(Boolean, default=False)
    phone_verified = Column(Boolean, default=False)
    teacher_id = Column(String, nullable=True)
    student_id = Column(String, nullable=True)
    parent_id = Column(String, nullable=True)
    created_by = Column(String, nullable=True)
    last_login = Column(DateTime(timezone=True), nullable=True)
    region = Column(String, nullable=True)
    city = Column(String, nullable=True)
    educational_department = Column(String, nullable=True)
    school_name_ar = Column(String, nullable=True)
    school_name_en = Column(String, nullable=True)
    permissions = Column(JSONB, default=list)
    notification_settings = Column(JSONB, nullable=True)

    # MFA (Task #169) — denormalised flags read by the policy helper and
    # the recovery-code lifecycle. ``mfa_required`` is a cache of
    # ``mfa_policy.required_for(user) is not None`` for fast filtering;
    # ``mfa_policy`` remains the source of truth at request time.
    mfa_required = Column(Boolean, nullable=False, default=False)
    mfa_enrolled_at = Column(DateTime(timezone=True), nullable=True)
    # Set true when a recovery code is consumed; cleared by a successful
    # passkey/TOTP re-enrolment. Read by ``require_recent_mfa`` to refuse
    # Tier A sensitive routes with MFA_RESTORE_REQUIRED while true.
    mfa_must_restore_factor = Column(Boolean, nullable=False, default=False)
    mfa_recovery_codes_generated_at = Column(DateTime(timezone=True), nullable=True)
    # Flips true once the user has clicked the "I have saved my recovery
    # codes in a safe place" checkbox in the forced presentation modal.
    mfa_recovery_codes_acknowledged = Column(Boolean, nullable=False, default=False)

    # Task #250 — IT first-login onboarding tour. NULL means "show the
    # welcome card next time this user lands on their IT dashboard";
    # non-IT roles always carry NULL here (the trigger surfaces are
    # IT-only).
    it_onboarding_completed_at = Column(DateTime(timezone=True), nullable=True)

    # Parent Charter (ميثاق ولي الأمر) blocking guard. NULL means the
    # parent has not accepted the mandatory charter yet; the FE
    # ``CharterGuard`` intercepts every /parent/* route until this is
    # set. Stored as a timestamp (rather than a boolean) so the
    # acceptance moment is auditable.
    charter_accepted_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), default=_utcnow)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    tenant = relationship("School", foreign_keys=[tenant_id], lazy="selectin")
    audit_logs = relationship("AuditLog", back_populates="user", foreign_keys="AuditLog.performed_by", lazy="noload")
    notifications = relationship("Notification", back_populates="user", foreign_keys="Notification.user_id", lazy="noload")

    __table_args__ = (
        Index("idx_pg_users_role_tenant", "role", "tenant_id"),
        Index("idx_pg_users_tenant_active", "tenant_id", "is_active"),
    )


class UserSession(Base):
    __tablename__ = "user_sessions"

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, nullable=False, index=True)
    jti = Column(String(64), nullable=False, unique=True, index=True)
    device = Column(String(128), nullable=True)
    browser = Column(String(64), nullable=True)
    os = Column(String(64), nullable=True)
    ip_address = Column(String(64), nullable=True)
    user_agent = Column(Text, nullable=True)
    location = Column(String(128), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    last_seen_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    revoked_at = Column(DateTime(timezone=True), nullable=True, index=True)
    # Task #374 — refresh token jti + family id paired with this session's
    # access jti. Required so single-session and end-all revocation can
    # block the refresh path too (otherwise the device silently revives
    # on /auth/refresh after its short-lived access token expires).
    refresh_jti = Column(String(64), nullable=True, index=True)
    refresh_family_id = Column(String(64), nullable=True, index=True)
    # Task #374 follow-up — refresh token's own ``exp``. Used by
    # settings_routes._revoke_session_refresh_chain so the revoked
    # refresh JTI lives in revoked_tokens until the refresh token
    # actually expires (not the access token's ~15 min lifetime, which
    # would let the cleanup loop purge the revocation early).
    refresh_expires_at = Column(DateTime(timezone=True), nullable=True)


class RevokedToken(Base):
    __tablename__ = "revoked_tokens"

    jti = Column(String(36), primary_key=True, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    revoked_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)

    __table_args__ = (
        Index("ix_revoked_tokens_expires_at", "expires_at"),
    )

