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
) -> None:
    """Reject the request if another active class in the same workspace
    already uses this `name` or `name_en` (case-insensitive, whitespace-
    normalized). Soft-deleted (`is_active=False`) rows are ignored so a
    teacher can re-create a previously deleted class (Task #308).
    Mirrors `_assert_subject_name_unique` in academics_subject_routes.
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
        existing_names = {
            _normalize_class_name(row.get("name")),
            _normalize_class_name(row.get("name_en")),
        }
        if candidates & (existing_names - {""}):
            raise HTTPException(status_code=409, detail="يوجد بالفعل فصل بنفس الاسم")


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
    await _assert_class_name_unique(school_id, class_name, class_name_en)

    # Create class document - use correct field names for ORM model
    class_doc = {
        "id": class_id,
        "school_id": school_id,
        "name": class_name,
        "name_en": class_name_en,
        "grade_id": grade_level.get("id") if grade_level else data.grade_id,
        "grade_level": data.grade_id,
        "capacity": data.capacity,
        "homeroom_teacher_id": data.homeroom_teacher_id,
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
    if data.homeroom_teacher_id:
        teacher = await gd_find_one(db.session, "teachers", {"id": data.homeroom_teacher_id})
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

    await _assert_class_name_unique(school_id, class_data.name, getattr(class_data, 'name_en', None))

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
    school_id: Optional[str] = None,
    grade_level: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """Get all classes or filter by school/grade"""
    query = {}
    if school_id:
        query["school_id"] = school_id
    elif current_user.get("role") != UserRole.PLATFORM_ADMIN.value:
        from auth_scope import independent_workspace_id as _itw_id
        query["school_id"] = current_user.get("tenant_id") or _itw_id(current_user)
    
    if grade_level:
        query["grade_level"] = grade_level
    
    classes = await gd_find(db.session, "classes", query, limit=1000)
    
    # Get teacher names
    teacher_ids = list(set([c.get("homeroom_teacher_id") for c in classes if c.get("homeroom_teacher_id")]))
    teachers = await gd_find(db.session, "teachers", {"id": {"$in": teacher_ids}}, limit=100)
    teacher_map = {t.get("id"): t.get("full_name") or t.get("full_name_ar") for t in teachers}

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
            await _assert_class_name_unique(
                existing.get("school_id"),
                class_data.name if class_data.name is not None else existing.get("name"),
                class_data.name_en if class_data.name_en is not None else existing.get("name_en"),
                exclude_id=class_id,
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
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.INDEPENDENT_TEACHER]))
):
    """Delete class — full removal from system. IT callers are pinned to
    their own workspace (cross-workspace ids return 404)."""
    from auth_scope import is_independent_teacher, independent_workspace_id
    if is_independent_teacher(current_user):
        wsid = independent_workspace_id(current_user)
        class_doc = await gd_find_one(db.session, "classes", {"id": class_id, "school_id": wsid})
    else:
        class_doc = await gd_find_one(db.session, "classes", {"id": class_id})
    if not class_doc:
        raise HTTPException(status_code=404, detail="الفصل غير موجود")
    
    student_count = await gd_count(db.session, "students", {"class_id": class_id, "is_active": {"$ne": False}})
    if student_count > 0:
        raise HTTPException(
            status_code=409,
            detail=f"لا يمكن حذف الفصل لوجود {student_count} طالب مرتبط به. يرجى نقل الطلاب أولاً."
        )
    
    school_id = class_doc.get("school_id")
    cleanup = {}
    await gd_delete_one(db.session, "classes", {"id": class_id})
    r = await gd_delete_many(db.session, "teacher_assignments", {"class_id": class_id})
    cleanup["teacher_assignments"] = r
    r = await gd_delete_many(db.session, "teacher_class_assignments", {"class_id": class_id})
    cleanup["teacher_class_assignments"] = r
    r = await gd_delete_many(db.session, "class_subjects", {"class_id": class_id})
    cleanup["class_subjects"] = r
    r = await gd_delete_many(db.session, "timetable_sessions", {"class_id": class_id})
    cleanup["timetable_sessions"] = r
    r = await gd_delete_many(db.session, "class_sessions", {"class_id": class_id})
    cleanup["class_sessions"] = r
    r = await gd_delete_many(db.session, "attendance", {"class_id": class_id})
    cleanup["attendance"] = r
    r = await gd_delete_many(db.session, "session_attendance", {"class_id": class_id})
    cleanup["session_attendance"] = r
    r = await gd_delete_many(db.session, "assessments", {"class_id": class_id})
    cleanup["assessments"] = r
    r = await gd_delete_many(db.session, "grades", {"class_id": class_id})
    cleanup["grades"] = r
    r = await gd_delete_many(db.session, "behaviour_records", {"class_id": class_id})
    cleanup["behaviour_records"] = r

    return {"message": "تم حذف الفصل وجميع البيانات المرتبطة به بنجاح", "success": True, "cleanup": cleanup}




