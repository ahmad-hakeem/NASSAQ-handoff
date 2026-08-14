"""Task #249 §6.X — IT Notifications Inbox + per-category preferences.

Workspace-pinned read/ack/preferences surface for the Independent-Teacher
inbox. Every read/write pins ``user_id == current_user.id`` AND
``tenant_id == itw_{user_id}``. Cross-workspace by-id reads return 404
per spec §8 inv. 3.

Routes
======
``GET    /independent-teacher/notifications``       (cursor or offset paged)
``GET    /independent-teacher/notifications/unread-count``
``POST   /independent-teacher/notifications/{id}/read``
``POST   /independent-teacher/notifications/read-all``
``POST   /independent-teacher/notifications/mark-all-read``  (alias)
``GET    /independent-teacher/notifications/preferences``
``PUT    /independent-teacher/notifications/preferences``

Preferences are persisted in the ``notifications_preferences`` table
(one row per ``(user_id, category)``) — NOT in ``users`` JSON. The
``in_app`` channel is stored but the GET/PUT surface forces it to True
on read so the inbox can never be silenced (it is the source of truth).

Channel suppression
===================
``should_send_channel(user, category, channel)`` is the single helper
used by every email sender to decide whether the email channel may
fire. ``in_app`` always returns True.
"""
from __future__ import annotations

import base64
import logging
import uuid as _uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from src.core.guards.tenant_guard import independent_workspace_id, is_independent_teacher
from dependencies import db, get_current_user
from engines.sql_utils import (
    gd_count,
    gd_find,
    gd_find_one,
    gd_insert,
    gd_update_many,
    gd_update_one,
)


logger = logging.getLogger(__name__)


router = APIRouter(tags=["IT Notifications"])


IT_CATEGORIES: List[str] = [
    "collab_invite",
    "parent_accept",
    "workspace_lifecycle",
    "quota",
    "lesson_plan",
    "general",
]

_CHANNELS: List[str] = ["in_app", "email"]

_DEFAULT_CATEGORY_CHANNELS: Dict[str, Dict[str, bool]] = {
    cat: {"in_app": True, "email": True} for cat in IT_CATEGORIES
}

_MSG_NOT_FOUND_AR = "الإشعار غير موجود."
_MSG_NOT_IT_AR = "هذه الميزة متاحة لحساب المعلم المستقل فقط."
_MSG_INVALID_AR = "بيانات غير صالحة."


# -- Helpers --------------------------------------------------------------

def _require_independent_teacher(
    current_user: dict = Depends(get_current_user),
) -> dict:
    if not is_independent_teacher(current_user):
        raise HTTPException(status_code=403, detail=_MSG_NOT_IT_AR)
    return current_user


def _normalise_category(value: Optional[str]) -> str:
    if not value:
        return "general"
    v = str(value).strip().lower()
    return v if v in IT_CATEGORIES else "general"


async def _load_prefs_for_user(user_id: str) -> Dict[str, Dict[str, bool]]:
    """Return the full category→channels matrix for ``user_id``.

    Reads the ``notifications_preferences`` table; missing rows fall back
    to defaults so callers can always index without KeyError.
    """
    out: Dict[str, Dict[str, bool]] = {
        cat: dict(_DEFAULT_CATEGORY_CHANNELS[cat]) for cat in IT_CATEGORIES
    }
    try:
        rows = await gd_find(
            db.session, "notifications_preferences",
            {"user_id": user_id},
        )
    except Exception as exc:  # noqa: BLE001
        logger.debug("prefs lookup failed: %s", exc)
        return out
    for r in rows or []:
        cat = _normalise_category(r.get("category"))
        # ``in_app`` is intentionally NOT honoured here — the inbox is
        # the source of truth and silent suppression would lose audit
        # trail. We keep the row's stored value out of the response so
        # the FE always sees True.
        out[cat] = {
            "in_app": True,
            "email": bool(r.get("email", True)),
        }
    return out


async def should_send_channel(
    user_or_id: Any,
    category: str,
    channel: str,
) -> bool:
    """Return ``True`` when the given channel may fire for ``category``."""
    ch = (channel or "").lower()
    if ch not in _CHANNELS:
        return True
    if ch == "in_app":
        return True
    cat = _normalise_category(category)

    if isinstance(user_or_id, dict):
        uid = user_or_id.get("id")
    elif isinstance(user_or_id, str):
        uid = user_or_id
    else:
        return True
    if not uid:
        return True

    try:
        prefs = await _load_prefs_for_user(uid)
    except Exception as exc:  # noqa: BLE001
        logger.debug("should_send_channel prefs read failed: %s", exc)
        return True
    return bool(prefs.get(cat, _DEFAULT_CATEGORY_CHANNELS[cat]).get(ch, True))


# -- Cursor encode/decode -------------------------------------------------

def _encode_cursor(created_at: Any, row_id: str) -> str:
    """Cursor = base64('<iso_created_at>|<row_id>'). Opaque to clients."""
    if isinstance(created_at, datetime):
        ts = created_at.isoformat()
    else:
        ts = str(created_at or "")
    raw = f"{ts}|{row_id}".encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _decode_cursor(cursor: str) -> Optional[Tuple[str, str]]:
    if not cursor:
        return None
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        raw = base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8")
        ts, _, rid = raw.partition("|")
        if not ts or not rid:
            return None
        return ts, rid
    except Exception:  # noqa: BLE001
        return None


# -- Pydantic shapes ------------------------------------------------------

class CategoryChannels(BaseModel):
    in_app: Optional[bool] = None
    email: Optional[bool] = None


class PreferencesUpdate(BaseModel):
    categories: Dict[str, CategoryChannels] = Field(default_factory=dict)


# -- Endpoint: GET list ---------------------------------------------------

@router.get("/independent-teacher/notifications")
async def list_notifications(
    category: Optional[str] = Query(default=None),
    unread_only: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    cursor: Optional[str] = Query(default=None),
    current_user: dict = Depends(_require_independent_teacher),
):
    workspace_id = independent_workspace_id(current_user)
    query: Dict[str, Any] = {
        "user_id": current_user["id"],
        "tenant_id": workspace_id,
    }
    if category:
        query["category"] = _normalise_category(category)
    if unread_only:
        query["is_read"] = False

    # Cursor pagination: created_at < cursor_ts (newest-first).
    decoded = _decode_cursor(cursor) if cursor else None
    if decoded:
        ts, _ = decoded
        query["created_at"] = {"$lt": ts}

    rows = await gd_find(
        db.session, "notifications", query,
        order_by="created_at", desc_order=True,
        limit=limit + 1, offset=offset if not decoded else 0,
    )
    total = await gd_count(db.session, "notifications", {
        "user_id": current_user["id"],
        "tenant_id": workspace_id,
        **({"category": query["category"]} if "category" in query and isinstance(query["category"], str) else {}),
        **({"is_read": False} if unread_only else {}),
    })

    has_more = len(rows) > limit
    page_rows = rows[:limit]
    next_cursor: Optional[str] = None
    if has_more and page_rows:
        last = page_rows[-1]
        next_cursor = _encode_cursor(last.get("created_at"), last.get("id") or "")

    def _serialise(r: Dict[str, Any]) -> Dict[str, Any]:
        created = r.get("created_at")
        if isinstance(created, datetime):
            created = created.isoformat()
        return {
            "id": r.get("id"),
            "category": _normalise_category(r.get("category")),
            "title": r.get("title"),
            "title_en": r.get("title_en"),
            "message": r.get("message"),
            "message_en": r.get("message_en"),
            "type": r.get("type"),
            "priority": r.get("priority"),
            "cta_url": r.get("cta_url"),
            "is_read": bool(r.get("is_read")),
            "read_at": r.get("read_at"),
            "created_at": created,
            "data": r.get("data") or {},
        }

    return {
        "items": [_serialise(r) for r in page_rows],
        "total": total,
        "next_cursor": next_cursor,
        "has_more": has_more,
    }


# -- Endpoint: GET unread-count ------------------------------------------

@router.get("/independent-teacher/notifications/unread-count")
async def unread_count(
    current_user: dict = Depends(_require_independent_teacher),
):
    workspace_id = independent_workspace_id(current_user)
    count = await gd_count(db.session, "notifications", {
        "user_id": current_user["id"],
        "tenant_id": workspace_id,
        "is_read": False,
    })
    return {"unread_count": count}


# -- Endpoint: POST mark single read --------------------------------------

@router.post("/independent-teacher/notifications/{notification_id}/read")
async def mark_read(
    notification_id: str,
    current_user: dict = Depends(_require_independent_teacher),
):
    workspace_id = independent_workspace_id(current_user)
    # Cross-workspace by-id MUST 404 per spec §8 inv. 3.
    row = await gd_find_one(db.session, "notifications", {
        "id": notification_id,
        "user_id": current_user["id"],
        "tenant_id": workspace_id,
    })
    if not row:
        raise HTTPException(status_code=404, detail=_MSG_NOT_FOUND_AR)

    if row.get("is_read"):
        return {"ok": True, "already_read": True}

    now_iso = datetime.now(timezone.utc).isoformat()
    await gd_update_one(
        db.session, "notifications",
        {"id": notification_id},
        {"is_read": True, "read_at": now_iso},
    )
    return {"ok": True, "already_read": False}


# -- Endpoint: POST read-all (canonical) + mark-all-read alias ------------

async def _read_all_impl(current_user: dict) -> Dict[str, Any]:
    workspace_id = independent_workspace_id(current_user)
    now_iso = datetime.now(timezone.utc).isoformat()
    updated = await gd_update_many(
        db.session, "notifications",
        {
            "user_id": current_user["id"],
            "tenant_id": workspace_id,
            "is_read": False,
        },
        {"is_read": True, "read_at": now_iso},
    )
    return {"ok": True, "updated": int(updated or 0)}


@router.post("/independent-teacher/notifications/read-all")
async def read_all(
    current_user: dict = Depends(_require_independent_teacher),
):
    return await _read_all_impl(current_user)


@router.post("/independent-teacher/notifications/mark-all-read")
async def mark_all_read_alias(
    current_user: dict = Depends(_require_independent_teacher),
):
    # Back-compat alias — same handler.
    return await _read_all_impl(current_user)


# -- Endpoint: GET preferences --------------------------------------------

@router.get("/independent-teacher/notifications/preferences")
async def get_preferences(
    current_user: dict = Depends(_require_independent_teacher),
):
    return {
        "categories": await _load_prefs_for_user(current_user["id"]),
        "available_categories": IT_CATEGORIES,
        "available_channels": _CHANNELS,
    }


# -- Endpoint: PUT preferences --------------------------------------------

@router.put("/independent-teacher/notifications/preferences")
async def update_preferences(
    payload: PreferencesUpdate = Body(...),
    current_user: dict = Depends(_require_independent_teacher),
):
    incoming = payload.categories or {}
    if not isinstance(incoming, dict):
        raise HTTPException(status_code=422, detail=_MSG_INVALID_AR)

    uid = current_user["id"]
    now_iso = datetime.now(timezone.utc).isoformat()

    for cat_raw, channels in incoming.items():
        cat = _normalise_category(cat_raw)
        if not channels:
            continue
        ch_dict = channels.model_dump() if hasattr(channels, "model_dump") else dict(channels)
        # Resolve target email value (in_app is forced True on read, so
        # we never persist a False in_app — write True regardless).
        email_val: Optional[bool] = None
        if "email" in ch_dict and ch_dict["email"] is not None:
            email_val = bool(ch_dict["email"])

        existing = await gd_find_one(
            db.session, "notifications_preferences",
            {"user_id": uid, "category": cat},
        )
        if existing:
            updates: Dict[str, Any] = {"updated_at": now_iso, "in_app": True}
            if email_val is not None:
                updates["email"] = email_val
            await gd_update_one(
                db.session, "notifications_preferences",
                {"id": existing["id"]},
                updates,
            )
        else:
            await gd_insert(db.session, "notifications_preferences", {
                "id": str(_uuid.uuid4()),
                "user_id": uid,
                "category": cat,
                "in_app": True,
                "email": True if email_val is None else email_val,
                "created_at": now_iso,
                "updated_at": now_iso,
            })

    prefs = await _load_prefs_for_user(uid)
    return {
        "ok": True,
        "categories": prefs,
        "available_categories": IT_CATEGORIES,
        "available_channels": _CHANNELS,
    }


__all__ = ["router", "should_send_channel", "IT_CATEGORIES"]
