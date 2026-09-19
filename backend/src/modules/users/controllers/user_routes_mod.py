"""
NASSAQ Route Module: User management, profiles, sessions, avatars
Auto-consolidated during Phase 8 modularization.
"""
from fastapi import APIRouter, HTTPException, Depends, status, Header, Query, Body, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import Response
from starlette.responses import StreamingResponse
from pydantic import BaseModel, Field, ConfigDict, EmailStr, model_validator
from typing import List, Optional, Any, Dict
from datetime import datetime, timezone, timedelta
import uuid, os, logging, json, random, re, io, base64

from dependencies import (
    db, get_current_user, require_roles, UserRole, SchoolStatus,
    hash_password, verify_password, create_access_token,
    JWT_SECRET, JWT_ALGORITHM, ACCESS_TOKEN_EXPIRE, security, logger,
    audit_engine, AuditAction, AuditSeverity,
    smart_scheduling_engine, TimetableRunStatus, TimetableStatus,
    ConflictType, ConflictSeverity, PreValidationResult, GenerationResult,
    hakim_engine, reporting_engine, export_engine, session_engine,
    REPORT_TYPES, generate_student_qr_code,
    require_recent_mfa_403_if_independent_teacher,
    require_recent_mfa,
)

from shared_models import (
    UserResponse
)

from src.common.utils.avatar_image import normalize_image_field_or_400

from src.common.utils.avatar_serving import signed_image_url, is_internal_image_url

router = APIRouter()


async def _normalized_avatar(value: Optional[str]) -> Optional[str]:
    """Bound any client-supplied avatar before it is persisted.

    Every avatar write path routes through here. An oversized image stored on
    ``users.avatar_url`` is shipped inline by /auth/me and every other user
    serializer, so normalising at the write site is what keeps those payloads
    small — the client-side cropper cannot be trusted to do it (it only
    compresses above 500 kB, and it is bypassable anyway).
    """
    return await normalize_image_field_or_400(value)

# Task #201 — IT §5.7 step-up backfill: a single shared dependency
# instance so FastAPI can dedupe it across replays.
_REQUIRE_RECENT_MFA_403_IT = require_recent_mfa_403_if_independent_teacher()


# ---- School-teacher academic-record provisioning -----------------------
# A school teacher exists in BOTH `users` (login / role / tenant_id) and the
# authoritative `teachers` table (keyed by school_id) — the latter drives the
# Teachers page and every academic flow. Platform-Admin user edits only ever
# wrote the `users` row, so a teacher linked here never appeared under the
# school. These helpers reconcile the `teachers` record when a teacher is
# linked to a school: create-if-missing in the target school, and BLOCK moving
# a teacher who already has an academic record in a DIFFERENT school (academic
# data is never silently migrated).
async def _generate_school_teacher_id(school_id: str) -> str:
    school = await gd_find_one(db.session, "schools", {"id": school_id})
    name = (school or {}).get("name") or "SCH"
    code = "".join(ch for ch in name[:3] if ch.isalnum()).upper() or "SCH"
    year = datetime.now().strftime("%y")
    count = await gd_count(db.session, "teachers", {"school_id": school_id})
    candidate = f"TCH-{code}-{year}-{str(count + 1).zfill(4)}"
    if await gd_find_one(db.session, "teachers", {"id": candidate}):
        candidate = f"TCH-{code}-{year}-{uuid.uuid4().hex[:6].upper()}"
    return candidate


async def _ensure_school_teacher_record(user: dict, target_school_id: str, created_by: str) -> str:
    """Reconcile the authoritative `teachers` record for a school teacher.

    create-if-missing in ``target_school_id``; block (HTTP 400) when a
    non-deleted academic record already exists in a *different* school.
    Idempotent (and reactivating) when the record already lives in the target
    school.

    Returns the resolved ``teachers.id`` so the CALLER can write
    ``users.teacher_id`` as part of its own single user-row write. This helper
    touches ONLY the ``teachers`` table and never the ``users`` row — that keeps
    the write ordering in the caller's hands so a blocked move (which raises
    before the caller persists anything) cannot leave a partial commit.
    """
    uid = user.get("id")
    email = user.get("email")

    # Gather every academic record linked to this teacher (by explicit user_id
    # link first, else by canonical email). Soft-deleted history (deleted_at
    # set) is ignored — a genuinely removed record must not block re-linking.
    rows = []
    if uid:
        rows = await gd_find(db.session, "teachers", {"user_id": uid}) or []
    if not rows and email:
        rows = await gd_find(db.session, "teachers", {"email": email}) or []
    live = [r for r in rows if not r.get("deleted_at")]

    # Block: any live record in a different school — do not migrate it.
    other = next((r for r in live if r.get("school_id") and r.get("school_id") != target_school_id), None)
    if other:
        raise HTTPException(
            status_code=400,
            detail="لا يمكن نقل معلم لديه سجل أكاديمي في مدرسة أخرى. الرجاء إنشاء حساب المعلم في المدرسة المطلوبة.",
        )

    # Already in the target school — reactivate if needed and ensure the link.
    same = next((r for r in live if r.get("school_id") == target_school_id), None)
    if same:
        patch = {}
        if uid and not same.get("user_id"):
            patch["user_id"] = uid
        if same.get("is_active") is False:
            patch["is_active"] = True
        if patch:
            await gd_update_one(db.session, "teachers", {"id": same["id"]}, patch)
        if "is_active" in patch:
            # Reactivating an archived row changes the live teacher count, so
            # recompute the school's stored columns (Task #826).
            from engines.entity_counts import reconcile_school_counts
            await reconcile_school_counts(db.session, target_school_id)
        return same["id"]

    # A teacher's identity WITHIN a school is (national_id, school_id) — a UNIQUE
    # constraint (uq_teachers_national_id_school). A row for this national_id may
    # already exist in the target school under a different email/user_id, so it
    # escaped the user_id/email match above. A blind insert would violate that
    # constraint, so adopt the canonical row (link the user, fill a missing
    # user_id, reactivate a deactivated row) instead of minting a duplicate.
    # Soft-deleted rows are left archived — silent resurrection is an explicit
    # admin action, not an automatic side effect.
    national_id = user.get("national_id")
    if national_id:
        by_nid = await gd_find_one(db.session, "teachers", {"national_id": national_id, "school_id": target_school_id})
        if by_nid:
            # The constraint is a FULL unique constraint (it covers soft-deleted
            # rows too), so we must never fall through to INSERT once a row for
            # this (national_id, school_id) exists. Adopt ONLY a clean candidate:
            # live (not soft-deleted) and not already owned by a DIFFERENT user.
            # A soft-deleted row (silent resurrection) or one bound to another
            # user (dual-link corruption) is surfaced for manual review instead.
            owned_by_other = by_nid.get("user_id") and by_nid.get("user_id") != uid
            if by_nid.get("deleted_at") or owned_by_other:
                raise HTTPException(
                    status_code=400,
                    detail="يوجد سجل معلم بنفس رقم الهوية في هذه المدرسة يحتاج إلى مراجعة يدوية قبل الربط.",
                )
            patch = {}
            if uid and not by_nid.get("user_id"):
                patch["user_id"] = uid
            if by_nid.get("is_active") is False:
                patch["is_active"] = True
            if patch:
                await gd_update_one(db.session, "teachers", {"id": by_nid["id"]}, patch)
            if "is_active" in patch:
                # Reactivating an archived row changes the live teacher count,
                # so recompute the school's stored columns (Task #826).
                from engines.entity_counts import reconcile_school_counts
                await reconcile_school_counts(db.session, target_school_id)
            return by_nid["id"]

    # No academic record yet — provision a minimal one in the target school.
    teacher_id = await _generate_school_teacher_id(target_school_id)
    now = datetime.now(timezone.utc).isoformat()
    await gd_insert(db.session, "teachers", {
        "id": teacher_id,
        "teacher_id": teacher_id,
        "user_id": uid,
        "full_name": user.get("full_name") or user.get("full_name_ar") or email,
        "full_name_en": user.get("full_name_en"),
        "email": email,
        "phone": user.get("phone"),
        "national_id": user.get("national_id"),
        "school_id": target_school_id,
        "is_active": True,
        "created_by": created_by,
        "created_at": now,
        "updated_at": now,
    })
    # Recompute the school's stored counts from live rows (Task #826) so the
    # denormalized columns stay accurate instead of drifting.
    from engines.entity_counts import reconcile_school_counts
    await reconcile_school_counts(db.session, target_school_id)
    return teacher_id


# ============== USER MANAGEMENT ROUTES ==============
class PlatformUserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    role: str  # Will be validated against allowed roles
    phone: Optional[str] = None
    region: Optional[str] = None
    city: Optional[str] = None
    educational_department: Optional[str] = None
    school_name_ar: Optional[str] = None
    school_name_en: Optional[str] = None
    tenant_id: Optional[str] = None
    permissions: List[str] = []

class PlatformUserResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    email: str
    full_name: str
    role: str
    phone: Optional[str] = None
    region: Optional[str] = None
    city: Optional[str] = None
    educational_department: Optional[str] = None
    school_name_ar: Optional[str] = None
    school_name_en: Optional[str] = None
    permissions: List[str] = []
    is_active: bool = True
    must_change_password: bool = True
    created_at: str
    created_by: str

@router.post("/users/create", response_model=PlatformUserResponse)
async def create_platform_user(
    user_data: PlatformUserCreate,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN])),
    _mfa: dict = Depends(require_recent_mfa()),
):
    """
    Create a new platform user (admin or teacher) - Platform Admin only
    """
    allowed_roles = [r.value for r in UserRole]
    if user_data.role not in allowed_roles:
        raise HTTPException(status_code=400, detail="نوع الحساب غير مسموح به")

    # ---- Role scoping for school-context creation --------------------
    # A school context is signalled by a tenant_id (the selected school).
    # When a school is selected, only school-scoped roles may be created:
    # platform-level and Independent-Teacher roles must be rejected here
    # server-side so a tampered payload cannot cross the scope boundary
    # even if the frontend role filter is bypassed.
    SCHOOL_CREATABLE_ROLES = {
        UserRole.SCHOOL_PRINCIPAL.value,
        UserRole.SCHOOL_ADMIN.value,
        UserRole.SCHOOL_SUB_ADMIN.value,
        UserRole.TEACHER.value,
        UserRole.PARENT.value,
    }

    tenant_id = (user_data.tenant_id or "").strip() or None
    if tenant_id:
        # School context: only school roles, and the tenant must exist.
        if user_data.role not in SCHOOL_CREATABLE_ROLES:
            raise HTTPException(
                status_code=400,
                detail="هذا الدور غير مسموح به عند إنشاء حساب لمدرسة محددة",
            )
        school = await gd_find_one(db.session, "schools", {"id": tenant_id})
        if not school:
            raise HTTPException(status_code=404, detail="المدرسة غير موجودة")
        if (
            school.get("tenant_type") == "independent_teacher"
            or school.get("school_type") == "independent_teacher"
        ):
            raise HTTPException(
                status_code=400,
                detail="لا يمكن ربط المستخدم بمساحة عمل معلم مستقل",
            )
        # Derive school naming from the canonical record so it can never
        # drift from (or leak) another tenant's name.
        user_data.school_name_ar = school.get("name")
        user_data.school_name_en = school.get("name_en")
    
    # Normalize email to lowercase so create, uniqueness, login and reset all
    # agree on the same canonical form (mirrors /auth/register).
    user_data.email = (user_data.email or "").strip().lower()

    # Check if email exists (case-insensitive; legacy rows may be uppercase).
    from src.modules.auth.controllers.auth_routes_mod import _find_user_by_email_ci
    existing_email = await _find_user_by_email_ci(user_data.email)
    if existing_email:
        raise HTTPException(status_code=400, detail="البريد الإلكتروني مستخدم مسبقاً")
    
    # Check if phone exists (if provided)
    if user_data.phone:
        existing_phone = await gd_find_one(db.session, "users", {"phone": user_data.phone})
        if existing_phone:
            raise HTTPException(status_code=400, detail="رقم الهاتف مستخدم مسبقاً")
    
    # Create user
    user_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    
    new_user = {
        "id": user_id,
        "email": user_data.email,
        "password_hash": hash_password(user_data.password),
        "full_name": user_data.full_name,
        "role": user_data.role,
        "phone": user_data.phone,
        "region": user_data.region,
        "city": user_data.city,
        "educational_department": user_data.educational_department,
        "school_name_ar": user_data.school_name_ar,
        "school_name_en": user_data.school_name_en,
        "tenant_id": tenant_id,
        "permissions": user_data.permissions,
        "is_active": True,
        "must_change_password": True,  # Force password change on first login
        "preferred_language": "ar",
        "preferred_theme": "light",
        "created_at": now,
        "updated_at": now,
        "created_by": current_user["id"],
    }
    
    # Provision the authoritative academic record for school teachers so they
    # appear under the school immediately (mirrors the update path). Run BEFORE
    # the users insert: if this blocks (HTTP 400), the request fails closed with
    # no orphaned user row committed.
    if tenant_id and user_data.role == UserRole.TEACHER.value:
        new_user["teacher_id"] = await _ensure_school_teacher_record(new_user, tenant_id, current_user["id"])

    await gd_insert(db.session, "users", new_user)

    # Log this action using the new Audit Engine
    await audit_engine.log_data_change(
        action=AuditAction.USER_CREATED.value,
        performed_by=current_user["id"],
        entity_type="user",
        entity_id=user_id,
        tenant_id=current_user.get("tenant_id"),
        new_values={
            "role": user_data.role,
            "email": user_data.email,
            "full_name": user_data.full_name,
            "permissions_count": len(user_data.permissions)
        }
    )
    
    return PlatformUserResponse(
        id=user_id,
        email=user_data.email,
        full_name=user_data.full_name,
        role=user_data.role,
        phone=user_data.phone,
        region=user_data.region,
        city=user_data.city,
        educational_department=user_data.educational_department,
        school_name_ar=user_data.school_name_ar,
        school_name_en=user_data.school_name_en,
        permissions=user_data.permissions,
        is_active=True,
        must_change_password=True,
        created_at=now,
        created_by=current_user["id"]
    )

@router.get("/users/management-stats")
async def get_users_management_stats(
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.PLATFORM_SUB_ADMIN])),
):
    """Real-time stats for the Users Management page analysis cards.
    All values are direct DB counts — no mock data, no hardcoded values."""
    total_users = await gd_count(db.session, "users", {})
    active_users = await gd_count(db.session, "users", {"is_active": {"$ne": False}})
    suspended_users = await gd_count(db.session, "users", {"is_active": False})

    platform_admins = await gd_count(db.session, "users", {"role": {"$in": ["platform_admin", "platform_operations_manager"]}})
    school_admins = await gd_count(db.session, "users", {"role": {"$in": ["school_principal", "school_sub_admin", "school_manager"]}})
    teachers = await gd_count(db.session, "users", {"role": "teacher"})
    students = await gd_count(db.session, "users", {"role": "student"})
    parents = await gd_count(db.session, "users", {"role": "parent"})

    # Requests queue with several "still open" statuses (pending_review,
    # under_review, ...) — counting only the literal "pending" hid the
    # entire school-teacher approval backlog (stat showed 0).
    from engines.approval_engine import PENDING_STATUSES
    pending_requests = await gd_count(
        db.session, "registration_requests", {"status": {"$in": sorted(PENDING_STATUSES)}}
    )

    return {
        "total_users": total_users,
        "active_users": active_users,
        "suspended_users": suspended_users,
        "platform_admins": platform_admins,
        "school_admins": school_admins,
        "teachers": teachers,
        "students": students,
        "parents": parents,
        "pending_requests": pending_requests,
    }


@router.get("/users/platform-users")
async def get_platform_users(
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.PLATFORM_SUB_ADMIN])),
    skip: int = 0,
    limit: int = 100,
    role: Optional[str] = None,
    search: Optional[str] = None,
    status: Optional[str] = None,
    ai_status: Optional[str] = None,
    account_type: Optional[str] = None,
):
    """
    Get list of all platform users for admin management.
    Supports server-side filtering by role, status, AI, account_type and search.
    """
    query = {}
    
    if status and status != 'all':
        if status == 'active':
            query["is_active"] = {"$ne": False}
        elif status == 'suspended':
            query["is_active"] = False

    if ai_status and ai_status != 'all':
        if ai_status == 'enabled':
            query["ai_enabled"] = True
        elif ai_status == 'disabled':
            query["ai_enabled"] = {"$ne": True}

    role_conditions = []
    if role and role != 'all':
        role_conditions.append({"role": role})

    if account_type and account_type != 'all':
        if account_type == 'platform':
            role_conditions.append({"role": {"$regex": "^platform_", "$options": "i"}})
        elif account_type == 'school':
            role_conditions.append({"role": {"$in": ["school_principal", "school_admin", "school_sub_admin", "teacher", "student", "parent", "driver", "gatekeeper"]}})
        elif account_type == 'independent':
            role_conditions.append({"role": "independent_teacher"})
        elif account_type == 'testing':
            role_conditions.append({"role": {"$regex": "test", "$options": "i"}})

    if not role_conditions:
        pass
    elif len(role_conditions) == 1:
        query.update(role_conditions[0])
    else:
        query.setdefault("$and", []).extend(role_conditions)
    
    if search:
        import re as _re
        safe_search = _re.escape(search)
        search_conditions = [
            {"full_name": {"$regex": safe_search, "$options": "i"}},
            {"email": {"$regex": safe_search, "$options": "i"}},
            {"phone": {"$regex": safe_search, "$options": "i"}},
        ]
        if "$or" in query:
            query["$and"] = [{"$or": query.pop("$or")}, {"$or": search_conditions}]
        else:
            query["$or"] = search_conditions

    users = await gd_find(db.session, "users", query, offset=skip, limit=limit)

    # Task #1139 — never ship inline base64 avatars in list payloads; hand
    # out the signed cacheable URL instead (non-data: values pass through).
    for u in users:
        if u.get("avatar_url"):
            u["avatar_url"] = signed_image_url("avatar", u.get("id"), u.get("avatar_url"))

    total = await gd_count(db.session, "users", query)

    return {
        "users": users,
        "total": total,
        "skip": skip,
        "limit": limit
    }

@router.delete("/users/{user_id}")
async def delete_platform_user(
    user_id: str,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))
):
    """
    Soft delete a platform user
    """
    user = await gd_find_one(db.session, "users", {"id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="المستخدم غير موجود")
    
    # Cannot delete platform_admin
    if user.get("role") == "platform_admin":
        raise HTTPException(status_code=400, detail="لا يمكن حذف مدير المنصة")
    
    # Soft delete - just mark as inactive
    await gd_update_one(db.session, "users", {"id": user_id}, {
            "is_active": False,
            "deleted_at": datetime.now(timezone.utc).isoformat(),
            "deleted_by": current_user["id"]
        })
    
    # Audit log
    audit_log = {
        "id": str(uuid.uuid4()),
        "action": "user_deleted",
        "action_by": current_user["id"],
        "action_by_name": current_user.get("full_name", ""),
        "target_type": "user",
        "target_id": user_id,
        "target_name": user.get("full_name", ""),
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    await gd_insert(db.session, "audit_logs", audit_log)
    
    return {"message": "تم حذف المستخدم بنجاح"}




# ============== USERS MANAGEMENT ROUTES ==============
@router.get("/users", response_model=List[UserResponse])
async def get_users(
    role: Optional[str] = None,
    tenant_id: Optional[str] = None,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.SCHOOL_SUB_ADMIN]))
):
    query = {}
    
    if current_user["role"] in [UserRole.SCHOOL_PRINCIPAL.value, UserRole.SCHOOL_ADMIN.value, UserRole.SCHOOL_SUB_ADMIN.value]:
        query["tenant_id"] = current_user.get("tenant_id")
    elif tenant_id:
        query["tenant_id"] = tenant_id
    
    if role:
        query["role"] = role
    
    users = await gd_find(db.session, "users", query, limit=1000)
    # Task #1139 — never ship inline base64 avatars; mint signed URLs.
    for u in users:
        if u.get("avatar_url"):
            u["avatar_url"] = signed_image_url("avatar", u.get("id"), u.get("avatar_url"))
    return [UserResponse(**u) for u in users]


_SCHOOL_USER_ROLES = [
    "school_principal",
    "school_sub_admin",
    "teacher",
    "school_manager",
]


@router.get("/users/by-school")
async def get_users_by_school(
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.PLATFORM_SUB_ADMIN]))
):
    """Return school-level users grouped by tenant in a single query.

    Replaces the per-school N+1 fetch the User Management "School Users" tab
    used to perform. Filters server-side to the school-level roles so the
    client does not over-fetch and discard.
    """
    users = await gd_find(
        db.session,
        "users",
        {"role": {"$in": _SCHOOL_USER_ROLES}},
        limit=None,
    )

    grouped: Dict[str, List[dict]] = {}
    for u in users:
        tenant_id = u.get("tenant_id")
        if not tenant_id:
            continue
        if u.get("avatar_url"):
            u["avatar_url"] = signed_image_url("avatar", u.get("id"), u.get("avatar_url"))
        grouped.setdefault(tenant_id, []).append(
            UserResponse(**u).model_dump(mode="json")
        )

    return grouped


class UserStatusRequest(BaseModel):
    is_active: bool

@router.put("/users/{user_id}/status")
@router.patch("/users/{user_id}/status")
async def update_user_status(
    user_id: str,
    status_data: UserStatusRequest,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN]))
):
    user = await gd_find_one(db.session, "users", {"id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="المستخدم غير موجود")

    if current_user.get("role") != UserRole.PLATFORM_ADMIN.value:
        if user.get("tenant_id") != current_user.get("tenant_id"):
            raise HTTPException(status_code=403, detail="غير مصرح لك بتعديل بيانات هذا المستخدم")

    old_status = user.get("is_active", True)
    await gd_update_one(db.session, "users", {"id": user_id}, {
        "is_active": status_data.is_active,
        # Keep the existing status column authoritative for lifecycle callers.
        # Previously this API changed only is_active, making an administrative
        # suspension indistinguishable from teacher soft-deletion.
        "status": "active" if status_data.is_active else "suspended",
        "updated_at": datetime.now(timezone.utc).isoformat(),
    })

    audit_log = {
        "id": str(uuid.uuid4()),
        "action": "user_activated" if status_data.is_active else "user_suspended",
        "action_by": current_user["id"],
        "action_by_name": current_user.get("full_name", ""),
        "target_type": "user",
        "target_id": user_id,
        "target_name": user.get("full_name", ""),
        "details": {
            "old_status": "active" if old_status else "suspended",
            "new_status": "active" if status_data.is_active else "suspended",
        },
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    await gd_insert(db.session, "audit_logs", audit_log)

    return {"message": "تم تحديث حالة المستخدم"}




# ============== USER DETAILS & MANAGEMENT ROUTES ==============

async def _list_teacher_school_mismatches(
    *,
    school_id: Optional[str] = None,
    limit: Optional[int] = None,
    offset: int = 0,
) -> dict:
    """Core read of every stuck teacher transfer. Performs no writes.

    Shared by the listing endpoint and the bulk-resolution endpoint's
    resolve-all fallback. See ``get_teacher_school_mismatches`` for semantics.

    ``school_id`` scopes the scan to a single intended school
    (``users.tenant_id``) at the database level, so the report stays responsive
    as the teacher population grows. ``limit``/``offset`` paginate the resulting
    list (``total`` always reflects the full count within scope). When ``limit``
    is ``None`` the entire list is returned — the resolve-all fallback relies on
    this to act on every stuck teacher in one batch.
    """
    user_filter: Dict[str, Any] = {"role": UserRole.TEACHER.value}
    if school_id:
        user_filter["tenant_id"] = school_id
    teacher_users = await gd_find(db.session, "users", user_filter, limit=5000)
    teacher_users = [
        u for u in teacher_users
        if (u.get("tenant_id") or "").strip()
    ]
    if not teacher_users:
        return {"mismatches": [], "total": 0, "offset": offset, "limit": limit, "returned": 0}

    user_ids = [u["id"] for u in teacher_users if u.get("id")]
    emails = [u["email"] for u in teacher_users if u.get("email")]

    # Bulk-fetch every academic record linked to these teachers — by explicit
    # user_id link and by canonical email — to avoid per-user N+1 queries.
    teacher_rows: List[dict] = []
    if user_ids:
        teacher_rows += await gd_find(db.session, "teachers", {"user_id": {"$in": user_ids}}, limit=5000) or []
    if emails:
        teacher_rows += await gd_find(db.session, "teachers", {"email": {"$in": emails}}, limit=5000) or []

    # Index live (non-deleted) records by user_id and by email. Soft-deleted
    # (archived) records are indexed separately so we can warn the admin when a
    # resolution would RESTORE an old record in the intended school rather than
    # mint a brand-new one.
    rows_by_uid: Dict[str, List[dict]] = {}
    rows_by_email: Dict[str, List[dict]] = {}
    deleted_by_uid: Dict[str, List[dict]] = {}
    deleted_by_email: Dict[str, List[dict]] = {}
    seen_row_ids = set()
    for r in teacher_rows:
        rid = r.get("id")
        if rid in seen_row_ids:
            continue
        seen_row_ids.add(rid)
        if r.get("deleted_at"):
            if r.get("user_id"):
                deleted_by_uid.setdefault(r["user_id"], []).append(r)
            if r.get("email"):
                deleted_by_email.setdefault(r["email"], []).append(r)
            continue
        if r.get("user_id"):
            rows_by_uid.setdefault(r["user_id"], []).append(r)
        if r.get("email"):
            rows_by_email.setdefault(r["email"], []).append(r)

    mismatches = []
    needed_school_ids = set()
    for u in teacher_users:
        intended = (u.get("tenant_id") or "").strip()
        live = rows_by_uid.get(u.get("id")) or rows_by_email.get(u.get("email")) or []
        if not live:
            continue
        # A mismatch = the teacher has live academic record(s), but NONE of them
        # live in the intended school. (If a record already exists in the
        # intended school the teacher appears there normally and is not stuck.)
        in_intended = any(r.get("school_id") == intended for r in live)
        if in_intended:
            continue
        other_school_ids = sorted({r.get("school_id") for r in live if r.get("school_id")})
        if not other_school_ids:
            continue
        # Does an archived (soft-deleted) record already sit in the intended
        # school? If so, resolving will RESTORE that old record in place rather
        # than mint a fresh, disconnected one — surface it so the admin knows.
        archived = (deleted_by_uid.get(u.get("id")) or []) + (deleted_by_email.get(u.get("email")) or [])
        archived_in_intended = [r for r in archived if r.get("school_id") == intended]
        needed_school_ids.add(intended)
        needed_school_ids.update(other_school_ids)
        mismatches.append({
            "user": u,
            "intended_school_id": intended,
            "record_school_ids": other_school_ids,
            "teacher_records": live,
            "archived_record_ids_in_intended": [r.get("id") for r in archived_in_intended],
        })

    # Resolve school names in a single query.
    school_name_map: Dict[str, str] = {}
    school_id_list = [sid for sid in needed_school_ids if sid]
    if school_id_list:
        school_rows = await gd_find(db.session, "schools", {"id": {"$in": school_id_list}}, limit=5000) or []
        school_name_map = {
            s.get("id"): (s.get("name") or s.get("name_en") or s.get("id"))
            for s in school_rows
        }

    results = []
    for m in mismatches:
        u = m["user"]
        intended_id = m["intended_school_id"]
        record_schools = [
            {"id": sid, "name": school_name_map.get(sid) or sid}
            for sid in m["record_school_ids"]
        ]
        results.append({
            "user_id": u.get("id"),
            "full_name": u.get("full_name") or u.get("full_name_ar") or u.get("email"),
            "email": u.get("email"),
            "phone": u.get("phone"),
            "is_active": u.get("is_active", True),
            "intended_school": {
                "id": intended_id,
                "name": school_name_map.get(intended_id) or intended_id,
            },
            "record_schools": record_schools,
            "teacher_record_ids": [r.get("id") for r in m["teacher_records"]],
            # True → an archived record already exists in the intended school;
            # resolving will restore it in place instead of minting a new id.
            "will_restore_existing_record": bool(m.get("archived_record_ids_in_intended")),
            "archived_record_ids_in_intended": m.get("archived_record_ids_in_intended", []),
        })

    results.sort(key=lambda r: (r.get("full_name") or "").lower())

    total = len(results)
    if limit is None:
        page = results[offset:] if offset else results
    else:
        page = results[offset:offset + limit]
    return {
        "mismatches": page,
        "total": total,
        "offset": offset,
        "limit": limit,
        "returned": len(page),
    }


@router.get("/users/teacher-school-mismatches")
async def get_teacher_school_mismatches(
    school_id: Optional[str] = Query(
        None,
        description="Scope the scan to a single intended school (users.tenant_id).",
    ),
    limit: int = Query(
        100, ge=1, le=500,
        description="Max mismatches to return in this page.",
    ),
    offset: int = Query(0, ge=0, description="Page offset into the result list."),
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.PLATFORM_SUB_ADMIN]))
):
    """List teacher users whose intended school differs from their academic record.

    Surfaces the teachers that ``_ensure_school_teacher_record`` intentionally
    BLOCKS from being moved: a teacher user whose ``users.tenant_id`` points to
    one school while their live (non-deleted) ``teachers`` record lives in a
    DIFFERENT school. These users never appear under their intended school's
    Teachers page, with no prior visibility for admins. Each entry exposes both
    the intended school (from ``users.tenant_id``) and the school(s) where the
    live academic record actually exists so an admin can resolve the conflict
    (e.g. deactivate the old record, then reassign).

    Pass ``school_id`` to scope the scan to a single intended school
    (``users.tenant_id``) at the database level, and ``limit``/``offset`` to page
    through the results — both keep the report responsive as the teacher
    population grows. ``total`` always reflects the full count within scope.

    Platform-admin only. Read-only — performs no writes.
    """
    return await _list_teacher_school_mismatches(
        school_id=school_id, limit=limit, offset=offset
    )


async def _do_resolve_teacher_mismatch(user_id: str, current_user: dict) -> dict:
    """Core one-click resolution of a single stuck teacher transfer.

    Shared by the per-teacher endpoint and the bulk endpoint. Raises
    ``HTTPException`` on business/validation problems (so the single-teacher
    route surfaces them unchanged); the bulk route catches these to classify a
    case as skipped vs. failed. Audit-logs each successful resolution.
    """
    user = await gd_find_one(db.session, "users", {"id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="المستخدم غير موجود")

    if user.get("role") != UserRole.TEACHER.value:
        raise HTTPException(status_code=400, detail="هذا الإجراء مخصص لحسابات المعلمين فقط")

    intended = (user.get("tenant_id") or "").strip()
    if not intended:
        raise HTTPException(status_code=400, detail="المعلم غير مرتبط بمدرسة مطلوبة")

    # Gather every academic record linked to this teacher — by explicit user_id
    # link first, else by canonical email (mirrors _ensure_school_teacher_record).
    uid = user.get("id")
    email = user.get("email")
    rows = []
    if uid:
        rows = await gd_find(db.session, "teachers", {"user_id": uid}) or []
    if not rows and email:
        rows = await gd_find(db.session, "teachers", {"email": email}) or []
    live = [r for r in rows if not r.get("deleted_at")]

    if not live:
        raise HTTPException(status_code=400, detail="لا يوجد سجل أكاديمي نشط لهذا المعلم")

    # No conflict if a live record already lives in the intended school.
    if any(r.get("school_id") == intended for r in live):
        raise HTTPException(status_code=400, detail="لا يوجد تعارض — سجل المعلم موجود بالفعل في المدرسة المطلوبة")

    other_records = [r for r in live if r.get("school_id") and r.get("school_id") != intended]
    if not other_records:
        raise HTTPException(status_code=400, detail="لا يوجد تعارض لحلّه")

    # A soft-deleted (archived) academic record may already exist in the
    # intended school — e.g. the teacher was previously removed from it. We
    # detect it BEFORE retiring anything so step 2 can restore that old record
    # in place instead of minting a brand-new, disconnected duplicate (which
    # would orphan the record's prior schedules/history).
    archived_intended = [
        r for r in rows
        if r.get("deleted_at") and r.get("school_id") == intended
    ]

    now = datetime.now(timezone.utc).isoformat()

    # Step 1 — retire the stuck record(s) in the other school(s) in place.
    retired = []
    for r in other_records:
        await gd_update_one(db.session, "teachers", {"id": r["id"]}, {
            "is_active": False,
            "deleted_at": now,
            "deleted_by": current_user["id"],
            "updated_at": now,
        })
        retired.append({
            "teacher_record_id": r.get("id"),
            "school_id": r.get("school_id"),
        })

    # Step 2 — re-establish the record in the intended school.
    #   * If an archived record already exists there, RESTORE it in place
    #     (clear deleted_at, reactivate, re-link the user) so the teacher's old
    #     academic record — and everything attached to it — comes back rather
    #     than a fresh, disconnected id.
    #   * Otherwise provision a new one via the shared helper. The foreign
    #     records now carry deleted_at, so the helper no longer blocks the move.
    restored_existing_record = False
    if archived_intended:
        restore = sorted(
            archived_intended,
            key=lambda r: r.get("deleted_at") or "",
            reverse=True,
        )[0]
        restore_patch = {
            "is_active": True,
            "deleted_at": None,
            "deleted_by": None,
            "updated_at": now,
        }
        if uid and not restore.get("user_id"):
            restore_patch["user_id"] = uid
        await gd_update_one(db.session, "teachers", {"id": restore["id"]}, restore_patch)
        resolved_teacher_id = restore["id"]
        restored_existing_record = True
    else:
        resolved_teacher_id = await _ensure_school_teacher_record(user, intended, current_user["id"])

    user_patch = {"updated_at": now}
    if resolved_teacher_id and user.get("teacher_id") != resolved_teacher_id:
        user_patch["teacher_id"] = resolved_teacher_id
    await gd_update_one(db.session, "users", {"id": user_id}, user_patch)

    # Recompute stored counts for every school whose live teacher set changed:
    # the school(s) we retired the record from, plus the intended school where
    # it was restored/created (Task #826).
    from engines.entity_counts import reconcile_school_counts
    _affected = {intended} | {r.get("school_id") for r in retired if r.get("school_id")}
    for _sid in _affected:
        await reconcile_school_counts(db.session, _sid)

    await audit_engine.log(
        action="teacher_school_mismatch_resolved",
        performed_by=current_user["id"],
        actor_name=current_user.get("full_name"),
        actor_role=current_user.get("role"),
        actor_email=current_user.get("email"),
        tenant_id=intended,
        entity_type="teacher",
        entity_id=resolved_teacher_id,
        details={
            "user_id": user_id,
            "user_full_name": user.get("full_name") or user.get("full_name_ar") or email,
            "intended_school_id": intended,
            "resolved_teacher_id": resolved_teacher_id,
            "retired_records": retired,
            "restored_existing_record": restored_existing_record,
        },
    )

    return {
        "message": (
            "تم حل تعارض المعلم واستعادة سجله السابق في المدرسة المطلوبة"
            if restored_existing_record
            else "تم حل تعارض المعلم وإنشاء سجل جديد له في المدرسة المطلوبة"
        ),
        "user_id": user_id,
        "resolved_teacher_id": resolved_teacher_id,
        "retired_records": retired,
        # True  → an archived record already in the intended school was restored
        #         in place. False → a brand-new record was minted there.
        "restored_existing_record": restored_existing_record,
    }


@router.post("/users/{user_id}/resolve-teacher-mismatch")
async def resolve_teacher_school_mismatch(
    user_id: str,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN])),
    _mfa: dict = Depends(require_recent_mfa()),
):
    """One-click resolution of a stuck teacher transfer.

    Surfaced by ``GET /users/teacher-school-mismatches``: a teacher user whose
    ``users.tenant_id`` points to one school while their live academic
    ``teachers`` record is stuck in a DIFFERENT school. Platform-admin only,
    requires fresh MFA, and is audit-logged. See ``_do_resolve_teacher_mismatch``
    for the resolution steps.

    Product behavior when the intended school already holds an ARCHIVED
    (soft-deleted) record for this teacher: that old record is RESTORED in place
    (reactivated, ``deleted_at`` cleared, re-linked) rather than a brand-new,
    disconnected record being minted — so the teacher's prior academic record
    and everything attached to it comes back. The response (and listing) carry
    ``restored_existing_record`` / ``will_restore_existing_record`` so the admin
    knows which happened.
    """
    return await _do_resolve_teacher_mismatch(user_id, current_user)


class BulkResolveTeacherMismatchRequest(BaseModel):
    user_ids: Optional[List[str]] = None


@router.post("/users/resolve-teacher-mismatches-bulk")
async def resolve_teacher_school_mismatches_bulk(
    payload: BulkResolveTeacherMismatchRequest = Body(default=BulkResolveTeacherMismatchRequest()),
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN])),
    _mfa: dict = Depends(require_recent_mfa()),
):
    """Bulk one-click resolution of every stuck teacher transfer.

    Resolves the teacher-school mismatches listed in ``user_ids`` (the cases the
    admin currently sees). When ``user_ids`` is omitted, every currently-stuck
    teacher is resolved. Reuses the per-teacher core, so each successful
    resolution is audit-logged individually. Platform-admin only, requires fresh
    MFA (a single step-up covers the whole batch).

    Partial failures never abort the batch: each case is classified as resolved,
    skipped (no conflict left to fix — e.g. already resolved), or failed, and the
    per-case outcome is returned so the UI can report succeeded vs. skipped vs.
    failed before refreshing the list.
    """
    user_ids = payload.user_ids
    if user_ids is None:
        # Resolve everything currently stuck.
        listing = await _list_teacher_school_mismatches()
        user_ids = [m["user_id"] for m in listing.get("mismatches", [])]

    # De-dupe while preserving order.
    seen = set()
    ordered_ids = []
    for uid in user_ids or []:
        if uid and uid not in seen:
            seen.add(uid)
            ordered_ids.append(uid)

    resolved, skipped, failed = [], [], []
    for uid in ordered_ids:
        try:
            result = await _do_resolve_teacher_mismatch(uid, current_user)
            resolved.append({"user_id": uid, "resolved_teacher_id": result.get("resolved_teacher_id")})
        except HTTPException as e:
            # 400 "no conflict left" cases are already-resolved → skip, not fail.
            detail = e.detail if isinstance(e.detail, str) else "تعذّر حل التعارض"
            if e.status_code == 400 and "لا يوجد تعارض" in detail:
                skipped.append({"user_id": uid, "reason": detail})
            else:
                failed.append({"user_id": uid, "reason": detail})
        except Exception as exc:  # noqa: BLE001
            logger.warning("Bulk teacher-mismatch resolution failed for %s: %s", uid, exc)
            failed.append({"user_id": uid, "reason": "خطأ غير متوقع أثناء حل التعارض"})

    return {
        "message": (
            f"تم حل {len(resolved)} تعارض"
            + (f"، تم تخطي {len(skipped)}" if skipped else "")
            + (f"، فشل {len(failed)}" if failed else "")
        ),
        "total": len(ordered_ids),
        "resolved_count": len(resolved),
        "skipped_count": len(skipped),
        "failed_count": len(failed),
        "resolved": resolved,
        "skipped": skipped,
        "failed": failed,
    }


@router.get("/users/{user_id}")
async def get_user_by_id(
    user_id: str,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))
):
    """Get detailed user information by ID"""
    user = await gd_find_one(db.session, "users", {"id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="المستخدم غير موجود")
    
    # Get creator name if exists
    if user.get("created_by"):
        creator = await gd_find_one(db.session, "users", {"id": user["created_by"]})
        user["created_by_name"] = creator.get("full_name") if creator else None
    
    return user

class UserUpdateRequest(BaseModel):
    full_name_ar: Optional[str] = None
    full_name_en: Optional[str] = None
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    region: Optional[str] = None
    city: Optional[str] = None
    educational_department: Optional[str] = None
    avatar_url: Optional[str] = None
    role: Optional[str] = None
    tenant_id: Optional[str] = None
    school_name: Optional[str] = None

@router.put("/users/{user_id}")
@router.patch("/users/{user_id}")
async def update_user(
    user_id: str,
    user_data: UserUpdateRequest,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN])),
    _mfa: dict = Depends(require_recent_mfa()),
):
    """Update user information"""
    user = await gd_find_one(db.session, "users", {"id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="المستخدم غير موجود")
    
    updates = {"updated_at": datetime.now(timezone.utc).isoformat()}
    
    if user_data.full_name_ar:
        updates["full_name_ar"] = user_data.full_name_ar
        updates["full_name"] = user_data.full_name_ar
    if user_data.full_name_en:
        updates["full_name_en"] = user_data.full_name_en
    if user_data.full_name:
        updates["full_name"] = user_data.full_name
    if user_data.email:
        # Check email uniqueness
        existing = await gd_find_one(db.session, "users", {"email": user_data.email, "id": {"$ne": user_id}})
        if existing:
            raise HTTPException(status_code=400, detail="البريد الإلكتروني مستخدم مسبقاً")
        updates["email"] = user_data.email
    if user_data.phone:
        updates["phone"] = user_data.phone
    if user_data.region:
        updates["region"] = user_data.region
    if user_data.city:
        updates["city"] = user_data.city
    if user_data.educational_department:
        updates["educational_department"] = user_data.educational_department
    if user_data.avatar_url and not is_internal_image_url(user_data.avatar_url):
        updates["avatar_url"] = await _normalized_avatar(user_data.avatar_url)
    if user_data.role:
        valid_roles = [r.value for r in UserRole]
        if user_data.role not in valid_roles:
            raise HTTPException(status_code=400, detail=f"الدور غير صالح. الأدوار المسموحة: {', '.join(valid_roles)}")
        updates["role"] = user_data.role

    # --- Tenant (school) linking with server-side validation ----------
    # A tenant_id must reference a real production school — never an
    # Independent-Teacher workspace — and the effective role must be
    # school-scoped. school_name is always derived from the canonical
    # school record (never trusted from the client). Clearing tenant_id
    # also clears school_name so no stale cross-tenant name remains.
    SCHOOL_LINKABLE_ROLES = {
        UserRole.SCHOOL_PRINCIPAL.value,
        UserRole.SCHOOL_ADMIN.value,
        UserRole.SCHOOL_SUB_ADMIN.value,
        UserRole.TEACHER.value,
        UserRole.PARENT.value,
    }
    if user_data.tenant_id is not None:
        new_tenant_id = (user_data.tenant_id or "").strip() or None
        if new_tenant_id:
            effective_role = updates.get("role") or user.get("role")
            if effective_role not in SCHOOL_LINKABLE_ROLES:
                raise HTTPException(
                    status_code=400,
                    detail="هذا الدور لا يمكن ربطه بمدرسة",
                )
            school = await gd_find_one(db.session, "schools", {"id": new_tenant_id})
            if not school:
                raise HTTPException(status_code=404, detail="المدرسة غير موجودة")
            if (
                school.get("tenant_type") == "independent_teacher"
                or school.get("school_type") == "independent_teacher"
            ):
                raise HTTPException(
                    status_code=400,
                    detail="لا يمكن ربط المستخدم بمساحة عمل معلم مستقل",
                )
            updates["tenant_id"] = new_tenant_id
            # Derive the school name from the canonical record so it can
            # never drift from (or leak) another tenant's name. (`users` has
            # school_name_ar/en — there is NO `school_name` column, so writing
            # it was a silent no-op.)
            updates["school_name_ar"] = school.get("name")
            updates["school_name_en"] = school.get("name_en")
            # Reconcile the authoritative academic record so a school teacher
            # actually appears under the school. Runs BEFORE the users write so
            # a blocked cross-school move fails closed (no false success); the
            # resolved teacher_id is folded into the single users update below.
            if effective_role == UserRole.TEACHER.value:
                _resolved_teacher_id = await _ensure_school_teacher_record(user, new_tenant_id, current_user["id"])
                if _resolved_teacher_id and user.get("teacher_id") != _resolved_teacher_id:
                    updates["teacher_id"] = _resolved_teacher_id
        else:
            # Clearing the link — drop any stale school name with it.
            updates["tenant_id"] = None
            updates["school_name_ar"] = None
            updates["school_name_en"] = None

    # When role or tenant_id changes, bump last_password_change to invalidate
    # all outstanding tokens — including switched/impersonation ones.
    # Both get_current_user() and decode_token_for_ws() reject tokens whose
    # iat < last_password_change, so this ensures entitlement changes take
    # effect immediately even for already-issued switched tokens.
    _role_or_tenant_changed = (
        ("role" in updates and updates["role"] != user.get("role"))
        or ("tenant_id" in updates and updates["tenant_id"] != user.get("tenant_id"))
    )
    if _role_or_tenant_changed:
        updates["last_password_change"] = datetime.now(timezone.utc).isoformat()

    await gd_update_one(db.session, "users", {"id": user_id}, updates)

    # If the user is a parent, synchronize the parents table
    effective_role = updates.get("role") or user.get("role")
    if effective_role == UserRole.PARENT.value or user.get("parent_id"):
        parent_sync = {}
        if "full_name" in updates:
            parent_sync["full_name"] = updates["full_name"]
        if "phone" in updates:
            parent_sync["phone"] = updates["phone"]
        if "email" in updates:
            parent_sync["email"] = updates["email"]
        if parent_sync:
            parent_sync["updated_at"] = datetime.now(timezone.utc).isoformat()
            if user.get("parent_id"):
                await gd_update_one(db.session, "parents", {"id": user["parent_id"]}, parent_sync)
            elif user.get("email"):
                await gd_update_one(db.session, "parents", {"email": user["email"]}, parent_sync)
    
    field_changes = {}
    for field, new_val in updates.items():
        if field == "updated_at":
            continue
        old_val = user.get(field)
        if old_val != new_val:
            field_changes[field] = {"old": old_val, "new": new_val}

    audit_log = {
        "id": str(uuid.uuid4()),
        "action": "user_updated",
        "action_by": current_user["id"],
        "action_by_name": current_user.get("full_name", ""),
        "target_type": "user",
        "target_id": user_id,
        "target_name": user.get("full_name", ""),
        "changes": field_changes,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    if "role" in field_changes:
        audit_log["action"] = "user_role_changed"
        audit_log["old_role"] = field_changes["role"]["old"]
        audit_log["new_role"] = field_changes["role"]["new"]
    await gd_insert(db.session, "audit_logs", audit_log)
    
    return {"message": "تم تحديث البيانات بنجاح"}

class PermissionsUpdateRequest(BaseModel):
    permissions: List[str]

@router.put("/users/{user_id}/permissions")
async def update_user_permissions(
    user_id: str,
    data: PermissionsUpdateRequest,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))
):
    """Update user permissions"""
    user = await gd_find_one(db.session, "users", {"id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="المستخدم غير موجود")
    
    old_permissions = user.get("permissions", [])
    
    await gd_update_one(db.session, "users", {"id": user_id}, {
            "permissions": data.permissions,
            "updated_at": datetime.now(timezone.utc).isoformat()
        })
    
    # Audit log
    audit_log = {
        "id": str(uuid.uuid4()),
        "action": "permissions_updated",
        "action_by": current_user["id"],
        "action_by_name": current_user.get("full_name", ""),
        "target_type": "user",
        "target_id": user_id,
        "target_name": user.get("full_name", ""),
        "details": {
            "old_permissions": old_permissions,
            "new_permissions": data.permissions,
            "added": [p for p in data.permissions if p not in old_permissions],
            "removed": [p for p in old_permissions if p not in data.permissions]
        },
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    await gd_insert(db.session, "audit_logs", audit_log)
    
    return {"message": "تم تحديث الصلاحيات بنجاح"}

class PasswordResetRequest(BaseModel):
    new_password: str


_ROLES_PROTECTED_FROM_SCHOOL_ADMIN = {
    "platform_admin",
    "platform_security_officer",
    "school_principal",
    "school_admin",
}


def _assert_role_ceiling(caller_role: str, target_role: str) -> None:
    """Raise 403 if the caller's role does not outrank the target's role.

    school_admin may only act on users whose role is strictly below theirs in
    the school hierarchy (teachers, students, parents, school_sub_admin). They
    must not be able to reset or suspend a school_principal (or any
    platform-level account), which would be a direct privilege-escalation path.
    """
    if caller_role == UserRole.PLATFORM_ADMIN.value:
        return
    if caller_role == UserRole.SCHOOL_PRINCIPAL.value:
        if target_role in {"platform_admin", "platform_security_officer"}:
            raise HTTPException(status_code=403, detail="غير مصرح لك بتعديل بيانات هذا المستخدم")
        return
    if caller_role == UserRole.SCHOOL_ADMIN.value:
        if target_role in _ROLES_PROTECTED_FROM_SCHOOL_ADMIN:
            raise HTTPException(status_code=403, detail="غير مصرح لك بتعديل بيانات هذا المستخدم")
        return
    raise HTTPException(status_code=403, detail="غير مصرح لك بتعديل بيانات هذا المستخدم")


@router.post("/users/{user_id}/reset-password")
async def reset_user_password(
    user_id: str,
    data: PasswordResetRequest,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN])),
    _mfa: dict = Depends(require_recent_mfa()),
):
    """Reset user password (admin only)"""
    user = await gd_find_one(db.session, "users", {"id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="المستخدم غير موجود")

    if current_user.get("role") != UserRole.PLATFORM_ADMIN.value:
        if user.get("tenant_id") != current_user.get("tenant_id"):
            raise HTTPException(status_code=403, detail="غير مصرح لك بتعديل بيانات هذا المستخدم")

    _assert_role_ceiling(current_user.get("role", ""), user.get("role", ""))

    now_iso = datetime.now(timezone.utc).isoformat()
    await gd_update_one(db.session, "users", {"id": user_id}, {
            "password_hash": hash_password(data.new_password),
            "must_change_password": True,
            "password_reset_at": now_iso,
            "password_reset_by": current_user["id"],
            "last_password_change": now_iso,
            "updated_at": now_iso,
        })
    
    # Audit log
    audit_log = {
        "id": str(uuid.uuid4()),
        "action": "password_reset",
        "action_by": current_user["id"],
        "action_by_name": current_user.get("full_name", ""),
        "target_type": "user",
        "target_id": user_id,
        "target_name": user.get("full_name", ""),
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    await gd_insert(db.session, "audit_logs", audit_log)

    try:
        from engines.email_service import send_admin_password_reset_notification
        from services.email_client import send_email_off_loop
        user_email = user.get("email", "")
        if user_email:
            await send_email_off_loop(
                send_admin_password_reset_notification,
                to_email=user_email,
                user_name=user.get("full_name", ""),
                admin_name=current_user.get("full_name", "المدير"),
            )
    except Exception as e:
        logger.warning(f"Failed to send admin reset notification email: {e}")
    
    return {"message": "تم إعادة تعيين كلمة المرور بنجاح"}

@router.post("/users/{user_id}/suspend")
async def suspend_user(
    user_id: str,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN]))
):
    """Toggle user suspension status"""
    user = await gd_find_one(db.session, "users", {"id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="المستخدم غير موجود")

    if current_user.get("role") != UserRole.PLATFORM_ADMIN.value:
        if user.get("tenant_id") != current_user.get("tenant_id"):
            raise HTTPException(status_code=403, detail="غير مصرح لك بتعديل بيانات هذا المستخدم")

    _assert_role_ceiling(current_user.get("role", ""), user.get("role", ""))

    # Cannot suspend platform_admin
    if user.get("role") == "platform_admin":
        raise HTTPException(status_code=400, detail="لا يمكن تعليق حساب مدير المنصة")
    
    new_status = not user.get("is_active", True)
    
    await gd_update_one(db.session, "users", {"id": user_id}, {
            "is_active": new_status,
            "suspended_at": datetime.now(timezone.utc).isoformat() if not new_status else None,
            "suspended_by": current_user["id"] if not new_status else None,
            "updated_at": datetime.now(timezone.utc).isoformat()
        })
    
    # Audit log
    audit_log = {
        "id": str(uuid.uuid4()),
        "action": "user_suspended" if not new_status else "user_activated",
        "action_by": current_user["id"],
        "action_by_name": current_user.get("full_name", ""),
        "target_type": "user",
        "target_id": user_id,
        "target_name": user.get("full_name", ""),
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    await gd_insert(db.session, "audit_logs", audit_log)
    
    return {
        "message": "تم تعليق الحساب بنجاح" if not new_status else "تم تفعيل الحساب بنجاح",
        "is_active": new_status
    }

class NotificationRequest(BaseModel):
    title: str
    message: str
    type: str = "system"

@router.post("/users/{user_id}/notify")
async def send_user_notification(
    user_id: str,
    data: NotificationRequest,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))
):
    """Send notification to a user"""
    user = await gd_find_one(db.session, "users", {"id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="المستخدم غير موجود")
    
    notification = {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "title": data.title,
        "message": data.message,
        "type": data.type,
        "sent_by": current_user["id"],
        "sent_by_name": current_user.get("full_name", ""),
        "is_read": False,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await gd_insert(db.session, "notifications", notification)
    
    return {"message": "تم إرسال الإشعار بنجاح", "notification_id": notification["id"]}

import base64
from engines.sql_utils import gd_find, gd_find_one, gd_insert, gd_insert_many, gd_update_one, gd_update_many, gd_count, gd_delete_one, gd_delete_many, gd_distinct, gd_upsert, _gd_aggregate

class ImageUploadRequest(BaseModel):
    image_data: str  # Base64 encoded image

@router.post("/users/{user_id}/upload-image")
async def upload_user_image(
    user_id: str,
    data: ImageUploadRequest,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))
):
    """Upload user profile image (base64)"""
    MAX_B64_LENGTH = 2 * 1024 * 1024
    if len(data.image_data) > MAX_B64_LENGTH:
        raise HTTPException(status_code=413, detail="حجم الصورة كبير جداً (الحد الأقصى 2MB) | Image too large (max 2MB)")

    allowed_prefixes = ("data:image/jpeg;base64,", "data:image/png;base64,", "data:image/webp;base64,")
    if not data.image_data.startswith(allowed_prefixes):
        raise HTTPException(status_code=400, detail="صيغة الصورة غير مدعومة (فقط JPEG, PNG, WEBP) | Unsupported image format (only JPEG, PNG, WEBP)")

    try:
        b64_content = data.image_data.split(",", 1)[1]
        base64.b64decode(b64_content, validate=True)
    except Exception:
        raise HTTPException(status_code=400, detail="بيانات الصورة غير صالحة | Invalid image data")

    user = await gd_find_one(db.session, "users", {"id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="المستخدم غير موجود")
    
    normalized = await _normalized_avatar(data.image_data)

    await gd_update_one(db.session, "users", {"id": user_id}, {
            "avatar_url": normalized,
            "updated_at": datetime.now(timezone.utc).isoformat()
        })
    
    return {"message": "تم رفع الصورة بنجاح", "avatar_url": signed_image_url("avatar", user_id, normalized)}

@router.get("/users/{user_id}/activity")
async def get_user_activity(
    user_id: str,
    limit: int = 50,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))
):
    """Get user activity logs"""
    user = await gd_find_one(db.session, "users", {"id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="المستخدم غير موجود")
    
    # Get activity from audit logs
    activities = await gd_find(db.session, "audit_logs", {"$or": [
            {"action_by": user_id},
            {"target_id": user_id}
        ]}, order_by="timestamp", desc_order=True, limit=limit)
    
    return {"activities": activities, "total": len(activities)}





# ============== USER PROFILE APIs ==============
class UserProfileUpdate(BaseModel):
    full_name: Optional[str] = None
    full_name_en: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    avatar_url: Optional[str] = None

class UserPreferencesUpdate(BaseModel):
    language: Optional[str] = None
    theme: Optional[str] = None
    time_format: Optional[str] = None
    date_format: Optional[str] = None
    first_day_of_week: Optional[str] = None
    # Task #200 §5.8 — Independent-teacher communication preferences
    # (default channel + quiet hours). Persisted as a JSONB blob inside
    # the existing `users.notification_preferences` column under the key
    # `it_communication`. No new persistence layer is introduced.
    it_communication: Optional[Dict[str, Any]] = None

class UserNotificationSettings(BaseModel):
    email_notifications: Optional[bool] = None
    sms_notifications: Optional[bool] = None
    push_notifications: Optional[bool] = None
    attendance_alerts: Optional[bool] = None
    grade_alerts: Optional[bool] = None
    behavior_alerts: Optional[bool] = None
    announcement_alerts: Optional[bool] = None
    weekly_digest: Optional[bool] = None

@router.put("/users/me", response_model=UserResponse)
async def update_current_user_profile(
    data: UserProfileUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Update current user's profile"""
    update_data = {"updated_at": datetime.now(timezone.utc).isoformat()}
    
    if data.full_name is not None:
        from engines.name_validation import validate_personal_name
        valid, err_msg = validate_personal_name(data.full_name)
        if not valid:
            raise HTTPException(status_code=400, detail=err_msg)
        update_data["full_name"] = data.full_name
    if data.full_name_en is not None:
        update_data["full_name_en"] = data.full_name_en
    if data.email is not None:
        # Check if email is already used by another user
        existing = await gd_find_one(db.session, "users", {"email": data.email, "id": {"$ne": current_user["id"]}})
        if existing:
            raise HTTPException(status_code=400, detail="البريد الإلكتروني مستخدم مسبقاً")
        update_data["email"] = data.email
    if data.phone is not None:
        # Check if phone is already used by another user
        existing = await gd_find_one(db.session, "users", {"phone": data.phone, "id": {"$ne": current_user["id"]}})
        if existing:
            raise HTTPException(status_code=400, detail="رقم الهاتف مستخدم مسبقاً")
        update_data["phone"] = data.phone
    if data.avatar_url is not None and not is_internal_image_url(data.avatar_url):
        update_data["avatar_url"] = await _normalized_avatar(data.avatar_url)
    
    await gd_update_one(db.session, "users", {"id": current_user["id"]}, update_data)
    
    updated_user = await gd_find_one(db.session, "users", {"id": current_user["id"]})
    if updated_user.get("avatar_url"):
        updated_user["avatar_url"] = signed_image_url(
            "avatar", updated_user.get("id"), updated_user.get("avatar_url")
        )
    return UserResponse(**updated_user)

@router.get("/users/me/preferences")
async def get_current_user_preferences(
    current_user: dict = Depends(get_current_user)
):
    """Get current user's preferences"""
    notif_prefs = current_user.get("notification_preferences") or {}
    if not isinstance(notif_prefs, dict):
        notif_prefs = {}
    it_comm = notif_prefs.get("it_communication") or {}
    if not isinstance(it_comm, dict):
        it_comm = {}
    return {
        "language": current_user.get("preferred_language", "ar"),
        "theme": current_user.get("preferred_theme", "light"),
        "time_format": current_user.get("time_format", "12h"),
        "date_format": current_user.get("date_format", "dd/mm/yyyy"),
        "first_day_of_week": current_user.get("first_day_of_week", "sunday"),
        "it_communication": {
            "default_channel": it_comm.get("default_channel", "email"),
            "quiet_hours_start": it_comm.get("quiet_hours_start", "21:00"),
            "quiet_hours_end": it_comm.get("quiet_hours_end", "07:00"),
        },
    }

@router.put("/users/me/preferences")
async def update_current_user_preferences(
    data: UserPreferencesUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Update current user's preferences"""
    update_data = {"updated_at": datetime.now(timezone.utc).isoformat()}
    
    if data.language is not None:
        update_data["preferred_language"] = data.language
    if data.theme is not None:
        update_data["preferred_theme"] = data.theme
    if data.time_format is not None:
        update_data["time_format"] = data.time_format
    if data.date_format is not None:
        update_data["date_format"] = data.date_format
    if data.first_day_of_week is not None:
        update_data["first_day_of_week"] = data.first_day_of_week
    # Task #200 §5.8 — merge IT communication prefs into existing
    # `users.notification_preferences` JSONB blob without touching other keys.
    if data.it_communication is not None:
        existing = current_user.get("notification_preferences") or {}
        if not isinstance(existing, dict):
            existing = {}
        prior_it = existing.get("it_communication") if isinstance(existing.get("it_communication"), dict) else {}
        merged_it = {**prior_it, **{k: v for k, v in data.it_communication.items() if v is not None}}
        update_data["notification_preferences"] = {**existing, "it_communication": merged_it}

    await gd_update_one(db.session, "users", {"id": current_user["id"]}, update_data)

    return {"message": "تم تحديث التفضيلات بنجاح", "success": True}

@router.get("/users/me/notifications")
async def get_current_user_notification_settings(
    current_user: dict = Depends(get_current_user)
):
    """Get current user's notification settings.

    Independent-Teacher (IT) accounts only support push (in-app) delivery
    in this release — the email and SMS channels are intentionally
    suppressed for that role so any downstream dispatcher reading these
    flags sees ``False`` regardless of whatever historical value sits on
    the user row. The PUT counterpart enforces the same invariant.
    """
    is_independent_teacher = (current_user.get("role") or "").lower() == "independent_teacher"
    return {
        "email_notifications": False if is_independent_teacher else current_user.get("email_notifications", True),
        "sms_notifications": False if is_independent_teacher else current_user.get("sms_notifications", False),
        "push_notifications": current_user.get("push_notifications", True),
        "attendance_alerts": current_user.get("attendance_alerts", True),
        "grade_alerts": current_user.get("grade_alerts", True),
        "behavior_alerts": current_user.get("behavior_alerts", True),
        "announcement_alerts": current_user.get("announcement_alerts", True),
        "weekly_digest": current_user.get("weekly_digest", True),
    }

@router.put("/users/me/notifications")
async def update_current_user_notification_settings(
    data: UserNotificationSettings,
    current_user: dict = Depends(get_current_user)
):
    """Update current user's notification settings.

    IT accounts cannot opt back into email/SMS from this endpoint — those
    two fields are silently ignored for that role to keep the GET/PUT
    invariant aligned with the frontend (push-only channel selector).
    """
    update_data = {"updated_at": datetime.now(timezone.utc).isoformat()}
    is_independent_teacher = (current_user.get("role") or "").lower() == "independent_teacher"

    if data.email_notifications is not None and not is_independent_teacher:
        update_data["email_notifications"] = data.email_notifications
    if data.sms_notifications is not None and not is_independent_teacher:
        update_data["sms_notifications"] = data.sms_notifications
    if data.push_notifications is not None:
        update_data["push_notifications"] = data.push_notifications
    if data.attendance_alerts is not None:
        update_data["attendance_alerts"] = data.attendance_alerts
    if data.grade_alerts is not None:
        update_data["grade_alerts"] = data.grade_alerts
    if data.behavior_alerts is not None:
        update_data["behavior_alerts"] = data.behavior_alerts
    if data.announcement_alerts is not None:
        update_data["announcement_alerts"] = data.announcement_alerts
    if data.weekly_digest is not None:
        update_data["weekly_digest"] = data.weekly_digest
    
    await gd_update_one(db.session, "users", {"id": current_user["id"]}, update_data)
    
    return {"message": "تم تحديث إعدادات الإشعارات بنجاح", "success": True}





# ============== USER AVATAR UPLOAD ==============
@router.post("/users/me/avatar")
async def upload_user_avatar(
    request: Request,
    current_user: dict = Depends(get_current_user)
):
    """Upload user avatar image (supports jpg, png, jpeg, webp)"""
    try:
        body = await request.json()
        image_data = body.get("image_data")
        
        if not image_data:
            raise HTTPException(status_code=400, detail="لم يتم إرسال صورة")

        MAX_B64_LENGTH = 2 * 1024 * 1024
        if len(image_data) > MAX_B64_LENGTH:
            raise HTTPException(status_code=413, detail="حجم الصورة كبير جداً (الحد الأقصى 2MB) | Image too large (max 2MB)")

        allowed_prefixes = ("data:image/jpeg;base64,", "data:image/png;base64,", "data:image/webp;base64,", "data:image/jpg;base64,")
        if not image_data.startswith(allowed_prefixes):
            raise HTTPException(status_code=400, detail="صيغة الصورة غير مدعومة. الصيغ المدعومة: jpg, jpeg, png, webp | Unsupported format. Allowed: jpg, jpeg, png, webp")
        
        try:
            b64_content = image_data.split(",", 1)[1]
            base64.b64decode(b64_content, validate=True)
        except Exception:
            raise HTTPException(status_code=400, detail="بيانات الصورة غير صالحة | Invalid image data")

        # Bound the image before persisting: stored verbatim, it is re-sent
        # inline by /auth/me on every app load.
        normalized = await _normalized_avatar(image_data)
        update_data = {
            "avatar_url": normalized,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        
        await gd_update_one(db.session, "users", {"id": current_user["id"]}, update_data)
        
        return {
            "success": True,
            "message": "تم رفع الصورة بنجاح",
            "avatar_url": signed_image_url("avatar", current_user["id"], normalized)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="فشل رفع الصورة")


class UserProfileUpdateExtended(BaseModel):
    """Extended profile update with title support"""
    title: Optional[str] = None
    full_name: Optional[str] = None
    full_name_en: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    avatar_url: Optional[str] = None
    preferred_language: Optional[str] = None
    bio: Optional[str] = None


@router.put("/users/me/profile")
async def update_user_profile_extended(
    data: UserProfileUpdateExtended,
    current_user: dict = Depends(get_current_user),
    # Task #201 — IT §5.7 step-up backfill. IT-conditional so non-IT
    # roles (principal, school admin, teacher, parent, platform admin)
    # keep their existing MFA posture and outcomes unchanged.
    _mfa: dict = Depends(_REQUIRE_RECENT_MFA_403_IT),
):
    """Update current user's profile including title and language"""
    update_data = {"updated_at": datetime.now(timezone.utc).isoformat()}
    
    if data.title is not None:
        update_data["title"] = data.title if data.title != "none" else ""
    if data.full_name is not None:
        from engines.name_validation import validate_personal_name
        valid, err_msg = validate_personal_name(data.full_name)
        if not valid:
            raise HTTPException(status_code=400, detail=err_msg)
        update_data["full_name"] = data.full_name
    if data.full_name_en is not None:
        update_data["full_name_en"] = data.full_name_en
    if data.email is not None and data.email:
        existing = await gd_find_one(db.session, "users", {"email": data.email, "id": {"$ne": current_user["id"]}})
        if existing:
            raise HTTPException(status_code=400, detail="البريد الإلكتروني مستخدم مسبقاً")
        # Extra guard for teacher accounts: block updates that would collide with
        # a teachers row not already linked to this user.  Without this check a
        # teacher could update their email to an orphaned teacher record's email
        # and trigger the auto-link in get_current_user(), hijacking that record.
        if current_user.get("role") == "teacher":
            _caller_teacher_id = current_user.get("teacher_id")
            _tenant = current_user.get("tenant_id")
            _q: dict = {"email": str(data.email)}
            if _tenant:
                _q["school_id"] = _tenant
            _teacher_collision = await gd_find_one(db.session, "teachers", _q)
            if _teacher_collision and _teacher_collision.get("id") != _caller_teacher_id:
                raise HTTPException(status_code=400, detail="البريد الإلكتروني مستخدم مسبقاً")
        update_data["email"] = data.email
    if data.phone is not None and data.phone:
        existing = await gd_find_one(db.session, "users", {"phone": data.phone, "id": {"$ne": current_user["id"]}})
        if existing:
            raise HTTPException(status_code=400, detail="رقم الهاتف مستخدم مسبقاً")
        # Same guard as email: block phone values that exist on a teachers row
        # not owned by this user to prevent identity-hijack via auto-link.
        if current_user.get("role") == "teacher":
            _caller_teacher_id = current_user.get("teacher_id")
            _tenant = current_user.get("tenant_id")
            _q = {"phone": data.phone}
            if _tenant:
                _q["school_id"] = _tenant
            _teacher_collision = await gd_find_one(db.session, "teachers", _q)
            if _teacher_collision and _teacher_collision.get("id") != _caller_teacher_id:
                raise HTTPException(status_code=400, detail="رقم الهاتف مستخدم مسبقاً")
        update_data["phone"] = data.phone
    if data.avatar_url is not None and not is_internal_image_url(data.avatar_url):
        update_data["avatar_url"] = await _normalized_avatar(data.avatar_url)
    if data.preferred_language is not None:
        update_data["preferred_language"] = data.preferred_language
    if data.bio is not None:
        update_data["bio"] = data.bio
    
    await gd_update_one(db.session, "users", {"id": current_user["id"]}, update_data)
    
    updated_user = await gd_find_one(db.session, "users", {"id": current_user["id"]})
    
    return {
        "success": True,
        "message": "تم حفظ الملف الشخصي بنجاح",
        "user": updated_user
    }





# NOTE: User session management endpoints (/settings/sessions, /settings/sessions/end-all,
# /settings/sessions/{id}) live in routes/settings_routes.py and are backed by the real
# user_sessions table populated on login. The stubs that were here used a deleted
# `is_current` boolean and didn't actually revoke tokens.





# ============== TEST ACCOUNTS CREATION ENDPOINT ==============
@router.post("/test-accounts/create")
async def create_test_accounts(
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))
):
    """
    Create test student and parent accounts for testing the portal
    إنشاء حسابات تجريبية للطالب وولي الأمر
    """
    from src.modules.portals.controllers.student_portal_routes import create_test_student_account, create_test_parent_account
    
    try:
        student = await create_test_student_account(db)
        parent = await create_test_parent_account(db)
        
        return {
            "success": True,
            "message": "تم إنشاء الحسابات التجريبية بنجاح",
            "accounts": {
                "student": {
                    "email": "student@nassaq.com",
                    "password": "Student@123",
                    "name": student.get("full_name") if student else "طالب تجريبي"
                },
                "parent": {
                    "email": "parent@nassaq.com", 
                    "password": "Parent@123",
                    "name": parent.get("full_name") if parent else "ولي أمر تجريبي"
                }
            }
        }
    except Exception as e:
        logger.error(f"Test account creation error: {e}")
        return {
            "success": False,
            "message": "حدث خطأ أثناء إنشاء الحسابات التجريبية"
        }


# Configure logging



