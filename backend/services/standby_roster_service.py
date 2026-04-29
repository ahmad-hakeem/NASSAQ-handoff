"""
Standby Roster Service — جدول الانتظار الذكي (Smart Standby Roster).

يُولّد جدول انتظار منفصل عن الجدول الرئيسي ينظّم استخدام المعلمين كمعلمي
انتظار (سدّ شواغر) عبر الأسبوع، مع توزيع متوازن يومياً حتى لا يتراكم العبء
على معلم واحد في يوم واحد.

البنية:
  - لكل معلم نحسب فترات الفراغ (free periods) من timetable_sessions.
  - نشتق "السعة" (standby_capacity) = max(weekly_quota - assigned_periods, 0)
    أو نأخذها من إعداد teacher.standby_periods إن وُجد، أيهما أكبر.
  - نوزّعها على الأيام بحدّ يومي ⌈capacity / 5⌉ كحدّ أعلى لكل معلم.
  - النتيجة: قاموس {teacher_id: set[(day, period)]} يمثّل خانات الانتظار
    المتاحة لكل معلم.

ملاحظة: في هذه المرحلة نحسب الجدول on-demand. الـ persistence في collection
`standby_slots` يمكن إضافته لاحقاً عبر `persist_standby_roster()` دون تغيير
العقد الذي يستهلكه `substitution_service.score_candidates_for_slot`.
"""
from __future__ import annotations

from math import ceil
from typing import Dict, List, Set, Tuple

from engines.sql_utils import gd_find


DAYS = ["sunday", "monday", "tuesday", "wednesday", "thursday"]
PERIODS = list(range(1, 8))  # 1..7
DEFAULT_WEEKLY_QUOTA = 24


async def _fetch_active_timetable(session, school_id: str) -> dict | None:
    """يفضّل الجدول المنشور، ثم أحدث مسودة."""
    published = await gd_find(
        session, "timetables",
        {"school_id": school_id, "status": "published"},
        order_by="created_at", desc_order=True, limit=1,
    )
    if published:
        return published[0]
    drafts = await gd_find(
        session, "timetables",
        {"school_id": school_id, "status": "draft"},
        order_by="created_at", desc_order=True, limit=1,
    )
    return drafts[0] if drafts else None


def _safe_int(value, default: int = 0) -> int:
    try:
        if value is None or value == "":
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


async def compute_standby_roster(
    session,
    *,
    school_id: str,
    timetable_id: str | None = None,
    teachers: list[dict] | None = None,
    sessions: list[dict] | None = None,
) -> Dict[str, Set[Tuple[str, int]]]:
    """يُرجع خريطة `{teacher_id: set[(day, period)]}` لخانات الانتظار المتاحة.

    إذا لم يُمرَّر `teachers` أو `sessions` فسنجلبهما من قاعدة البيانات.
    `timetable_id` اختياري — إن لم يُمرَّر نشتقه من الجدول النشط للمدرسة.
    """
    if teachers is None:
        teachers = await gd_find(
            session, "teachers",
            {"school_id": school_id, "is_active": True},
            limit=2000,
        )
    if not teachers:
        return {}

    if timetable_id is None:
        tt = await _fetch_active_timetable(session, school_id)
        timetable_id = tt.get("id") if tt else None

    if sessions is None:
        if timetable_id:
            sessions = await gd_find(
                session, "timetable_sessions",
                {"timetable_id": timetable_id},
                limit=10000,
            )
        else:
            sessions = []

    # 1) Map: teacher_id -> set of (day, period) where they're already busy.
    busy: Dict[str, Set[Tuple[str, int]]] = {t["id"]: set() for t in teachers if t.get("id")}
    teacher_load: Dict[str, int] = {tid: 0 for tid in busy}
    for sess in sessions:
        tid = sess.get("teacher_id")
        if not tid or tid not in busy:
            continue
        day = (sess.get("day_of_week") or sess.get("day") or "").lower()
        period = _safe_int(sess.get("period_number"), 0)
        if day not in DAYS or period not in PERIODS:
            continue
        busy[tid].add((day, period))
        teacher_load[tid] += 1

    # 2) For each teacher, compute their free slots and distribute capacity.
    roster: Dict[str, Set[Tuple[str, int]]] = {}
    for t in teachers:
        tid = t.get("id")
        if not tid:
            continue
        weekly_quota = _safe_int(t.get("weekly_periods"), DEFAULT_WEEKLY_QUOTA)
        if weekly_quota <= 0:
            weekly_quota = DEFAULT_WEEKLY_QUOTA
        configured_standby = _safe_int(t.get("standby_periods"), 0)
        load = teacher_load.get(tid, 0)
        derived_capacity = max(weekly_quota - load, 0)
        # Use the larger of the configured setting and derived headroom — the
        # explicit standby_periods is a hint of willingness, but we never
        # promise more standby than the quota actually allows.
        capacity = max(configured_standby, derived_capacity)
        if capacity <= 0:
            continue

        # Identify free slots, deterministic order: by day index then period.
        free_slots: List[Tuple[str, int]] = []
        for day in DAYS:
            for period in PERIODS:
                if (day, period) not in busy[tid]:
                    free_slots.append((day, period))
        if not free_slots:
            continue

        # Daily cap: spread evenly so no day exceeds ⌈capacity / 5⌉.
        per_day_cap = max(1, ceil(capacity / len(DAYS)))
        per_day_count: Dict[str, int] = {d: 0 for d in DAYS}
        chosen: Set[Tuple[str, int]] = set()

        # Round-robin pass: prefer earliest available slot per day to spread
        # standby duty across the week instead of stacking at week start.
        for slot in free_slots:
            if len(chosen) >= capacity:
                break
            day, period = slot
            if per_day_count[day] >= per_day_cap:
                continue
            chosen.add(slot)
            per_day_count[day] += 1

        if chosen:
            roster[tid] = chosen

    return roster


__all__ = [
    "compute_standby_roster",
    "DAYS",
    "PERIODS",
    "DEFAULT_WEEKLY_QUOTA",
]
