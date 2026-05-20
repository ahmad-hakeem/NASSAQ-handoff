"""Canonical student → parent-user resolution (Task #463).

Resolves the parent ``users.id`` for a given student inside the caller's
tenant. Used by the Teacher Communication Center "Homework Reminder"
send path so the recipient cohort is deterministic and tenant-safe.

Resolution order:
  1. Active ``guardian_links`` row scoped to the caller's tenant whose
     ``parent_ref`` resolves to a ``users`` row with ``role == 'parent'``
     in the same tenant. This is the canonical multi-guardian linkage.
  2. ``students.parent_id`` only when it resolves to a ``users`` row
     with ``role == 'parent'`` in the same tenant. Strict — never
     matches by mutable ``parent_email`` / ``parent_phone`` /
     ``parent_name`` columns (threat-model: those are documented weak
     parent-linkage paths).
  3. Otherwise ``None`` — caller raises a safe Arabic 404.

Both single and bulk variants are exposed. The bulk variant performs
at most one ``gd_find`` per table (``guardian_links``, ``users``,
``students``, ``users``) — no N+1 — so the "all parents in class"
send path can resolve in O(1) round-trips per table.
"""
from __future__ import annotations

from typing import Dict, List, Optional

from dependencies import db
from engines.sql_utils import gd_find, gd_find_one


PARENT_NOT_FOUND_AR = "لا يوجد ولي أمر مرتبط بهذا الطالب"


async def resolve_student_parent_user_id(
    student_id: str, tenant_id: str,
) -> Optional[str]:
    """Resolve the parent ``users.id`` for ``student_id`` in ``tenant_id``.

    See module docstring for the resolution order. Returns ``None`` when
    no canonical parent user exists in the same tenant.
    """
    if not student_id or not tenant_id:
        return None
    link = await gd_find_one(
        db.session, "guardian_links",
        {
            "student_id": student_id,
            "tenant_id": tenant_id,
            "is_active": True,
        },
    )
    if link and link.get("parent_ref"):
        parent_user = await gd_find_one(
            db.session, "users",
            {
                "id": link["parent_ref"],
                "role": "parent",
                "tenant_id": tenant_id,
            },
        )
        if parent_user and parent_user.get("id"):
            return parent_user["id"]

    student = await gd_find_one(
        db.session, "students",
        {"id": student_id, "school_id": tenant_id},
    )
    if student and student.get("parent_id"):
        parent_user = await gd_find_one(
            db.session, "users",
            {
                "id": student["parent_id"],
                "role": "parent",
                "tenant_id": tenant_id,
            },
        )
        if parent_user and parent_user.get("id"):
            return parent_user["id"]
    return None


async def resolve_students_parent_user_ids(
    student_ids: List[str], tenant_id: str,
) -> Dict[str, str]:
    """Bulk variant — returns ``{student_id: parent_user_id}`` for those
    that resolved. Skips students with no canonical linkage. At most
    one ``gd_find`` per table (no N+1)."""
    ids = [s for s in (student_ids or []) if s]
    if not ids or not tenant_id:
        return {}
    out: Dict[str, str] = {}

    links = await gd_find(
        db.session, "guardian_links",
        {
            "student_id": {"$in": ids},
            "tenant_id": tenant_id,
            "is_active": True,
        },
        limit=5000,
    )
    parent_ref_by_student: Dict[str, str] = {}
    for link in links:
        sid = link.get("student_id")
        pref = link.get("parent_ref")
        if sid and pref and sid not in parent_ref_by_student:
            parent_ref_by_student[sid] = pref
    if parent_ref_by_student:
        users = await gd_find(
            db.session, "users",
            {
                "id": {"$in": list(set(parent_ref_by_student.values()))},
                "role": "parent",
                "tenant_id": tenant_id,
            },
            limit=5000,
        )
        valid = {u["id"] for u in users if u.get("id")}
        for sid, pref in parent_ref_by_student.items():
            if pref in valid:
                out[sid] = pref

    remaining = [sid for sid in ids if sid not in out]
    if remaining:
        students = await gd_find(
            db.session, "students",
            {"id": {"$in": remaining}, "school_id": tenant_id},
            limit=5000,
        )
        candidate_by_sid: Dict[str, str] = {}
        for s in students:
            sid = s.get("id")
            pid = s.get("parent_id")
            if sid and pid:
                candidate_by_sid[sid] = pid
        if candidate_by_sid:
            users = await gd_find(
                db.session, "users",
                {
                    "id": {"$in": list(set(candidate_by_sid.values()))},
                    "role": "parent",
                    "tenant_id": tenant_id,
                },
                limit=5000,
            )
            valid = {u["id"] for u in users if u.get("id")}
            for sid, pid in candidate_by_sid.items():
                if pid in valid:
                    out[sid] = pid
    return out


__all__ = [
    "PARENT_NOT_FOUND_AR",
    "resolve_student_parent_user_id",
    "resolve_students_parent_user_ids",
]
