"""
NASSAQ — MFA routes (Task #169)

Step 2: pending-challenge plumbing + factor inventory.
Step 3: TOTP enrol begin/confirm + TOTP verify-during-login.

Authentication model
--------------------
Routes split into three groups by what bearer token they accept:

* **Enrol routes** (``/auth/mfa/totp/enroll/...``) require a normal
  ``type=access`` token — the user is already logged in and wants to add
  a factor.
* **Challenge-only routes** (``/auth/mfa/verify``) require the short-lived
  ``type=mfa_challenge`` token minted by ``/auth/login``. They MUST NOT
  accept access tokens — that would defeat the second-factor requirement
  by letting a stolen access token "verify" itself.
* **Hybrid** (``/auth/mfa/factors``) accepts either, because the login
  challenge UI needs to show what kinds the user can verify with before
  the user has any access token.

The actual factor verification logic for non-TOTP kinds lands in Steps
4-6.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import List, Optional

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

from dependencies import (
    db,
    JWT_SECRET,
    JWT_ALGORITHM,
    create_access_token,
    create_refresh_token,
    get_current_user,
)
from engines.audit_engine import AuditLogEngine
from engines.sql_utils import gd_find, gd_find_one, gd_insert, gd_update_one
from repositories import Repos
from services import mfa_crypto, mfa_policy
from shared_models import TokenResponse, UserResponse, UserRole

logger = logging.getLogger("nassaq.mfa")

router = APIRouter()
_security = HTTPBearer(auto_error=True)


# ---------------------------------------------------------------------------
# challenge-token helpers (Step 2)
# ---------------------------------------------------------------------------

async def _resolve_challenge(
    credentials: HTTPAuthorizationCredentials,
) -> tuple[dict, dict]:
    """Decode the challenge JWT, look up the matching ``mfa_pending_challenges``
    row, and return ``(challenge_row, user_row)``. Raises 401 on any failure.
    Does NOT consume the challenge — callers do that explicitly on success.
    """
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="انتهت صلاحية رمز التحقق")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="رمز تحقق غير صالح")

    if payload.get("type") != "mfa_challenge":
        raise HTTPException(status_code=401, detail="رمز تحقق غير صالح")

    jti = payload.get("jti")
    user_id = payload.get("sub")
    if not jti or not user_id:
        raise HTTPException(status_code=401, detail="رمز تحقق غير صالح")

    challenge = await gd_find_one(db.session, "mfa_pending_challenges", {"challenge_token_jti": jti})
    if not challenge:
        raise HTTPException(status_code=401, detail="رمز التحقق غير معروف أو مستهلك")
    if challenge.get("consumed_at"):
        raise HTTPException(status_code=401, detail="تم استخدام رمز التحقق مسبقاً")

    expires_at = challenge.get("expires_at")
    if expires_at:
        try:
            exp_dt = expires_at if isinstance(expires_at, datetime) else datetime.fromisoformat(str(expires_at).replace("Z", "+00:00"))
            if exp_dt.tzinfo is None:
                exp_dt = exp_dt.replace(tzinfo=timezone.utc)
            if exp_dt < datetime.now(timezone.utc):
                raise HTTPException(status_code=401, detail="انتهت صلاحية رمز التحقق")
        except HTTPException:
            raise
        except Exception as exc:
            logger.debug(f"_resolve_challenge: expires_at parse failed: {exc}")

    if (challenge.get("attempts") or 0) >= 5:
        raise HTTPException(status_code=429, detail="عدد محاولات التحقق تجاوز الحد المسموح")

    user = await gd_find_one(db.session, "users", {"id": user_id})
    if not user or not user.get("is_active", True):
        raise HTTPException(status_code=401, detail="الحساب غير متاح")

    return challenge, user


async def _bump_challenge_attempts(challenge: dict) -> None:
    """Increment the attempts counter on a pending challenge after a failed
    verify. Each row is hard-capped at 5 attempts by ``_resolve_challenge``."""
    try:
        await gd_update_one(
            db.session,
            "mfa_pending_challenges",
            {"id": challenge["id"]},
            {"attempts": (challenge.get("attempts") or 0) + 1},
        )
    except Exception as exc:
        logger.debug(f"_bump_challenge_attempts failed: {exc}")


async def _consume_challenge(challenge: dict) -> None:
    """Mark a pending challenge as consumed (one-shot)."""
    await gd_update_one(
        db.session,
        "mfa_pending_challenges",
        {"id": challenge["id"]},
        {"consumed_at": datetime.now(timezone.utc)},
    )


async def _complete_mfa_login(
    user: dict,
    challenge: dict,
    factor_kind: str,
    request: Optional[Request],
) -> TokenResponse:
    """Mint access+refresh tokens, record the session, mark the challenge
    consumed, mark the factor as last-used, and write the success audit
    row. Shared by every successful factor verification path (Steps 3-6)."""
    user_id = user["id"]
    token_payload = {"sub": user_id, "role": user["role"]}
    if user.get("tenant_id"):
        token_payload["tenant_id"] = user["tenant_id"]
    if user.get("school_id"):
        token_payload["school_id"] = user["school_id"]
    access = create_access_token(token_payload)
    try:
        access_jti = jwt.decode(access, JWT_SECRET, algorithms=[JWT_ALGORITHM]).get("jti")
    except Exception:
        access_jti = None
    refresh = create_refresh_token(
        token_payload,
        remember_me=bool(challenge.get("remember_me")),
        linked_access_jti=access_jti,
    )

    # Best-effort session row (lazy-import to avoid circular import with auth_routes_mod)
    try:
        from routes.auth_routes_mod import _record_session_from_token
        ip = request.client.host if request and request.client else None
        ua = request.headers.get("user-agent") if request else None
        await _record_session_from_token(db.session, access, user_id, ip, ua)
    except Exception as exc:
        logger.debug(f"_complete_mfa_login: session record failed: {exc}")

    await _consume_challenge(challenge)

    audit = AuditLogEngine(Repos(db.session))
    await audit.log_auth_event(
        action="mfa.login.success",
        user_id=user_id,
        tenant_id=user.get("tenant_id"),
        success=True,
        email=user.get("email"),
        reason=factor_kind,
    )

    from engines.name_validation import is_generic_name
    user_response = UserResponse(
        id=user_id,
        email=user["email"],
        full_name=user["full_name"],
        full_name_en=user.get("full_name_en"),
        role=UserRole(user["role"]),
        tenant_id=user.get("tenant_id"),
        phone=user.get("phone"),
        avatar_url=user.get("avatar_url"),
        is_active=user.get("is_active") if user.get("is_active") is not None else True,
        must_change_password=bool(user.get("must_change_password")),
        has_generic_name=is_generic_name(user.get("full_name")),
        preferred_language=user.get("preferred_language") or "ar",
        preferred_theme=user.get("preferred_theme") or "light",
        created_at=user.get("created_at") or "",
        teacher_id=user.get("teacher_id"),
        student_id=user.get("student_id"),
        parent_id=user.get("parent_id"),
    )

    # Surface the "show recovery codes again" hint if the user has never
    # acknowledged them and has codes generated.
    pending_view = bool(
        user.get("mfa_recovery_codes_generated_at")
        and not user.get("mfa_recovery_codes_acknowledged")
    )

    return TokenResponse(
        access_token=access,
        refresh_token=refresh,
        user=user_response,
        mfa_recovery_codes_pending_view=pending_view,
    )


# ---------------------------------------------------------------------------
# Factor inventory (Step 2)
# ---------------------------------------------------------------------------

class MfaFactorView(BaseModel):
    id: str
    kind: str  # 'totp' | 'webauthn'
    label: Optional[str] = None
    is_primary: bool = False
    is_active: bool = False
    webauthn_attachment: Optional[str] = None
    last_used_at: Optional[str] = None


class MfaFactorsResponse(BaseModel):
    user_id: str
    tier: Optional[str] = None
    allowed_kinds: List[str]
    factors: List[MfaFactorView]
    unused_recovery_codes: int = 0
    mfa_must_restore_factor: bool = False
    mfa_recovery_codes_acknowledged: bool = False


@router.get("/auth/mfa/factors", response_model=MfaFactorsResponse)
async def list_mfa_factors(
    credentials: HTTPAuthorizationCredentials = Depends(_security),
):
    """List enrolled factors. Accepts access OR mfa_challenge tokens."""
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="انتهت صلاحية الرمز")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="رمز غير صالح")

    if payload.get("type") not in ("access", "mfa_challenge"):
        raise HTTPException(status_code=401, detail="نوع الرمز غير مسموح")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="رمز غير صالح")

    user = await gd_find_one(db.session, "users", {"id": user_id})
    if not user:
        raise HTTPException(status_code=401, detail="المستخدم غير موجود")

    rows = await gd_find(db.session, "mfa_factors", {"user_id": user_id, "is_active": True})
    factors = [
        MfaFactorView(
            id=str(r.get("id")),
            kind=r.get("kind"),
            label=r.get("label"),
            is_primary=bool(r.get("is_primary")),
            is_active=bool(r.get("is_active")),
            webauthn_attachment=r.get("webauthn_attachment"),
            last_used_at=str(r.get("last_used_at")) if r.get("last_used_at") else None,
        )
        for r in (rows or [])
    ]

    rc_rows = await gd_find(db.session, "mfa_recovery_codes", {"user_id": user_id, "consumed_at": None})
    unused = len(rc_rows or [])

    tier = mfa_policy.required_for(user)
    return MfaFactorsResponse(
        user_id=user_id,
        tier=tier.value if tier else None,
        allowed_kinds=sorted(mfa_policy.allowed_factor_kinds(user)),
        factors=factors,
        unused_recovery_codes=unused,
        mfa_must_restore_factor=bool(user.get("mfa_must_restore_factor")),
        mfa_recovery_codes_acknowledged=bool(user.get("mfa_recovery_codes_acknowledged")),
    )


# ---------------------------------------------------------------------------
# TOTP — enrol begin / confirm (Step 3)
# ---------------------------------------------------------------------------

class TotpEnrollBeginResponse(BaseModel):
    factor_id: str
    otpauth_uri: str
    qr_svg: str
    issuer: str = "NASSAQ"
    account_label: str


class TotpEnrollConfirmRequest(BaseModel):
    factor_id: str = Field(..., min_length=8)
    code: str = Field(..., min_length=6, max_length=10)
    label: Optional[str] = Field(None, max_length=64)


class TotpEnrollConfirmResponse(BaseModel):
    factor_id: str
    activated_at: str
    is_primary: bool


def _ensure_totp_kind_allowed(user: dict) -> None:
    """Refuse TOTP enrolment for roles whose policy doesn't allow it."""
    if "totp" not in mfa_policy.allowed_factor_kinds(user):
        raise HTTPException(
            status_code=403,
            detail="نوع التحقق هذا غير متاح لحسابك",
        )


@router.post("/auth/mfa/totp/enroll/begin", response_model=TotpEnrollBeginResponse)
async def totp_enroll_begin(current_user: dict = Depends(get_current_user)):
    """Generate a fresh TOTP secret, store it encrypted as an *inactive*
    factor row, and return the otpauth URI + an inline QR SVG.

    The factor row is created in ``is_active=False`` state. The user must
    successfully verify a generated code via ``/auth/mfa/totp/enroll/confirm``
    before it can be used to log in. Stale unconfirmed rows are tolerated:
    re-running ``begin`` simply creates a new pending factor — the old one
    will never be activated and is harmless beyond a small row.
    """
    _ensure_totp_kind_allowed(current_user)

    secret_b32 = mfa_crypto.generate_totp_secret()
    encrypted = mfa_crypto.encrypt_totp_secret(secret_b32)
    account_label = current_user.get("email") or current_user["id"]
    otpauth_uri = mfa_crypto.build_otpauth_uri(account_label, secret_b32)
    qr_svg = mfa_crypto.qr_svg_for_otpauth(otpauth_uri)

    factor_id = str(uuid.uuid4())
    await gd_insert(
        db.session,
        "mfa_factors",
        {
            "id": factor_id,
            "user_id": current_user["id"],
            "kind": "totp",
            "label": None,
            "is_primary": False,
            "is_active": False,
            "totp_secret_encrypted": encrypted,
            "created_at": datetime.now(timezone.utc),
        },
    )

    audit = AuditLogEngine(Repos(db.session))
    await audit.log(
        action="mfa.totp.enroll_begin",
        performed_by=current_user["id"],
        tenant_id=current_user.get("tenant_id"),
        entity_type="mfa_factor",
        entity_id=factor_id,
        actor_email=current_user.get("email"),
        actor_role=current_user.get("role"),
    )

    return TotpEnrollBeginResponse(
        factor_id=factor_id,
        otpauth_uri=otpauth_uri,
        qr_svg=qr_svg,
        account_label=account_label,
    )


@router.post("/auth/mfa/totp/enroll/confirm", response_model=TotpEnrollConfirmResponse)
async def totp_enroll_confirm(
    body: TotpEnrollConfirmRequest,
    current_user: dict = Depends(get_current_user),
):
    """Verify the first TOTP code from the user's authenticator app and
    activate the pending factor row.

    Refuses to activate:
    * a row that doesn't belong to the calling user,
    * a row of a kind other than ``totp``,
    * a row that is already active (replay protection),
    * a row whose code does not verify against the stored secret.
    """
    _ensure_totp_kind_allowed(current_user)

    factor = await gd_find_one(db.session, "mfa_factors", {"id": body.factor_id})
    if (
        not factor
        or factor.get("user_id") != current_user["id"]
        or factor.get("kind") != "totp"
    ):
        raise HTTPException(status_code=404, detail="عامل التحقق غير موجود")
    if factor.get("is_active"):
        raise HTTPException(status_code=409, detail="عامل التحقق مفعّل مسبقاً")

    encrypted = factor.get("totp_secret_encrypted")
    if not encrypted:
        # Should be impossible if the row was created via /enroll/begin.
        raise HTTPException(status_code=500, detail="عامل التحقق غير صالح")
    try:
        secret_b32 = mfa_crypto.decrypt_totp_secret(
            encrypted if isinstance(encrypted, (bytes, bytearray)) else bytes(encrypted)
        )
    except mfa_crypto.MfaCryptoConfigError as exc:
        logger.warning(f"totp_enroll_confirm: decrypt failed for factor {body.factor_id}: {exc}")
        raise HTTPException(status_code=500, detail="عامل التحقق غير صالح")

    if not mfa_crypto.verify_totp_code(secret_b32, body.code, window=1):
        audit = AuditLogEngine(Repos(db.session))
        await audit.log(
            action="mfa.totp.enroll_failure",
            performed_by=current_user["id"],
            tenant_id=current_user.get("tenant_id"),
            entity_type="mfa_factor",
            entity_id=body.factor_id,
            actor_email=current_user.get("email"),
            actor_role=current_user.get("role"),
        )
        raise HTTPException(status_code=400, detail="رمز التحقق غير صحيح")

    # Decide is_primary: first activated factor for this user becomes primary.
    existing_active = await gd_find(
        db.session, "mfa_factors", {"user_id": current_user["id"], "is_active": True}
    )
    is_primary = not existing_active

    now = datetime.now(timezone.utc)
    await gd_update_one(
        db.session,
        "mfa_factors",
        {"id": body.factor_id},
        {
            "is_active": True,
            "verified_at": now,
            "label": body.label or "TOTP",
            "is_primary": is_primary,
        },
    )

    # If this is the user's first ever factor, stamp mfa_enrolled_at.
    if not current_user.get("mfa_enrolled_at"):
        await gd_update_one(
            db.session, "users", {"id": current_user["id"]}, {"mfa_enrolled_at": now}
        )

    audit = AuditLogEngine(Repos(db.session))
    await audit.log(
        action="mfa.totp.enroll_success",
        performed_by=current_user["id"],
        tenant_id=current_user.get("tenant_id"),
        entity_type="mfa_factor",
        entity_id=body.factor_id,
        actor_email=current_user.get("email"),
        actor_role=current_user.get("role"),
        details={"is_primary": is_primary},
    )

    return TotpEnrollConfirmResponse(
        factor_id=body.factor_id,
        activated_at=now.isoformat(),
        is_primary=is_primary,
    )


# ---------------------------------------------------------------------------
# Verify (Step 2 dispatch shell + Step 3 TOTP handler)
# ---------------------------------------------------------------------------

class MfaVerifyRequest(BaseModel):
    factor_kind: str  # 'totp' | 'webauthn' | 'email_otp' | 'recovery'
    code: Optional[str] = None
    webauthn_response: Optional[dict] = None


@router.post("/auth/mfa/verify", response_model=TokenResponse)
async def verify_mfa(
    body: MfaVerifyRequest,
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(_security),
):
    """Consume an MFA pending challenge by presenting a valid factor proof.

    On success returns the final ``access_token`` + ``refresh_token`` pair
    and consumes the challenge row. On failure increments the per-row
    attempt counter (challenge is hard-capped at 5).
    """
    challenge, user = await _resolve_challenge(credentials)

    allowed = mfa_policy.allowed_factor_kinds(user)
    if body.factor_kind not in allowed:
        await _bump_challenge_attempts(challenge)
        raise HTTPException(status_code=400, detail="نوع العامل غير مسموح لهذا الحساب")

    if body.factor_kind == "totp":
        if not body.code:
            await _bump_challenge_attempts(challenge)
            raise HTTPException(status_code=400, detail="رمز التحقق مطلوب")

        # Find an active TOTP factor for the user. There is normally exactly
        # one; if there are several (re-enrolled), accept the most recently
        # verified one.
        factors = await gd_find(
            db.session, "mfa_factors", {"user_id": user["id"], "kind": "totp", "is_active": True}
        )
        if not factors:
            await _bump_challenge_attempts(challenge)
            raise HTTPException(status_code=400, detail="لا يوجد عامل TOTP مفعّل لهذا الحساب")

        # Prefer the newest verified row.
        def _sort_key(f):
            return f.get("verified_at") or f.get("created_at") or datetime.min

        factor = sorted(factors, key=_sort_key, reverse=True)[0]
        encrypted = factor.get("totp_secret_encrypted")
        try:
            secret_b32 = mfa_crypto.decrypt_totp_secret(
                encrypted if isinstance(encrypted, (bytes, bytearray)) else bytes(encrypted)
            )
        except mfa_crypto.MfaCryptoConfigError as exc:
            logger.warning(f"verify_mfa(totp): decrypt failed for factor {factor.get('id')}: {exc}")
            await _bump_challenge_attempts(challenge)
            raise HTTPException(status_code=500, detail="عامل التحقق غير صالح")

        if not mfa_crypto.verify_totp_code(secret_b32, body.code, window=1):
            await _bump_challenge_attempts(challenge)
            audit = AuditLogEngine(Repos(db.session))
            await audit.log_auth_event(
                action="mfa.login.failure",
                user_id=user["id"],
                tenant_id=user.get("tenant_id"),
                success=False,
                email=user.get("email"),
                reason="totp_invalid",
            )
            raise HTTPException(status_code=400, detail="رمز التحقق غير صحيح")

        # Stamp last_used_at on the factor row.
        try:
            await gd_update_one(
                db.session,
                "mfa_factors",
                {"id": factor["id"]},
                {"last_used_at": datetime.now(timezone.utc)},
            )
        except Exception as exc:
            logger.debug(f"verify_mfa(totp): last_used_at update failed: {exc}")

        return await _complete_mfa_login(user, challenge, "totp", request)

    # Other factor kinds land in Steps 4-6.
    raise HTTPException(
        status_code=501,
        detail=f"MFA verify handler for {body.factor_kind!r} not yet implemented",
    )
