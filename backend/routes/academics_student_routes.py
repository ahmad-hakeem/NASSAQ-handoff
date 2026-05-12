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
    REPORT_TYPES, generate_student_qr_code,
    require_recent_mfa_403_if_independent_teacher,
)
from engines.sql_utils import gd_find, gd_find_one, gd_insert, gd_insert_many, gd_update_one, gd_update_many, gd_count, gd_delete_one, gd_delete_many, gd_distinct, _gd_inc, _gd_pull, _gd_push, _gd_addtoset
from auth_scope import require_request_school_id


from shared_models import (
    TeacherCreate, TeacherUpdate, TeacherResponse, StudentCreate, StudentUpdate, StudentResponse, ClassCreate, ClassUpdate, ClassResponse, SubjectCreate, SubjectResponse
)

router = APIRouter()

# Task #201 — IT §5.7 step-up backfill on student contact-field
# mutations. Conditional on caller role so principal/admin/sub-admin
# behaviour on PUT /students/{id} is preserved.
_REQUIRE_RECENT_MFA_403_IT = require_recent_mfa_403_if_independent_teacher()


async def get_school_id_from_context(current_user: dict, x_school_context: str = None) -> str:
    """Resolve school_id from header, with strict tenant isolation.

    Delegates to `utils.tenant_scope.resolve_school_id` so that non-platform
    callers can never address another school's data via the X-School-Context
    header (mismatched override → 403). Platform admins retain free override.
    """
    from utils.tenant_scope import resolve_school_id
    return resolve_school_id(current_user, x_school_context)


# Local `_independent_workspace_id` / `_scoped_school_id` helpers were
# removed in Phase 0 §4.B-1 of the Independent-Teacher spec. Use
# `auth_scope.independent_workspace_id` / `require_request_school_id`.

# ============== STUDENTS ROUTES ==============
@router.post("/students", response_model=StudentResponse)
async def create_student(
    student_data: StudentCreate,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.SCHOOL_SUB_ADMIN]))
):
    """Create a new student"""
    school_id = getattr(student_data, 'school_id', None) or current_user.get("tenant_id")
    if not school_id:
        raise HTTPException(status_code=400, detail="يجب تحديد المدرسة / School context is required")
    user_tenant = current_user.get("tenant_id")
    if user_tenant and school_id != user_tenant:
        raise HTTPException(status_code=403, detail="لا يمكنك إنشاء طالب في مدرسة أخرى / Cannot create student in another school")

    student_id = str(uuid.uuid4())
    
    student_doc = {
        "id": student_id,
        "user_id": None,
        "full_name": student_data.full_name,
        "full_name_en": getattr(student_data, 'full_name_en', None),
        "email": student_data.email,
        "phone": student_data.phone,
        "school_id": school_id,
        "class_id": student_data.class_id,
        "student_number": student_data.student_number,
        "date_of_birth": getattr(student_data, 'date_of_birth', None),
        "gender": getattr(student_data, 'gender', None),
        "parent_phone": student_data.parent_phone,
        "parent_name": student_data.parent_name,
        "talents": getattr(student_data, 'talents', []) or [],
        "character_traits": getattr(student_data, 'character_traits', []) or [],
        "is_gifted": len(getattr(student_data, 'talents', []) or []) > 0 or bool(getattr(student_data, 'is_gifted', False)),
        "is_active": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    
    await gd_insert(db.session, "students", student_doc)
    
    await _gd_inc(db.session, "schools", {"id": student_doc["school_id"]}, {"current_students": 1})
    
    if student_data.class_id:
        await _gd_inc(db.session, "classes", {"id": student_data.class_id}, {"current_students": 1})
    
    await audit_engine.log(
        action=AuditAction.USER_CREATED.value,
        performed_by=current_user.get("id"),
        tenant_id=student_doc["school_id"],
        entity_type="student",
        entity_id=student_id,
        details={
            "full_name": student_data.full_name,
            "school_id": student_doc["school_id"],
            "class_id": student_data.class_id,
        },
        actor_name=current_user.get("full_name"),
        actor_role=current_user.get("role"),
        actor_email=current_user.get("email"),
    )
    
    class_name = None
    if student_data.class_id:
        class_doc = await gd_find_one(db.session, "classes", {"id": student_data.class_id})
        if class_doc:
            class_name = class_doc.get("name")
    
    return StudentResponse(**student_doc, class_name=class_name)

@router.get("/students", response_model=List[StudentResponse])
async def get_students(
    school_id: Optional[str] = None,
    class_id: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """Get all students or filter by school/class"""
    query = {"is_active": {"$ne": False}}
    if current_user.get("role") == UserRole.PLATFORM_ADMIN.value:
        if school_id:
            query["school_id"] = school_id
    else:
        query["school_id"] = current_user.get("tenant_id")
    
    if class_id:
        query["class_id"] = class_id
    
    students = await gd_find(db.session, "students", query, limit=1000)
    
    # Get class names
    class_ids = list(set([s.get("class_id") for s in students if s.get("class_id")]))
    classes = await gd_find(db.session, "classes", {"id": {"$in": class_ids}}, limit=100)
    class_map = {c.get("id"): c.get("name") or c.get("name_ar") for c in classes}
    
    result = []
    for s in students:
        s["class_name"] = class_map.get(s.get("class_id"))
        # Normalize field names - map full_name_ar to full_name if needed
        if not s.get("full_name") and s.get("full_name_ar"):
            s["full_name"] = s["full_name_ar"]
        result.append(StudentResponse(**s))
    
    return result

@router.get("/classes/options/grades")
async def get_class_grades_options(current_user: dict = Depends(require_roles([
    UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN,
    UserRole.SCHOOL_SUB_ADMIN, UserRole.TEACHER, UserRole.INDEPENDENT_TEACHER
]))):
    """Get available grade levels for class creation"""
    # Task #155: fail-closed school-id resolution; see audit row #10.
    school_id = require_request_school_id(current_user)

    grades = await gd_find(db.session, "grade_levels", {"school_id": school_id}, limit=100)
    
    result_grades = []
    for g in grades:
        result_grades.append({
            "id": g.get("id", g.get("_id", "")),
            "name_ar": g.get("name_ar") or g.get("name", ""),
            "name_en": g.get("name_en", ""),
            "grade": g.get("grade"),
            "stage": g.get("stage"),
            "stage_id": g.get("stage_id")
        })
    
    if not result_grades:
        grade_levels = await gd_distinct(db.session, "students", "grade_level", {"school_id": school_id, "is_active": {"$ne": False}})
        grade_levels = sorted([g for g in grade_levels if g], key=lambda x: int(x) if x.isdigit() else 999)
        grade_names = {
            "1": ("الصف الأول", "Grade 1"), "2": ("الصف الثاني", "Grade 2"),
            "3": ("الصف الثالث", "Grade 3"), "4": ("الصف الرابع", "Grade 4"),
            "5": ("الصف الخامس", "Grade 5"), "6": ("الصف السادس", "Grade 6"),
            "7": ("الصف السابع", "Grade 7"), "8": ("الصف الثامن", "Grade 8"),
            "9": ("الصف التاسع", "Grade 9"), "10": ("الصف العاشر", "Grade 10"),
            "11": ("الصف الحادي عشر", "Grade 11"), "12": ("الصف الثاني عشر", "Grade 12"),
        }
        if not grade_levels:
            grade_levels = [str(i) for i in range(1, 13)]
        for gl in grade_levels:
            names = grade_names.get(gl, (f"الصف {gl}", f"Grade {gl}"))
            result_grades.append({"id": gl, "name_ar": names[0], "name_en": names[1], "grade": int(gl) if gl.isdigit() else None, "stage": "ابتدائي" if gl.isdigit() and int(gl) <= 6 else "متوسط/ثانوي"})

    return {"grades": result_grades}

@router.get("/classes/options/teachers")
async def get_class_teachers_options(current_user: dict = Depends(require_roles([
    UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN,
    UserRole.SCHOOL_SUB_ADMIN, UserRole.TEACHER, UserRole.INDEPENDENT_TEACHER
]))):
    """Get available teachers for homeroom assignment"""
    # Task #155 (audit row #16, post-review): fail-closed scope. The previous
    # `if school_id else {}` form returned every tenant's teachers when scope
    # could not be resolved.
    school_id = require_request_school_id(current_user)

    teachers = await gd_find(db.session, "teachers", {"school_id": school_id, "is_active": {"$ne": False}}, limit=200)
    
    result_teachers = []
    for t in teachers:
        result_teachers.append({
            "teacher_id": t.get("teacher_id") or t.get("id", ""),
            "full_name_ar": t.get("full_name_ar") or t.get("name_ar") or t.get("full_name") or t.get("name", ""),
            "full_name_en": t.get("full_name_en", ""),
            "specialization": t.get("specialization", ""),
            "email": t.get("email", "")
        })
    
    return {"teachers": result_teachers}

@router.get("/classes/options/students")
async def get_class_students_options(current_user: dict = Depends(require_roles([
    UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN,
    UserRole.SCHOOL_SUB_ADMIN, UserRole.TEACHER, UserRole.INDEPENDENT_TEACHER
]))):
    """Get available students for class assignment"""
    # Task #155 (audit row #17, post-review): fail-closed scope. The previous
    # `if school_id else {}` form returned every tenant's students when scope
    # could not be resolved.
    school_id = require_request_school_id(current_user)

    query = {"school_id": school_id, "is_active": {"$ne": False}}
    students = await gd_find(db.session, "students", query, limit=500)
    
    result_students = []
    for s in students:
        result_students.append({
            "student_id": s.get("student_id") or s.get("id", ""),
            "full_name_ar": s.get("full_name_ar") or s.get("full_name", ""),
            "full_name_en": s.get("full_name_en", ""),
            "student_number": s.get("student_number", ""),
            "grade_id": s.get("grade_id") or (f"grade_{s.get('grade_level')}" if s.get("grade_level") else ""),
            "grade_level": s.get("grade_level", ""),
            "class_id": s.get("class_id")
        })
    
    return {"students": result_students}

@router.get("/classes/options/class-types")
async def get_class_types_options(current_user: dict = Depends(get_current_user)):
    """Get available class types"""
    types = [
        {"code": "regular", "name_ar": "عادي", "name_en": "Regular"},
        {"code": "advanced", "name_ar": "متقدم", "name_en": "Advanced"},
        {"code": "special", "name_ar": "تربية خاصة", "name_en": "Special Education"},
        {"code": "gifted", "name_ar": "موهوبين", "name_en": "Gifted"},
    ]
    return {"types": types}

@router.get("/classes/{class_id}/students", response_model=List[StudentResponse])
async def get_class_students(
    class_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get all students in a specific class"""
    query = {"class_id": class_id, "is_active": True}
    if current_user.get("role") != UserRole.PLATFORM_ADMIN.value:
        tenant = current_user.get("tenant_id")
        if tenant:
            query["school_id"] = tenant

    students = await gd_find(db.session, "students", query, limit=1000)

    cls = await gd_find_one(db.session, "classes", {"id": class_id})
    class_name = cls.get("name") if cls else None

    students_missing_parent = [s["id"] for s in students if not s.get("parent_id") and s.get("parent_phone")]
    parent_lookup = {}
    if students_missing_parent:
        parent_links = await gd_find(db.session, "parent_student_links", {"student_id": {"$in": students_missing_parent}}, limit=500)
        for link in parent_links:
            parent_lookup[link["student_id"]] = link.get("parent_id")
        if not parent_lookup:
            parent_users = await gd_find(db.session, "users", {"role": "parent", "student_ids": {"$in": students_missing_parent}}, limit=500)
            for pu in parent_users:
                for sid in (pu.get("student_ids") or []):
                    if sid in students_missing_parent:
                        parent_lookup[sid] = pu["id"]

    result = []
    for s in students:
        s["class_name"] = class_name
        if not s.get("full_name") and s.get("full_name_ar"):
            s["full_name"] = s["full_name_ar"]
        if hasattr(s.get("created_at"), "isoformat"):
            s["created_at"] = s["created_at"].isoformat()
        if not s.get("parent_id") and s["id"] in parent_lookup:
            s["parent_id"] = parent_lookup[s["id"]]
        result.append(StudentResponse(**s))

    return result


@router.get("/students/me", response_model=StudentResponse)
async def get_my_student_profile(current_user: dict = Depends(get_current_user)):
    """E-03: Return the student row associated with the logged-in user.
    Resolution order: enriched JWT student_id → email → phone → national_id."""
    student = None
    sid = current_user.get("student_id")
    if sid:
        student = await gd_find_one(db.session, "students", {"id": sid})

    # Tenant-scoped fallback lookups to prevent cross-tenant resolution.
    def _scoped(field, value):
        q = {field: value}
        if current_user.get("tenant_id"):
            q["school_id"] = current_user.get("tenant_id")
        return q

    if not student and current_user.get("email"):
        student = await gd_find_one(db.session, "students", _scoped("email", current_user.get("email")))
    if not student and current_user.get("phone"):
        student = await gd_find_one(db.session, "students", _scoped("phone", current_user.get("phone")))
    if not student and current_user.get("national_id"):
        student = await gd_find_one(db.session, "students", _scoped("national_id", current_user.get("national_id")))
    if not student:
        raise HTTPException(status_code=404, detail="لا يوجد ملف طالب مرتبط بالحساب")
    # Defensive cross-tenant guard.
    if current_user.get("tenant_id") and student.get("school_id") and student.get("school_id") != current_user.get("tenant_id"):
        raise HTTPException(status_code=404, detail="لا يوجد ملف طالب مرتبط بالحساب")

    class_name = None
    if student.get("class_id"):
        class_doc = await gd_find_one(db.session, "classes", {"id": student.get("class_id")})
        if class_doc:
            class_name = class_doc.get("name") or class_doc.get("name_ar")
    if not student.get("full_name") and student.get("full_name_ar"):
        student["full_name"] = student["full_name_ar"]
    student["class_name"] = class_name
    return StudentResponse(**student)


@router.get("/students/{student_id}", response_model=StudentResponse)
async def get_student(student_id: str, current_user: dict = Depends(get_current_user)):
    """Get student by ID"""
    student = await gd_find_one(db.session, "students", {"id": student_id})
    if not student:
        raise HTTPException(status_code=404, detail="الطالب غير موجود")

    if current_user.get("role") != UserRole.PLATFORM_ADMIN.value:
        # Resolve the caller's effective workspace id; for IT this is
        # the synthetic `itw_{user_id}`. Cross-tenant lookups MUST 404
        # (not 403) so the route never confirms the existence of a
        # student in another tenant — see #192 spec §5.6.
        from auth_scope import independent_workspace_id
        user_school = current_user.get("tenant_id") or independent_workspace_id(current_user)
        student_school = student.get("school_id")
        if user_school and student_school and student_school != user_school:
            raise HTTPException(status_code=404, detail="الطالب غير موجود")
    
    class_name = None
    if student.get("class_id"):
        class_doc = await gd_find_one(db.session, "classes", {"id": student.get("class_id")})
        if class_doc:
            class_name = class_doc.get("name") or class_doc.get("name_ar")
    
    # Normalize field names
    if not student.get("full_name") and student.get("full_name_ar"):
        student["full_name"] = student["full_name_ar"]
    
    student["class_name"] = class_name
    return StudentResponse(**student)

@router.put("/students/{student_id}")
async def update_student(
    student_id: str,
    student_data: StudentUpdate,
    # Task #201 — IT §5.7 widens this allow-list to include
    # INDEPENDENT_TEACHER so IT callers can manage students inside their
    # own workspace. Non-IT roles see exactly the same allow-list as
    # before. The MFA step-up gate below is IT-conditional, so non-IT
    # behaviour is byte-for-byte unchanged.
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.SCHOOL_SUB_ADMIN, UserRole.INDEPENDENT_TEACHER])),
    _mfa: dict = Depends(_REQUIRE_RECENT_MFA_403_IT),
):
    """Update student"""
    # Task #201 — fall back to the synthetic IT workspace id so the
    # tenant filter scopes correctly for Independent-Teacher callers
    # (their `users.tenant_id` is NULL by design).
    from auth_scope import independent_workspace_id as _itw_id
    school_id = current_user.get("tenant_id") or _itw_id(current_user)
    query = {"id": student_id}
    if school_id:
        query["school_id"] = school_id

    existing = await gd_find_one(db.session, "students", query)
    if not existing:
        raise HTTPException(status_code=404, detail="الطالب غير موجود")

    update_fields = {"updated_at": datetime.now(timezone.utc).isoformat()}
    
    if student_data.full_name is not None:
        update_fields["full_name"] = student_data.full_name
    if student_data.full_name_en is not None:
        update_fields["full_name_en"] = student_data.full_name_en
    if student_data.email is not None:
        update_fields["email"] = student_data.email
    if student_data.phone is not None:
        update_fields["phone"] = student_data.phone
    if student_data.grade is not None:
        update_fields["grade"] = student_data.grade
    if student_data.class_id is not None:
        update_fields["class_id"] = student_data.class_id
    if student_data.date_of_birth is not None:
        update_fields["date_of_birth"] = student_data.date_of_birth
    if student_data.gender is not None:
        update_fields["gender"] = student_data.gender
    if student_data.parent_phone is not None:
        update_fields["parent_phone"] = student_data.parent_phone
    if student_data.parent_name is not None:
        update_fields["parent_name"] = student_data.parent_name
    if student_data.talents is not None:
        update_fields["talents"] = student_data.talents
        update_fields["is_gifted"] = len(student_data.talents) > 0
    elif student_data.is_gifted is not None:
        update_fields["is_gifted"] = student_data.is_gifted
    if student_data.character_traits is not None:
        update_fields["character_traits"] = student_data.character_traits
    if student_data.is_active is not None:
        update_fields["is_active"] = student_data.is_active
    
    result = await gd_update_one(db.session, "students", query, update_fields)
    if result == 0:
        raise HTTPException(status_code=404, detail="الطالب غير موجود")
    
    await audit_engine.log(
        action=AuditAction.USER_UPDATED.value,
        performed_by=current_user.get("id"),
        tenant_id=school_id,
        entity_type="student",
        entity_id=student_id,
        details={"updated_fields": list(update_fields.keys())},
        actor_name=current_user.get("full_name"),
        actor_role=current_user.get("role"),
        actor_email=current_user.get("email"),
    )
    
    return {"message": "تم تحديث بيانات الطالب وحفظها في قاعدة البيانات بنجاح", "success": True}

# FIX (C13): Validate the transfer payload via Pydantic instead of pulling
# raw values out of `request.json()`. The previous implementation accepted any
# shape and only checked for missing keys after parsing.
class ClassTransferRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    student_id: str = Field(..., min_length=1, max_length=64)
    target_class_id: str = Field(..., min_length=1, max_length=64)


@router.post("/students/transfer-class")
async def transfer_student_class(
    payload: ClassTransferRequest,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN]))
):
    student_id = payload.student_id
    target_class_id = payload.target_class_id

    school_id = current_user.get("tenant_id") or current_user.get("school_id")
    if not school_id:
        raise HTTPException(status_code=400, detail="سياق المدرسة مطلوب")

    student = await gd_find_one(db.session, "students", {"id": student_id, "school_id": school_id})
    if not student:
        raise HTTPException(status_code=404, detail="الطالب غير موجود")

    target_class = await gd_find_one(db.session, "classes", {"id": target_class_id, "school_id": school_id})
    if not target_class:
        raise HTTPException(status_code=404, detail="الفصل المستهدف غير موجود")

    old_class_id = student.get("class_id")
    if old_class_id == target_class_id:
        return {"success": True, "message": "الطالب موجود بالفعل في هذا الفصل"}

    now = datetime.now(timezone.utc).isoformat()
    await gd_update_one(db.session, "students", {"id": student_id, "school_id": school_id}, {
            "class_id": target_class_id,
            "class_name": target_class.get("name_ar") or target_class.get("name", ""),
            "updated_at": now
        })

    if old_class_id:
        await _gd_pull(db.session, "classes", {"id": old_class_id, "school_id": school_id}, {"student_ids": student_id})
        await _gd_inc(db.session, "classes", {"id": old_class_id, "school_id": school_id}, {"student_count": -1})

    await _gd_addtoset(db.session, "classes", {"id": target_class_id, "school_id": school_id}, {"student_ids": student_id})
    await _gd_inc(db.session, "classes", {"id": target_class_id, "school_id": school_id}, {"student_count": 1})

    student_name = student.get("full_name", "")
    target_name = target_class.get("name_ar") or target_class.get("name", "")
    return {
        "success": True,
        "message": f"تم نقل الطالب {student_name} إلى الفصل {target_name} بنجاح"
    }

@router.delete("/students/{student_id}")
async def delete_student(
    student_id: str,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN]))
):
    """Delete student — full removal from system"""
    student = await gd_find_one(db.session, "students", {"id": student_id})
    if not student:
        raise HTTPException(status_code=404, detail="الطالب غير موجود")
    
    school_id = student.get("school_id")
    class_id = student.get("class_id")
    user_id = student.get("user_id")

    await audit_engine.log(
        action=AuditAction.USER_DELETED.value,
        performed_by=current_user.get("id"),
        tenant_id=school_id,
        entity_type="student",
        entity_id=student_id,
        details={
            "full_name": student.get("full_name"),
            "school_id": school_id,
            "class_id": class_id,
        },
        actor_name=current_user.get("full_name"),
        actor_role=current_user.get("role"),
        actor_email=current_user.get("email"),
    )

    cleanup = {}
    await gd_delete_many(db.session, "attendance", {"student_id": student_id})
    await gd_delete_one(db.session, "students", {"id": student_id})

    await _gd_inc(db.session, "schools", {"id": school_id}, {"current_students": -1})
    if class_id:
        await _gd_inc(db.session, "classes", {"id": class_id}, {"current_students": -1})

    r = await gd_delete_many(db.session, "attendance", {"student_id": student_id})
    cleanup["attendance"] = r
    r = await gd_delete_many(db.session, "session_attendance", {"student_id": student_id})
    cleanup["session_attendance"] = r
    r = await gd_delete_many(db.session, "grades", {"student_id": student_id})
    cleanup["grades"] = r
    r = await gd_delete_many(db.session, "student_daily_scores", {"student_id": student_id})
    cleanup["student_daily_scores"] = r
    r = await gd_delete_many(db.session, "student_score_ledger", {"student_id": student_id})
    cleanup["student_score_ledger"] = r
    r = await gd_delete_many(db.session, "student_skills", {"student_id": student_id})
    cleanup["student_skills"] = r
    r = await gd_delete_many(db.session, "behaviour_records", {"student_id": student_id})
    cleanup["behaviour_records"] = r
    r = await gd_delete_many(db.session, "session_interactions", {"student_id": student_id})
    cleanup["session_interactions"] = r
    r = await gd_delete_many(db.session, "guardian_links", {"student_id": student_id})
    cleanup["guardian_links"] = r
    r = await gd_delete_many(db.session, "user_relationships", {"$or": [{"source_id": student_id}, {"target_id": student_id}]})
    cleanup["user_relationships"] = r

    if user_id:
        await gd_delete_one(db.session, "users", {"id": user_id})
        await gd_delete_many(db.session, "user_roles", {"user_id": user_id})
        await gd_delete_many(db.session, "user_identities", {"user_id": user_id})
        cleanup["user_account"] = 1

    return {"message": "تم حذف الطالب وجميع بياناته من النظام بالكامل", "success": True, "cleanup": cleanup}




# ============== STUDENT WIZARD ROUTES ==============
class StudentWizardCreate(BaseModel):
    """Student wizard creation model"""
    full_name: str
    email: Optional[str] = None
    national_id: Optional[str] = None
    gender: str = "male"
    date_of_birth: Optional[str] = None
    education_level: Optional[str] = None
    grade_id: Optional[str] = None
    class_id: Optional[str] = None
    parent: Optional[dict] = None
    health: Optional[dict] = None
    link_to_parent_id: Optional[str] = None

@router.post("/student-wizard/check-parent")
async def check_parent_exists(
    phone: Optional[str] = None,
    email: Optional[str] = None,
    national_id: Optional[str] = None,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.SCHOOL_SUB_ADMIN]))
):
    """Check if parent already exists and return their students (siblings)"""
    school_id = current_user.get("tenant_id")
    
    query = {"school_id": school_id}
    conditions = []
    
    if phone:
        conditions.append({"phone": phone})
    if email:
        conditions.append({"email": email})
    if national_id:
        conditions.append({"national_id": national_id})
    
    if not conditions:
        return {"found": False}
    
    query["$or"] = conditions
    
    parent = await gd_find_one(db.session, "parents", query)
    
    if parent:
        # Get parent's students (siblings)
        students = await gd_find(db.session, "students", {"school_id": school_id, "id": {"$in": parent.get("student_ids", [])}}, limit=100)
        
        return {
            "found": True,
            "parent": parent,
            "students": students
        }
    
    return {"found": False}


@router.get("/parents")
async def get_parents(
    current_user: dict = Depends(get_current_user)
):
    school_id = current_user.get("tenant_id")
    query = {"status": {"$ne": "closed"}}
    if school_id:
        query["school_id"] = school_id
    parents = await gd_find(db.session, "parents", query, limit=1000)
    result = []
    for p in parents:
        student_ids = p.get("student_ids", [])
        children = []
        if student_ids:
            child_query = {"id": {"$in": student_ids}}
            if school_id:
                child_query["school_id"] = school_id
            students_docs = await gd_find(db.session, "students", child_query, limit=50)
            children = [{"id": s.get("id"), "name": s.get("full_name") or s.get("full_name_ar")} for s in students_docs]
        p["children"] = children
        p["children_count"] = len(children)
        if not p.get("full_name") and p.get("full_name_ar"):
            p["full_name"] = p["full_name_ar"]
        if not p.get("relationship"):
            p["relationship"] = p.get("relation")
        result.append(p)
    return result


@router.get("/student-wizard/search-parents")
async def search_parents(
    q: str = "",
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.SCHOOL_SUB_ADMIN]))
):
    """Search for existing parents by name or phone"""
    school_id = current_user.get("tenant_id")
    
    if not q or len(q) < 2:
        return {"parents": []}
    
    import re as _re
    safe_q = _re.escape(q)
    # Search by name or phone
    query = {
        "school_id": school_id,
        "$or": [
            {"full_name": {"$regex": safe_q, "$options": "i"}},
            {"phone": {"$regex": safe_q, "$options": "i"}},
        ]
    }
    
    parents = await gd_find(db.session, "parents", query, limit=10)
    
    # Add children count and names
    result = []
    for parent in parents:
        student_ids = parent.get("student_ids", [])
        children_count = len(student_ids)
        children = []
        
        if student_ids:
            students = await gd_find(
                db.session, "students",
                {"id": {"$in": student_ids}, "school_id": school_id},
                limit=10,
            )
            children = [{"name": s.get("full_name")} for s in students]
        
        result.append({
            "id": parent.get("id"),
            "full_name": parent.get("full_name"),
            "phone": parent.get("phone"),
            "email": parent.get("email"),
            "national_id": parent.get("national_id"),
            "relationship": parent.get("relationship", "father"),
            "address": parent.get("address"),
            "children_count": children_count,
            "children": children
        })
    
    return {"parents": result}

@router.post("/student-wizard/create")
async def create_student_with_wizard(
    data: StudentWizardCreate,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.SCHOOL_SUB_ADMIN, UserRole.INDEPENDENT_TEACHER]))
):
    """Create student with parent and health info via wizard.

    IT workspace mode (#192 spec §5.6):
      * `school_id` is pinned to the synthetic `itw_{user_id}` workspace
        regardless of any client-supplied tenant/school id.
      * Parent payload is fully optional. When absent (or partial), no
        `parents` row is materialised — the partial fragments land in
        `students.pending_parent_{name,phone,email}` until a real parent
        is later linked via the IT inline-link flow.
      * The Phase-0 student quota (MAX_STUDENTS=200) is enforced.
    """
    from auth_scope import (
        require_request_school_id,
        is_independent_teacher,
        independent_workspace_id,
    )
    from quotas.independent_teacher import enforce_student_quota

    is_it = is_independent_teacher(current_user)
    if is_it:
        # Defensive tenant pin — JWT-derived workspace id is the ONLY
        # acceptable tenant; any client-supplied id is ignored.
        school_id = independent_workspace_id(current_user)
        await enforce_student_quota(db.session, current_user)
    else:
        school_id = require_request_school_id(current_user)

    if not school_id:
        raise HTTPException(status_code=400, detail="المستخدم غير مرتبط بمدرسة")

    # Get school info
    school = await gd_find_one(db.session, "schools", {"id": school_id})
    if not school:
        raise HTTPException(status_code=404, detail="المدرسة غير موجودة")

    # School-admin contract (unchanged): a parent payload (with at least
    # full_name + phone) is required. IT workspace mode skips this.
    if not is_it and not data.link_to_parent_id:
        p = data.parent or {}
        if not (p.get("full_name") and p.get("phone")):
            raise HTTPException(
                status_code=422,
                detail="بيانات ولي الأمر مطلوبة (الاسم والهاتف)",
            )

    # Validate student email uniqueness if provided
    if data.email:
        existing_student_user = await gd_find_one(db.session, "users", {"email": data.email})
        if existing_student_user:
            raise HTTPException(status_code=400, detail="البريد الإلكتروني للطالب مسجل مسبقاً")

    # Validate link_to_parent_id belongs to same school (tenant isolation)
    if data.link_to_parent_id:
        existing_parent = await gd_find_one(
            db.session, "parents",
            {"id": data.link_to_parent_id, "school_id": school_id}
        )
        if not existing_parent:
            raise HTTPException(status_code=404, detail="ولي الأمر غير موجود في هذه المدرسة")

    # Workspace-mode parent gate (#192 spec §5.6): in IT workspace mode
    # the parent payload is FULLY OPTIONAL — any parent fragments
    # supplied through the inline-create flow (including phone-only,
    # name-only, or no parent at all) land in `pending_parent_*` and
    # never materialise a `parents` row. Only an explicit
    # `link_to_parent_id` opts into linking.
    p = data.parent or {}
    skip_parent_materialise = is_it and not data.link_to_parent_id

    # Generate student number: NSS-CODE-GRADE-XXXX using actual grade number
    school_code = school.get("code", "NSS")
    grade_num = "0"
    if data.grade_id:
        grade_level_doc = await gd_find_one(
            db.session, "grade_levels",
            {"id": data.grade_id, "school_id": school_id}
        ) or await gd_find_one(db.session, "grade_levels", {"id": data.grade_id})
        if grade_level_doc and grade_level_doc.get("grade") is not None:
            grade_num = str(grade_level_doc.get("grade"))

    # Count existing students to generate sequential number
    student_count = await gd_count(db.session, "students", {"school_id": school_id})
    student_number = f"NSS-{school_code}-{grade_num}-{str(student_count + 1).zfill(4)}"
    
    student_id = str(uuid.uuid4())
    
    # Get class info (enforce tenant isolation)
    class_doc = None
    if data.class_id:
        class_doc = await gd_find_one(db.session, "classes", {"id": data.class_id, "school_id": school_id})
        if not class_doc:
            raise HTTPException(status_code=404, detail="الفصل غير موجود في هذه المدرسة")
    
    # Create student
    student_doc = {
        "id": student_id,
        "school_id": school_id,
        "student_number": student_number,
        "full_name": data.full_name,
        "full_name_en": data.full_name,
        "email": data.email,
        "national_id": data.national_id,
        "gender": data.gender,
        "date_of_birth": data.date_of_birth,
        "grade": class_doc.get("grade") if class_doc else None,
        "section": class_doc.get("section") if class_doc else None,
        "class_id": data.class_id,
        "education_level": data.education_level,
        "is_active": True,
        "enrollment_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    
    # Add health info if provided
    if data.health:
        student_doc["health_status"] = data.health.get("health_status")
        student_doc["allergies"] = data.health.get("allergies", [])
        student_doc["medications"] = data.health.get("medications", [])
        student_doc["special_needs"] = data.health.get("special_needs")
        student_doc["health_notes"] = data.health.get("notes")
    
    # Workspace-mode (#192 spec §5.6): persist partial parent fragments
    # into the canonical pending_parent_* columns so a real parent can
    # be linked later by the IT inline-link flow. The DB trigger
    # `students_clear_pending_parent_on_link_trg` clears these on
    # parent_id NULL→non-NULL transitions.
    if skip_parent_materialise:
        student_doc["pending_parent_name"] = (p.get("full_name") or None)
        student_doc["pending_parent_phone"] = (p.get("phone") or None)
        student_doc["pending_parent_email"] = (p.get("email") or None)

    await gd_insert(db.session, "students", student_doc)

    # Handle parent
    parent_doc = None
    parent_password = None

    if skip_parent_materialise:
        # No parents row, no parent user, no guardian_link. Done.
        pass
    elif data.link_to_parent_id:
        # Link to existing parent
        await _gd_push(db.session, "parents", {"id": data.link_to_parent_id}, {"student_ids": student_id})
        parent_doc = await gd_find_one(db.session, "parents", {"id": data.link_to_parent_id})
    elif data.parent:
        # Create new parent
        parent_id = str(uuid.uuid4())
        parent_password = f"P{random.randint(100000, 999999)}"
        
        parent_login_email = data.parent.get("email") or f"parent_{parent_id[:8]}@{school_code.lower()}.edu.sa"
        parent_doc = {
            "id": parent_id,
            "school_id": school_id,
            "full_name": data.parent.get("full_name"),
            "phone": data.parent.get("phone"),
            "email": parent_login_email,
            "national_id": data.parent.get("national_id"),
            "relation": data.parent.get("relationship", "father"),
            "address": data.parent.get("address"),
            "student_ids": [student_id],
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await gd_insert(db.session, "parents", parent_doc)
        
        # Create parent user account
        parent_user = {
            "id": str(uuid.uuid4()),
            "email": parent_login_email,
            "password_hash": hash_password(parent_password),
            "full_name": data.parent.get("full_name"),
            "role": "parent",
            "is_active": True,
            "is_suspended": False,
            "tenant_id": school_id,
            "school_id": school_id,
            "parent_id": parent_id,
            "student_ids": [student_id],
            "permissions": ["view_child_data", "view_grades", "view_attendance"],
            "preferred_language": "ar",
            "preferred_theme": "light",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        await gd_insert(db.session, "users", parent_user)
    
    # Update student with parent info
    if parent_doc:
        await gd_update_one(db.session, "students", {"id": student_id}, {
                "parent_id": parent_doc.get("id"),
                "parent_name": parent_doc.get("full_name"),
                "parent_phone": parent_doc.get("phone"),
            })
    
    # Update class student count
    if data.class_id:
        await _gd_inc(db.session, "classes", {"id": data.class_id}, {"student_count": 1})
    
    # Update school student count
    await _gd_inc(db.session, "schools", {"id": school_id}, {"current_students": 1})
    
    # Create student user account
    student_password = f"S{random.randint(100000, 999999)}"
    student_email = data.email or f"student_{student_id[:8]}@{school_code.lower()}.edu.sa"
    
    student_user = {
        "id": str(uuid.uuid4()),
        "email": student_email,
        "password_hash": hash_password(student_password),
        "full_name": data.full_name,
        "role": "student",
        "is_active": True,
        "is_suspended": False,
        "tenant_id": school_id,
        "school_id": school_id,
        "student_id": student_id,
        "permissions": ["view_schedule", "view_grades", "view_attendance"],
        "preferred_language": "ar",
        "preferred_theme": "light",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    await gd_insert(db.session, "users", student_user)
    
    # Generate welcome message
    welcome_message = f"""مرحباً في نظام نَسَّق!
    
🎓 بيانات الطالب:
الاسم: {data.full_name}
رقم الطالب: {student_number}
البريد: {student_email}
كلمة المرور: {student_password}

👨‍👩‍👧 بيانات ولي الأمر:
الاسم: {parent_doc.get('full_name') if parent_doc else 'غير محدد'}
البريد: {(parent_user.get('email') if parent_password else (parent_doc.get('email') if parent_doc else None)) or 'غير محدد'}
الهاتف: {parent_doc.get('phone') if parent_doc else 'غير محدد'}
كلمة المرور: {parent_password if parent_password else 'موجودة مسبقاً'}

🔗 رابط تسجيل الدخول: {os.environ.get('FRONTEND_URL', '')}
"""
    
    # Generate QR Code for student
    qr_code = generate_student_qr_code(student_id, data.full_name, student_number)
    
    return {
        "success": True,
        "student": {
            "id": student_id,
            "student_id": student_number,  # Alias for student_number
            "student_number": student_number,
            "full_name": data.full_name,
            "email": student_email,
            "temp_password": student_password,
            "class_name": class_doc.get("name") if class_doc else None,
            "grade": class_doc.get("grade") if class_doc else None,
            "section": class_doc.get("section") if class_doc else None,
            "qr_code": qr_code,  # Base64 encoded QR code image
        },
        "parent": {
            "id": parent_doc.get("id") if parent_doc else None,
            "full_name": parent_doc.get("full_name") if parent_doc else None,
            "email": parent_doc.get("email") if parent_doc else None,
            "phone": parent_doc.get("phone") if parent_doc else None,
            "temp_password": parent_password,
            "is_new": parent_password is not None,
        } if parent_doc else None,
        "welcome_message": welcome_message,
        "siblings": {
            "count": 0,
            "list": [],
        }
    }




