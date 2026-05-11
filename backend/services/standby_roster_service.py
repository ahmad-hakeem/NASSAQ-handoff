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

    # 2) For each teacher, compute their free slots and distribute capacity.
    roster: Dict[str, Set[Tuple[str, int]]] = {}
    for t in teachers:
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
            day_periods = [p for p in PERIODS if (day, p) not in locked]
            if day_periods:
                eligible_by_day[day] = day_periods
        if not eligible_by_day:
            continue

        # Even split per spec: per_day = N // D, extras = N % D.
        # First `extras` working days (in DAYS order) get +1 slot.
        D = len(eligible_days)
        per_day = capacity // D
        extras = capacity % D
        chosen: Set[Tuple[str, int]] = set()
        remaining = capacity
        for idx, day in enumerate(eligible_days):
            if remaining <= 0:
                break
            target = per_day + (1 if idx < extras else 0)
            if target <= 0:
                continue
            day_periods = eligible_by_day.get(day, [])
            take = min(target, len(day_periods), remaining)
            for p in day_periods[:take]:
                chosen.add((day, p))
            remaining -= take

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


def project_day_centric_roster(
    *,
    final_roster: Dict[str, Set[Tuple[str, int]]],
    teachers: List[dict],
    overrides: List[dict],
    busy: Dict[str, Set[Tuple[str, int]]],
    periods: List[int],
    days: List[str] = DAYS,
) -> Dict[str, Any]:
    """يبني عرض «جدول الانتظار» السعودي day-centric من سجلات atomic موجودة.

    لا migration ولا collection جديدة — نقرأ نفس `final_roster` و
    `standby_overrides` التي تستهلكها الواجهة الـ teacher-centric ونعيد
    تجميعها بصيغة (يوم → صف منتظر #N → عمود حصة → معلم).

    لكل (يوم، حصة) نأخذ قائمة المعلمين المُسندين للانتظار، نفرز التعديلات
    اليدوية ("manual") قبل التلقائية ("auto") ثم بالاسم الأبجدي لضمان ترتيب
    ثابت. عدد صفوف اليوم = أقصى طول لقوائم الحصص في ذلك اليوم.

    يعيد أيضاً قائمة `warnings` لأي override يدوي صار يصطدم مع حصة فعلية
    للمعلم — لم يتم محوه (محفوظ في `standby_overrides`) لكنه أُسقط من العرض
    حماية للمستخدم.
    """
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

    # Manual-add lookup: (tid, day, period) -> True
    manual_add: Set[Tuple[str, str, int]] = set()
    for ov in overrides or []:
        if (ov.get("action") or "").lower() != "add":
            continue
        tid = ov.get("teacher_id")
        d = (ov.get("day") or "").lower()
        try:
            p = int(ov.get("period"))
        except (TypeError, ValueError):
            continue
        if tid and d in days and p in periods:
            manual_add.add((tid, d, p))

    # (day, period) -> ordered list of teacher entries
    by_day_period: Dict[Tuple[str, int], List[dict]] = {}
    for tid, slots in final_roster.items():
        meta = teacher_meta.get(tid)
        if not meta:
            continue
        for (d, p) in slots:
            if d not in days or p not in periods:
                continue
            source = "manual" if (tid, d, p) in manual_add else "auto"
            by_day_period.setdefault((d, p), []).append({
                "teacher_id": tid,
                "teacher_name": meta["name"],
                "subject": meta["subject"],
                "source": source,
            })

    # Stable ordering: manual first, then auto, then by name.
    for key in by_day_period:
        by_day_period[key].sort(
            key=lambda e: (0 if e["source"] == "manual" else 1, e["teacher_name"])
        )

    # Build day-centric rows
    days_payload: List[dict] = []
    for d in days:
        # Slot count = max teachers across periods for this day, min 1 row
        # so the day always renders with at least one (possibly empty) row.
        max_slots = 0
        for p in periods:
            max_slots = max(max_slots, len(by_day_period.get((d, p), [])))
        slot_count = max(max_slots, 1)
        rows: List[dict] = []
        for idx in range(slot_count):
            cells: Dict[str, Optional[dict]] = {}
            for p in periods:
                lst = by_day_period.get((d, p), [])
                cells[str(p)] = lst[idx] if idx < len(lst) else None
            rows.append({"slot_index": idx + 1, "cells": cells})
        days_payload.append({
            "day": d,
            "slot_count": slot_count,
            "rows": rows,
        })

    # Conflict warnings: manual add that lost out to busy (silently dropped).
    warnings: List[dict] = []
    for (tid, d, p) in manual_add:
        meta = teacher_meta.get(tid)
        if not meta:
            continue
        # In final_roster?
        if (d, p) in final_roster.get(tid, set()):
            continue
        # Was it dropped because the teacher is now busy at this slot?
        if (d, p) in busy.get(tid, set()):
            warnings.append({
                "teacher_id": tid,
                "teacher_name": meta["name"],
                "day": d,
                "period": p,
                "code": "manual_conflicts_with_busy",
                "message_ar": (
                    f"التعديل اليدوي للمعلم «{meta['name']}» في يوم {d} حصة {p} "
                    "صار يصطدم مع حصة فعلية وتم استبعاده من العرض دون مسحه."
                ),
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
