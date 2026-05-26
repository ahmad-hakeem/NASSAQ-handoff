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

# Structured 409 for name collisions — clients should key off `code`, not
# substring-match the Arabic `message` (which may be localized later).
DUPLICATE_CLASS_NAME_DETAIL: Dict[str, str] = {
    "message": "يوجد بالفعل فصل بنفس الاسم",
    "code": "duplicate_class_name",
}

# ============== CLASSES ROUTES ==============

def _normalize_class_name(value: Optional[str]) -> str:
    """Normalize a class name for case-insensitive duplicate comparison.

    Trims surrounding whitespace, collapses internal whitespace, and
    case-folds. Returns an empty string for falsy input so the dedupe
    check is a no-op when no name was supplied.
    """
    if not value:
        return ""
    return " ".join(str(value).split()).casefold()


async def _assert_class_name_unique(
    school_id: Optional[str],
    name: Optional[str],
    name_en: Optional[str] = None,
    exclude_id: Optional[str] = None,
    homeroom_teacher_id: Optional[str] = None,
) -> None:
    """Reject the request if another active class in the same school/workspace
    already uses this `name` or `name_en` (case-insensitive, whitespace-
    normalized). Soft-deleted (`is_active=False`) rows are ignored so a
    teacher can re-create a previously deleted class (Task #308).

    When ``homeroom_teacher_id`` is set, only classes assigned to that same
    homeroom teacher participate in the duplicate check (so two different
    teachers in the same school may reuse a label). When it is omitted, the
    check is school-wide (principal wizard / unassigned classes).
    """
    candidates = {n for n in (_normalize_class_name(name), _normalize_class_name(name_en)) if n}
    if not candidates or not school_id:
        return
    existing = await gd_find(
        db.session,
        "classes",
        {"school_id": school_id, "is_active": {"$ne": False}},
        limit=1000,
    )
    for row in existing:
        if exclude_id and row.get("id") == exclude_id:
            continue
        if homeroom_teacher_id:
            row_ht = row.get("homeroom_teacher_id")
            if row_ht != homeroom_teacher_id:
                continue
        existing_names = {
            _normalize_class_name(row.get("name")),
            _normalize_class_name(row.get("name_en")),
        }
        if candidates & (existing_names - {""}):
            raise HTTPException(status_code=409, detail=DUPLICATE_CLASS_NAME_DETAIL)


# Class Wizard Options

class ClassWizardCreate(BaseModel):
    """Class creation via wizard"""
    name: Optional[str] = None
    name_ar: Optional[str] = None  # Support Arabic name from frontend
    name_en: Optional[str] = None
    grade_id: str
    grade: Optional[int] = None  # Can be derived from grade_id
    section: Optional[str] = "أ"  # Default section
    class_type: Optional[str] = "regular"
    capacity: int = 30
    homeroom_teacher_id: Optional[str] = None
    student_ids: List[str] = []
    # Independent-Teacher workspace UI — validated when present (ignored for
    # school principals who use the legacy wizard body).
    subject_id: Optional[str] = None

@router.post("/classes/create")
async def create_class_wizard(
    data: ClassWizardCreate,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.SCHOOL_SUB_ADMIN, UserRole.INDEPENDENT_TEACHER]))
):
    """Create a new class via wizard"""
    # Phase 0 §4.B-1 — canonical workspace-id resolver; IT accounts land
    # in their synthetic `itw_{user_id}` workspace.
    from auth_scope import require_request_school_id, is_independent_teacher, independent_workspace_id
    from quotas.independent_teacher import enforce_class_quota
    school_id = require_request_school_id(current_user)
    # Defensive tenant pin (spec §5.3 step 6): even though the canonical
    # resolver above already returns the IT workspace id from JWT, we
    # double-check here so a future regression that lets the client supply
    # `school_id` cannot smuggle an IT account into another tenant.
    if is_independent_teacher(current_user):
        expected = independent_workspace_id(current_user)
        if school_id != expected:
            raise HTTPException(status_code=403, detail="غير مصرح لك بإنشاء فصل خارج مساحة عملك")
    # Phase 0 §4.B-5 — IT v1 class quota.
    await enforce_class_quota(db.session, current_user)

    # Optional workspace subject (IT create-class dialog). Reject invalid ids
    # early so the client never mis-reads a downstream failure as a duplicate.
    sid_raw = (getattr(data, "subject_id", None) or "").strip()
    if sid_raw:
        sub_row = await gd_find_one(
            db.session,
            "subjects",
            {"id": sid_raw, "school_id": school_id, "is_active": {"$ne": False}},
        )
        if not sub_row:
            raise HTTPException(
                status_code=400,
                detail="معرف المادة غير صالح أو غير موجود في مساحة العمل / Invalid subject for this workspace",
            )
    
    class_id = str(uuid.uuid4())

    # Validate homeroom teacher belongs to same school (tenant isolation)
    if data.homeroom_teacher_id:
        teacher_doc = await gd_find_one(
            db.session, "teachers",
            {"id": data.homeroom_teacher_id, "school_id": school_id}
        )
        if not teacher_doc:
            raise HTTPException(status_code=404, detail="المعلم غير موجود في هذه المدرسة")

    # Get grade level info - try by UUID first, then by code/number
    grade_level = await gd_find_one(db.session, "grade_levels", {"id": data.grade_id, "school_id": school_id})
    if not grade_level:
        grade_level = await gd_find_one(db.session, "grade_levels", {"id": data.grade_id})
    if not grade_level:
        grade_level = await gd_find_one(db.session, "grade_levels", {"code": data.grade_id, "school_id": school_id})
    
    # Derive grade number from grade_level if not provided
    grade_number = data.grade
    if not grade_number and grade_level:
        grade_number = grade_level.get("grade", 1)
    elif not grade_number:
        # Try to extract from grade_id
        try:
            grade_number = int(data.grade_id)
        except (ValueError, TypeError):
            grade_number = 1
    
    # Use name_ar if name is not provided
    class_name = data.name or data.name_ar
    if not class_name:
        grade_name = grade_level.get("name_ar") if grade_level else f"الصف {grade_number}"
        class_name = f"{grade_name} - {data.section or 'أ'}"
    
    grade_name = grade_level.get("name_ar") if grade_level else f"الصف {grade_number}"

    class_name_en = data.name_en or f"Grade {grade_number} - {data.section or 'A'}"
    # Duplicate check must NOT include auto-generated English labels: many
    # distinct Arabic course titles share the same default
    # ``Grade {n} - {section}`` pattern and would false-trigger 409.
    explicit_name_en = (data.name_en or "").strip() or None
    homeroom_for_dedupe: Optional[str] = data.homeroom_teacher_id
    if is_independent_teacher(current_user) and not homeroom_for_dedupe:
        tid = current_user.get("teacher_id")
        if not tid:
            trow = await gd_find_one(
                db.session,
                "teachers",
                {"user_id": current_user.get("id"), "school_id": school_id},
            )
            if trow:
                tid = trow.get("id")
        homeroom_for_dedupe = tid
    await _assert_class_name_unique(
        school_id,
        class_name,
        explicit_name_en,
        homeroom_teacher_id=homeroom_for_dedupe,
    )

    # Create class document - use correct field names for ORM model
    class_doc = {
        "id": class_id,
        "school_id": school_id,
        "name": class_name,
        "name_en": class_name_en,
        "grade_id": grade_level.get("id") if grade_level else data.grade_id,
        "grade_level": data.grade_id,
        "capacity": data.capacity,
        "homeroom_teacher_id": data.homeroom_teacher_id or homeroom_for_dedupe,
        "is_active": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    
    await gd_insert(db.session, "classes", class_doc)
    
    # Assign students to class (enforce tenant isolation via school_id filter)
    if data.student_ids:
        await gd_update_many(
            db.session, "students",
            {"id": {"$in": data.student_ids}, "school_id": school_id},
            {
                "class_id": class_id,
                "grade": data.grade,
                "section": data.section,
            })
    
    # Get homeroom teacher name
    teacher_name = None
    _htid = class_doc.get("homeroom_teacher_id")
    if _htid:
        teacher = await gd_find_one(db.session, "teachers", {"id": _htid})
        if teacher:
            teacher_name = teacher.get("full_name")
    
    return {
        "success": True,
        "class": {
            "id": class_id,
            "name": class_name,
            "grade": grade_number,
            "section": data.section or "أ",
            "capacity": data.capacity,
            "student_count": len(data.student_ids),
            "homeroom_teacher_name": teacher_name,
        },
        "class_id": class_id,
        "message": "تم إنشاء الفصل بنجاح"
    }

@router.post("/classes", response_model=ClassResponse)
async def create_class(
    class_data: ClassCreate,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.SCHOOL_SUB_ADMIN]))
):
    """Create a new class"""
    school_id = getattr(class_data, 'school_id', None) or current_user.get("tenant_id")
    if not school_id:
        raise HTTPException(status_code=400, detail="يجب تحديد المدرسة / School context is required")
    user_tenant = current_user.get("tenant_id")
    if user_tenant and school_id != user_tenant:
        raise HTTPException(status_code=403, detail="لا يمكنك إنشاء فصل في مدرسة أخرى / Cannot create class in another school")

    _raw_en = getattr(class_data, "name_en", None)
    _name_en_chk = (_raw_en.strip() if isinstance(_raw_en, str) else None) or None
    _ht_create = getattr(class_data, "homeroom_teacher_id", None) or getattr(class_data, "class_teacher_id", None)
    await _assert_class_name_unique(
        school_id,
        class_data.name,
        _name_en_chk,
        homeroom_teacher_id=_ht_create,
    )

    class_id = str(uuid.uuid4())
    
    class_doc = {
        "id": class_id,
        "name": class_data.name,
        "name_en": getattr(class_data, 'name_en', None),
        "school_id": school_id,
        "grade_level": getattr(class_data, 'grade_level', None) or getattr(class_data, 'grade', None),
        "section": class_data.section,
        "capacity": class_data.capacity,
        "current_students": 0,
        "homeroom_teacher_id": getattr(class_data, 'homeroom_teacher_id', None) or getattr(class_data, 'class_teacher_id', None),
        "is_active": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    
    await gd_insert(db.session, "classes", class_doc)
    
    # Get homeroom teacher name
    teacher_name = None
    if class_doc["homeroom_teacher_id"]:
        teacher = await gd_find_one(db.session, "teachers", {"id": class_doc["homeroom_teacher_id"]})
        if teacher:
            teacher_name = teacher.get("full_name")
    
    class_doc["homeroom_teacher_name"] = teacher_name
    return ClassResponse(**class_doc)

@router.get("/classes", response_model=List[ClassResponse])
async def get_classes(
    grade_level: Optional[str] = None,
    include_inactive: bool = Query(default=False),
    include_deleted: bool = Query(default=False),
    x_school_context: Optional[str] = Header(default=None, alias="X-School-Context"),
    current_user: dict = Depends(get_current_user)
):
    """Get all classes or filter by school/grade.

    Task #508 / Task #511: Platform admins MUST resolve preview scope
    via the `X-School-Context` header through `resolve_school_id`,
    which only honors the override when the bearer token was minted
    by `/role-switch/switch`. When the resolver returns no school
    context (plain PA token without a header, or a token not minted
    via the hardened role-switch flow), the route now FAILS CLOSED
    and returns an empty list — never an unscoped cross-tenant class
    directory. The legacy `?school_id=` query param is not honored.
    """
    from utils.tenant_scope import resolve_school_id
    query = {}
    if current_user.get("role") == UserRole.PLATFORM_ADMIN.value:
        scoped = resolve_school_id(current_user, x_school_context)
        if not scoped:
            return []
        query["school_id"] = scoped
    else:
        from auth_scope import independent_workspace_id as _itw_id
        scoped = resolve_school_id(current_user, x_school_context)
        query["school_id"] = scoped or current_user.get("tenant_id") or _itw_id(current_user)

    # Task #627 — `include_deleted` exposes soft-deleted rows (is_active=False
    # with deleted_at/deleted_by populated) so admins can audit recent
    # deletions and discover candidates for restoration. Restricted to
    # platform/school admin roles; other callers silently get the active-only
    # view regardless of the param.
    _admin_roles = {
        UserRole.PLATFORM_ADMIN.value,
        UserRole.SCHOOL_PRINCIPAL.value,
        UserRole.SCHOOL_ADMIN.value,
        # Task #631 — IT owns its workspace, so it is the sole party that
        # can restore one of its own soft-deleted classes. Allow it to see
        # the soft-deleted rows in its own workspace.
        UserRole.INDEPENDENT_TEACHER.value,
    }
    show_deleted = bool(include_deleted) and current_user.get("role") in _admin_roles

    if grade_level:
        query["grade_level"] = grade_level

    all_classes = await gd_find(db.session, "classes", query, limit=1000)
    classes = list(all_classes)
    # Filter 1: hide soft-deleted rows (deleted_at IS NOT NULL) unless admin
    # explicitly asked for them via include_deleted.
    if not show_deleted:
        classes = [c for c in classes if c.get("deleted_at") is None]
    # Filter 2: hide genuinely-inactive rows (is_active=False, not deleted)
    # unless the caller asked for them via include_inactive.
    if not include_inactive:
        classes = [c for c in classes if c.get("is_active") is not False]
    
    # Get teacher names
    teacher_ids = list(set([c.get("homeroom_teacher_id") for c in classes if c.get("homeroom_teacher_id")]))
    teachers = await gd_find(db.session, "teachers", {"id": {"$in": teacher_ids}}, limit=100)
    teacher_map = {t.get("id"): t.get("full_name") or t.get("full_name_ar") for t in teachers}

    # Task #631 — when soft-deleted rows are included, resolve a display
    # name for ``deleted_by`` (a users.id) so the "Recently deleted classes"
    # surface can show *who* deleted each class without a follow-up
    # per-row lookup from the frontend.
    deleted_by_map: Dict[str, str] = {}
    if show_deleted:
        deleter_ids = list({c.get("deleted_by") for c in classes if c.get("deleted_by")})
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
                    f"Failed to resolve deleted_by names for classes: {_deleter_err}"
                )
                deleted_by_map = {}

    # Aggregate live student counts per class so the UI cards can render
    # "{student_count} / {capacity} طلاب" and the fill progress instead of
    # always showing 0. Counts only active students assigned to a class,
    # scoped by (school_id, class_id) so tenants never see another school's
    # totals even if class IDs ever collide across tenants.
    from sqlalchemy import select as _sa_select, func as _sa_func, and_ as _sa_and, tuple_ as _sa_tuple
    from pg_models import Student as _PgStudent
    pairs = [(c.get("school_id"), c.get("id")) for c in classes if c.get("id") and c.get("school_id")]
    counts_map: Dict[tuple, int] = {}
    if pairs:
        try:
            count_stmt = (
                _sa_select(
                    _PgStudent.school_id,
                    _PgStudent.class_id,
                    _sa_func.count(_PgStudent.id),
                )
                .where(
                    _sa_and(
                        _PgStudent.is_active == True,
                        _sa_tuple(_PgStudent.school_id, _PgStudent.class_id).in_(pairs),
                    )
                )
                .group_by(_PgStudent.school_id, _PgStudent.class_id)
            )
            count_rows = await db.session.execute(count_stmt)
            counts_map = {
                (sid, cid): int(cnt or 0)
                for sid, cid, cnt in count_rows.all()
                if cid and sid
            }
        except Exception as _agg_err:
            logger.warning(f"Failed to aggregate student counts for classes: {_agg_err}")
            counts_map = {}

    result = []
    for c in classes:
        c["homeroom_teacher_name"] = teacher_map.get(c.get("homeroom_teacher_id"))
        if show_deleted and c.get("deleted_by"):
            c["deleted_by_name"] = deleted_by_map.get(c.get("deleted_by"))
        # Normalize field names - map name_ar to name if needed
        if not c.get("name") and c.get("name_ar"):
            c["name"] = c["name_ar"]
        # Map grade_id to grade_level_id if needed
        if not c.get("grade_level_id") and c.get("grade_id"):
            c["grade_level_id"] = c["grade_id"]
        # Bind aggregated student count to both fields the frontend reads
        live_count = counts_map.get((c.get("school_id"), c.get("id")), 0)
        c["student_count"] = live_count
        c["current_students"] = live_count
        result.append(ClassResponse(**c))
    
    return result

@router.get("/classes/{class_id}", response_model=ClassResponse)
async def get_class(class_id: str, response: Response, current_user: dict = Depends(get_current_user)):
    """Get class by ID"""
    # Bug #372 — class detail header (student_count / capacity bar) is
    # the post-delete refetch target on the class detail page. Disable
    # browser heuristic caching so the live count after DELETE
    # /students/{id} is never served from the disk cache.
    response.headers["Cache-Control"] = "no-store"
    # Tenant scoping (Task #188 security fix): non-platform callers must
    # only be able to read classes inside their own resolved workspace
    # (regular school for affiliated users, `itw_{user_id}` for IT). Any
    # other class id resolves to a clean Arabic 404 — never 200 — so an
    # IT cannot enumerate another tenant's class ids.
    query: Dict[str, Any] = {"id": class_id}
    if current_user.get("role") != UserRole.PLATFORM_ADMIN.value:
        from auth_scope import require_request_school_id
        query["school_id"] = require_request_school_id(current_user)
    class_doc = await gd_find_one(db.session, "classes", query)
    # IT §6.7 (Task #210) — collaborator widening for the named class
    # only. Falls through to a strict 404 if the caller is not a
    # collaborator either, so cross-workspace ids never leak.
    if not class_doc and current_user.get("role") == UserRole.INDEPENDENT_TEACHER.value:
        from utils.collab_access import caller_collab_row_for_class
        row = await caller_collab_row_for_class(db.session, current_user, class_id)
        if row:
            class_doc = await gd_find_one(db.session, "classes", {"id": class_id})
    if not class_doc:
        raise HTTPException(status_code=404, detail="الفصل غير موجود")
    
    teacher_name = None
    teacher_id_resolved = class_doc.get("homeroom_teacher_id")
    if teacher_id_resolved:
        teacher = await gd_find_one(db.session, "teachers", {"id": teacher_id_resolved})
        if teacher:
            teacher_name = teacher.get("full_name")

    # Fallback: if no explicit homeroom is set, use the first assigned teacher
    # from teacher_class_assignments so the principal/teacher views agree with
    # what the assignment screen shows.
    if not teacher_name:
        tca = await gd_find_one(
            db.session,
            "teacher_class_assignments",
            {"class_id": class_id, "is_active": {"$ne": False}},
        )
        if tca and tca.get("teacher_id"):
            teacher = await gd_find_one(db.session, "teachers", {"id": tca["teacher_id"]})
            if teacher:
                teacher_name = teacher.get("full_name")
                if not class_doc.get("homeroom_teacher_id"):
                    class_doc["homeroom_teacher_id"] = teacher.get("id")

    class_doc["homeroom_teacher_name"] = teacher_name

    # Aggregate live student count for this class so detail views stay in
    # sync with the cards on the listing page. Scope by the class's
    # school_id to prevent cross-tenant leakage if class IDs ever collide.
    try:
        from sqlalchemy import select as _sa_select, func as _sa_func, and_ as _sa_and
        from pg_models import Student as _PgStudent
        _scope_school_id = class_doc.get("school_id")
        _conds = [_PgStudent.is_active == True, _PgStudent.class_id == class_id]
        if _scope_school_id:
            _conds.append(_PgStudent.school_id == _scope_school_id)
        single_count = await db.session.execute(
            _sa_select(_sa_func.count(_PgStudent.id)).where(_sa_and(*_conds))
        )
        live_count = int(single_count.scalar() or 0)
    except Exception as _agg_err:
        logger.warning(f"Failed to aggregate student count for class {class_id}: {_agg_err}")
        live_count = int(class_doc.get("student_count") or class_doc.get("current_students") or 0)
    class_doc["student_count"] = live_count
    class_doc["current_students"] = live_count

    return ClassResponse(**class_doc)

@router.put("/classes/{class_id}")
async def update_class(
    class_id: str,
    class_data: ClassUpdate,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.SCHOOL_SUB_ADMIN, UserRole.INDEPENDENT_TEACHER]))
):
    """Update class. IT callers can only touch their own workspace
    (cross-workspace ids return 404 per §8 inv. 3)."""
    from auth_scope import is_independent_teacher, independent_workspace_id
    existing = None
    if is_independent_teacher(current_user):
        wsid = independent_workspace_id(current_user)
        existing = await gd_find_one(db.session, "classes", {"id": class_id, "school_id": wsid})
        if not existing:
            raise HTTPException(status_code=404, detail="الفصل غير موجود")
    if class_data.name is not None or class_data.name_en is not None:
        if existing is None:
            existing = await gd_find_one(db.session, "classes", {"id": class_id})
        if existing:
            _new_name = class_data.name if class_data.name is not None else existing.get("name")
            if class_data.name_en is not None:
                _new_en = class_data.name_en.strip() if isinstance(class_data.name_en, str) else class_data.name_en
            else:
                _new_en = existing.get("name_en")
            _en_for_dedupe = (_new_en.strip() if isinstance(_new_en, str) else None) or None
            # Only treat English as part of the duplicate set when the client
            # explicitly PATCHes name_en; otherwise rely on primary name only
            # so auto-filled English does not widen false positives.
            if class_data.name_en is None:
                _en_for_dedupe = None
            await _assert_class_name_unique(
                existing.get("school_id"),
                _new_name,
                _en_for_dedupe,
                exclude_id=class_id,
                homeroom_teacher_id=existing.get("homeroom_teacher_id"),
            )
    # Build update dict with only provided fields
    update_fields = {"updated_at": datetime.now(timezone.utc).isoformat()}
    
    if class_data.name is not None:
        update_fields["name"] = class_data.name
    if class_data.name_en is not None:
        update_fields["name_en"] = class_data.name_en
    if class_data.grade_level is not None:
        update_fields["grade_level"] = class_data.grade_level
    if class_data.section is not None:
        update_fields["section"] = class_data.section
    if class_data.capacity is not None:
        update_fields["capacity"] = class_data.capacity
    if class_data.homeroom_teacher_id is not None:
        update_fields["homeroom_teacher_id"] = class_data.homeroom_teacher_id
    if class_data.is_active is not None:
        update_fields["is_active"] = class_data.is_active
    
    result = await gd_update_one(db.session, "classes", {"id": class_id}, update_fields)
    if result == 0:
        raise HTTPException(status_code=404, detail="الفصل غير موجود")

    if "name" in update_fields:
        new_name = update_fields["name"]
        await gd_update_many(db.session, "teacher_assignments", {"class_id": class_id}, {"class_name": new_name})
        await gd_update_many(db.session, "schedule_sessions", {"class_id": class_id}, {"class_name": new_name})

    return {"message": "تم تحديث بيانات الفصل", "success": True}

@router.delete("/classes/{class_id}")
async def delete_class(
    class_id: str,
    force: bool = False,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.SCHOOL_SUB_ADMIN, UserRole.INDEPENDENT_TEACHER]))
):
    """Soft-delete a class. Returns a requires_confirmation envelope when
    blocking active records exist and force=False. On force=True, cascades
    soft-deactivation to dependent rows without touching historical records
    (attendance, grades, behaviour_records, assessments).
    IT callers are pinned to their own workspace (cross-workspace ids return 404)."""
    from auth_scope import is_independent_teacher, independent_workspace_id
    if is_independent_teacher(current_user):
        wsid = independent_workspace_id(current_user)
        class_doc = await gd_find_one(db.session, "classes", {"id": class_id, "school_id": wsid, "is_active": {"$ne": False}})
    else:
        class_doc = await gd_find_one(db.session, "classes", {"id": class_id, "is_active": {"$ne": False}})
    if not class_doc:
        raise HTTPException(status_code=404, detail="الفصل غير موجود")

    student_count = await gd_count(db.session, "students", {"class_id": class_id, "is_active": {"$ne": False}})
    if student_count > 0:
        raise HTTPException(
            status_code=409,
            detail=f"لا يمكن حذف الفصل لوجود {student_count} طالب مرتبط به. يرجى نقل الطلاب أولاً."
        )

    teacher_assignments_count = await gd_count(db.session, "teacher_assignments", {"class_id": class_id, "is_active": {"$ne": False}})
    class_subjects_count = await gd_count(db.session, "class_subjects", {"class_id": class_id, "is_active": {"$ne": False}})
    timetable_sessions_count = await gd_count(db.session, "timetable_sessions", {"class_id": class_id, "is_active": {"$ne": False}})

    blocking_count = teacher_assignments_count + class_subjects_count + timetable_sessions_count
    if blocking_count > 0 and not force:
        return {
            "warning": True,
            "requires_confirmation": True,
            "message": (
                f"هذا الفصل مرتبط بـ {teacher_assignments_count} إسناد معلم"
                f"، و{class_subjects_count} مادة دراسية"
                f"، و{timetable_sessions_count} حصة جدولة. هل تريد المتابعة؟"
            ),
            "dependencies": {
                "teacher_assignments": teacher_assignments_count,
                "class_subjects": class_subjects_count,
                "timetable_sessions": timetable_sessions_count,
            },
        }

    now_iso = datetime.now(timezone.utc).isoformat()
    soft_delete_payload = {
        "is_active": False,
        "deleted_at": now_iso,
        "deleted_by": current_user["id"],
    }

    await gd_update_one(db.session, "classes", {"id": class_id}, soft_delete_payload)

    deactivated = {}
    r = await gd_update_many(db.session, "teacher_assignments", {"class_id": class_id, "is_active": {"$ne": False}}, {"is_active": False})
    deactivated["teacher_assignments"] = r
    r = await gd_update_many(db.session, "teacher_class_assignments", {"class_id": class_id, "is_active": {"$ne": False}}, {"is_active": False})
    deactivated["teacher_class_assignments"] = r
    r = await gd_update_many(db.session, "class_subjects", {"class_id": class_id}, {"is_active": False})
    deactivated["class_subjects"] = r
    r = await gd_update_many(db.session, "timetable_sessions", {"class_id": class_id}, {"is_active": False})
    deactivated["timetable_sessions"] = r
    r = await gd_update_many(db.session, "class_sessions", {"class_id": class_id}, {"is_active": False})
    deactivated["class_sessions"] = r
    r = await gd_update_many(db.session, "curriculum_lessons", {"class_id": class_id}, {"is_active": False})
    deactivated["curriculum_lessons"] = r

    school_id = class_doc.get("school_id")
    audit_log = {
        "id": str(uuid.uuid4()),
        "school_id": school_id,
        "action": "delete",
        "entity_type": "class",
        "entity_id": class_id,
        "old_data": {"name": class_doc.get("name"), "is_active": True},
        "new_data": {"is_active": False},
        "performed_by": current_user["id"],
        "performed_by_name": current_user.get("full_name", ""),
        "timestamp": now_iso,
        "ip_address": None,
    }
    await gd_insert(db.session, "audit_logs", audit_log)

    return {
        "message": "تم حذف الفصل بنجاح",
        "success": True,
        "deactivated": deactivated,
    }


@router.post("/classes/{class_id}/restore")
async def restore_class(
    class_id: str,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.SCHOOL_SUB_ADMIN, UserRole.INDEPENDENT_TEACHER]))
):
    """Restore a soft-deleted class. Clears ``is_active=False`` and the
    ``deleted_at`` / ``deleted_by`` markers so the row reappears in
    ``GET /classes``. Dependent rows (teacher_assignments, class_subjects,
    timetable_sessions, class_sessions, curriculum_lessons,
    teacher_class_assignments) are NOT auto-reactivated — the response
    body lists the inactive counts so the UI can prompt the principal to
    re-link them. Only classes where ``is_active=False`` AND
    ``deleted_at IS NOT NULL`` are restorable (a class deactivated for
    other reasons cannot be restored through this endpoint).
    IT callers are pinned to their own workspace (cross-workspace ids
    return 404 per spec §8 inv. 3)."""
    from auth_scope import is_independent_teacher, independent_workspace_id
    base_filter = {"id": class_id, "is_active": False, "deleted_at": {"$ne": None}}
    if is_independent_teacher(current_user):
        wsid = independent_workspace_id(current_user)
        base_filter["school_id"] = wsid
    class_doc = await gd_find_one(db.session, "classes", base_filter)
    if not class_doc:
        raise HTTPException(status_code=404, detail="الفصل غير موجود")

    now_iso = datetime.now(timezone.utc).isoformat()
    restore_payload = {
        "is_active": True,
        "deleted_at": None,
        "deleted_by": None,
    }
    await gd_update_one(db.session, "classes", {"id": class_id}, restore_payload)

    inactive_dependents = {
        "teacher_assignments": await gd_count(db.session, "teacher_assignments", {"class_id": class_id, "is_active": False}),
        "teacher_class_assignments": await gd_count(db.session, "teacher_class_assignments", {"class_id": class_id, "is_active": False}),
        "class_subjects": await gd_count(db.session, "class_subjects", {"class_id": class_id, "is_active": False}),
        "timetable_sessions": await gd_count(db.session, "timetable_sessions", {"class_id": class_id, "is_active": False}),
        "class_sessions": await gd_count(db.session, "class_sessions", {"class_id": class_id, "is_active": False}),
        "curriculum_lessons": await gd_count(db.session, "curriculum_lessons", {"class_id": class_id, "is_active": False}),
    }

    school_id = class_doc.get("school_id")
    audit_log = {
        "id": str(uuid.uuid4()),
        "school_id": school_id,
        "action": "restore",
        "entity_type": "class",
        "entity_id": class_id,
        "old_data": {
            "name": class_doc.get("name"),
            "is_active": False,
            "deleted_at": class_doc.get("deleted_at"),
            "deleted_by": class_doc.get("deleted_by"),
        },
        "new_data": {"is_active": True, "deleted_at": None, "deleted_by": None},
        "performed_by": current_user["id"],
        "performed_by_name": current_user.get("full_name", ""),
        "timestamp": now_iso,
        "ip_address": None,
    }
    await gd_insert(db.session, "audit_logs", audit_log)

    return {
        "message": "تمت استعادة الفصل بنجاح",
        "success": True,
        "inactive_dependents": inactive_dependents,
    }


# ---- Re-link wizard ----------------------------------------------------------
#
# After restoring a soft-deleted class, the principal needs a way to selectively
# reactivate the dependent rows that were soft-deleted alongside it. The class
# itself must already be active before any of these endpoints will operate
# (otherwise the principal must restore it first via /classes/{id}/restore).
#
# All endpoints below:
#   - require an active class (404 if missing or still deleted)
#   - pin Independent-Teacher callers to their own workspace (spec §8 inv. 3)
#   - flip is_active back to True ONLY for rows whose class_id matches the
#     just-restored class, optionally narrowed by an explicit ids list
#   - emit a single audit_logs row per call describing what was reactivated
#
# Task #644 also adds the all-tables convenience route
# POST /classes/{id}/reactivate-dependents (defined below) which is what the
# post-restore NassaqAlertDialog's "Reactivate linked items" button calls.

_RELINK_TABLES = {
    "teacher_assignments",
    "teacher_class_assignments",
    "class_subjects",
    "timetable_sessions",
    "class_sessions",
    "curriculum_lessons",
}


@router.post("/classes/{class_id}/reactivate-dependents")
async def reactivate_class_dependents(
    class_id: str,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.SCHOOL_SUB_ADMIN, UserRole.INDEPENDENT_TEACHER]))
):
    """Task #644 — re-activate every inactive dependent row attached to
    ``class_id`` in one shot (teacher_assignments,
    teacher_class_assignments, class_subjects, timetable_sessions,
    class_sessions, curriculum_lessons). This is the all-tables
    convenience route invoked by the post-restore dialog's "Reactivate
    linked items" button; the per-table ``/relink/<table>`` wizard
    routes below are the granular alternative.

    The class itself must already be active — callers are expected to
    hit ``POST /classes/{id}/restore`` first. Returns the per-table
    reactivated counts and the remaining inactive counts. Tenant-scoped
    via ``_load_active_class_for_relink`` (IT callers are pinned to
    their own workspace; cross-workspace ids return 404 per spec §8
    inv. 3)."""
    class_doc = await _load_active_class_for_relink(class_id, current_user)

    now_iso = datetime.now(timezone.utc).isoformat()
    reactivated: Dict[str, int] = {}
    for table in _RELINK_TABLES:
        count = await gd_update_many(
            db.session,
            table,
            {"class_id": class_id, "is_active": False},
            {"is_active": True},
        )
        reactivated[table] = int(count or 0)

    remaining_inactive: Dict[str, int] = {}
    for table in _RELINK_TABLES:
        remaining_inactive[table] = await gd_count(
            db.session, table, {"class_id": class_id, "is_active": False}
        )

    audit_log = {
        "id": str(uuid.uuid4()),
        "school_id": class_doc.get("school_id"),
        "action": "reactivate_dependents",
        "entity_type": "class",
        "entity_id": class_id,
        "old_data": None,
        "new_data": {"reactivated": reactivated},
        "performed_by": current_user["id"],
        "performed_by_name": current_user.get("full_name", ""),
        "timestamp": now_iso,
        "ip_address": None,
    }
    await gd_insert(db.session, "audit_logs", audit_log)

    return {
        "message": "تمت إعادة تفعيل العناصر المرتبطة بنجاح",
        "success": True,
        "reactivated": reactivated,
        "inactive_dependents": remaining_inactive,
    }


async def _load_active_class_for_relink(class_id: str, current_user: dict) -> dict:
    from auth_scope import is_independent_teacher, independent_workspace_id
    base_filter: Dict[str, Any] = {"id": class_id, "is_active": True}
    if is_independent_teacher(current_user):
        base_filter["school_id"] = independent_workspace_id(current_user)
    class_doc = await gd_find_one(db.session, "classes", base_filter)
    if not class_doc:
        raise HTTPException(status_code=404, detail="الفصل غير موجود")
    return class_doc


def _candidate_label(table: str, row: Dict[str, Any]) -> Dict[str, Any]:
    """Pick a small set of attributes that the wizard can display per row."""
    base = {"id": row.get("id")}
    if table == "teacher_assignments":
        base.update({
            "teacher_id": row.get("teacher_id"),
            "teacher_name": row.get("teacher_name"),
            "subject_id": row.get("subject_id"),
            "subject_name": row.get("subject_name"),
            "weekly_sessions": row.get("weekly_sessions") or row.get("periods_per_week"),
        })
    elif table == "teacher_class_assignments":
        base.update({
            "teacher_id": row.get("teacher_id"),
            "teacher_name": row.get("teacher_name"),
        })
    elif table == "class_subjects":
        base.update({
            "subject_id": row.get("subject_id"),
            "subject_name": row.get("subject_name"),
            "weekly_periods": row.get("weekly_periods") or row.get("weekly_sessions"),
        })
    elif table == "timetable_sessions":
        base.update({
            "day_of_week": row.get("day_of_week"),
            "period_number": row.get("period_number"),
            "teacher_id": row.get("teacher_id"),
            "subject_id": row.get("subject_id"),
        })
    elif table == "class_sessions":
        base.update({
            "date": row.get("date"),
            "subject_id": row.get("subject_id"),
            "status": row.get("status"),
        })
    elif table == "curriculum_lessons":
        base.update({
            "title": row.get("title"),
            "week": row.get("week"),
            "subject_id": row.get("subject_id"),
        })
    return base


@router.get("/classes/{class_id}/relink-candidates")
async def list_relink_candidates(
    class_id: str,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.SCHOOL_SUB_ADMIN, UserRole.INDEPENDENT_TEACHER])),
):
    """List inactive dependents for a just-restored class, grouped by table.

    Powers the "Re-link previous assignments" wizard. The class must already
    be active (typically immediately after POST /classes/{id}/restore).
    Returns up to 200 rows per group with the minimum attributes needed to
    render a row label."""
    await _load_active_class_for_relink(class_id, current_user)
    preview_limit = 200
    groups: Dict[str, Dict[str, Any]] = {}
    for table in _RELINK_TABLES:
        filt = {"class_id": class_id, "is_active": False}
        total = await gd_count(db.session, table, filt)
        rows = await gd_find(db.session, table, filt, limit=preview_limit) if total > 0 else []
        groups[table] = {
            # `count` is the true number of inactive dependents for this table;
            # `items` is a bounded preview the wizard can render. The wizard
            # still uses the "Reactivate all" path (server-side filter) to
            # cover anything past the preview window.
            "count": total,
            "preview_limit": preview_limit,
            "items": [_candidate_label(table, r) for r in rows],
        }
    return {"class_id": class_id, "groups": groups}


class RelinkRequest(BaseModel):
    ids: Optional[List[str]] = None
    all: bool = False

    model_config = ConfigDict(extra="forbid")


async def _reactivate_dependents(
    class_id: str,
    table: str,
    payload: RelinkRequest,
    current_user: dict,
) -> Dict[str, Any]:
    if table not in _RELINK_TABLES:
        raise HTTPException(status_code=404, detail="نوع غير مدعوم")
    class_doc = await _load_active_class_for_relink(class_id, current_user)

    filters: Dict[str, Any] = {"class_id": class_id, "is_active": False}
    if not payload.all:
        ids = [i for i in (payload.ids or []) if isinstance(i, str) and i]
        if not ids:
            raise HTTPException(status_code=400, detail="لم يتم تحديد أي عناصر")
        filters["id"] = {"$in": ids}

    reactivated = await gd_update_many(
        db.session, table, filters, {"is_active": True}
    )

    now_iso = datetime.now(timezone.utc).isoformat()
    audit_log = {
        "id": str(uuid.uuid4()),
        "school_id": class_doc.get("school_id"),
        "action": "relink",
        "entity_type": table,
        "entity_id": class_id,
        "old_data": {"is_active": False},
        "new_data": {
            "is_active": True,
            "scope": "all" if payload.all else "selected",
            "selected_ids": None if payload.all else (payload.ids or []),
            "reactivated": reactivated,
        },
        "performed_by": current_user["id"],
        "performed_by_name": current_user.get("full_name", ""),
        "timestamp": now_iso,
        "ip_address": None,
    }
    await gd_insert(db.session, "audit_logs", audit_log)

    return {
        "success": True,
        "table": table,
        "class_id": class_id,
        "reactivated": reactivated,
    }


@router.post("/classes/{class_id}/relink/teacher_assignments")
async def relink_teacher_assignments(
    class_id: str,
    payload: RelinkRequest = Body(...),
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.SCHOOL_SUB_ADMIN, UserRole.INDEPENDENT_TEACHER])),
):
    return await _reactivate_dependents(class_id, "teacher_assignments", payload, current_user)


@router.post("/classes/{class_id}/relink/teacher_class_assignments")
async def relink_teacher_class_assignments(
    class_id: str,
    payload: RelinkRequest = Body(...),
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.SCHOOL_SUB_ADMIN, UserRole.INDEPENDENT_TEACHER])),
):
    return await _reactivate_dependents(class_id, "teacher_class_assignments", payload, current_user)


@router.post("/classes/{class_id}/relink/class_subjects")
async def relink_class_subjects(
    class_id: str,
    payload: RelinkRequest = Body(...),
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.SCHOOL_SUB_ADMIN, UserRole.INDEPENDENT_TEACHER])),
):
    return await _reactivate_dependents(class_id, "class_subjects", payload, current_user)


@router.post("/classes/{class_id}/relink/timetable_sessions")
async def relink_timetable_sessions(
    class_id: str,
    payload: RelinkRequest = Body(...),
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.SCHOOL_SUB_ADMIN, UserRole.INDEPENDENT_TEACHER])),
):
    return await _reactivate_dependents(class_id, "timetable_sessions", payload, current_user)


@router.post("/classes/{class_id}/relink/class_sessions")
async def relink_class_sessions(
    class_id: str,
    payload: RelinkRequest = Body(...),
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.SCHOOL_SUB_ADMIN, UserRole.INDEPENDENT_TEACHER])),
):
    return await _reactivate_dependents(class_id, "class_sessions", payload, current_user)


@router.post("/classes/{class_id}/relink/curriculum_lessons")
async def relink_curriculum_lessons(
    class_id: str,
    payload: RelinkRequest = Body(...),
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.SCHOOL_SUB_ADMIN, UserRole.INDEPENDENT_TEACHER])),
):
    return await _reactivate_dependents(class_id, "curriculum_lessons", payload, current_user)
