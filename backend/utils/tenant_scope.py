import logging
from typing import Optional, Any, Dict

from fastapi import HTTPException, status

from models.enums import UserRole  # backend/ is on sys.path; matches existing convention

_logger = logging.getLogger("nassaq.tenant_scope")


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


async def can_view_student(
    session,
    current_user: dict,
    student_id: str,
    *,
    permission_type: Optional[str] = None,
    permission_types: Optional[list] = None,
) -> bool:
    """Return True iff `current_user` is allowed to read student-scoped data
    (attendance, grades, behaviour, portfolio, participation) for `student_id`.

    ``permission_type`` refines the check for parent/guardian callers.  Pass
    ``"attendance"`` when guarding attendance data, ``"grades"`` when guarding
    grade/report data, or leave as ``None`` for a general access check.  When
    set, the corresponding per-guardian permission flag in ``guardian_links``
    must also be ``True``; guardians that have been restricted to pickup-only
    will be denied.

    ``permission_types`` accepts a list of permission strings and requires ALL
    of them to be satisfied.  Use this for composite endpoints that return
    multiple data domains (e.g., ``["grades", "attendance"]`` for student
    reports that include both).  Takes precedence over ``permission_type``
    when both are supplied.

    Allowed:
      - Platform admins.
      - School admin roles (principal/admin/sub_admin) within the student's tenant.
      - Independent teachers for any student inside their own workspace (they are
        the sole admin of their synthetic school).
      - The student themselves.
      - The student's *active* guardians via ``guardian_links`` (with
        ``is_active=True``) whose permissions allow the requested data type, or
        via the legacy ``parents.student_ids`` array when no ``guardian_links``
        row has ever been created for this pair (backward compatibility only).
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

    student_tenant = student.get("school_id") or student.get("tenant_id")

    # Independent teachers carry no tenant_id; resolve via their synthetic workspace.
    if role == UserRole.INDEPENDENT_TEACHER.value:
        from auth_scope import independent_workspace_id  # local: avoid cycle
        it_workspace = independent_workspace_id(current_user)
        if not it_workspace or it_workspace != student_tenant:
            return False
        # Within their own workspace they have full admin-level access.
        return True

    user_tenant = current_user.get("tenant_id") or current_user.get("school_id")
    if not user_tenant or user_tenant != student_tenant:
        return False

    if role in _SCHOOL_ADMIN_ROLES:
        return True

    user_id = current_user.get("id")

    if role == UserRole.STUDENT.value:
        return current_user.get("student_id") == student_id or user_id == student_id

    if role == UserRole.PARENT.value:
        # Resolve the caller's parent record once.  guardian_links may have been
        # created with parent_user_id, with parent_id, or with both — so we
        # match on either identifier to avoid bypasses via partially-populated rows.
        parent_row = await gd_find_one(session, "parents", {"user_id": user_id})
        parent_row_id = parent_row.get("id") if parent_row else None
        _id_cond: dict = (
            {"$or": [{"parent_user_id": user_id}, {"parent_id": parent_row_id}]}
            if parent_row_id
            else {"parent_user_id": user_id}
        )

        # Authoritative check: an active guardian_links row with the required
        # permission flag(s) (when permission_type or permission_types is specified).
        link = await gd_find_one(
            session,
            "guardian_links",
            {**_id_cond, "student_id": student_id, "is_active": True},
        )
        if link:
            _perm_map = {
                "attendance": "can_view_attendance",
                "grades": "can_view_grades",
                "communicate": "can_communicate",
            }
            # Normalise to a list of types to check (permission_types takes precedence).
            _types_to_check = permission_types if permission_types else ([permission_type] if permission_type else [])
            _permissions = link.get("permissions") or {}
            for _pt in _types_to_check:
                _perm_key = _perm_map.get(_pt)
                if _perm_key and not _permissions.get(_perm_key, True):
                    _logger.debug(
                        "Guardian %s denied %s access to student %s: %s=False",
                        user_id, _pt, student_id, _perm_key,
                    )
                    return False
            return True
        # If an *inactive* guardian_links row exists the guardian was explicitly
        # unlinked.  Deny access even if a stale parents.student_ids entry remains.
        inactive_link = await gd_find_one(
            session,
            "guardian_links",
            {**_id_cond, "student_id": student_id, "is_active": False},
        )
        if inactive_link:
            return False
        # Legacy fallback: no guardian_links row exists at all — trust the legacy array.
        return bool(parent_row and student_id in (parent_row.get("student_ids") or []))

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


async def get_teacher_allowed_class_ids(session, teacher_id: str) -> set:
    """Canonical set of class_ids a regular/independent teacher may read
    (rosters, attendance, class-level reports).

    Source of truth = ACTIVE ``teacher_assignments`` ∪ ``class_sessions``.

    ``teacher_class_assignments`` is INTENTIONALLY EXCLUDED: it is a
    scheduling-convenience table that is auto-populated to link every
    teacher to every class in the school (see
    ``school_settings_mod._auto_populate_teacher_class_assignments``), so
    trusting it as a visibility source silently grants a teacher access to
    the entire school's rosters. ``can_view_class`` below checks single-class
    membership against these same two sources and MUST stay in sync with
    this helper. Only ``is_active != False`` assignments grant access so a
    soft-revoked assignment stops disclosing that class.
    """
    from engines.sql_utils import gd_find  # local import to avoid cycles

    if not teacher_id:
        return set()
    ta = await gd_find(
        session, "teacher_assignments",
        {"teacher_id": teacher_id, "is_active": {"$ne": False}}, limit=1000,
    )
    cs = await gd_find(
        session, "class_sessions", {"teacher_id": teacher_id}, limit=1000,
    )
    return {
        cid for cid in (
            [a.get("class_id") for a in ta] + [s.get("class_id") for s in cs]
        ) if cid
    }


async def can_view_class(session, current_user: dict, class_id: str) -> bool:
    """Return True iff `current_user` is authorized to read class-level data
    (attendance records, class reports, section summaries) for `class_id`.

    Allowed:
      - Platform admins.
      - School admin roles (principal / admin / sub_admin) — already tenant-scoped
        at the query level, so no extra check needed.
      - Teachers with a `teacher_assignments` or `class_sessions` row that links
        them directly to this class within the tenant.

    Same-tenant membership alone is not sufficient for teachers.
    """
    from engines.sql_utils import gd_find_one  # local import to avoid cycles

    if not class_id:
        return False

    role = current_user.get("role", "")
    if role in _PLATFORM_ROLES:
        return True
    if role in _SCHOOL_ADMIN_ROLES:
        return True

    user_id = current_user.get("id")
    teacher_id = current_user.get("teacher_id") or user_id

    if role in (UserRole.TEACHER.value, UserRole.INDEPENDENT_TEACHER.value):
        # Mirror get_teacher_allowed_class_ids(): only an ACTIVE assignment
        # grants access — a soft-revoked (is_active=False) row must stop
        # disclosing this class. teacher_class_assignments is never consulted.
        assign = await gd_find_one(
            session, "teacher_assignments",
            {"teacher_id": teacher_id, "class_id": class_id, "is_active": {"$ne": False}},
        )
        if assign:
            return True
        sess = await gd_find_one(
            session, "class_sessions", {"teacher_id": teacher_id, "class_id": class_id}
        )
        return bool(sess)

    return False


def require_can_view_class_sync_check(allowed: bool) -> None:
    """Raise the canonical 403 when `can_view_class` returned False."""
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="لا يمكنك الوصول لبيانات هذا الفصل",
        )


def assert_school_access(current_user: dict, school_id: str) -> None:
    """Raise 403 unless the caller belongs to school_id (or is platform admin).

    The single authoritative tenant guard for every timetable route.

    User-facing ``detail`` strings are safe Arabic copy (spec: no raw
    technical phrases like ``tenant`` / ``caller`` reach the UI). The
    underlying technical reason is captured in the server log so we can
    still debug. HTTP status codes are unchanged — fail-closed behavior
    is preserved exactly.
    """
    if not school_id:
        _logger.debug("assert_school_access: missing school_id for user=%s role=%s",
                      (current_user or {}).get("id"), (current_user or {}).get("role"))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="معرّف المدرسة مطلوب لإتمام هذه العملية",
        )
    if _is_platform_admin(current_user):
        return
    user_tenant = current_user.get("tenant_id") or current_user.get("school_id")
    if not user_tenant or str(user_tenant) != str(school_id):
        _logger.debug(
            "assert_school_access: tenant mismatch user=%s user_tenant=%s target=%s",
            (current_user or {}).get("id"), user_tenant, school_id,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="لا يمكن الوصول إلى بيانات هذه المدرسة من هذا الحساب",
        )


def resolve_school_id(current_user: dict, override: Optional[str]) -> Optional[str]:
    """Decide which school_id a request should operate on.

    Non-admins always operate on their own tenant; an override that
    matches their tenant is OK, an override that doesn't match is 403.

    Platform admins may only use a cross-tenant override when their token
    was minted by /role-switch/switch (i.e., carries is_impersonating=True
    and a tenant_id claim). A plain platform-admin access token must go
    through the MFA-gated, audited role-switch flow before operating inside
    any school's tenant. With no override they get None (caller decides).
    """
    if _is_platform_admin(current_user):
        if override is None:
            return None  # caller decides; no cross-tenant attempt
        # Reject cross-tenant override unless an active impersonation session
        # is present (token minted by /role-switch/switch with MFA + audit).
        if not current_user.get("is_impersonating"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="يجب استخدام مسار تبديل الدور للوصول إلى بيانات المدرسة",
            )
        # The switched token MUST carry the target tenant (set by /role-switch/switch).
        # Fail explicitly if the claim is absent to prevent issuance-path drift
        # from silently re-opening the bypass.
        token_tenant = current_user.get("tenant_id") or current_user.get("school_id")
        if not token_tenant:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="رمز الانتحال لا يحتوي على معرّف المدرسة المطلوب",
            )
        # The override (X-School-Context) must match the token's tenant to
        # prevent override-within-override escalation.
        if str(override) != str(token_tenant):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="لا يمكن تجاوز المدرسة المحددة في رمز الانتحال",
            )
        return override
    user_tenant = current_user.get("tenant_id") or current_user.get("school_id")
    if override is not None and str(override) != str(user_tenant):
        _logger.debug(
            "resolve_school_id: override mismatch user=%s user_tenant=%s override=%s",
            (current_user or {}).get("id"), user_tenant, override,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="لا يمكن الوصول إلى بيانات هذه المدرسة من هذا الحساب",
        )
    if not user_tenant:
        # Most common product cause for this branch is a school-side role
        # (e.g. teacher) whose account has not yet been linked to a real
        # school tenant. Keep the 403 (fail-closed) but surface a
        # friendly, actionable Arabic message — never the raw
        # ``caller has no tenant`` phrase.
        _logger.info(
            "resolve_school_id: caller has no tenant (likely unlinked account) user=%s role=%s",
            (current_user or {}).get("id"), (current_user or {}).get("role"),
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="هذا الحساب غير مرتبط بمدرسة حاليًا. يرجى التواصل مع إدارة المدرسة لإكمال ربط الحساب.",
        )
    return str(user_tenant)
