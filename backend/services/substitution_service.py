"""
Substitution Service — منطق إسناد البديل عند غياب معلم.

يُغذّي endpoint `/api/standby/candidates` بالمرشحين المرتّبين، و
endpoints `/api/substitutions` (إنشاء / تراجع) بمنطق الإسناد + الإشعار.

الصيغة الذكية للترتيب:
    S = T − (C × 2) + (W × 3)
حيث:
    T = حمل المعلم اليوم (عدد حصصه المُجدوَلة في نفس اليوم).
    C = عدد الحصص المجاورة (الحصة قبل أو بعد الخانة المطلوبة) للمعلم نفسه.
    W = عدد مرّات استخدام المعلم كمعلم انتظار خلال الأسبوع الحالي.
الأقل = الأفضل.

المرشّحون يأتون من «جدول الانتظار» (Standby Roster) الذي يبنيه
`standby_roster_service.compute_standby_roster`. الإسناد لا يعدّل
`timetable_sessions` نهائياً — بل يُحفظ سجل في collection
`substitute_assignments` كي يبقى الجدول الأصلي مرجعاً تاريخياً نظيفاً.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from engines.sql_utils import (
    gd_count,
    gd_delete_one,
    gd_find,
    gd_find_one,
    gd_insert,
)
from engines.notification_engine import (
    NotificationCategory,
    NotificationEngine,
    NotificationPriority,
    NotificationType,
)

from services.standby_roster_service import (
    DAYS,
    PERIODS,
    compute_standby_roster,
)


DAY_LABEL_AR = {
    "sunday": "الأحد", "monday": "الإثنين", "tuesday": "الثلاثاء",
    "wednesday": "الأربعاء", "thursday": "الخميس",
    "friday": "الجمعة", "saturday": "السبت",
}


def _safe_int(v, default: int = 0) -> int:
    try:
        return int(v) if v not in (None, "") else default
    except (TypeError, ValueError):
        return default


def _iso_week_start(d: datetime) -> str:
    """Returns the Sunday-anchored ISO date string for the current week.

    The school week in ar-SA starts on Sunday; we treat Sunday as day-0.
    """
    weekday = d.weekday()  # Monday=0..Sunday=6
    # Translate so Sunday=0:
    days_from_sun = (weekday + 1) % 7
    sun = (d - timedelta(days=days_from_sun)).date()
    return sun.isoformat()


async def _resolve_active_timetable(session, school_id: str) -> Optional[dict]:
    pub = await gd_find(
        session, "timetables",
        {"school_id": school_id, "status": "published"},
        order_by="created_at", desc_order=True, limit=1,
    )
    if pub:
        return pub[0]
    drafts = await gd_find(
        session, "timetables",
        {"school_id": school_id, "status": "draft"},
        order_by="created_at", desc_order=True, limit=1,
    )
    return drafts[0] if drafts else None


async def score_candidates_for_slot(
    session,
    *,
    school_id: str,
    day_of_week: str,
    period_number: int,
    absence_date: Optional[str] = None,
    limit: int = 3,
) -> Dict[str, Any]:
    """يُرجع المرشحين الأنسب لتغطية حصة شاغرة، مرتّبين تصاعدياً بالـ Score.

    لا يُرجع المعلمين الغائبين اليوم، ولا من لديه حصة فعلاً في نفس الخانة،
    ولا من سبق إسناده كبديل في نفس الخانة لنفس التاريخ.
    """
    day = (day_of_week or "").lower().strip()
    if day not in DAYS:
        return {"candidates": [], "total_considered": 0, "error_ar": "يوم غير صالح"}
    if period_number not in PERIODS:
        return {"candidates": [], "total_considered": 0, "error_ar": "رقم حصة غير صالح"}

    timetable = await _resolve_active_timetable(session, school_id)
    timetable_id = timetable.get("id") if timetable else None

    teachers = await gd_find(
        session, "teachers",
        {"school_id": school_id, "is_active": True},
        limit=2000,
    )
    if not teachers:
        return {"candidates": [], "total_considered": 0}

    sessions = []
    if timetable_id:
        sessions = await gd_find(
            session, "timetable_sessions",
            {"timetable_id": timetable_id},
            limit=10000,
        )

    # 1) Standby roster
    roster = await compute_standby_roster(
        session,
        school_id=school_id,
        timetable_id=timetable_id,
        teachers=teachers,
        sessions=sessions,
    )

    # 2) Indexes for scoring inputs
    busy_today: dict[str, set[int]] = {}            # teacher_id -> {periods today}
    busy_at_slot: set[str] = set()                   # teachers booked in our exact slot
    for s in sessions:
        tid = s.get("teacher_id")
        if not tid:
            continue
        sd = (s.get("day_of_week") or s.get("day") or "").lower()
        sp = _safe_int(s.get("period_number"), 0)
        if sd != day or sp <= 0:
            continue
        busy_today.setdefault(tid, set()).add(sp)
        if sp == period_number:
            busy_at_slot.add(tid)

    # 3) Absent teachers today (must not appear as candidates)
    absent_ids: set[str] = set()
    if not absence_date:
        absence_date = datetime.now(timezone.utc).date().isoformat()
    today_iso = absence_date
    user_to_teacher = {t.get("user_id"): t.get("id") for t in teachers if t.get("user_id")}
    valid_tids = {t.get("id") for t in teachers if t.get("id")}
    att_rows = await gd_find(
        session, "teacher_attendance",
        {"school_id": school_id, "status": "absent"},
        limit=2000,
    )
    for r in att_rows:
        d = r.get("date")
        d_iso = d if isinstance(d, str) else (d.isoformat() if hasattr(d, "isoformat") else "")
        if not d_iso.startswith(today_iso):
            continue
        raw = r.get("teacher_id") or r.get("user_id")
        tid = raw if raw in valid_tids else user_to_teacher.get(raw)
        if tid:
            absent_ids.add(tid)

    # 4) Existing substitute assignments this week (for W) and same-slot-today
    week_start = _iso_week_start(datetime.fromisoformat(absence_date))
    week_end = (datetime.fromisoformat(week_start) + timedelta(days=7)).date().isoformat()
    sub_rows = await gd_find(
        session, "substitute_assignments",
        {"school_id": school_id},
        limit=5000,
    )
    weekly_standby_count: dict[str, int] = {}
    occupied_slot: set[str] = set()
    for r in sub_rows:
        tid = r.get("substitute_teacher_id")
        ad = (r.get("absence_date") or "")[:10]
        if not tid or not ad:
            continue
        if week_start <= ad < week_end:
            weekly_standby_count[tid] = weekly_standby_count.get(tid, 0) + 1
        if (
            ad == absence_date
            and (r.get("day_of_week") or "").lower() == day
            and _safe_int(r.get("period_number"), 0) == period_number
        ):
            occupied_slot.add(tid)

    # 5) Score each eligible teacher
    scored: list[dict] = []
    for t in teachers:
        tid = t.get("id")
        if not tid:
            continue
        if tid in absent_ids:
            continue
        if tid in busy_at_slot:
            continue
        if tid in occupied_slot:
            continue
        # Must appear in standby roster for this slot
        slots = roster.get(tid, set())
        if (day, period_number) not in slots:
            continue

        T = len(busy_today.get(tid, set()))
        # Adjacent count: do they have a class at period-1 or period+1 today?
        adj = 0
        for adj_p in (period_number - 1, period_number + 1):
            if adj_p in PERIODS and adj_p in busy_today.get(tid, set()):
                adj += 1
        C = adj
        W = weekly_standby_count.get(tid, 0)
        S = T - (C * 2) + (W * 3)

        weekly_quota = _safe_int(t.get("weekly_periods"), 0)
        # Count this teacher's actual weekly load from sessions
        load = sum(1 for s in sessions if s.get("teacher_id") == tid)

        scored.append({
            "teacher_id": tid,
            "teacher_name": t.get("full_name") or t.get("name") or "—",
            "specialty": t.get("specialization") or t.get("subject") or "غير محدد",
            "user_id": t.get("user_id"),
            "weekly_quota": weekly_quota,
            "weekly_load": load,
            "today_load": T,
            "adjacent_count": C,
            "standby_used_this_week": W,
            "score": S,
            "score_breakdown": {"T": T, "C": C, "W": W, "formula": "S = T − (C × 2) + (W × 3)"},
        })

    # 6) Sort ascending: lowest score first; tie-break by today load, then name
    scored.sort(key=lambda x: (x["score"], x["today_load"], x["weekly_load"], x["teacher_name"]))

    # 7) Tag computation (after sort so we know who's #1 + can identify minima)
    min_W = min((c["standby_used_this_week"] for c in scored), default=0)
    for idx, c in enumerate(scored):
        tags: list[str] = []
        if idx == 0:
            tags.append("is_best_match")
        if c["adjacent_count"] == 0:
            tags.append("no_adjacent_classes")
        if c["weekly_quota"] > 0 and c["weekly_load"] / c["weekly_quota"] < 0.6:
            tags.append("low_quota")
        if c["standby_used_this_week"] == min_W:
            tags.append("least_standby")
        c["tags"] = tags
        c["rank"] = idx + 1

    return {
        "candidates": scored[:limit],
        "total_considered": len(teachers),
        "total_eligible": len(scored),
        "formula": "S = T − (C × 2) + (W × 3)",
        "formula_legend_ar": "T = حصصك اليوم · C = حصص مجاورة · W = مرات الانتظار هذا الأسبوع · الأقل = الأفضل",
        "day_of_week": day,
        "period_number": period_number,
        "absence_date": absence_date,
    }


async def assign_substitute(
    session,
    *,
    school_id: str,
    original_session_id: str,
    substitute_teacher_id: str,
    absence_date: str,
    notification_engine: NotificationEngine,
    actor_user_id: Optional[str] = None,
) -> Dict[str, Any]:
    """يُسجّل بديلاً لحصة معيّنة ويُرسل إشعاراً للمعلم البديل.

    لا يُعدّل `timetable_sessions` — يُنشئ صفّاً في `substitute_assignments`.
    """
    if not original_session_id or not substitute_teacher_id or not absence_date:
        return {"success": False, "error": "missing_fields", "message_ar": "بيانات ناقصة"}

    orig = await gd_find_one(session, "timetable_sessions", {"id": original_session_id})
    if not orig:
        return {"success": False, "error": "session_not_found", "message_ar": "الحصة غير موجودة"}
    if orig.get("school_id") and orig.get("school_id") != school_id:
        return {"success": False, "error": "cross_tenant", "message_ar": "الحصة لا تنتمي لهذه المدرسة"}

    sub_teacher = await gd_find_one(session, "teachers", {"id": substitute_teacher_id})
    if not sub_teacher or sub_teacher.get("school_id") != school_id:
        return {"success": False, "error": "invalid_teacher", "message_ar": "المعلم البديل غير صالح"}

    day = (orig.get("day_of_week") or orig.get("day") or "").lower()
    period = _safe_int(orig.get("period_number"), 0)
    if day not in DAYS or period not in PERIODS:
        return {"success": False, "error": "invalid_slot", "message_ar": "بيانات الحصة غير سليمة"}

    # Conflict checks: substitute must be free at this slot in main timetable
    main_conflict = await gd_count(session, "timetable_sessions", {
        "timetable_id": orig.get("timetable_id"),
        "teacher_id": substitute_teacher_id,
        "day_of_week": day,
        "period_number": period,
    })
    if main_conflict:
        return {"success": False, "error": "teacher_busy",
                "message_ar": "المعلم البديل لديه حصة في هذا الوقت"}

    # And not already substituting another class at this slot for this date
    parallel_sub = await gd_find_one(session, "substitute_assignments", {
        "school_id": school_id,
        "substitute_teacher_id": substitute_teacher_id,
        "day_of_week": day,
        "period_number": period,
        "absence_date": absence_date,
    })
    if parallel_sub:
        return {"success": False, "error": "already_substituting",
                "message_ar": "المعلم البديل يغطّي حصة أخرى في نفس الخانة"}

    # Idempotency: if a sub already exists for this exact (session, date), reject
    existing = await gd_find_one(session, "substitute_assignments", {
        "school_id": school_id,
        "original_session_id": original_session_id,
        "absence_date": absence_date,
    })
    if existing:
        return {"success": False, "error": "already_assigned",
                "message_ar": "تم إسناد بديل لهذه الحصة مسبقاً",
                "existing_id": existing.get("id")}

    sub_id = str(uuid.uuid4())
    now_iso = datetime.now(timezone.utc).isoformat()
    sub_doc = {
        "id": sub_id,
        "school_id": school_id,
        "timetable_id": orig.get("timetable_id"),
        "original_session_id": original_session_id,
        "original_teacher_id": orig.get("teacher_id"),
        "substitute_teacher_id": substitute_teacher_id,
        "absence_date": absence_date,
        "day_of_week": day,
        "period_number": period,
        "class_id": orig.get("class_id"),
        "class_name": orig.get("class_name"),
        "subject_id": orig.get("subject_id"),
        "subject_name": orig.get("subject_name"),
        "created_by": actor_user_id,
        "created_at": now_iso,
        "notification_id": None,
    }
    await gd_insert(session, "substitute_assignments", sub_doc)

    # ── Post-insert race guard ────────────────────────────────────────────
    # We don't have a unique DB constraint on (school_id, original_session_id,
    # absence_date) inside the generic_documents store, so two concurrent
    # POSTs could both pass the pre-insert `gd_find_one` check and end up
    # writing duplicate rows. Re-count after insert: if >1 row exists for
    # this conflict key OR another row exists for (substitute, slot, date),
    # rollback our insert and surface a clear error.
    dup_for_session = await gd_count(session, "substitute_assignments", {
        "school_id": school_id,
        "original_session_id": original_session_id,
        "absence_date": absence_date,
    })
    dup_for_substitute = await gd_count(session, "substitute_assignments", {
        "school_id": school_id,
        "substitute_teacher_id": substitute_teacher_id,
        "day_of_week": day,
        "period_number": period,
        "absence_date": absence_date,
    })
    if dup_for_session > 1 or dup_for_substitute > 1:
        await gd_delete_one(session, "substitute_assignments", {"id": sub_id})
        return {
            "success": False,
            "error": "race_conflict",
            "message_ar": "تم إسناد بديل لهذه الحصة من جلسة أخرى — حدّث الصفحة",
        }

    # Send in-app notification to substitute teacher
    notification_id = None
    sub_user_id = sub_teacher.get("user_id")
    if sub_user_id:
        try:
            day_ar = DAY_LABEL_AR.get(day, day)
            cls_name = orig.get("class_name") or "—"
            subj_name = orig.get("subject_name") or "—"
            title = "إسناد حصة انتظار جديدة"
            message = (
                f"تم إسنادك لتغطية حصة في {day_ar} — الحصة {period} · {cls_name} · {subj_name}."
            )
            notif = await notification_engine.create_notification(
                tenant_id=school_id,
                recipient_id=sub_user_id,
                title=title,
                message=message,
                notification_type=NotificationType.ALERT.value,
                category=NotificationCategory.SCHEDULE.value,
                priority=NotificationPriority.HIGH.value,
                entity_type="substitute_assignment",
                entity_id=sub_id,
                action_url=f"/schedule",
                metadata={
                    "absence_date": absence_date,
                    "day_of_week": day,
                    "period_number": period,
                    "class_id": orig.get("class_id"),
                    "subject_id": orig.get("subject_id"),
                },
            )
            notification_id = notif.get("id")
            if notification_id:
                from engines.sql_utils import gd_update_one
                await gd_update_one(
                    session, "substitute_assignments",
                    {"id": sub_id},
                    {"notification_id": notification_id},
                )
                sub_doc["notification_id"] = notification_id
        except Exception:
            # Notification failure must NOT roll back the assignment.
            import logging
            logging.getLogger("nassaq.substitution").exception(
                "Failed to send substitute notification (sub_id=%s)", sub_id
            )

    return {"success": True, "substitution": sub_doc}


async def revoke_substitute(
    session,
    *,
    school_id: str,
    substitution_id: str,
    notification_engine: NotificationEngine,
) -> Dict[str, Any]:
    """يحذف صفّ الإسناد ويزيل الإشعار المرتبط."""
    row = await gd_find_one(session, "substitute_assignments", {"id": substitution_id})
    if not row:
        return {"success": False, "error": "not_found", "message_ar": "السجل غير موجود"}
    if row.get("school_id") != school_id:
        return {"success": False, "error": "cross_tenant", "message_ar": "السجل لا ينتمي لهذه المدرسة"}

    notif_id = row.get("notification_id")
    sub_teacher = await gd_find_one(session, "teachers", {"id": row.get("substitute_teacher_id")})
    sub_user_id = sub_teacher.get("user_id") if sub_teacher else None

    deleted = await gd_delete_one(session, "substitute_assignments", {"id": substitution_id})
    if not deleted:
        return {"success": False, "error": "delete_failed", "message_ar": "فشل حذف السجل"}

    if notif_id and sub_user_id:
        try:
            await notification_engine.delete_notification(notif_id, sub_user_id)
        except Exception:
            import logging
            logging.getLogger("nassaq.substitution").exception(
                "Failed to delete substitute notification (notif_id=%s)", notif_id
            )

    return {"success": True, "id": substitution_id}


__all__ = [
    "score_candidates_for_slot",
    "assign_substitute",
    "revoke_substitute",
    "DAY_LABEL_AR",
]
