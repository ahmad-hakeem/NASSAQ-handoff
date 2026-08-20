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
to every student fetch so a stale link can never leak a foreign-tenant
student.

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


async def resolve_parent_children(
    current_user: Dict[str, Any],
    school_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Return the tenant-scoped allow-list of students linked to this
    parent across all three linkage paths."""
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
