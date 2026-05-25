"""
Independent-Teacher workspace bootstrap (Task #183 — Phase 1).

Single endpoint:
  POST /independent-teacher/bootstrap

Atomically materialises the IT account's synthetic workspace:

  * `schools`            — synthetic row id `itw_{user_id}` (canonical
                            convention from `auth_scope.independent_workspace_id`).
  * `school_settings`    — schedule baseline (working_days, periods_per_day).
  * `academic_years`     — single active year (Hijri-aware label, dates
                            optional — wizard collects the year window).
  * `academic_terms`     — single active term linked to the year.
  * `teachers`           — IT's teacher row (user_id = caller).
  * `users.tenant_id`    — set to the workspace id (this is the SOLE
                            place the IT lifecycle writes this column).
  * `classes` (optional) — only when wizard step 3 was filled. Counts
                            against `quotas.independent_teacher.MAX_CLASSES`.

All-or-nothing: any failure inside the transaction triggers a rollback
and a 500 with a safe Arabic message — no partial workspace ever leaks
through.

Idempotent: replays after a successful materialisation return the
existing workspace summary instead of inserting duplicates / erroring.

Issues a fresh access+refresh token pair on success so the caller's
subsequent requests carry the freshly-set `tenant_id`. The
`require_workspace_materialised` global gate reads `tenant_id` from
the bearer JWT, so without rotation the caller would still see 409s
from non-allow-listed routes.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import List, Optional

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel, Field, field_validator

from auth_scope import (
    is_independent_teacher,
    independent_workspace_id,
)
from dependencies import (
    db,
    get_current_user,
    create_access_token,
    create_refresh_token,
    require_recent_mfa,
    security,
    JWT_SECRET,
    JWT_ALGORITHM,
    UserRole,
)
from engines.audit_engine import AuditLogEngine
from engines.name_validation import is_generic_name
from engines.sql_utils import gd_count, gd_find_one, gd_insert, gd_update_one
from quotas.independent_teacher import MAX_CLASSES
from repositories import Repos
from shared_models import UserResponse

logger = logging.getLogger("nassaq.it_bootstrap")

router = APIRouter()


# -- Safe Arabic copy ------------------------------------------------------

_MSG_INTERNAL = (
    "تعذّر إنشاء مساحتك التعليمية. حاول مرة أخرى لاحقًا."
)
_MSG_NOT_INDEPENDENT_TEACHER = (
    "هذه الميزة متاحة لحسابات المعلم المستقل فقط."
)
_MSG_MFA_ENROLLMENT_REQUIRED = (
    "يلزم إعداد عامل تحقق ثانوي قبل إنشاء مساحتك."
)
_MSG_MFA_STEPUP_REQUIRED = (
    "يلزم التحقق المسبق عبر العامل الثاني قبل إنشاء مساحتك."
)
_MSG_QUOTA_CLASSES = (
    f"بلغت الحد الأقصى لعدد الفصول في حسابك المستقل ({MAX_CLASSES})."
)
_MSG_NAME_REQUIRED = "اسم المساحة باللغة العربية مطلوب."
_MSG_PERIODS_INVALID = "عدد الحصص اليومي يجب أن يكون بين ١ و١٢."
_MSG_WORKING_DAYS_INVALID = "اختر يومًا واحدًا على الأقل ضمن أيام العمل."

_MFA_STEPUP_MAX_AGE_SECONDS = 300  # mirrors require_recent_mfa default

_VALID_WEEKDAYS = {"sun", "mon", "tue", "wed", "thu", "fri", "sat"}


# -- Request / response models --------------------------------------------

class WorkspaceClassDraft(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    grade_level: Optional[str] = Field(default=None, max_length=120)
    subject: Optional[str] = Field(default=None, max_length=120)
    capacity: int = Field(default=30, ge=1, le=200)


class WorkspaceBootstrapRequest(BaseModel):
    workspace_name_ar: str = Field(..., min_length=1, max_length=200)
    workspace_name_en: Optional[str] = Field(default=None, max_length=200)
    # Accepts either a short URL or a base64 data:image/* payload (the
    # onboarding wizard's ImageCropModal hands back the latter). Cap matches
    # /users/me/avatar (2 MB raw, ~2.7 MB base64) so the workspace logo and
    # user avatar share the same upload contract.
    avatar_url: Optional[str] = Field(default=None, max_length=3 * 1024 * 1024)

    academic_year_label: str = Field(..., min_length=1, max_length=64)
    academic_year_start: Optional[str] = None  # ISO yyyy-mm-dd
    academic_year_end: Optional[str] = None
    term_label: Optional[str] = Field(default=None, max_length=64)

    working_days: List[str] = Field(default_factory=list)
    periods_per_day: int = Field(default=7, ge=1, le=12)

    first_class: Optional[WorkspaceClassDraft] = None

    @field_validator("workspace_name_ar")
    @classmethod
    def _strip_name(cls, v: str) -> str:
        v = (v or "").strip()
        if not v:
            raise ValueError(_MSG_NAME_REQUIRED)
        return v

    @field_validator("working_days")
    @classmethod
    def _validate_days(cls, v: List[str]) -> List[str]:
        cleaned = [d.strip().lower() for d in (v or []) if d and isinstance(d, str)]
        bad = [d for d in cleaned if d not in _VALID_WEEKDAYS]
        if bad:
            raise ValueError(_MSG_WORKING_DAYS_INVALID)
        # Default to Sun–Thu (Saudi school week) if caller sent nothing.
        return cleaned or ["sun", "mon", "tue", "wed", "thu"]


# -- Helpers --------------------------------------------------------------

def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _parse_iso_date(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        # Accept both date-only and full ISO strings.
        if len(value) == 10:
            return datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


async def _existing_workspace_summary(workspace_id: str) -> Optional[dict]:
    school = await gd_find_one(db.session, "schools", {"id": workspace_id})
    if not school:
        return None
    settings = await gd_find_one(
        db.session, "school_settings", {"school_id": workspace_id}
    )
    year = await gd_find_one(
        db.session, "academic_years", {"school_id": workspace_id}
    )
    term = await gd_find_one(
        db.session, "academic_terms", {"school_id": workspace_id}
    )
    teacher = await gd_find_one(db.session, "teachers", {"school_id": workspace_id})
    class_count = await gd_count(db.session, "classes", {"school_id": workspace_id, "is_active": {"$ne": False}})
    return {
        "workspace_id": workspace_id,
        "school": {
            "id": school.get("id"),
            "name": school.get("name"),
            "name_en": school.get("name_en"),
            "logo_url": school.get("logo_url"),
        },
        "settings": {
            "working_days": (settings or {}).get("working_days") or [],
            "periods_per_day": (settings or {}).get("periods_per_day") or 7,
        },
        "academic_year": (year or {}).get("name"),
        "academic_term": (term or {}).get("name"),
        "teacher_id": (teacher or {}).get("id"),
        "class_count": int(class_count or 0),
    }


def _mint_session_tokens(user: dict, workspace_id: str, mfa_recent_at: Optional[int]) -> dict:
    """Rotate the caller's tokens so the freshly-set tenant_id is in claims."""
    base_payload = {
        "sub": user["id"],
        "role": user.get("role"),
        "tenant_id": workspace_id,
    }
    access = create_access_token(
        base_payload, mfa_recent_at=mfa_recent_at, mfa_kind=user.get("mfa_kind")
    )
    refresh = create_refresh_token(
        base_payload,
        remember_me=False,
        mfa_recent_at=mfa_recent_at,
        mfa_kind=user.get("mfa_kind"),
    )
    return {"access_token": access, "refresh_token": refresh}


def _build_user_response(user: dict, workspace_id: str, school_name: str) -> UserResponse:
    return UserResponse(
        id=user["id"],
        email=user["email"],
        full_name=user["full_name"],
        full_name_en=user.get("full_name_en"),
        title=user.get("title"),
        role=UserRole(user["role"]),
        tenant_id=workspace_id,
        tenant_name=school_name,
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
        is_switched=False,
        original_role=None,
    )


# -- Endpoint -------------------------------------------------------------

@router.post("/independent-teacher/bootstrap")
async def bootstrap_independent_teacher_workspace(
    payload: WorkspaceBootstrapRequest,
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    current_user: dict = Depends(get_current_user),
):
    """Atomic workspace materialisation for an IT account.

    Frozen order (per spec §5.1 first-login orchestration):
      login → MFA enrolment → recent assertion → wizard → bootstrap.
    """
    # 1. Role gate (defense in depth — frontend already routes here only
    #    for IT, but the backend is the security boundary).
    if not is_independent_teacher(current_user):
        raise HTTPException(status_code=403, detail=_MSG_NOT_INDEPENDENT_TEACHER)

    # 2. MFA enrolment must have completed.
    #    Skipped entirely while the demo kill switch
    #    (``MFA_ENFORCEMENT_DISABLED``) is engaged so an IT user can
    #    bootstrap their workspace without an enrolled second factor.
    from services import mfa_policy as _mfa_policy
    _mfa_disabled = _mfa_policy.is_enforcement_disabled()
    if not _mfa_disabled and not current_user.get("mfa_enrolled_at"):
        raise HTTPException(
            status_code=403,
            detail={
                "code": "mfa_enrollment_required",
                "message": _MSG_MFA_ENROLLMENT_REQUIRED,
            },
        )

    # 3. Recent MFA assertion in the bearer (≤ 5 minutes). We deliberately
    #    do NOT use the Tier-A `require_recent_mfa` dep here: that gate
    #    additionally demands a registered Passkey, but for IT bootstrap
    #    we accept whichever factor the user enrolled in step 2 (TOTP or
    #    WebAuthn). The 401 + MFA_STEPUP_REQUIRED contract below matches
    #    exactly what the global axios step-up modal (AuthContext.js
    #    interceptor) consumes, so a stale assertion pops the modal,
    #    user re-asserts, and the original POST is replayed.
    try:
        token_payload = jwt.decode(
            credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM]
        )
    except jwt.PyJWTError:
        if _mfa_disabled:
            token_payload = {}
        else:
            raise HTTPException(
                status_code=401,
                detail={
                    "code": "MFA_STEPUP_REQUIRED",
                    "message": _MSG_MFA_STEPUP_REQUIRED,
                    "challenge_endpoint": "/api/auth/mfa/stepup/start",
                    "max_age_seconds": _MFA_STEPUP_MAX_AGE_SECONDS,
                },
            )
    mfa_recent_at = token_payload.get("mfa_recent_at")
    now_ts = int(_utcnow().timestamp())
    if not _mfa_disabled and (
        mfa_recent_at is None
        or (now_ts - int(mfa_recent_at)) > _MFA_STEPUP_MAX_AGE_SECONDS
    ):
        raise HTTPException(
            status_code=401,
            detail={
                "code": "MFA_STEPUP_REQUIRED",
                "message": _MSG_MFA_STEPUP_REQUIRED,
                "challenge_endpoint": "/api/auth/mfa/stepup/start",
                "max_age_seconds": _MFA_STEPUP_MAX_AGE_SECONDS,
            },
        )

    workspace_id = independent_workspace_id(current_user)
    if not workspace_id:
        # is_independent_teacher returned True but the helper couldn't
        # resolve a workspace id — only happens with a malformed user dict.
        raise HTTPException(status_code=500, detail=_MSG_INTERNAL)

    # 4. Idempotency — if the workspace has already been materialised,
    #    return its summary plus rotated tokens. No new rows.
    existing_user = await gd_find_one(db.session, "users", {"id": current_user["id"]})
    if (existing_user or {}).get("tenant_id") == workspace_id:
        existing_school = await gd_find_one(db.session, "schools", {"id": workspace_id})
        if existing_school:
            summary = await _existing_workspace_summary(workspace_id)
            tokens = _mint_session_tokens(existing_user or current_user, workspace_id, mfa_recent_at)
            user_resp = _build_user_response(
                existing_user or current_user,
                workspace_id,
                existing_school.get("name") or summary["school"]["name"],
            )
            return {
                "already_materialised": True,
                "workspace": summary,
                **tokens,
                "token_type": "bearer",
                "user": user_resp.model_dump(),
            }

    # 5. Quota — guard the optional first class BEFORE inserting anything.
    if payload.first_class is not None:
        # Brand-new workspace, but defense in depth: count existing classes
        # against the IT v1 cap (5). A pre-bootstrap workspace has zero
        # classes by construction, so this only fires if step 3 ever loops.
        current_classes = await gd_count(
            db.session, "classes", {"school_id": workspace_id, "is_active": {"$ne": False}}
        )
        if current_classes >= MAX_CLASSES:
            raise HTTPException(status_code=409, detail=_MSG_QUOTA_CLASSES)

    # 6. Atomic materialisation.
    session = db.session
    now = _utcnow()
    school_id = workspace_id
    school_settings_id = str(uuid.uuid4())
    academic_year_id = str(uuid.uuid4())
    academic_term_id = str(uuid.uuid4())
    teacher_id = str(uuid.uuid4())
    class_id: Optional[str] = None

    try:
        # 6.a — schools row (synthetic id).
        await gd_insert(session, "schools", {
            "id": school_id,
            "name": payload.workspace_name_ar,
            "name_en": payload.workspace_name_en,
            "code": school_id[:24],  # synthetic — uniqueness guaranteed by user_id
            "email": current_user.get("email"),
            "logo_url": payload.avatar_url,
            "country": "SA",
            "language": "ar",
            "calendar_system": "hijri_gregorian",
            "status": "active",
            "school_type": "independent_teacher",
            "tenant_type": "independent_teacher",
            "setup_completed": True,
            "principal_id": current_user.get("id"),
            "principal_name": current_user.get("full_name"),
            "principal_email": current_user.get("email"),
            "created_by": current_user.get("id"),
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
        })

        # 6.b — school_settings.
        await gd_insert(session, "school_settings", {
            "id": school_settings_id,
            "school_id": school_id,
            "working_days": payload.working_days,
            "periods_per_day": payload.periods_per_day,
            "language": "ar",
            "calendar": "hijri_gregorian",
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
        })

        # 6.c — academic_year.
        year_start = _parse_iso_date(payload.academic_year_start) or now
        year_end = _parse_iso_date(payload.academic_year_end) or (now + timedelta(days=300))
        await gd_insert(session, "academic_years", {
            "id": academic_year_id,
            "school_id": school_id,
            "name": payload.academic_year_label,
            "start_date": year_start.isoformat(),
            "end_date": year_end.isoformat(),
            "is_current": True,
            "status": "active",
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
        })

        # 6.d — academic_term (single active term).
        await gd_insert(session, "academic_terms", {
            "id": academic_term_id,
            "school_id": school_id,
            "academic_year_id": academic_year_id,
            "name": payload.term_label or "الفصل الأول",
            "term_number": 1,
            "start_date": year_start.isoformat(),
            "end_date": year_end.isoformat(),
            "is_current": True,
            "status": "active",
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
        })

        # 6.e — teachers row mirroring the IT user.
        await gd_insert(session, "teachers", {
            "id": teacher_id,
            "school_id": school_id,
            "user_id": current_user["id"],
            "full_name": current_user.get("full_name") or payload.workspace_name_ar,
            "full_name_en": current_user.get("full_name_en"),
            "email": current_user.get("email"),
            "phone": current_user.get("phone"),
            "is_active": True,
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
        })

        # 6.f — set users.tenant_id (the SOLE place the IT lifecycle
        #        writes this column).
        await gd_update_one(session, "users", {"id": current_user["id"]}, {
            "tenant_id": school_id,
            "teacher_id": teacher_id,
            "updated_at": now.isoformat(),
        })

        # 6.g — optional first class (and matching subject row when the
        #        wizard provided a subject name, so the workspace ships
        #        with at least one Subject FK to attach future lessons /
        #        assessments to). Both rows live in this same transaction.
        subject_id: Optional[str] = None
        if payload.first_class is not None:
            if payload.first_class.subject:
                subject_id = str(uuid.uuid4())
                await gd_insert(session, "subjects", {
                    "id": subject_id,
                    "school_id": school_id,
                    "name": payload.first_class.subject,
                    "name_ar": payload.first_class.subject,
                    "category": "core",
                    "default_periods_per_week": 4,
                    "is_active": True,
                    "is_global": False,
                    "created_at": now.isoformat(),
                    "updated_at": now.isoformat(),
                })
            class_id = str(uuid.uuid4())
            await gd_insert(session, "classes", {
                "id": class_id,
                "school_id": school_id,
                "name": payload.first_class.name,
                "grade_level": payload.first_class.grade_level,
                "capacity": payload.first_class.capacity,
                "current_students": 0,
                "homeroom_teacher_id": teacher_id,
                "homeroom_teacher_name": current_user.get("full_name"),
                "is_active": True,
                "created_at": now.isoformat(),
                "updated_at": now.isoformat(),
            })

        # 6.g.bis — Phase 2 §6.1 (#207): seed the workspace_quota row so
        # the bulk-student-import endpoints find an authoritative row
        # without lazily inserting one on first use. Defaults are taken
        # from the migration's server_defaults so any future schema-level
        # change carries through transparently.
        from quotas.independent_teacher import (
            MAX_STUDENTS as _IT_MAX_STUDENTS,
            MAX_CLASSES as _IT_MAX_CLASSES,
        )
        await gd_insert(session, "workspace_quota", {
            "workspace_school_id": school_id,
            "max_students": _IT_MAX_STUDENTS,
            "max_classes": _IT_MAX_CLASSES,
            "max_imports_per_day": 5,
            "max_rows_per_import": 200,
            "imports_today": 0,
            "imports_today_date": None,
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
        })

        # 6.h — audit log. Part of the success contract: a failed audit
        #        write rolls back the entire bootstrap (every insert above
        #        is in this same SQLAlchemy session). Spec §5.1 requires
        #        exactly one INDEPENDENT_TEACHER_BOOTSTRAP entry on
        #        success, scoped to the new workspace id — no silent
        #        success without an audit row is permitted.
        audit = AuditLogEngine(Repos(session))
        await audit.log(
            action="INDEPENDENT_TEACHER_BOOTSTRAP",
            performed_by=current_user["id"],
            tenant_id=school_id,
            entity_type="school",
            entity_id=school_id,
            actor_email=current_user.get("email"),
            actor_name=current_user.get("full_name"),
            actor_role=current_user.get("role"),
            ip_address=(request.client.host if request.client else None),
            user_agent=request.headers.get("user-agent"),
            details={
                "workspace_name_ar": payload.workspace_name_ar,
                "periods_per_day": payload.periods_per_day,
                "working_days_count": len(payload.working_days),
                "first_class_created": class_id is not None,
                "first_subject_created": subject_id is not None,
            },
        )

        # Single commit — every insert above is in this same SQLAlchemy
        # session. If any insert raised, control jumped to except/rollback
        # below and nothing was committed.
        await session.commit()

    except HTTPException:
        await session.rollback()
        raise
    except Exception as exc:
        await session.rollback()
        logger.exception("IT workspace bootstrap failed: %s", exc)
        raise HTTPException(status_code=500, detail=_MSG_INTERNAL)

    # 7. Re-read the user (with refreshed tenant_id) and rotate tokens.
    refreshed_user = await gd_find_one(db.session, "users", {"id": current_user["id"]}) or current_user
    refreshed_user["tenant_id"] = school_id
    refreshed_user.setdefault("teacher_id", teacher_id)

    summary = await _existing_workspace_summary(school_id) or {
        "workspace_id": school_id,
        "school": {"id": school_id, "name": payload.workspace_name_ar},
        "settings": {
            "working_days": payload.working_days,
            "periods_per_day": payload.periods_per_day,
        },
        "academic_year": payload.academic_year_label,
        "academic_term": payload.term_label or "الفصل الأول",
        "teacher_id": teacher_id,
        "class_count": 1 if class_id else 0,
    }

    tokens = _mint_session_tokens(refreshed_user, school_id, mfa_recent_at)
    user_resp = _build_user_response(refreshed_user, school_id, payload.workspace_name_ar)

    return {
        "already_materialised": False,
        "workspace": summary,
        **tokens,
        "token_type": "bearer",
        "user": user_resp.model_dump(),
    }


__all__ = ["router"]
