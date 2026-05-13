"""IT first-login onboarding tour state (Task #250).

Three IT-only endpoints driving the welcome card + replay link on
``AccountSettingsPage`` and the in-product coach-mark tour:

  * ``GET  /independent-teacher/onboarding/state``    — idempotent read
  * ``POST /independent-teacher/onboarding/complete`` — idempotent stamp
  * ``POST /independent-teacher/onboarding/reset``    — clears the stamp
                                                       (replay support)

Everything is gated on ``UserRole.INDEPENDENT_TEACHER``; non-IT callers
get a 403 with the canonical Arabic copy. The endpoints are deliberately
free of MFA step-up — they only flip a single ``users.it_onboarding_completed_at``
timestamp on the caller's own row, never write any other tenant data.

``should_show`` is the authoritative trigger flag: ``True`` only when
the column is NULL **and** the caller has already materialised their
workspace (otherwise the wizard / bootstrap chrome takes priority).
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from auth_scope import (
    INDEPENDENT_TEACHER_DENIED_AR,
    independent_workspace_id,
    is_independent_teacher,
)
from dependencies import db, get_current_user
from engines.sql_utils import gd_find_one, gd_update_one

logger = logging.getLogger("nassaq.it_onboarding")

router = APIRouter(
    prefix="/independent-teacher/onboarding",
    tags=["IT Onboarding"],
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _require_it(current_user: dict) -> None:
    if not is_independent_teacher(current_user):
        raise HTTPException(status_code=403, detail=INDEPENDENT_TEACHER_DENIED_AR)


def _iso(value) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


async def _load_user_row(user_id: str) -> dict:
    row = await gd_find_one(db.session, "users", {"id": user_id})
    if not row:
        # Bearer was valid but the row vanished between auth and here —
        # treat as a hard 401-equivalent without leaking detail.
        raise HTTPException(status_code=403, detail=INDEPENDENT_TEACHER_DENIED_AR)
    return row


def _build_state(user_row: dict) -> dict:
    completed_at = user_row.get("it_onboarding_completed_at")
    workspace_id = independent_workspace_id(user_row)
    has_workspace = bool(user_row.get("tenant_id")) and user_row.get("tenant_id") == workspace_id
    return {
        "completed_at": _iso(completed_at),
        # Only nudge the user once their workspace exists — pre-bootstrap
        # the wizard owns the screen, so the tour would be a confusing
        # second overlay. Once bootstrap rotates the bearer, tenant_id
        # equals the synthetic workspace id and the tour kicks in.
        "should_show": completed_at is None and has_workspace,
        "has_workspace": has_workspace,
    }


@router.get("/state")
async def get_onboarding_state(current_user: dict = Depends(get_current_user)):
    _require_it(current_user)
    user_row = await _load_user_row(current_user["id"])
    return _build_state(user_row)


@router.post("/complete")
async def complete_onboarding(current_user: dict = Depends(get_current_user)):
    _require_it(current_user)
    user_row = await _load_user_row(current_user["id"])
    if user_row.get("it_onboarding_completed_at") is None:
        now = _utcnow()
        await gd_update_one(
            db.session,
            "users",
            {"id": current_user["id"]},
            {"it_onboarding_completed_at": now.isoformat(), "updated_at": now.isoformat()},
        )
        user_row["it_onboarding_completed_at"] = now
    return _build_state(user_row)


@router.post("/reset")
async def reset_onboarding(current_user: dict = Depends(get_current_user)):
    _require_it(current_user)
    user_row = await _load_user_row(current_user["id"])
    if user_row.get("it_onboarding_completed_at") is not None:
        now = _utcnow()
        await gd_update_one(
            db.session,
            "users",
            {"id": current_user["id"]},
            {"it_onboarding_completed_at": None, "updated_at": now.isoformat()},
        )
        user_row["it_onboarding_completed_at"] = None
    return _build_state(user_row)
