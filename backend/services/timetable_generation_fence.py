"""Optimistic fencing for timetable generation versus structural settings."""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import text

from engines.sql_utils import gd_find_one, gd_update_many


ACTIVE_RUN_STATUSES = [
    "pending",
    "validating",
    "loading",
    "generating",
    "optimizing",
]


class GenerationSettingsChanged(RuntimeError):
    """The settings snapshot used by a generation is no longer current."""

    code = "GENERATION_SETTINGS_CHANGED"

    def __init__(self) -> None:
        super().__init__(
            "تم تغيير إعدادات الجدول أثناء التوليد. أُلغيت النتيجة القديمة؛ "
            "يرجى بدء التوليد مجدداً."
        )


async def get_timetable_settings_version(session, school_id: str) -> int:
    """Return the monotonic version embedded in school_settings.custom_settings."""
    row = await gd_find_one(session, "school_settings", {"school_id": school_id})
    custom = (row or {}).get("custom_settings") or {}
    version = custom.get("settings_version", 0)
    return version if isinstance(version, int) and not isinstance(version, bool) else 0


async def assert_generation_settings_current(
    session,
    school_id: str,
    expected_version: int,
    *,
    acquire_lifecycle_lock: bool = False,
) -> None:
    """Reject stale output; optionally serialize the check with its final writes."""
    if acquire_lifecycle_lock:
        await session.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:k))"),
            {"k": f"sched_draft_ensure:{school_id}"},
        )
    current = await get_timetable_settings_version(session, school_id)
    if current != expected_version:
        raise GenerationSettingsChanged()


async def cancel_active_generation_runs(session, school_id: str) -> int:
    """Cancel queued/running generations after a structural settings change.

    Contract: caller already holds ``sched_draft_ensure:{school_id}`` and calls
    this in the same transaction that increments ``settings_version``.
    """
    now = datetime.now(timezone.utc).isoformat()
    return await gd_update_many(
        session,
        "timetable_runs",
        {"school_id": school_id, "status": {"$in": ACTIVE_RUN_STATUSES}},
        {
            "status": "failed",
            "finished_at": now,
            "completion_percentage": 100,
            "error_code": GenerationSettingsChanged.code,
            "notes": str(GenerationSettingsChanged()),
        },
    )