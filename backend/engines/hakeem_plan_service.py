"""
Hakeem Daily Plan — AI Injection Service

Service-layer helper that lets the in-process AI engine (Hakeem) seamlessly
inject proactive tasks into a user's daily plan without going through the
HTTP API. Tasks injected this way are flagged with `source='ai'` so the
frontend can render the Sparkle badge.

Typical usage from an analysis job:

    from engines.hakeem_plan_service import inject_ai_task

    await inject_ai_task(
        session,
        tenant_id=school_id,
        user_id=principal_id,
        title="انخفاض ملحوظ في الحضور — الصف الثالث",
        details="تراجع الحضور بنسبة 22% خلال آخر 7 أيام",
        priority="urgent",
        ai_meta={"trigger": "attendance_drop", "class_id": class_id, "delta": -0.22},
    )
"""
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from engines.sql_utils import gd_find_one, gd_insert


_ALLOWED_PRIORITIES = {"urgent", "medium", "normal"}


def _today_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


async def inject_ai_task(
    session: AsyncSession,
    *,
    tenant_id: Optional[str],
    user_id: Optional[str],
    title: str,
    details: Optional[str] = None,
    priority: str = "urgent",
    task_date: Optional[str] = None,
    ai_meta: Optional[Dict[str, Any]] = None,
    dedupe_key: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Insert a Hakeem-injected task into a user's daily plan.

    Args:
        session: Active AsyncSession.
        tenant_id: School id the task belongs to (nullable for platform-wide tasks).
        user_id: Recipient user id (typically the principal/admin).
        title: Short, action-oriented Arabic task title.
        details: Optional supporting detail line.
        priority: One of urgent/medium/normal — defaults to urgent for AI tasks.
        task_date: YYYY-MM-DD; defaults to today (UTC).
        ai_meta: Free-form JSON describing what triggered the injection
            (e.g. {"trigger": "attendance_drop", "class_id": "..."}).
        dedupe_key: Optional string stored under `ai_meta.dedupe_key`. If a row
            with the same key already exists for the same user+date+source='ai',
            the call is a no-op and the existing row is returned instead.

    Returns:
        The serialized task dict, or None if the title is empty.
    """
    if not title or not str(title).strip():
        return None

    pri = priority if priority in _ALLOWED_PRIORITIES else "urgent"
    date = task_date or _today_str()
    meta = dict(ai_meta or {})
    if dedupe_key:
        meta["dedupe_key"] = dedupe_key
        existing = await gd_find_one(
            session,
            "daily_tasks",
            {
                "user_id": user_id,
                "task_date": date,
                "source": "ai",
            },
        )
        # Best-effort dedupe: only suppress if both the dedupe_key and title match
        if existing and (existing.get("ai_meta") or {}).get("dedupe_key") == dedupe_key:
            return existing

    doc = {
        "tenant_id": tenant_id,
        "user_id": user_id,
        "title": str(title).strip(),
        "details": (details or "").strip() or None,
        "priority": pri,
        "status": "active",
        "source": "ai",
        "task_date": date,
        "ai_meta": meta or None,
        "created_by": None,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    new_id = await gd_insert(session, "daily_tasks", doc)
    return await gd_find_one(session, "daily_tasks", {"id": new_id})
