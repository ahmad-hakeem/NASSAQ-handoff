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
from typing import Any, Dict, List, Optional, Set, Tuple

from engines.sql_utils import gd_find, gd_find_one


DAYS = ["sunday", "monday", "tuesday", "wednesday", "thursday"]
PERIODS = list(range(1, 13))  # 1..12 — يغطّي مدارس الفترتين والمدارس متعدّدة الحصص
DEFAULT_WEEKLY_QUOTA = 24
DEFAULT_MAX_STANDBY_PER_WEEK = 5
MAX_STANDBY_CAP_HARD_LIMIT = 20  # absolute upper bound regardless of setting

# Per-(day, period) cap on auto-assigned standby teachers. Prevents the
# generator from front-loading every teacher into the earliest periods of
# the day. Mirrored by `school_settings.custom_settings.max_standby_per_period`.
DEFAULT_MAX_STANDBY_PER_PERIOD = 5
MAX_STANDBY_PER_PERIOD_HARD_LIMIT = 50


async def _fetch_school_standby_cap(session, school_id: str) -> int:
    """Returns the school's `max_standby_per_teacher_per_week` setting.

    Reads from `school_settings.custom_settings.max_standby_per_teacher_per_week`.
    Falls back to DEFAULT_MAX_STANDBY_PER_WEEK (5) when missing or invalid.
    Clamped to the range [1, MAX_STANDBY_CAP_HARD_LIMIT].
    """
    row = await gd_find_one(session, "school_settings", {"school_id": school_id})
    if not row:
        return DEFAULT_MAX_STANDBY_PER_WEEK
    cs = row.get("custom_settings") or {}
    raw = cs.get("max_standby_per_teacher_per_week")
    val = _safe_int(raw, DEFAULT_MAX_STANDBY_PER_WEEK)
    if val < 1:
        return DEFAULT_MAX_STANDBY_PER_WEEK
    return min(val, MAX_STANDBY_CAP_HARD_LIMIT)


async def _fetch_school_per_period_cap(session, school_id: str) -> int:
    """Returns the school's `max_standby_per_period` setting (hard ceiling
    on auto-assigned standby teachers per (day, period)).

    Reads from `school_settings.custom_settings.max_standby_per_period`.
    Falls back to DEFAULT_MAX_STANDBY_PER_PERIOD (5) when missing/invalid.
    Clamped to [1, MAX_STANDBY_PER_PERIOD_HARD_LIMIT].
    """
    row = await gd_find_one(session, "school_settings", {"school_id": school_id})
    if not row:
        return DEFAULT_MAX_STANDBY_PER_PERIOD
    cs = row.get("custom_settings") or {}
    raw = cs.get("max_standby_per_period")
    val = _safe_int(raw, DEFAULT_MAX_STANDBY_PER_PERIOD)
    if val < 1:
        return DEFAULT_MAX_STANDBY_PER_PERIOD
    return min(val, MAX_STANDBY_PER_PERIOD_HARD_LIMIT)


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


def _detect_timetable_periods(sessions: Optional[List[dict]]) -> List[int]:
    """Period universe = the distinct period numbers that actually occur in
    the timetable's own sessions.

    Standby slots are only ever eligible at these periods, so the generator
    can never place a teacher on a period no class meets at (e.g. period 12
    in a school whose day ends at period 9). Such a phantom slot can never
    be covered and would surface to the teacher as a permanent
    "بانتظار الإسناد" row.

    Falls back to the full PERIODS range when there are no sessions to learn
    from (e.g. no timetable yet) — preserving prior behaviour for that case.
    """
    seen: Set[int] = set()
    for s in sessions or []:
        p = _safe_int(s.get("period_number"), 0)
        if p in PERIODS:
            seen.add(p)
    return sorted(seen) if seen else list(PERIODS)


def _select_slots_for_teacher(
    *,
    eligible_days: List[str],
    eligible_by_day: Dict[str, List[int]],
    capacity: int,
    per_day: int,
    extras: int,
    period_load: Dict[Tuple[str, int], int],
    per_period_cap: int,
) -> Set[Tuple[str, int]]:
    """Pure helper: pick up to `capacity` (day, period) slots for a single
    teacher in a fairness-first manner.

    Within each working day:
      - The teacher is asked to take up to `target = per_day (+1 if early-day)`
        slots from `eligible_by_day[day]`.
      - Eligible periods are ordered by current global `period_load` ascending,
        then by period number — so the *least-filled* period of the day is
        picked first. This is the fix for the front-loading regression
        (Pasted-Objective-…1778715035001.txt) where every teacher was being
        stacked into period 1, 2, 3 because the previous algorithm took
        `day_periods[:take]` in raw period order.
      - Periods already at `per_period_cap` are skipped entirely. The cap is
        a hard upper bound; we under-fill the day rather than overflow it.
      - Skipped capacity (because every remaining eligible period is capped)
        is forfeit for that day — we do NOT spill over into another day,
        because that would re-introduce uneven per-teacher load.

    `period_load` is mutated in place so the next teacher sees fresh counts
    and naturally fills the now-emptier periods first. Determinism is
    preserved by the (load, period_number) tiebreak.
    """
    chosen: Set[Tuple[str, int]] = set()
    remaining = capacity
    cap = max(int(per_period_cap), 1)
    for idx, day in enumerate(eligible_days):
        if remaining <= 0:
            break
        target = per_day + (1 if idx < extras else 0)
        if target <= 0:
            continue
        day_periods = eligible_by_day.get(day, [])
        if not day_periods:
            continue
        # Fairness-first ordering: least-loaded period of the day first.
        day_periods_ordered = sorted(
            day_periods, key=lambda p: (period_load.get((day, p), 0), p),
        )
        take_budget = min(target, remaining)
        taken = 0
        for p in day_periods_ordered:
            if taken >= take_budget:
                break
            if period_load.get((day, p), 0) >= cap:
                # Period is saturated — skip and try the next least-loaded.
                continue
            chosen.add((day, p))
            period_load[(day, p)] = period_load.get((day, p), 0) + 1
            taken += 1
        remaining -= taken
    return chosen


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

    # Eligible-period universe: only the periods that actually exist in this
    # timetable. Prevents the auto pass from generating standby slots at a
    # period no class meets at (phantom slots that can never be covered).
    timetable_periods = _detect_timetable_periods(sessions)

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

    # 1b) Map: teacher_id -> set of (day, period) where they're explicitly
    # UNAVAILABLE (per-slot lockout from the `unavailability` collection,
    # entity_type="teacher"). Treated as locked, equivalent to busy for the
    # purpose of standby eligibility, but does not consume teaching quota.
    unavailable: Dict[str, Set[Tuple[str, int]]] = {tid: set() for tid in busy}
    unavail_rows = await gd_find(
        session, "unavailability",
        {"school_id": school_id, "entity_type": "teacher"},
        limit=10000,
    )
    for row in unavail_rows or []:
        tid = row.get("entity_id") or row.get("teacher_id")
        if not tid or tid not in unavailable:
            continue
        day = _normalize_day_key(row.get("day"))
        period = _safe_int(row.get("period"), 0)
        if not day or day not in DAYS or period not in PERIODS:
            continue
        unavailable[tid].add((day, period))

    # School-wide cap: hard upper bound on standby slots per teacher per week.
    # See spec docs/superpowers/specs/2026-05-03-standby-engine-refactor-design.md.
    school_cap = await _fetch_school_standby_cap(session, school_id)
    # Per-(day, period) hard ceiling — prevents the auto pass from
    # front-loading every teacher into the earliest periods of the day.
    per_period_cap = await _fetch_school_per_period_cap(session, school_id)

    # 2a) Seed period_load with pinned manual `add` overrides so the auto
    # pass treats them as already-occupying their slot for cap purposes.
    # This keeps "manual + auto" combined load under the cap whenever the
    # cap can still be honoured. (Manual edits themselves are authoritative
    # and may exceed the cap — they're applied below in apply_overrides_to_roster.)
    #
    # CRITICAL: only seed overrides that would actually SURVIVE
    # `apply_overrides_to_roster` — i.e. not collide with the teacher's
    # busy/unavailable/blocked-day state. Otherwise stale `add` rows would
    # consume cap during auto allocation but get dropped later, leaving
    # the final roster with phantom under-allocation. Mirrors the filter
    # in apply_overrides_to_roster (lines below).
    period_load: Dict[Tuple[str, int], int] = {}
    if apply_overrides:
        try:
            seed_overrides = await fetch_standby_overrides(
                session, school_id=school_id, timetable_id=timetable_id,
            )
        except Exception:  # noqa: BLE001 — degrade gracefully
            seed_overrides = []
        blocked_by_teacher_seed: Dict[str, Set[str]] = {
            t["id"]: _resolve_blocked_days(t)
            for t in teachers if t.get("id")
        }
        seen_pin: Set[Tuple[str, str, int]] = set()
        for ov in seed_overrides or []:
            if (ov.get("action") or "").lower() != "add":
                continue
            tid = ov.get("teacher_id")
            day = _normalize_day_key(ov.get("day"))
            period = _safe_int(ov.get("period"), 0)
            if not tid or day not in DAYS or period not in PERIODS:
                continue
            # Skip stale adds — they will be dropped by apply_overrides_to_roster.
            if (day, period) in busy.get(tid, set()):
                continue
            if (day, period) in unavailable.get(tid, set()):
                continue
            if day in blocked_by_teacher_seed.get(tid, set()):
                continue
            key = (tid, day, period)
            if key in seen_pin:
                continue
            seen_pin.add(key)
            period_load[(day, period)] = period_load.get((day, period), 0) + 1

    # 2b) Distribute capacity, prioritizing teachers with the most free
    # headroom (max remaining_capacity first). Stable secondary key on
    # full_name keeps the result deterministic across runs.
    def _priority(t: dict) -> tuple:
        wq = _safe_int(t.get("weekly_periods"), 0)
        load = teacher_load.get(t.get("id"), 0)
        free = max(wq - load, 0)
        return (-free, (t.get("full_name") or "").lower())

    teachers_sorted = sorted(teachers, key=_priority)

    roster: Dict[str, Set[Tuple[str, int]]] = {}
    for t in teachers_sorted:
        tid = t.get("id")
        if not tid:
            continue
        weekly_quota = _safe_int(t.get("weekly_periods"), 0)
        load = teacher_load.get(tid, 0)
        # Inverse Gap Analysis: remaining headroom from the master schedule.
        if weekly_quota <= 0:
            # No quota configured → teacher is excluded from auto-standby.
            # Manual `add` overrides still work via apply_overrides_to_roster.
            continue
        remaining_capacity = max(weekly_quota - load, 0)
        # Per-teacher explicit override (legacy `standby_periods` field) still
        # acts as a tighter ceiling when set; otherwise fall back to school cap.
        configured_standby = _safe_int(t.get("standby_periods"), 0)
        per_teacher_ceiling = configured_standby if configured_standby > 0 else school_cap
        capacity = min(remaining_capacity, per_teacher_ceiling)
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

        # Identify eligible periods per day in deterministic order. A slot
        # is ELIGIBLE iff it is neither BUSY (master schedule) nor
        # UNAVAILABLE (per-slot teacher unavailability).
        locked = busy[tid] | unavailable.get(tid, set())
        eligible_by_day: Dict[str, List[int]] = {}
        for day in eligible_days:
            day_periods = [p for p in timetable_periods if (day, p) not in locked]
            if day_periods:
                eligible_by_day[day] = day_periods
        if not eligible_by_day:
            continue

        # Even split per spec: per_day = N // D, extras = N % D.
        # First `extras` working days (in DAYS order) get +1 slot.
        D = len(eligible_days) or 1
        per_day = capacity // D
        extras = capacity % D
        chosen = _select_slots_for_teacher(
            eligible_days=eligible_days,
            eligible_by_day=eligible_by_day,
            capacity=capacity,
            per_day=per_day,
            extras=extras,
            period_load=period_load,
            per_period_cap=per_period_cap,
        )

        if chosen:
            roster[tid] = chosen

    if apply_overrides:
        overrides = await fetch_standby_overrides(
            session, school_id=school_id, timetable_id=timetable_id,
        )
        blocked_by_teacher = {
            t["id"]: _resolve_blocked_days(t)
            for t in teachers if t.get("id")
        }
        roster = apply_overrides_to_roster(
            roster, overrides,
            busy=busy,
            unavailable=unavailable,
            blocked_by_teacher=blocked_by_teacher,
        )

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
    unavailable: Dict[str, Set[Tuple[str, int]]] | None = None,
    blocked_by_teacher: Dict[str, Set[str]] | None = None,
) -> Dict[str, Set[Tuple[str, int]]]:
    """Apply manual `overrides` on top of the auto roster.

    Manual `add` overrides are dropped (kept in DB, surfaced as warnings
    by the projection) when the slot collides with a real teaching
    session, an `unavailability` lockout, or a teacher's blocked day.
    """
    final: Dict[str, Set[Tuple[str, int]]] = {
        tid: set(slots) for tid, slots in auto_roster.items()
    }
    busy = busy or {}
    unavailable = unavailable or {}
    blocked_by_teacher = blocked_by_teacher or {}
    for ov in overrides or []:
        tid = ov.get("teacher_id")
        day = _normalize_day_key(ov.get("day")) or (ov.get("day") or "").lower()
        period = _safe_int(ov.get("period"), 0)
        action = (ov.get("action") or "").lower()
        if not tid or day not in DAYS or period not in PERIODS:
            continue
        if action == "add":
            if (day, period) in busy.get(tid, set()):
                continue
            if (day, period) in unavailable.get(tid, set()):
                continue
            if day in blocked_by_teacher.get(tid, set()):
                continue
            final.setdefault(tid, set()).add((day, period))
        elif action == "remove":
            slots = final.get(tid)
            if slots is not None:
                slots.discard((day, period))
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


def project_day_centric_roster(
    *,
    final_roster: Dict[str, Set[Tuple[str, int]]],
    teachers: List[dict],
    overrides: List[dict],
    busy: Dict[str, Set[Tuple[str, int]]],
    periods: List[int],
    days: List[str] = DAYS,
    unavailable: Dict[str, Set[Tuple[str, int]]] | None = None,
    blocked_by_teacher: Dict[str, Set[str]] | None = None,
) -> Dict[str, Any]:
    """Day-centric projection of the standby roster (Saudi MoE format).

    Rows are pinned by slot_index for manual overrides; auto teachers
    fill remaining slots alphabetically. Returns `warnings` for stale
    manual overrides that collide with busy/unavailable/blocked-day
    constraints (records remain in `standby_overrides`).
    """
    unavailable = unavailable or {}
    blocked_by_teacher = blocked_by_teacher or {}
    teacher_meta = {}
    for t in teachers:
        tid = t.get("id")
        if not tid:
            continue
        teacher_meta[tid] = {
            "id": tid,
            "name": t.get("full_name") or t.get("name") or "—",
            "subject": t.get("specialization") or t.get("subject") or "",
        }

    # Split overrides into pinned-add, pinned-remove, and legacy
    # unpinned buckets so day-centric edits stay slot-local.
    pinned_add: Dict[Tuple[str, int, int], dict] = {}
    pinned_remove: Dict[Tuple[str, int, int], str] = {}
    manual_add_unpinned: Set[Tuple[str, str, int]] = set()
    pinned_teacher_in_dp: Dict[Tuple[str, int], Set[str]] = {}
    for ov in overrides or []:
        action = (ov.get("action") or "").lower()
        tid = ov.get("teacher_id")
        d = _normalize_day_key(ov.get("day")) or (ov.get("day") or "").lower()
        try:
            p = int(ov.get("period"))
        except (TypeError, ValueError):
            continue
        if not tid or d not in days or p not in periods:
            continue
        slot_raw = ov.get("slot_index")
        slot = None
        if isinstance(slot_raw, int) and slot_raw >= 1:
            slot = slot_raw
        if action == "add":
            meta = teacher_meta.get(tid)
            if not meta:
                continue
            if slot is None:
                manual_add_unpinned.add((tid, d, p))
                continue
            entry = {
                "teacher_id": tid,
                "teacher_name": meta["name"],
                "subject": meta["subject"],
                "source": "manual",
            }
            # Drop pinned add on busy/unavail/blocked; override stays
            # in DB and surfaces as a warning below.
            if (d, p) in busy.get(tid, set()):
                continue
            if (d, p) in unavailable.get(tid, set()):
                continue
            if d in blocked_by_teacher.get(tid, set()):
                continue
            pinned_add[(d, p, slot)] = entry
            pinned_teacher_in_dp.setdefault((d, p), set()).add(tid)
        elif action == "remove" and slot is not None:
            pinned_remove[(d, p, slot)] = tid

    # Auto pool: teachers from final_roster excluding those already
    # pinned in the same (d,p) so no teacher appears twice per column.
    auto_pool: Dict[Tuple[str, int], List[dict]] = {}
    for tid, slots in final_roster.items():
        meta = teacher_meta.get(tid)
        if not meta:
            continue
        for (d, p) in slots:
            if d not in days or p not in periods:
                continue
            if tid in pinned_teacher_in_dp.get((d, p), set()):
                continue
            source = "manual" if (tid, d, p) in manual_add_unpinned else "auto"
            auto_pool.setdefault((d, p), []).append({
                "teacher_id": tid,
                "teacher_name": meta["name"],
                "subject": meta["subject"],
                "source": source,
            })
    for key in auto_pool:
        auto_pool[key].sort(key=lambda e: e["teacher_name"])

    # Place autos into the lowest-numbered non-pinned slots.
    auto_slot: Dict[Tuple[str, int, int], dict] = {}
    auto_max_slot: Dict[Tuple[str, int], int] = {}
    for (d_key, p_key), pool in auto_pool.items():
        used = {s for (dd, pp, s) in pinned_add if dd == d_key and pp == p_key}
        used |= {s for (dd, pp, s) in pinned_remove if dd == d_key and pp == p_key}
        s = 0
        idx = 0
        while idx < len(pool):
            s += 1
            if s in used:
                continue
            auto_slot[(d_key, p_key, s)] = pool[idx]
            auto_max_slot[(d_key, p_key)] = s
            idx += 1

    pinned_max_in_dp: Dict[Tuple[str, int], int] = {}
    for (dd, pp, s) in list(pinned_add) + list(pinned_remove):
        cur = pinned_max_in_dp.get((dd, pp), 0)
        if s > cur:
            pinned_max_in_dp[(dd, pp)] = s

    days_payload: List[dict] = []
    for d in days:
        max_slots = 0
        for p in periods:
            max_slots = max(
                max_slots,
                pinned_max_in_dp.get((d, p), 0),
                auto_max_slot.get((d, p), 0),
            )
        slot_count = max(max_slots, 1)
        rows: List[dict] = []
        for slot_idx in range(1, slot_count + 1):
            cells: Dict[str, Optional[dict]] = {}
            for p in periods:
                if (d, p, slot_idx) in pinned_add:
                    cells[str(p)] = pinned_add[(d, p, slot_idx)]
                elif (d, p, slot_idx) in pinned_remove:
                    # Manual remove holds the slot empty (no backfill).
                    cells[str(p)] = None
                elif (d, p, slot_idx) in auto_slot:
                    cells[str(p)] = auto_slot[(d, p, slot_idx)]
                else:
                    cells[str(p)] = None
            rows.append({"slot_index": slot_idx, "cells": cells})
        days_payload.append({
            "day": d,
            "slot_count": slot_count,
            "rows": rows,
        })

    # Aggregate every manual add (pinned + unpinned + dropped) so the
    # warning loop catches DB rows that won't appear in the projection.
    manual_add: Set[Tuple[str, str, int]] = set(manual_add_unpinned)
    for (d_key, p_key, _s), entry in pinned_add.items():
        manual_add.add((entry["teacher_id"], d_key, p_key))
    for ov in overrides or []:
        if (ov.get("action") or "").lower() != "add":
            continue
        tid = ov.get("teacher_id")
        d = _normalize_day_key(ov.get("day")) or (ov.get("day") or "").lower()
        try:
            p = int(ov.get("period"))
        except (TypeError, ValueError):
            continue
        if tid and d in days and p in periods:
            manual_add.add((tid, d, p))

    # Surface stale manual adds dropped because reality changed.
    warnings: List[dict] = []
    for (tid, d, p) in manual_add:
        meta = teacher_meta.get(tid)
        if not meta:
            continue
        if (d, p) in final_roster.get(tid, set()):
            continue
        code = None
        message = None
        if (d, p) in busy.get(tid, set()):
            code = "manual_conflicts_with_busy"
            message = (
                f"التعديل اليدوي للمعلم «{meta['name']}» في يوم {d} حصة {p} "
                "صار يصطدم مع حصة فعلية وتم استبعاده من العرض دون مسحه."
            )
        elif (d, p) in unavailable.get(tid, set()):
            code = "manual_conflicts_with_unavailability"
            message = (
                f"التعديل اليدوي للمعلم «{meta['name']}» في يوم {d} حصة {p} "
                "صار ضمن منع زمني (إجازة/عدم توفر) وتم استبعاده من العرض دون مسحه."
            )
        elif d in blocked_by_teacher.get(tid, set()):
            code = "manual_conflicts_with_blocked_day"
            message = (
                f"التعديل اليدوي للمعلم «{meta['name']}» يوم {d} يقع في يوم "
                "إجازته وتم استبعاده من العرض دون مسحه."
            )
        if code:
            warnings.append({
                "teacher_id": tid,
                "teacher_name": meta["name"],
                "day": d,
                "period": p,
                "code": code,
                "message_ar": message,
            })

    return {"days": days_payload, "warnings": warnings}


__all__ = [
    "compute_standby_roster",
    "fetch_standby_overrides",
    "apply_overrides_to_roster",
    "project_day_centric_roster",
    "DAYS",
    "PERIODS",
    "DEFAULT_WEEKLY_QUOTA",
]
