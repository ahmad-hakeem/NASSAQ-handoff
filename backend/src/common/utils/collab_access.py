"""IT §6.7 cross-workspace co-teaching access helpers.

The single sanctioned cross-tenant data path for Independent-Teacher
workspaces. Reads ``workspace_collaborators`` to decide whether a
collaborator IT may touch a *specific* host class.

The single-tenant invariant (§8) is intentionally relaxed only for the
named class — never the broader workspace.

Usage::

    if not await caller_can_access_class(db.session, current_user, class_id):
        raise HTTPException(404, "...")

For "is this collaborator allowed to *write*?" checks, use
``caller_collab_mode_for_class`` and gate on ``mode == "write"``.
"""
from __future__ import annotations

from typing import Literal, Optional

from src.core.guards.tenant_guard import independent_workspace_id, is_independent_teacher
from engines.sql_utils import gd_find_one


CollabMode = Literal["read", "write"]


async def caller_collab_row_for_class(
    session, current_user: dict, class_id: str,
) -> Optional[dict]:
    """Return the active accepted collab row for `current_user` against
    `class_id`, or None. Cheap; safe to call from per-request guards."""
    if not is_independent_teacher(current_user):
        return None
    wsid = independent_workspace_id(current_user)
    if not wsid:
        return None
    return await gd_find_one(session, "workspace_collaborators", {
        "collaborator_school_id": wsid,
        "class_id": class_id,
        "status": "accepted",
    })


async def caller_can_access_class(
    session, current_user: dict, class_id: str,
) -> bool:
    """True iff `current_user` is the host IT of `class_id` OR holds an
    active accepted collab row for it. Same-tenant (own workspace) wins
    via the cheap class lookup before we ever touch the collab table."""
    if not class_id:
        return False
    cls = await gd_find_one(session, "classes", {"id": class_id})
    if not cls:
        return False
    own_tenant = current_user.get("tenant_id") or current_user.get("school_id")
    if not own_tenant and is_independent_teacher(current_user):
        own_tenant = independent_workspace_id(current_user)
    if own_tenant and str(cls.get("school_id")) == str(own_tenant):
        return True
    row = await caller_collab_row_for_class(session, current_user, class_id)
    return row is not None


async def caller_collab_mode_for_class(
    session, current_user: dict, class_id: str,
) -> Optional[CollabMode]:
    """Return the granted scope mode (`'read'` or `'write'`) when the
    caller is a *collaborator* on `class_id`. Returns ``None`` when the
    caller is not a collaborator (host or unauthorised callers must be
    handled separately)."""
    row = await caller_collab_row_for_class(session, current_user, class_id)
    if not row:
        return None
    scope = row.get("scope") or {}
    mode = scope.get("mode") if isinstance(scope, dict) else None
    return "write" if mode == "write" else "read"
