from typing import Optional, Any, Dict

from fastapi import HTTPException, status

from models.enums import UserRole  # backend/ is on sys.path; matches existing convention


_PLATFORM_ROLES = frozenset({
    UserRole.PLATFORM_ADMIN.value,
})

_SCHOOL_ADMIN_ROLES = frozenset({
    UserRole.SCHOOL_PRINCIPAL.value,
    UserRole.SCHOOL_ADMIN.value,
    UserRole.SCHOOL_SUB_ADMIN.value,
})

_TENANT_OWNED_TABLES = frozenset({
    "academic_years",
    "terms",
    "academic_terms",
    "grade_levels",
    "educational_stages",
    "physical_classrooms",
    "assessments",
    "assessment_submissions",
    "student_grades",
    "behaviour_records",
    "attendance",
    "classes",
    "subjects",
    "teachers",
    "students",
    "parents",
    "teacher_assignments",
    "teacher_class_assignments",
    "timetables",
    "timetable_runs",
    "schedule_sessions",
    "time_slots",
    "timetable_constraints",
    "calendar_events",
    "events",
    "messages",
    "notifications",
    "approval_requests",
    "school_settings",
    "registration_requests",
    "guardian_links",
    "user_relationships",
})

# Tables that historically used `tenant_id` as the column name. Everything else
# defaults to `school_id`.
_TENANT_KEY_BY_TABLE = {
    "users": "tenant_id",
    "attendance": "tenant_id",
    "assessments": "tenant_id",
    "assessment_submissions": "tenant_id",
    "behaviour_records": "tenant_id",
    "notifications": "tenant_id",
    "audit_logs": "tenant_id",
    "approval_requests": "tenant_id",
    "ai_insights": "tenant_id",
    "ai_interventions": "tenant_id",
    "session_event_logs": "tenant_id",
    "session_notes": "tenant_id",
    "session_interactions": "tenant_id",
    "skill_types": "tenant_id",
    "student_skills": "tenant_id",
    "user_sessions": "tenant_id",
    "messages": "tenant_id",
}


def _tenant_key_for(collection: str) -> str:
    return _TENANT_KEY_BY_TABLE.get(collection, "school_id")


def _is_platform_admin(current_user: dict) -> bool:
    return current_user.get("role") in _PLATFORM_ROLES


async def tenant_scoped_find_one(
    session,
    collection: str,
    record_id: str,
    current_user: dict,
    *,
    id_field: str = "id",
) -> Optional[Dict[str, Any]]:
    """Fail-closed `gd_find_one` that enforces tenant scope at the query level.

    Behaviour:
      - Platform admins (and sub-admins) bypass the tenant filter — they can
        legitimately read any tenant's records.
      - Every other caller MUST have a tenant_id; otherwise 403.
      - The query always pins the tenant column. Per architect v3 feedback,
        legacy data has rows where tenant_id was set on one row in a table
        and school_id on another row in the same table — so we attempt the
        primary tenant column first, and if no row matches, fall back to
        the alternate column. BOTH queries pin the caller's tenant_id, so
        the fallback cannot leak cross-tenant data.
      - Returns `None` when not found in the caller's tenant — callers raise 404.
    """
    from engines.sql_utils import gd_find_one  # local import to avoid cycles

    if _is_platform_admin(current_user):
        return await gd_find_one(session, collection, {id_field: record_id})

    tenant_id = current_user.get("tenant_id") or current_user.get("school_id")
    if not tenant_id:
        # Task #203: Independent-Teacher callers carry no tenant_id;
        # resolve to their synthetic per-user workspace `itw_{user_id}`
        # so cross-workspace by-id lookups return None (→ route 404)
        # instead of 403 (spec §8 invariant 3).
        from auth_scope import independent_workspace_id  # local: avoid cycle
        tenant_id = independent_workspace_id(current_user)
    if not tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="تعذّر التحقق من صلاحياتك للوصول إلى هذه البيانات",
        )

    primary = _tenant_key_for(collection)
    alternate = "school_id" if primary == "tenant_id" else "tenant_id"

    row = await gd_find_one(session, collection, {id_field: record_id, primary: tenant_id})
    if row is not None:
        return row
    # Fallback for mixed-schema tables. Still tenant-pinned, so cannot leak
    # foreign rows; just covers the case where this row was written under
    # the alternate column name.
    return await gd_find_one(session, collection, {id_field: record_id, alternate: tenant_id})


async def tenant_scoped_assert_one(
    session,
    collection: str,
    record_id: str,
    current_user: dict,
    *,
    not_found_detail: str = "العنصر غير موجود",
) -> Dict[str, Any]:
    """Wrapper around `tenant_scoped_find_one` that raises 404 instead of
    returning None — convenient for write paths (PUT/DELETE) where missing
    rows and foreign-tenant rows must both 404 before any mutation runs."""
    row = await tenant_scoped_find_one(session, collection, record_id, current_user)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=not_found_detail)
    return row


async def can_view_student(session, current_user: dict, student_id: str) -> bool:
    """Return True iff `current_user` is allowed to read student-scoped data
    (attendance, grades, behaviour, portfolio, participation) for `student_id`.

    Allowed:
      - Platform admins.
      - School admin roles (principal/admin/sub_admin) within the student's tenant.
      - The student themselves.
      - The student's guardians via `parents.student_ids` or `guardian_links`.
      - Teachers with a `teacher_assignments` or `class_sessions` assignment to
        the student's class.

    Same-tenant alone is not sufficient.
    """
    from engines.sql_utils import gd_find_one  # local import to avoid cycles

    if not student_id:
        return False

    role = current_user.get("role", "")
    if role in _PLATFORM_ROLES:
        return True

    student = await gd_find_one(session, "students", {"id": student_id})
    if not student:
        return False

    user_tenant = current_user.get("tenant_id") or current_user.get("school_id")
    student_tenant = student.get("school_id") or student.get("tenant_id")
    if not user_tenant or user_tenant != student_tenant:
        return False

    if role in _SCHOOL_ADMIN_ROLES:
        return True

    user_id = current_user.get("id")

    if role == UserRole.STUDENT.value:
        return current_user.get("student_id") == student_id or user_id == student_id

    if role == UserRole.PARENT.value:
        parent = await gd_find_one(session, "parents", {"user_id": user_id})
        if parent and student_id in (parent.get("student_ids") or []):
            return True
        link = await gd_find_one(
            session,
            "guardian_links",
            {"parent_user_id": user_id, "student_id": student_id},
        )
        return bool(link)

    if role == UserRole.TEACHER.value:
        teacher_id = current_user.get("teacher_id") or user_id
        class_id = student.get("class_id")
        if not class_id:
            return False
        assign = await gd_find_one(
            session,
            "teacher_assignments",
            {"teacher_id": teacher_id, "class_id": class_id},
        )
        if assign:
            return True
        sess = await gd_find_one(
            session,
            "class_sessions",
            {"teacher_id": teacher_id, "class_id": class_id},
        )
        return bool(sess)

    return False


def require_can_view_student_sync_check(allowed: bool) -> None:
    """Tiny convenience to raise the canonical 403 when `can_view_student`
    returned False. Kept separate so route handlers stay readable."""
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="لا يمكنك الوصول لبيانات هذا الطالب",
        )


def assert_school_access(current_user: dict, school_id: str) -> None:
    """Raise 403 unless the caller belongs to school_id (or is platform admin).

    The single authoritative tenant guard for every timetable route.
    """
    if not school_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="school_id is required",
        )
    if _is_platform_admin(current_user):
        return
    user_tenant = current_user.get("tenant_id") or current_user.get("school_id")
    if not user_tenant or str(user_tenant) != str(school_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: school does not match caller's tenant",
        )


def resolve_school_id(current_user: dict, override: Optional[str]) -> Optional[str]:
    """Decide which school_id a request should operate on.

    Non-admins always operate on their own tenant; an override that
    matches their tenant is OK, an override that doesn't match is 403.
    Platform admins may override freely; with no override they get None
    (caller decides whether to require one).
    """
    if _is_platform_admin(current_user):
        return override  # may be None — caller decides
    user_tenant = current_user.get("tenant_id") or current_user.get("school_id")
    if override is not None and str(override) != str(user_tenant):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: school does not match caller's tenant",
        )
    if not user_tenant:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: caller has no tenant",
        )
    return str(user_tenant)
