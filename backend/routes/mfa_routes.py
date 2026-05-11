"""
NASSAQ — MFA routes (Task #169)

Step 2 deliverable: skeleton routes that the login flow and the future
factor-specific verify routes (TOTP / WebAuthn / email-OTP / recovery)
plug into. The actual factor verification logic ships in Steps 3-6 — this
module provides the consistent challenge-token validation, the factors
listing endpoint, and a verify endpoint that returns 501 until the
factor handlers are wired in.

Authentication model
--------------------
These routes do NOT use ``get_current_user`` because the caller has not
yet completed login. Instead they validate the short-lived
``type=mfa_challenge`` JWT minted by ``/auth/login`` against a row in
``mfa_pending_challenges``. The challenge row records ``attempts`` and
``consumed_at``; the helper below is the single place that bumps those.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import List, Optional

import jwt
from fastapi import APIRouter, Depends, HTTPException, Header
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from dependencies import db, JWT_SECRET, JWT_ALGORITHM
from engines.sql_utils import gd_find, gd_find_one, gd_update_one
from services import mfa_policy

logger = logging.getLogger("nassaq.mfa")

router = APIRouter()
_security = HTTPBearer(auto_error=True)


async def _resolve_challenge(credentials: HTTPAuthorizationCredentials) -> tuple[dict, dict]:
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


# ---- factor inventory ------------------------------------------------------

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
    tier: Optional[str] = None  # 'A' | 'B' | 'C' | None (no MFA required)
    allowed_kinds: List[str]
    factors: List[MfaFactorView]
    unused_recovery_codes: int = 0
    mfa_must_restore_factor: bool = False
    mfa_recovery_codes_acknowledged: bool = False


@router.get("/auth/mfa/factors", response_model=MfaFactorsResponse)
async def list_mfa_factors(
    credentials: HTTPAuthorizationCredentials = Depends(_security),
):
    """List the current user's enrolled factors.

    Accepts EITHER a normal access bearer token (for use from
    ``AccountSettingsPage``) OR an mfa_challenge token (for use from the
    login MFA challenge screen, where the user does not yet have an access
    token). This is the only MFA route that accepts both — every verify
    route requires the challenge token.
    """
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="انتهت صلاحية الرمز")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="رمز غير صالح")

    tok_type = payload.get("type")
    if tok_type not in ("access", "mfa_challenge"):
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

    # Recovery codes are tracked separately — we only surface the count of
    # unused codes (never the values).
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


# ---- verify (skeleton — Steps 3-6 fill in) --------------------------------

class MfaVerifyRequest(BaseModel):
    factor_kind: str  # 'totp' | 'webauthn' | 'email_otp' | 'recovery'
    code: Optional[str] = None
    webauthn_response: Optional[dict] = None


@router.post("/auth/mfa/verify")
async def verify_mfa(
    body: MfaVerifyRequest,
    credentials: HTTPAuthorizationCredentials = Depends(_security),
):
    """Consume an MFA pending challenge by presenting a valid factor proof.

    Step 2 ships only the challenge resolution + per-kind dispatch shell.
    The actual factor handlers (TOTP / WebAuthn / email_otp / recovery)
    are wired in Steps 3-6 of the plan. Until then this returns 501 so the
    frontend can integration-test the routing without us silently
    minting tokens for no reason.
    """
    challenge, user = await _resolve_challenge(credentials)

    allowed = mfa_policy.allowed_factor_kinds(user)
    if body.factor_kind not in allowed:
        await gd_update_one(
            db.session,
            "mfa_pending_challenges",
            {"id": challenge["id"]},
            {"attempts": (challenge.get("attempts") or 0) + 1},
        )
        raise HTTPException(status_code=400, detail="نوع العامل غير مسموح لهذا الحساب")

    raise HTTPException(
        status_code=501,
        detail="MFA verify handler not yet implemented (Steps 3-6 of plan)",
    )
