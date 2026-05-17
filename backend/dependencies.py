"""
NASSAQ Shared Dependencies
Central module exporting db, auth helpers, models, and engine instances.
All route modules should import from here instead of server.py.
"""
from fastapi import Depends, HTTPException, Header, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv
from pathlib import Path
from typing import List, Optional
from datetime import datetime, timezone, timedelta
from enum import Enum
from pydantic import BaseModel, Field, ConfigDict, EmailStr
import os
import jwt
import bcrypt
import uuid
import logging
import qrcode
import io
import base64

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# B-16: do not call logging.basicConfig here — server.py owns the structured
# JSON formatter. Calling basicConfig before server.py imports this module
# briefly installs the plain-text format and competes with the JSON handler.
logger = logging.getLogger("nassaq")

from repositories import Repos
db = Repos()

JWT_SECRET = os.environ.get('JWT_SECRET_KEY', '')
if not JWT_SECRET:
    logger.critical("JWT_SECRET_KEY environment variable is not set — refusing to start with an ephemeral secret")
    raise SystemExit("FATAL: JWT_SECRET_KEY must be set. Aborting.")
JWT_ALGORITHM = os.environ.get('JWT_ALGORITHM', 'HS256')
ACCESS_TOKEN_EXPIRE = int(os.environ.get('ACCESS_TOKEN_EXPIRE_MINUTES', 60))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.environ.get('REFRESH_TOKEN_EXPIRE_DAYS', 30))
REFRESH_TOKEN_SHORT_HOURS = int(os.environ.get('REFRESH_TOKEN_SHORT_HOURS', 2))

security = HTTPBearer()

from engines.audit_engine import AuditLogEngine, AuditAction, AuditSeverity
from engines.session_engine import TeacherSessionEngine
from engines.hakim_ai_engine import HakimAIEngine
from engines.reporting_engine import ReportingEngine, REPORT_TYPES
from engines.export_engine import ExportEngine
from engines.smart_scheduling_engine import (
    SmartSchedulingEngine,
    TimetableRunStatus,
    TimetableStatus,
    ConflictType,
    ConflictSeverity,
    PreValidationResult,
    GenerationResult
)

from db import get_pg_session, get_db, async_session_factory
from sqlalchemy.ext.asyncio import AsyncSession
from engines.sql_utils import gd_find, gd_find_one, gd_insert, gd_insert_many, gd_update_one, gd_update_many, gd_count, gd_delete_one, gd_delete_many, gd_distinct, gd_upsert, _gd_aggregate

audit_engine = AuditLogEngine(db)
smart_scheduling_engine = SmartSchedulingEngine(db)
hakim_engine = HakimAIEngine(db)
reporting_engine = ReportingEngine(db, hakim_engine=hakim_engine)
export_engine = ExportEngine(db, reporting_engine=reporting_engine)
session_engine = TeacherSessionEngine(db)


def generate_secure_password(length=10):
    import secrets
    import string
    alphabet = string.ascii_letters + string.digits + "!@#$%"
    return ''.join(secrets.choice(alphabet) for _ in range(length))


def generate_student_qr_code(student_id: str, student_name: str, student_number: str) -> str:
    qr_data = f"NASSAQ|STUDENT|{student_id}|{student_number}|{student_name}"
    qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=10, border=4)
    qr.add_data(qr_data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)
    return base64.b64encode(buffer.read()).decode('utf-8')


class UserRole(str, Enum):
    PLATFORM_ADMIN = "platform_admin"
    PLATFORM_SUB_ADMIN = "platform_sub_admin"
    PLATFORM_OPERATIONS_MANAGER = "platform_operations_manager"
    PLATFORM_TECHNICAL_ADMIN = "platform_technical_admin"
    PLATFORM_SUPPORT_SPECIALIST = "platform_support_specialist"
    PLATFORM_DATA_ANALYST = "platform_data_analyst"
    PLATFORM_SECURITY_OFFICER = "platform_security_officer"
    PLATFORM_SALES = "platform_sales"
    PLATFORM_MARKETING = "platform_marketing"
    PLATFORM_QUALITY = "platform_quality"
    MINISTRY_REP = "ministry_rep"
    SCHOOL_PRINCIPAL = "school_principal"
    SCHOOL_ADMIN = "school_admin"
    SCHOOL_SUB_ADMIN = "school_sub_admin"
    TEACHER = "teacher"
    INDEPENDENT_TEACHER = "independent_teacher"
    STUDENT = "student"
    PARENT = "parent"
    DRIVER = "driver"
    GATEKEEPER = "gatekeeper"
    TESTING_ACCOUNT = "testing_account"


STUDENT_LOGIN_DISABLED = True
STUDENT_LOGIN_DISABLED_MESSAGE_AR = (
    "تسجيل دخول الطالب غير متاح حالياً. سيتم تفعيله بعد إعادة بناء حساب الطالب."
)
STUDENT_LOGIN_DISABLED_CODE = "STUDENT_LOGIN_DISABLED"


def _user_role_value(user) -> str:
    if not isinstance(user, dict):
        return ""
    role = user.get("role")
    if hasattr(role, "value"):
        role = role.value
    return (role or "").lower()


def assert_student_login_enabled(user) -> None:
    """Reject login/refresh/token-issuance for student-role accounts while
    the student portal is being rebuilt. Surfaces a structured 403 envelope
    so the FE can render the safe Arabic message verbatim without falling
    back to the generic credentials error."""
    if not STUDENT_LOGIN_DISABLED:
        return
    if _user_role_value(user) == UserRole.STUDENT.value:
        raise HTTPException(
            status_code=403,
            detail={
                "code": STUDENT_LOGIN_DISABLED_CODE,
                "message": "Student login is temporarily unavailable",
                "message_ar": STUDENT_LOGIN_DISABLED_MESSAGE_AR,
            },
        )


class SchoolStatus(str, Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    PENDING = "pending"
    SETUP = "setup"


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))
    except (ValueError, TypeError):
        return False

def create_access_token(
    data: dict,
    expires_delta: timedelta = None,
    mfa_recent_at: Optional[int] = None,
    mfa_kind: Optional[str] = None,
) -> str:
    """Mint a ``type=access`` JWT.

    Task #169 Step 7: ``mfa_recent_at`` is the UTC unix-second timestamp of
    the user's most recent successful MFA verification; ``mfa_kind`` records
    which factor was used. Both are embedded so the ``require_recent_mfa``
    dependency can decide whether a sensitive route call is fresh enough
    without re-querying the DB. Refresh PRESERVES (does not advance) these
    claims; the only path that ADVANCES ``mfa_recent_at`` is a successful
    ``/auth/mfa/verify`` or ``/auth/mfa/stepup/verify`` mint.
    """
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=ACCESS_TOKEN_EXPIRE)
    # Task #342: include `iat` so the password-change boundary check in
    # get_current_user() and decode_token_for_ws() can compare issuance time
    # against last_password_change, matching what refresh tokens already do.
    to_encode.update({"exp": expire, "iat": now, "type": "access", "jti": str(uuid.uuid4())})
    if mfa_recent_at is not None:
        to_encode["mfa_recent_at"] = int(mfa_recent_at)
    if mfa_kind:
        to_encode["mfa_kind"] = mfa_kind
    return jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)


MFA_CHALLENGE_EXPIRE_MINUTES = int(os.environ.get('MFA_CHALLENGE_EXPIRE_MINUTES', 10))


def create_mfa_challenge_token(user_id: str, role: str, tenant_id: Optional[str] = None) -> tuple[str, str, datetime]:
    """Mint a short-lived ``type=mfa_challenge`` JWT for the post-password
    pre-second-factor state. Returned tuple is ``(token, jti, expires_at)``.

    These tokens MUST NOT be accepted by ``get_current_user`` — they only
    authorise calls to ``/auth/mfa/*`` verify endpoints. Enforcement is in
    ``get_current_user``: only ``type == "access"`` is accepted as a normal
    bearer token. Task #169.
    """
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=MFA_CHALLENGE_EXPIRE_MINUTES)
    jti = str(uuid.uuid4())
    payload = {
        "sub": user_id,
        "role": role,
        "type": "mfa_challenge",
        "jti": jti,
        "iat": now,
        "exp": expires_at,
    }
    if tenant_id:
        payload["tenant_id"] = tenant_id
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return token, jti, expires_at


def create_refresh_token(
    data: dict,
    remember_me: bool = False,
    linked_access_jti: Optional[str] = None,
    family_id: Optional[str] = None,
    mfa_recent_at: Optional[int] = None,
    mfa_kind: Optional[str] = None,
) -> str:
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    if remember_me:
        expire = now + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    else:
        expire = now + timedelta(hours=REFRESH_TOKEN_SHORT_HOURS)
    if mfa_recent_at is not None:
        to_encode["mfa_recent_at"] = int(mfa_recent_at)
    if mfa_kind:
        to_encode["mfa_kind"] = mfa_kind
    to_encode.update({
        "exp": expire,
        # Explicitly include iat so the refresh endpoint can compare issuance
        # time against last_password_change and reject stale tokens after a
        # password change or reset.
        "iat": now,
        "type": "refresh",
        "rm": remember_me,
        "jti": str(uuid.uuid4()),
        # Phase 3 (audit Open Question 5): every refresh token belongs to a
        # *family*. On legitimate rotation the family id is preserved across
        # the new token. If a previously-rotated jti is ever replayed, the
        # `/auth/refresh` handler revokes the entire family in one shot —
        # killing the attacker's tokens AND the legitimate user's, forcing
        # re-login. This is the standard stolen-refresh-token pattern.
        "fid": family_id or str(uuid.uuid4()),
    })
    if linked_access_jti:
        to_encode["acc_jti"] = linked_access_jti
    return jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        # Task #169: only true access tokens are accepted as bearer tokens.
        # Refresh tokens and mfa_challenge tokens both have distinct ``type``
        # claims and must NOT be usable to call protected APIs. Tokens
        # without an explicit ``type`` (legacy / pre-Phase 3) are also
        # rejected because every issuance path now sets ``type=access``.
        if payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="Invalid token type")
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")

        jti = payload.get("jti")
        if jti:
            try:
                from engines.sql_utils import gd_find_one as _gd_find_one
                revoked = await _gd_find_one(db.session, "revoked_tokens", {"jti": jti})
                if revoked:
                    raise HTTPException(status_code=401, detail="Token has been revoked")
            except HTTPException:
                raise
            except Exception:
                pass

        user = await gd_find_one(db.session, "users", {"id": user_id})

        if not user:
            raise HTTPException(status_code=401, detail="User not found")

        if not user.get("is_active", True):
            raise HTTPException(status_code=401, detail="Account is deactivated")

        if user.get("is_locked", False):
            raise HTTPException(status_code=401, detail="Account is locked")

        # Temporary platform-wide block: invalidate any already-issued
        # access token whose subject is a student. Returned as 401 (rather
        # than the 403 envelope used by the login/refresh gates) so the
        # FE axios interceptor treats it like any other expired session
        # and bounces the browser to /login instead of attempting an MFA
        # step-up replay — there is no way to satisfy this gate from the
        # browser while the block is on.
        if STUDENT_LOGIN_DISABLED and _user_role_value(user) == UserRole.STUDENT.value:
            raise HTTPException(
                status_code=401,
                detail=STUDENT_LOGIN_DISABLED_MESSAGE_AR,
            )

        # IT §6.8 — defense-in-depth: reject access tokens for IT users whose
        # workspace has been archived or is pending erasure. The lifecycle
        # routes bump last_password_change (and is_active for erasure) to
        # cut existing sessions; this gate catches the narrow window where
        # an access token was issued within the same second as the archival.
        _u_role = (user.get("role") or "").lower()
        _u_acct = (
            (user.get("account_type") or "")
            or ((user.get("data") or {}).get("account_type") or "")
        ).lower()
        if _u_role == "independent_teacher" or _u_acct == "independent_teacher":
            _it_ws_id = f"itw_{user_id}"
            try:
                _it_ws = await gd_find_one(db.session, "schools", {"id": _it_ws_id})
                if _it_ws and (
                    (_it_ws.get("status") or "").lower() == "archived"
                    or _it_ws.get("pending_hard_delete")
                ):
                    raise HTTPException(
                        status_code=401,
                        detail="تم أرشفة مساحة العمل. يرجى مراجعة بريدك الإلكتروني.",
                    )
            except HTTPException:
                raise
            except Exception as _it_err:
                # Fail closed: an unexpected error querying workspace state
                # for an IT user must not allow an archived workspace to slip
                # through. Log the root cause at warning level and reject.
                logger.warning(
                    "get_current_user: IT workspace archived check failed, "
                    "rejecting token for safety: %s",
                    _it_err,
                )
                raise HTTPException(
                    status_code=401,
                    detail="تعذّر التحقق من حالة مساحة العمل. يرجى تسجيل الدخول مجدداً.",
                )

        # Task #342: reject access tokens issued before the last password change
        # or reset. This closes the session-invalidation gap where an attacker
        # retains a stolen access token after the victim changes their password.
        # Mirrors the same check already enforced in the refresh-token handler.
        last_pw_change = user.get("last_password_change")
        token_iat = payload.get("iat")
        if last_pw_change:
            if token_iat is None:
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
            except Exception as _lpc_err:
                logger.debug(f"get_current_user: last_password_change parse failed: {_lpc_err}")

        user.pop("_id", None)
        if "id" not in user or not user.get("id"):
            user["id"] = user_id

        # E-02/E-03 + architect-review fix: scope fallback identifier lookups
        # by school_id == user.tenant_id whenever both are present, to prevent
        # cross-tenant resolution via shared email/phone/national_id. Also persist
        # the resolved id back to the users row so we never re-query on subsequent
        # requests (eliminates per-request query amplification).
        _tenant = user.get("tenant_id")

        async def _scoped_lookup(table: str, by_field: str, value):
            """Look up a row by `by_field=value`, constrained by school_id when known."""
            if not value:
                return None
            q = {by_field: value}
            if _tenant:
                q["school_id"] = _tenant
            row = await gd_find_one(db.session, table, q)
            # Last-resort: if tenant scoping returned nothing AND the user has no tenant
            # (platform-level account or pre-link), allow unscoped lookup.
            if not row and not _tenant:
                row = await gd_find_one(db.session, table, {by_field: value})
            return row

        async def _persist_link(field: str, value: str):
            try:
                from engines.sql_utils import gd_update_one as _gd_update_one
                await _gd_update_one(db.session, "users", {"id": user["id"]}, {field: value})
            except Exception:
                pass  # non-fatal; will retry on next request

        if user.get("role") == UserRole.TEACHER.value and not user.get("teacher_id"):
            # Prefer typed FK (teachers.user_id) — already deterministic, no scope needed.
            teacher = await gd_find_one(db.session, "teachers", {"user_id": user.get("id")})
            if not teacher:
                teacher = await _scoped_lookup("teachers", "email", user.get("email"))
            if not teacher:
                teacher = await _scoped_lookup("teachers", "phone", user.get("phone"))
            if not teacher:
                teacher = await _scoped_lookup("teachers", "national_id", user.get("national_id"))
            if teacher:
                user["teacher_id"] = teacher.get("id")
                await _persist_link("teacher_id", teacher.get("id"))

        if user.get("role") == UserRole.STUDENT.value and not user.get("student_id"):
            # students table has no user_id column → use email/phone/national_id, tenant-scoped.
            student = await _scoped_lookup("students", "email", user.get("email"))
            if not student:
                student = await _scoped_lookup("students", "phone", user.get("phone"))
            if not student:
                student = await _scoped_lookup("students", "national_id", user.get("national_id"))
            if student:
                user["student_id"] = student.get("id")
                await _persist_link("student_id", student.get("id"))

        if user.get("role") == UserRole.PARENT.value and not user.get("parent_id"):
            # Use tenant-scoped lookups (same _scoped_lookup helper as teachers/students)
            # to prevent a shared phone/email/national_id from binding a parent account
            # to the wrong family's `parents` row across workspace boundaries.
            parent = await _scoped_lookup("parents", "email", user.get("email"))
            if not parent:
                parent = await _scoped_lookup("parents", "phone", user.get("phone"))
            if not parent:
                parent = await _scoped_lookup("parents", "national_id", user.get("national_id"))
            if parent:
                user["parent_id"] = parent.get("id")
                await _persist_link("parent_id", parent.get("id"))
            else:
                # Fall back to guardian_links, scoped by tenant_id when available.
                link_q: dict = {"parent_ref": user.get("id"), "is_active": True}
                if _tenant:
                    link_q["tenant_id"] = _tenant
                link = await gd_find_one(db.session, "guardian_links", link_q)
                if link:
                    resolved = link.get("parent_id") or link.get("parent_ref")
                    user["parent_id"] = resolved
                    if resolved:
                        await _persist_link("parent_id", resolved)

        if payload.get("is_impersonating"):
            user["is_impersonating"] = True
            user["original_role"] = payload.get("original_role")
            user["original_user_id"] = payload.get("original_user_id")
            if payload.get("role"):
                user["role"] = payload["role"]
            if payload.get("tenant_id"):
                user["tenant_id"] = payload["tenant_id"]

        if payload.get("is_switched"):
            user["is_switched"] = True
            user["original_role"] = payload.get("original_role")
            if payload.get("role"):
                user["role"] = payload["role"]
            if payload.get("tenant_id"):
                user["tenant_id"] = payload["tenant_id"]

        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


def require_roles(allowed_roles: List[UserRole]):
    async def role_checker(current_user: dict = Depends(get_current_user)):
        if current_user["role"] not in [r.value for r in allowed_roles]:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return current_user
    return role_checker


# ---------------------------------------------------------------------------
# Task #169 Step 7 — server-side step-up dependency
# ---------------------------------------------------------------------------
#
# ``require_recent_mfa(max_age_seconds=300)`` is the ONLY authority for
# step-up enforcement. It returns a FastAPI dependency that:
#
#   * Fast-paths users whose role is not subject to MFA policy (students,
#     drivers, gatekeepers, etc.) — they pass through unchanged.
#   * Reads ``mfa_recent_at`` directly from the bearer JWT (the token
#     signature was already verified by ``get_current_user`` upstream).
#     Missing or older-than-``max_age_seconds`` → HTTP 401 with structured
#     body {detail: {code: "MFA_STEPUP_REQUIRED", ...}}. The Step-9 Axios
#     interceptor opens the step-up modal on this code.
#   * For Tier-A users only, additionally enforces:
#       - ``mfa_must_restore_factor`` (set when a recovery code is consumed)
#         → 401 ``MFA_RESTORE_REQUIRED`` until the user re-enrols a normal
#         factor (Passkey or TOTP).
#       - At-least-one active WebAuthn credential
#         → 401 ``MFA_PASSKEY_REQUIRED`` until the user adds one.
#
# Refresh deliberately PRESERVES but does NOT advance ``mfa_recent_at``;
# the only paths that mint a fresh timestamp are ``/auth/mfa/verify`` and
# ``/auth/mfa/stepup/verify``.

_STEPUP_CHALLENGE_ENDPOINT = "/api/auth/mfa/stepup/start"


def _stepup_required_detail(
    code: str,
    message_ar: str,
    max_age_seconds: int,
) -> dict:
    return {
        "code": code,
        "message": message_ar,
        "challenge_endpoint": _STEPUP_CHALLENGE_ENDPOINT,
        "max_age_seconds": max_age_seconds,
    }


def require_recent_mfa(max_age_seconds: int = 300):
    """Return a FastAPI dependency that enforces a fresh MFA proof.

    Stack alongside ``require_roles`` (or use as the sole dep when the
    route doesn't already require a specific role) — both reuse the same
    upstream ``get_current_user`` so FastAPI dedupes the call.
    """
    async def _dep(
        credentials: HTTPAuthorizationCredentials = Depends(security),
        current_user: dict = Depends(get_current_user),
    ) -> dict:
        # Lazy import to avoid module-load cycles.
        from services import mfa_policy as _mfa_policy

        # Roles outside Tier A/B/C have no MFA policy at all — the route
        # guard collapses to "authenticated" for them. Sensitive routes
        # like change-password are still always called by an authed user;
        # this branch only fires for student/driver/gatekeeper accounts.
        if not _mfa_policy.is_required(current_user):
            return current_user

        # Re-decode the bearer to read the post-MFA claims. Signature was
        # validated upstream by get_current_user; we only need the payload.
        try:
            payload = jwt.decode(
                credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM]
            )
        except jwt.PyJWTError:
            raise HTTPException(
                status_code=401,
                detail=_stepup_required_detail(
                    "MFA_STEPUP_REQUIRED",
                    "يلزم التحقق المسبق عبر العامل الثاني للمتابعة",
                    max_age_seconds,
                ),
            )

        # Tier-A-only hard blocks. These ALWAYS run before the freshness
        # check so a Tier-A user with a stale token still sees the most
        # specific reason (passkey/restore) rather than a generic step-up
        # prompt that they cannot satisfy.
        if _mfa_policy.is_tier_a(current_user):
            if current_user.get("mfa_must_restore_factor"):
                raise HTTPException(
                    status_code=401,
                    detail=_stepup_required_detail(
                        "MFA_RESTORE_REQUIRED",
                        "تم استخدام رمز استرداد. يجب إعادة تسجيل عامل تحقق (مفتاح أمان أو تطبيق مصادقة) قبل المتابعة",
                        max_age_seconds,
                    ),
                )
            try:
                from engines.sql_utils import gd_find as _gd_find
                rows = await _gd_find(
                    db.session,
                    "mfa_factors",
                    {"user_id": current_user["id"], "kind": "webauthn", "is_active": True},
                ) or []
                if not _mfa_policy.tier_a_passkey_satisfied(rows):
                    raise HTTPException(
                        status_code=401,
                        detail=_stepup_required_detail(
                            "MFA_PASSKEY_REQUIRED",
                            "هذا الإجراء يتطلب تسجيل مفتاح أمان (Passkey) أولاً",
                            max_age_seconds,
                        ),
                    )
            except HTTPException:
                raise
            except Exception as exc:
                logger.warning(f"require_recent_mfa: tier-A passkey check failed: {exc}")

        mfa_recent_at = payload.get("mfa_recent_at")
        now_ts = int(datetime.now(timezone.utc).timestamp())
        if mfa_recent_at is None or (now_ts - int(mfa_recent_at)) > max_age_seconds:
            raise HTTPException(
                status_code=401,
                detail=_stepup_required_detail(
                    "MFA_STEPUP_REQUIRED",
                    "يلزم التحقق المسبق عبر العامل الثاني للمتابعة",
                    max_age_seconds,
                ),
            )

        return current_user

    return _dep


# ---------------------------------------------------------------------------
# Task #201 — IT §5.7 MFA step-up backfill
# ---------------------------------------------------------------------------
#
# The frontend axios interceptor (frontend/src/contexts/AuthContext.js)
# replays a request after step-up only when the canonical step-up envelope
# (``code = MFA_STEPUP_REQUIRED`` / ``MFA_PASSKEY_REQUIRED`` /
# ``MFA_RESTORE_REQUIRED``) arrives as **HTTP 403**. ``require_recent_mfa``
# itself emits the same payload but with status 401, which the interceptor
# does NOT replay (401 is treated as a hard logout). The two helpers below
# wrap ``require_recent_mfa`` to convert 401 → 403 verbatim, mirroring the
# pattern Task #199 introduced inline in
# ``routes/independent_teacher_invite_parent_routes.py``.
#
#   * ``require_recent_mfa_403`` — unconditional wrapper. Use on routes
#     that are already gated to a single role (e.g. an IT-only router).
#   * ``require_recent_mfa_403_if_independent_teacher`` — IT-conditional.
#     Non-IT callers (principal, school admin, regular teacher, parent,
#     platform admin) pass through unchanged so their existing MFA posture
#     is not regressed. Use on shared routes that an IT user happens to
#     reach (profile updates, generic exports, student/parent CRUD).


def require_recent_mfa_403(max_age_seconds: int = 300):
    """Return a FastAPI dependency that mirrors ``require_recent_mfa`` but
    emits the canonical step-up envelope as **HTTP 403** instead of 401.
    """
    base = require_recent_mfa(max_age_seconds=max_age_seconds)

    async def _dep(
        credentials: HTTPAuthorizationCredentials = Depends(security),
        current_user: dict = Depends(get_current_user),
    ) -> dict:
        try:
            return await base(
                credentials=credentials, current_user=current_user,
            )
        except HTTPException as exc:
            if (
                exc.status_code == 401
                and isinstance(exc.detail, dict)
                and exc.detail.get("code") in {
                    "MFA_STEPUP_REQUIRED",
                    "MFA_PASSKEY_REQUIRED",
                    "MFA_RESTORE_REQUIRED",
                }
            ):
                raise HTTPException(
                    status_code=403, detail=exc.detail,
                ) from exc
            raise

    return _dep


def require_recent_mfa_403_if_independent_teacher(max_age_seconds: int = 300):
    """Return a FastAPI dependency that enforces ``require_recent_mfa_403``
    **only** when the caller is an Independent-Teacher account. Non-IT
    callers pass through untouched so their existing MFA posture, success
    codes, and 4xx outcomes on the underlying route are unchanged.
    """
    base_403 = require_recent_mfa_403(max_age_seconds=max_age_seconds)

    async def _dep(
        credentials: HTTPAuthorizationCredentials = Depends(security),
        current_user: dict = Depends(get_current_user),
    ) -> dict:
        # Lazy import to avoid a module-load cycle with auth_scope, which
        # itself imports symbols from dependencies.
        from auth_scope import is_independent_teacher

        if not is_independent_teacher(current_user):
            return current_user
        return await base_403(
            credentials=credentials, current_user=current_user,
        )

    return _dep
