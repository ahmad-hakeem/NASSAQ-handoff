"""IT Phase 2 (Task #251) — Workspace-wide command-palette search.

Single IT-only endpoint that powers the Cmd/Ctrl+K palette. Runs five
small parallel queries (students / classes / subjects / lesson plans /
calendar events) and returns up to ``limit`` ranked results per
category. Every read pins ``school_id`` (or ``tenant_id`` /
``workspace_school_id`` depending on the table) to ``itw_{user_id}``
so cross-workspace rows are never returned.

Spec §8 inv. 3 — by-id reads are not exposed here; this endpoint is
search-only and returns results scoped to the caller's workspace.
"""
from __future__ import annotations

import asyncio
import logging
import re
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from auth_scope import (
    INDEPENDENT_TEACHER_DENIED_AR,
    independent_workspace_id,
    is_independent_teacher,
    require_request_school_id,
)
from dependencies import db, get_current_user
from engines.sql_utils import gd_find
from middleware.rate_limiter import rate_store


logger = logging.getLogger("nassaq.it_search")

router = APIRouter(
    prefix="/independent-teacher",
    tags=["IT Search"],
)


_MIN_Q = 2
_DEFAULT_LIMIT = 8
_MAX_LIMIT = 20

# Per-user token bucket — same in-memory store the public parent-invitation
# accept route uses. Keyed on the authenticated user.id (NOT the workspace
# tenant) so a noisy keypress in one IT account can't fan out to siblings.
_SEARCH_RATE_MAX = 30
_SEARCH_RATE_WINDOW = 10
_MSG_RATE_LIMITED_AR = "تم تجاوز عدد محاولات البحث المسموح بها. يرجى الانتظار قليلاً ثم المحاولة مرة أخرى."


def _workspace_id(current_user: dict) -> str:
    return independent_workspace_id(current_user) or require_request_school_id(current_user)


async def _require_independent_teacher(
    current_user: dict = Depends(get_current_user),
) -> dict:
    if not is_independent_teacher(current_user):
        raise HTTPException(status_code=403, detail=INDEPENDENT_TEACHER_DENIED_AR)
    return current_user


def _normalize(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip().lower()


def _rank(field: str, q: str) -> int:
    """Lower is better. 0=exact, 1=prefix, 2=token-prefix, 3=substring, 9=miss."""
    f = _normalize(field)
    qn = _normalize(q)
    if not f or not qn:
        return 9
    if f == qn:
        return 0
    if f.startswith(qn):
        return 1
    for tok in re.split(r"\s+", f):
        if tok.startswith(qn):
            return 2
    if qn in f:
        return 3
    return 9


def _best_rank(row: Dict[str, Any], q: str, fields: List[str]) -> int:
    best = 9
    for f in fields:
        r = _rank(row.get(f), q)
        if r < best:
            best = r
    return best


async def _search_students(workspace_id: str, q: str, limit: int) -> List[Dict[str, Any]]:
    pattern = {"$regex": re.escape(q), "$options": "i"}
    rows = await gd_find(
        db.session, "students",
        {
            "school_id": workspace_id,
            "is_active": {"$ne": False},
            "$or": [
                {"full_name": pattern},
                {"national_id": pattern},
                {"student_number": pattern},
            ],
        },
        limit=limit * 3,
    )
    ranked = sorted(
        (rows or []),
        key=lambda r: (_best_rank(r, q, ["full_name", "national_id", "student_number"]),
                       _normalize(r.get("full_name"))),
    )[:limit]
    return [
        {
            "id": r.get("id"),
            "category": "students",
            "primary": r.get("full_name") or "",
            "secondary": r.get("grade") or r.get("national_id") or "",
            "href": f"/teacher/students?student_id={r.get('id')}",
        }
        for r in ranked
    ]


async def _search_classes(workspace_id: str, q: str, limit: int) -> List[Dict[str, Any]]:
    pattern = {"$regex": re.escape(q), "$options": "i"}
    rows = await gd_find(
        db.session, "classes",
        {
            "school_id": workspace_id,
            "is_active": {"$ne": False},
            "$or": [{"name": pattern}, {"name_en": pattern}],
        },
        limit=limit * 3,
    )
    ranked = sorted(
        (rows or []),
        key=lambda r: (_best_rank(r, q, ["name", "name_en"]),
                       _normalize(r.get("name"))),
    )[:limit]
    return [
        {
            "id": r.get("id"),
            "category": "classes",
            "primary": r.get("name") or r.get("name_en") or "",
            "secondary": r.get("grade_level") or "",
            "href": f"/teacher/class/{r.get('id')}",
        }
        for r in ranked
    ]


async def _search_subjects(workspace_id: str, q: str, limit: int) -> List[Dict[str, Any]]:
    pattern = {"$regex": re.escape(q), "$options": "i"}
    rows = await gd_find(
        db.session, "subjects",
        {
            "school_id": workspace_id,
            "is_active": {"$ne": False},
            "$or": [
                {"name": pattern},
                {"name_ar": pattern},
                {"name_en": pattern},
            ],
        },
        limit=limit * 3,
    )
    ranked = sorted(
        (rows or []),
        key=lambda r: (_best_rank(r, q, ["name", "name_ar", "name_en"]),
                       _normalize(r.get("name"))),
    )[:limit]
    return [
        {
            "id": r.get("id"),
            "category": "subjects",
            "primary": r.get("name_ar") or r.get("name") or r.get("name_en") or "",
            "secondary": r.get("code") or "",
            # Subjects do not have a dedicated detail page in the IT
            # surface — link to the classes list view (the closest place
            # the IT actually manages subject usage). No id param: would
            # be silently ignored downstream.
            "href": "/teacher/classes",
        }
        for r in ranked
    ]


async def _search_lesson_plans(
    workspace_id: str, user_id: str, q: str, limit: int,
) -> List[Dict[str, Any]]:
    pattern = {"$regex": re.escape(q), "$options": "i"}
    rows = await gd_find(
        db.session, "lesson_plans",
        {
            "workspace_school_id": workspace_id,
            "created_by": user_id,
            "is_saved": True,
            "$or": [
                {"topic": pattern},
                {"subject": pattern},
                {"grade_level": pattern},
            ],
        },
        limit=limit * 3,
    )
    ranked = sorted(
        (rows or []),
        key=lambda r: (_best_rank(r, q, ["topic", "subject", "grade_level"]),
                       _normalize(r.get("topic"))),
    )[:limit]
    return [
        {
            "id": r.get("id"),
            "category": "lesson_plans",
            "primary": r.get("topic") or "",
            "secondary": r.get("subject") or r.get("grade_level") or "",
            "href": f"/teacher/lesson-planner?plan_id={r.get('id')}",
        }
        for r in ranked
    ]


async def _search_calendar_events(
    workspace_id: str, user_id: str, q: str, limit: int,
) -> List[Dict[str, Any]]:
    pattern = {"$regex": re.escape(q), "$options": "i"}
    rows = await gd_find(
        db.session, "calendar_events",
        {
            "tenant_id": workspace_id,
            "created_by": user_id,
            "is_personal": True,
            "$or": [
                {"title_ar": pattern},
                {"title_en": pattern},
                {"details_ar": pattern},
                {"details_en": pattern},
            ],
        },
        limit=limit * 3,
    )
    ranked = sorted(
        (rows or []),
        key=lambda r: (_best_rank(r, q, ["title_ar", "title_en"]),
                       _normalize(r.get("title_ar") or r.get("title_en"))),
    )[:limit]
    return [
        {
            "id": r.get("id"),
            "category": "calendar_events",
            "primary": r.get("title_ar") or r.get("title_en") or "",
            "secondary": r.get("date") or "",
            "href": f"/teacher/calendar?event_id={r.get('id')}",
        }
        for r in ranked
    ]


@router.get("/search")
async def workspace_search(
    q: str = Query(default="", max_length=200),
    limit: int = Query(default=_DEFAULT_LIMIT, ge=1, le=_MAX_LIMIT),
    current_user: dict = Depends(_require_independent_teacher),
) -> Dict[str, Any]:
    """Workspace-wide command-palette search for the IT user.

    Empty (or sub-min-length) ``q`` returns an empty payload — never an
    error — so the FE can call this on every keystroke without special-
    casing the empty state.
    """
    q_clean = (q or "").strip()
    empty = {
        "q": q_clean,
        "students": [],
        "classes": [],
        "subjects": [],
        "lesson_plans": [],
        "calendar_events": [],
    }

    user_id = current_user.get("id")
    if not user_id:
        raise HTTPException(status_code=403, detail=INDEPENDENT_TEACHER_DENIED_AR)

    # Per-user rate limit — applied BEFORE the empty-q short-circuit so a
    # client spamming empty queries also gets throttled.
    limited, _, retry_after = await rate_store.is_rate_limited(
        f"it_search:{user_id}",
        _SEARCH_RATE_MAX,
        _SEARCH_RATE_WINDOW,
    )
    if limited:
        raise HTTPException(
            status_code=429,
            detail=_MSG_RATE_LIMITED_AR,
            headers={"Retry-After": str(retry_after)},
        )

    if len(q_clean) < _MIN_Q:
        return empty

    workspace_id = _workspace_id(current_user)

    try:
        students, classes, subjects, plans, events = await asyncio.gather(
            _search_students(workspace_id, q_clean, limit),
            _search_classes(workspace_id, q_clean, limit),
            _search_subjects(workspace_id, q_clean, limit),
            _search_lesson_plans(workspace_id, user_id, q_clean, limit),
            _search_calendar_events(workspace_id, user_id, q_clean, limit),
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("IT workspace search failed: %s", exc)
        return empty

    return {
        "q": q_clean,
        "students": students,
        "classes": classes,
        "subjects": subjects,
        "lesson_plans": plans,
        "calendar_events": events,
    }
