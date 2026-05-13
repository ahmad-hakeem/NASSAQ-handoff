"""IT Phase 2 §6.3 — Personal calendar event authoring (Task #208).

This is the SOLE backend writer that flips ``calendar_events.is_personal``
to ``True``. Every write pins ``tenant_id = itw_{user_id}`` and
``created_by = current_user.id`` server-side; the request body cannot
override either field. Cross-workspace ids return **404** per spec §8
inv. 3 — never 200, never 403 — so the API does not confirm the
existence of foreign-tenant rows.

The legacy school-wide router ``calendar_routes_mod`` is left
unchanged: principal events keep ``is_personal IS NULL`` (the migration
defaults the column to ``false`` for new rows but the read filter here
treats both NULL and false as "not personal", so legacy rows are simply
invisible to this surface).
"""
from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from auth_scope import (
    INDEPENDENT_TEACHER_DENIED_AR,
    independent_workspace_id,
    is_independent_teacher,
    require_request_school_id,
)
from dependencies import db, get_current_user
from engines.sql_utils import (
    gd_delete_one,
    gd_find,
    gd_find_one,
    gd_insert,
    gd_update_one,
)

logger = logging.getLogger("nassaq")

router = APIRouter(prefix="/independent-teacher/calendar", tags=["IT Personal Calendar"])


_ALLOWED_TYPES = {"trip", "parents", "report", "exam", "holiday", "meeting", "other"}
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

_MSG_NOT_FOUND = "الحدث غير موجود"
_MSG_TITLE_REQUIRED = "العنوان مطلوب (عربي أو إنجليزي)"
_MSG_BAD_DATE = "تاريخ غير صالح. استخدم الصيغة YYYY-MM-DD"


# -- Schemas -------------------------------------------------------------

class _PersonalEventBase(BaseModel):
    title_ar: Optional[str] = Field(default=None, max_length=200)
    title_en: Optional[str] = Field(default=None, max_length=200)
    type: Optional[str] = Field(default="meeting", max_length=32)
    date: Optional[str] = Field(default=None, max_length=10)
    details_ar: Optional[str] = Field(default=None, max_length=2000)
    details_en: Optional[str] = Field(default=None, max_length=2000)

    @field_validator("title_ar", "title_en", "type", "date", "details_ar", "details_en")
    @classmethod
    def _strip(cls, v):
        if v is None:
            return None
        s = str(v).strip()
        return s or None


class PersonalEventCreate(_PersonalEventBase):
    date: str = Field(min_length=10, max_length=10)


class PersonalEventUpdate(_PersonalEventBase):
    pass


# -- Gates ---------------------------------------------------------------

async def _require_independent_teacher(
    current_user: dict = Depends(get_current_user),
) -> dict:
    if not is_independent_teacher(current_user):
        raise HTTPException(status_code=403, detail=INDEPENDENT_TEACHER_DENIED_AR)
    return current_user


# -- Helpers -------------------------------------------------------------

def _normalize_type(raw: Optional[str]) -> str:
    if not raw:
        return "meeting"
    key = str(raw).strip().lower()
    if key in _ALLOWED_TYPES:
        return key
    return "other"


def _validate_date(value: Optional[str]) -> str:
    if not value or not isinstance(value, str) or not _DATE_RE.match(value):
        raise HTTPException(status_code=422, detail=_MSG_BAD_DATE)
    return value


def _serialize(row: Dict[str, Any]) -> Dict[str, Any]:
    if not row:
        return {}
    out: Dict[str, Any] = {
        "id": row.get("id"),
        "tenant_id": row.get("tenant_id"),
        "title_ar": row.get("title_ar") or "",
        "title_en": row.get("title_en") or "",
        "type": row.get("type") or "meeting",
        "date": row.get("date") or "",
        "details_ar": row.get("details_ar") or "",
        "details_en": row.get("details_en") or "",
        "is_personal": True,
        "created_by": row.get("created_by"),
    }
    for k in ("created_at", "updated_at"):
        v = row.get(k)
        if v is not None:
            out[k] = v if isinstance(v, str) else v.isoformat()
    return out


def _workspace_id(current_user: dict) -> str:
    """Pinned workspace tenant for IT writes/reads. Never derived from
    request body. Falls back to ``require_request_school_id`` when the
    JWT carries it explicitly (e.g. mid-bootstrap)."""
    return independent_workspace_id(current_user) or require_request_school_id(current_user)


def _is_visible_to_it(row: Dict[str, Any], user_id: str) -> bool:
    """Spec §6.3 read filter: an IT user sees rows in their workspace
    where ``is_personal`` is true OR they authored the row themselves
    (defence-in-depth — in practice the workspace tenant is sealed to
    one IT, so both halves coincide)."""
    if not row:
        return False
    return bool(row.get("is_personal")) or row.get("created_by") == user_id


async def _load_own_event(event_id: str, workspace_id: str, user_id: str) -> Dict[str, Any]:
    """Tenant pinned lookup with the §6.3 OR-semantics visibility check.
    Cross-workspace ids OR rows that are neither personal nor authored
    by the caller → 404 (§8 inv. 3) so the API does not confirm the
    existence of foreign rows."""
    row = await gd_find_one(db.session, "calendar_events", {
        "id": event_id,
        "tenant_id": workspace_id,
    })
    if not _is_visible_to_it(row, user_id):
        raise HTTPException(status_code=404, detail=_MSG_NOT_FOUND)
    return row


# -- Endpoints -----------------------------------------------------------

@router.get("/events")
async def list_personal_events(
    current_user: dict = Depends(_require_independent_teacher),
):
    """Return the caller's own personal events in their workspace,
    sorted by date asc. Workspace and author are both pinned; another
    IT in another workspace cannot see these rows even with the same
    permission."""
    workspace_id = _workspace_id(current_user)
    rows = await gd_find(
        db.session,
        "calendar_events",
        {"tenant_id": workspace_id},
        order_by="date",
        desc_order=False,
    )
    visible = [r for r in rows if _is_visible_to_it(r, current_user["id"])]
    return {"events": [_serialize(r) for r in visible]}


@router.post("/events", status_code=201)
async def create_personal_event(
    payload: PersonalEventCreate,
    current_user: dict = Depends(_require_independent_teacher),
):
    if not (payload.title_ar or payload.title_en):
        raise HTTPException(status_code=422, detail=_MSG_TITLE_REQUIRED)
    date = _validate_date(payload.date)
    workspace_id = _workspace_id(current_user)
    now = datetime.now(timezone.utc)

    title_ar = (payload.title_ar or payload.title_en or "").strip()
    doc = {
        "id": str(uuid.uuid4()),
        "tenant_id": workspace_id,
        "title_ar": title_ar,
        "title_en": (payload.title_en or "").strip() or None,
        "type": _normalize_type(payload.type),
        "date": date,
        "details_ar": (payload.details_ar or "").strip() or None,
        "details_en": (payload.details_en or "").strip() or None,
        "is_personal": True,
        "created_by": current_user["id"],
        "created_at": now,
        "updated_at": now,
    }
    await gd_insert(db.session, "calendar_events", doc)
    row = await gd_find_one(db.session, "calendar_events", {"id": doc["id"]})
    return {"event": _serialize(row or doc)}


@router.put("/events/{event_id}")
async def update_personal_event(
    event_id: str,
    payload: PersonalEventUpdate,
    current_user: dict = Depends(_require_independent_teacher),
):
    workspace_id = _workspace_id(current_user)
    await _load_own_event(event_id, workspace_id, current_user["id"])

    updates: Dict[str, Any] = {}
    if payload.title_ar is not None:
        updates["title_ar"] = payload.title_ar.strip()
    if payload.title_en is not None:
        updates["title_en"] = payload.title_en.strip() or None
    if payload.type is not None:
        updates["type"] = _normalize_type(payload.type)
    if payload.date is not None:
        updates["date"] = _validate_date(payload.date)
    if payload.details_ar is not None:
        updates["details_ar"] = payload.details_ar.strip() or None
    if payload.details_en is not None:
        updates["details_en"] = payload.details_en.strip() or None

    if updates:
        updates["updated_at"] = datetime.now(timezone.utc)
        await gd_update_one(
            db.session,
            "calendar_events",
            {"id": event_id, "tenant_id": workspace_id},
            updates,
        )

    row = await gd_find_one(db.session, "calendar_events", {"id": event_id})
    return {"event": _serialize(row or {})}


@router.delete("/events/{event_id}")
async def delete_personal_event(
    event_id: str,
    current_user: dict = Depends(_require_independent_teacher),
):
    workspace_id = _workspace_id(current_user)
    # Visibility re-checked under §6.3 OR-semantics before delete; still
    # tenant-pinned in the actual DELETE filter so cross-workspace rows
    # cannot be touched even if the visibility check were bypassed.
    await _load_own_event(event_id, workspace_id, current_user["id"])
    deleted = await gd_delete_one(db.session, "calendar_events", {
        "id": event_id,
        "tenant_id": workspace_id,
    })
    if not deleted:
        raise HTTPException(status_code=404, detail=_MSG_NOT_FOUND)
    return {"success": True, "deleted_id": event_id}
