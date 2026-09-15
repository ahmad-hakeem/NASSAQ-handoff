"""Canonical parent → linked children resolver (Task #484).

Single source of truth used by both the Parent Portal dashboard
(`backend/routes/parent_portal_routes.py`) and the Hakim assistant
(`backend/routes/ai_routes_mod.py`) so the AI sees exactly the same
allow-list of students the dashboard renders — no more, no less.

Combines three linkage paths, in this order:

  1. Canonical ``students.parent_id`` / ``students.parent_user_id``
     against the parent's ``users.id`` AND, when known, the parent's
     ``parents.id`` (carried on the token as ``current_user['parent_id']``).
     This is the path that surfaces principal-managed linkages where
     ``students.parent_id`` holds a ``parents.id`` FK.

  2. ``guardian_links`` join table — active rows where ``parent_ref``
     matches any of the parent identifiers.

  3. ``parents.student_ids`` array on the parent's own ``parents`` row.

Paths 2 and 3 are best-effort and MUST fail safe: a missing
``guardian_links`` table or a malformed ``parents`` row must not
break the canonical path. Tenant scoping (``school_id``) is applied
to every legacy student fetch so a stale link can never leak a
foreign-tenant student. The parent portal has one narrow exception for a
reused/global parent account: an active canonical
``guardian_links.parent_ref == users.id`` may authorize a child in another
school only when the link tenant, student school, and (when present) parent
record all agree. Contact fields are never used for that exception.

This module is read-only and stateless.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from sqlalchemy.exc import OperationalError, ProgrammingError

from src.core.database.repository import Repos
db = Repos()
from engines.sql_utils import gd_find, gd_find_one


logger = logging.getLogger("nassaq.parent_children_resolution")

# Narrow set of DB errors that mean the optional legacy linkage surfaces
# are unreachable in this environment (missing table / column / blip).
# Mirrors `_LEGACY_LINKAGE_DB_ERRORS` in parent_portal_routes.py.
LEGACY_LINKAGE_DB_ERRORS = (ProgrammingError, OperationalError)


def parent_refs(current_user: Dict[str, Any]) -> List[str]:
    """Return every identifier that may have been used to link a parent:
    the ``users.id`` and the ``parents.id`` (if known)."""
    refs: List[str] = []
    uid = current_user.get("id")
    pid = current_user.get("parent_id")
    if uid:
        refs.append(uid)
    if pid and pid != uid:
        refs.append(pid)
    return refs


def _parent_or_conditions(refs: List[str]) -> List[Dict[str, Any]]:
    """Build a ``$or`` list matching ``students.parent_id`` /
    ``students.parent_user_id`` against any of the parent refs. Mutable
    contact fields (phone/email) are intentionally excluded."""
    conditions: List[Dict[str, Any]] = []
    seen = set()
    for pid in refs:
        if pid and pid not in seen:
            conditions.append({"parent_id": pid})
            conditions.append({"parent_user_id": pid})
            seen.add(pid)
    return conditions


async def _linked_student_ids(
    current_user: Dict[str, Any], school_id: Optional[str],
) -> List[str]:
    """Resolve extra student ids via the two legacy linkage paths.

    Returns the union of ``guardian_links`` student ids and the parent
    row's ``student_ids`` array. Each path is isolated so one broken
    path does not poison the other.
    """
    refs = parent_refs(current_user)
    if not refs:
        return []
    student_ids: set = set()

    # Path A: guardian_links — optional join table. Match against BOTH
    # the legacy `parent_ref` column (which may hold either a users.id
    # or a parents.id) AND the canonical `parent_user_id` column. Some
    # linkage flows only populate `parent_user_id`, so omitting it here
    # used to silently hide legitimate children.
    query: Dict[str, Any] = {
        "$or": [
            {"parent_ref": {"$in": refs}},
            {"parent_user_id": {"$in": refs}},
        ],
        "is_active": True,
    }
    if school_id:
        query["tenant_id"] = school_id
    try:
        links = await gd_find(db.session, "guardian_links", query, limit=50)
        for link in links:
            sid = link.get("student_id")
            if sid:
                student_ids.add(sid)
    except LEGACY_LINKAGE_DB_ERRORS as exc:
        logger.debug("guardian_links lookup degraded for parent %s: %s",
                     current_user.get("id"), exc)

    # Path B: parents.student_ids on the parent record.
    parent_record_id = current_user.get("parent_id")
    if parent_record_id:
        try:
            parent_rec = await gd_find_one(
                db.session, "parents", {"id": parent_record_id},
            )
            if parent_rec and isinstance(parent_rec.get("student_ids"), list):
                for sid in parent_rec["student_ids"]:
                    if sid:
                        student_ids.add(sid)
        except LEGACY_LINKAGE_DB_ERRORS as exc:
            logger.debug("parents.student_ids lookup degraded for parent %s: %s",
                         current_user.get("id"), exc)

    return list(student_ids)


async def _cross_school_guardian_children(
    current_user: Dict[str, Any],
    school_id: Optional[str],
) -> List[Dict[str, Any]]:
    """Resolve explicitly cross-school children through canonical links only.

    A parent's ``users.tenant_id`` is the account's historical/primary
    workspace, not proof that the account cannot have a child in another
    school.  The only safe exception to the normal tenant filter is an active
    ``guardian_links`` row whose ``parent_ref`` is this exact parent
    ``users.id``.

    This path is deliberately stricter than the legacy same-tenant fallbacks:

    * only authenticated parent identities may use it;
    * ``parent_ref`` must be the canonical user id (not a mutable contact
      field, and not a ``parents.id`` alias);
    * the link must name a tenant and that tenant must equal the student's
      ``school_id``;
    * when the link carries ``parent_id``, it must agree with both the
      student's parent FK and the school-scoped ``parents`` row;
    * a link without ``parent_id`` is accepted only for a student without a
      conflicting ``parent_id``.  A mismatched legacy FK therefore cannot be
      bypassed by adding a user-only link.

    The relation checks are intentionally fail-closed.  In particular, this
    helper never searches by email or phone and never treats an inactive link
    as evidence of access.
    """
    parent_user_id = current_user.get("id")
    if not parent_user_id or current_user.get("role") != "parent":
        return []

    # Do not rely solely on role claims supplied by a caller that invokes this
    # resolver directly.  The API dependency already loads the authoritative
    # users row, but this check keeps the shared resolver safe for its other
    # callers too and prevents a non-parent role from gaining the exceptional
    # cross-school path.
    parent_user = await gd_find_one(
        db.session,
        "users",
        {"id": parent_user_id, "role": "parent"},
    )
    if not parent_user or parent_user.get("is_active") is False:
        return []

    try:
        links = await gd_find(
            db.session,
            "guardian_links",
            {
                "parent_ref": parent_user_id,
                "is_active": True,
            },
            limit=500,
        )
    except LEGACY_LINKAGE_DB_ERRORS as exc:
        logger.debug(
            "cross-school guardian_links lookup degraded for parent %s: %s",
            parent_user_id,
            exc,
        )
        return []

    # Cross-school access is only the exception to the requested tenant's
    # normal legacy resolution.  Keep same-tenant links on the existing rules
    # so this change cannot broaden or otherwise alter those fallbacks.
    candidate_links = []
    candidate_student_ids: set[str] = set()
    candidate_parent_ids: set[str] = set()
    for link in links:
        link_school_id = link.get("tenant_id")
        student_id = link.get("student_id")
        if not link_school_id or not student_id:
            continue
        if school_id and link_school_id == school_id:
            continue
        # If a newer canonical column is present, it must not contradict the
        # canonical parent_ref that authorized this exceptional path.
        link_parent_user_id = link.get("parent_user_id")
        if link_parent_user_id and link_parent_user_id != parent_user_id:
            continue
        parent_id = link.get("parent_id")
        if parent_id:
            candidate_parent_ids.add(parent_id)
        candidate_student_ids.add(student_id)
        candidate_links.append(link)

    if not candidate_links:
        return []

    try:
        students = await gd_find(
            db.session,
            "students",
            {
                "id": {"$in": list(candidate_student_ids)},
                "is_active": True,
            },
            limit=len(candidate_student_ids),
        )
    except LEGACY_LINKAGE_DB_ERRORS as exc:
        logger.debug(
            "cross-school students lookup degraded for parent %s: %s",
            parent_user_id,
            exc,
        )
        return []

    students_by_id = {
        student.get("id"): student
        for student in students
        if student.get("id")
    }

    parent_rows: Dict[str, Dict[str, Any]] = {}
    if candidate_parent_ids:
        try:
            parent_records = await gd_find(
                db.session,
                "parents",
                {"id": {"$in": list(candidate_parent_ids)}},
                limit=len(candidate_parent_ids),
            )
        except LEGACY_LINKAGE_DB_ERRORS as exc:
            logger.debug(
                "cross-school parents lookup degraded for parent %s: %s",
                parent_user_id,
                exc,
            )
            return []
        parent_rows = {
            parent.get("id"): parent
            for parent in parent_records
            if parent.get("id")
        }

    children: List[Dict[str, Any]] = []
    seen_student_ids: set[str] = set()
    for link in candidate_links:
        student_id = link.get("student_id")
        student = students_by_id.get(student_id)
        link_school_id = link.get("tenant_id")
        if not student or student.get("school_id") != link_school_id:
            continue

        link_parent_id = link.get("parent_id")
        student_parent_id = student.get("parent_id")
        if link_parent_id:
            # A canonical link that names a parent record must agree with the
            # student's FK and with a parent row in the same school.
            if student_parent_id != link_parent_id:
                continue
            parent_record = parent_rows.get(link_parent_id)
            if (
                not parent_record
                or parent_record.get("school_id") != link_school_id
                or parent_record.get("is_active") is False
            ):
                continue
            linked_parent_user_id = parent_record.get("user_id")
            if linked_parent_user_id and linked_parent_user_id != parent_user_id:
                continue
        elif student_parent_id:
            # Without a parent_id on the link, a pre-existing student FK would
            # be an unresolved second identity.  Do not guess through contact
            # fields; reject the relation instead.
            continue

        student_parent_user_id = student.get("parent_user_id")
        if student_parent_user_id and student_parent_user_id != parent_user_id:
            continue
        if student_id in seen_student_ids:
            continue
        seen_student_ids.add(student_id)
        children.append(student)

    return children


async def resolve_parent_children(
    current_user: Dict[str, Any],
    school_id: Optional[str] = None,
    *,
    allow_cross_school_guardian_links: bool = True,
) -> List[Dict[str, Any]]:
    """Return the allow-list of students linked to this parent.

    Legacy ``students.parent_id``, ``students.parent_user_id``,
    ``guardian_links`` and ``parents.student_ids`` paths remain scoped to
    ``school_id`` exactly as before.  Parent portal callers additionally use
    the narrowly-validated canonical ``guardian_links.parent_ref`` exception
    so a reused/global parent account can see a child in another school.  A
    caller that must remain strictly tenant-pinned (for example Hakim's
    tenant-bound context) can disable that exception explicitly.
    """
    refs = parent_refs(current_user)
    if not refs:
        return []

    or_conditions = _parent_or_conditions(refs)
    children: List[Dict[str, Any]] = []
    if or_conditions:
        student_query: Dict[str, Any] = {"$or": or_conditions}
        if school_id:
            student_query["school_id"] = school_id
        student_query["is_active"] = True
        children = await gd_find(db.session, "students", student_query, limit=50)

    found_ids = {c.get("id") for c in children}
    linked_ids = await _linked_student_ids(current_user, school_id)
    missing_ids = [sid for sid in linked_ids if sid not in found_ids]
    if missing_ids:
        extra_q: Dict[str, Any] = {"id": {"$in": missing_ids}, "is_active": True}
        if school_id:
            extra_q["school_id"] = school_id
        extra = await gd_find(db.session, "students", extra_q, limit=50)
        children.extend(extra)

    if allow_cross_school_guardian_links:
        cross_school_children = await _cross_school_guardian_children(
            current_user,
            school_id,
        )
        existing_ids = {child.get("id") for child in children}
        children.extend(
            child for child in cross_school_children
            if child.get("id") not in existing_ids
        )
    return children


async def enrich_children_with_class_names(
    children: List[Dict[str, Any]],
    session: Any,
    school_id: Optional[str],
) -> List[Dict[str, Any]]:
    """Overwrite each child's ``class_name`` with the live value from the
    ``classes`` table, keyed by the child's ``class_id``.

    This corrects stale denormalized ``students.class_name`` values that were
    written at enrollment time and never updated when the student was moved.

    Guarantees:
    - Only classes belonging to ``school_id`` are fetched (tenant-scoped).
    - If a child has no ``class_id``, or no matching class row exists, the
      existing ``class_name`` value is kept as a fallback and a warning is
      logged (no PII, no raw DB internals exposed).
    - If the returned class row's ``id`` does not equal the student's
      ``class_id`` (a ``gd_find`` matching anomaly), the row is skipped and
      an error is logged; the child's ``class_name`` is left unchanged
      (fail-safe, not fail-hard).
    """
    if not children:
        return children

    class_ids = list({
        c.get("class_id") for c in children if c.get("class_id")
    })
    if not class_ids:
        return children

    query: Dict[str, Any] = {"id": {"$in": class_ids}}
    if school_id:
        query["school_id"] = school_id

    class_rows = await gd_find(session, "classes", query, limit=len(class_ids) + 10)

    class_map: Dict[str, str] = {}
    queried_ids = set(class_ids)
    for row in class_rows:
        row_id = row.get("id")
        if not row_id:
            continue
        if row_id not in queried_ids:
            logger.error(
                "enrich_children_with_class_names: gd_find returned unexpected "
                "class row id=%s (not in queried set) — skipping",
                row_id,
            )
            continue
        class_map[row_id] = row.get("name") or row.get("class_name") or ""

    for child in children:
        class_id = child.get("class_id")
        if not class_id:
            continue
        if class_id in class_map:
            child["class_name"] = class_map[class_id]
        else:
            logger.warning(
                "enrich_children_with_class_names: no class row found "
                "student_id=%s class_id=%s school_id=%s — keeping fallback",
                child.get("id"),
                class_id,
                school_id,
            )

    return children


__all__ = [
    "LEGACY_LINKAGE_DB_ERRORS",
    "parent_refs",
    "resolve_parent_children",
    "enrich_children_with_class_names",
]
