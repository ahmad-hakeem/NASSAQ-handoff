"""
NASSAQ Academics Sub-module
"""
from fastapi import APIRouter, HTTPException, Depends, status, Header, Query, Body, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import Response
from starlette.responses import StreamingResponse
from pydantic import BaseModel, Field, ConfigDict, EmailStr, model_validator
from typing import List, Optional, Any, Dict
from datetime import datetime, timezone, timedelta
import uuid, os, logging, json, random, re, io, base64

logger = logging.getLogger("nassaq.academics")

from dependencies import (
    db, get_current_user, require_roles, UserRole, SchoolStatus,
    hash_password, verify_password, create_access_token,
    JWT_SECRET, JWT_ALGORITHM, ACCESS_TOKEN_EXPIRE, security,
    audit_engine, AuditAction, AuditSeverity,
    smart_scheduling_engine, TimetableRunStatus, TimetableStatus,
    ConflictType, ConflictSeverity, PreValidationResult, GenerationResult,
    hakim_engine, reporting_engine, export_engine, session_engine,
    REPORT_TYPES, generate_student_qr_code
)
from engines.sql_utils import gd_find, gd_find_one, gd_insert, gd_insert_many, gd_update_one, gd_update_many, gd_count, gd_delete_one, gd_delete_many, gd_distinct


from shared_models import (
    TeacherCreate, TeacherUpdate, TeacherResponse, StudentCreate, StudentUpdate, StudentResponse, ClassCreate, ClassUpdate, ClassResponse, SubjectCreate, SubjectResponse
)

router = APIRouter()


async def get_school_id_from_context(current_user: dict, x_school_context: str = None) -> str:
    """Resolve school_id from header, with strict tenant isolation.

    Delegates to `utils.tenant_scope.resolve_school_id` so that non-platform
    callers can never address another school's data via the X-School-Context
    header (mismatched override → 403). Platform admins retain free override.
    """
    from utils.tenant_scope import resolve_school_id
    return resolve_school_id(current_user, x_school_context)


class SubjectCreateForSchool(BaseModel):
    name: str
    name_en: Optional[str] = None
    grade_id: Optional[str] = None
    weekly_periods: int = 4

# ============== SUBJECTS CRUD - إدارة المواد الدراسية ==============
# NOTE: these models are intentionally NAMED differently from the shared
# `SubjectCreate` (which is `name`-keyed) so the `/subjects` routes below
# bind to the shared model — keeping the IT-facing FE contract aligned
# with the existing `/subjects` REST surface (Task #190).

class SchoolSubjectCreate(BaseModel):
    name_ar: str
    name_en: Optional[str] = None
    code: Optional[str] = None
    category: Optional[str] = None
    weekly_periods: int = 4
    description: Optional[str] = None

# Task #185 — payload used by the generic /subjects POST/PUT endpoints
# (Independent-Teacher + school-admin surfaces). Decoupled from the
# legacy /school/subjects `SubjectCreate` model so the IT FE can send
# `name`/`weekly_hours` without breaking the older school-admin schema.
class SubjectMutate(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: str
    name_en: Optional[str] = None
    code: Optional[str] = None
    description: Optional[str] = None
    weekly_hours: Optional[int] = 4
    grade_levels: Optional[List[str]] = None
    school_id: Optional[str] = None  # ignored for IT callers

# Renamed from SubjectUpdate (Task #190) to avoid shadowing the shared
# `SubjectCreate` (`name`-keyed) used by the generic /subjects routes;
# this model backs the legacy /school/subjects PUT only.
class SchoolSubjectUpdate(BaseModel):
    name_ar: Optional[str] = None
    name_en: Optional[str] = None
    code: Optional[str] = None
    category: Optional[str] = None
    weekly_periods: Optional[int] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None

@router.post("/school/subjects")
async def create_school_subject(
    subject_data: SchoolSubjectCreate,
    current_user: dict = Depends(require_roles([UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN])),
    x_school_context: str = Header(default=None, alias="X-School-Context")
):
    """Create a new subject for the school - إضافة مادة جديدة للمدرسة"""
    school_id = await get_school_id_from_context(current_user, x_school_context)
    
    if not school_id:
        raise HTTPException(status_code=400, detail="School context required")
    
    subject_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    
    subject_doc = {
        "id": subject_id,
        "school_id": school_id,
        "name_ar": subject_data.name_ar,
        "name_en": subject_data.name_en or subject_data.name_ar,
        "code": subject_data.code or f"SUB-{subject_id[:8].upper()}",
        "category": subject_data.category or "general",
        "weekly_periods": subject_data.weekly_periods,
        "description": subject_data.description,
        "is_active": True,
        "created_at": now,
        "updated_at": now,
        "created_by": current_user.get("id")
    }
    
    await gd_insert(db.session, "subjects", subject_doc)
    
    # Remove _id from response
    if "_id" in subject_doc:
        del subject_doc["_id"]
    
    return {"id": subject_id, "message": "تم إضافة المادة بنجاح", "subject": subject_doc}

@router.put("/school/subjects/{subject_id}")
async def update_school_subject(
    subject_id: str,
    subject_data: SchoolSubjectUpdate,
    current_user: dict = Depends(require_roles([UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN])),
    x_school_context: str = Header(default=None, alias="X-School-Context")
):
    """Update a subject - تعديل مادة"""
    school_id = await get_school_id_from_context(current_user, x_school_context)
    
    if not school_id:
        raise HTTPException(status_code=400, detail="School context required")
    
    # Check if subject exists for this school
    subject = await gd_find_one(db.session, "subjects", {"id": subject_id, "school_id": school_id})
    
    if not subject:
        raise HTTPException(status_code=404, detail="المادة غير موجودة")
    
    update_data = {"updated_at": datetime.now(timezone.utc).isoformat()}
    
    if subject_data.name_ar is not None:
        update_data["name_ar"] = subject_data.name_ar
    if subject_data.name_en is not None:
        update_data["name_en"] = subject_data.name_en
    if subject_data.code is not None:
        update_data["code"] = subject_data.code
    if subject_data.category is not None:
        update_data["category"] = subject_data.category
    if subject_data.weekly_periods is not None:
        update_data["weekly_periods"] = subject_data.weekly_periods
    if subject_data.description is not None:
        update_data["description"] = subject_data.description
    if subject_data.is_active is not None:
        update_data["is_active"] = subject_data.is_active
    
    await gd_update_one(db.session, "subjects", {"id": subject_id}, update_data)
    
    return {"message": "تم تحديث المادة بنجاح"}

@router.delete("/school/subjects/{subject_id}")
async def delete_school_subject(
    subject_id: str,
    force: bool = False,
    current_user: dict = Depends(require_roles([UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN])),
    x_school_context: str = Header(default=None, alias="X-School-Context")
):
    """Delete (soft) a subject - حذف مادة"""
    school_id = await get_school_id_from_context(current_user, x_school_context)
    
    if not school_id:
        raise HTTPException(status_code=400, detail="School context required")
    
    # Check if subject exists for this school
    subject = await gd_find_one(db.session, "subjects", {"id": subject_id, "school_id": school_id})
    
    if not subject:
        raise HTTPException(status_code=404, detail="المادة غير موجودة")
    
    # Check for dependencies (teacher assignments)
    assignments_count = await gd_count(db.session, "teacher_assignments", {"subject_id": subject_id, "school_id": school_id})
    
    if assignments_count > 0 and not force:
        return {
            "warning": True,
            "message": f"هذه المادة مرتبطة بـ {assignments_count} إسناد للمعلمين. هل تريد الحذف؟",
            "dependencies": {
                "teacher_assignments": assignments_count
            },
            "requires_confirmation": True
        }
    
    # Soft delete
    await gd_update_one(db.session, "subjects", {"id": subject_id}, {"is_active": False, "deleted_at": datetime.now(timezone.utc).isoformat(), "deleted_by": current_user["id"]})
    
    # Audit log
    audit_log = {
        "id": str(uuid.uuid4()),
        "school_id": school_id,
        "action": "delete",
        "entity_type": "subject",
        "entity_id": subject_id,
        "old_data": {"name_ar": subject.get("name_ar"), "is_active": True},
        "new_data": {"is_active": False},
        "performed_by": current_user["id"],
        "performed_by_name": current_user.get("full_name", ""),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "ip_address": None
    }
    await gd_insert(db.session, "audit_logs", audit_log)
    
    return {"message": "تم حذف المادة بنجاح"}

@router.get("/school/subjects")
async def get_school_subjects(
    current_user: dict = Depends(get_current_user),
    x_school_context: str = Header(default=None, alias="X-School-Context")
):
    """Get all subjects for the school - جلب جميع المواد للمدرسة"""
    school_id = await get_school_id_from_context(current_user, x_school_context)
    
    if not school_id:
        raise HTTPException(status_code=400, detail="School context required")
    
    subjects = await gd_find(db.session, "subjects", {"school_id": school_id, "is_active": True}, limit=100)
    
    return subjects

@router.get("/school/subjects/unique")
async def get_unique_school_subjects(
    current_user: dict = Depends(get_current_user),
    x_school_context: str = Header(default=None, alias="X-School-Context")
):
    """Get unique subjects from all sources for teacher assignment - جلب المواد الفريدة للإسناد"""
    school_id = await get_school_id_from_context(current_user, x_school_context)
    
    if not school_id:
        raise HTTPException(status_code=400, detail="School context required")
    
    subjects_dict = {}
    
    # 1. Get subjects from school's subjects collection
    school_subjects = await gd_find(db.session, "subjects", {"school_id": school_id, "is_active": {"$ne": False}}, limit=500)
    
    for s in school_subjects:
        name = s.get("name") or s.get("name_ar") or "مادة بدون اسم"
        if name not in subjects_dict:
            subjects_dict[name] = {
                "id": s.get("id"),
                "name_ar": s.get("name_ar") or s.get("name"),
                "name_en": s.get("name_en"),
                "code": s.get("code"),
                "source": "school"
            }
    
    # 2. Get subjects from reference_subjects (if not enough)
    if len(subjects_dict) < 10:
        ref_subjects = await gd_find(db.session, "reference_subjects", {}, limit=500)
        
        for s in ref_subjects:
            name = s.get("name") or s.get("name_ar") or "مادة بدون اسم"
            if name not in subjects_dict:
                subjects_dict[name] = {
                    "id": s.get("id"),
                    "name_ar": s.get("name_ar") or s.get("name"),
                    "name_en": s.get("name_en"),
                    "code": s.get("code"),
                    "source": "reference"
                }
    
    # 3. If still not enough, get from official curriculum
    if len(subjects_dict) < 10:
        official_subjects = await gd_find(db.session, "official_curriculum_subjects", {}, limit=500)
        
        for s in official_subjects:
            name = s.get("name_ar") or s.get("name") or "مادة بدون اسم"
            if name not in subjects_dict:
                subjects_dict[name] = {
                    "id": s.get("id"),
                    "name_ar": s.get("name_ar") or s.get("name"),
                    "name_en": s.get("name_en"),
                    "code": s.get("code"),
                    "source": "official"
                }
    
    # Convert to list sorted by name
    result = sorted(subjects_dict.values(), key=lambda x: x.get("name_ar") or "")
    
    return result





# ============== SUBJECTS ROUTES ==============
def _normalize_subject_name(value: Optional[str]) -> str:
    """Normalize a subject name for case-insensitive duplicate comparison.

    Trims surrounding whitespace, collapses internal whitespace, and
    case-folds. Returns an empty string for falsy input so the dedupe
    check is a no-op when no name was supplied.
    """
    if not value:
        return ""
    return " ".join(str(value).split()).casefold()


async def _assert_subject_name_unique(
    school_id: str,
    name: Optional[str],
    name_ar: Optional[str] = None,
    exclude_id: Optional[str] = None,
) -> None:
    """Reject the request if another active subject in the same workspace
    already uses this `name` or `name_ar` (case-insensitive, whitespace-
    normalized). Soft-deleted (`is_active=False`) rows are ignored so a
    teacher can re-create a previously deleted subject (Task #190).
    """
    candidates = {n for n in (_normalize_subject_name(name), _normalize_subject_name(name_ar)) if n}
    if not candidates or not school_id:
        return
    existing = await gd_find(
        db.session,
        "subjects",
        {"school_id": school_id, "is_active": {"$ne": False}},
        limit=1000,
    )
    for row in existing:
        if exclude_id and row.get("id") == exclude_id:
            continue
        existing_names = {
            _normalize_subject_name(row.get("name")),
            _normalize_subject_name(row.get("name_ar")),
        }
        if candidates & (existing_names - {""}):
            raise HTTPException(status_code=409, detail="يوجد بالفعل مادة بنفس الاسم")


@router.post("/subjects", response_model=SubjectResponse)
async def create_subject(
    subject_data: SubjectMutate,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.SCHOOL_SUB_ADMIN, UserRole.INDEPENDENT_TEACHER]))
):
    """Create a new subject. IT callers are always pinned to their own
    workspace; any caller-supplied `school_id` for IT is ignored."""
    from auth_scope import is_independent_teacher, independent_workspace_id
    subject_id = str(uuid.uuid4())

    if is_independent_teacher(current_user):
        target_school_id = independent_workspace_id(current_user)
    else:
        target_school_id = subject_data.school_id or current_user.get("tenant_id")

    await _assert_subject_name_unique(target_school_id, subject_data.name)

    subject_doc = {
        "id": subject_id,
        "name": subject_data.name,
        "name_en": subject_data.name_en,
        "school_id": target_school_id,
        "code": subject_data.code,
        "description": subject_data.description,
        "weekly_hours": subject_data.weekly_hours or 4,
        "grade_levels": subject_data.grade_levels,
        "is_active": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat()
    }

    try:
        from services.translation_service import translate_fields, is_available
        if is_available():
            subject_doc = await translate_fields(subject_doc, ["name"])
    except Exception:
        pass

    await gd_insert(db.session, "subjects", subject_doc)
    return SubjectResponse(**subject_doc)

@router.get("/subjects", response_model=List[SubjectResponse])
async def get_subjects(
    school_id: Optional[str] = None,
    include_inactive: bool = False,
    current_user: dict = Depends(get_current_user)
):
    """Get all subjects or filter by school. Non-platform callers are
    pinned to their own tenant; a caller-supplied `school_id` that does
    not match is rejected with 403 so the API never confirms the
    existence of foreign-tenant rows. Soft-deleted (`is_active=False`)
    rows are hidden by default; platform admins can opt in via
    `include_inactive=true`."""
    from auth_scope import is_independent_teacher, independent_workspace_id
    query = {}
    if not include_inactive:
        query["is_active"] = {"$ne": False}
    # Tenant scope. IT callers fall back to their synthetic workspace id
    # (`itw_{user_id}`) via `independent_workspace_id` when `tenant_id`
    # is unset on the JWT.
    is_platform = current_user.get("role") == UserRole.PLATFORM_ADMIN.value
    caller_tenant = (
        current_user.get("tenant_id")
        or (independent_workspace_id(current_user) if is_independent_teacher(current_user) else None)
    )
    if is_platform:
        # Platform admin may scope by any school_id, or list across all
        # tenants when omitted.
        if school_id:
            query["school_id"] = school_id
    else:
        # Non-platform callers are pinned to their own tenant. A
        # caller-supplied `school_id` that does not match the caller's
        # tenant is rejected with 403 so the API never confirms the
        # existence of foreign-tenant rows.
        if school_id and school_id != caller_tenant:
            raise HTTPException(status_code=403, detail="غير مصرح")
        query["school_id"] = caller_tenant

    subjects = await gd_find(db.session, "subjects", query, limit=1000)
    result = []
    for s in subjects:
        if "name" not in s and "name_ar" in s:
            s["name"] = s["name_ar"]
        if "weekly_periods" not in s and "weekly_hours" in s:
            s["weekly_periods"] = s["weekly_hours"]
        try:
            result.append(SubjectResponse(**s))
        except Exception as e:
            logger.warning(f"Failed to serialize subject {s.get('id', 'unknown')}: {e}")
    return result

@router.get("/subjects/{subject_id}", response_model=SubjectResponse)
async def get_subject(subject_id: str, current_user: dict = Depends(get_current_user)):
    """Get subject by ID. Tenant-scoped for non-platform callers; cross-
    workspace by-id reads return 404 (spec §8 inv. 3) so the API never
    confirms the existence of foreign-tenant rows. Fails closed when a
    non-platform caller has no resolvable tenant context."""
    from auth_scope import is_independent_teacher, independent_workspace_id
    query = {"id": subject_id}
    if current_user.get("role") != UserRole.PLATFORM_ADMIN.value:
        caller_tenant = (
            independent_workspace_id(current_user) if is_independent_teacher(current_user)
            else current_user.get("tenant_id")
        )
        if not caller_tenant:
            raise HTTPException(status_code=403, detail="غير مصرح")
        query["school_id"] = caller_tenant
    subject = await gd_find_one(db.session, "subjects", query)
    if not subject:
        raise HTTPException(status_code=404, detail="المادة غير موجودة")
    if "name" not in subject and "name_ar" in subject:
        subject["name"] = subject["name_ar"]
    if "weekly_periods" not in subject and "weekly_hours" in subject:
        subject["weekly_periods"] = subject["weekly_hours"]
    return SubjectResponse(**subject)

@router.put("/subjects/{subject_id}")
async def update_subject(
    subject_id: str,
    subject_data: SubjectMutate,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.SCHOOL_SUB_ADMIN, UserRole.INDEPENDENT_TEACHER]))
):
    """Update subject. Tenant-scoped for non-platform callers; cross-
    workspace ids return 404 (spec §8 inv. 3). Fails closed when a non-
    platform caller has no resolvable tenant context."""
    from auth_scope import is_independent_teacher, independent_workspace_id
    subject_query = {"id": subject_id}
    if current_user.get("role") != UserRole.PLATFORM_ADMIN.value:
        caller_tenant = (
            independent_workspace_id(current_user) if is_independent_teacher(current_user)
            else current_user.get("tenant_id")
        )
        # Fail closed: refuse to run an unscoped lookup if the caller has
        # no resolvable tenant context.
        if not caller_tenant:
            raise HTTPException(status_code=403, detail="غير مصرح")
        subject_query["school_id"] = caller_tenant
    old_subject = await gd_find_one(db.session, "subjects", subject_query)
    if not old_subject:
        raise HTTPException(status_code=404, detail="المادة غير موجودة")
    new_name = subject_data.name
    await _assert_subject_name_unique(
        old_subject.get("school_id"), new_name, exclude_id=subject_id
    )
    update_doc = {
        "name": new_name,
        "name_en": subject_data.name_en,
        "code": subject_data.code,
        "description": subject_data.description,
        "weekly_hours": subject_data.weekly_hours or 4,
        "grade_levels": subject_data.grade_levels,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    result = await gd_update_one(db.session, "subjects", subject_query, update_doc)
    if result == 0:
        raise HTTPException(status_code=404, detail="المادة غير موجودة")

    if old_subject and new_name and new_name != old_subject.get("name"):
        await gd_update_many(db.session, "teacher_assignments", {"subject_id": subject_id}, {"subject_name": new_name})
        await gd_update_many(db.session, "schedule_sessions", {"subject_id": subject_id}, {"subject_name": new_name})

    return {"message": "تم تحديث بيانات المادة"}

@router.delete("/subjects/{subject_id}")
async def delete_subject(
    subject_id: str,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.INDEPENDENT_TEACHER]))
):
    """Delete subject (soft delete). Tenant-scoped for non-platform
    callers; cross-workspace ids return 404 (spec §8 inv. 3). Fails
    closed when a non-platform caller has no resolvable tenant."""
    from auth_scope import is_independent_teacher, independent_workspace_id
    subject_query = {"id": subject_id}
    if current_user.get("role") != UserRole.PLATFORM_ADMIN.value:
        caller_tenant = (
            independent_workspace_id(current_user) if is_independent_teacher(current_user)
            else current_user.get("tenant_id")
        )
        if not caller_tenant:
            raise HTTPException(status_code=403, detail="غير مصرح")
        subject_query["school_id"] = caller_tenant
    subject = await gd_find_one(db.session, "subjects", subject_query)
    if not subject:
        raise HTTPException(status_code=404, detail="المادة غير موجودة")

    await gd_update_one(db.session, "subjects", subject_query, {"is_active": False})
    return {"message": "تم حذف المادة"}




# ============== SUBJECTS (for scheduling) ==============

@router.get("/school/settings/subjects")
async def get_school_subjects(
    current_user: dict = Depends(get_current_user),
    x_school_context: str = Header(default=None, alias="X-School-Context")
):
    """Get school subjects - جلب المواد الدراسية"""
    school_id = await get_school_id_from_context(current_user, x_school_context)
    
    if not school_id:
        raise HTTPException(status_code=400, detail="School context required")
    
    subjects = await gd_find(db.session, "subjects", {"tenant_id": school_id}, limit=100)
    return {"subjects": subjects}


@router.post("/school/settings/subjects")
async def create_school_subject(
    data: SubjectCreateForSchool,
    current_user: dict = Depends(require_roles([UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN])),
    x_school_context: str = Header(default=None, alias="X-School-Context")
):
    """Create subject - إنشاء مادة دراسية"""
    school_id = await get_school_id_from_context(current_user, x_school_context)
    
    if not school_id:
        raise HTTPException(status_code=400, detail="School context required")
    
    subject = {
        "id": str(uuid.uuid4()),
        "tenant_id": school_id,
        "name": data.name,
        "name_en": data.name_en,
        "grade_id": data.grade_id,
        "weekly_periods": data.weekly_periods,
        "is_active": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by": current_user["id"]
    }
    
    await gd_insert(db.session, "subjects", subject)
    subject.pop("_id", None)
    
    return {"message": "تم إضافة المادة الدراسية", "subject": subject}


@router.delete("/school/settings/subjects/{subject_id}")
async def delete_school_subject(
    subject_id: str,
    current_user: dict = Depends(require_roles([UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN])),
    x_school_context: str = Header(default=None, alias="X-School-Context")
):
    """Delete subject - حذف مادة دراسية"""
    school_id = await get_school_id_from_context(current_user, x_school_context)
    
    if not school_id:
        raise HTTPException(status_code=400, detail="School context required")
    
    await gd_delete_one(db.session, "subjects", {"id": subject_id, "tenant_id": school_id})
    
    return {"message": "تم حذف المادة الدراسية"}





