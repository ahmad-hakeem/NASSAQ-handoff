"""IT-only communication recipients router (Task #198 §5.6).

Surfaces exactly the two cohorts mandated by spec §5.6:

  * ``my_students``  — students whose ``school_id == itw_{user_id}``
    AND who are in one of the IT's classes (homeroom OR teacher_assignments).
  * ``my_parents``   — parent USERs linked, via ``guardian_links``
    (``tenant_id == itw_{user_id}`` AND ``is_active``), to those students.
    The legacy ``students.parent_id`` fallback is also honoured to mirror
    the canonical pattern in
    ``backend/routes/ai_routes_mod.py::_resolve_parent_linked_children``.

Response shape (per spec §5.6):
  * my_students → ``{user_id, full_name, student_id}``
  * my_parents  → ``{user_id, full_name, student_id, parent_id}``

Send paths live in ``notification_routes_mod.py``; this router is
read-only.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Set, Tuple

from fastapi import APIRouter, Depends, HTTPException, Query

from src.core.guards.tenant_guard import (
    INDEPENDENT_TEACHER_DENIED_AR,
    is_independent_teacher,
    require_request_school_id,
)
from dependencies import db, get_current_user
from engines.sql_utils import gd_find, gd_find_one

logger = logging.getLogger("nassaq.it_communication")

router = APIRouter()

_COHORT_MY_STUDENTS = "my_students"
_COHORT_MY_PARENTS = "my_parents"
_VALID_COHORTS = {_COHORT_MY_STUDENTS, _COHORT_MY_PARENTS}

_MSG_BAD_COHORT = "نوع المستلمين غير معروف."
_MSG_TEACHER_MISSING = "تعذّر التعرف على معلم المساحة."


async def _require_independent_teacher(
    current_user: dict = Depends(get_current_user),
) -> dict:
    if not is_independent_teacher(current_user):
        raise HTTPException(
            status_code=403, detail=INDEPENDENT_TEACHER_DENIED_AR,
        )
    return current_user


async def _resolve_workspace_teacher_id(user_id: str, school_id: str) -> str:
    teacher = await gd_find_one(
        db.session, "teachers",
        {"user_id": user_id, "school_id": school_id},
    )
    if not teacher:
        raise HTTPException(status_code=404, detail=_MSG_TEACHER_MISSING)
    return teacher["id"]


async def _teacher_class_ids(school_id: str, teacher_id: str) -> Set[str]:
    """Spec §5.6 — IT's class set = homeroom UNION teacher_assignments."""
    out: Set[str] = set()
    homerooms = await gd_find(
        db.session, "classes",
        {
            "school_id": school_id,
            "homeroom_teacher_id": teacher_id,
            "is_active": True,
        },
        limit=2000,
    )
    out.update(c["id"] for c in homerooms if c.get("id"))
    assignments = await gd_find(
        db.session, "teacher_assignments",
        {
            "school_id": school_id,
            "teacher_id": teacher_id,
            "is_active": True,
        },
        limit=2000,
    )
    out.update(
        a["class_id"] for a in assignments
        if a.get("class_id")
    )
    return out


async def _my_students_rows(school_id: str, teacher_id: str) -> List[dict]:
    """Return active students in the IT's classes, scoped to this workspace."""
    class_ids = await _teacher_class_ids(school_id, teacher_id)
    if not class_ids:
        return []
    return await gd_find(
        db.session, "students",
        {
            "school_id": school_id,
            "class_id": {"$in": list(class_ids)},
            "is_active": True,
        },
        limit=2000,
    )


async def _resolve_my_students_recipients(
    school_id: str, teacher_id: str,
) -> List[Dict[str, Any]]:
    students = await _my_students_rows(school_id, teacher_id)
    if not students:
        return []
    # students.email <-> users.email is the canonical link in the live
    # schema (students.user_id is not a real column); see
    # backend/routes/student_creation_routes.py.
    emails = [s["email"] for s in students if s.get("email")]
    if not emails:
        return []
    users = await gd_find(
        db.session, "users",
        {
            "email": {"$in": emails},
            "role": "student",
            "tenant_id": school_id,
            "is_active": True,
        },
        limit=2000,
    )
    by_email = {u["email"]: u for u in users if u.get("email")}
    out: List[Dict[str, Any]] = []
    for s in students:
        u = by_email.get(s.get("email"))
        if not u:
            continue
        # Defence-in-depth: re-assert tenant scoping on each row.
        if u.get("tenant_id") != school_id:
            continue
        out.append({
            "user_id": u["id"],
            "full_name": u.get("full_name") or s.get("full_name") or "",
            "student_id": s["id"],
        })
    return out


async def _resolve_my_parents_recipients(
    school_id: str, teacher_id: str,
) -> List[Dict[str, Any]]:
    students = await _my_students_rows(school_id, teacher_id)
    if not students:
        return []
    student_ids = [s["id"] for s in students if s.get("id")]
    if not student_ids:
        return []
    # Primary source of truth: active guardian_links scoped to the IT
    # workspace tenant. Mirrors _resolve_parent_linked_children in
    # ai_routes_mod.py.
    links = await gd_find(
        db.session, "guardian_links",
        {
            "student_id": {"$in": student_ids},
            "tenant_id": school_id,
            "is_active": True,
        },
        limit=2000,
    )
    pairs: List[Tuple[str, str, str]] = []  # (parent_user_id, parent_id, student_id)
    for link in links:
        if link.get("tenant_id") != school_id:
            continue
        pref = link.get("parent_ref")
        sid = link.get("student_id")
        pid = link.get("parent_id")
        if pref and sid:
            pairs.append((pref, pid or "", sid))
    # Legacy fallback — students.parent_id may point at a parents row that
    # has not yet been guardian_linked. Honour it but still require an
    # active parent USER inside the workspace tenant.
    legacy_parent_ids = [s["parent_id"] for s in students if s.get("parent_id")]
    if legacy_parent_ids:
        parents = await gd_find(
            db.session, "parents",
            {"id": {"$in": legacy_parent_ids}, "school_id": school_id},
            limit=2000,
        )
        emails_by_parent = {p["id"]: p.get("email") for p in parents}
        legacy_emails = [e for e in emails_by_parent.values() if e]
        legacy_users_by_email: Dict[str, dict] = {}
        if legacy_emails:
            for u in await gd_find(
                db.session, "users",
                {
                    "email": {"$in": legacy_emails},
                    "role": "parent",
                    "tenant_id": school_id,
                    "is_active": True,
                },
                limit=2000,
            ):
                if u.get("email"):
                    legacy_users_by_email[u["email"]] = u
        for s in students:
            pid = s.get("parent_id")
            if not pid:
                continue
            email = emails_by_parent.get(pid)
            if not email:
                continue
            user = legacy_users_by_email.get(email)
            if not user or user.get("tenant_id") != school_id:
                continue
            pairs.append((user["id"], pid, s["id"]))

    if not pairs:
        return []

    parent_user_ids = list({p[0] for p in pairs})
    users = await gd_find(
        db.session, "users",
        {
            "id": {"$in": parent_user_ids},
            "role": "parent",
            "tenant_id": school_id,
            "is_active": True,
        },
        limit=2000,
    )
    user_by_id = {
        u["id"]: u for u in users
        if u.get("id") and u.get("tenant_id") == school_id
    }

    seen: Set[str] = set()
    out: List[Dict[str, Any]] = []
    for pref, pid, sid in pairs:
        if pref in seen:
            continue
        u = user_by_id.get(pref)
        if not u:
            continue
        seen.add(pref)
        out.append({
            "user_id": u["id"],
            "full_name": u.get("full_name") or "",
            "student_id": sid,
            "parent_id": pid or None,
        })
    return out


@router.get("/independent-teacher/communication/recipients")
async def list_recipients(
    cohort: str = Query(...),
    current_user: dict = Depends(_require_independent_teacher),
) -> Dict[str, Any]:
    if cohort not in _VALID_COHORTS:
        raise HTTPException(status_code=400, detail=_MSG_BAD_COHORT)

    school_id = require_request_school_id(current_user)
    teacher_id = await _resolve_workspace_teacher_id(
        current_user["id"], school_id,
    )

    if cohort == _COHORT_MY_STUDENTS:
        items = await _resolve_my_students_recipients(school_id, teacher_id)
    else:
        items = await _resolve_my_parents_recipients(school_id, teacher_id)

    return {"cohort": cohort, "items": items}


__all__ = ["router"]
