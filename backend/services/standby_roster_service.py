"""
Standby Roster Service — جدول الانتظار الذكي (Smart Standby Roster).

يُولّد جدول انتظار منفصل عن الجدول الرئيسي ينظّم استخدام المعلمين كمعلمي
انتظار (سدّ شواغر) عبر الأسبوع، مع توزيع متوازن يومياً حتى لا يتراكم العبء
على معلم واحد في يوم واحد.

البنية:
  - لكل معلم نحسب فترات الفراغ (free periods) من timetable_sessions.
  - نستثني الأيام المحظورة على المعلم (`constraints.blocked_days`) فلا نولّد
    له خانات انتظار في يوم إجازته.
  - نشتق "السعة" (standby_capacity) = max(weekly_quota - assigned_periods, 0)
    ثم نُسقفها بـ `teacher.standby_periods` إن كان مضبوطاً (>0) — أي
    الإعداد الصريح هو حدّ أعلى لا أرضية.
  - نوزّعها على الأيام المتاحة بحدّ يومي ⌈capacity / working_days⌉ كحدّ أعلى
    لكل معلم.
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
PERIODS = list(range(1, 13))  # 1..12 — يغطّي مدارس الفترتين والمدارس متعدّدة الحصص
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
    apply_overrides: bool = True,
) -> Dict[str, Set[Tuple[str, int]]]:
    """يُرجع خريطة `{teacher_id: set[(day, period)]}` لخانات الانتظار المتاحة.

    إذا لم يُمرَّر `teachers` أو `sessions` فسنجلبهما من قاعدة البيانات.
    `timetable_id` اختياري — إن لم يُمرَّر نشتقه من الجدول النشط للمدرسة.

    عند `apply_overrides=True` (الافتراضي) نقرأ collection `standby_overrides`
    ونطبّق التعديلات اليدوية فوق التوزيع التلقائي:
      - action="add"    → نُجبر إدراج (teacher, day, period) حتى لو لم يختره
        المحرك التلقائي (مع استثناء الخانات المشغولة فعلاً بحصة).
      - action="remove" → نُزيل (teacher, day, period) حتى لو اختاره المحرك.
    التعديلات اليدوية تأخذ أولوية على التوزيع التلقائي ولا تُمحى عند إعادة
    التوليد لأنها مخزَّنة في collection مستقل.
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
        # Derived headroom from the main timetable: how many periods of the
        # weekly quota the teacher hasn't been assigned to teach.
        derived_capacity = max(weekly_quota - load, 0)
        # The explicit `standby_periods` setting (when present and > 0) is an
        # UPPER BOUND on how often this teacher can be tagged for standby
        # duty in a week — it expresses a school-policy cap, not a floor. We
        # therefore take the smaller of the two when the cap is configured.
        if configured_standby > 0:
            capacity = min(configured_standby, derived_capacity)
        else:
            capacity = derived_capacity
        if capacity <= 0:
            continue

        # Day-off / blocked-day exclusion: a teacher must never receive a
        # standby slot on a day they're not working. We pull both the
        # explicit `constraints.blocked_days` (Task #95) and the legacy
        # `working_days` whitelist if present.
        blocked = _resolve_blocked_days(t)
        eligible_days = [d for d in DAYS if d not in blocked]
        if not eligible_days:
            continue

        # Identify free slots on eligible days, deterministic order:
        # by day index then period.
        free_slots: List[Tuple[str, int]] = []
        for day in eligible_days:
            for period in PERIODS:
                if (day, period) not in busy[tid]:
                    free_slots.append((day, period))
        if not free_slots:
            continue

        # Daily cap: spread evenly so no day exceeds
        # ⌈capacity / eligible_working_days⌉.
        per_day_cap = max(1, ceil(capacity / len(eligible_days)))
        per_day_count: Dict[str, int] = {d: 0 for d in eligible_days}
        chosen: Set[Tuple[str, int]] = set()

        # Round-robin pass: prefer earliest available slot per day to spread
        # standby duty across the week instead of stacking at week start.
        for slot in free_slots:
            if len(chosen) >= capacity:
                break
            day, period = slot
            if per_day_count.get(day, 0) >= per_day_cap:
                continue
            chosen.add(slot)
            per_day_count[day] = per_day_count.get(day, 0) + 1

        if chosen:
            roster[tid] = chosen

    if apply_overrides:
        overrides = await fetch_standby_overrides(
            session, school_id=school_id, timetable_id=timetable_id,
        )
        # نمرّر `busy` كي ترفض دالة الدمج إضافة خانة فوق حصة مجدولة فعلاً
        # (حماية من override يصطدم بالجدول الأصلي).
        roster = apply_overrides_to_roster(roster, overrides, busy=busy)

    return roster


async def fetch_standby_overrides(
    session,
    *,
    school_id: str,
    timetable_id: str | None = None,
) -> List[dict]:
    """يجلب سجلات `standby_overrides` للمدرسة، مع تصفية اختيارية بحسب
    `timetable_id` (نعتبر الأوفرايد بلا `timetable_id` ساري المفعول لكل
    الجداول حتى يبقى نافعاً بعد إعادة التوليد)."""
    rows = await gd_find(
        session, "standby_overrides",
        {"school_id": school_id},
        limit=10000,
    )
    if timetable_id is None:
        return rows
    filtered: List[dict] = []
    for r in rows:
        ttid = r.get("timetable_id")
        if not ttid or ttid == timetable_id:
            filtered.append(r)
    return filtered


def apply_overrides_to_roster(
    auto_roster: Dict[str, Set[Tuple[str, int]]],
    overrides: List[dict],
    busy: Dict[str, Set[Tuple[str, int]]] | None = None,
) -> Dict[str, Set[Tuple[str, int]]]:
    """يطبّق قائمة `overrides` فوق الـ auto roster ويُرجع النسخة النهائية.

    الإضافة تُتجاهل بصمت إذا كانت الخانة مشغولة فعلاً بحصة في الجدول الأصلي
    (المعلم لا يمكن أن يكون في انتظار وفي حصة في الوقت نفسه).
    """
    final: Dict[str, Set[Tuple[str, int]]] = {
        tid: set(slots) for tid, slots in auto_roster.items()
    }
    busy = busy or {}
    for ov in overrides or []:
        tid = ov.get("teacher_id")
        day = (ov.get("day") or "").lower()
        period = _safe_int(ov.get("period"), 0)
        action = (ov.get("action") or "").lower()
        if not tid or day not in DAYS or period not in PERIODS:
            continue
        if action == "add":
            if (day, period) in busy.get(tid, set()):
                # لا يمكن إضافة خانة فوق حصة فعلية — نتجاهل بصمت.
                continue
            final.setdefault(tid, set()).add((day, period))
        elif action == "remove":
            slots = final.get(tid)
            if slots is not None:
                slots.discard((day, period))
        # أي action آخر — نتجاهل (forward compatibility).
    return final


def _resolve_blocked_days(teacher: dict) -> Set[str]:
    """Returns the set of weekdays on which `teacher` must not be assigned
    standby duty.

    Sources merged:
      - `teacher.constraints.blocked_days` (Task #95 — explicit hard
        constraint, e.g. ["thursday"]).
      - `teacher.working_days` (legacy whitelist) — anything in DAYS that is
        absent from the whitelist is treated as a day-off.
      - Localized values like "الخميس" are normalized via _AR_DAY_KEYS.
    """
    blocked: Set[str] = set()

    constraints = teacher.get("constraints") or {}
    if isinstance(constraints, dict):
        raw = constraints.get("blocked_days") or []
        if isinstance(raw, list):
            for item in raw:
                key = _normalize_day_key(item)
                if key:
                    blocked.add(key)
        elif isinstance(raw, dict):
            # Map shape: {"thursday": True, ...}
            for k, v in raw.items():
                key = _normalize_day_key(k)
                if key and v:
                    blocked.add(key)

    # `working_days` is a whitelist. If the field is *present* on the teacher
    # row (even when empty / all-false / unrecognized), treat unlisted days
    # as blocked — the school explicitly opted into a per-teacher schedule.
    # When the field is missing entirely we fall back to "all DAYS allowed"
    # (the default before per-teacher day-offs existed).
    if "working_days" in teacher and teacher.get("working_days") is not None:
        working = teacher.get("working_days")
        allowed: Set[str] = set()
        if isinstance(working, list):
            allowed = {_normalize_day_key(d) for d in working if _normalize_day_key(d)}
        elif isinstance(working, dict):
            allowed = {
                _normalize_day_key(k)
                for k, v in working.items()
                if v and _normalize_day_key(k)
            }
        else:
            # Unknown payload shape — log and treat as "no whitelist" so we
            # don't accidentally block every day on a data glitch.
            import logging
            logging.getLogger("nassaq.standby").warning(
                "Ignoring malformed teacher.working_days payload (type=%s) "
                "for teacher_id=%s",
                type(working).__name__,
                teacher.get("id"),
            )
            allowed = None  # type: ignore[assignment]

        if allowed is not None:
            # An explicit whitelist (even empty) blocks any DAYS not in it.
            for d in DAYS:
                if d not in allowed:
                    blocked.add(d)

    return blocked


_AR_DAY_KEYS = {
    "الأحد": "sunday", "الاحد": "sunday",
    "الإثنين": "monday", "الاثنين": "monday",
    "الثلاثاء": "tuesday",
    "الأربعاء": "wednesday", "الاربعاء": "wednesday",
    "الخميس": "thursday",
    "الجمعة": "friday",
    "السبت": "saturday",
}


def _normalize_day_key(value) -> str | None:
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    low = s.lower()
    if low in DAYS or low in ("friday", "saturday"):
        return low
    return _AR_DAY_KEYS.get(s)


__all__ = [
    "compute_standby_roster",
    "fetch_standby_overrides",
    "apply_overrides_to_roster",
    "DAYS",
    "PERIODS",
    "DEFAULT_WEEKLY_QUOTA",
]
