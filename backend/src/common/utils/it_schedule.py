"""Independent-Teacher synthetic-workspace schedule read helpers.

The IT workspace model (spec §5.4) stores schedule rows directly in
``schedule_sessions`` keyed by ``schedule_id = itw_schedule_{school_id}``
with ``status = "scheduled"``. It never materialises a ``time_slots``
collection and never creates a published ``timetables`` / ``schedules``
parent. The generic teacher-schedule read path, on the other hand,
expects a published parent and a ``time_slots`` collection.

These helpers bridge that gap on the READ side only — they do not touch
the IT save flow / editor grid. They normalise the short weekday codes
the editor stores (``sun``/``mon``/…) to the full names the generic
teacher-schedule frontend uses (``sunday``/``monday``/…), and derive a
deterministic clock from the workspace period config so the read page can
show slot times and detect the current/next session.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

# Short weekday codes used by the IT editor → full names expected by the
# generic teacher-schedule frontend (its DAYS keys) and the dashboard.
_IT_DAY_FULL = {
    "sun": "sunday",
    "mon": "monday",
    "tue": "tuesday",
    "wed": "wednesday",
    "thu": "thursday",
    "fri": "friday",
    "sat": "saturday",
}

_IT_DEFAULT_DAY_START = "07:00"
_IT_PASSING_MINUTES = 5


def normalize_it_day(value: Any) -> str:
    """Map a stored IT weekday code to the full name the read UI expects.

    Already-full names (and unknown values) pass through unchanged so the
    helper is safe to call on either representation.
    """
    s = str(value or "").strip().lower()
    return _IT_DAY_FULL.get(s, s)


def _coerce_settings(settings: Optional[Dict[str, Any]]) -> Tuple[int, int]:
    settings = settings or {}
    cs = settings.get("custom_settings") or {}
    periods = int(
        cs.get("periods_per_day")
        or settings.get("periods_per_day")
        or 7
    )
    periods = max(1, min(periods, 12))
    period_minutes = int(
        cs.get("period_duration_minutes")
        or settings.get("period_duration")
        or settings.get("period_duration_minutes")
        or 45
    )
    period_minutes = max(20, min(period_minutes, 90))
    return periods, period_minutes


def _resolve_day_start(settings: Optional[Dict[str, Any]]) -> str:
    s = settings or {}
    cs = s.get("custom_settings") or {}
    candidate = cs.get("school_day_start") or s.get("start_time")
    if isinstance(candidate, str) and ":" in candidate:
        try:
            hh, mm = candidate.split(":")[:2]
            if 0 <= int(hh) <= 23 and 0 <= int(mm) <= 59:
                return f"{int(hh):02d}:{int(mm):02d}"
        except (ValueError, TypeError):
            pass
    return _IT_DEFAULT_DAY_START


def compute_it_slot_times(
    settings: Optional[Dict[str, Any]],
) -> Dict[int, Tuple[str, str]]:
    """Map ``slot_number`` → ``(start_time, end_time)`` for an IT workspace.

    The IT model has no per-slot times, so we derive a deterministic clock
    from the workspace period config (``periods_per_day`` +
    ``period_duration``) using the same period/passing-time cadence as the
    standard time-slot generator. This keeps the read page's slot times and
    its current/next-session detection consistent with the synthesized
    ``time_slots`` returned by the time-slots endpoint.
    """
    periods, period_minutes = _coerce_settings(settings)
    day_start = _resolve_day_start(settings)
    h, m = map(int, day_start.split(":"))
    current = h * 60 + m
    out: Dict[int, Tuple[str, str]] = {}
    for slot in range(1, periods + 1):
        start = current
        end = current + period_minutes
        sh, sm = divmod(start, 60)
        eh, em = divmod(end, 60)
        out[slot] = (f"{sh:02d}:{sm:02d}", f"{eh:02d}:{em:02d}")
        current = end + _IT_PASSING_MINUTES
    return out


def synthesize_it_time_slots(
    school_id: str, settings: Optional[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Build virtual ``time_slots`` rows for an IT workspace.

    IT workspaces never persist a ``time_slots`` collection, but the generic
    teacher weekly-grid renders its rows by iterating ``time_slots``. We
    derive the rows from the workspace period config and return them
    (un-persisted) so the grid renders. Ids are stable across loads so the
    frontend list keys don't churn.
    """
    periods, period_minutes = _coerce_settings(settings)
    times = compute_it_slot_times(settings)
    slots: List[Dict[str, Any]] = []
    for slot in range(1, periods + 1):
        start, end = times.get(slot, (None, None))
        slots.append({
            "id": f"itw_slot_{school_id}_{slot}",
            "school_id": school_id,
            "name": f"الحصة {slot}",
            "name_en": f"Period {slot}",
            "start_time": start,
            "end_time": end,
            "slot_number": slot,
            "period_number": slot,
            "duration_minutes": period_minutes,
            "type": "class",
            "is_break": False,
            "is_prayer": False,
            "is_active": True,
        })
    return slots
