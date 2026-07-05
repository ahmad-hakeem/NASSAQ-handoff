"""
NASSAQ Academics Sub-module
"""
from fastapi import APIRouter, HTTPException, Depends, status, Header, Query, Body, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import Response
from starlette.responses import StreamingResponse
from pydantic import BaseModel, Field, ConfigDict, EmailStr, model_validator, AliasChoices
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
    REPORT_TYPES, generate_student_qr_code,
    require_recent_mfa_403_if_independent_teacher,
)
from engines.sql_utils import gd_find, gd_find_one, gd_insert, gd_insert_many, gd_update_one, gd_update_many, gd_count, gd_delete_one, gd_delete_many, gd_distinct


from shared_models import (
    TeacherCreate, TeacherUpdate, TeacherResponse, StudentCreate, StudentUpdate, StudentResponse, ClassCreate, ClassUpdate, ClassResponse, SubjectCreate, SubjectResponse
)

router = APIRouter()

_REQUIRE_RECENT_MFA_403_IT = require_recent_mfa_403_if_independent_teacher()


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
    model_config = ConfigDict(extra="ignore", populate_by_name=True)
    name: str
    name_en: Optional[str] = None
    code: Optional[str] = None
    description: Optional[str] = None
    # Accept both `weekly_hours` and the `weekly_periods` alias the FE/response
    # use, since the two names have drifted before. Either key persists onto
    # the real `default_periods_per_week` column.
    weekly_hours: Optional[int] = Field(
        default=None,
        validation_alias=AliasChoices("weekly_hours", "weekly_periods"),
    )
    grade_levels: Optional[List[str]] = None
    school_id: Optional[str] = None  # ignored for IT callers
    category: Optional[str] = None
    credits: Optional[int] = None

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
        "name": subject_data.name_ar,
        "name_ar": subject_data.name_ar,
        "name_en": subject_data.name_en or subject_data.name_ar,
        "code": subject_data.code or f"SUB-{subject_id[:8].upper()}",
        "category": subject_data.category or "general",
        # Map the API's `weekly_periods` onto the real column so the value
        # is persisted (the table has no `weekly_periods`/`data` column, so
        # the old key was silently dropped on insert).
        "default_periods_per_week": subject_data.weekly_periods,
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
        update_data["default_periods_per_week"] = subject_data.weekly_periods
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


# --- Subject-code suggestion ("Generate with Hakim") ---------------------
# Category → deterministic ASCII prefix fallback, used when no usable English
# name is available and the LLM yields nothing. Mirrors the category options
# rendered by the frontend Add-Subject modal.
_CATEGORY_CODE_PREFIX = {
    "core": "CORE",
    "elective": "ELEC",
    "language": "LANG",
    "science": "SCI",
    "math": "MATH",
    "social": "SOC",
    "arts": "ART",
    "physical": "PE",
    "technology": "TECH",
    "religion": "REL",
}


def _code_letters(raw: Optional[str], limit: int = 4) -> str:
    """Uppercase A-Z letters only from an arbitrary string, capped at `limit`."""
    if not raw:
        return ""
    return "".join(c for c in raw.upper() if "A" <= c <= "Z")[:limit]


def _build_subject_code(
    *,
    name_en: Optional[str],
    category: Optional[str],
    llm_prefix: Optional[str],
    existing_codes: set,
) -> str:
    """Build a normalized, collision-free subject code for one school.

    Prefix precedence: a usable LLM-refined prefix → English name → category
    fallback → generic "SUBJ". A numeric suffix is appended and bumped until
    the value is free among the school's active subject codes. The result is
    always uppercase letters+digits and satisfies the create-flow format.
    """
    prefix = _code_letters(llm_prefix) or _code_letters(name_en)
    if len(prefix) < 2:
        prefix = _CATEGORY_CODE_PREFIX.get((category or "").strip().lower(), "")
    if len(prefix) < 2:
        prefix = "SUBJ"
    taken = {str(c).upper() for c in existing_codes if c}
    n = 101
    while f"{prefix}{n}" in taken:
        n += 1
        if n > 9999:
            # Practically unreachable; vary the prefix to guarantee termination.
            prefix = (prefix[:3] + "X")
            n = 101
    return f"{prefix}{n}"


class SubjectCodeSuggestRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: Optional[str] = None
    name_en: Optional[str] = None
    category: Optional[str] = None


@router.post("/subjects/hakim-code")
async def hakim_subject_code(
    payload: SubjectCodeSuggestRequest,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN])),
    x_school_context: Optional[str] = Header(default=None, alias="X-School-Context"),
):
    """Suggest a normalized, collision-free subject code for the caller's
    school ("Generate with Hakim" in the Add-Subject modal).

    School-scoped: existing codes are read only within the caller's resolved
    tenant. The LLM output is treated purely as a candidate prefix — the
    server always normalizes (uppercase, letters+digits, length cap) and
    de-duplicates, with a deterministic fallback so a valid code is returned
    even when the model yields nothing. Never auto-submits; the frontend
    keeps the value editable and the normal POST /subjects path unchanged.
    """
    from utils.tenant_scope import resolve_school_id
    school_id = resolve_school_id(current_user, x_school_context) or current_user.get("tenant_id")
    if not school_id:
        raise HTTPException(status_code=400, detail="تعذّر تحديد المدرسة")

    name_ar = (payload.name or "").strip()
    name_en = (payload.name_en or "").strip()
    if not name_ar and not name_en:
        return {"success": False, "reason": "NAME_REQUIRED"}

    # Tenant-scoped existing codes (active subjects only) — collision set.
    existing = await gd_find(
        db.session,
        "subjects",
        {"school_id": school_id, "is_active": {"$ne": False}},
        limit=2000,
    )
    existing_codes = {str(r.get("code")) for r in existing if r.get("code")}

    # Optional LLM refinement → an English prefix. Best-effort and never
    # fatal: any failure / disabled-AI falls through to the deterministic
    # path below.
    llm_prefix: Optional[str] = None
    try:
        from services.hakim_llm_service import hakim_generate
        result = await hakim_generate(
            mode="generate",
            field="subject_code",
            context={"subject": name_en or name_ar, "category": payload.category or None},
            language="en",
            tenant_id=school_id,
        )
        if result.get("success"):
            llm_prefix = result.get("text")
    except Exception as e:  # noqa: BLE001 - best-effort refinement
        logger.warning(f"[Hakim] subject_code generate failed: {e}")

    code = _build_subject_code(
        name_en=name_en,
        category=payload.category,
        llm_prefix=llm_prefix,
        existing_codes=existing_codes,
    )
    return {"success": True, "code": code}


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
        from utils.tenant_scope import resolve_school_id
        target_school_id = resolve_school_id(current_user, subject_data.school_id) or current_user.get("tenant_id")

    await _assert_subject_name_unique(target_school_id, subject_data.name)

    periods = subject_data.weekly_hours or 4
    subject_doc = {
        "id": subject_id,
        "name": subject_data.name,
        "name_en": subject_data.name_en,
        "school_id": target_school_id,
        "code": subject_data.code,
        "description": subject_data.description,
        "category": subject_data.category or "core",
        "credits": subject_data.credits or 1,
        # Persist onto the real columns (`weekly_hours`/`grade_levels` are
        # not columns and were silently dropped on insert).
        "default_periods_per_week": periods,
        "applicable_stages": subject_data.grade_levels or [],
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
    return SubjectResponse(**{**subject_doc, "weekly_periods": periods})

@router.get("/subjects", response_model=List[SubjectResponse])
async def get_subjects(
    include_inactive: bool = False,
    include_deleted: bool = Query(default=False),
    x_school_context: Optional[str] = Header(default=None, alias="X-School-Context"),
    current_user: dict = Depends(get_current_user)
):
    """Get all subjects or filter by school.

    Task #510: Platform admins resolve preview scope via the
    `X-School-Context` header through `resolve_school_id`, which only
    honors the override when the bearer token was minted by
    `/role-switch/switch`. Without an override a plain platform-admin
    token still returns the cross-tenant directory (legacy admin-console
    behavior). The previous `?school_id=` query param branch silently
    let any caller pivot to another tenant's rows and is no longer
    honored. Non-platform callers are pinned to their own tenant.
    Soft-deleted (`is_active=False`) rows are hidden by default;
    platform admins can opt in via `include_inactive=true`."""
    from auth_scope import is_independent_teacher, independent_workspace_id
    from utils.tenant_scope import resolve_school_id
    _admin_roles = {
        UserRole.PLATFORM_ADMIN.value,
        UserRole.SCHOOL_PRINCIPAL.value,
        UserRole.SCHOOL_ADMIN.value,
        UserRole.SCHOOL_SUB_ADMIN.value,
        UserRole.INDEPENDENT_TEACHER.value,
    }
    show_deleted = bool(include_deleted) and current_user.get("role") in _admin_roles
    query = {}
    if not include_inactive and not show_deleted:
        query["is_active"] = {"$ne": False}
    is_platform = current_user.get("role") == UserRole.PLATFORM_ADMIN.value
    if is_platform:
        scoped = resolve_school_id(current_user, x_school_context)
        if scoped:
            query["school_id"] = scoped
    else:
        # Compute caller's own tenant/workspace first so Independent
        # Teacher tokens (which carry no real `tenant_id`) keep working
        # even when no X-School-Context header is supplied. Only invoke
        # the strict override validation when the caller actually sent
        # a header — otherwise `resolve_school_id` would 403 for IT.
        caller_tenant = (
            (independent_workspace_id(current_user) if is_independent_teacher(current_user) else None)
            or current_user.get("tenant_id")
        )
        if x_school_context is not None:
            scoped = resolve_school_id(current_user, x_school_context)
            caller_tenant = scoped or caller_tenant
        query["school_id"] = caller_tenant

    subjects = await gd_find(db.session, "subjects", query, limit=1000)

    deleted_by_map: Dict[str, str] = {}
    if show_deleted:
        deleter_ids = list({s.get("deleted_by") for s in subjects if s.get("deleted_by")})
        if deleter_ids:
            try:
                deleter_rows = await gd_find(
                    db.session, "users", {"id": {"$in": deleter_ids}}, limit=200
                )
                deleted_by_map = {
                    u.get("id"): (u.get("full_name") or u.get("email") or "")
                    for u in deleter_rows
                    if u.get("id")
                }
            except Exception as _deleter_err:
                logger.warning(
                    f"Failed to resolve deleted_by names for subjects: {_deleter_err}"
                )
                deleted_by_map = {}

    result = []
    for s in subjects:
        if "name" not in s and "name_ar" in s:
            s["name"] = s["name_ar"]
        if "weekly_periods" not in s:
            s["weekly_periods"] = (
                s.get("default_periods_per_week") or s.get("weekly_hours") or 4
            )
        if show_deleted and s.get("deleted_by"):
            s["deleted_by_name"] = deleted_by_map.get(s.get("deleted_by"))
        try:
            result.append(SubjectResponse(**s))
        except Exception as e:
            logger.warning(f"Failed to serialize subject {s.get('id', 'unknown')}: {e}")
    return result

def _serialize_subject(s: dict) -> Optional[SubjectResponse]:
    """Coerce a raw subjects row into the canonical SubjectResponse shape,
    backfilling the `name`/`weekly_periods` aliases the way GET /subjects
    does. Returns None when the row cannot be serialized."""
    if "name" not in s and "name_ar" in s:
        s["name"] = s["name_ar"]
    if "weekly_periods" not in s:
        s["weekly_periods"] = (
            s.get("default_periods_per_week") or s.get("weekly_hours") or 4
        )
    try:
        return SubjectResponse(**s)
    except Exception as e:
        logger.warning(f"Failed to serialize subject {s.get('id', 'unknown')}: {e}")
        return None


@router.get("/teacher/my-subjects", response_model=List[SubjectResponse])
async def get_my_subjects(
    current_user: dict = Depends(
        require_roles([UserRole.TEACHER, UserRole.INDEPENDENT_TEACHER])
    ),
):
    """Return only the subjects the authenticated teacher is authorised to
    teach — the backing query for the session-settings subject dropdown.

    * **School teachers**: JOIN `teacher_assignments` on the canonical
      `(teacher_id, school_id)` derived from the session (never a
      client-supplied id) and return only the distinct *active* subjects
      linked to that teacher. Zero assignments → `[]` (the FE renders a
      safe Arabic empty-state instead of the full catalogue).
    * **Independent teachers**: return the full workspace-scoped subject
      list, because an IT teacher owns every subject in their workspace
      (no per-teacher narrowing applies). This matches the existing
      `/subjects` response for IT callers — no regression.

    Teacher-only: principal/admin callers receive 403 from `require_roles`
    and must keep using the unfiltered `/subjects` route.
    """
    from auth_scope import is_independent_teacher, independent_workspace_id

    if is_independent_teacher(current_user):
        workspace_id = independent_workspace_id(current_user)
        if not workspace_id:
            raise HTTPException(status_code=403, detail="غير مصرح")
        subjects = await gd_find(
            db.session,
            "subjects",
            {"school_id": workspace_id, "is_active": {"$ne": False}},
            limit=1000,
        )
        result = []
        for s in subjects:
            serialized = _serialize_subject(s)
            if serialized is not None:
                result.append(serialized)
        return result

    # School teacher: derive the canonical teacher_id + tenant from the
    # session. Fail closed (empty list) if either is missing.
    teacher_id = current_user.get("teacher_id")
    school_id = current_user.get("tenant_id")
    if not teacher_id or not school_id:
        return []

    assignments = await gd_find(
        db.session,
        "teacher_assignments",
        {"teacher_id": teacher_id, "school_id": school_id, "is_active": {"$ne": False}},
        limit=1000,
    )
    subject_ids = list(
        {a.get("subject_id") for a in assignments if a.get("subject_id")}
    )
    if not subject_ids:
        return []

    subjects = await gd_find(
        db.session,
        "subjects",
        {
            "id": {"$in": subject_ids},
            "school_id": school_id,
            "is_active": {"$ne": False},
        },
        limit=1000,
    )
    result = []
    for s in subjects:
        serialized = _serialize_subject(s)
        if serialized is not None:
            result.append(serialized)
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
    if "weekly_periods" not in subject:
        subject["weekly_periods"] = (
            subject.get("default_periods_per_week") or subject.get("weekly_hours") or 4
        )
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
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    # Only touch the periods column when the caller explicitly provided a
    # value; otherwise an edit that omits weekly_hours would reset the
    # seeded `default_periods_per_week` (a scheduling-constraint input)
    # back to a default. `weekly_hours` is mapped onto the real column.
    if subject_data.weekly_hours is not None:
        update_doc["default_periods_per_week"] = subject_data.weekly_hours
    if subject_data.grade_levels is not None:
        update_doc["applicable_stages"] = subject_data.grade_levels
    # Persist catalog metadata only when explicitly provided, so an edit that
    # omits these fields never clobbers the stored value.
    if subject_data.category is not None:
        update_doc["category"] = subject_data.category
    if subject_data.credits is not None:
        update_doc["credits"] = subject_data.credits
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
    force: bool = False,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.INDEPENDENT_TEACHER])),
    _mfa: dict = Depends(_REQUIRE_RECENT_MFA_403_IT),
):
    """Delete subject (soft delete). Tenant-scoped for non-platform
    callers; cross-workspace ids return 404 (spec §8 inv. 3). Fails
    closed when a non-platform caller has no resolvable tenant.

    Mirrors the `/school/subjects/{id}` dependency-warning pattern
    (Task #289): when the subject is still referenced by classes,
    teacher_assignments, or schedule_sessions in the same workspace,
    returns a `requires_confirmation` envelope instead of soft-deleting.
    The caller must re-issue the request with `?force=true` to proceed.
    """
    from auth_scope import is_independent_teacher, independent_workspace_id
    subject_query = {"id": subject_id}
    scope_school_id = None
    if current_user.get("role") != UserRole.PLATFORM_ADMIN.value:
        caller_tenant = (
            independent_workspace_id(current_user) if is_independent_teacher(current_user)
            else current_user.get("tenant_id")
        )
        if not caller_tenant:
            raise HTTPException(status_code=403, detail="غير مصرح")
        subject_query["school_id"] = caller_tenant
        scope_school_id = caller_tenant
    subject = await gd_find_one(db.session, "subjects", subject_query)
    if not subject:
        raise HTTPException(status_code=404, detail="المادة غير موجودة")

    if not force:
        ref_query_base = {"subject_id": subject_id, "is_active": {"$ne": False}}
        if scope_school_id:
            ref_query_base["school_id"] = scope_school_id
        classes_count = await gd_count(db.session, "classes", ref_query_base)
        assignments_count = await gd_count(db.session, "teacher_assignments", ref_query_base)
        sessions_count = await gd_count(db.session, "schedule_sessions", ref_query_base)
        total = classes_count + assignments_count + sessions_count
        if total > 0:
            return {
                "warning": True,
                "requires_confirmation": True,
                "message": (
                    f"هذه المادة مرتبطة بـ {classes_count} فصل و{assignments_count} "
                    f"إسناد للمعلمين و{sessions_count} حصة. هل تريد الحذف؟"
                ),
                "dependencies": {
                    "classes": classes_count,
                    "teacher_assignments": assignments_count,
                    "schedule_sessions": sessions_count,
                },
            }

    now_iso = datetime.now(timezone.utc).isoformat()
    await gd_update_one(
        db.session,
        "subjects",
        subject_query,
        {"is_active": False, "deleted_at": now_iso, "deleted_by": current_user["id"]},
    )

    audit_log = {
        "id": str(uuid.uuid4()),
        "school_id": subject.get("school_id"),
        "action": "delete",
        "entity_type": "subject",
        "entity_id": subject_id,
        "old_data": {"name": subject.get("name"), "is_active": True},
        "new_data": {"is_active": False, "deleted_at": now_iso, "deleted_by": current_user["id"]},
        "performed_by": current_user["id"],
        "performed_by_name": current_user.get("full_name", ""),
        "timestamp": now_iso,
        "ip_address": None,
    }
    try:
        await gd_insert(db.session, "audit_logs", audit_log)
    except Exception as _audit_err:
        logger.warning(f"Failed to record subject delete audit log: {_audit_err}")

    return {"message": "تم حذف المادة"}


@router.post("/subjects/{subject_id}/restore")
async def restore_subject(
    subject_id: str,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.INDEPENDENT_TEACHER])),
):
    """Restore a soft-deleted subject (Task #645).

    Clears ``is_active=False`` and the ``deleted_at`` / ``deleted_by``
    markers so the row reappears in ``GET /subjects``. Dependent rows
    (classes/teacher_assignments/schedule_sessions) are NOT
    auto-reactivated — the response body lists their inactive counts
    so the UI can prompt the principal to re-link them. Only subjects
    where ``is_active=False`` AND ``deleted_at IS NOT NULL`` are
    restorable. Tenant-scoped for non-platform callers; cross-
    workspace ids return 404 (spec §8 inv. 3).
    """
    from auth_scope import is_independent_teacher, independent_workspace_id
    subject_query: Dict[str, Any] = {
        "id": subject_id,
        "is_active": False,
        "deleted_at": {"$ne": None},
    }
    scope_school_id = None
    if current_user.get("role") != UserRole.PLATFORM_ADMIN.value:
        caller_tenant = (
            independent_workspace_id(current_user) if is_independent_teacher(current_user)
            else current_user.get("tenant_id")
        )
        if not caller_tenant:
            raise HTTPException(status_code=403, detail="غير مصرح")
        subject_query["school_id"] = caller_tenant
        scope_school_id = caller_tenant

    subject = await gd_find_one(db.session, "subjects", subject_query)
    if not subject:
        raise HTTPException(status_code=404, detail="المادة غير موجودة")

    now_iso = datetime.now(timezone.utc).isoformat()
    await gd_update_one(
        db.session,
        "subjects",
        {"id": subject_id},
        {"is_active": True, "deleted_at": None, "deleted_by": None},
    )

    ref_query_base: Dict[str, Any] = {"subject_id": subject_id, "is_active": False}
    if scope_school_id:
        ref_query_base["school_id"] = scope_school_id
    inactive_dependents = {
        "classes": await gd_count(db.session, "classes", ref_query_base),
        "teacher_assignments": await gd_count(db.session, "teacher_assignments", ref_query_base),
        "schedule_sessions": await gd_count(db.session, "schedule_sessions", ref_query_base),
    }

    audit_log = {
        "id": str(uuid.uuid4()),
        "school_id": subject.get("school_id"),
        "action": "restore",
        "entity_type": "subject",
        "entity_id": subject_id,
        "old_data": {
            "name": subject.get("name"),
            "is_active": False,
            "deleted_at": subject.get("deleted_at"),
            "deleted_by": subject.get("deleted_by"),
        },
        "new_data": {"is_active": True, "deleted_at": None, "deleted_by": None},
        "performed_by": current_user["id"],
        "performed_by_name": current_user.get("full_name", ""),
        "timestamp": now_iso,
        "ip_address": None,
    }
    try:
        await gd_insert(db.session, "audit_logs", audit_log)
    except Exception as _audit_err:
        logger.warning(f"Failed to record subject restore audit log: {_audit_err}")

    return {
        "message": "تمت استعادة المادة بنجاح",
        "success": True,
        "inactive_dependents": inactive_dependents,
    }




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
async def delete_school_settings_subject(
    subject_id: str,
    force: bool = False,
    current_user: dict = Depends(require_roles([UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN])),
    x_school_context: str = Header(default=None, alias="X-School-Context")
):
    """Delete subject - حذف مادة دراسية.

    Returns a requires_confirmation envelope when the subject is still
    referenced by active teacher assignments, schedule sessions, or classes,
    and force=False. The caller must re-issue with ?force=true to proceed.
    """
    school_id = await get_school_id_from_context(current_user, x_school_context)

    if not school_id:
        raise HTTPException(status_code=400, detail="School context required")

    subject = await gd_find_one(db.session, "subjects", {"id": subject_id, "tenant_id": school_id})
    if not subject:
        raise HTTPException(status_code=404, detail="المادة غير موجودة")

    if not force:
        ref_query = {"subject_id": subject_id, "is_active": {"$ne": False}, "school_id": school_id}
        classes_count = await gd_count(db.session, "classes", ref_query)
        assignments_count = await gd_count(db.session, "teacher_assignments", ref_query)
        sessions_count = await gd_count(db.session, "schedule_sessions", ref_query)
        total = classes_count + assignments_count + sessions_count
        if total > 0:
            return {
                "warning": True,
                "requires_confirmation": True,
                "message": (
                    f"هذه المادة مرتبطة بـ {classes_count} فصل و{assignments_count} "
                    f"إسناد للمعلمين و{sessions_count} حصة. هل تريد الحذف؟"
                ),
                "dependencies": {
                    "classes": classes_count,
                    "teacher_assignments": assignments_count,
                    "schedule_sessions": sessions_count,
                },
            }

    await gd_update_one(
        db.session, "subjects",
        {"id": subject_id, "tenant_id": school_id},
        {
            "is_active": False,
            "deleted_at": datetime.now(timezone.utc).isoformat(),
            "deleted_by": current_user["id"],
        },
    )

    return {"message": "تم حذف المادة الدراسية"}





