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
from engines.sql_utils import gd_find, gd_find_one, gd_insert, gd_update_one
from repositories import Repos
from services import mfa_crypto, mfa_policy, mfa_webauthn
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

    # email_otp / recovery land in Steps 5-6.
    raise HTTPException(
        status_code=501,
        detail=f"MFA verify handler for {body.factor_kind!r} not yet implemented",
    )


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
) -> TokenResponse:
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
    return await _complete_mfa_login(user, challenge, "webauthn", request)


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
