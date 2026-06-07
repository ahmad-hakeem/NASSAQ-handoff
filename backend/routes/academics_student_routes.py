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
from engines.entity_counts import reconcile_school_counts, reconcile_class_counts
from auth_scope import require_request_school_id
from utils.it_parent_link import link_workspace_parent_to_student
from utils.canonical_grades import CANONICAL_GRADES, normalize_canonical_grade
from utils.stage_grade import normalize_stage


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
    
    class_name = None
    if student_data.class_id:
        class_doc = await gd_find_one(db.session, "classes", {"id": student_data.class_id, "school_id": school_id})
        if not class_doc:
            raise HTTPException(status_code=404, detail="الفصل غير موجود أو لا ينتمي إلى مدرستك")
        class_name = class_doc.get("name")

    await gd_insert(db.session, "students", student_doc)
    
    # Reconcile (recompute) the school's stored counts from live rows instead of
    # blindly nudging by +1, so the denormalized columns never drift (Task #826).
    await reconcile_school_counts(db.session, student_doc["school_id"])
    
    # Recompute the class counter from live rows (Task #829) instead of nudging
    # by +1, so classes.current_students never drifts.
    if student_data.class_id:
        await reconcile_class_counts(db.session, student_data.class_id, school_id)
    
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
    
    return StudentResponse(**student_doc, class_name=class_name)

@router.get("/students", response_model=List[StudentResponse])
async def get_students(
    class_id: Optional[str] = None,
    x_school_context: Optional[str] = Header(default=None, alias="X-School-Context"),
    current_user: dict = Depends(require_roles([
        UserRole.PLATFORM_ADMIN,
        UserRole.SCHOOL_PRINCIPAL,
        UserRole.SCHOOL_ADMIN,
        UserRole.SCHOOL_SUB_ADMIN,
        UserRole.TEACHER,
        UserRole.INDEPENDENT_TEACHER,
    ]))
):
    """Get all students or filter by school/class.

    Task #335: fail-closed school-id resolution. Non-platform callers
    must resolve a concrete tenant via `require_request_school_id`
    (covers school roles AND independent-teacher synthetic workspaces);
    a token without a tenant raises 403 instead of silently degrading
    into an unscoped or empty query.

    Task #508 / Task #511: Platform admins MUST resolve preview scope
    via the `X-School-Context` header through `resolve_school_id`,
    which only honors the override when the bearer token was minted
    by `/role-switch/switch` (is_impersonating + matching tenant_id).
    When the resolver returns no school context (plain PA token with
    no `X-School-Context` header, or a token that has not been minted
    via the hardened role-switch flow), the route now FAILS CLOSED and
    returns an empty list — never an unscoped cross-tenant directory
    dump. The legacy `?school_id=` query param is not honored.
    """
    from utils.tenant_scope import resolve_school_id
    query = {"is_active": {"$ne": False}}
    if current_user.get("role") == UserRole.PLATFORM_ADMIN.value:
        scoped = resolve_school_id(current_user, x_school_context)
        if not scoped:
            return []
        query["school_id"] = scoped
    else:
        # Task #509: non-platform callers may not address another tenant
        # via X-School-Context; validating through resolve_school_id 403s
        # on mismatch and matches /teachers and /classes behaviour.
        if x_school_context is not None:
            resolve_school_id(current_user, x_school_context)
        query["school_id"] = require_request_school_id(current_user)

    if class_id:
        query["class_id"] = class_id

    # Least-privilege for regular school teachers (dropdown-audit LOW-3):
    # a TEACHER token may only list students in classes actually assigned to
    # them — same-tenant membership alone is NOT sufficient. This uses the
    # canonical get_teacher_allowed_class_ids() helper (ACTIVE
    # teacher_assignments ∪ class_sessions), the exact same source of truth
    # enforced by can_view_class() / GET /classes/{class_id}/students, so the
    # two roster paths can no longer disagree. teacher_class_assignments is
    # deliberately NOT consulted: it is auto-populated to link every teacher
    # to every class, so trusting it leaked the whole school's students and
    # let ?class_id=<not-taught> return a foreign roster (within-tenant IDOR).
    # INDEPENDENT_TEACHER (workspace pool), school-admin roles and platform
    # admins are intentionally unaffected.
    if current_user.get("role") == UserRole.TEACHER.value:
        from utils.tenant_scope import get_teacher_allowed_class_ids
        teacher_id = current_user.get("teacher_id") or current_user.get("id")
        allowed_class_ids = await get_teacher_allowed_class_ids(db.session, teacher_id)
        if not allowed_class_ids:
            return []
        if class_id:
            if class_id not in allowed_class_ids:
                return []
        else:
            query["class_id"] = {"$in": list(allowed_class_ids)}

    students = await gd_find(db.session, "students", query, limit=1000)
    
    # Get class names
    class_ids = list(set([s.get("class_id") for s in students if s.get("class_id")]))
    classes = await gd_find(db.session, "classes", {"id": {"$in": class_ids}, "is_active": {"$ne": False}}, limit=100)
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
    """Get the canonical grade levels for student/class flows.

    Always returns exactly the twelve product-approved canonical grades
    (``utils/canonical_grades.py``) with the correct ``name_ar`` label and a
    ``stage`` of ``primary|middle|high`` so the frontend stage→grade cascade is
    reliable everywhere. Where the resolved school already has a matching
    ``grade_levels`` row (matched by grade number / normalized label), that
    row's existing ``id`` is returned so persistence and existing student/class
    linkage are preserved; otherwise the canonical grade number (``"1".."12"``)
    is used as the id, which backend write validation already accepts.
    """
    # Task #155: fail-closed school-id resolution; see audit row #10.
    school_id = require_request_school_id(current_user)

    rows = await gd_find(db.session, "grade_levels", {"school_id": school_id}, limit=200)

    # Index existing tenant rows by canonical grade number so a selected
    # canonical grade maps back to the school's real row id (preserving links).
    existing_id_by_grade: Dict[int, str] = {}
    for r in rows:
        row_id = r.get("id") or r.get("_id")
        if not row_id:
            continue
        entry = normalize_canonical_grade(r.get("grade")) or normalize_canonical_grade(
            r.get("name_ar") or r.get("name")
        )
        if entry and entry["grade"] not in existing_id_by_grade:
            existing_id_by_grade[entry["grade"]] = row_id

    result_grades = [
        {
            "id": existing_id_by_grade.get(g["grade"], str(g["grade"])),
            "name_ar": g["label_ar"],
            "name_en": g["label_en"],
            "grade": g["grade"],
            "stage": g["stage"],
            "stage_id": g["stage"],
        }
        for g in CANONICAL_GRADES
    ]

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
    response: Response,
    current_user: dict = Depends(require_roles([
        UserRole.PLATFORM_ADMIN,
        UserRole.SCHOOL_PRINCIPAL,
        UserRole.SCHOOL_ADMIN,
        UserRole.SCHOOL_SUB_ADMIN,
        UserRole.TEACHER,
        UserRole.INDEPENDENT_TEACHER,
    ]))
):
    """Get all students in a specific class.

    SECURITY: Restricted to staff roles only. The full class roster
    (including PII and family linkage) must not be accessible to
    parents or students. Regular teachers are additionally checked for
    class assignment via can_view_class() for parity with attendance
    and reporting endpoints. The IT §6.7 collab path has its own gate.
    """
    # Bug #372 — class roster is the post-delete refetch target on the
    # class detail page. Disable browser heuristic caching so a fresh
    # GET after DELETE /students/{id} always reflects the deletion
    # instead of returning the pre-delete list from the disk cache.
    response.headers["Cache-Control"] = "no-store"
    # Object-level class authorization for regular TEACHER callers.
    # INDEPENDENT_TEACHER access is controlled further below via the
    # §6.7 collab row check (workspace pinning / §8 invariant 3).
    if current_user.get("role") == UserRole.TEACHER.value:
        from utils.tenant_scope import can_view_class, require_can_view_class_sync_check
        cls_allowed = await can_view_class(db.session, current_user, class_id)
        require_can_view_class_sync_check(cls_allowed)

    query = {"class_id": class_id, "is_active": True}
    # IT §6.7 (Task #210) — for an Independent-Teacher caller who holds
    # an accepted cross-workspace collab row on this class, scope the
    # students lookup by the *host* school_id (the class's owner) so the
    # roster comes back; otherwise fall back to the caller's tenant.
    widened_for_collab = False
    if current_user.get("role") != UserRole.PLATFORM_ADMIN.value:
        if current_user.get("role") == UserRole.INDEPENDENT_TEACHER.value:
            from utils.collab_access import caller_collab_row_for_class
            from auth_scope import independent_workspace_id
            row = await caller_collab_row_for_class(db.session, current_user, class_id)
            if row:
                query["school_id"] = row["host_school_id"]
                widened_for_collab = True
            else:
                # Fail-closed for IT: always pin to the caller's
                # workspace even when the JWT didn't carry tenant_id, so
                # a non-collaborator can never receive a foreign-tenant
                # roster (§8 inv. 3).
                query["school_id"] = (
                    current_user.get("tenant_id")
                    or independent_workspace_id(current_user)
                )
        if not widened_for_collab and current_user.get("role") != UserRole.INDEPENDENT_TEACHER.value:
            tenant = current_user.get("tenant_id")
            if tenant:
                query["school_id"] = tenant

    # §8 inv. 3 — a by-id roster read MUST 404 (never return 200 []) for a
    # class the caller cannot see, so the endpoint does not silently
    # confirm or deny the existence of a foreign-workspace / non-existent
    # class. Scope the existence check to the same school_id the student
    # query is pinned to.
    _class_scope = {"id": class_id}
    if query.get("school_id"):
        _class_scope["school_id"] = query["school_id"]
    cls = await gd_find_one(db.session, "classes", _class_scope)
    if not cls:
        raise HTTPException(status_code=404, detail="الفصل غير موجود")
    class_name = cls.get("name")

    students = await gd_find(db.session, "students", query, limit=1000)

    # IT §6.7 — cross-workspace collaborators receive a strictly
    # downscoped roster: only the minimum classroom-teaching fields.
    # Sensitive PII (national IDs, DOB, contact info, parent linkage,
    # health, emergency contacts) is stripped before serialization so
    # the §6.7 widening cannot leak guardian or child records into a
    # foreign tenant. The §8 invariant is intentionally relaxed only
    # for the named class — not for the underlying personal data.
    COLLAB_STRIPPED_FIELDS = (
        "email",
        "phone",
        "student_number",
        "national_id",
        "date_of_birth",
        "parent_id",
        "parent_phone",
        "parent_email",
        "parent_name",
        "parent_relationship",
        "qr_code",
        "nationality",
        "enrollment_date",
        "health_info",
        "emergency_contact",
        "emergency_phone",
    )

    # Parent backfill is only needed when the caller will actually
    # receive parent_id; skip the lookup entirely for collaborators.
    parent_lookup = {}
    if not widened_for_collab:
        students_missing_parent = [s["id"] for s in students if not s.get("parent_id") and s.get("parent_phone")]
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
        if widened_for_collab:
            for _f in COLLAB_STRIPPED_FIELDS:
                if _f in s:
                    s[_f] = None
        elif not s.get("parent_id") and s["id"] in parent_lookup:
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
        student = await gd_find_one(db.session, "students", {"id": sid, "is_active": True})

    # Tenant-scoped fallback lookups to prevent cross-tenant resolution.
    def _scoped(field, value):
        q = {field: value, "is_active": True}
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
    """Get student by ID.

    SECURITY: Same-tenant membership alone is not enough. The caller must
    be the student themselves, a guardian of the student, a teacher assigned
    to the student's class, or an admin role within the tenant. This prevents
    any low-privilege account from enumerating the full student directory via
    brute-forced or guessed student IDs.
    """
    student = await gd_find_one(db.session, "students", {"id": student_id, "is_active": True})
    if not student:
        raise HTTPException(status_code=404, detail="الطالب غير موجود")

    if current_user.get("role") != UserRole.PLATFORM_ADMIN.value:
        # Cross-tenant lookup MUST 404 (not 403) so the route never confirms
        # the existence of a student in another tenant — see #192 spec §5.6.
        from auth_scope import independent_workspace_id
        user_school = current_user.get("tenant_id") or independent_workspace_id(current_user)
        student_school = student.get("school_id")
        if user_school and student_school and student_school != user_school:
            raise HTTPException(status_code=404, detail="الطالب غير موجود")

    # Object-level authorization: verify the caller has a legitimate
    # relationship to this specific student (self / guardian / assigned teacher
    # / admin). Tenant membership alone is not sufficient.
    from utils.tenant_scope import can_view_student, require_can_view_student_sync_check
    allowed = await can_view_student(db.session, current_user, student_id)
    require_can_view_student_sync_check(allowed)
    
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
    query = {"id": student_id, "is_active": True}
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
        class_owner_id = school_id or existing.get("school_id")
        if class_owner_id:
            class_check = await gd_find_one(db.session, "classes", {"id": student_data.class_id, "school_id": class_owner_id})
            if not class_check:
                raise HTTPException(status_code=404, detail="الفصل غير موجود أو لا ينتمي إلى مدرستك")
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

    # Defense-in-depth (Task #795): these two pre-lookups previously ran
    # OUTSIDE any try/except, and there is no global generic-Exception
    # handler, so an unexpected DB error here returned an unparseable
    # plain-text 500 that the frontend could only render as the generic
    # cause-hiding popup. Guard them so any unexpected failure is logged
    # and surfaced through the standard safe-Arabic envelope instead —
    # while still letting the deliberate 404 (HTTPException) propagate
    # untouched so tenant scoping / not-found semantics are preserved.
    try:
        student = await gd_find_one(db.session, "students", {"id": student_id, "school_id": school_id, "is_active": True})
        if not student:
            raise HTTPException(status_code=404, detail="الطالب غير موجود")

        target_class = await gd_find_one(db.session, "classes", {"id": target_class_id, "school_id": school_id})
        if not target_class:
            raise HTTPException(status_code=404, detail="الفصل المستهدف غير موجود")
    except HTTPException:
        raise
    except Exception:
        logger.exception(
            "Failed to look up student %s / target class %s for transfer",
            student_id, target_class_id,
        )
        raise HTTPException(status_code=500, detail="تعذر نقل الطالب، يرجى المحاولة مرة أخرى")

    old_class_id = student.get("class_id")
    if old_class_id == target_class_id:
        return {"success": True, "message": "الطالب موجود بالفعل في هذا الفصل"}

    now = datetime.now(timezone.utc).isoformat()
    student_name = student.get("full_name", "")
    target_name = target_class.get("name_ar") or target_class.get("name", "")

    # NOTE: `class_name`/`student_ids`/`student_count` are NOT real columns
    # (Student/Class are plain ORM models with no `data` column), so the old
    # bookkeeping silently dropped those writes and class counters never moved.
    # Move the student via the real `class_id` column and re-derive the
    # canonical `current_students` counter for both classes via gd_count so
    # any pre-existing drift self-heals.
    try:
        await gd_update_one(db.session, "students", {"id": student_id, "school_id": school_id}, {
            "class_id": target_class_id,
            "updated_at": now,
        })

        old_class_current_students = None
        if old_class_id:
            old_class_current_students = await reconcile_class_counts(
                db.session, old_class_id, school_id
            )

        target_class_current_students = await reconcile_class_counts(
            db.session, target_class_id, school_id
        )
    except Exception:
        logger.exception(
            "Failed to transfer student %s to class %s", student_id, target_class_id
        )
        raise HTTPException(status_code=500, detail="تعذر نقل الطالب، يرجى المحاولة مرة أخرى")

    return {
        "success": True,
        "message": f"تم نقل الطالب {student_name} إلى الفصل {target_name} بنجاح",
        "student_id": student_id,
        "old_class_id": old_class_id,
        "target_class_id": target_class_id,
        "old_class_current_students": old_class_current_students,
        "target_class_current_students": target_class_current_students,
    }

@router.delete("/students/{student_id}")
async def delete_student(
    student_id: str,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.INDEPENDENT_TEACHER]))
):
    """Delete student — full removal from system. IT callers are pinned
    to their own workspace (cross-workspace ids return 404)."""
    from auth_scope import is_independent_teacher, independent_workspace_id
    if is_independent_teacher(current_user):
        wsid = independent_workspace_id(current_user)
        student = await gd_find_one(db.session, "students", {"id": student_id, "school_id": wsid, "is_active": True})
    elif current_user.get("role") == UserRole.PLATFORM_ADMIN.value:
        student = await gd_find_one(db.session, "students", {"id": student_id, "is_active": True})
    else:
        caller_tenant = current_user.get("tenant_id")
        if not caller_tenant:
            raise HTTPException(status_code=403, detail="سياق المدرسة مطلوب")
        student = await gd_find_one(db.session, "students", {"id": student_id, "school_id": caller_tenant, "is_active": True})
    if not student:
        raise HTTPException(status_code=404, detail="الطالب غير موجود")
    
    school_id = student.get("school_id")
    class_id = student.get("class_id")
    user_id = student.get("user_id")

    now_iso = datetime.now(timezone.utc).isoformat()
    await gd_update_one(
        db.session, "students",
        {"id": student_id},
        {"$set": {"is_active": False, "updated_at": now_iso}},
    )

    await reconcile_school_counts(db.session, school_id)
    # Recompute the class counter from live rows (Task #829) instead of nudging
    # by -1, so classes.current_students never drifts.
    if class_id:
        await reconcile_class_counts(db.session, class_id, school_id)

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
            "soft_delete": True,
        },
        actor_name=current_user.get("full_name"),
        actor_role=current_user.get("role"),
        actor_email=current_user.get("email"),
    )

    return {"message": "تم إلغاء تفعيل الطالب وإخفاؤه من جميع القوائم مع الحفاظ على سجلاته", "success": True}




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
        students = await gd_find(db.session, "students", {"school_id": school_id, "is_active": True, "id": {"$in": parent.get("student_ids", [])}}, limit=100)
        
        return {
            "found": True,
            "parent": parent,
            "students": students
        }
    
    return {"found": False}


@router.get("/parents")
async def get_parents(
    x_school_context: Optional[str] = Header(default=None, alias="X-School-Context"),
    current_user: dict = Depends(require_roles([
        UserRole.PLATFORM_ADMIN,
        UserRole.SCHOOL_PRINCIPAL,
        UserRole.SCHOOL_ADMIN,
        UserRole.SCHOOL_SUB_ADMIN,
    ]))
):
    """List parents in the caller's tenant.

    SECURITY: Restricted to admin roles only. The parent directory contains
    personal and family information (names, phone numbers, linked children)
    and must not be accessible to teachers, students, or other parents.

    Task #335: fail-closed school-id resolution for non-platform callers
    (mirrors `/students`).

    Task #508 / Task #511: Platform admins MUST resolve preview scope
    via the `X-School-Context` header through `resolve_school_id`,
    which only honors the override when the bearer token was minted
    by `/role-switch/switch`. When the resolver returns no school
    context (plain PA token without a header, or a token not minted
    via the hardened role-switch flow), the route now FAILS CLOSED
    and returns an empty list — never the cross-tenant parent
    directory.
    """
    from utils.tenant_scope import resolve_school_id
    if current_user.get("role") == UserRole.PLATFORM_ADMIN.value:
        school_id = resolve_school_id(current_user, x_school_context)
        if not school_id:
            return []
    else:
        # Task #509: 403 on foreign X-School-Context for non-platform callers
        # (matches /teachers and /classes behaviour).
        if x_school_context is not None:
            resolve_school_id(current_user, x_school_context)
        school_id = require_request_school_id(current_user)
    query: Dict[str, Any] = {"status": {"$ne": "closed"}, "school_id": school_id}
    parents = await gd_find(db.session, "parents", query, limit=1000)

    # Deterministic children aggregation: combine the two link sources
    # (`parents.student_ids` array and `students.parent_id` back-reference)
    # so the per-parent children count cannot silently collapse to 0 when
    # only one of the two is populated (e.g. legacy rows, partial Noor
    # imports, or parent rows created before guardian linkage).
    parent_ids = [p.get("id") for p in parents if p.get("id")]
    back_ref_map: Dict[str, list] = {}
    if parent_ids:
        back_query: Dict[str, Any] = {"parent_id": {"$in": parent_ids}, "is_active": True}
        if school_id:
            back_query["school_id"] = school_id
        # Narrow to the specific failure mode the back-ref guards against
        # (legacy DBs missing `students.parent_id`). Any other failure
        # propagates so callers see a real 5xx instead of a partial,
        # silently-degraded children list.
        from sqlalchemy.exc import ProgrammingError as _SAProgrammingError
        try:
            back_students = await gd_find(db.session, "students", back_query, limit=5000)
        except _SAProgrammingError as _back_err:
            logger.warning(f"parents back-ref skipped (schema): {_back_err}")
            back_students = []
        for s in back_students:
            pid = s.get("parent_id")
            if not pid:
                continue
            back_ref_map.setdefault(pid, []).append(s)

    result = []
    for p in parents:
        student_ids = list(p.get("student_ids") or [])
        children: List[Dict[str, Any]] = []
        seen_ids = set()
        if student_ids:
            child_query: Dict[str, Any] = {"id": {"$in": student_ids}, "is_active": True}
            if school_id:
                child_query["school_id"] = school_id
            students_docs = await gd_find(db.session, "students", child_query, limit=50)
            for s in students_docs:
                sid = s.get("id")
                if sid and sid not in seen_ids:
                    seen_ids.add(sid)
                    children.append({"id": sid, "name": s.get("full_name") or s.get("full_name_ar")})
        for s in back_ref_map.get(p.get("id"), []):
            sid = s.get("id")
            if sid and sid not in seen_ids:
                seen_ids.add(sid)
                children.append({"id": sid, "name": s.get("full_name") or s.get("full_name_ar")})
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
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.SCHOOL_SUB_ADMIN, UserRole.INDEPENDENT_TEACHER])),
    credentials: HTTPAuthorizationCredentials = Depends(security),
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
    # the parent payload is optional. Behaviour splits on whether a
    # *usable* parent identifier (national_id / phone / email) is present:
    #
    #   * Task #817 — when at least one usable identifier is supplied, the
    #     IT create flow auto-links a parent at create-time via the
    #     canonical workspace writer (utils.it_parent_link), so the student
    #     is born Linked exactly like the principal/school create flow.
    #   * No usable identifier — preserve the §5.6 Pending behaviour: any
    #     parent fragments land in `pending_parent_*` and never materialise
    #     a `parents` row. Only an explicit `link_to_parent_id` (handled
    #     separately) otherwise opts into linking.
    p = data.parent or {}
    _it_parent_national_id = (p.get("national_id") or "").strip() or None
    _it_parent_phone = (p.get("phone") or "").strip() or None
    _it_parent_email = (p.get("email") or "").strip() or None
    it_auto_link = (
        is_it
        and not data.link_to_parent_id
        and bool(_it_parent_national_id or _it_parent_phone or _it_parent_email)
    )
    skip_parent_materialise = (
        is_it and not data.link_to_parent_id and not it_auto_link
    )

    # §5.7 step-up: auto-linking a parent is the same Pending → Linked
    # write that the invite-parent writer gates behind fresh MFA. Enforce
    # it here BEFORE any DB write (memory: middleware-commits-on-4xx — the
    # session middleware commits non-GET writes even on a raised
    # HTTPException, so the guard must precede every write). Non-auto-link
    # IT creates and principal/admin creates keep their existing posture.
    if it_auto_link:
        await _REQUIRE_RECENT_MFA_403_IT(
            credentials=credentials, current_user=current_user,
        )

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

    # Handle parent
    parent_doc = None
    parent_password = None

    if it_auto_link:
        # Task #817 — IT create-time auto-link. Insert the student and run
        # the canonical workspace parent-link writer inside ONE savepoint
        # so a link failure rolls back the freshly created student too (no
        # half-created student / orphaned parent). The writer flips
        # students.parent_id (the DB trigger clears pending_parent_*),
        # tags guardian_links.tenant_id == workspace_id, and writes the
        # INDEPENDENT_TEACHER_PARENT_LINK audit — identical to invite.
        async with db.session.begin_nested():
            await gd_insert(db.session, "students", student_doc)
            link_result = await link_workspace_parent_to_student(
                db.session,
                student=student_doc,
                workspace_id=school_id,
                school_id=school_id,
                full_name=(p.get("full_name") or None),
                phone=_it_parent_phone,
                email=_it_parent_email,
                national_id=_it_parent_national_id,
                relationship=(p.get("relationship") or p.get("relation")),
                actor=current_user,
            )
        parent_doc = link_result.get("parent")
        # Mirror the principal flow: populate the denormalised parent_*
        # columns on the student row so the roster serializers (which read
        # parent_name/phone/email directly off the student) display the
        # linked parent. parent_id was already set by the writer.
        if parent_doc:
            await gd_update_one(db.session, "students", {"id": student_id}, {
                "parent_name": parent_doc.get("full_name"),
                "parent_phone": parent_doc.get("phone"),
                "parent_email": parent_doc.get("email"),
            })
        # The canonical writer owns parent_id; skip the legacy back-fill.
        skip_legacy_parent_update = True
    else:
        await gd_insert(db.session, "students", student_doc)
        skip_legacy_parent_update = False

    if it_auto_link:
        # Already linked above.
        pass
    elif skip_parent_materialise:
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
    
    # Update student with parent info (legacy denormalised back-fill). The
    # IT auto-link path already set parent_id via the canonical writer and
    # mirrored the denormalised columns, so skip it here.
    if parent_doc and not skip_legacy_parent_update:
        await gd_update_one(db.session, "students", {"id": student_id}, {
                "parent_id": parent_doc.get("id"),
                "parent_name": parent_doc.get("full_name"),
                "parent_phone": parent_doc.get("phone"),
            })
    
    # Recompute the class counter from live rows (Task #829). The previous
    # `_gd_inc(..., {"student_count": 1})` was a silent no-op anyway —
    # `student_count` is not a real `classes` column; `current_students` is.
    if data.class_id:
        await reconcile_class_counts(db.session, data.class_id, school_id)
    
    # Update school student count (reconcile from live rows — Task #826)
    await reconcile_school_counts(db.session, school_id)
    
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
            "is_new": (
                link_result.get("matched_by") == "new"
                if it_auto_link else parent_password is not None
            ),
            "matched_by": link_result.get("matched_by") if it_auto_link else None,
        } if parent_doc else None,
        "welcome_message": welcome_message,
        "siblings": {
            "count": 0,
            "list": [],
        }
    }




