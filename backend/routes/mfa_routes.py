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

import json
import logging
import uuid
from datetime import datetime, timedelta, timezone
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
from engines.email_service import send_mfa_email_otp
from engines.sql_utils import gd_find, gd_find_one, gd_insert, gd_update_one
from middleware.rate_limiter import rate_store
from repositories import Repos
from services import mfa_crypto, mfa_policy, mfa_webauthn
from shared_models import TokenResponse, UserResponse, UserRole
from utils.trusted_proxy import extract_client_ip

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
    stepup_only: bool = False,
):
    """Mint tokens, record the session, mark the challenge consumed, mark
    the factor as last-used, and write the success audit row. Shared by
    every successful factor verification path (Steps 3-6).

    Task #169 Step 7: when ``stepup_only=True`` this is the post-step-up
    completion path. We mint ONLY a fresh access token with an updated
    ``mfa_recent_at`` claim — the existing refresh token (and therefore
    the existing session lifetime) is preserved. We also skip the new
    user_sessions row to avoid churning that table; the old access token
    continues to age out naturally and the new one inherits the same
    sub/role/tenant claims. Returns a plain dict in step-up mode and a
    full ``TokenResponse`` in login mode.
    """
    user_id = user["id"]
    token_payload = {"sub": user_id, "role": user["role"]}
    if user.get("tenant_id"):
        token_payload["tenant_id"] = user["tenant_id"]
    if user.get("school_id"):
        token_payload["school_id"] = user["school_id"]

    # Step 7: stamp mfa_recent_at + mfa_kind on the freshly minted access AND
    # refresh tokens. Refresh PRESERVES (does not advance) these claims;
    # only this path and /auth/mfa/stepup/verify advance them.
    mfa_recent_at = int(datetime.now(timezone.utc).timestamp())

    access = create_access_token(
        token_payload, mfa_recent_at=mfa_recent_at, mfa_kind=factor_kind
    )
    try:
        access_jti = jwt.decode(access, JWT_SECRET, algorithms=[JWT_ALGORITHM]).get("jti")
    except Exception:
        access_jti = None
    if not stepup_only:
        refresh = create_refresh_token(
            token_payload,
            remember_me=bool(challenge.get("remember_me")),
            linked_access_jti=access_jti,
            mfa_recent_at=mfa_recent_at,
            mfa_kind=factor_kind,
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
        action=("mfa.stepup.success" if stepup_only else "mfa.login.success"),
        user_id=user_id,
        tenant_id=user.get("tenant_id"),
        success=True,
        email=user.get("email"),
        reason=factor_kind,
    )

    if stepup_only:
        return {
            "access_token": access,
            "mfa_recent_at": mfa_recent_at,
            "mfa_kind": factor_kind,
            "token_type": "bearer",
        }

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
        mfa_enrolled_at=user.get("mfa_enrolled_at"),
    )

    # Surface the "show recovery codes again" hint if the user has never
    # acknowledged them and has codes generated.
    pending_view = bool(
        user.get("mfa_recovery_codes_generated_at")
        and not user.get("mfa_recovery_codes_acknowledged")
    )

    # Task #231 — embed the IT workspace lifecycle snapshot (banner gate
    # included) so the post-login dashboard paints the banner in the same
    # frame as the rest of the page. Best-effort.
    workspace_lifecycle = None
    try:
        from routes.independent_teacher_workspace_lifecycle_routes import (
            fetch_workspace_lifecycle_for_user,
        )
        workspace_lifecycle = await fetch_workspace_lifecycle_for_user(user)
    except Exception as _wl_err:
        logger.debug("verify_mfa: workspace_lifecycle fetch skipped: %s", _wl_err)

    return TokenResponse(
        access_token=access,
        refresh_token=refresh,
        user=user_response,
        mfa_recovery_codes_pending_view=pending_view,
        workspace_lifecycle=workspace_lifecycle,
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
    webauthn_challenge_id: Optional[str] = None  # pins the WebAuthn ceremony


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

    # Accept both "recovery" and "recovery_code" from the client; the
    # policy uses the canonical "recovery_code" name.
    if body.factor_kind == "recovery":
        body.factor_kind = "recovery_code"

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

    if body.factor_kind == "webauthn":
        if not body.webauthn_response:
            await _bump_challenge_attempts(challenge)
            raise HTTPException(status_code=400, detail="استجابة مفتاح الأمان مطلوبة")
        return await _verify_webauthn_and_complete(
            user=user,
            challenge=challenge,
            credential=body.webauthn_response,
            webauthn_challenge_id=body.webauthn_challenge_id,
            request=request,
        )

    if body.factor_kind == "email_otp":
        if not body.code:
            await _bump_challenge_attempts(challenge)
            raise HTTPException(status_code=400, detail="رمز التحقق مطلوب")
        return await _verify_email_otp_and_complete(
            user=user, challenge=challenge, code=body.code, request=request,
        )

    if body.factor_kind == "recovery_code":
        if not body.code:
            await _bump_challenge_attempts(challenge)
            raise HTTPException(status_code=400, detail="رمز الاسترداد مطلوب")
        return await _verify_recovery_code_and_complete(
            user=user, challenge=challenge, code=body.code, request=request,
        )

    raise HTTPException(
        status_code=400,
        detail=f"نوع العامل غير مدعوم: {body.factor_kind!r}",
    )


# ---------------------------------------------------------------------------
# Step-up: server-driven re-prompt before sensitive actions (Task #169 Step 7)
# ---------------------------------------------------------------------------
#
# Flow
# ----
# Sensitive routes are guarded by ``require_recent_mfa(max_age_seconds=300)``
# (see backend/dependencies.py). When the user's bearer JWT lacks a fresh
# enough ``mfa_recent_at`` claim, the server replies 401 with
# ``{detail: {code: "MFA_STEPUP_REQUIRED", challenge_endpoint:
# "/api/auth/mfa/stepup/start", ...}}``. The frontend Axios interceptor
# (Step 9) opens the step-up modal which:
#
#   1. POST /auth/mfa/stepup/start (Authorization: Bearer <ACCESS_TOKEN>)
#      → server creates a fresh mfa_pending_challenges row for the user
#        and returns a short-lived ``mfa_challenge`` JWT plus the list of
#        factor kinds the user can satisfy.
#   2. POST /auth/mfa/stepup/verify { factor_kind, code|webauthn_response }
#      with Authorization: Bearer <CHALLENGE_TOKEN>
#      → on success the server mints a NEW access token with a refreshed
#        ``mfa_recent_at`` claim. The user's REFRESH token is left
#        untouched — the existing session continues with the new access
#        token; the old access token's natural expiry is unchanged.
#
# The two endpoints intentionally reuse the same per-factor verification
# helpers as the login path. The only behavioural deltas live in
# ``_complete_mfa_login(stepup_only=True)``: skip refresh mint, skip
# user_sessions row, return a small ``StepupVerifyResponse`` shape.

class StepupStartResponse(BaseModel):
    challenge_token: str
    challenge_expires_at: str
    available_factor_kinds: List[str]
    mfa_tier: str


class StepupVerifyResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    mfa_recent_at: int
    mfa_kind: str


@router.post("/auth/mfa/stepup/start", response_model=StepupStartResponse)
async def stepup_start(
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    """Mint a fresh MFA challenge for the currently-authenticated user so
    they can re-satisfy their second factor before a sensitive action.

    Bearer is the user's normal access token — there is no password
    re-prompt; the act of re-presenting a fresh second factor IS the
    step-up. Roles outside Tier A/B/C have no factor to present and get
    409 here, but they would never have hit a require_recent_mfa guard
    in the first place because that dep fast-paths them.
    """
    tier = mfa_policy.required_for(current_user)
    if tier is None:
        raise HTTPException(
            status_code=409,
            detail="هذا الحساب غير مشمول بسياسة العامل الثاني",
        )

    user_id = current_user["id"]
    active_factors = await gd_find(
        db.session, "mfa_factors", {"user_id": user_id, "is_active": True}
    ) or []

    # Tier B/C have an implicit email_otp factor (the user's email IS the
    # delivery channel). Tier A users must hold at least one enrolled
    # active factor — if they have none they'd already be blocked by the
    # tier-A passkey enforcement branch in require_recent_mfa.
    from services.mfa_policy import MfaTier as _MfaTier
    implicit_email_otp = tier in (_MfaTier.B, _MfaTier.C)
    if not active_factors and not implicit_email_otp:
        raise HTTPException(
            status_code=409,
            detail="لا يوجد عامل تحقق مفعّل — يجب تسجيل عامل أولاً",
        )

    from dependencies import create_mfa_challenge_token
    challenge_token, challenge_jti, challenge_exp = create_mfa_challenge_token(
        user_id, current_user["role"], current_user.get("tenant_id"),
    )

    await gd_insert(
        db.session,
        "mfa_pending_challenges",
        {
            "user_id": user_id,
            "challenge_token_jti": challenge_jti,
            "expires_at": challenge_exp,
            "attempts": 0,
            "ip": request.client.host if request and request.client else None,
            "user_agent": (request.headers.get("user-agent") if request else None) or None,
            # Step-up does not extend the refresh-token lifetime so this is
            # always the short-lived flavour regardless of the original
            # session's remember_me posture.
            "remember_me": False,
        },
    )

    try:
        audit = AuditLogEngine(Repos(db.session))
        await audit.log_auth_event(
            action="mfa.stepup.challenge_issued",
            user_id=user_id,
            tenant_id=current_user.get("tenant_id"),
            success=True,
            email=current_user.get("email"),
        )
    except Exception as exc:
        logger.debug(f"stepup_start: audit failed: {exc}")

    allowed_for_user = mfa_policy.allowed_factor_kinds(current_user)
    enrolled_kinds = {
        f.get("kind") for f in active_factors
        if f.get("kind") in allowed_for_user
    }
    if implicit_email_otp and "email_otp" in allowed_for_user:
        enrolled_kinds.add("email_otp")
    if "recovery_code" in allowed_for_user:
        try:
            rc_rows = await gd_find(
                db.session,
                "mfa_recovery_codes",
                {"user_id": user_id, "consumed_at": None},
            ) or []
            if rc_rows:
                enrolled_kinds.add("recovery_code")
        except Exception as exc:
            logger.debug(f"stepup_start: recovery_code lookup failed: {exc}")

    return StepupStartResponse(
        challenge_token=challenge_token,
        challenge_expires_at=challenge_exp.isoformat(),
        available_factor_kinds=sorted(k for k in enrolled_kinds if k),
        mfa_tier=tier.value,
    )


@router.post("/auth/mfa/stepup/verify", response_model=StepupVerifyResponse)
async def stepup_verify(
    body: MfaVerifyRequest,
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(_security),
):
    """Consume a step-up challenge by presenting a valid factor proof.

    Mirrors ``/auth/mfa/verify`` byte-for-byte except every per-factor
    branch threads ``stepup_only=True`` so the completion helper mints a
    NEW access token with a refreshed ``mfa_recent_at`` claim and
    intentionally leaves the existing refresh token untouched.
    """
    challenge, user = await _resolve_challenge(credentials)

    if body.factor_kind == "recovery":
        body.factor_kind = "recovery_code"

    allowed = mfa_policy.allowed_factor_kinds(user)
    if body.factor_kind not in allowed:
        await _bump_challenge_attempts(challenge)
        raise HTTPException(status_code=400, detail="نوع العامل غير مسموح لهذا الحساب")

    if body.factor_kind == "totp":
        if not body.code:
            await _bump_challenge_attempts(challenge)
            raise HTTPException(status_code=400, detail="رمز التحقق مطلوب")
        factors = await gd_find(
            db.session, "mfa_factors", {"user_id": user["id"], "kind": "totp", "is_active": True}
        )
        if not factors:
            await _bump_challenge_attempts(challenge)
            raise HTTPException(status_code=400, detail="لا يوجد عامل TOTP مفعّل لهذا الحساب")

        def _sort_key(f):
            return f.get("verified_at") or f.get("created_at") or datetime.min

        factor = sorted(factors, key=_sort_key, reverse=True)[0]
        encrypted = factor.get("totp_secret_encrypted")
        try:
            secret_b32 = mfa_crypto.decrypt_totp_secret(
                encrypted if isinstance(encrypted, (bytes, bytearray)) else bytes(encrypted)
            )
        except mfa_crypto.MfaCryptoConfigError as exc:
            logger.warning(f"stepup_verify(totp): decrypt failed for factor {factor.get('id')}: {exc}")
            await _bump_challenge_attempts(challenge)
            raise HTTPException(status_code=500, detail="عامل التحقق غير صالح")

        if not mfa_crypto.verify_totp_code(secret_b32, body.code, window=1):
            await _bump_challenge_attempts(challenge)
            try:
                audit = AuditLogEngine(Repos(db.session))
                await audit.log_auth_event(
                    action="mfa.stepup.failure",
                    user_id=user["id"],
                    tenant_id=user.get("tenant_id"),
                    success=False,
                    email=user.get("email"),
                    reason="totp_invalid",
                )
            except Exception as exc:
                logger.debug(f"stepup_verify(totp): audit failed: {exc}")
            raise HTTPException(status_code=400, detail="رمز التحقق غير صحيح")

        try:
            await gd_update_one(
                db.session,
                "mfa_factors",
                {"id": factor["id"]},
                {"last_used_at": datetime.now(timezone.utc)},
            )
        except Exception as exc:
            logger.debug(f"stepup_verify(totp): last_used_at update failed: {exc}")

        return StepupVerifyResponse(
            **(await _complete_mfa_login(user, challenge, "totp", request, stepup_only=True))
        )

    if body.factor_kind == "webauthn":
        if not body.webauthn_response:
            await _bump_challenge_attempts(challenge)
            raise HTTPException(status_code=400, detail="استجابة مفتاح الأمان مطلوبة")
        result = await _verify_webauthn_and_complete(
            user=user,
            challenge=challenge,
            credential=body.webauthn_response,
            webauthn_challenge_id=body.webauthn_challenge_id,
            request=request,
            stepup_only=True,
        )
        return StepupVerifyResponse(**result)

    if body.factor_kind == "email_otp":
        if not body.code:
            await _bump_challenge_attempts(challenge)
            raise HTTPException(status_code=400, detail="رمز التحقق مطلوب")
        result = await _verify_email_otp_and_complete(
            user=user, challenge=challenge, code=body.code, request=request,
            stepup_only=True,
        )
        return StepupVerifyResponse(**result)

    if body.factor_kind == "recovery_code":
        if not body.code:
            await _bump_challenge_attempts(challenge)
            raise HTTPException(status_code=400, detail="رمز الاسترداد مطلوب")
        result = await _verify_recovery_code_and_complete(
            user=user, challenge=challenge, code=body.code, request=request,
            stepup_only=True,
        )
        return StepupVerifyResponse(**result)

    raise HTTPException(
        status_code=400,
        detail=f"نوع العامل غير مدعوم: {body.factor_kind!r}",
    )


# ---------------------------------------------------------------------------
# Email OTP — Tier B/C factor (Step 5)
# ---------------------------------------------------------------------------
#
# Flow summary
# ------------
# Login with email OTP (user already holds the short-lived mfa_challenge
# token from /auth/login):
#   1. POST /auth/mfa/email-otp/send (Authorization: Bearer <chal>)
#      → server generates a fresh 6-digit code, persists a salted-sha256
#        hash + salt in ``mfa_email_otps`` (TTL 10 min), and emails the
#        code to the user's mailbox. Returns a masked email and the
#        expiry timestamp; never returns the code itself.
#   2. POST /auth/mfa/verify { factor_kind: "email_otp", code: "123456" }
#      → server looks up the most recent unconsumed unexpired row for
#        the challenge, verifies the hash, marks consumed_at, and mints
#        the final access+refresh pair via ``_complete_mfa_login``.
#
# Throttles (defence in depth — distinct from the per-challenge attempt
# cap, which is enforced by ``_resolve_challenge`` at 5):
#   - per-challenge: at most 3 sends per pending-challenge row
#   - per-user:      5 sends per 600 s
#   - per-IP:        30 sends per 600 s
# All three use the in-process ``rate_store``; if the workspace later
# moves to multiple workers the limits multiply per-worker which is
# acceptable for a 6-digit code with a 10-minute TTL and a 5-attempt
# challenge cap.

EMAIL_OTP_TTL_SECONDS = 600  # 10 minutes
EMAIL_OTP_MAX_PER_CHALLENGE = 3
EMAIL_OTP_USER_RATE = (5, 600)
EMAIL_OTP_IP_RATE = (30, 600)


class EmailOtpSendResponse(BaseModel):
    sent: bool
    masked_email: str
    expires_at: datetime
    remaining_sends: int


def _mask_email(email: str) -> str:
    """Return e.g. ``ah***@example.com`` so the UI can confirm the
    destination without echoing the full address back to anyone holding
    a stolen challenge token."""
    if not email or "@" not in email:
        return "***"
    local, _, domain = email.partition("@")
    if len(local) <= 2:
        keep = local[:1] or "*"
    else:
        keep = local[:2]
    return f"{keep}***@{domain}"


@router.post("/auth/mfa/email-otp/send", response_model=EmailOtpSendResponse)
async def email_otp_send(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(_security),
):
    """Mint a fresh 6-digit OTP, store its hash, and email it to the
    user. Idempotent only in the sense that re-calling burns one of
    your three allowed sends — each send invalidates nothing, but only
    the latest unexpired row will be matched on verify."""
    challenge, user = await _resolve_challenge(credentials)

    if "email_otp" not in mfa_policy.allowed_factor_kinds(user):
        raise HTTPException(status_code=403, detail="رمز البريد غير متاح لحسابك")

    email = (user.get("email") or "").strip()
    if not email:
        raise HTTPException(status_code=400, detail="لا يوجد بريد إلكتروني مسجّل لهذا الحساب")

    # Per-challenge cap (3 sends per pending-challenge row).
    existing = await gd_find(
        db.session, "mfa_email_otps", {"challenge_id": challenge["id"]}
    )
    if len(existing) >= EMAIL_OTP_MAX_PER_CHALLENGE:
        raise HTTPException(
            status_code=429,
            detail="تجاوزت الحد المسموح من إرسال رمز البريد. ابدأ تسجيل الدخول من جديد",
        )

    # Per-user + per-IP sliding-window throttles.
    client_ip = extract_client_ip(request) or "unknown"
    limited_user, _, retry_user = await rate_store.is_rate_limited(
        f"mfa_email_otp:user:{user['id']}", *EMAIL_OTP_USER_RATE,
    )
    if limited_user:
        raise HTTPException(
            status_code=429,
            detail="عدد طلبات الرمز تجاوز الحد. حاول بعد قليل",
            headers={"Retry-After": str(retry_user)},
        )
    limited_ip, _, retry_ip = await rate_store.is_rate_limited(
        f"mfa_email_otp:ip:{client_ip}", *EMAIL_OTP_IP_RATE,
    )
    if limited_ip:
        raise HTTPException(
            status_code=429,
            detail="عدد طلبات الرمز تجاوز الحد. حاول بعد قليل",
            headers={"Retry-After": str(retry_ip)},
        )

    # Mint, hash, persist.
    code = mfa_crypto.generate_email_otp()
    salt = mfa_crypto.generate_email_otp_salt()
    code_hash = mfa_crypto.hash_email_otp(code, salt)
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(seconds=EMAIL_OTP_TTL_SECONDS)
    row_id = str(uuid.uuid4())

    await gd_insert(
        db.session,
        "mfa_email_otps",
        {
            "id": row_id,
            "user_id": user["id"],
            "challenge_id": challenge["id"],
            "code_hash": code_hash,
            "code_salt": salt,
            "sent_at": now,
            "expires_at": expires_at,
            "attempts": 0,
            "consumed_at": None,
        },
    )

    # Best-effort send. We deliberately do NOT fail the request when
    # Resend is misconfigured in dev — the row is persisted and an ops
    # operator can read the code from the DB during diagnosis. In prod
    # the missing-API-key path is already loud (logger.error) and the
    # masked_email response makes the failure obvious to the UI.
    user_name = user.get("full_name") or user.get("name") or email
    try:
        send_mfa_email_otp(
            to_email=email,
            user_name=user_name,
            code=code,
            expires_in_minutes=EMAIL_OTP_TTL_SECONDS // 60,
        )
    except Exception as exc:
        logger.warning(f"email_otp_send: provider call failed: {exc}")

    try:
        audit = AuditLogEngine(Repos(db.session))
        await audit.log_auth_event(
            action="mfa.email_otp.sent",
            user_id=user["id"],
            tenant_id=user.get("tenant_id"),
            success=True,
            email=email,
        )
    except Exception as exc:
        logger.debug(f"email_otp_send: audit log failed: {exc}")

    remaining = max(0, EMAIL_OTP_MAX_PER_CHALLENGE - len(existing) - 1)
    return EmailOtpSendResponse(
        sent=True,
        masked_email=_mask_email(email),
        expires_at=expires_at,
        remaining_sends=remaining,
    )


async def _verify_email_otp_and_complete(
    *, user: dict, challenge: dict, code: str, request: Optional[Request],
    stepup_only: bool = False,
):
    """Match a user-supplied 6-digit OTP against the latest unconsumed
    unexpired row for this challenge. On success: stamp consumed_at,
    delete the row's siblings (defence-in-depth — only one OTP per
    challenge survives a successful verify), and complete the login."""
    rows = await gd_find(
        db.session, "mfa_email_otps", {"challenge_id": challenge["id"]}
    )
    now = datetime.now(timezone.utc)

    def _norm_dt(v):
        if isinstance(v, datetime):
            return v if v.tzinfo else v.replace(tzinfo=timezone.utc)
        try:
            dt = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except Exception:
            return datetime.min.replace(tzinfo=timezone.utc)

    fresh = [
        r for r in rows
        if r.get("consumed_at") is None and _norm_dt(r.get("expires_at")) >= now
    ]
    if not fresh:
        await _bump_challenge_attempts(challenge)
        try:
            audit = AuditLogEngine(Repos(db.session))
            await audit.log_auth_event(
                action="mfa.login.failure",
                user_id=user["id"],
                tenant_id=user.get("tenant_id"),
                success=False,
                email=user.get("email"),
                reason="email_otp_missing_or_expired",
            )
        except Exception as exc:
            logger.debug(f"verify_mfa(email_otp): audit log failed: {exc}")
        raise HTTPException(status_code=400, detail="انتهت صلاحية الرمز أو لم يتم إرساله")

    fresh.sort(key=lambda r: _norm_dt(r.get("sent_at")), reverse=True)

    # Verify against any fresh row — supports the "I requested a second
    # code while the first was still valid, then typed the first" UX
    # without leaking which row matched.
    matched = None
    for row in fresh:
        if mfa_crypto.verify_email_otp(code, row.get("code_salt") or "", row.get("code_hash") or ""):
            matched = row
            break

    if not matched:
        # Bump per-row attempts on the newest row + the global challenge
        # attempt counter. Don't disclose which row failed.
        try:
            await gd_update_one(
                db.session,
                "mfa_email_otps",
                {"id": fresh[0]["id"]},
                {"attempts": int(fresh[0].get("attempts") or 0) + 1},
            )
        except Exception as exc:
            logger.debug(f"verify_mfa(email_otp): attempts bump failed: {exc}")
        await _bump_challenge_attempts(challenge)
        try:
            audit = AuditLogEngine(Repos(db.session))
            await audit.log_auth_event(
                action="mfa.login.failure",
                user_id=user["id"],
                tenant_id=user.get("tenant_id"),
                success=False,
                email=user.get("email"),
                reason="email_otp_invalid",
            )
        except Exception as exc:
            logger.debug(f"verify_mfa(email_otp): audit log failed: {exc}")
        raise HTTPException(status_code=400, detail="رمز التحقق غير صحيح")

    # Mark this row consumed and burn the rest so a leaked sibling code
    # cannot be replayed against the same challenge later.
    try:
        await gd_update_one(
            db.session,
            "mfa_email_otps",
            {"id": matched["id"]},
            {"consumed_at": now, "attempts": int(matched.get("attempts") or 0) + 1},
        )
        for sibling in fresh:
            if sibling["id"] == matched["id"]:
                continue
            await gd_update_one(
                db.session,
                "mfa_email_otps",
                {"id": sibling["id"]},
                {"consumed_at": now},
            )
    except Exception as exc:
        logger.debug(f"verify_mfa(email_otp): consumed_at update failed: {exc}")

    return await _complete_mfa_login(user, challenge, "email_otp", request, stepup_only=stepup_only)


# ---------------------------------------------------------------------------
# WebAuthn — Tier A passkey factor (Step 4)
# ---------------------------------------------------------------------------
#
# Flow summary
# ------------
# Enrol (user already authenticated):
#   1. POST /auth/mfa/webauthn/register/begin
#      → server mints a fresh random challenge, stores it in
#        ``mfa_webauthn_challenges`` (purpose='enroll'), returns the
#        WebAuthn ``CredentialCreationOptions`` JSON for the browser.
#   2. Browser calls ``navigator.credentials.create(options)`` and POSTs
#      the resulting PublicKeyCredential to:
#      POST /auth/mfa/webauthn/register/finish
#      → server looks up the most recent unexpired enroll challenge for
#        this user, verifies the attestation, persists the credential as
#        an active ``mfa_factors`` row, and DELETES the challenge.
#
# Login (user has only the short-lived mfa_challenge token):
#   1. POST /auth/mfa/webauthn/verify/begin (Authorization: Bearer <chal>)
#      → server gathers the user's active webauthn credential ids, mints
#        a fresh challenge with ``purpose='verify'``, and returns the
#        ``CredentialRequestOptions`` JSON.
#   2. Browser calls ``navigator.credentials.get(options)`` and POSTs the
#      resulting PublicKeyCredential to either:
#         POST /auth/mfa/webauthn/verify/finish, OR
#         POST /auth/mfa/verify { factor_kind: "webauthn", webauthn_response: ... }
#      → server verifies the assertion against the matching factor row,
#        bumps ``webauthn_sign_count``, deletes the challenge, and mints
#        the final access+refresh tokens via ``_complete_mfa_login``.
#
# Both finish endpoints share ``_verify_webauthn_and_complete`` so the
# unified verify dispatch and the dedicated WebAuthn endpoint cannot
# diverge.


_ENROLL_CHALLENGE_TTL = timedelta(minutes=5)
_VERIFY_CHALLENGE_TTL = timedelta(minutes=5)


def _ensure_webauthn_kind_allowed(user: dict) -> None:
    if "webauthn" not in mfa_policy.allowed_factor_kinds(user):
        raise HTTPException(
            status_code=403,
            detail="مفتاح الأمان غير متاح لحسابك",
        )


def _bytes(val) -> bytes:
    """Coerce a stored BYTEA/memoryview/bytes value into ``bytes``."""
    if val is None:
        return b""
    if isinstance(val, (bytes, bytearray)):
        return bytes(val)
    if isinstance(val, memoryview):
        return val.tobytes()
    # asyncpg occasionally returns Buffer-like objects.
    return bytes(val)


async def _store_webauthn_challenge(
    *, user_id: str, purpose: str, challenge: bytes, ttl: timedelta
) -> str:
    """Insert a row into ``mfa_webauthn_challenges`` and return its id."""
    chal_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    await gd_insert(
        db.session,
        "mfa_webauthn_challenges",
        {
            "id": chal_id,
            "user_id": user_id,
            "purpose": purpose,
            "challenge": challenge,
            "created_at": now,
            "expires_at": now + ttl,
        },
    )
    return chal_id


async def _take_webauthn_challenge(
    *,
    user_id: str,
    purpose: str,
    challenge_id: Optional[str] = None,
) -> Optional[dict]:
    """Return the matching unexpired challenge for the given user.

    When ``challenge_id`` is supplied (preferred path — the ``begin``
    endpoint always returns one to the client and the ``finish`` body
    must echo it back), the lookup is keyed by exact id, ruling out
    concurrent-ceremony confusion entirely. The fallback "latest
    unexpired" lookup remains for backwards-compat callers but is
    defence-in-depth only — the WebAuthn signature binds the challenge
    bytes to the credential, so a wrong match would fail verification
    anyway.
    """
    if challenge_id:
        row = await gd_find_one(
            db.session,
            "mfa_webauthn_challenges",
            {"id": challenge_id, "user_id": user_id, "purpose": purpose},
        )
        if not row:
            return None
        rows = [row]
    else:
        rows = await gd_find(
            db.session,
            "mfa_webauthn_challenges",
            {"user_id": user_id, "purpose": purpose},
        )
        if not rows:
            return None

    now = datetime.now(timezone.utc)

    def _exp(row):
        v = row.get("expires_at")
        if isinstance(v, datetime):
            return v if v.tzinfo else v.replace(tzinfo=timezone.utc)
        try:
            dt = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except Exception:
            return datetime.min.replace(tzinfo=timezone.utc)

    fresh = [r for r in rows if _exp(r) >= now]
    if not fresh:
        return None
    fresh.sort(key=lambda r: r.get("created_at") or datetime.min, reverse=True)
    return fresh[0]


async def _delete_webauthn_challenge(chal_id: str) -> None:
    """Single-use semantics — best-effort delete."""
    try:
        from sqlalchemy import text  # local import keeps top-of-file clean
        await db.session.execute(
            text("DELETE FROM mfa_webauthn_challenges WHERE id = :id"),
            {"id": chal_id},
        )
    except Exception as exc:
        logger.debug(f"_delete_webauthn_challenge failed: {exc}")


async def _user_active_webauthn_credential_ids(user_id: str) -> List[bytes]:
    rows = await gd_find(
        db.session,
        "mfa_factors",
        {"user_id": user_id, "kind": "webauthn", "is_active": True},
    )
    out: List[bytes] = []
    for r in rows or []:
        cid = r.get("webauthn_credential_id")
        if cid:
            out.append(_bytes(cid))
    return out


async def _find_webauthn_factor_by_credential_id(
    *, user_id: str, credential_id: bytes
) -> Optional[dict]:
    rows = await gd_find(
        db.session,
        "mfa_factors",
        {"user_id": user_id, "kind": "webauthn", "is_active": True},
    )
    target = bytes(credential_id)
    for r in rows or []:
        if _bytes(r.get("webauthn_credential_id")) == target:
            return r
    return None


# ---- request/response models ----------------------------------------------

class WebauthnRegisterBeginResponse(BaseModel):
    challenge_id: str
    options: dict  # PublicKeyCredentialCreationOptions, JSON-safe shape


class WebauthnRegisterFinishRequest(BaseModel):
    credential: dict
    label: Optional[str] = Field(None, max_length=64)
    challenge_id: Optional[str] = Field(
        None,
        description="The challenge_id returned by /webauthn/register/begin. Strongly recommended — pins this finish call to the exact ceremony.",
    )


class WebauthnRegisterFinishResponse(BaseModel):
    factor_id: str
    activated_at: str
    is_primary: bool
    attachment: Optional[str] = None


class WebauthnVerifyBeginResponse(BaseModel):
    challenge_id: str
    options: dict  # PublicKeyCredentialRequestOptions


class WebauthnVerifyFinishRequest(BaseModel):
    credential: dict
    challenge_id: Optional[str] = Field(
        None,
        description="The challenge_id returned by /webauthn/verify/begin. Strongly recommended — pins this finish call to the exact ceremony.",
    )


# ---- enrol begin -----------------------------------------------------------

@router.post(
    "/auth/mfa/webauthn/register/begin",
    response_model=WebauthnRegisterBeginResponse,
)
async def webauthn_register_begin(
    current_user: dict = Depends(get_current_user),
):
    """Build a CredentialCreationOptions challenge for the calling user.

    Existing active credentials are sent back as ``excludeCredentials`` so
    the browser refuses to register the same authenticator twice on this
    account.
    """
    _ensure_webauthn_kind_allowed(current_user)
    try:
        existing = await _user_active_webauthn_credential_ids(current_user["id"])
        options_json, challenge = mfa_webauthn.make_registration_options(
            user_id=current_user["id"],
            user_name=current_user.get("email") or current_user["id"],
            user_display_name=current_user.get("full_name"),
            exclude_credential_ids=existing,
        )
    except mfa_webauthn.WebauthnUnavailable as exc:
        logger.error(f"webauthn package missing: {exc}")
        raise HTTPException(status_code=501, detail="مفاتيح الأمان غير مفعّلة على الخادم")

    chal_id = await _store_webauthn_challenge(
        user_id=current_user["id"],
        purpose="enroll",
        challenge=challenge,
        ttl=_ENROLL_CHALLENGE_TTL,
    )

    audit = AuditLogEngine(Repos(db.session))
    await audit.log(
        action="mfa.webauthn.register_begin",
        performed_by=current_user["id"],
        tenant_id=current_user.get("tenant_id"),
        entity_type="mfa_webauthn_challenge",
        entity_id=chal_id,
        actor_email=current_user.get("email"),
        actor_role=current_user.get("role"),
    )

    return WebauthnRegisterBeginResponse(
        challenge_id=chal_id,
        options=json.loads(options_json),
    )


# ---- enrol finish ----------------------------------------------------------

def _attachment_from_verified(verified) -> Optional[str]:
    """Extract a human-friendly 'platform' / 'cross-platform' string from
    the VerifiedRegistration object. ``credential_device_type`` is the
    closest field (single_device / multi_device); we prefer the more
    specific ``aaguid``-derived hint when available, falling back to a
    safe ``None``."""
    try:
        # webauthn>=2 surfaces this as ``credential_device_type``;
        # there is no official ``authenticator_attachment`` echoed back.
        ct = getattr(verified, "credential_device_type", None)
        if ct is None:
            return None
        # Map to the UX hint our schema column expects.
        return "platform" if str(ct).lower().endswith("single_device") else "cross-platform"
    except Exception:
        return None


@router.post(
    "/auth/mfa/webauthn/register/finish",
    response_model=WebauthnRegisterFinishResponse,
)
async def webauthn_register_finish(
    body: WebauthnRegisterFinishRequest,
    current_user: dict = Depends(get_current_user),
):
    """Verify the attestation produced by ``navigator.credentials.create``
    and persist the credential as an active ``mfa_factors`` row.

    Refuses gracefully if the underlying ``webauthn`` package is missing,
    if the challenge has expired, or if the attestation does not verify.
    """
    _ensure_webauthn_kind_allowed(current_user)

    chal_row = await _take_webauthn_challenge(
        user_id=current_user["id"],
        purpose="enroll",
        challenge_id=body.challenge_id,
    )
    if not chal_row:
        raise HTTPException(status_code=400, detail="انتهت صلاحية تحدي التسجيل أو لم يبدأ")

    try:
        verified = mfa_webauthn.verify_registration(
            credential=body.credential,
            expected_challenge=_bytes(chal_row.get("challenge")),
        )
    except mfa_webauthn.WebauthnUnavailable as exc:
        logger.error(f"webauthn package missing: {exc}")
        raise HTTPException(status_code=501, detail="مفاتيح الأمان غير مفعّلة على الخادم")
    except Exception as exc:
        logger.info(f"webauthn_register_finish: attestation verify failed: {exc}")
        audit = AuditLogEngine(Repos(db.session))
        await audit.log(
            action="mfa.webauthn.register_failure",
            performed_by=current_user["id"],
            tenant_id=current_user.get("tenant_id"),
            entity_type="mfa_webauthn_challenge",
            entity_id=chal_row.get("id"),
            actor_email=current_user.get("email"),
            actor_role=current_user.get("role"),
            details={"reason": "attestation_invalid"},
        )
        raise HTTPException(status_code=400, detail="فشل التحقق من مفتاح الأمان")

    cred_id = bytes(getattr(verified, "credential_id", b"") or b"")
    pub_key = bytes(getattr(verified, "credential_public_key", b"") or b"")
    sign_count = int(getattr(verified, "sign_count", 0) or 0)
    aaguid_raw = getattr(verified, "aaguid", None)
    aaguid = str(aaguid_raw) if aaguid_raw else None
    attachment = _attachment_from_verified(verified)

    if not cred_id or not pub_key:
        raise HTTPException(status_code=400, detail="فشل التحقق من مفتاح الأمان")

    # Globally-unique credential id — refuse cross-account replay attempts.
    duplicate_rows = await gd_find(
        db.session, "mfa_factors", {"webauthn_credential_id": cred_id}
    )
    if duplicate_rows:
        raise HTTPException(status_code=409, detail="مفتاح الأمان مسجّل مسبقاً")

    existing_active = await gd_find(
        db.session, "mfa_factors", {"user_id": current_user["id"], "is_active": True}
    )
    is_primary = not existing_active

    factor_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    await gd_insert(
        db.session,
        "mfa_factors",
        {
            "id": factor_id,
            "user_id": current_user["id"],
            "kind": "webauthn",
            "label": body.label or "Passkey",
            "is_primary": is_primary,
            "is_active": True,
            "webauthn_credential_id": cred_id,
            "webauthn_public_key": pub_key,
            "webauthn_sign_count": sign_count,
            "webauthn_aaguid": aaguid,
            "webauthn_attachment": attachment,
            "created_at": now,
            "verified_at": now,
        },
    )

    if not current_user.get("mfa_enrolled_at"):
        await gd_update_one(
            db.session, "users", {"id": current_user["id"]}, {"mfa_enrolled_at": now}
        )

    await _delete_webauthn_challenge(chal_row["id"])

    audit = AuditLogEngine(Repos(db.session))
    await audit.log(
        action="mfa.webauthn.register_success",
        performed_by=current_user["id"],
        tenant_id=current_user.get("tenant_id"),
        entity_type="mfa_factor",
        entity_id=factor_id,
        actor_email=current_user.get("email"),
        actor_role=current_user.get("role"),
        details={"is_primary": is_primary, "attachment": attachment},
    )

    return WebauthnRegisterFinishResponse(
        factor_id=factor_id,
        activated_at=now.isoformat(),
        is_primary=is_primary,
        attachment=attachment,
    )


# ---- verify begin (login challenge token) ---------------------------------

@router.post(
    "/auth/mfa/webauthn/verify/begin",
    response_model=WebauthnVerifyBeginResponse,
)
async def webauthn_verify_begin(
    credentials: HTTPAuthorizationCredentials = Depends(_security),
):
    """Mint a fresh CredentialRequestOptions challenge tied to this
    user's pending login challenge. Caller passes the short-lived
    ``mfa_challenge`` JWT in the ``Authorization`` header."""
    _challenge, user = await _resolve_challenge(credentials)
    allow_ids = await _user_active_webauthn_credential_ids(user["id"])
    if not allow_ids:
        raise HTTPException(status_code=400, detail="لا يوجد مفتاح أمان مسجّل لهذا الحساب")

    try:
        options_json, challenge_bytes = mfa_webauthn.make_authentication_options(
            allow_credential_ids=allow_ids,
        )
    except mfa_webauthn.WebauthnUnavailable as exc:
        logger.error(f"webauthn package missing: {exc}")
        raise HTTPException(status_code=501, detail="مفاتيح الأمان غير مفعّلة على الخادم")

    chal_id = await _store_webauthn_challenge(
        user_id=user["id"],
        purpose="verify",
        challenge=challenge_bytes,
        ttl=_VERIFY_CHALLENGE_TTL,
    )

    return WebauthnVerifyBeginResponse(
        challenge_id=chal_id,
        options=json.loads(options_json),
    )


# ---- verify finish (login challenge token) -------------------------------

async def _verify_webauthn_and_complete(
    *,
    user: dict,
    challenge: dict,
    credential: dict,
    request: Optional[Request],
    webauthn_challenge_id: Optional[str] = None,
    stepup_only: bool = False,
):
    """Shared helper: verify a WebAuthn assertion against a stored
    credential, bump the sign count, delete the verify challenge, and
    mint final tokens via ``_complete_mfa_login``.

    The ``challenge`` arg is the *login* challenge row from
    ``mfa_pending_challenges``. The WebAuthn ceremony challenge is
    looked up separately from ``mfa_webauthn_challenges`` keyed by
    user_id + purpose='verify'.
    """
    if "webauthn" not in mfa_policy.allowed_factor_kinds(user):
        await _bump_challenge_attempts(challenge)
        raise HTTPException(status_code=403, detail="مفتاح الأمان غير متاح لهذا الحساب")

    # Decode the credential.id (base64url) to match the stored bytes.
    raw_id = credential.get("rawId") or credential.get("id")
    if not raw_id:
        await _bump_challenge_attempts(challenge)
        raise HTTPException(status_code=400, detail="استجابة مفتاح الأمان غير مكتملة")
    try:
        from webauthn.helpers import base64url_to_bytes  # type: ignore
        credential_id_bytes = base64url_to_bytes(raw_id) if isinstance(raw_id, str) else bytes(raw_id)
    except Exception as exc:
        await _bump_challenge_attempts(challenge)
        logger.info(f"webauthn verify: rawId decode failed: {exc}")
        raise HTTPException(status_code=400, detail="استجابة مفتاح الأمان غير صالحة")

    factor = await _find_webauthn_factor_by_credential_id(
        user_id=user["id"], credential_id=credential_id_bytes
    )
    if not factor:
        await _bump_challenge_attempts(challenge)
        raise HTTPException(status_code=400, detail="مفتاح الأمان غير معروف")

    chal_row = await _take_webauthn_challenge(
        user_id=user["id"],
        purpose="verify",
        challenge_id=webauthn_challenge_id,
    )
    if not chal_row:
        await _bump_challenge_attempts(challenge)
        raise HTTPException(status_code=400, detail="انتهت صلاحية تحدي التحقق")

    try:
        verified = mfa_webauthn.verify_authentication(
            credential=credential,
            expected_challenge=_bytes(chal_row.get("challenge")),
            stored_public_key=_bytes(factor.get("webauthn_public_key")),
            stored_sign_count=int(factor.get("webauthn_sign_count") or 0),
        )
    except mfa_webauthn.WebauthnUnavailable as exc:
        logger.error(f"webauthn package missing: {exc}")
        raise HTTPException(status_code=501, detail="مفاتيح الأمان غير مفعّلة على الخادم")
    except Exception as exc:
        await _bump_challenge_attempts(challenge)
        logger.info(f"webauthn verify: assertion failed: {exc}")
        audit = AuditLogEngine(Repos(db.session))
        await audit.log_auth_event(
            action="mfa.login.failure",
            user_id=user["id"],
            tenant_id=user.get("tenant_id"),
            success=False,
            email=user.get("email"),
            reason="webauthn_invalid",
        )
        raise HTTPException(status_code=400, detail="فشل التحقق من مفتاح الأمان")

    new_sign_count = int(getattr(verified, "new_sign_count", 0) or 0)
    try:
        await gd_update_one(
            db.session,
            "mfa_factors",
            {"id": factor["id"]},
            {
                "webauthn_sign_count": new_sign_count,
                "last_used_at": datetime.now(timezone.utc),
            },
        )
    except Exception as exc:
        logger.debug(f"webauthn verify: factor update failed: {exc}")

    await _delete_webauthn_challenge(chal_row["id"])
    return await _complete_mfa_login(user, challenge, "webauthn", request, stepup_only=stepup_only)


@router.post(
    "/auth/mfa/webauthn/verify/finish",
    response_model=TokenResponse,
)
async def webauthn_verify_finish(
    body: WebauthnVerifyFinishRequest,
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(_security),
):
    """Verify the assertion produced by ``navigator.credentials.get`` and,
    on success, mint final access+refresh tokens. Same shape as the
    unified ``/auth/mfa/verify`` for ``factor_kind='webauthn'``."""
    challenge, user = await _resolve_challenge(credentials)
    return await _verify_webauthn_and_complete(
        user=user,
        challenge=challenge,
        credential=body.credential,
        webauthn_challenge_id=body.challenge_id,
        request=request,
    )


# ---------------------------------------------------------------------------
# Recovery codes — backup factor for every tier (Step 6)
# ---------------------------------------------------------------------------
#
# All tiers MUST have recovery codes once they enrol any primary factor.
# Codes are 12-symbol Crockford-base32 (60 bits each), bcrypt-hashed,
# single-use, and shown to the user in plaintext exactly once at the
# moment of regeneration.
#
# Endpoints (all require an access token — recovery codes are managed
# from inside the user's authenticated session):
#   POST /auth/mfa/recovery-codes/regenerate
#       → marks every existing unconsumed row consumed_at=now (replaced),
#         inserts ``RECOVERY_CODES_BATCH`` (10) fresh hashed rows, stamps
#         ``users.mfa_recovery_codes_generated_at`` and resets
#         ``mfa_recovery_codes_acknowledged=False``. Returns the plaintext
#         list of codes ONCE; the server cannot recover them after.
#   POST /auth/mfa/recovery-codes/acknowledge
#       → flips ``mfa_recovery_codes_acknowledged=True`` so the post-login
#         "show recovery codes" nudge stops appearing.
#   GET /auth/mfa/recovery-codes
#       → status only: {generated_at, acknowledged, total, remaining}.
#         Never returns the codes themselves.
#
# Verify path (in /auth/mfa/verify, factor_kind="recovery_code"):
#   _verify_recovery_code_and_complete iterates the user's unconsumed
#   rows, bcrypt-checks the supplied code (tolerant to case/spaces/
#   missing dashes via mfa_crypto._normalise_recovery_code), stamps
#   consumed_at, and completes the login. Bcrypt cost is ~250ms — the
#   per-challenge 5-attempt cap keeps total worst-case work bounded.

RECOVERY_CODES_BATCH = 10
RECOVERY_LOW_REMAINING_THRESHOLD = 3  # below this, surface the
                                      # mfa_recovery_codes_pending_view
                                      # nudge so the UI prompts a regen


class RecoveryCodesRegenerateRequest(BaseModel):
    # Re-auth proof. Required so a hijacked access token alone cannot
    # mint a fresh set of recovery codes and lock out the legitimate
    # owner. Once Step 7 ships, the require_recent_mfa dependency will
    # additionally gate this route; password re-auth is kept as the
    # belt-and-suspenders inner check.
    password: str


class RecoveryCodesRegenerateResponse(BaseModel):
    codes: List[str]
    generated_at: datetime
    total: int
    note: str = (
        "احفظ هذه الرموز في مكان آمن. لن تتمكن من رؤيتها مرة أخرى. "
        "Store these codes securely — they cannot be shown again."
    )


class RecoveryCodesStatusResponse(BaseModel):
    generated_at: Optional[datetime] = None
    acknowledged: bool = False
    total: int = 0
    remaining: int = 0


def _ensure_recovery_allowed(user: dict) -> None:
    if "recovery_code" not in mfa_policy.allowed_factor_kinds(user):
        raise HTTPException(status_code=403, detail="رموز الاسترداد غير متاحة لحسابك")


@router.post(
    "/auth/mfa/recovery-codes/regenerate",
    response_model=RecoveryCodesRegenerateResponse,
)
async def recovery_codes_regenerate(
    body: RecoveryCodesRegenerateRequest,
    current_user: dict = Depends(get_current_user),
):
    """Burn the user's existing unconsumed recovery codes and issue
    ``RECOVERY_CODES_BATCH`` new ones. Returns the plaintext codes
    ONCE — the server stores only bcrypt hashes.

    Requires the user's current password as re-auth proof so a
    hijacked access token alone cannot mint a fresh set of codes and
    persist past the legitimate owner's password rotation.
    """
    _ensure_recovery_allowed(current_user)

    # Re-auth proof. Failed attempts are audited for the abuse-detection
    # tooling that Step 8 hooks into.
    from dependencies import verify_password as _verify_password
    if not body.password or not _verify_password(
        body.password, current_user.get("password_hash") or ""
    ):
        try:
            audit = AuditLogEngine(Repos(db.session))
            await audit.log_auth_event(
                action="mfa.recovery.regenerate.denied",
                user_id=current_user["id"],
                tenant_id=current_user.get("tenant_id"),
                success=False,
                email=current_user.get("email"),
                reason="password_invalid",
            )
        except Exception as exc:
            logger.debug(f"recovery_codes_regenerate: audit denied failed: {exc}")
        raise HTTPException(status_code=401, detail="كلمة المرور غير صحيحة")

    user_id = current_user["id"]
    now = datetime.now(timezone.utc)

    # Burn every existing unconsumed row in a single atomic UPDATE so a
    # leaked old code cannot be used after a regen and there is never a
    # window where a user has more than RECOVERY_CODES_BATCH active
    # codes. Rows are kept (consumed_at stamped) because the Step-8
    # audit hash chain references them.
    try:
        from sqlalchemy import text as _sa_text
        await db.session.execute(
            _sa_text(
                "UPDATE mfa_recovery_codes "
                "SET consumed_at = :now "
                "WHERE user_id = :uid AND consumed_at IS NULL"
            ),
            {"now": now, "uid": user_id},
        )
    except Exception as exc:
        logger.warning(f"recovery_codes_regenerate: bulk burn failed: {exc}")
        raise HTTPException(status_code=500, detail="تعذّر تجديد رموز الاسترداد")

    # Generate, hash, persist.
    plaintext: List[str] = []
    for _ in range(RECOVERY_CODES_BATCH):
        code = mfa_crypto.generate_recovery_code()
        plaintext.append(code)
        await gd_insert(
            db.session,
            "mfa_recovery_codes",
            {
                "id": str(uuid.uuid4()),
                "user_id": user_id,
                "code_hash": mfa_crypto.hash_recovery_code(code),
                "created_at": now,
                "consumed_at": None,
            },
        )

    # Stamp the generation marker on the user row + reset acknowledgement.
    try:
        await gd_update_one(
            db.session,
            "users",
            {"id": user_id},
            {
                "mfa_recovery_codes_generated_at": now,
                "mfa_recovery_codes_acknowledged": False,
            },
        )
    except Exception as exc:
        logger.warning(f"recovery_codes_regenerate: stamp user row failed: {exc}")

    try:
        audit = AuditLogEngine(Repos(db.session))
        await audit.log_auth_event(
            action="mfa.recovery.regenerated",
            user_id=user_id,
            tenant_id=current_user.get("tenant_id"),
            success=True,
            email=current_user.get("email"),
            reason=f"count={RECOVERY_CODES_BATCH}",
        )
    except Exception as exc:
        logger.debug(f"recovery_codes_regenerate: audit log failed: {exc}")

    return RecoveryCodesRegenerateResponse(
        codes=plaintext,
        generated_at=now,
        total=RECOVERY_CODES_BATCH,
    )


@router.post("/auth/mfa/recovery-codes/acknowledge")
async def recovery_codes_acknowledge(
    current_user: dict = Depends(get_current_user),
):
    """Flip the "user has saved their codes" flag so the post-login
    nudge stops appearing. The codes themselves are unchanged."""
    _ensure_recovery_allowed(current_user)
    try:
        await gd_update_one(
            db.session,
            "users",
            {"id": current_user["id"]},
            {"mfa_recovery_codes_acknowledged": True},
        )
    except Exception as exc:
        logger.warning(f"recovery_codes_acknowledge: update failed: {exc}")
        raise HTTPException(status_code=500, detail="تعذّر حفظ الإقرار")
    try:
        audit = AuditLogEngine(Repos(db.session))
        await audit.log_auth_event(
            action="mfa.recovery.acknowledged",
            user_id=current_user["id"],
            tenant_id=current_user.get("tenant_id"),
            success=True,
            email=current_user.get("email"),
        )
    except Exception as exc:
        logger.debug(f"recovery_codes_acknowledge: audit log failed: {exc}")
    return {"acknowledged": True}


@router.get("/auth/mfa/recovery-codes", response_model=RecoveryCodesStatusResponse)
async def recovery_codes_status(
    current_user: dict = Depends(get_current_user),
):
    """Counts only — never returns the codes themselves."""
    _ensure_recovery_allowed(current_user)
    rows = await gd_find(
        db.session, "mfa_recovery_codes", {"user_id": current_user["id"]}
    )
    total = len(rows)
    remaining = sum(1 for r in rows if r.get("consumed_at") is None)
    gen_at = current_user.get("mfa_recovery_codes_generated_at")
    if isinstance(gen_at, str):
        try:
            gen_at = datetime.fromisoformat(gen_at.replace("Z", "+00:00"))
        except Exception:
            gen_at = None
    return RecoveryCodesStatusResponse(
        generated_at=gen_at,
        acknowledged=bool(current_user.get("mfa_recovery_codes_acknowledged")),
        total=total,
        remaining=remaining,
    )


async def _verify_recovery_code_and_complete(
    *, user: dict, challenge: dict, code: str, request: Optional[Request],
    stepup_only: bool = False,
):
    """Verify a single-use recovery code, mark it consumed, and
    complete the login. Bcrypt verifies are slow (~250 ms each) so we
    cap the per-call check at the user's first 50 unconsumed rows; in
    practice a user has 10 active rows, and the per-challenge 5-attempt
    cap further bounds work."""
    rows = await gd_find(
        db.session, "mfa_recovery_codes", {"user_id": user["id"]}
    )
    fresh = [r for r in rows if r.get("consumed_at") is None][:50]

    if not fresh:
        await _bump_challenge_attempts(challenge)
        try:
            audit = AuditLogEngine(Repos(db.session))
            await audit.log_auth_event(
                action="mfa.login.failure",
                user_id=user["id"],
                tenant_id=user.get("tenant_id"),
                success=False,
                email=user.get("email"),
                reason="recovery_no_codes",
            )
        except Exception as exc:
            logger.debug(f"verify_mfa(recovery): audit log failed: {exc}")
        raise HTTPException(status_code=400, detail="لا توجد رموز استرداد فعّالة لهذا الحساب")

    matched = None
    for row in fresh:
        if mfa_crypto.verify_recovery_code(code, row.get("code_hash") or ""):
            matched = row
            break

    if not matched:
        await _bump_challenge_attempts(challenge)
        try:
            audit = AuditLogEngine(Repos(db.session))
            await audit.log_auth_event(
                action="mfa.login.failure",
                user_id=user["id"],
                tenant_id=user.get("tenant_id"),
                success=False,
                email=user.get("email"),
                reason="recovery_invalid",
            )
        except Exception as exc:
            logger.debug(f"verify_mfa(recovery): audit log failed: {exc}")
        raise HTTPException(status_code=400, detail="رمز الاسترداد غير صحيح")

    # Mark consumed BEFORE completing login so a concurrent racing call
    # cannot reuse the same row. _complete_mfa_login is the final step.
    now = datetime.now(timezone.utc)
    try:
        await gd_update_one(
            db.session,
            "mfa_recovery_codes",
            {"id": matched["id"]},
            {"consumed_at": now},
        )
    except Exception as exc:
        logger.warning(f"verify_mfa(recovery): consumed_at update failed: {exc}")

    # Step 6 deferral satisfied here in Step 7: a recovery-code redemption
    # sets mfa_must_restore_factor=True so the require_recent_mfa
    # dependency refuses every Tier-A sensitive route with
    # MFA_RESTORE_REQUIRED until the user re-enrols a normal factor
    # (Passkey or TOTP). Tier B/C users can ignore this flag — their
    # require_recent_mfa branch is the freshness check only.
    try:
        await gd_update_one(
            db.session,
            "users",
            {"id": user["id"]},
            {"mfa_must_restore_factor": True},
        )
    except Exception as exc:
        logger.warning(f"verify_mfa(recovery): mfa_must_restore_factor stamp failed: {exc}")

    response = await _complete_mfa_login(user, challenge, "recovery_code", request, stepup_only=stepup_only)

    # If the user is now low on codes, force the post-login nudge regardless
    # of the acknowledgement flag — they must regenerate before they get
    # locked out. (Only meaningful for the full-login response shape; the
    # step-up dict response has no equivalent flag to attach.)
    remaining_after = sum(
        1 for r in fresh if r["id"] != matched["id"] and r.get("consumed_at") is None
    )
    if remaining_after <= RECOVERY_LOW_REMAINING_THRESHOLD and not stepup_only:
        response = response.copy(update={"mfa_recovery_codes_pending_view": True})
    return response
