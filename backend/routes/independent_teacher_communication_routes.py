"""IT-only communication recipients router (Task #198 §5.6).

Surfaces exactly two cohorts to an Independent-Teacher caller:

  * ``my_students``  — every active ``users`` row whose
    ``tenant_id == itw_{user_id}`` AND ``role == 'student'``.
  * ``my_parents``   — every active ``users`` row whose
    ``tenant_id == itw_{user_id}`` AND ``role == 'parent'``,
    cross-checked against ``guardian_links`` so an orphan parent
    account never leaks into the picker.

Membership of an IT workspace is canonicalised on
``users.tenant_id`` — that is the field every IT student/parent
materialiser sets (see `backend/routes/student_creation_routes.py`),
and the same field the send-side validator
(`notification_routes_mod._it_validate_recipients_or_403`) checks.
Reading and writing via the same key keeps the picker and the send
path in lock-step and prevents tenant-scope drift.

Send paths live in ``notification_routes_mod.py``; this router is
read-only.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Query

from auth_scope import (
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


@router.get("/independent-teacher/communication/recipients")
async def list_recipients(
    cohort: str = Query(...),
    current_user: dict = Depends(_require_independent_teacher),
) -> Dict[str, Any]:
    if cohort not in _VALID_COHORTS:
        raise HTTPException(status_code=400, detail=_MSG_BAD_COHORT)

    school_id = require_request_school_id(current_user)
    # Surface a clean Arabic 404 when the IT has not bootstrapped yet
    # (the workspace gate in app/routes.py already blocks pre-bootstrap
    # callers, but the dedicated dependency here gives a clearer signal).
    await _resolve_workspace_teacher_id(current_user["id"], school_id)

    target_role = "student" if cohort == _COHORT_MY_STUDENTS else "parent"
    users = await gd_find(
        db.session, "users",
        {"tenant_id": school_id, "role": target_role, "is_active": True},
        limit=2000,
    )
    if not users:
        return {"cohort": cohort, "items": []}

    items: List[Dict[str, Any]] = []
    if cohort == _COHORT_MY_STUDENTS:
        # Defence-in-depth: re-assert tenant scoping on each row.
        for u in users:
            if u.get("tenant_id") != school_id:
                continue
            items.append({
                "user_id": u["id"],
                "full_name": u.get("full_name") or "",
            })
        return {"cohort": cohort, "items": items}

    # cohort == my_parents — require an active guardian_link in the
    # workspace so a stray parent user (e.g. left-over after unlink)
    # never appears in the picker.
    parent_ids = [u["id"] for u in users if u.get("tenant_id") == school_id]
    if not parent_ids:
        return {"cohort": cohort, "items": []}
    links = await gd_find(
        db.session, "guardian_links",
        {
            "parent_ref": {"$in": parent_ids},
            "tenant_id": school_id,
            "is_active": True,
        },
        limit=2000,
    )
    linked = {
        link["parent_ref"] for link in links
        if link.get("parent_ref") and link.get("tenant_id") == school_id
    }
    for u in users:
        if u["id"] not in linked:
            continue
        items.append({
            "user_id": u["id"],
            "full_name": u.get("full_name") or "",
        })
    return {"cohort": cohort, "items": items}


__all__ = ["router"]
