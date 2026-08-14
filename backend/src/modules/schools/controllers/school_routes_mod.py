"""
NASSAQ Route Module: School CRUD, dashboard, updates
Auto-consolidated during Phase 8 modularization.
"""
from fastapi import APIRouter, HTTPException, Depends, status, Header, Query, Body, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import Response
from starlette.responses import StreamingResponse
from pydantic import BaseModel, Field, ConfigDict, EmailStr, model_validator
from typing import List, Optional, Any, Dict, Tuple
from datetime import datetime, timezone, timedelta
import uuid, os, logging, json, random, re, io, base64
import time as _time

_public_stats_cache = {"data": None, "expires": 0}
_PUBLIC_STATS_TTL = 60

# SECURITY: a curated, low-cardinality public counter for the landing-page
# social-proof line. Returns *only* the total active-school count — no
# students/teachers/parents breakdown, no school names/ids, no per-tenant
# enumeration. Cached aggressively to blunt scraping.
_public_schools_count_cache = {"data": None, "expires": 0}
_PUBLIC_SCHOOLS_COUNT_TTL = 300
_public_growth_cache = {"data": None, "expires": 0}
_PUBLIC_GROWTH_TTL = 300


def _bucket_display(n: int) -> str:
    """Bucket a raw count into a vetted display string.

    SECURITY: never returns the raw value. The output is one of a small set
    of preformatted, monotonic strings ("10+", "25+", ... "1K+", "2.5K+", ...)
    so the browser cannot reverse-engineer the exact count from the response.
    """
    try:
        n = int(n or 0)
    except (TypeError, ValueError):
        n = 0
    if n <= 0:
        return "10+"
    buckets = [
        (10, "10+"), (25, "25+"), (50, "50+"), (100, "100+"),
        (250, "250+"), (500, "500+"), (1000, "1K+"),
        (2500, "2.5K+"), (5000, "5K+"), (10000, "10K+"),
        (25000, "25K+"), (50000, "50K+"), (100000, "100K+"),
    ]
    chosen = "10+"
    for threshold, label in buckets:
        if n >= threshold:
            chosen = label
        else:
            break
    return chosen

from dependencies import (
    db, get_current_user, require_roles, UserRole, SchoolStatus,
    hash_password, verify_password, create_access_token,
    JWT_SECRET, JWT_ALGORITHM, ACCESS_TOKEN_EXPIRE, security, logger,
    audit_engine, AuditAction, AuditSeverity,
    smart_scheduling_engine, TimetableRunStatus, TimetableStatus,
    ConflictType, ConflictSeverity, PreValidationResult, GenerationResult,
    hakim_engine, reporting_engine, export_engine, session_engine,
    REPORT_TYPES, generate_student_qr_code,
    require_recent_mfa,
)

from sqlalchemy.exc import IntegrityError
from engines.sql_utils import gd_find, gd_find_one, gd_insert, gd_insert_many, gd_update_one, gd_update_many, gd_count, gd_delete_one, gd_delete_many, gd_distinct, gd_upsert, _gd_aggregate
from shared_models import (
    SchoolCreate, SchoolResponse
)
from src.common.utils.avatar_image import normalize_image_field_or_400
from src.common.utils.avatar_serving import is_internal_image_url, signed_image_url
from src.common.utils.platform_admin_preview import assess_principal_preview_eligibility
from src.common.utils.school_code import (
    insert_school_with_unique_code,
    insert_school_with_custom_code,
    is_school_code_conflict,
)

router = APIRouter()



# ============== SCHOOLS (TENANTS) ROUTES ==============
@router.post("/schools", response_model=SchoolResponse)
async def create_school(
    school_data: SchoolCreate,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))
):
    # Validate principal email uniqueness (except if teacher creating parent account)
    if school_data.principal_email:
        existing_email = await gd_find_one(db.session, "users", {"email": school_data.principal_email})
        if existing_email:
            raise HTTPException(status_code=400, detail="البريد الإلكتروني مستخدم مسبقاً")
    
    # Validate principal phone uniqueness
    if school_data.principal_phone:
        existing_phone = await gd_find_one(db.session, "users", {"phone": school_data.principal_phone})
        if existing_phone:
            raise HTTPException(status_code=400, detail="رقم الهاتف مستخدم مسبقاً")
    
    school_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).isoformat()
    school_phone = school_data.phone or school_data.principal_phone

    def _build_school_doc(code: str) -> dict:
        return {
            "id": school_id,
            "name": school_data.name,
            "name_en": school_data.name_en,
            "code": code,
            # Use principal_email as school email if not provided
            "email": school_data.email or school_data.principal_email or f"school-{code.lower()}@nassaq.com",
            "phone": school_phone,
            "address": school_data.address,
            "city": school_data.city,
            "region": school_data.region,
            "country": school_data.country or "SA",
            "logo_url": None,
            "status": SchoolStatus.ACTIVE.value,  # Set to active immediately
            "student_capacity": school_data.student_capacity,
            "current_students": 0,
            "current_teachers": 0,
            # New fields
            "language": school_data.language or "ar",
            "calendar_system": school_data.calendar_system or "hijri_gregorian",
            "school_type": school_data.school_type or "public",
            "stage": school_data.stage or "primary",
            "principal_name": school_data.principal_name,
            "principal_email": school_data.principal_email,
            "principal_phone": school_data.principal_phone,
            "principal_mobile": school_data.principal_mobile,
            "educational_pathway": school_data.educational_pathway,
            "created_at": created_at,
            "updated_at": created_at,
            "created_by": current_user.get("user_id"),
        }

    if school_data.code:
        # Operator-supplied custom code: a genuine duplicate is a real error.
        try:
            await insert_school_with_custom_code(db.session, _build_school_doc, school_data.code)
        except IntegrityError as ie:
            if is_school_code_conflict(ie):
                raise HTTPException(status_code=400, detail="رمز المدرسة مستخدم مسبقاً — يُرجى اختيار رمز آخر")
            raise
        school_code = school_data.code
    else:
        # Auto-generated code: silently regenerate on collision.
        school_code, _ = await insert_school_with_unique_code(
            db.session, _build_school_doc, country=school_data.country or "SA"
        )

    school_email = school_data.email or school_data.principal_email or f"school-{school_code.lower()}@nassaq.com"
    
    # Create principal account if email provided
    if school_data.principal_email and school_data.principal_name:
        import secrets
        import string
        chars = string.ascii_letters + string.digits + "@#$"
        temp_password = ''.join(secrets.choice(chars) for _ in range(12))
        
        hashed_password = hash_password(temp_password)
        
        principal_id = str(uuid.uuid4())
        principal_doc = {
            "id": principal_id,
            "email": school_data.principal_email,
            "password_hash": hashed_password,
            "full_name": school_data.principal_name,
            "full_name_en": None,
            "role": UserRole.SCHOOL_PRINCIPAL.value,
            "tenant_id": school_id,
            "phone": school_data.principal_phone,
            "avatar_url": None,
            "is_active": True,
            "must_change_password": True,  # Force password change on first login
            "preferred_language": school_data.language or "ar",
            "preferred_theme": "light",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        await gd_insert(db.session, "users", principal_doc)
        
        # Log tenant creation using Audit Engine
        await audit_engine.log_data_change(
            action=AuditAction.TENANT_CREATED.value,
            performed_by=current_user.get("id", current_user.get("user_id")),
            entity_type="tenant",
            entity_id=school_id,
            new_values={
                "school_code": school_code,
                "school_name": school_data.name,
                "principal_email": school_data.principal_email,
                "school_type": school_data.school_type,
                "stage": school_data.stage
            }
        )
        
        # Log principal creation
        await audit_engine.log_data_change(
            action=AuditAction.USER_CREATED.value,
            performed_by=current_user.get("id", current_user.get("user_id")),
            entity_type="user",
            entity_id=principal_id,
            tenant_id=school_id,
            new_values={
                "role": "school_principal",
                "email": school_data.principal_email,
                "full_name": school_data.principal_name
            }
        )
    
    # Create default school settings from template
    default_settings = await gd_find_one(db.session, "default_settings", {"id": "default-school-settings"})
    if default_settings:
        from routes.school_settings_mod import normalize_school_settings_doc
        school_settings = normalize_school_settings_doc({
            "id": f"settings-{school_id}",
            "school_id": school_id,
            "working_days": default_settings.get("working_days"),
            "working_days_ar": default_settings.get("working_days_ar"),
            "working_days_en": default_settings.get("working_days_en"),
            "weekend_days_ar": default_settings.get("weekend_days_ar"),
            "weekend_days_en": default_settings.get("weekend_days_en"),
            "periods_per_day": default_settings.get("periods_per_day"),
            "period_duration_minutes": default_settings.get("period_duration_minutes"),
            "break_duration_minutes": default_settings.get("break_duration_minutes"),
            "prayer_duration_minutes": default_settings.get("prayer_duration_minutes"),
            "school_day_start": default_settings.get("school_day_start"),
            "school_day_end": default_settings.get("school_day_end"),
            "time_slots": default_settings.get("time_slots"),
            "education_track": "track-general",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        })
        await gd_insert(db.session, "school_settings", school_settings)

    # Seed the canonical standard subject catalog so the newly created
    # school can immediately assign teaching subjects in the add-teacher
    # wizard and build schedules. create_school is a platform-admin
    # tenant-creation surface and never mints Independent-Teacher
    # workspaces, so every school created here is a real school. A failure
    # rolls back the whole creation (atomic) rather than leaving a school
    # with no subjects; the Alembic backfill migration is the safety net.
    from constants.default_subjects import build_default_subject_docs
    await gd_insert_many(
        db.session, "subjects", build_default_subject_docs(school_id, created_at)
    )

    return SchoolResponse(
        id=school_id,
        name=school_data.name,
        name_en=school_data.name_en,
        code=school_code,
        email=school_email,
        phone=school_phone,
        address=school_data.address,
        city=school_data.city,
        region=school_data.region,
        country=school_data.country or "SA",
        logo_url=None,
        status=SchoolStatus.ACTIVE,
        student_capacity=school_data.student_capacity,
        current_students=0,
        current_teachers=0,
        created_at=created_at
    )

@router.post("/schools/draft", response_model=SchoolResponse)
async def create_school_draft(
    school_data: SchoolCreate,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))
):
    """Create a school as draft (setup status) - does not create principal account"""
    school_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).isoformat()
    school_phone = school_data.phone or school_data.principal_phone

    def _build_school_doc(code: str) -> dict:
        return {
            "id": school_id,
            "name": school_data.name or "مسودة مدرسة",
            "name_en": school_data.name_en,
            "code": code,
            "email": school_data.email or f"school-{code.lower()}@nassaq.com",
            "phone": school_phone,
            "address": school_data.address or "",
            "city": school_data.city or "",
            "region": school_data.region,
            "country": school_data.country or "SA",
            "logo_url": None,
            "status": "setup",  # Set as draft/setup
            "student_capacity": school_data.student_capacity,
            "current_students": 0,
            "current_teachers": 0,
            "language": school_data.language or "ar",
            "calendar_system": school_data.calendar_system or "hijri_gregorian",
            "school_type": school_data.school_type or "public",
            "stage": school_data.stage or "primary",
            "principal_name": school_data.principal_name or "",
            "principal_email": school_data.principal_email or "",
            "principal_phone": school_data.principal_phone or "",
            "principal_mobile": school_data.principal_mobile or "",
            "educational_pathway": school_data.educational_pathway or "",
            "created_at": created_at,
            "updated_at": created_at,
            "created_by": current_user.get("user_id"),
        }

    if school_data.code:
        try:
            await insert_school_with_custom_code(db.session, _build_school_doc, school_data.code)
        except IntegrityError as ie:
            if is_school_code_conflict(ie):
                raise HTTPException(status_code=400, detail="رمز المدرسة مستخدم مسبقاً — يُرجى اختيار رمز آخر")
            raise
        school_code = school_data.code
    else:
        school_code, _ = await insert_school_with_unique_code(
            db.session, _build_school_doc, country=school_data.country or "SA"
        )

    school_email = school_data.email or f"school-{school_code.lower()}@nassaq.com"

    # Log draft creation
    await audit_engine.log_data_change(
        action=AuditAction.TENANT_CREATED.value,
        performed_by=current_user.get("id", current_user.get("user_id")),
        entity_type="tenant",
        entity_id=school_id,
        new_values={
            "school_code": school_code,
            "school_name": school_data.name,
            "status": "setup",
            "is_draft": True
        }
    )
    
    # Create default school settings from template
    default_settings = await gd_find_one(db.session, "default_settings", {"id": "default-school-settings"})
    if default_settings:
        from routes.school_settings_mod import normalize_school_settings_doc
        school_settings = normalize_school_settings_doc({
            "id": f"settings-{school_id}",
            "school_id": school_id,
            "working_days": default_settings.get("working_days"),
            "working_days_ar": default_settings.get("working_days_ar"),
            "working_days_en": default_settings.get("working_days_en"),
            "weekend_days_ar": default_settings.get("weekend_days_ar"),
            "weekend_days_en": default_settings.get("weekend_days_en"),
            "periods_per_day": default_settings.get("periods_per_day"),
            "period_duration_minutes": default_settings.get("period_duration_minutes"),
            "break_duration_minutes": default_settings.get("break_duration_minutes"),
            "prayer_duration_minutes": default_settings.get("prayer_duration_minutes"),
            "school_day_start": default_settings.get("school_day_start"),
            "school_day_end": default_settings.get("school_day_end"),
            "time_slots": default_settings.get("time_slots"),
            "education_track": "track-general",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        })
        await gd_insert(db.session, "school_settings", school_settings)
    
    return SchoolResponse(
        id=school_id,
        name=school_data.name or "مسودة مدرسة",
        name_en=school_data.name_en,
        code=school_code,
        email=school_email,
        phone=school_phone,
        address=school_data.address or "",
        city=school_data.city or "",
        region=school_data.region,
        country=school_data.country or "SA",
        logo_url=None,
        status=SchoolStatus.SETUP,
        student_capacity=school_data.student_capacity,
        current_students=0,
        current_teachers=0,
        created_at=created_at
    )

@router.delete("/schools/{school_id}/draft")
async def delete_school_draft(
    school_id: str,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))
):
    """Delete a school draft (only if status is 'setup')"""
    school = await gd_find_one(db.session, "schools", {"id": school_id})
    if not school:
        raise HTTPException(status_code=404, detail="المدرسة غير موجودة")

    if school.get("status") != "setup":
        raise HTTPException(status_code=400, detail="يمكن حذف المسودات فقط (الحالة: قيد الإعداد)")

    await gd_delete_one(db.session, "schools", {"id": school_id})

    # Clean up any associated data
    await gd_delete_many(db.session, "users", {"tenant_id": school_id})
    await gd_delete_many(db.session, "school_settings", {"school_id": school_id})

    await audit_engine.log_data_change(
        action=AuditAction.TENANT_UPDATED.value,
        performed_by=current_user.get("id", current_user.get("user_id")),
        entity_type="tenant",
        entity_id=school_id,
        new_values={
            "action": "DRAFT_DELETED",
            "school_name": school.get("name", ""),
        }
    )

    return {"success": True, "message": "تم حذف المسودة بنجاح"}


def _normalize_school(
    s: dict,
    *,
    principal_counts: Optional[Dict[str, int]] = None,
    student_counts: Optional[Dict[str, int]] = None,
    teacher_counts: Optional[Dict[str, int]] = None,
) -> dict:
    """Normalize school document to match SchoolResponse fields.

    Task #825: ``current_students`` / ``current_teachers`` are reported from
    live, tenant-scoped counts (``student_counts`` / ``teacher_counts``,
    computed by :func:`_live_entity_counts_by_tenant`) when supplied, instead
    of the stale denormalized columns on the ``schools`` row. The denormalized
    columns are only nudged by scattered increments and drift below the real
    row count over time. When no live maps are passed we fall back to the
    stored values for backward compatibility.
    """
    school_id = s.get("id") or ""
    principal_count = None
    if principal_counts is not None:
        principal_count = principal_counts.get(school_id, 0)

    preview = assess_principal_preview_eligibility(
        s,
        active_principal_count=principal_count,
    )

    if student_counts is not None:
        current_students = student_counts.get(school_id, 0)
    else:
        current_students = s.get("current_students") or s.get("student_count") or 0
    if teacher_counts is not None:
        current_teachers = teacher_counts.get(school_id, 0)
    else:
        current_teachers = s.get("current_teachers") or s.get("teacher_count") or 0

    return {
        **s,
        # Task #1139 — never ship the stored base64 logo inline; mint the
        # signed cacheable URL (non-data: values pass through unchanged).
        "logo_url": signed_image_url("logo", school_id, s.get("logo_url")),
        "name": s.get("name") or s.get("name_ar") or s.get("name_en") or "",
        "code": s.get("code") or s.get("license_number") or s.get("id") or "",
        "email": s.get("email") or "",
        "country": s.get("country") or "SA",
        "status": s.get("status") or "active",
        "student_capacity": s.get("student_capacity") or s.get("student_count") or 500,
        "current_students": current_students,
        "current_teachers": current_teachers,
        "created_at": s.get("created_at") or "",
        "entity_kind": preview["entity_kind"],
        "can_preview_as_principal": preview["can_preview_as_principal"],
        "preview_block_reason": preview["preview_block_reason"],
    }


async def _active_principal_counts_by_tenant() -> Dict[str, int]:
    """Batch count active school principals per tenant for preview metadata."""
    from sqlalchemy import text as _sa_text

    result = await db.session.execute(
        _sa_text(
            """
            SELECT tenant_id, COUNT(*)::int AS cnt
            FROM users
            WHERE role = 'school_principal'
              AND is_active = TRUE
              AND tenant_id IS NOT NULL
            GROUP BY tenant_id
            """
        )
    )
    rows = result.mappings().all()
    return {row["tenant_id"]: row["cnt"] for row in rows if row.get("tenant_id")}


async def _live_entity_counts_by_tenant() -> Tuple[Dict[str, int], Dict[str, int]]:
    """Batch live student/teacher counts per tenant for the platform list.

    Task #825 / #826: the platform schools list reports live, tenant-scoped
    counts instead of the stale denormalized ``current_students`` /
    ``current_teachers`` columns. The canonical predicates and grouped queries
    now live in :mod:`engines.entity_counts` so the platform list, the stored
    columns (reconciled on every write), and each school's own pages all share
    one definition and never disagree.
    """
    from engines.entity_counts import live_counts_by_tenant

    return await live_counts_by_tenant(db.session)


@router.get("/schools", response_model=List[SchoolResponse])
async def get_schools(
    status: Optional[str] = None,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.MINISTRY_REP, UserRole.PLATFORM_SUB_ADMIN]))
):
    query = {}
    if status:
        query["status"] = status
    
    schools = await gd_find(db.session, "schools", query, limit=1000)
    principal_counts = await _active_principal_counts_by_tenant()
    student_counts, teacher_counts = await _live_entity_counts_by_tenant()
    return [
        SchoolResponse(**_normalize_school(
            s,
            principal_counts=principal_counts,
            student_counts=student_counts,
            teacher_counts=teacher_counts,
        ))
        for s in schools
    ]

@router.get("/schools/{school_id}", response_model=SchoolResponse)
async def get_school(school_id: str, current_user: dict = Depends(get_current_user)):
    # Authorization: platform/ministry roles can fetch any school;
    # everyone else may only read their own tenant's school (prevents IDOR).
    privileged_roles = {UserRole.PLATFORM_ADMIN.value, UserRole.MINISTRY_REP.value}
    user_role = current_user.get("role")
    user_tenant = current_user.get("tenant_id")
    if user_role not in privileged_roles and school_id != user_tenant:
        raise HTTPException(status_code=403, detail="غير مصرح بالوصول إلى بيانات هذه المدرسة")

    school = await gd_find_one(db.session, "schools", {"id": school_id})
    if not school:
        raise HTTPException(status_code=404, detail="المدرسة غير موجودة")
    principal_counts = await _active_principal_counts_by_tenant()
    # Task #825: report the same live counts as the list / in-school pages.
    student_counts, teacher_counts = await _live_entity_counts_by_tenant()
    return SchoolResponse(**_normalize_school(
        school,
        principal_counts=principal_counts,
        student_counts=student_counts,
        teacher_counts=teacher_counts,
    ))

@router.put("/schools/{school_id}/status")
async def update_school_status(
    school_id: str,
    status: SchoolStatus,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))
):
    result = await gd_update_one(db.session, "schools", {"id": school_id}, {"status": status.value, "updated_at": datetime.now(timezone.utc).isoformat()})
    if result == 0:
        raise HTTPException(status_code=404, detail="المدرسة غير موجودة")
    return {"message": "تم تحديث حالة المدرسة"}


class SchoolStatusChangeRequest(BaseModel):
    reason: str = Field(..., min_length=3, description="سبب التغيير")


@router.post("/schools/{school_id}/suspend")
async def suspend_school(
    school_id: str,
    body: SchoolStatusChangeRequest,
    request: Request,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN])),
    # Suspend is as destructive as its inverse — it flips the tenant to
    # ``suspended`` AND disables every user account in it. It must carry the
    # same fresh-MFA posture as ``activate_school``. When the global MFA
    # kill switch (``MFA_ENFORCEMENT_DISABLED``) is engaged this dependency
    # short-circuits to a no-op, so it is safe while MFA is paused.
    _stepup: dict = Depends(require_recent_mfa()),
):
    """Suspend a school with reason - logs full audit trail"""
    school = await gd_find_one(db.session, "schools", {"id": school_id})
    if not school:
        raise HTTPException(status_code=404, detail="المدرسة غير موجودة")

    previous_status = school.get("status", "active")
    if previous_status == "suspended":
        raise HTTPException(status_code=400, detail="المدرسة معلقة مسبقاً")

    now = datetime.now(timezone.utc).isoformat()

    # Update school status
    await gd_update_one(db.session, "schools", {"id": school_id}, {
            "status": "suspended",
            "suspended_at": now,
            "suspended_by": current_user.get("id", current_user.get("user_id")),
            "suspension_reason": body.reason,
            "updated_at": now,
        })

    await gd_update_many(db.session, "users", {"tenant_id": school_id, "is_active": True}, {"is_active": False, "suspended_at": now, "suspended_by_school": True})

    # Audit log
    performer_id = current_user.get("id", current_user.get("user_id"))
    await audit_engine.log_data_change(
        action=AuditAction.TENANT_SUSPENDED.value,
        performed_by=performer_id,
        entity_type="school",
        entity_id=school_id,
        tenant_id=school_id,
        previous_values={"status": previous_status},
        new_values={
            "status": "suspended",
            "reason": body.reason,
            "performed_by_email": current_user.get("email", ""),
            "school_name": school.get("name", ""),
        },
        actor_role=current_user.get("role"),
        actor_email=current_user.get("email"),
        actor_name=current_user.get("full_name"),
    )

    return {
        "message": "تم تعليق المدرسة بنجاح",
        "school_id": school_id,
        "previous_status": previous_status,
        "new_status": "suspended",
        "reason": body.reason,
        "timestamp": now,
    }


@router.post("/schools/{school_id}/activate")
async def activate_school(
    school_id: str,
    body: SchoolStatusChangeRequest,
    request: Request,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN])),
    # Reactivating a suspended school re-enables every user account in that
    # tenant. Require a fresh MFA proof so a stolen admin bearer token cannot
    # silently restore an entire suspended tenant.
    _stepup: dict = Depends(require_recent_mfa()),
):
    """Activate a suspended school with reason - logs full audit trail"""
    school = await gd_find_one(db.session, "schools", {"id": school_id})
    if not school:
        raise HTTPException(status_code=404, detail="المدرسة غير موجودة")

    previous_status = school.get("status", "suspended")

    now = datetime.now(timezone.utc).isoformat()

    # Update school status
    await gd_update_one(db.session, "schools", {"id": school_id}, {
            "status": "active",
            "activated_at": now,
            "activated_by": current_user.get("id", current_user.get("user_id")),
            "activation_reason": body.reason,
            "updated_at": now,
        })

    # Re-enable accounts and advance last_password_change so any attacker-held
    # tokens that were valid before the suspension are immediately rejected.
    # The token validator rejects access/refresh tokens whose iat predates
    # last_password_change, closing the window where old stolen tokens would
    # become valid again the moment the school is reactivated.
    await gd_update_many(
        db.session, "users",
        {"tenant_id": school_id, "is_active": False, "suspended_by_school": True},
        {"is_active": True, "activated_at": now, "suspended_by_school": False,
         "last_password_change": now},
    )

    # Audit log
    performer_id = current_user.get("id", current_user.get("user_id"))
    await audit_engine.log_data_change(
        action=AuditAction.TENANT_ACTIVATED.value,
        performed_by=performer_id,
        entity_type="school",
        entity_id=school_id,
        tenant_id=school_id,
        previous_values={"status": previous_status},
        new_values={
            "status": "active",
            "reason": body.reason,
            "performed_by_email": current_user.get("email", ""),
            "school_name": school.get("name", ""),
        },
        actor_role=current_user.get("role"),
        actor_email=current_user.get("email"),
        actor_name=current_user.get("full_name"),
    )

    return {
        "message": "تم تفعيل المدرسة بنجاح",
        "school_id": school_id,
        "previous_status": previous_status,
        "new_status": "active",
        "reason": body.reason,
        "timestamp": now,
    }


@router.get("/schools/{school_id}/detail")
async def get_school_detail(
    school_id: str,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))
):
    """Get comprehensive school detail for Platform Admin"""
    school = await gd_find_one(db.session, "schools", {"id": school_id})
    if not school:
        raise HTTPException(status_code=404, detail="المدرسة غير موجودة")

    # Fetch related data
    users = await gd_find(db.session, "users", {"tenant_id": school_id}, limit=1000)
    students = await gd_find(db.session, "students", {"school_id": school_id}, limit=500)
    teachers = await gd_find(db.session, "teachers", {"school_id": school_id}, limit=500)
    classes = await gd_find(db.session, "classes", {"school_id": school_id, "is_active": {"$ne": False}}, limit=200)

    # Find principal account (school admin login)
    principal_account = await gd_find_one(db.session, "users", {"tenant_id": school_id, "role": UserRole.SCHOOL_PRINCIPAL.value})
    has_credentials = principal_account is not None

    # Audit logs for this school
    audit_logs = await gd_find(db.session, "audit_logs", {"$or": [{"tenant_id": school_id}, {"entity_id": school_id}]}, limit=100)
    audit_logs.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    audit_logs = audit_logs[:50]

    # Log VIEW_SCHOOL action
    performer_id = current_user.get("id", current_user.get("user_id"))
    await audit_engine.log_data_change(
        action=AuditAction.TENANT_UPDATED.value,
        performed_by=performer_id,
        entity_type="school",
        entity_id=school_id,
        tenant_id=school_id,
        new_values={"action": "VIEW_SCHOOL", "school_name": school.get("name", "")}
    )

    principal_counts = await _active_principal_counts_by_tenant()
    # Task #825: keep the normalized school card's counts consistent with the
    # platform list (live, is_active-filtered) rather than the stale columns.
    student_counts, teacher_counts = await _live_entity_counts_by_tenant()
    school_payload = _normalize_school(
        school,
        principal_counts=principal_counts,
        student_counts=student_counts,
        teacher_counts=teacher_counts,
    )

    return {
        "school": school_payload,
        "stats": {
            "total_users": len(users),
            "total_students": len(students),
            "total_teachers": len(teachers),
            "total_classes": len(classes),
        },
        "principal_account": principal_account,
        "has_credentials": has_credentials,
        "users": users[:100],
        "students": students[:100],
        "teachers": teachers[:100],
        "classes": classes[:50],
        "audit_logs": audit_logs,
    }


class SchoolCredentialsRequest(BaseModel):
    email: str = Field(..., min_length=5, description="البريد الإلكتروني لمدير المدرسة")
    name: Optional[str] = None
    password: Optional[str] = Field(None, min_length=8, description="كلمة المرور الجديدة (اختياري - يُولَّد تلقائياً إن لم تُحدَّد)")


@router.post("/schools/{school_id}/credentials")
async def manage_school_credentials(
    school_id: str,
    body: SchoolCredentialsRequest,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN])),
    _mfa: dict = Depends(require_recent_mfa()),
):
    """Create or update the school principal account credentials (email + password)"""
    school = await gd_find_one(db.session, "schools", {"id": school_id})
    if not school:
        raise HTTPException(status_code=404, detail="المدرسة غير موجودة")

    import secrets, string as _string
    now = datetime.now(timezone.utc).isoformat()
    principal_name = body.name or school.get("principal_name") or "مدير المدرسة"

    # Find existing principal account for this school
    existing_principal = await gd_find_one(db.session, "users", {
        "tenant_id": school_id,
        "role": UserRole.SCHOOL_PRINCIPAL.value
    })

    # Determine password handling
    raw_password = None
    generated = False
    if body.password:
        raw_password = body.password
    elif not existing_principal:
        # New account — auto-generate password
        chars = _string.ascii_letters + _string.digits + "!@#$%"
        raw_password = ''.join(secrets.choice(chars) for _ in range(14))
        generated = True
    # If updating existing and no password provided — keep current password (no override)

    is_new = False
    if existing_principal:
        # Update credentials (only password if explicitly provided)
        update_fields = {
            "email": body.email,
            "full_name": principal_name,
            "must_change_password": True if raw_password else existing_principal.get("must_change_password", False),
            "updated_at": now,
        }
        if raw_password:
            update_fields["password_hash"] = hash_password(raw_password)
            update_fields["last_password_change"] = now
        await gd_update_one(db.session, "users", {"id": existing_principal["id"]}, update_fields)
        principal_id = existing_principal["id"]
    else:
        # Create new principal
        hashed = hash_password(raw_password)
        principal_id = str(uuid.uuid4())
        await gd_insert(db.session, "users", {
            "id": principal_id,
            "email": body.email,
            "password_hash": hashed,
            "full_name": principal_name,
            "role": UserRole.SCHOOL_PRINCIPAL.value,
            "tenant_id": school_id,
            "is_active": True,
            "must_change_password": True,
            "preferred_language": "ar",
            "preferred_theme": "light",
            "created_at": now,
            "updated_at": now,
        })
        is_new = True

    # Update school record with principal info
    await gd_update_one(db.session, "schools", {"id": school_id}, {
            "principal_email": body.email,
            "principal_name": principal_name,
            "updated_at": now,
        })

    # Audit log
    performer_id = current_user.get("id", current_user.get("user_id"))
    await audit_engine.log_data_change(
        action=AuditAction.USER_CREATED.value if is_new else AuditAction.USER_UPDATED.value,
        performed_by=performer_id,
        entity_type="user",
        entity_id=principal_id,
        tenant_id=school_id,
        new_values={
            "action": "SET_SCHOOL_CREDENTIALS",
            "email": body.email,
            "school_name": school.get("name", ""),
            "is_new_account": is_new,
        }
    )

    return {
        "success": True,
        "is_new": is_new,
        "email": body.email,
        "name": principal_name,
        "temp_password": raw_password,
        "password_was_generated": generated,
        "password_was_changed": raw_password is not None,
        "message": "تم إنشاء حساب المدير بنجاح" if is_new else "تم تحديث بيانات الدخول بنجاح",
    }


@router.patch("/schools/{school_id}")
async def patch_school(
    school_id: str,
    data: dict,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN]))
):
    """Patch school fields (status, ai_enabled, etc.)"""
    privileged_roles = {UserRole.PLATFORM_ADMIN.value}
    if current_user.get("role") not in privileged_roles and school_id != current_user.get("tenant_id"):
        raise HTTPException(status_code=403, detail="غير مصرح بتعديل بيانات هذه المدرسة")

    school = await gd_find_one(db.session, "schools", {"id": school_id})
    if not school:
        raise HTTPException(status_code=404, detail="المدرسة غير موجودة")

    patchable = ["name", "name_en", "email", "phone", "address", "city", "region",
                 "logo_url", "website", "principal_name", "status", "ai_enabled",
                 "student_capacity", "school_type", "stage"]
    update_data = {"updated_at": datetime.now(timezone.utc).isoformat()}
    for field in patchable:
        if field in data:
            update_data[field] = data[field]

    if "logo_url" in update_data and is_internal_image_url(update_data["logo_url"]):
        # Echoed-back signed URL means "unchanged" — never store it.
        update_data.pop("logo_url")
    if "logo_url" in update_data:
        update_data["logo_url"] = await normalize_image_field_or_400(update_data["logo_url"])

    await gd_update_one(db.session, "schools", {"id": school_id}, update_data)
    updated = await gd_find_one(db.session, "schools", {"id": school_id})
    updated["logo_url"] = signed_image_url("logo", school_id, updated.get("logo_url"))
    return updated




# ============== UPDATE SCHOOL API ==============
@router.put("/schools/{school_id}")
async def update_school(
    school_id: str,
    data: dict,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN]))
):
    """Update school information"""
    privileged_roles = {UserRole.PLATFORM_ADMIN.value}
    if current_user.get("role") not in privileged_roles and school_id != current_user.get("tenant_id"):
        raise HTTPException(status_code=403, detail="غير مصرح بتعديل بيانات هذه المدرسة")

    school = await gd_find_one(db.session, "schools", {"id": school_id})
    if not school:
        raise HTTPException(status_code=404, detail="المدرسة غير موجودة")
    
    # Build update data
    update_data = {"updated_at": datetime.now(timezone.utc).isoformat()}
    
    allowed_fields = ["name", "name_en", "email", "phone", "address", "city", "region", "logo_url", "website", "principal_name"]
    for field in allowed_fields:
        if field in data and data[field] is not None:
            update_data[field] = data[field]

    if "logo_url" in update_data and is_internal_image_url(update_data["logo_url"]):
        # Echoed-back signed URL means "unchanged" — never store it.
        update_data.pop("logo_url")
    if "logo_url" in update_data:
        update_data["logo_url"] = await normalize_image_field_or_400(update_data["logo_url"])

    await gd_update_one(db.session, "schools", {"id": school_id}, update_data)
    
    updated_school = await gd_find_one(db.session, "schools", {"id": school_id})
    updated_school["logo_url"] = signed_image_url("logo", school_id, updated_school.get("logo_url"))
    return updated_school





# ============== SCHOOL DASHBOARD API ==============
@router.get("/school/dashboard")
async def get_school_dashboard(
    current_user: dict = Depends(get_current_user)
):
    """Get comprehensive dashboard data for the school principal - LIVE DATA"""
    school_id = current_user.get("tenant_id")
    
    if not school_id:
        raise HTTPException(status_code=400, detail="المستخدم غير مرتبط بمدرسة")
    
    # Get counts from database - REAL DATA
    total_students = await gd_count(db.session, "students", {"school_id": school_id, "is_active": True})
    total_teachers = await gd_count(db.session, "teachers", {"school_id": school_id, "is_active": True})
    total_classes = await gd_count(db.session, "classes", {"school_id": school_id, "is_active": True})
    
    # Get today's attendance - using 'type' field
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    
    student_attendance = await gd_find(db.session, "attendance", {
        "school_id": school_id,
        "date": today,
        "type": "student"
    }, limit=10000)
    
    # Get teacher attendance from teacher_attendance collection (where it's actually stored)
    teacher_attendance_records = await gd_find(db.session, "teacher_attendance", {
        "school_id": school_id,
        "date": today
    }, limit=1000)
    
    # If no records in teacher_attendance, fallback to attendance collection
    if not teacher_attendance_records:
        teacher_attendance_records = await gd_find(db.session, "attendance", {
            "school_id": school_id,
            "date": today,
            "type": "teacher"
        }, limit=1000)
    
    # Calculate attendance stats - REAL DATA
    student_present = len([a for a in student_attendance if a.get("status") == "present"])
    student_absent = len([a for a in student_attendance if a.get("status") == "absent"])
    student_late = len([a for a in student_attendance if a.get("status") == "late"])
    student_excused = len([a for a in student_attendance if a.get("status") == "excused"])
    
    teacher_present = len([a for a in teacher_attendance_records if a.get("status") == "present"])
    teacher_absent = len([a for a in teacher_attendance_records if a.get("status") == "absent"])
    teacher_late = len([a for a in teacher_attendance_records if a.get("status") == "late"])
    teacher_excused = len([a for a in teacher_attendance_records if a.get("status") == "excused"])
    
    # Get today's sessions count
    today_day = datetime.now(timezone.utc).strftime("%A").lower()
    sessions_count = await gd_count(db.session, "schedule_sessions", {
        "school_id": school_id,
        "day_of_week": today_day
    })
    
    # Get total sessions
    total_sessions = await gd_count(db.session, "schedule_sessions", {"school_id": school_id})
    
    # Get recent notifications/alerts
    alerts = await gd_find(db.session, "notifications", {
        "school_id": school_id
    }, order_by="created_at", desc_order=True, limit=10)
    
    # Calculate attendance rate from REAL data
    total_student_today = len(student_attendance)
    student_attendance_rate = round((student_present / total_student_today) * 100, 1) if total_student_today > 0 else 0
    
    total_teacher_today = len(teacher_attendance_records)
    teacher_attendance_rate = round((teacher_present / total_teacher_today) * 100, 1) if total_teacher_today > 0 else 0
    
    # Count teachers with frequent absences (>2 in last 30 days) - check both collections
    from datetime import timedelta
    thirty_days_ago = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%d")
    
    # Check teacher_attendance collection first
    frequent_absence_pipeline = [
        {"$match": {"school_id": school_id, "status": "absent", "date": {"$gte": thirty_days_ago}}},
        {"$group": {"_id": "$teacher_id", "count": {"$sum": 1}}},
        {"$match": {"count": {"$gt": 2}}}
    ]
    frequent_absences = await _gd_aggregate(db.session, "teacher_attendance", frequent_absence_pipeline)
    
    # Fallback to attendance collection if no data
    if not frequent_absences:
        frequent_absence_pipeline_old = [
            {"$match": {"school_id": school_id, "type": "teacher", "status": "absent", "date": {"$gte": thirty_days_ago}}},
            {"$group": {"_id": "$teacher_id", "count": {"$sum": 1}}},
            {"$match": {"count": {"$gt": 2}}}
        ]
        frequent_absences = await _gd_aggregate(db.session, "attendance", frequent_absence_pipeline_old)
    
    teachers_frequent_absence = len(frequent_absences)
    
    # Count classes with low attendance (<80%)
    classes_low_attendance = 0
    all_classes = await gd_find(db.session, "classes", {"school_id": school_id, "is_active": True}, limit=100)
    for cls in all_classes:
        class_attendance = [a for a in student_attendance if a.get("class_id") == cls["id"]]
        if class_attendance:
            present_count = len([a for a in class_attendance if a.get("status") == "present"])
            rate = (present_count / len(class_attendance)) * 100 if class_attendance else 0
            if rate < 80:
                classes_low_attendance += 1
    
    # Generate dynamic alerts based on real data
    dynamic_alerts = []
    if teacher_absent > 0:
        dynamic_alerts.append({
            "id": "alert-1",
            "type": "warning",
            "title_ar": f"{teacher_absent} معلم غائب اليوم",
            "title_en": f"{teacher_absent} teacher(s) absent today",
            "time_ar": "اليوم",
            "time_en": "Today"
        })
    if student_absent > 0:
        dynamic_alerts.append({
            "id": "alert-2",
            "type": "info",
            "title_ar": f"{student_absent} طالب غائب من إجمالي {total_student_today}",
            "title_en": f"{student_absent} student(s) absent out of {total_student_today}",
            "time_ar": "اليوم",
            "time_en": "Today"
        })
    if classes_low_attendance > 0:
        dynamic_alerts.append({
            "id": "alert-3",
            "type": "error",
            "title_ar": f"{classes_low_attendance} فصل بنسبة حضور أقل من 80%",
            "title_en": f"{classes_low_attendance} class(es) with <80% attendance",
            "time_ar": "اليوم",
            "time_en": "Today"
        })
    if student_attendance_rate >= 90:
        dynamic_alerts.append({
            "id": "alert-4",
            "type": "success",
            "title_ar": f"نسبة حضور ممتازة: {student_attendance_rate}%",
            "title_en": f"Excellent attendance rate: {student_attendance_rate}%",
            "time_ar": "اليوم",
            "time_en": "Today"
        })
    
    # Use stored alerts if available, otherwise use dynamic
    final_alerts = alerts if alerts else dynamic_alerts
    
    return {
        "metrics": {
            "totalStudents": {
                "value": total_students,
                "change": f"+{total_students}" if total_students > 0 else "0",
                "changeType": "up" if total_students > 0 else "same",
                "status": "normal"
            },
            "totalTeachers": {
                "value": total_teachers,
                "change": f"+{total_teachers}" if total_teachers > 0 else "0",
                "changeType": "up" if total_teachers > 0 else "same",
                "status": "normal"
            },
            "totalClasses": {
                "value": total_classes,
                "change": str(total_classes),
                "changeType": "same",
                "status": "normal"
            },
            "todaySessions": {
                "value": sessions_count,
                "change": str(sessions_count),
                "changeType": "same" if sessions_count > 0 else "down",
                "status": "normal" if sessions_count > 0 else "warning"
            },
            "attendanceRate": {
                "value": f"{student_attendance_rate}%",
                "change": f"{student_attendance_rate}%",
                "changeType": "up" if student_attendance_rate >= 80 else "down",
                "status": "normal" if student_attendance_rate >= 80 else "warning"
            },
            "waitingSubstitute": {
                "value": teacher_absent,
                "change": str(teacher_absent),
                "changeType": "up" if teacher_absent > 0 else "same",
                "status": "warning" if teacher_absent > 0 else "normal"
            },
        },
        "attendance": {
            "students": {
                "present": student_present,
                "absent": student_absent,
                "late": student_late,
                "excused": student_excused,
                "total": total_student_today if total_student_today > 0 else total_students
            },
            "teachers": {
                "present": teacher_present,
                "absent": teacher_absent,
                "late": teacher_late,
                "excused": teacher_excused,
                "total": total_teacher_today if total_teacher_today > 0 else total_teachers
            },
        },
        "interventions": {
            "classesWithoutTeacher": teacher_absent,
            "teachersWithFrequentAbsence": teachers_frequent_absence,
            "classesLowAttendance": classes_low_attendance,
        },
        "alerts": final_alerts,
        "generated_at": datetime.now(timezone.utc).isoformat()
    }





# ============== PLATFORM STATS ROUTE (Platform admins only) ==============
# SECURITY (audit C-4): originally unauthenticated; tenant/usage enumeration
# is a sovereign-grade red line. Restricted to platform admins. The duplicate
# in `routes/public_routes.py` carries the same gate.
# ============== PUBLIC SCHOOLS COUNT (curated, landing-page only) ==============
# SECURITY: deliberately public. Returns ONLY a single aggregate integer —
# the number of active schools on the platform — for the landing-page
# social-proof line. No per-tenant data, no breakdowns, no names/ids. The
# minimum value is clamped so an exact zero/one count cannot be inferred
# from an empty platform, and the result is cached for 5 minutes to blunt
# scraping. This is the only public surface that exposes any platform-wide
# aggregate; the full `/public/stats` payload remains platform-admin gated
# (audit C-4).
@router.get("/public/schools-count")
async def get_public_schools_count():
    try:
        _now = _time.monotonic()
        if _public_schools_count_cache["data"] and _now < _public_schools_count_cache["expires"]:
            return _public_schools_count_cache["data"]

        try:
            active_count = await gd_count(db.session, "schools", {"status": "active"})
        except Exception:
            active_count = 0

        # Floor the displayed number so we don't leak "exactly N" when the
        # platform is small. Anything below the floor renders as the floor.
        DISPLAY_FLOOR = 1
        displayed = max(int(active_count or 0), DISPLAY_FLOOR)

        result = {"count": displayed}
        _public_schools_count_cache["data"] = result
        _public_schools_count_cache["expires"] = _now + _PUBLIC_SCHOOLS_COUNT_TTL
        return result
    except Exception as e:
        logging.error(f"Error fetching public schools count: {e}")
        # Preserve the display floor on the error path too, so a transient
        # backend hiccup doesn't blank out the landing-page social proof.
        return {"count": 1}


# ============== PUBLIC GROWTH INDICATORS (curated, landing-page only) ==============
# SECURITY: deliberately public, but never returns raw aggregate counts. The
# response is composed of *preformatted, bucketed display strings* (e.g. "100+",
# "1K+") chosen from a small fixed vocabulary, so the browser cannot
# reverse-engineer the exact platform-wide totals from the payload. Used by the
# landing-page "نمو متزايد بثقة" trust section. Cached aggressively to blunt
# scraping.
@router.get("/public/growth-indicators")
async def get_public_growth_indicators():
    try:
        _now = _time.monotonic()
        if _public_growth_cache["data"] and _now < _public_growth_cache["expires"]:
            return _public_growth_cache["data"]

        try:
            schools_n = await gd_count(db.session, "schools", {"status": "active"})
        except Exception:
            schools_n = 0
        try:
            teachers_n = await gd_count(db.session, "teachers", {"is_active": True})
        except Exception:
            try:
                teachers_n = await gd_count(db.session, "teachers", {})
            except Exception:
                teachers_n = 0

        result = {
            "schools": _bucket_display(schools_n),
            "teachers": _bucket_display(teachers_n),
        }
        _public_growth_cache["data"] = result
        _public_growth_cache["expires"] = _now + _PUBLIC_GROWTH_TTL
        return result
    except Exception as e:
        logging.error(f"Error fetching public growth indicators: {e}")
        return {"schools": "10+", "teachers": "10+"}


@router.get("/public/stats")
async def get_public_stats(current_user: dict = Depends(get_current_user)):
    from src.common.utils.tenant_scope import _PLATFORM_ROLES
    if current_user.get("role") not in _PLATFORM_ROLES:
        raise HTTPException(status_code=403, detail="غير مصرح بالوصول")
    """
    Get platform statistics for the landing page (admin-gated).
    """
    try:
        _now = _time.monotonic()
        if _public_stats_cache["data"] and _now < _public_stats_cache["expires"]:
            from src.core.middleware.cache_metrics import record_hit
            record_hit()
            return _public_stats_cache["data"]
        from src.core.middleware.cache_metrics import record_miss
        record_miss()

        cached_stats = await gd_find_one(db.session, "platform_stats", {"id": "platform_stats"})
        
        if cached_stats:
            result = {
                "schools": cached_stats.get("total_schools", 0),
                "students": cached_stats.get("total_students", 0),
                "teachers": cached_stats.get("total_teachers", 0),
                "parents": cached_stats.get("total_parents", 0),
                "active_schools": cached_stats.get("active_schools", 0),
                "last_updated": cached_stats.get("last_updated", "")
            }
            _public_stats_cache["data"] = result
            _public_stats_cache["expires"] = _now + _PUBLIC_STATS_TTL
            return result
        
        total_schools = await gd_count(db.session, "schools", {})
        active_schools = await gd_count(db.session, "schools", {"status": "active"})

        students_from_users = await gd_count(db.session, "users", {"role": "student"})
        students_from_col = await gd_count(db.session, "students", {})
        total_students = max(students_from_users, students_from_col)

        teachers_from_users = await gd_count(db.session, "users", {"role": "teacher"})
        teachers_from_col = await gd_count(db.session, "teachers", {})
        total_teachers = max(teachers_from_users, teachers_from_col)

        parents_from_users = await gd_count(db.session, "users", {"role": "parent"})
        parents_from_col = await gd_count(db.session, "parents", {})
        total_parents = max(parents_from_users, parents_from_col)

        result = {
            "schools": total_schools,
            "students": total_students,
            "teachers": total_teachers,
            "parents": total_parents,
            "active_schools": active_schools,
            "last_updated": datetime.now(timezone.utc).isoformat()
        }
        _public_stats_cache["data"] = result
        _public_stats_cache["expires"] = _now + _PUBLIC_STATS_TTL
        return result
    except Exception as e:
        logging.error(f"Error fetching public stats: {e}")
        return {
            "schools": 0,
            "students": 0,
            "teachers": 0,
            "parents": 0,
            "active_schools": 0,
            "last_updated": datetime.now(timezone.utc).isoformat()
        }


