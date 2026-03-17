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

router = APIRouter()

ADMIN_ROLES = [UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.SCHOOL_SUB_ADMIN]


@router.get("/search/global")
async def global_search(
    q: str = Query(..., min_length=1),
    entity_type: Optional[str] = None,
    limit: int = 20,
    current_user: dict = Depends(get_current_user)
):
    """Unified search across students, teachers, parents, classes, subjects"""
    school_id = current_user.get("tenant_id") or current_user.get("school_id")

    pattern = {"$regex": re.escape(q), "$options": "i"}
    results = {"students": [], "teachers": [], "parents": [], "classes": [], "subjects": [], "total": 0}

    tenant_filter = {"tenant_id": school_id} if school_id else {}

    if not entity_type or entity_type == "student":
        students = await db.students.find(
            {**tenant_filter, "$or": [
                {"full_name": pattern}, {"national_id": pattern},
                {"email": pattern}, {"student_number": pattern}
            ]},
            {"_id": 0, "id": 1, "full_name": 1, "class_id": 1, "grade_level": 1, "gender": 1, "email": 1}
        ).limit(limit).to_list(limit)
        results["students"] = [dict(s, entity_type="student") for s in students]

    if not entity_type or entity_type == "teacher":
        teachers = await db.users.find(
            {**tenant_filter, "role": "teacher", "$or": [
                {"full_name": pattern}, {"email": pattern}, {"phone": pattern}
            ]},
            {"_id": 0, "id": 1, "full_name": 1, "email": 1, "phone": 1, "specialization": 1}
        ).limit(limit).to_list(limit)
        results["teachers"] = [dict(t, entity_type="teacher") for t in teachers]

    parent_filter = {"school_id": school_id} if school_id else {}
    if not entity_type or entity_type == "parent":
        parents = await db.parents.find(
            {**parent_filter, "$or": [
                {"full_name": pattern}, {"phone": pattern},
                {"email": pattern}, {"national_id": pattern}
            ]},
            {"_id": 0, "id": 1, "full_name": 1, "phone": 1, "email": 1, "relationship": 1}
        ).limit(limit).to_list(limit)
        results["parents"] = [dict(p, entity_type="parent") for p in parents]

    if not entity_type or entity_type == "class":
        classes = await db.classes.find(
            {**tenant_filter, "$or": [{"name": pattern}, {"name_en": pattern}]},
            {"_id": 0, "id": 1, "name": 1, "name_en": 1, "grade_level": 1, "capacity": 1}
        ).limit(limit).to_list(limit)
        results["classes"] = [dict(c, entity_type="class") for c in classes]

    if not entity_type or entity_type == "subject":
        subjects = await db.subjects.find(
            {**tenant_filter, "$or": [{"name": pattern}, {"name_en": pattern}]},
            {"_id": 0, "id": 1, "name": 1, "name_en": 1, "code": 1}
        ).limit(limit).to_list(limit)
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
    """Fast autocomplete for search fields"""
    school_id = current_user.get("tenant_id")
    pattern = {"$regex": f"^{re.escape(q)}", "$options": "i"}
    suggestions = []

    if entity_type in ("all", "student"):
        students = await db.students.find(
            {"tenant_id": school_id, "full_name": pattern},
            {"_id": 0, "id": 1, "full_name": 1}
        ).limit(limit).to_list(limit)
        suggestions.extend([{"id": s["id"], "label": s["full_name"], "type": "student"} for s in students])

    if entity_type in ("all", "teacher"):
        teachers = await db.users.find(
            {"tenant_id": school_id, "role": "teacher", "full_name": pattern},
            {"_id": 0, "id": 1, "full_name": 1}
        ).limit(limit).to_list(limit)
        suggestions.extend([{"id": t["id"], "label": t["full_name"], "type": "teacher"} for t in teachers])

    if entity_type in ("all", "parent"):
        parents = await db.parents.find(
            {"school_id": school_id, "full_name": pattern},
            {"_id": 0, "id": 1, "full_name": 1}
        ).limit(limit).to_list(limit)
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
    current_user: dict = Depends(get_current_user)
):
    """Student directory with filters and pagination"""
    school_id = current_user.get("tenant_id") or current_user.get("school_id")
    query = {}
    if school_id:
        query["tenant_id"] = school_id
    if class_id:
        query["class_id"] = class_id
    if grade_level:
        query["grade_level"] = grade_level
    if gender:
        query["gender"] = gender

    total = await db.students.count_documents(query)
    skip = (page - 1) * per_page

    students = await db.students.find(
        query,
        {"_id": 0, "id": 1, "full_name": 1, "email": 1, "gender": 1,
         "class_id": 1, "class_name": 1, "grade_level": 1, "national_id": 1,
         "date_of_birth": 1, "parent_phone": 1, "is_active": 1}
    ).sort(sort_by, 1).skip(skip).limit(per_page).to_list(per_page)

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
    school_id = current_user.get("tenant_id") or current_user.get("school_id")
    query = {"role": "teacher"}
    if school_id:
        query["tenant_id"] = school_id

    total = await db.users.count_documents(query)
    skip = (page - 1) * per_page

    teachers = await db.users.find(
        query,
        {"_id": 0, "id": 1, "full_name": 1, "email": 1, "phone": 1,
         "specialization": 1, "is_active": 1, "created_at": 1}
    ).sort(sort_by, 1).skip(skip).limit(per_page).to_list(per_page)

    if subject_id:
        assignments = await db.teacher_assignments.find(
            {"tenant_id": school_id, "subject_id": subject_id, "is_active": True},
            {"_id": 0, "teacher_id": 1}
        ).to_list(500)
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
    current_user: dict = Depends(get_current_user)
):
    """Parent directory with children info"""
    school_id = current_user.get("tenant_id") or current_user.get("school_id")
    query = {}
    if school_id:
        query["school_id"] = school_id

    total = await db.parents.count_documents(query)
    skip = (page - 1) * per_page

    parents = await db.parents.find(
        query, {"_id": 0}
    ).sort("full_name", 1).skip(skip).limit(per_page).to_list(per_page)

    for p in parents:
        children = await db.students.find(
            {"tenant_id": school_id, "$or": [
                {"parent_id": p["id"]},
                {"parent_user_id": p.get("user_id")}
            ]},
            {"_id": 0, "id": 1, "full_name": 1, "class_name": 1}
        ).to_list(20)
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
    school_id = current_user.get("tenant_id") or current_user.get("school_id")
    query = {}
    if school_id:
        query["tenant_id"] = school_id
    if grade_level:
        query["grade_level"] = grade_level

    classes = await db.classes.find(query, {"_id": 0}).sort("name", 1).to_list(200)

    for c in classes:
        c["student_count"] = await db.students.count_documents(
            {"tenant_id": school_id, "class_id": c["id"]}
        )
        c["teacher_count"] = await db.teacher_assignments.count_documents(
            {"tenant_id": school_id, "class_id": c["id"], "is_active": True}
        )

    return {"classes": classes, "total": len(classes)}


@router.get("/directory/statistics")
async def directory_statistics(
    current_user: dict = Depends(get_current_user)
):
    """Get overall directory statistics"""
    school_id = current_user.get("tenant_id") or current_user.get("school_id")
    t_filter = {"tenant_id": school_id} if school_id else {}
    s_filter = {"school_id": school_id} if school_id else {}

    students_total = await db.students.count_documents(t_filter)
    students_active = await db.students.count_documents({**t_filter, "is_active": {"$ne": False}})
    teachers_total = await db.users.count_documents({**t_filter, "role": "teacher"})
    parents_total = await db.parents.count_documents(s_filter)
    classes_total = await db.classes.count_documents(t_filter)
    subjects_total = await db.subjects.count_documents(t_filter)

    gender_dist = {}
    for g in ["male", "female"]:
        gender_dist[g] = await db.students.count_documents({**t_filter, "gender": g})

    return {
        "students": {"total": students_total, "active": students_active, "by_gender": gender_dist},
        "teachers": {"total": teachers_total},
        "parents": {"total": parents_total},
        "classes": {"total": classes_total},
        "subjects": {"total": subjects_total}
    }
