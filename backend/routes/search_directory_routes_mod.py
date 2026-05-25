"""
NASSAQ Route Module: Search & Directory Engine
Unified search across all entities, user directory, and autocomplete.
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Optional, List
from datetime import datetime, timezone
import re

from dependencies import (
    db, get_current_user, require_roles, UserRole, logger
)
from engines.sql_utils import gd_find, gd_find_one, gd_insert, gd_insert_many, gd_update_one, gd_update_many, gd_count, gd_delete_one, gd_delete_many, gd_distinct
from auth_scope import require_request_school_id


router = APIRouter()

ADMIN_ROLES = [UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.SCHOOL_SUB_ADMIN]

_STAFF_ROLES = [
    UserRole.PLATFORM_ADMIN,
    UserRole.SCHOOL_PRINCIPAL,
    UserRole.SCHOOL_ADMIN,
    UserRole.SCHOOL_SUB_ADMIN,
    UserRole.TEACHER,
    UserRole.INDEPENDENT_TEACHER,
]

_STAFF_ROLE_VALUES = frozenset(r.value for r in _STAFF_ROLES)

_ADMIN_ROLE_VALUES = frozenset(r.value for r in ADMIN_ROLES)

_STAFF_ROLES_SET = frozenset({r.value for r in ADMIN_ROLES} | {"teacher", "independent_teacher"})


def _is_staff(current_user: dict) -> bool:
    return current_user.get("role", "") in _STAFF_ROLES_SET


def _is_admin(current_user: dict) -> bool:
    return current_user.get("role", "") in _ADMIN_ROLE_VALUES


async def _get_teacher_class_ids(school_id: str, current_user: dict) -> List[str]:
    """Return the class IDs the calling teacher is assigned to.

    Checks both ``teacher_assignments`` and ``class_sessions`` so that
    schedule-only assignments are included.  Returns an empty list when the
    teacher has no assignments — callers must treat that as zero-access.
    """
    user_id = current_user.get("id", "")
    teacher_id = current_user.get("teacher_id") or user_id
    assignments = await gd_find(
        db.session, "teacher_assignments",
        {"tenant_id": school_id, "teacher_id": teacher_id, "is_active": True},
        limit=500,
    )
    class_ids: set = {a["class_id"] for a in assignments if a.get("class_id")}
    if not class_ids:
        sessions = await gd_find(
            db.session, "class_sessions",
            {"tenant_id": school_id, "teacher_id": teacher_id},
            limit=500,
        )
        class_ids = {s["class_id"] for s in sessions if s.get("class_id")}
    return list(class_ids)


@router.get("/search/global")
async def global_search(
    q: str = Query(..., min_length=1),
    entity_type: Optional[str] = None,
    limit: int = 20,
    current_user: dict = Depends(get_current_user)
):
    """Unified search across students, teachers, parents, classes, subjects.

    SECURITY: Student and parent records contain personal and family PII.
    Only staff roles (admins, principals, teachers) may search for students
    or parents.  Low-privilege users (student, parent) receive empty lists
    for those entity types so they cannot enumerate other families.
    """
    # Task #155: fail-closed school-id resolution; see audit row #3.
    school_id = require_request_school_id(current_user)
    caller_is_staff = _is_staff(current_user)

    pattern = {"$regex": re.escape(q), "$options": "i"}
    results = {"students": [], "teachers": [], "parents": [], "classes": [], "subjects": [], "total": 0}

    tenant_filter = {"tenant_id": school_id}

    caller_is_admin = _is_admin(current_user)

    if caller_is_staff and (not entity_type or entity_type == "student"):
        student_query = {**tenant_filter, "is_active": True, "$or": [
            {"full_name": pattern}, {"national_id": pattern},
            {"email": pattern}, {"student_number": pattern},
        ]}
        if not caller_is_admin:
            teacher_class_ids = await _get_teacher_class_ids(school_id, current_user)
            if not teacher_class_ids:
                teacher_class_ids = ["__no_access__"]
            student_query["class_id"] = {"$in": teacher_class_ids}
        students = await gd_find(db.session, "students", student_query, limit=limit)
        results["students"] = [dict(s, entity_type="student") for s in students]

    if not entity_type or entity_type == "teacher":
        teachers = await gd_find(db.session, "users", {**tenant_filter, "role": "teacher", "$or": [
                {"full_name": pattern}, {"email": pattern}, {"phone": pattern}
            ]}, limit=limit)
        results["teachers"] = [dict(t, entity_type="teacher") for t in teachers]

    parent_filter = {"school_id": school_id}
    if caller_is_admin and (not entity_type or entity_type == "parent"):
        parents = await gd_find(db.session, "parents", {**parent_filter, "$or": [
                {"full_name": pattern}, {"phone": pattern},
                {"email": pattern}, {"national_id": pattern}
            ]}, limit=limit)
        results["parents"] = [dict(p, entity_type="parent") for p in parents]

    if not entity_type or entity_type == "class":
        classes = await gd_find(db.session, "classes", {**tenant_filter, "$or": [{"name": pattern}, {"name_en": pattern}]}, limit=limit)
        results["classes"] = [dict(c, entity_type="class") for c in classes]

    if not entity_type or entity_type == "subject":
        subjects = await gd_find(db.session, "subjects", {**tenant_filter, "$or": [{"name": pattern}, {"name_en": pattern}]}, limit=limit)
        results["subjects"] = [dict(s, entity_type="subject") for s in subjects]

    results["total"] = sum(len(v) for k, v in results.items() if isinstance(v, list))
    results["query"] = q
    return results


@router.get("/search/autocomplete")
async def autocomplete_search(
    q: str = Query(..., min_length=1),
    entity_type: str = "all",
    limit: int = 10,
    current_user: dict = Depends(get_current_user)
):
    """Fast autocomplete for search fields.

    SECURITY: Student and parent names are PII; autocomplete for those
    types is restricted to staff roles only.  Non-staff callers silently
    receive only teacher/class suggestions.
    """
    # Task #155: shared school-id adapter for consistency. Audit row #4
    # classified the prior pattern as inconsistent-but-not-exploitable, but
    # we still gate on the canonical fail-closed resolver.
    school_id = require_request_school_id(current_user)
    caller_is_staff = _is_staff(current_user)
    caller_is_admin = _is_admin(current_user)
    pattern = {"$regex": f"^{re.escape(q)}", "$options": "i"}
    suggestions = []

    if caller_is_staff and entity_type in ("all", "student"):
        student_query: dict = {"tenant_id": school_id, "is_active": True, "full_name": pattern}
        if not caller_is_admin:
            teacher_class_ids = await _get_teacher_class_ids(school_id, current_user)
            if not teacher_class_ids:
                teacher_class_ids = ["__no_access__"]
            student_query["class_id"] = {"$in": teacher_class_ids}
        students = await gd_find(db.session, "students", student_query, limit=limit)
        suggestions.extend([{"id": s["id"], "label": s["full_name"], "type": "student"} for s in students])

    if entity_type in ("all", "teacher"):
        teachers = await gd_find(db.session, "users", {"tenant_id": school_id, "role": "teacher", "full_name": pattern}, limit=limit)
        suggestions.extend([{"id": t["id"], "label": t["full_name"], "type": "teacher"} for t in teachers])

    if caller_is_admin and entity_type in ("all", "parent"):
        parents = await gd_find(db.session, "parents", {"school_id": school_id, "full_name": pattern}, limit=limit)
        suggestions.extend([{"id": p["id"], "label": p["full_name"], "type": "parent"} for p in parents])

    return {"suggestions": suggestions[:limit], "query": q}


@router.get("/directory/students")
async def directory_students(
    class_id: Optional[str] = None,
    grade_level: Optional[str] = None,
    gender: Optional[str] = None,
    sort_by: str = "full_name",
    page: int = 1,
    per_page: int = 50,
    current_user: dict = Depends(require_roles([
        UserRole.PLATFORM_ADMIN,
        UserRole.SCHOOL_PRINCIPAL,
        UserRole.SCHOOL_ADMIN,
        UserRole.SCHOOL_SUB_ADMIN,
        UserRole.TEACHER,
        UserRole.INDEPENDENT_TEACHER,
    ]))
):
    """Student directory with filters and pagination.

    SECURITY: Admin roles see the full school directory. Teacher and
    independent-teacher callers are scoped to only the classes they are
    assigned to — they cannot enumerate students outside their classroom.
    Parent and student roles are blocked entirely by require_roles.
    """
    # Task #155: fail-closed school-id resolution; see audit row #5.
    school_id = require_request_school_id(current_user)
    query: dict = {"tenant_id": school_id, "is_active": True}

    caller_role = current_user.get("role", "")
    caller_is_teacher = caller_role in (UserRole.TEACHER.value, UserRole.INDEPENDENT_TEACHER.value)

    if caller_is_teacher:
        teacher_class_ids = await _get_teacher_class_ids(school_id, current_user)
        if not teacher_class_ids:
            return {"students": [], "total": 0, "page": page, "per_page": per_page, "total_pages": 0}
        if class_id:
            if class_id not in teacher_class_ids:
                raise HTTPException(status_code=403, detail="لا يمكنك الاطلاع على طلاب هذا الفصل")
            query["class_id"] = class_id
        else:
            query["class_id"] = {"$in": teacher_class_ids}
    else:
        if class_id:
            query["class_id"] = class_id

    if grade_level:
        query["grade_level"] = grade_level
    if gender:
        query["gender"] = gender

    total = await gd_count(db.session, "students", query)
    skip = (page - 1) * per_page

    students = await gd_find(db.session, "students", query, order_by=sort_by, desc_order=False, offset=skip, limit=per_page)

    return {
        "students": students,
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": (total + per_page - 1) // per_page
    }


@router.get("/directory/teachers")
async def directory_teachers(
    subject_id: Optional[str] = None,
    sort_by: str = "full_name",
    page: int = 1,
    per_page: int = 50,
    current_user: dict = Depends(get_current_user)
):
    """Teacher directory with filters and pagination"""
    # Task #155: fail-closed school-id resolution; see audit row #6.
    school_id = require_request_school_id(current_user)
    query = {"role": "teacher", "tenant_id": school_id}

    total = await gd_count(db.session, "users", query)
    skip = (page - 1) * per_page

    teachers = await gd_find(db.session, "users", query, order_by=sort_by, desc_order=False, offset=skip, limit=per_page)

    if subject_id:
        assignments = await gd_find(db.session, "teacher_assignments", {"tenant_id": school_id, "subject_id": subject_id, "is_active": True}, limit=500)
        teacher_ids = {a["teacher_id"] for a in assignments}
        teachers = [t for t in teachers if t["id"] in teacher_ids]

    return {
        "teachers": teachers,
        "total": total if not subject_id else len(teachers),
        "page": page,
        "per_page": per_page
    }


@router.get("/directory/parents")
async def directory_parents(
    page: int = 1,
    per_page: int = 50,
    current_user: dict = Depends(require_roles([
        UserRole.PLATFORM_ADMIN,
        UserRole.SCHOOL_PRINCIPAL,
        UserRole.SCHOOL_ADMIN,
        UserRole.SCHOOL_SUB_ADMIN,
    ]))
):
    """Parent directory with children info.

    SECURITY: Restricted to admin roles only. The parent directory
    exposes personal contact information and family-linkage data for all
    parents in the school and must not be accessible to teachers,
    students, or other parents.
    """
    # Task #155: fail-closed school-id resolution; see audit row #7.
    school_id = require_request_school_id(current_user)
    query = {"school_id": school_id}

    total = await gd_count(db.session, "parents", query)
    skip = (page - 1) * per_page

    parents = await gd_find(db.session, "parents", query, order_by="full_name", desc_order=False, offset=skip, limit=per_page)

    for p in parents:
        children = await gd_find(db.session, "students", {"tenant_id": school_id, "is_active": True, "$or": [
                {"parent_id": p["id"]},
                {"parent_user_id": p.get("user_id")}
            ]}, limit=20)
        p["children"] = children
        p["children_count"] = len(children)

    return {
        "parents": parents,
        "total": total,
        "page": page,
        "per_page": per_page
    }


@router.get("/directory/classes")
async def directory_classes(
    grade_level: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """Class directory with student counts"""
    # Task #155: fail-closed school-id resolution; see audit row #8.
    school_id = require_request_school_id(current_user)
    query = {"tenant_id": school_id}
    if grade_level:
        query["grade_level"] = grade_level

    classes = await gd_find(db.session, "classes", query, order_by="name", desc_order=False, limit=200)

    for c in classes:
        c["student_count"] = await gd_count(db.session, "students", {"tenant_id": school_id, "class_id": c["id"]})
        c["teacher_count"] = await gd_count(db.session, "teacher_assignments", {"tenant_id": school_id, "class_id": c["id"], "is_active": True})

    return {"classes": classes, "total": len(classes)}


@router.get("/directory/statistics")
async def directory_statistics(
    current_user: dict = Depends(get_current_user)
):
    """Get overall directory statistics"""
    # Task #155: fail-closed school-id resolution; see audit row #9.
    school_id = require_request_school_id(current_user)
    t_filter = {"tenant_id": school_id}
    s_filter = {"school_id": school_id}

    students_total = await gd_count(db.session, "students", t_filter)
    students_active = await gd_count(db.session, "students", {**t_filter, "is_active": {"$ne": False}})
    teachers_total = await gd_count(db.session, "users", {**t_filter, "role": "teacher"})
    parents_total = await gd_count(db.session, "parents", s_filter)
    classes_total = await gd_count(db.session, "classes", t_filter)
    subjects_total = await gd_count(db.session, "subjects", t_filter)

    gender_dist = {}
    for g in ["male", "female"]:
        gender_dist[g] = await gd_count(db.session, "students", {**t_filter, "gender": g})

    return {
        "students": {"total": students_total, "active": students_active, "by_gender": gender_dist},
        "teachers": {"total": teachers_total},
        "parents": {"total": parents_total},
        "classes": {"total": classes_total},
        "subjects": {"total": subjects_total}
    }
