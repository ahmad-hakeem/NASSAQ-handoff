"""
NASSAQ Route Module: Authentication, login, role context, password, role switching
Auto-consolidated during Phase 8 modularization.
"""
from fastapi import APIRouter, HTTPException, Depends, status, Header, Query, Body, Request, BackgroundTasks
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import Response
from starlette.responses import StreamingResponse
from pydantic import BaseModel, Field, ConfigDict, EmailStr, model_validator, field_validator
from typing import List, Optional, Any, Dict
from datetime import datetime, timezone, timedelta

import uuid, os, logging, json, random, re, io, base64, jwt

from dependencies import (
    db, get_current_user, require_roles, require_recent_mfa, UserRole, SchoolStatus,
    hash_password, verify_password, create_access_token, create_refresh_token,
    JWT_SECRET, JWT_ALGORITHM, ACCESS_TOKEN_EXPIRE, security, logger,
    audit_engine, AuditAction, AuditSeverity,
    smart_scheduling_engine, TimetableRunStatus, TimetableStatus,
    ConflictType, ConflictSeverity, PreValidationResult, GenerationResult,
    hakim_engine, reporting_engine, export_engine, session_engine,
    REPORT_TYPES, generate_student_qr_code
)

from engines.sql_utils import gd_find, gd_find_one, gd_insert, gd_insert_many, gd_update_one, gd_update_many, gd_count, gd_delete_one, gd_delete_many, gd_distinct, gd_upsert, _gd_aggregate
from shared_models import (
    UserCreate, UserLogin, UserResponse, TokenResponse,
    validate_password_complexity,
)

router = APIRouter()



# ============== AUTH ROUTES ==============
@router.post("/auth/register", response_model=TokenResponse)
async def register(user_data: UserCreate):
    user_data.role = UserRole.STUDENT
    user_data.tenant_id = None

    try:
        validate_password_complexity(user_data.password)
    except ValueError:
        raise HTTPException(status_code=400, detail="كلمة المرور لا تستوفي متطلبات التعقيد")

    existing = await gd_find_one(db.session, "users", {"email": user_data.email})
    if existing:
        raise HTTPException(status_code=400, detail="البريد الإلكتروني مسجل مسبقاً")
    
    # Create user
    user_id = str(uuid.uuid4())
    user_doc = {
        "id": user_id,
        "email": user_data.email,
        "password_hash": hash_password(user_data.password),
        "full_name": user_data.full_name,
        "full_name_en": user_data.full_name_en,
        "role": user_data.role.value,
        "tenant_id": user_data.tenant_id,
        "phone": user_data.phone,
        "avatar_url": None,
        "is_active": True,
        "preferred_language": "ar",
        "preferred_theme": "light",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    
    await gd_insert(db.session, "users", user_doc)
    
    # Create token
    token = create_access_token({"sub": user_id, "role": user_data.role.value})
    
    user_response = UserResponse(
        id=user_id,
        email=user_data.email,
        full_name=user_data.full_name,
        full_name_en=user_data.full_name_en,
        role=user_data.role,
        tenant_id=user_data.tenant_id,
        phone=user_data.phone,
        avatar_url=None,
        is_active=True,
        preferred_language="ar",
        preferred_theme="light",
        created_at=user_doc["created_at"]
    )
    
    return TokenResponse(access_token=token, user=user_response)

def _parse_user_agent(ua: str) -> dict:
    """Best-effort parse of User-Agent → {device, browser, os}."""
    if not ua:
        return {"device": "Unknown", "browser": "Unknown", "os": "Unknown"}
    s = ua.lower()
    if "iphone" in s:
        device, os_name = "iPhone", "iOS"
    elif "ipad" in s:
        device, os_name = "iPad", "iPadOS"
    elif "android" in s:
        device, os_name = "Android", "Android"
    elif "windows" in s:
        device, os_name = "Windows PC", "Windows"
    elif "mac os" in s or "macintosh" in s:
        device, os_name = "Mac", "macOS"
    elif "linux" in s:
        device, os_name = "Linux PC", "Linux"
    else:
        device, os_name = "Desktop", "Unknown"
    if "edg/" in s or "edge/" in s:
        browser = "Edge"
    elif "chrome/" in s and "chromium" not in s:
        browser = "Chrome"
    elif "firefox/" in s:
        browser = "Firefox"
    elif "safari/" in s and "chrome" not in s:
        browser = "Safari"
    elif "opera" in s or "opr/" in s:
        browser = "Opera"
    else:
        browser = "Browser"
    return {"device": device, "browser": browser, "os": os_name}


async def _record_session_from_token(session, token_str: str, user_id: str, ip_address, user_agent):
    """Decode token, extract jti+exp, insert a user_sessions row. Best-effort."""
    try:
        payload = jwt.decode(token_str, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        jti = payload.get("jti")
        exp = payload.get("exp")
        if not jti:
            return
        from datetime import timezone as _tz
        expires_at = datetime.fromtimestamp(exp, tz=_tz.utc) if exp else None
        ua_info = _parse_user_agent(user_agent or "")
        await gd_insert(session, "user_sessions", {
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "jti": jti,
            "device": ua_info["device"],
            "browser": ua_info["browser"],
            "os": ua_info["os"],
            "ip_address": ip_address,
            "user_agent": (user_agent or "")[:1000],
            "expires_at": expires_at,
            "created_at": datetime.now(_tz.utc),
            "last_seen_at": datetime.now(_tz.utc),
        })
    except Exception as _e:
        logger.debug(f"_record_session_from_token failed: {_e}")


@router.post("/auth/login", response_model=TokenResponse)
async def login(credentials: UserLogin, request: Request, background_tasks: BackgroundTasks):
    from middleware.rate_limiter import rate_store

    # Per-account brute-force protection: limit login attempts by email address
    # regardless of source IP. This prevents credential-stuffing attacks even
    # when the per-IP limit is circumvented (e.g. distributed bots).
    account_key = f"login_account:{credentials.email.lower()}"
    acc_limited, _acc_rem, _acc_retry = await rate_store.is_rate_limited(account_key, 10, 60)
    if acc_limited:
        raise HTTPException(
            status_code=429,
            detail="عدد محاولات تسجيل الدخول تجاوز الحد المسموح. يرجى المحاولة بعد دقيقة",
        )

    user = await gd_find_one(db.session, "users", {"email": credentials.email})
    if not user:
        # Log failed login attempt
        await audit_engine.log_auth_event(
            action=AuditAction.LOGIN_FAILED.value,
            user_id=None,
            success=False,
            email=credentials.email,
            reason="user_not_found"
        )
        raise HTTPException(status_code=401, detail="بيانات الدخول غير صحيحة")
    
    if not verify_password(credentials.password, user["password_hash"]):
        # Log failed login attempt
        await audit_engine.log_auth_event(
            action=AuditAction.LOGIN_FAILED.value,
            user_id=str(user["_id"]),
            tenant_id=user.get("tenant_id"),
            success=False,
            email=credentials.email,
            reason="invalid_password"
        )
        raise HTTPException(status_code=401, detail="بيانات الدخول غير صحيحة")
    
    if not user.get("is_active", True):
        # Log failed login attempt
        await audit_engine.log_auth_event(
            action=AuditAction.LOGIN_FAILED.value,
            user_id=str(user["_id"]),
            tenant_id=user.get("tenant_id"),
            success=False,
            email=credentials.email,
            reason="account_disabled"
        )
        raise HTTPException(status_code=401, detail="الحساب معطل")

    if user.get("is_locked", False):
        await audit_engine.log_auth_event(
            action=AuditAction.LOGIN_FAILED.value,
            user_id=str(user.get("id") or user["_id"]),
            tenant_id=user.get("tenant_id"),
            success=False,
            email=credentials.email,
            reason="account_locked"
        )
        raise HTTPException(status_code=401, detail="الحساب مقفل. يرجى التواصل مع الإدارة")
    
    user_id = user.get("id") or str(user["_id"])

    # ── MFA challenge gate (Task #169) ──────────────────────────────────────
    # If the user has any active second factor enrolled, do NOT mint access
    # tokens here. Instead create a short-lived ``mfa_pending_challenges``
    # row and return a ``type=mfa_challenge`` JWT. The frontend then calls
    # ``/auth/mfa/verify`` with a factor proof to exchange the challenge
    # for real tokens.
    #
    # Users without any active factor enrolled keep getting normal tokens
    # for now — Tier A enforcement (block login if no passkey) ships with
    # the enrolment wizard in Step 9 of the plan, gated by ``MFA_GRACE_UNTIL``.
    try:
        from dependencies import create_mfa_challenge_token
        from services import mfa_policy
        from engines.sql_utils import gd_insert
        active_factors = await gd_find(db.session, "mfa_factors", {"user_id": user_id, "is_active": True}) or []
        tier = mfa_policy.required_for(user)
        # Tier B (teacher) and Tier C (parent) always get a challenge — their
        # email_otp factor is implicit (the user record's email IS the factor)
        # so a missing mfa_factors row is the expected normal case. Tier A
        # users still require an explicitly enrolled factor row here; the
        # "force enrolment if Tier A and zero factors" gate ships with the
        # login UI in Step 10 (gated by MFA_GRACE_UNTIL).
        from services.mfa_policy import MfaTier as _MfaTier
        implicit_email_otp = tier in (_MfaTier.B, _MfaTier.C)
        if tier is not None and (active_factors or implicit_email_otp):
            challenge_token, challenge_jti, challenge_exp = create_mfa_challenge_token(
                user_id, user["role"], user.get("tenant_id"),
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
                    "remember_me": bool(credentials.remember_me),
                },
            )
            await audit_engine.log_auth_event(
                action="mfa.challenge_issued",
                user_id=user_id,
                tenant_id=user.get("tenant_id"),
                success=True,
                email=credentials.email,
            )
            allowed_for_user = mfa_policy.allowed_factor_kinds(user)
            enrolled_kinds = {
                f.get("kind") for f in active_factors
                if f.get("kind") in allowed_for_user
            }
            # email_otp is always available for Tier B/C even with zero rows.
            if implicit_email_otp and "email_otp" in allowed_for_user:
                enrolled_kinds.add("email_otp")
            # recovery_code is available iff the user has at least one
            # unconsumed row (a Step-6 backup factor).
            if "recovery_code" in allowed_for_user:
                try:
                    rc_rows = await gd_find(
                        db.session,
                        "mfa_recovery_codes",
                        {"user_id": user_id, "consumed_at": None},
                    ) or []
                    if rc_rows:
                        enrolled_kinds.add("recovery_code")
                except Exception as _rc_err:
                    logger.debug(f"login: recovery_code availability lookup failed: {_rc_err}")
            available_kinds = sorted(k for k in enrolled_kinds if k)
            return TokenResponse(
                mfa_required=True,
                mfa_tier=tier.value,
                mfa_enrollment_required=False,
                challenge_token=challenge_token,
                available_factor_kinds=available_kinds,
                challenge_expires_at=challenge_exp.isoformat(),
            )
    except HTTPException:
        raise
    except Exception as _mfa_err:
        # SECURITY (Task #169 Step 8 hardening — was previously fail-OPEN):
        # If the MFA challenge plumbing itself errors we MUST NOT fall through
        # to issuing a fully-authenticated session. For any user whose role
        # falls under an MFA tier (A/B/C — i.e. anyone other than student /
        # gatekeeper / driver) we fail CLOSED with a 503 and a safe Arabic
        # message. The login attempt is audited as a critical failure so SOC
        # tooling can flag a suspicious surge (which would otherwise look
        # like normal "MFA service down" noise). Out-of-tier users still
        # proceed to token issuance — they have no second factor required by
        # policy, so refusing them would lock the platform out without any
        # security benefit.
        logger.error(f"login: MFA challenge gate errored for user={user_id}: {_mfa_err}", exc_info=True)
        try:
            from services import mfa_policy as _mp
            _tier_on_err = _mp.required_for(user)
        except Exception:
            # If we cannot even determine the tier, treat the user as
            # in-tier (the conservative choice) so we never accidentally
            # admit a Tier-A/B/C user without a second factor.
            _tier_on_err = True

        if _tier_on_err is not None:
            try:
                await audit_engine.log_auth_event(
                    action="mfa.login.failure",
                    user_id=user_id,
                    tenant_id=user.get("tenant_id"),
                    success=False,
                    email=credentials.email,
                    reason=f"mfa_gate_error:{type(_mfa_err).__name__}",
                )
            except Exception as _audit_err:
                logger.debug(f"login: failed to audit mfa gate error: {_audit_err}")
            raise HTTPException(
                status_code=503,
                detail={
                    "code": "MFA_UNAVAILABLE",
                    "message": "MFA service is temporarily unavailable",
                    "message_ar": "خدمة التحقق متعدد العوامل غير متاحة مؤقتاً. يرجى المحاولة لاحقاً",
                },
            )
        # Out-of-tier user (e.g. student) → fall through to normal token
        # issuance below. Logged as a warning, not error, since it's expected
        # for those roles.
        logger.warning(f"login: MFA gate skipped for out-of-tier user={user_id}")

    token_payload = {"sub": user_id, "role": user["role"]}
    if user.get("tenant_id"):
        token_payload["tenant_id"] = user["tenant_id"]
    if user.get("school_id"):
        token_payload["school_id"] = user["school_id"]
    token = create_access_token(token_payload)
    try:
        _acc_jti = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM]).get("jti")
    except Exception:
        _acc_jti = None
    refresh = create_refresh_token(token_payload, remember_me=credentials.remember_me, linked_access_jti=_acc_jti)

    # Track this login as an active session row (best-effort, non-blocking)
    _ip = request.client.host if request and request.client else None
    _ua = request.headers.get("user-agent") if request else None
    await _record_session_from_token(db.session, token, user_id, _ip, _ua)

    # Fire-and-forget the success audit log so it doesn't block the response.
    # Use an independent session/engine instance because the request-scoped
    # session is committed/closed by the middleware before the background task
    # would otherwise run, which corrupts the pooled connection.
    # Failure logs above remain synchronous to guarantee they're persisted.
    async def _log_login_async(uid, tid, email):
        try:
            from db import async_session_factory
            from repositories import Repos
            from engines.audit_engine import AuditLogEngine
            from engines.sql_utils import gd_update_one
            async with async_session_factory() as bg_session:
                bg_repos = Repos(bg_session)
                bg_engine = AuditLogEngine(bg_repos)
                await bg_engine.log_auth_event(
                    action=AuditAction.LOGIN.value,
                    user_id=uid,
                    tenant_id=tid,
                    success=True,
                    email=email,
                )
                try:
                    await gd_update_one(
                        bg_session, "users",
                        {"id": uid},
                        {"$set": {"last_login": datetime.now(timezone.utc).isoformat()}},
                    )
                except Exception as _ue:
                    logger.debug(f"Background last_login update failed: {_ue}")
                await bg_session.commit()
        except Exception as _e:
            logger.debug(f"Background login audit failed: {_e}")

    background_tasks.add_task(
        _log_login_async, user_id, user.get("tenant_id"), credentials.email
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
        parent_id=user.get("parent_id")
    )
    
    return TokenResponse(access_token=token, refresh_token=refresh, user=user_response)


class RefreshTokenRequest(BaseModel):
    refresh_token: str


@router.post("/auth/refresh", response_model=TokenResponse)
async def refresh_token(body: RefreshTokenRequest, request: Request):
    try:
        payload = jwt.decode(body.refresh_token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Refresh token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid token type")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    # Phase 3 (audit Open Question 5): refresh-token family check. If the
    # whole family was revoked (e.g. due to a previously detected reuse),
    # refuse here — even before consulting revoked_tokens for the individual
    # jti — so that ALL siblings spawned from the compromised lineage are
    # killed in one shot.
    _fid = payload.get("fid")
    if _fid:
        try:
            from sqlalchemy import text as _sa_text_fid
            row = (await db.session.execute(
                _sa_text_fid("SELECT family_id FROM revoked_token_families WHERE family_id=:f"),
                {"f": _fid},
            )).first()
            if row:
                raise HTTPException(status_code=401, detail="Refresh token family has been revoked")
        except HTTPException:
            raise
        except Exception as _fid_err:
            # Schema not migrated yet → fall through. A missing migration
            # must not break refresh; the per-jti revocation check below
            # still applies.
            logger.debug(f"refresh: family check skipped: {_fid_err}")

    user = await gd_find_one(db.session, "users", {"id": user_id})
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    if not user.get("is_active", True):
        raise HTTPException(status_code=401, detail="Account disabled")
    if user.get("is_locked", False):
        raise HTTPException(status_code=401, detail="Account is locked")

    # Reject refresh tokens issued before the last password change.
    # This ensures that after a password change or reset, all previously
    # issued refresh tokens (e.g. on a stolen device) are invalidated.
    #
    # Security policy:
    #   - If last_password_change is set AND the token has no iat claim,
    #     reject it — tokens without iat cannot be verified against the
    #     password-change boundary and must not be accepted.
    #   - If both are present, compare timestamps and reject stale tokens.
    last_pw_change = user.get("last_password_change")
    token_iat = payload.get("iat")
    if last_pw_change:
        if token_iat is None:
            # Legacy token without iat — cannot verify issuance time relative
            # to password change. Force re-login for safety.
            raise HTTPException(
                status_code=401,
                detail="انتهت صلاحية الجلسة. يرجى تسجيل الدخول مجدداً"
            )
        try:
            _lpc_str = last_pw_change if isinstance(last_pw_change, str) else str(last_pw_change)
            _lpc_str = _lpc_str.replace("Z", "+00:00")
            pw_change_ts = datetime.fromisoformat(_lpc_str).timestamp()
            if token_iat < pw_change_ts:
                raise HTTPException(
                    status_code=401,
                    detail="انتهت صلاحية الجلسة بسبب تغيير كلمة المرور. يرجى تسجيل الدخول مجدداً"
                )
        except HTTPException:
            raise
        except Exception as _ts_err:
            logger.debug(f"refresh: last_password_change parse failed: {_ts_err}")

    token_payload = {"sub": user_id, "role": user["role"]}
    if user.get("tenant_id"):
        token_payload["tenant_id"] = user["tenant_id"]
    if user.get("school_id"):
        token_payload["school_id"] = user["school_id"]

    # ATOMIC REFRESH-TOKEN ROTATION (TOCTOU-safe):
    # Claim the old refresh jti by inserting it into revoked_tokens FIRST.
    # The PRIMARY KEY constraint on revoked_tokens.jti means concurrent
    # replays will get IntegrityError → exactly one rotation succeeds.
    # If the insert fails for any reason (duplicate or DB error), we refuse
    # to mint new tokens (no fail-open).
    from datetime import datetime as _dt2, timezone as _tz2
    from sqlalchemy import text as _sa_text
    from sqlalchemy.exc import IntegrityError as _IE
    now2 = _dt2.now(_tz2.utc)
    old_refresh_jti = payload.get("jti")
    if not old_refresh_jti:
        # Strict claim-or-deny: legacy refresh tokens issued before jti was
        # added cannot be safely rotated. Force re-login.
        raise HTTPException(status_code=401, detail="Refresh token must be reissued, please log in again")
    try:
        old_exp = payload.get("exp")
        old_exp_dt = (
            _dt2.fromtimestamp(old_exp, tz=_tz2.utc) if old_exp else now2
        )
        # Use a savepoint so an IntegrityError (replay) only rolls back the
        # claim, leaving the outer transaction usable for the family-
        # revocation insert below.
        async with db.session.begin_nested():
            await db.session.execute(
                _sa_text(
                    "INSERT INTO revoked_tokens (jti, expires_at, revoked_at) "
                    "VALUES (:jti, :exp, :rev)"
                ),
                {"jti": old_refresh_jti, "exp": old_exp_dt, "rev": now2},
            )
    except _IE:
        # Duplicate → token was already rotated (concurrent or sequential replay).
        # Phase 3: this is the canonical stolen-refresh-token signal. Revoke
        # the ENTIRE family so any sibling token spawned from this lineage
        # (legitimate or attacker-held) is killed too. The legitimate user
        # is forced to re-login; the attacker's chain dies.
        try:
            _replay_fid = payload.get("fid")
            if _replay_fid:
                await db.session.execute(
                    _sa_text(
                        "INSERT INTO revoked_token_families "
                        "(family_id, revoked_at, reason, user_id) "
                        "VALUES (:f, :r, :why, :uid) "
                        "ON CONFLICT (family_id) DO NOTHING"
                    ),
                    {"f": _replay_fid, "r": now2, "why": "refresh_token_reuse_detected", "uid": user_id},
                )
                await db.session.flush()
                logger.warning(
                    f"refresh: reuse detected — revoked family {_replay_fid} for user {user_id}"
                )
        except Exception as _fam_err:
            # Best-effort: even if we can't write the family revocation
            # (schema not migrated), the per-jti revocation already blocks
            # the replayed token.
            logger.debug(f"refresh: family revoke on reuse failed: {_fam_err}")
        raise HTTPException(status_code=401, detail="Refresh token has been revoked")
    except HTTPException:
        raise
    except Exception as _claim_err:
        logger.error(f"refresh: failed to claim old jti: {_claim_err}")
        raise HTTPException(status_code=500, detail="Failed to rotate refresh token")

    # Task #169 Step 7: refresh PRESERVES but does NOT advance mfa_recent_at
    # (and the companion mfa_kind tag). The only paths that advance the
    # timestamp are /auth/mfa/verify and /auth/mfa/stepup/verify.
    _preserved_mfa_recent_at = payload.get("mfa_recent_at")
    _preserved_mfa_kind = payload.get("mfa_kind")

    new_access = create_access_token(
        token_payload,
        mfa_recent_at=_preserved_mfa_recent_at,
        mfa_kind=_preserved_mfa_kind,
    )
    try:
        new_acc_jti = jwt.decode(new_access, JWT_SECRET, algorithms=[JWT_ALGORITHM]).get("jti")
    except Exception:
        new_acc_jti = None

    is_remember_me = payload.get("rm", False)
    # Preserve family id across rotation so reuse-detection works on the
    # whole lineage.
    new_refresh = create_refresh_token(
        token_payload,
        remember_me=is_remember_me,
        linked_access_jti=new_acc_jti,
        family_id=payload.get("fid"),
        mfa_recent_at=_preserved_mfa_recent_at,
        mfa_kind=_preserved_mfa_kind,
    )

    # Best-effort: revoke the prior access-session row tied to this refresh
    _r_ip = request.client.host if request and request.client else None
    _r_ua = request.headers.get("user-agent") if request else None
    try:
        prev_acc_jti = payload.get("acc_jti")
        if prev_acc_jti:
            await gd_update_one(
                db.session, "user_sessions",
                {"jti": prev_acc_jti, "user_id": user_id, "revoked_at": None},
                {"revoked_at": now2},
            )
    except Exception as _rev_err:
        logger.debug(f"refresh: prior session row revoke failed: {_rev_err}")
    await _record_session_from_token(db.session, new_access, user_id, _r_ip, _r_ua)

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
        parent_id=user.get("parent_id")
    )

    return TokenResponse(access_token=new_access, refresh_token=new_refresh, user=user_response)


class LogoutRequest(BaseModel):
    refresh_token: Optional[str] = None


@router.post("/auth/logout")
async def logout(
    request: Request,
    body: LogoutRequest = Body(default=LogoutRequest()),
    credentials: HTTPAuthorizationCredentials = Depends(security),
    current_user: dict = Depends(get_current_user)
):
    """
    Logout endpoint — revokes both the access token JTI and the refresh token
    JTI (when provided) by inserting them into revoked_tokens. This ensures
    that a stolen refresh token cannot be used to mint new access tokens after
    the legitimate user has logged out.
    """
    user_id = current_user.get("id") or str(current_user.get("_id", ""))
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    from datetime import timezone as _tz

    # Revoke the access token
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        jti = payload.get("jti")
        exp = payload.get("exp")
        if jti and exp:
            expires_at = datetime.fromtimestamp(exp, tz=_tz.utc)
            await gd_insert(db.session, "revoked_tokens", {
                "jti": jti,
                "expires_at": expires_at.isoformat(),
                "revoked_at": datetime.now(_tz.utc).isoformat(),
            })
            try:
                await gd_update_one(db.session, "user_sessions", {"jti": jti}, {"revoked_at": datetime.now(_tz.utc)})
            except Exception:
                pass
    except Exception:
        pass

    # Revoke the refresh token when the client provides it.
    # This closes the window where an attacker with a stolen refresh token
    # can keep minting new access tokens after the user logs out.
    if body.refresh_token:
        try:
            rt_payload = jwt.decode(body.refresh_token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
            rt_jti = rt_payload.get("jti")
            rt_exp = rt_payload.get("exp")
            if rt_jti and rt_exp and rt_payload.get("type") == "refresh":
                rt_expires_at = datetime.fromtimestamp(rt_exp, tz=_tz.utc)
                await gd_insert(db.session, "revoked_tokens", {
                    "jti": rt_jti,
                    "expires_at": rt_expires_at.isoformat(),
                    "revoked_at": datetime.now(_tz.utc).isoformat(),
                })
        except Exception:
            pass

    await audit_engine.log_auth_event(
        action=AuditAction.LOGOUT.value,
        user_id=user_id,
        tenant_id=current_user.get("tenant_id"),
        success=True,
        email=current_user.get("email"),
        ip_address=ip_address,
        user_agent=user_agent,
    )

    return {"message": "تم تسجيل الخروج بنجاح"}

@router.get("/auth/me", response_model=UserResponse)
async def get_me(current_user: dict = Depends(get_current_user)):
    from engines.name_validation import is_generic_name
    # Resolve the school's display name so the UI can show it without
    # needing a second round-trip (and without falling back to the UUID).
    tenant_name = None
    tenant_id = current_user.get("tenant_id")
    if tenant_id:
        school = await gd_find_one(db.session, "schools", {"id": tenant_id})
        if school:
            tenant_name = school.get("name_ar") or school.get("name") or school.get("name_en")
    return UserResponse(
        id=current_user["id"],
        email=current_user["email"],
        full_name=current_user["full_name"],
        full_name_en=current_user.get("full_name_en"),
        title=current_user.get("title"),
        role=UserRole(current_user["role"]),
        tenant_id=tenant_id,
        tenant_name=tenant_name,
        phone=current_user.get("phone"),
        avatar_url=current_user.get("avatar_url"),
        is_active=current_user.get("is_active") if current_user.get("is_active") is not None else True,
        must_change_password=bool(current_user.get("must_change_password")),
        has_generic_name=is_generic_name(current_user.get("full_name")),
        preferred_language=current_user.get("preferred_language") or "ar",
        preferred_theme=current_user.get("preferred_theme") or "light",
        created_at=current_user.get("created_at") or "",
        teacher_id=current_user.get("teacher_id"),
        student_id=current_user.get("student_id"),
        parent_id=current_user.get("parent_id"),
        is_switched=bool(current_user.get("is_switched")),
        original_role=current_user.get("original_role")
    )

@router.get("/auth/me/permissions")
async def get_my_permissions(current_user: dict = Depends(get_current_user)):
    """Phase 0 §4.B-6 — backend is the source of truth for the caller's
    permission set. The frontend uses this to seed role-aware UI without
    hardcoding role→permission mappings."""
    from middleware.rbac import RBACMiddleware, ROLE_PERMISSIONS
    role = current_user.get("role") or ""
    custom = current_user.get("permissions") or []
    permissions = RBACMiddleware.get_user_permissions(role, custom)
    return {
        "role": role,
        "permissions": permissions,
        "base_permissions": list(ROLE_PERMISSIONS.get(role, [])),
        "custom_permissions": list(custom),
    }


@router.get("/auth/permissions/role/{role}")
async def get_role_permissions(
    role: str,
    current_user: dict = Depends(require_roles([
        UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL,
        UserRole.SCHOOL_ADMIN, UserRole.SCHOOL_SUB_ADMIN,
    ]))
):
    """Phase 0 §4.B-6 — return the canonical permission set for a role so
    user-creation wizards can render the assignable permissions without
    hardcoding role→permission mappings on the client."""
    from middleware.rbac import ROLE_PERMISSIONS
    if role not in ROLE_PERMISSIONS:
        raise HTTPException(status_code=404, detail="الدور غير معروف")
    return {"role": role, "permissions": list(ROLE_PERMISSIONS[role])}


@router.put("/auth/preferences")
async def update_preferences(
    preferred_language: Optional[str] = None,
    preferred_theme: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    updates = {"updated_at": datetime.now(timezone.utc).isoformat()}
    if preferred_language:
        updates["preferred_language"] = preferred_language
    if preferred_theme:
        updates["preferred_theme"] = preferred_theme
    
    await gd_update_one(db.session, "users", {"id": current_user["id"]}, updates)
    return {"message": "تم تحديث الإعدادات"}





# ============== ACTIVE ROLE CONTEXT ==============
class ActiveRoleContextRequest(BaseModel):
    role_id: str
    school_id: Optional[str] = None
    scope_id: Optional[str] = None

class ActiveRoleContextResponse(BaseModel):
    user_identity_id: str
    role_id: str
    role_name: str
    school_id: Optional[str] = None
    school_name: Optional[str] = None
    scope_id: Optional[str] = None
    is_active: bool = True
    set_at: str
    access_token: Optional[str] = None
    token_type: Optional[str] = None

@router.post("/auth/set-active-role", response_model=ActiveRoleContextResponse)
async def set_active_role_context(
    context: ActiveRoleContextRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Set the active role context for the current session.
    تعيين سياق الدور النشط للجلسة الحالية
    """
    user_id = current_user["id"]
    now = datetime.now(timezone.utc).isoformat()
    
    # Validate user has this role
    user_roles = current_user.get("linked_roles", [])
    valid_role = None
    
    # Check primary role first
    if current_user.get("role") == context.role_id:
        primary_tenant = current_user.get("tenant_id")
        if context.school_id and context.school_id != primary_tenant:
            raise HTTPException(status_code=400, detail="المدرسة المحددة لا تتطابق مع دورك الأساسي")
        valid_role = {
            "role": current_user.get("role"),
            "tenant_id": primary_tenant,
            "is_active": True
        }
    else:
        # Check linked roles
        for role in user_roles:
            if role.get("role") == context.role_id and role.get("is_active", True):
                if context.school_id:
                    if role.get("tenant_id") == context.school_id:
                        valid_role = role
                        break
                else:
                    valid_role = role
                    break
    
    if not valid_role:
        raise HTTPException(status_code=400, detail="الدور غير متوفر للمستخدم")
    
    # Always use the validated role's tenant — never trust client-supplied school_id
    school_id = valid_role.get("tenant_id") or current_user.get("tenant_id")
    
    # Get school name if school_id provided
    school_name = None
    if school_id:
        school = await gd_find_one(db.session, "schools", {"id": school_id})
        if school:
            school_name = school.get("name_ar") or school.get("name_en")
    
    # Store active role context in user's session/document
    active_context = {
        "role_id": context.role_id,
        "school_id": school_id,
        "scope_id": context.scope_id,
        "set_at": now,
        "is_active": True
    }
    
    await gd_update_one(db.session, "users", {"id": user_id}, {
            "active_role_context": active_context,
            "updated_at": now
        })
    
    original_role = current_user.get("original_role") or current_user.get("role")
    new_token = create_access_token({
        "sub": user_id,
        "role": context.role_id,
        "tenant_id": school_id,
        "email": current_user.get("email", ""),
        "is_switched": True,
        "original_role": original_role,
    })

    return ActiveRoleContextResponse(
        user_identity_id=user_id,
        role_id=context.role_id,
        role_name=get_role_display_name(context.role_id),
        school_id=school_id,
        school_name=school_name,
        scope_id=context.scope_id,
        is_active=True,
        set_at=now,
        access_token=new_token,
        token_type="bearer",
    )

@router.get("/auth/active-role", response_model=ActiveRoleContextResponse)
async def get_active_role_context(current_user: dict = Depends(get_current_user)):
    """
    Get the current active role context.
    جلب سياق الدور النشط الحالي
    """
    user_id = current_user["id"]
    active_context = current_user.get("active_role_context")
    
    if not active_context:
        # Return default based on primary role
        school_id = current_user.get("tenant_id")
        school_name = None
        
        if school_id:
            school = await gd_find_one(db.session, "schools", {"id": school_id})
            if school:
                school_name = school.get("name_ar")
        
        return ActiveRoleContextResponse(
            user_identity_id=user_id,
            role_id=current_user.get("role", ""),
            role_name=get_role_display_name(current_user.get("role", "")),
            school_id=school_id,
            school_name=school_name,
            is_active=True,
            set_at=current_user.get("created_at", "")
        )
    
    # Get school name
    school_name = None
    if active_context.get("school_id"):
        school = await gd_find_one(db.session, "schools", {"id": active_context["school_id"]})
        if school:
            school_name = school.get("name_ar")
    
    return ActiveRoleContextResponse(
        user_identity_id=user_id,
        role_id=active_context.get("role_id", current_user.get("role", "")),
        role_name=get_role_display_name(active_context.get("role_id", current_user.get("role", ""))),
        school_id=active_context.get("school_id"),
        school_name=school_name,
        scope_id=active_context.get("scope_id"),
        is_active=active_context.get("is_active", True),
        set_at=active_context.get("set_at", "")
    )

def get_role_display_name(role: str) -> str:
    """Get Arabic display name for role"""
    role_names = {
        "platform_admin": "مدير المنصة",
        "school_principal": "مدير المدرسة",
        "school_sub_admin": "مشرف المدرسة",
        "teacher": "معلم",
        "student": "طالب",
        "parent": "ولي أمر"
    }
    return role_names.get(role, role)




# ============== FORGOT / RESET PASSWORD ==============
import hashlib

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def check_new_password(cls, v: str) -> str:
        return validate_password_complexity(v)

RESET_TOKEN_EXPIRE = timedelta(hours=1)

def _create_reset_token(user_id: str) -> str:
    payload = {
        "sub": user_id,
        "purpose": "password_reset",
        "jti": str(uuid.uuid4()),
        "exp": datetime.now(timezone.utc) + RESET_TOKEN_EXPIRE,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

# Canonical sha256 single-use token hash lives in ``backend/utils/tokens``
# so password-reset and parent-invitation flows share one scheme. The
# local alias is kept to minimise diff churn against the rest of this
# module's call sites.
from utils.tokens import token_hash as _token_hash  # noqa: E402

@router.post("/auth/forgot-password")
async def forgot_password(request: ForgotPasswordRequest):
    # SECURITY (audit H-3): per-email brute-force / enumeration limit, layered
    # on top of the per-IP middleware bucket. Mirrors the `login_account:`
    # pattern. Response stays generic regardless of outcome.
    from middleware.rate_limiter import rate_store
    email_key = f"forgot_password_email:{(request.email or '').strip().lower()}"
    limited, _, _ = await rate_store.is_rate_limited(email_key, 5, 3600)
    if limited:
        return {"message": "إذا كان البريد الإلكتروني مسجلاً، ستصلك رسالة لإعادة تعيين كلمة المرور"}

    user = await gd_find_one(db.session, "users", {"email": request.email})

    if user and user.get("is_active", True):
        token = _create_reset_token(user["id"])
        await gd_update_one(db.session, "users", {"id": user["id"]}, {
            "reset_token_hash": _token_hash(token),
            "reset_token_created_at": datetime.now(timezone.utc).isoformat(),
        })

        from engines.email_service import send_password_reset_email
        send_password_reset_email(
            to_email=request.email,
            user_name=user.get("full_name", ""),
            reset_token=token,
        )

        audit_log = {
            "id": str(uuid.uuid4()),
            "action": "password_reset_requested",
            "action_by": user["id"],
            "action_by_name": user.get("full_name", ""),
            "target_type": "user",
            "target_id": user["id"],
            "details": {"email": request.email},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        await gd_insert(db.session, "audit_logs", audit_log)

    return {"message": "إذا كان البريد الإلكتروني مسجلاً، ستصلك رسالة لإعادة تعيين كلمة المرور"}

@router.post("/auth/reset-password")
async def reset_password(request: ResetPasswordRequest):
    # SECURITY (audit H-3): layered limits applied AFTER JWT validation so
    # that no bucket can be moved by an unauthenticated/garbage payload, and
    # so that the limiter key is derived from a fully-discriminating value
    # rather than the constant JWT header prefix (which would near-globally
    # throttle every reset attempt — see architect review v3).
    #
    # Final layout:
    #   per-IP        — middleware bucket (RATE_LIMITS["/api/auth/reset-password"]).
    #   per-token     — sha256(full token) jti — caps brute-force against a single token.
    #   per-identity  — user_id from validated payload — caps total attempts
    #                   against any one victim across many distinct tokens.
    from middleware.rate_limiter import rate_store
    try:
        payload = jwt.decode(request.token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=400, detail="انتهت صلاحية رابط إعادة التعيين. يرجى طلب رابط جديد")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=400, detail="رابط إعادة التعيين غير صالح")

    if payload.get("purpose") != "password_reset":
        raise HTTPException(status_code=400, detail="رابط إعادة التعيين غير صالح")

    user_id = payload.get("sub")
    # Per-token bucket — keyed on the full-token sha256 (or jti when present)
    # so two distinct tokens never share a bucket. Token-prefix keys would
    # alias every JWT under a near-constant header and globally throttle
    # password resets.
    token_id = payload.get("jti") or _token_hash(request.token)
    token_key = f"reset_password_token:{token_id}"
    limited, _, _ = await rate_store.is_rate_limited(token_key, 10, 3600)
    if limited:
        raise HTTPException(status_code=429, detail="عدد المحاولات تجاوز الحد المسموح. يرجى المحاولة لاحقاً")
    # Per-identity bucket — caps total reset traffic per victim across
    # arbitrarily many distinct tokens.
    identity_key = f"reset_password_user:{user_id}"
    limited, _, _ = await rate_store.is_rate_limited(identity_key, 10, 3600)
    if limited:
        raise HTTPException(status_code=429, detail="عدد المحاولات تجاوز الحد المسموح. يرجى المحاولة لاحقاً")
    user = await gd_find_one(db.session, "users", {"id": user_id})
    if not user:
        raise HTTPException(status_code=400, detail="رابط إعادة التعيين غير صالح")

    stored_hash = user.get("reset_token_hash", "")
    if not stored_hash or stored_hash != _token_hash(request.token):
        raise HTTPException(status_code=400, detail="تم استخدام هذا الرابط مسبقاً. يرجى طلب رابط جديد")

    await gd_update_one(db.session, "users", {"id": user_id}, {
        "password_hash": hash_password(request.new_password),
        "reset_token_hash": None,
        "reset_token_created_at": None,
        "must_change_password": False,
        "last_password_change": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    })

    audit_log = {
        "id": str(uuid.uuid4()),
        "action": "password_reset_completed",
        "action_by": user_id,
        "action_by_name": user.get("full_name", ""),
        "target_type": "user",
        "target_id": user_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    await gd_insert(db.session, "audit_logs", audit_log)

    return {"message": "تم تعيين كلمة المرور الجديدة بنجاح. يمكنك تسجيل الدخول الآن"}


# ============== PASSWORD CHANGE ROUTE ==============
class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def check_new_password(cls, v: str) -> str:
        return validate_password_complexity(v)

@router.post("/auth/change-password")
async def change_password(
    request: PasswordChangeRequest,
    # Task #169 Step 7: change-password is a high-impact sensitive route,
    # gated by both the existing current-password check AND a fresh MFA
    # proof (≤5 minutes). require_recent_mfa returns the same user dict
    # as get_current_user, so the body of this handler is unchanged.
    current_user: dict = Depends(require_recent_mfa()),
):
    """
    Change user password. Required for first-time login with temporary password.
    """
    if not verify_password(request.current_password, current_user.get("password_hash", "")):
        raise HTTPException(status_code=400, detail="كلمة المرور الحالية غير صحيحة")
    
    if request.current_password == request.new_password:
        raise HTTPException(status_code=400, detail="كلمة المرور الجديدة يجب أن تكون مختلفة")
    
    # Update password and clear must_change_password flag
    await gd_update_one(db.session, "users", {"id": current_user["id"]}, {
            "password_hash": hash_password(request.new_password),
            "must_change_password": False,
            "last_password_change": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        })
    
    # Log password change
    audit_log = {
        "id": str(uuid.uuid4()),
        "action": "password_changed",
        "action_by": current_user["id"],
        "action_by_name": current_user.get("full_name", ""),
        "target_type": "user",
        "target_id": current_user["id"],
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    await gd_insert(db.session, "audit_logs", audit_log)
    
    return {"message": "تم تغيير كلمة المرور بنجاح"}




# ============== USER ROLE SWITCHING ==============
@router.get("/users/{user_id}/roles")
async def get_user_roles(
    user_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get all roles for a user"""
    # Only allow self or platform admin
    if current_user["id"] != user_id and current_user["role"] != "platform_admin":
        raise HTTPException(status_code=403, detail="غير مصرح")
    
    user = await gd_find_one(db.session, "users", {"id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="المستخدم غير موجود")
    
    roles = []
    
    # Primary role
    roles.append({
        "role": user.get("role") or user.get("primary_role"),
        "tenant_id": user.get("tenant_id") or user.get("primary_tenant_id"),
        "is_primary": True,
        "is_active": True
    })
    
    # Linked roles
    for linked in user.get("linked_roles", []):
        if linked.get("is_active"):
            roles.append({
                "role": linked.get("role"),
                "tenant_id": linked.get("tenant_id"),
                "scope_id": linked.get("scope_id"),
                "is_primary": False,
                "is_active": True
            })
    
    return {"roles": roles, "total": len(roles)}


@router.post("/users/{user_id}/switch-role")
async def switch_user_role(
    user_id: str,
    target_role: str,
    target_tenant_id: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """Switch active role for a user"""
    # Only allow self
    if current_user["id"] != user_id:
        raise HTTPException(status_code=403, detail="يمكنك فقط تبديل دورك الخاص")
    
    user = await gd_find_one(db.session, "users", {"id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="المستخدم غير موجود")
    
    # Get available roles
    available_roles = []
    primary_role = user.get("role") or user.get("primary_role")
    primary_tenant = user.get("tenant_id") or user.get("primary_tenant_id")
    
    available_roles.append({"role": primary_role, "tenant_id": primary_tenant})
    
    for linked in user.get("linked_roles", []):
        if linked.get("is_active"):
            available_roles.append({
                "role": linked.get("role"),
                "tenant_id": linked.get("tenant_id")
            })
    
    # Check if target role is valid
    role_valid = any(
        r["role"] == target_role and r["tenant_id"] == target_tenant_id
        for r in available_roles
    )
    
    if not role_valid:
        raise HTTPException(status_code=400, detail="ليس لديك صلاحية الوصول لهذا الدور")
    
    # Audit log
    now = datetime.now(timezone.utc).isoformat()
    await gd_insert(db.session, "audit_logs", {
        "id": str(uuid.uuid4()),
        "action": "role_switched",
        "action_category": "identity",
        "actor_id": user_id,
        "actor_name": user.get("full_name", ""),
        "target_type": "user",
        "target_id": user_id,
        "tenant_id": target_tenant_id,
        "details": {
            "from_role": primary_role,
            "to_role": target_role
        },
        "timestamp": now
    })
    
    new_token = create_access_token({
        "sub": user_id,
        "role": target_role,
        "tenant_id": target_tenant_id,
        "email": user.get("email", ""),
        "is_switched": True,
        "original_role": primary_role,
    })

    return {
        "message": "تم تبديل الدور بنجاح",
        "user_id": user_id,
        "active_role": target_role,
        "active_tenant_id": target_tenant_id,
        "full_name": user.get("full_name"),
        "email": user.get("email"),
        "access_token": new_token,
        "token_type": "bearer",
    }


@router.post("/users/{user_id}/add-role")
async def add_role_to_user(
    user_id: str,
    role: str,
    tenant_id: Optional[str] = None,
    scope_id: Optional[str] = None,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN]))
):
    """Add an additional role to a user"""
    now = datetime.now(timezone.utc).isoformat()
    
    user = await gd_find_one(db.session, "users", {"id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="المستخدم غير موجود")
    
    # Check if role already exists
    existing_roles = user.get("linked_roles", [])
    for existing in existing_roles:
        if (existing.get("role") == role and 
            existing.get("tenant_id") == tenant_id and
            existing.get("is_active")):
            raise HTTPException(status_code=400, detail="هذا الدور موجود مسبقاً للمستخدم")
    
    new_role = {
        "role": role,
        "tenant_id": tenant_id,
        "scope_id": scope_id,
        "is_active": True,
        "assigned_at": now,
        "assigned_by": current_user["id"],
    }
    
    await gd_update_one(db.session, "users", {"id": user_id},
        {
            "$push": {"linked_roles": new_role},
            "$set": {"updated_at": now}
        }
    )
    
    # Audit log
    await gd_insert(db.session, "audit_logs", {
        "id": str(uuid.uuid4()),
        "action": "role_assigned",
        "action_category": "identity",
        "actor_id": current_user["id"],
        "actor_name": current_user.get("full_name", ""),
        "target_type": "user",
        "target_id": user_id,
        "target_name": user.get("full_name"),
        "tenant_id": tenant_id,
        "details": {"role": role, "scope_id": scope_id},
        "timestamp": now
    })
    
    return {"message": "تم إضافة الدور بنجاح", "role": new_role}





# ============== PHASE 6: ROLE SWITCHING SYSTEM ==============

ROLE_SWITCH_ALLOWED = {
    UserRole.PLATFORM_ADMIN.value: [
        UserRole.SCHOOL_PRINCIPAL.value, UserRole.SCHOOL_ADMIN.value,
        UserRole.TEACHER.value, UserRole.STUDENT.value, UserRole.PARENT.value,
    ],
    UserRole.SCHOOL_PRINCIPAL.value: [
        UserRole.SCHOOL_ADMIN.value, UserRole.TEACHER.value,
    ],
    UserRole.SCHOOL_ADMIN.value: [
        UserRole.TEACHER.value,
    ],
}

@router.get("/role-switch/available-roles")
async def get_available_roles(
    current_user: dict = Depends(get_current_user),
):
    role = current_user.get("role", "")
    available = ROLE_SWITCH_ALLOWED.get(role, [])
    if not available:
        return {"current_role": role, "available_roles": [], "can_switch": False}

    schools = []
    if role == UserRole.PLATFORM_ADMIN.value:
        school_docs = await gd_find(db.session, "schools", {"status": "active"}, limit=100)
        schools = school_docs

    return {
        "current_role": role,
        "available_roles": available,
        "can_switch": True,
        "schools": schools,
    }

# SECURITY (audit H-2 / M-6): impersonation tokens are now bounded to a
# short server-controlled TTL and persisted in `impersonation_sessions`.
# The previous implementation trusted `original_user_id` from the switched
# JWT, which let any holder of a switched token mint a token back to *any*
# user_id of their choice. The restore handler now ignores that claim and
# resolves the original user from the persisted row keyed by the switched
# token's JTI.
IMPERSONATION_TOKEN_TTL_MINUTES = 15


@router.post("/role-switch/switch")
async def switch_role(
    request: Request,
    data: dict = Body(...),
    # Task #169 Step 7: cross-tenant role-switch is the canonical
    # privilege-escalation surface for platform admins; require fresh MFA.
    current_user: dict = Depends(require_recent_mfa()),
):
    target_role = data.get("target_role")
    target_school_id = data.get("school_id")
    reason = (data.get("reason") or "").strip()

    if not reason or len(reason) < 4:
        raise HTTPException(400, "يجب إدخال سبب واضح للتبديل (4 أحرف على الأقل)")
    if len(reason) > 500:
        raise HTTPException(400, "السبب طويل جداً (الحد الأقصى 500 حرف)")

    if current_user.get("is_impersonating"):
        # Disallow nested impersonation — keeps the audit trail linear and
        # makes restore unambiguous.
        raise HTTPException(409, "لا يمكنك التبديل وأنت بالفعل في وضع تبديل دور")

    current_role = current_user.get("role", "")
    allowed = ROLE_SWITCH_ALLOWED.get(current_role, [])

    if target_role not in allowed:
        raise HTTPException(403, "لا يمكنك التبديل إلى هذا الدور")

    if current_role == UserRole.PLATFORM_ADMIN.value:
        if target_school_id:
            school = await gd_find_one(db.session, "schools", {"id": target_school_id})
            if not school:
                raise HTTPException(404, "المدرسة غير موجودة")
        else:
            raise HTTPException(400, "يجب تحديد المدرسة للتبديل")
    else:
        target_school_id = current_user.get("tenant_id")
        if not target_school_id:
            raise HTTPException(400, "لم يتم تحديد المدرسة")

    user_id = current_user.get("id")

    # Mint the switched token with a hard 15-minute cap, regardless of the
    # platform-default access-token TTL.
    token_data = {
        "sub": user_id,
        "role": target_role,
        "original_role": current_role,
        # `original_user_id` is retained for backwards compatibility with
        # log readers, but the restore endpoint NO LONGER trusts it.
        "original_user_id": user_id,
        "tenant_id": target_school_id,
        "is_impersonating": True,
    }
    new_token = create_access_token(
        token_data,
        expires_delta=timedelta(minutes=IMPERSONATION_TOKEN_TTL_MINUTES),
    )
    new_jti = jwt.decode(new_token, JWT_SECRET, algorithms=[JWT_ALGORITHM]).get("jti")

    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=IMPERSONATION_TOKEN_TTL_MINUTES)

    from sqlalchemy import text as _sa_text
    from utils.trusted_proxy import extract_client_ip as _ip

    await db.session.execute(
        _sa_text(
            """
            INSERT INTO impersonation_sessions
              (id, jti, original_user_id, original_role, target_user_id,
               target_role, target_tenant_id, reason, started_at, expires_at,
               ip_address)
            VALUES
              (:id, :jti, :ouid, :orole, :tuid, :trole, :ttid, :reason,
               :started_at, :expires_at, :ip)
            """
        ),
        {
            "id": str(uuid.uuid4()),
            "jti": new_jti,
            "ouid": user_id,
            "orole": current_role,
            "tuid": user_id,  # platform/principal switches into their own user
            "trole": target_role,
            "ttid": target_school_id,
            "reason": reason,
            "started_at": now,
            "expires_at": expires_at,
            "ip": _ip(request),
        },
    )

    await gd_insert(db.session, "audit_logs", {
        "id": str(uuid.uuid4()),
        "action": "role_switch",
        "severity": "high",
        "action_by": user_id,
        "performed_by": user_id,
        "actor_role": current_role,
        "original_role": current_role,
        "target_role": target_role,
        "target_school_id": target_school_id,
        "tenant_id": target_school_id,
        "reason": reason,
        "ip_address": _ip(request),
        "timestamp": now.isoformat(),
    })

    try:
        from services.audit_sink import emit_audit
        emit_audit({
            "action": "role_switch.start",
            "severity": "high",
            "original_user_id": user_id,
            "original_role": current_role,
            "target_role": target_role,
            "target_tenant_id": target_school_id,
            "jti": new_jti,
            "reason": reason,
            "expires_at": expires_at.isoformat(),
            "ip_address": _ip(request),
        })
    except Exception as _e:
        logger.debug(f"audit_sink emit failed (role_switch.start): {_e}")

    return {
        "token": new_token,
        "role": target_role,
        "school_id": target_school_id,
        "is_impersonating": True,
        "original_role": current_role,
    }

@router.post("/role-switch/restore")
async def restore_role(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    # Task #169 Step 7: returning to the original role is symmetric to
    # role-switch in audit terms; gate it the same way.
    current_user: dict = Depends(require_recent_mfa()),
):
    """Restore the original role for an impersonating session.

    SECURITY (audit H-2): the original-user identity is read from the
    server-side `impersonation_sessions` row keyed by the *current
    switched token's JTI*. We deliberately ignore `original_user_id`
    from the JWT body — it's an attacker-controllable claim once the
    switched token is in their possession.
    """
    if not current_user.get("is_impersonating"):
        return {"message": "أنت بالفعل في دورك الأصلي", "restored": False}

    # Re-decode the bearer to lift the JTI out — `get_current_user`
    # already validated the signature, exp, revocation and account state.
    try:
        payload = jwt.decode(
            credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM]
        )
    except jwt.PyJWTError:
        raise HTTPException(401, "رمز غير صالح")

    jti = payload.get("jti")
    if not jti:
        raise HTTPException(401, "رمز التبديل غير صالح")

    from sqlalchemy import text as _sa_text
    from utils.trusted_proxy import extract_client_ip as _ip

    row = (
        await db.session.execute(
            _sa_text(
                """
                SELECT original_user_id, original_role, target_role,
                       target_tenant_id, ended_at, expires_at
                FROM impersonation_sessions
                WHERE jti = :jti
                """
            ),
            {"jti": jti},
        )
    ).mappings().first()

    if not row:
        # No server-side row → the token's claim is not honoured.
        raise HTTPException(401, "جلسة التبديل غير موجودة على الخادم")
    if row["ended_at"] is not None:
        raise HTTPException(401, "جلسة التبديل منتهية")

    original_user_id = row["original_user_id"]
    original_role_db = row["original_role"]

    user = await gd_find_one(db.session, "users", {"id": original_user_id})
    if not user:
        raise HTTPException(404, "المستخدم الأصلي غير موجود")

    uid = user.get("id") or original_user_id
    token_data = {
        "sub": uid,
        "role": user.get("role", original_role_db),
        "tenant_id": user.get("tenant_id"),
    }
    new_token = create_access_token(token_data)

    now = datetime.now(timezone.utc)
    await db.session.execute(
        _sa_text(
            """
            UPDATE impersonation_sessions
            SET ended_at = :ended_at, end_reason = :reason
            WHERE jti = :jti AND ended_at IS NULL
            """
        ),
        {"ended_at": now, "reason": "restored", "jti": jti},
    )

    try:
        from services.audit_sink import emit_audit
        emit_audit({
            "action": "role_switch.restore",
            "severity": "high",
            "original_user_id": original_user_id,
            "jti": jti,
            "ip_address": _ip(request),
        })
    except Exception as _e:
        logger.debug(f"audit_sink emit failed (role_switch.restore): {_e}")

    return {
        "token": new_token,
        "role": user.get("role", original_role_db),
        "school_id": user.get("tenant_id"),
        "is_impersonating": False,
        "restored": True,
    }


class ProfileCompletionUpdate(BaseModel):
    phone: Optional[str] = None
    address: Optional[str] = None
    emergency_contact: Optional[str] = None
    emergency_phone: Optional[str] = None
    date_of_birth: Optional[str] = None
    gender: Optional[str] = None
    nationality: Optional[str] = None
    bio: Optional[str] = None
    profile_picture: Optional[str] = None


@router.get("/auth/profile-completion")
async def get_profile_completion(
    current_user: dict = Depends(get_current_user)
):
    """Get profile completion percentage and missing fields"""
    profile_fields = {
        "full_name": "الاسم الكامل",
        "email": "البريد الإلكتروني",
        "phone": "رقم الهاتف",
        "gender": "الجنس",
        "date_of_birth": "تاريخ الميلاد",
        "address": "العنوان",
        "nationality": "الجنسية",
        "emergency_contact": "جهة اتصال الطوارئ",
        "emergency_phone": "هاتف الطوارئ"
    }

    completed = []
    missing = []
    for field, label in profile_fields.items():
        if current_user.get(field):
            completed.append({"field": field, "label": label})
        else:
            missing.append({"field": field, "label": label})

    percentage = round(len(completed) / len(profile_fields) * 100) if profile_fields else 0

    return {
        "percentage": percentage,
        "completed_fields": completed,
        "missing_fields": missing,
        "total_fields": len(profile_fields),
        "completed_count": len(completed)
    }


@router.put("/auth/complete-profile")
async def complete_profile(
    data: ProfileCompletionUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Update profile fields for completion"""
    updates = {"updated_at": datetime.now(timezone.utc).isoformat()}

    for field in ["phone", "address", "emergency_contact", "emergency_phone",
                  "date_of_birth", "gender", "nationality", "bio", "profile_picture"]:
        value = getattr(data, field, None)
        if value is not None:
            updates[field] = value

    await gd_update_one(db.session, "users", {"id": current_user["id"]}, updates)

    return {"message": "تم تحديث الملف الشخصي بنجاح"}


# NOTE: /auth/sessions and /auth/sessions/revoke-all stubs were removed.
# The real session-management endpoints live under /settings/sessions in
# routes/settings_routes.py and use the user_sessions table populated on login.

@router.get("/auth/login-history")
async def get_login_history(
    limit: int = 20,
    current_user: dict = Depends(get_current_user)
):
    """Get login history for the current user"""
    logs = await gd_find(db.session, "audit_logs", {"actor_id": current_user["id"], "action": {"$in": ["login", "login_success", "password_changed"]}}, order_by="timestamp", desc_order=True, limit=limit)

    return {"history": logs, "total": len(logs)}

