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


async def list_vacant_slots_for_absent_teacher(
    session,
    *,
    school_id: str,
    absent_teacher_id: str,
    absence_date: str,
    limit_per_slot: int = 3,
) -> Dict[str, Any]:
    """يُرجع كل الحصص الشاغرة لمعلم غائب في تاريخ معيّن مع المرشحين لكل خانة.

    تُستخدم لتغذية لوحة "تغطية كل حصص المعلم الغائب" (Bulk substitution).
    لا تشمل الخانات التي سبق إسناد بديل لها (تجنّباً للازدواج).
    """
    if not absent_teacher_id or not absence_date:
        return {
            "absent_teacher_id": absent_teacher_id,
            "absence_date": absence_date,
            "slots": [],
            "error_ar": "بيانات ناقصة",
        }

    try:
        day_of_week = datetime.fromisoformat(absence_date).strftime("%A").lower()
    except (TypeError, ValueError):
        return {
            "absent_teacher_id": absent_teacher_id,
            "absence_date": absence_date,
            "slots": [],
            "error_ar": "تاريخ غير صالح",
        }

    timetable = await _resolve_active_timetable(session, school_id)
    if not timetable:
        return {
            "absent_teacher_id": absent_teacher_id,
            "absence_date": absence_date,
            "day_of_week": day_of_week,
            "slots": [],
        }

    teacher = await gd_find_one(session, "teachers", {"id": absent_teacher_id})
    if not teacher or teacher.get("school_id") != school_id:
        return {
            "absent_teacher_id": absent_teacher_id,
            "absence_date": absence_date,
            "day_of_week": day_of_week,
            "slots": [],
            "error_ar": "المعلم غير موجود في هذه المدرسة",
        }

    teacher_sessions = await gd_find(
        session,
        "timetable_sessions",
        {
            "timetable_id": timetable.get("id"),
            "teacher_id": absent_teacher_id,
            "day_of_week": day_of_week,
        },
        limit=200,
    )

    existing_subs = await gd_find(
        session,
        "substitute_assignments",
        {
            "school_id": school_id,
            "original_teacher_id": absent_teacher_id,
            "absence_date": absence_date,
        },
        limit=200,
    )
    already_covered = {s.get("original_session_id") for s in existing_subs if s.get("original_session_id")}

    slots: list[dict] = []
    for sess in teacher_sessions:
        sid = sess.get("id")
        if not sid or sid in already_covered:
            continue
        period = _safe_int(sess.get("period_number"), 0)
        if period not in PERIODS:
            continue
        scoring = await score_candidates_for_slot(
            session,
            school_id=school_id,
            day_of_week=day_of_week,
            period_number=period,
            absence_date=absence_date,
            limit=limit_per_slot,
        )
        slots.append({
            "original_session_id": sid,
            "day_of_week": day_of_week,
            "period_number": period,
            "class_id": sess.get("class_id"),
            "class_name": sess.get("class_name"),
            "subject_id": sess.get("subject_id"),
            "subject_name": sess.get("subject_name"),
            "candidates": scoring.get("candidates", []),
            "total_eligible": scoring.get("total_eligible", 0),
        })

    slots.sort(key=lambda x: x["period_number"])

    return {
        "absent_teacher_id": absent_teacher_id,
        "absent_teacher_name": teacher.get("full_name") or teacher.get("name") or "—",
        "absence_date": absence_date,
        "day_of_week": day_of_week,
        "day_label_ar": DAY_LABEL_AR.get(day_of_week, day_of_week),
        "slots": slots,
        "formula": "S = T − (C × 2) + (W × 3)",
        "formula_legend_ar": (
            "T = حصصك اليوم · C = حصص مجاورة · W = مرات الانتظار هذا الأسبوع · الأقل = الأفضل"
        ),
    }


async def assign_bulk_substitutes(
    session,
    *,
    school_id: str,
    items: list[dict],
    absence_date: str,
    notification_engine: NotificationEngine,
    actor_user_id: Optional[str] = None,
) -> Dict[str, Any]:
    """يُسند عدّة حصص شاغرة دفعة واحدة ويُرسل إشعاراً مجمَّعاً لكل معلم بديل.

    items: قائمة من {original_session_id, substitute_teacher_id}.
    يحفظ لكل سجل ناجح حقل `batch_id` مشترك ليتمكّن المستخدم من التراجع عن
    كامل الدفعة بضغطة واحدة، أو تراجع الإسنادات الفردية عبر endpoint الأحادي.

    لا يُجهض على فشل صف واحد — يُرجع نتيجة تفصيلية لكل عنصر، ويرسل
    الإشعار المجمَّع فقط للمعلمين البدلاء الذين نجح لهم على الأقل إسناد واحد.
    """
    if not items:
        return {
            "success": False,
            "error": "empty_batch",
            "message_ar": "لا توجد عناصر للإسناد",
            "results": [],
        }
    if not absence_date:
        return {
            "success": False,
            "error": "missing_fields",
            "message_ar": "تاريخ الغياب مطلوب",
            "results": [],
        }

    batch_id = str(uuid.uuid4())
    now_iso = datetime.now(timezone.utc).isoformat()

    results: list[dict] = []
    successful_docs: list[dict] = []
    per_substitute: dict[str, list[dict]] = {}

    # In-memory guard against duplicate (sub, slot) pairs within the same batch.
    intra_batch_slots: set[tuple] = set()

    for item in items:
        orig_id = (item or {}).get("original_session_id")
        sub_tid = (item or {}).get("substitute_teacher_id")
        if not orig_id or not sub_tid:
            results.append({
                "success": False,
                "original_session_id": orig_id,
                "error": "missing_fields",
                "message_ar": "بيانات ناقصة",
            })
            continue

        orig = await gd_find_one(session, "timetable_sessions", {"id": orig_id})
        if not orig:
            results.append({
                "success": False,
                "original_session_id": orig_id,
                "error": "session_not_found",
                "message_ar": "الحصة غير موجودة",
            })
            continue
        if orig.get("school_id") and orig.get("school_id") != school_id:
            results.append({
                "success": False,
                "original_session_id": orig_id,
                "error": "cross_tenant",
                "message_ar": "الحصة لا تنتمي لهذه المدرسة",
            })
            continue

        sub_teacher = await gd_find_one(session, "teachers", {"id": sub_tid})
        if not sub_teacher or sub_teacher.get("school_id") != school_id:
            results.append({
                "success": False,
                "original_session_id": orig_id,
                "error": "invalid_teacher",
                "message_ar": "المعلم البديل غير صالح",
            })
            continue

        day = (orig.get("day_of_week") or orig.get("day") or "").lower()
        period = _safe_int(orig.get("period_number"), 0)
        if day not in DAYS or period not in PERIODS:
            results.append({
                "success": False,
                "original_session_id": orig_id,
                "error": "invalid_slot",
                "message_ar": "بيانات الحصة غير سليمة",
            })
            continue

        # Hard-constraint: substitute must be free at this slot in the timetable.
        main_conflict = await gd_count(session, "timetable_sessions", {
            "timetable_id": orig.get("timetable_id"),
            "teacher_id": sub_tid,
            "day_of_week": day,
            "period_number": period,
        })
        if main_conflict:
            results.append({
                "success": False,
                "original_session_id": orig_id,
                "error": "teacher_busy",
                "message_ar": "المعلم البديل لديه حصة في هذا الوقت",
            })
            continue

        intra_key = (sub_tid, day, period)
        parallel_sub = await gd_find_one(session, "substitute_assignments", {
            "school_id": school_id,
            "substitute_teacher_id": sub_tid,
            "day_of_week": day,
            "period_number": period,
            "absence_date": absence_date,
        })
        if parallel_sub or intra_key in intra_batch_slots:
            results.append({
                "success": False,
                "original_session_id": orig_id,
                "error": "already_substituting",
                "message_ar": "المعلم البديل يغطّي حصة أخرى في نفس الخانة",
            })
            continue

        existing = await gd_find_one(session, "substitute_assignments", {
            "school_id": school_id,
            "original_session_id": orig_id,
            "absence_date": absence_date,
        })
        if existing:
            results.append({
                "success": False,
                "original_session_id": orig_id,
                "error": "already_assigned",
                "message_ar": "تم إسناد بديل لهذه الحصة مسبقاً",
                "existing_id": existing.get("id"),
            })
            continue

        sub_id = str(uuid.uuid4())
        sub_doc = {
            "id": sub_id,
            "school_id": school_id,
            "timetable_id": orig.get("timetable_id"),
            "original_session_id": orig_id,
            "original_teacher_id": orig.get("teacher_id"),
            "substitute_teacher_id": sub_tid,
            "absence_date": absence_date,
            "day_of_week": day,
            "period_number": period,
            "class_id": orig.get("class_id"),
            "class_name": orig.get("class_name"),
            "subject_id": orig.get("subject_id"),
            "subject_name": orig.get("subject_name"),
            "created_by": actor_user_id,
            "created_at": now_iso,
            "batch_id": batch_id,
            "notification_id": None,
        }
        await gd_insert(session, "substitute_assignments", sub_doc)

        # Race guard — same as single-row endpoint.
        dup_for_session = await gd_count(session, "substitute_assignments", {
            "school_id": school_id,
            "original_session_id": orig_id,
            "absence_date": absence_date,
        })
        dup_for_substitute = await gd_count(session, "substitute_assignments", {
            "school_id": school_id,
            "substitute_teacher_id": sub_tid,
            "day_of_week": day,
            "period_number": period,
            "absence_date": absence_date,
        })
        if dup_for_session > 1 or dup_for_substitute > 1:
            await gd_delete_one(session, "substitute_assignments", {"id": sub_id})
            results.append({
                "success": False,
                "original_session_id": orig_id,
                "error": "race_conflict",
                "message_ar": "تم إسناد بديل لهذه الحصة من جلسة أخرى — حدّث الصفحة",
            })
            continue

        intra_batch_slots.add(intra_key)
        successful_docs.append(sub_doc)
        per_substitute.setdefault(sub_tid, []).append(sub_doc)
        results.append({
            "success": True,
            "original_session_id": orig_id,
            "substitution": sub_doc,
        })

    # ── Send one grouped notification per substitute teacher ──────────────
    notif_id_by_substitute: dict[str, str] = {}
    for sub_tid, docs in per_substitute.items():
        sub_teacher = await gd_find_one(session, "teachers", {"id": sub_tid})
        sub_user_id = sub_teacher.get("user_id") if sub_teacher else None
        if not sub_user_id:
            continue
        try:
            day_key = docs[0].get("day_of_week") or ""
            day_ar = DAY_LABEL_AR.get(day_key, day_key)
            count = len(docs)
            sorted_docs = sorted(docs, key=lambda x: x.get("period_number") or 0)
            slot_lines = "\n".join(
                f"• الحصة {d.get('period_number')} — {d.get('class_name') or '—'} ({d.get('subject_name') or '—'})"
                for d in sorted_docs
            )
            if count == 1:
                d = sorted_docs[0]
                title = "إسناد حصة انتظار جديدة"
                message = (
                    f"تم إسنادك لتغطية حصة في {day_ar} — الحصة {d.get('period_number')} · "
                    f"{d.get('class_name') or '—'} · {d.get('subject_name') or '—'}."
                )
            else:
                title = f"إسناد {count} حصص انتظار"
                message = f"تم إسنادك لتغطية {count} حصص في {day_ar}:\n{slot_lines}"

            notif = await notification_engine.create_notification(
                tenant_id=school_id,
                recipient_id=sub_user_id,
                title=title,
                message=message,
                notification_type=NotificationType.ALERT.value,
                category=NotificationCategory.SCHEDULE.value,
                priority=NotificationPriority.HIGH.value,
                entity_type="substitute_assignment_batch" if count > 1 else "substitute_assignment",
                entity_id=batch_id if count > 1 else docs[0].get("id"),
                action_url="/schedule",
                metadata={
                    "absence_date": absence_date,
                    "day_of_week": day_key,
                    "batch_id": batch_id,
                    "count": count,
                    "substitution_ids": [d.get("id") for d in sorted_docs],
                },
            )
            notification_id = notif.get("id")
            if notification_id:
                notif_id_by_substitute[sub_tid] = notification_id
                from engines.sql_utils import gd_update_one
                for d in docs:
                    await gd_update_one(
                        session, "substitute_assignments",
                        {"id": d.get("id")},
                        {"notification_id": notification_id},
                    )
                    d["notification_id"] = notification_id
        except Exception:
            import logging
            logging.getLogger("nassaq.substitution").exception(
                "Failed to send grouped substitute notification (batch=%s, sub=%s)",
                batch_id, sub_tid,
            )

    succeeded = sum(1 for r in results if r.get("success"))
    failed = len(results) - succeeded
    return {
        "success": succeeded > 0,
        "batch_id": batch_id if succeeded > 0 else None,
        "absence_date": absence_date,
        "total": len(items),
        "succeeded": succeeded,
        "failed": failed,
        "results": results,
    }


async def revoke_substitute_batch(
    session,
    *,
    school_id: str,
    batch_id: str,
    notification_engine: NotificationEngine,
) -> Dict[str, Any]:
    """يحذف كامل الإسنادات التي تشترك في `batch_id` ويُزيل إشعاراتها المجمَّعة."""
    if not batch_id:
        return {"success": False, "error": "missing_fields", "message_ar": "معرف الدفعة مطلوب"}

    rows = await gd_find(
        session,
        "substitute_assignments",
        {"school_id": school_id, "batch_id": batch_id},
        limit=500,
    )
    if not rows:
        return {"success": False, "error": "not_found", "message_ar": "الدفعة غير موجودة"}

    notif_user_pairs: list[tuple] = []
    deleted_ids: list[str] = []
    for row in rows:
        sub_id = row.get("id")
        notif_id = row.get("notification_id")
        sub_tid = row.get("substitute_teacher_id")
        if notif_id and sub_tid:
            sub_teacher = await gd_find_one(session, "teachers", {"id": sub_tid})
            sub_user_id = sub_teacher.get("user_id") if sub_teacher else None
            if sub_user_id:
                notif_user_pairs.append((notif_id, sub_user_id))
        ok = await gd_delete_one(session, "substitute_assignments", {"id": sub_id})
        if ok:
            deleted_ids.append(sub_id)

    seen: set[tuple] = set()
    for notif_id, user_id in notif_user_pairs:
        key = (notif_id, user_id)
        if key in seen:
            continue
        seen.add(key)
        try:
            await notification_engine.delete_notification(notif_id, user_id)
        except Exception:
            import logging
            logging.getLogger("nassaq.substitution").exception(
                "Failed to delete batch notification (notif_id=%s)", notif_id,
            )

    return {
        "success": True,
        "batch_id": batch_id,
        "revoked": len(deleted_ids),
        "ids": deleted_ids,
    }


__all__ = [
    "score_candidates_for_slot",
    "assign_substitute",
    "revoke_substitute",
    "list_vacant_slots_for_absent_teacher",
    "assign_bulk_substitutes",
    "revoke_substitute_batch",
    "DAY_LABEL_AR",
]
