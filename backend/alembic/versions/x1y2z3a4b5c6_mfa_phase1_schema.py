"""mfa phase 1 — schema, append-only trigger, hash chain (mfa.* scope)

Revision ID: x1y2z3a4b5c6
Revises: w1x2y3z4a5b6
Create Date: 2026-05-11

Adds the ground floor for role-tiered Multi-Factor Authentication (Task #169).

What this migration creates
---------------------------
1. ``mfa_factors`` — one row per enrolled second factor on a user
   (kind ∈ {totp, webauthn, recovery_code}).
2. ``mfa_recovery_codes`` — one row per single-use bcrypt-hashed recovery code.
3. ``mfa_pending_challenges`` — short-lived rows representing the post-password
   pre-token state where the backend has accepted the password but is still
   waiting for the second-factor proof.
4. ``mfa_email_otps`` — short-lived salted-sha256 hashed 6-digit codes for
   teacher / parent email-OTP login (Tier B, Tier C).
5. ``mfa_webauthn_challenges`` — short-lived random bytes used as the
   WebAuthn ceremony challenge for either enrol or verify.

It also extends ``users`` with the five flags the policy + recovery-code
lifecycle need (``mfa_required``, ``mfa_enrolled_at``,
``mfa_must_restore_factor``, ``mfa_recovery_codes_generated_at``,
``mfa_recovery_codes_acknowledged``), and ``audit_logs`` with two columns
(``prev_hash``, ``row_hash``) that form a per-tenant tamper-evident chain
*scoped to mfa.* rows only*. Generalisation of the chain to other
sensitive-admin action prefixes is explicitly deferred (see plan section
"Append-only & export readiness").

A database trigger ``audit_logs_mfa_immutable`` rejects UPDATE and DELETE
on any ``audit_logs`` row whose ``action`` starts with ``mfa.`` so a buggy
or malicious application path cannot rewrite MFA history.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from migration_idempotent import has_table, has_column, has_constraint


revision: str = "x1y2z3a4b5c6"
down_revision: Union[str, Sequence[str], None] = "w1x2y3z4a5b6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ---- mfa_factors ----------------------------------------------------
    if not has_table("mfa_factors"):
        op.create_table(
            "mfa_factors",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("user_id", sa.String(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("kind", sa.String(), nullable=False),  # totp | webauthn | recovery_code
            sa.Column("label", sa.String(), nullable=True),
            sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.false()),
            # encrypted TOTP seed (Fernet ciphertext) — null for non-TOTP rows
            sa.Column("totp_secret_encrypted", sa.LargeBinary(), nullable=True),
            # WebAuthn — null for non-WebAuthn rows
            sa.Column("webauthn_credential_id", sa.LargeBinary(), nullable=True),
            sa.Column("webauthn_public_key", sa.LargeBinary(), nullable=True),
            sa.Column("webauthn_sign_count", sa.Integer(), nullable=True),
            sa.Column("webauthn_aaguid", sa.String(), nullable=True),
            # 'platform' or 'cross-platform' — UX hint for "this device" vs "external key"
            sa.Column("webauthn_attachment", sa.String(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        )
    op.create_index("idx_mfa_factors_user_kind", "mfa_factors", ["user_id", "kind"], if_not_exists=True)
    op.create_index("idx_mfa_factors_user_active", "mfa_factors", ["user_id", "is_active"], if_not_exists=True)
    # WebAuthn credential ids must be globally unique to prevent cross-account replay
    if not has_constraint("mfa_factors", "uq_mfa_factors_webauthn_credential_id"):
        op.create_unique_constraint(
            "uq_mfa_factors_webauthn_credential_id",
            "mfa_factors",
            ["webauthn_credential_id"],
        )

    # ---- mfa_recovery_codes ---------------------------------------------
    if not has_table("mfa_recovery_codes"):
        op.create_table(
            "mfa_recovery_codes",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("user_id", sa.String(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("code_hash", sa.String(), nullable=False),  # bcrypt
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        )
    op.create_index("idx_mfa_recovery_user_unused", "mfa_recovery_codes", ["user_id", "consumed_at"], if_not_exists=True)

    # ---- mfa_pending_challenges -----------------------------------------
    if not has_table("mfa_pending_challenges"):
        op.create_table(
            "mfa_pending_challenges",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("user_id", sa.String(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("challenge_token_jti", sa.String(), nullable=False, unique=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("ip", sa.String(), nullable=True),
            sa.Column("user_agent", sa.String(), nullable=True),
            sa.Column("remember_me", sa.Boolean(), nullable=False, server_default=sa.false()),
        )
    op.create_index("idx_mfa_pending_expires", "mfa_pending_challenges", ["expires_at"], if_not_exists=True)

    # ---- mfa_email_otps -------------------------------------------------
    if not has_table("mfa_email_otps"):
        op.create_table(
            "mfa_email_otps",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("user_id", sa.String(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
            # salted sha256: stored as hex digest of (salt || code); salt stored separately
            sa.Column("code_hash", sa.String(), nullable=False),
            sa.Column("code_salt", sa.String(), nullable=False),
            sa.Column("challenge_id", sa.String(), sa.ForeignKey("mfa_pending_challenges.id", ondelete="CASCADE"), nullable=False),
            sa.Column("sent_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        )
    op.create_index("idx_mfa_email_otps_challenge", "mfa_email_otps", ["challenge_id"], if_not_exists=True)

    # ---- mfa_webauthn_challenges ----------------------------------------
    if not has_table("mfa_webauthn_challenges"):
        op.create_table(
            "mfa_webauthn_challenges",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("user_id", sa.String(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("purpose", sa.String(), nullable=False),  # 'enroll' | 'verify'
            sa.Column("challenge", sa.LargeBinary(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        )
    op.create_index("idx_mfa_webauthn_challenges_expires", "mfa_webauthn_challenges", ["expires_at"], if_not_exists=True)

    # ---- users column additions -----------------------------------------
    with op.batch_alter_table("users") as batch:
        if not has_column("users", "mfa_required"):
            batch.add_column(sa.Column("mfa_required", sa.Boolean(), nullable=False, server_default=sa.false()))
        if not has_column("users", "mfa_enrolled_at"):
            batch.add_column(sa.Column("mfa_enrolled_at", sa.DateTime(timezone=True), nullable=True))
        if not has_column("users", "mfa_must_restore_factor"):
            batch.add_column(sa.Column("mfa_must_restore_factor", sa.Boolean(), nullable=False, server_default=sa.false()))
        if not has_column("users", "mfa_recovery_codes_generated_at"):
            batch.add_column(sa.Column("mfa_recovery_codes_generated_at", sa.DateTime(timezone=True), nullable=True))
        if not has_column("users", "mfa_recovery_codes_acknowledged"):
            batch.add_column(sa.Column("mfa_recovery_codes_acknowledged", sa.Boolean(), nullable=False, server_default=sa.false()))

    # Backfill ``mfa_required`` for existing users in Tier A roles. The
    # mfa_policy helper is the source of truth at request time; this column
    # is only a denormalised cache for fast filtering / dashboards.
    op.execute(
        """
        UPDATE users
           SET mfa_required = TRUE
         WHERE role IN (
            'platform_admin',
            'platform_sub_admin',
            'platform_operations_manager',
            'platform_technical_admin',
            'platform_support_specialist',
            'platform_data_analyst',
            'platform_security_officer',
            'platform_sales',
            'platform_marketing',
            'platform_quality',
            'school_principal',
            'school_admin',
            'school_sub_admin',
            'independent_teacher'
         )
        """
    )

    # ---- audit_logs hash-chain columns (mfa.* scope only) ---------------
    with op.batch_alter_table("audit_logs") as batch:
        if not has_column("audit_logs", "prev_hash"):
            batch.add_column(sa.Column("prev_hash", sa.String(length=64), nullable=True))
        if not has_column("audit_logs", "row_hash"):
            batch.add_column(sa.Column("row_hash", sa.String(length=64), nullable=True))

    # ---- append-only trigger for mfa.* audit rows -----------------------
    # Application code must NEVER mutate a row whose action starts with
    # ``mfa.``. Enforced at the database layer so a buggy migration script,
    # an over-broad UPDATE, or a compromised admin path cannot rewrite MFA
    # history.  Non-mfa rows keep their existing mutability (other audit
    # surfaces are out of scope for this task — see plan).
    op.execute(
        """
        CREATE OR REPLACE FUNCTION audit_logs_mfa_immutable_fn()
        RETURNS trigger AS $$
        BEGIN
          IF TG_OP = 'UPDATE' THEN
            IF OLD.action LIKE 'mfa.%' THEN
              RAISE EXCEPTION 'audit_logs row with action % is append-only', OLD.action
                USING ERRCODE = 'check_violation';
            END IF;
            RETURN NEW;
          ELSIF TG_OP = 'DELETE' THEN
            IF OLD.action LIKE 'mfa.%' THEN
              RAISE EXCEPTION 'audit_logs row with action % is append-only', OLD.action
                USING ERRCODE = 'check_violation';
            END IF;
            RETURN OLD;
          END IF;
          RETURN NULL;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute("DROP TRIGGER IF EXISTS audit_logs_mfa_immutable_trg ON audit_logs;")
    op.execute(
        """
        CREATE TRIGGER audit_logs_mfa_immutable_trg
        BEFORE UPDATE OR DELETE ON audit_logs
        FOR EACH ROW EXECUTE FUNCTION audit_logs_mfa_immutable_fn();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS audit_logs_mfa_immutable_trg ON audit_logs;")
    op.execute("DROP FUNCTION IF EXISTS audit_logs_mfa_immutable_fn();")

    with op.batch_alter_table("audit_logs") as batch:
        batch.drop_column("row_hash")
        batch.drop_column("prev_hash")

    with op.batch_alter_table("users") as batch:
        batch.drop_column("mfa_recovery_codes_acknowledged")
        batch.drop_column("mfa_recovery_codes_generated_at")
        batch.drop_column("mfa_must_restore_factor")
        batch.drop_column("mfa_enrolled_at")
        batch.drop_column("mfa_required")

    op.drop_index("idx_mfa_webauthn_challenges_expires", table_name="mfa_webauthn_challenges")
    op.drop_table("mfa_webauthn_challenges")

    op.drop_index("idx_mfa_email_otps_challenge", table_name="mfa_email_otps")
    op.drop_table("mfa_email_otps")

    op.drop_index("idx_mfa_pending_expires", table_name="mfa_pending_challenges")
    op.drop_table("mfa_pending_challenges")

    op.drop_index("idx_mfa_recovery_user_unused", table_name="mfa_recovery_codes")
    op.drop_table("mfa_recovery_codes")

    op.drop_constraint("uq_mfa_factors_webauthn_credential_id", "mfa_factors", type_="unique")
    op.drop_index("idx_mfa_factors_user_active", table_name="mfa_factors")
    op.drop_index("idx_mfa_factors_user_kind", table_name="mfa_factors")
    op.drop_table("mfa_factors")
