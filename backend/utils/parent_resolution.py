"""Canonical student → parent-user resolution (Task #463).

Resolves the parent ``users.id`` for a given student inside the caller's
tenant. Used by the Teacher Communication Center "Homework Reminder"
send path so the recipient cohort is deterministic and tenant-safe.

Schema reality this resolver has to bridge
------------------------------------------
``students.parent_id`` is an FK to ``parents.id`` (NOT ``users.id``) —
see ``backend/pg_models.py`` Student model. ``guardian_links`` carries
two parent-side columns:

* ``parent_user_id`` — the canonical ``users.id`` (when known).
* ``parent_ref``     — populated by the principal-managed linkage path
  (`backend/routes/relationship_routes_mod.py`) as
  ``data.parent_id or data.parent_user_id``, so it may hold either a
  ``parents.id`` or a ``users.id``.

The ``parents`` table has no persisted ``user_id`` column (see the
comment in ``find_or_create_parent``). The canonical bridge from a
``parents`` row to its login account is therefore ``parents.email →
users.email`` with ``users.role == 'parent'`` in the same tenant —
the exact bridge ``find_or_create_parent`` uses to enrich
``existing_parent['user_id']`` for downstream guardian_links writes.

Resolution order (each step requires the resolved ``users`` row to have
``role == 'parent'`` and ``tenant_id == tenant_id``):

  1. ``guardian_links.parent_user_id`` — canonical users.id column.
  2. ``guardian_links.parent_ref`` interpreted as a ``users.id``
     (student-creation flow always writes the user id here).
  3. ``guardian_links.parent_ref`` interpreted as a ``parents.id`` →
     bridge through the parents row's ``email`` → ``users.email``.
  4. ``students.parent_id`` (FK to ``parents.id``) → same email bridge.
  5. Otherwise ``None`` — caller raises a safe Arabic 404.

The bridge uses ``parents.email`` (set at parent-account creation and
not mutated by normal flows). It deliberately does NOT use any of the
threat-modelled weak linkage columns on the student row itself
(``students.parent_email`` / ``parent_phone`` / ``parent_name``).

Both single and bulk variants are exposed. The bulk variant performs
a bounded number of ``gd_find`` calls per table — no N+1 — so the
"all parents in class" send path stays O(1) round-trips per table.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Set

from dependencies import db
from engines.sql_utils import gd_find, gd_find_one


PARENT_NOT_FOUND_AR = "لا يوجد ولي أمر مرتبط بهذا الطالب"


async def _validate_parent_user(
    candidate_user_id: Optional[str], tenant_id: str,
) -> Optional[str]:
    """Return ``candidate_user_id`` only when it resolves to a tenant-local
    ``users`` row with ``role == 'parent'``. Otherwise ``None``."""
    if not candidate_user_id:
        return None
    row = await gd_find_one(
        db.session, "users",
        {
            "id": candidate_user_id,
            "role": "parent",
            "tenant_id": tenant_id,
        },
    )
    if row and row.get("id"):
        return row["id"]
    return None


async def _bridge_parent_row_to_user_id(
    parent_id: Optional[str], tenant_id: str,
) -> Optional[str]:
    """Bridge ``parents.id`` → ``users.id`` via the parents row's email.

    Requires the ``parents`` row to be scoped to ``tenant_id`` and its
    ``email`` to resolve to an active ``users`` row with
    ``role == 'parent'`` and the same ``tenant_id``. No fallback to
    phone or name (threat-model: those are weak linkage columns).
    """
    if not parent_id:
        return None
    parent_row = await gd_find_one(
        db.session, "parents",
        {"id": parent_id, "school_id": tenant_id},
    )
    if not parent_row:
        return None
    email = parent_row.get("email")
    if not email:
        return None
    user_row = await gd_find_one(
        db.session, "users",
        {"email": email, "role": "parent", "tenant_id": tenant_id},
    )
    if user_row and user_row.get("id"):
        return user_row["id"]
    return None


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
    if link:
        # 1. Canonical ``parent_user_id`` column.
        resolved = await _validate_parent_user(
            link.get("parent_user_id"), tenant_id,
        )
        if resolved:
            return resolved
        ref = link.get("parent_ref")
        # 2. ``parent_ref`` written as the users.id (student-creation flow).
        resolved = await _validate_parent_user(ref, tenant_id)
        if resolved:
            return resolved
        # 3. ``parent_ref`` written as a parents.id (relationship flow) —
        #    bridge via parents.email → users.email.
        resolved = await _bridge_parent_row_to_user_id(ref, tenant_id)
        if resolved:
            return resolved

    # 4. ``students.parent_id`` (FK to parents.id) → email bridge. This
    #    is the path that covers the Teacher Communication Center
    #    "Homework Reminder" false-positive — every student created via
    #    the principal flow has students.parent_id set to a parents.id.
    student = await gd_find_one(
        db.session, "students",
        {"id": student_id, "school_id": tenant_id, "is_active": True},
    )
    if student and student.get("parent_id"):
        parent_id = student["parent_id"]
        resolved = await _bridge_parent_row_to_user_id(parent_id, tenant_id)
        if resolved:
            return resolved
        # Some legacy seed/test fixtures set students.parent_id directly
        # to a users.id. Strict role + tenant validation.
        resolved = await _validate_parent_user(parent_id, tenant_id)
        if resolved:
            return resolved
    return None


async def resolve_students_parent_user_ids(
    student_ids: List[str], tenant_id: str,
) -> Dict[str, str]:
    """Bulk variant — returns ``{student_id: parent_user_id}`` for those
    that resolved. Skips students with no canonical linkage. Bounded
    ``gd_find`` calls per table (no N+1)."""
    ids = [s for s in (student_ids or []) if s]
    if not ids or not tenant_id:
        return {}
    out: Dict[str, str] = {}

    # ------------------------------------------------------------------
    # Stage 1 — guardian_links lookup. Collect candidate users.id values
    # from `parent_user_id` and from `parent_ref` (which may be either a
    # users.id or a parents.id).
    # ------------------------------------------------------------------
    links = await gd_find(
        db.session, "guardian_links",
        {
            "student_id": {"$in": ids},
            "tenant_id": tenant_id,
            "is_active": True,
        },
        limit=5000,
    )

    user_candidates_by_student: Dict[str, List[str]] = {}
    parent_id_candidates_by_student: Dict[str, List[str]] = {}
    for link in links:
        sid = link.get("student_id")
        if not sid:
            continue
        pu = link.get("parent_user_id")
        if pu:
            user_candidates_by_student.setdefault(sid, []).append(pu)
        ref = link.get("parent_ref")
        if ref:
            # `ref` may be either a users.id (student-creation flow) or a
            # parents.id (relationship flow). Check both.
            user_candidates_by_student.setdefault(sid, []).append(ref)
            parent_id_candidates_by_student.setdefault(sid, []).append(ref)

    # Stage 2 — bulk-validate user candidates against `users`.
    all_user_candidates: Set[str] = {
        u for v in user_candidates_by_student.values() for u in v
    }
    valid_parent_users: Set[str] = set()
    if all_user_candidates:
        users = await gd_find(
            db.session, "users",
            {
                "id": {"$in": list(all_user_candidates)},
                "role": "parent",
                "tenant_id": tenant_id,
            },
            limit=5000,
        )
        valid_parent_users = {u["id"] for u in users if u.get("id")}
    for sid, cands in user_candidates_by_student.items():
        for c in cands:
            if c in valid_parent_users:
                out[sid] = c
                break

    # Stage 3 — bridge remaining guardian_links.parent_ref values that
    # turned out to be parents.id (not users.id) via parents.email.
    remaining = [sid for sid in ids if sid not in out]
    pending_parent_ids: Set[str] = set()
    for sid in remaining:
        for pid in parent_id_candidates_by_student.get(sid, []):
            pending_parent_ids.add(pid)

    parent_email_by_id: Dict[str, str] = {}
    if pending_parent_ids:
        parent_rows = await gd_find(
            db.session, "parents",
            {
                "id": {"$in": list(pending_parent_ids)},
                "school_id": tenant_id,
            },
            limit=5000,
        )
        for p in parent_rows:
            pid = p.get("id")
            em = p.get("email")
            if pid and em:
                parent_email_by_id[pid] = em

    # Stage 4 — also bridge students.parent_id for anything still missing.
    student_parent_id: Dict[str, str] = {}
    still_missing = [sid for sid in ids if sid not in out]
    if still_missing:
        students = await gd_find(
            db.session, "students",
            {"id": {"$in": still_missing}, "school_id": tenant_id, "is_active": True},
            limit=5000,
        )
        student_legacy_user_candidates: Dict[str, str] = {}
        for s in students:
            sid = s.get("id")
            pid = s.get("parent_id")
            if sid and pid:
                student_parent_id[sid] = pid
                # Also keep pid as a legacy users.id candidate (some seed
                # data sets students.parent_id directly to a users.id).
                student_legacy_user_candidates[sid] = pid

        # Bulk-load any parents rows we haven't already fetched.
        new_pids = {
            pid for pid in student_parent_id.values()
            if pid not in parent_email_by_id
        }
        if new_pids:
            parent_rows = await gd_find(
                db.session, "parents",
                {"id": {"$in": list(new_pids)}, "school_id": tenant_id},
                limit=5000,
            )
            for p in parent_rows:
                pid = p.get("id")
                em = p.get("email")
                if pid and em:
                    parent_email_by_id[pid] = em

        # Legacy users.id candidates need validation against users table.
        if student_legacy_user_candidates:
            legacy_ids = list(set(student_legacy_user_candidates.values()))
            legacy_users = await gd_find(
                db.session, "users",
                {
                    "id": {"$in": legacy_ids},
                    "role": "parent",
                    "tenant_id": tenant_id,
                },
                limit=5000,
            )
            legacy_valid = {u["id"] for u in legacy_users if u.get("id")}
            for sid, cand in student_legacy_user_candidates.items():
                if sid not in out and cand in legacy_valid:
                    out[sid] = cand

    # Stage 5 — bulk-resolve all collected parent emails to users.
    all_emails: Set[str] = set(parent_email_by_id.values())
    email_to_user_id: Dict[str, str] = {}
    if all_emails:
        users = await gd_find(
            db.session, "users",
            {
                "email": {"$in": list(all_emails)},
                "role": "parent",
                "tenant_id": tenant_id,
            },
            limit=5000,
        )
        for u in users:
            em = u.get("email")
            uid = u.get("id")
            if em and uid:
                email_to_user_id[em] = uid

    # Apply bridge results for guardian_links.parent_ref-as-parents.id.
    for sid in [s for s in ids if s not in out]:
        for pid in parent_id_candidates_by_student.get(sid, []):
            em = parent_email_by_id.get(pid)
            uid = email_to_user_id.get(em) if em else None
            if uid:
                out[sid] = uid
                break

    # Apply bridge results for students.parent_id.
    for sid, pid in student_parent_id.items():
        if sid in out:
            continue
        em = parent_email_by_id.get(pid)
        uid = email_to_user_id.get(em) if em else None
        if uid:
            out[sid] = uid

    return out


__all__ = [
    "PARENT_NOT_FOUND_AR",
    "resolve_student_parent_user_id",
    "resolve_students_parent_user_ids",
]
