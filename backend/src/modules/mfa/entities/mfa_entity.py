"""SQLAlchemy ORM Entities for mfa domain."""
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


class MfaFactor(Base):
    """One enrolled second factor on a user.

    The same user may have many active rows (e.g. one ``webauthn`` row per
    registered device, plus one ``totp`` row). ``recovery_code`` rows are
    tracked separately in :class:`MfaRecoveryCode` — this table covers the
    "interactive" factors only.
    """
    __tablename__ = "mfa_factors"

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    kind = Column(String, nullable=False)  # totp | webauthn
    label = Column(String, nullable=True)
    is_primary = Column(Boolean, nullable=False, default=False)
    is_active = Column(Boolean, nullable=False, default=False)

    # TOTP — null for non-TOTP rows. Stored as PostgreSQL ``BYTEA`` because
    # Fernet ciphertext is binary and round-trips cleanly via asyncpg as
    # ``bytes`` / ``memoryview``.
    totp_secret_encrypted = Column(LargeBinary, nullable=True)

    # WebAuthn — null for non-WebAuthn rows. Credential ID + public key are
    # raw CBOR/COSE bytes; storing as ``BYTEA`` avoids any base64-roundtrip
    # ambiguity at compare time.
    webauthn_credential_id = Column(LargeBinary, nullable=True)
    webauthn_public_key = Column(LargeBinary, nullable=True)
    webauthn_sign_count = Column(Integer, nullable=True)
    webauthn_aaguid = Column(String, nullable=True)
    webauthn_attachment = Column(String, nullable=True)  # 'platform' | 'cross-platform'

    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    verified_at = Column(DateTime(timezone=True), nullable=True)
    last_used_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("idx_mfa_factors_user_kind", "user_id", "kind"),
        Index("idx_mfa_factors_user_active", "user_id", "is_active"),
        UniqueConstraint("webauthn_credential_id", name="uq_mfa_factors_webauthn_credential_id"),
    )


class MfaRecoveryCode(Base):
    """One single-use bcrypt-hashed recovery code. ``consumed_at`` is set on
    use; the row is kept so the hash chain in audit logs remains verifiable."""
    __tablename__ = "mfa_recovery_codes"

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    code_hash = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    consumed_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("idx_mfa_recovery_user_unused", "user_id", "consumed_at"),
    )


class MfaPendingChallenge(Base):
    """Short-lived row representing the "password OK, waiting for second
    factor" state. The login route inserts this and returns a JWT whose
    ``jti`` matches ``challenge_token_jti``; ``/auth/mfa/verify`` consumes
    it on success and deletes/marks it on completion. Capped TTL ≤ 10 min."""
    __tablename__ = "mfa_pending_challenges"

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    challenge_token_jti = Column(String, nullable=False, unique=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    attempts = Column(Integer, nullable=False, default=0)
    consumed_at = Column(DateTime(timezone=True), nullable=True)
    ip = Column(String, nullable=True)
    user_agent = Column(String, nullable=True)
    remember_me = Column(Boolean, nullable=False, default=False)

    __table_args__ = (
        Index("idx_mfa_pending_expires", "expires_at"),
    )


class MfaEmailOtp(Base):
    """One emailed 6-digit OTP for Tier B/C login. Stored as salted-sha256;
    the salt lives on the same row so verify can recompute without
    decrypting anything."""
    __tablename__ = "mfa_email_otps"

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    code_hash = Column(String, nullable=False)
    code_salt = Column(String, nullable=False)
    challenge_id = Column(String, ForeignKey("mfa_pending_challenges.id", ondelete="CASCADE"), nullable=False)
    sent_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    attempts = Column(Integer, nullable=False, default=0)
    consumed_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("idx_mfa_email_otps_challenge", "challenge_id"),
    )


class MfaWebauthnChallenge(Base):
    """Random bytes used as the WebAuthn ceremony challenge for either an
    enrol (``purpose='enroll'``) or verify (``purpose='verify'``) flow.
    Short TTL (≤ 5 min)."""
    __tablename__ = "mfa_webauthn_challenges"

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    purpose = Column(String, nullable=False)  # 'enroll' | 'verify'
    challenge = Column(LargeBinary, nullable=False)  # raw random bytes
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        Index("idx_mfa_webauthn_challenges_expires", "expires_at"),
    )

