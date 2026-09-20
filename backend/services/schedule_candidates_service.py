"""
Schedule Candidates Service — يقترح معلمين مرشحين لكل خانة فارغة في الجدول.

Scoring (max 100):
  - specialty match: 50  (تخصص المعلم يطابق المادة)
  - nisab remaining: 0–30 (نسبة الحصص المتبقية من النصاب الأسبوعي)
  - availability:    0–20 (المعلم غير مشغول في نفس اليوم/الحصة)

تُعاد أعلى 3 مرشحين، مع شرح مختصر لسبب الترتيب.
"""
from typing import Any, Dict, List, Optional

from engines.sql_utils import gd_find, gd_find_one
from engines.timetable_session_lifecycle import (
    count_live_timetable_sessions,
    find_live_timetable_sessions,
)


DEFAULT_WEEKLY_NISAB = 24


def _matches_specialty(teacher: Dict[str, Any], subject: Optional[Dict[str, Any]]) -> bool:
    if not subject:
        return False
    sid = subject.get("id")
    sname = (subject.get("name") or subject.get("name_ar") or "").strip()
    if sid and (
        teacher.get("primary_subject_id") == sid
        or sid in (teacher.get("subject_ids") or [])
        or teacher.get("specialization") == sid
    ):
        return True
    spec_name = (teacher.get("specialization") or teacher.get("subject") or "").strip()
    if sname and spec_name and (sname in spec_name or spec_name in sname):
        return True
    return False


def _specialty_label(teacher: Dict[str, Any]) -> str:
    return (
        teacher.get("specialization")
        or teacher.get("subject")
        or "غير محدد"
    )


async def get_candidates(
    session,
    *,
    timetable_id: str,
    school_id: str,
    class_id: str,
    day_of_week: str,
    period_number: int,
    subject_id: Optional[str] = None,
    specialty_filter: Optional[str] = None,
    only_available: bool = False,
    limit: int = 3,
) -> Dict[str, Any]:
    """
    يُرجع قائمة المرشحين مع تفاصيل التقييم.
    """
    # 1. جلب المادة (إن وُجدت)
    subject_doc = None
    if subject_id:
        subject_doc = await gd_find_one(session, "subjects", {"id": subject_id})

    # 2. جلب جميع معلمي المدرسة النشطين
    teachers = await gd_find(
        session,
        "teachers",
        {"school_id": school_id, "is_active": True},
        limit=2000,
    )

    if not teachers:
        return {"candidates": [], "total_considered": 0}

    teacher_ids = [t["id"] for t in teachers]

    # 3. جلب جدول الحصص الحالي للمدرسة (لحساب النصاب والتوافر)
    all_sessions = await find_live_timetable_sessions(
        session,
        {"timetable_id": timetable_id, "teacher_id": {"$in": teacher_ids}},
        limit=10000,
    )

    # حساب الحمل الأسبوعي لكل معلم
    weekly_load: Dict[str, int] = {}
    busy_at_slot: set = set()
    for s in all_sessions:
        tid = s.get("teacher_id")
        if not tid:
            continue
        weekly_load[tid] = weekly_load.get(tid, 0) + 1
        if (
            s.get("day_of_week") == day_of_week
            and s.get("period_number") == period_number
        ):
            busy_at_slot.add(tid)

    # 4. تقييم كل معلم
    scored: List[Dict[str, Any]] = []
    for t in teachers:
        tid = t["id"]
        load = weekly_load.get(tid, 0)
        target = t.get("weekly_periods") or DEFAULT_WEEKLY_NISAB
        try:
            target = int(target) if target else DEFAULT_WEEKLY_NISAB
        except (TypeError, ValueError):
            target = DEFAULT_WEEKLY_NISAB
        target = max(target, 1)

        is_available = tid not in busy_at_slot
        specialty_ok = _matches_specialty(t, subject_doc) if subject_doc else None

        # فلتر التخصص
        spec_label = _specialty_label(t)
        if specialty_filter and specialty_filter.strip():
            if specialty_filter.strip() not in spec_label:
                continue

        # فلتر التوافر
        if only_available and not is_available:
            continue

        # الدرجات
        specialty_score = 0
        if subject_doc:
            specialty_score = 50 if specialty_ok else 0
        else:
            specialty_score = 25  # حيادي عند غياب المادة

        remaining = max(target - load, 0)
        nisab_score = round(30 * (remaining / target), 2) if target else 0

        availability_score = 20 if is_available else 0

        total_score = round(specialty_score + nisab_score + availability_score, 2)

        # سبب الترتيب باللغة العربية
        reason_parts = []
        if subject_doc:
            reason_parts.append("تخصص مطابق" if specialty_ok else "تخصص مختلف")
        reason_parts.append(f"نصاب {load}/{target}")
        reason_parts.append("متاح" if is_available else "مشغول بحصة أخرى")
        reason_ar = " · ".join(reason_parts)

        scored.append({
            "teacher_id": tid,
            "teacher_name": t.get("full_name") or t.get("name") or "—",
            "specialty": spec_label,
            "weekly_load": load,
            "weekly_target": target,
            "remaining_nisab": remaining,
            "available": is_available,
            "specialty_match": specialty_ok,
            "score": total_score,
            "score_breakdown": {
                "specialty": specialty_score,
                "nisab": nisab_score,
                "availability": availability_score,
            },
            "reason_ar": reason_ar,
        })

    # 5. الترتيب: الأعلى نقاطاً، ثم المتاح أولاً، ثم الأقل حملاً
    scored.sort(
        key=lambda x: (-x["score"], not x["available"], x["weekly_load"], x["teacher_name"]),
    )

    return {
        "candidates": scored[:limit],
        "total_considered": len(teachers),
    }


async def assign_teacher_to_slot(
    session,
    *,
    timetable_id: str,
    school_id: str,
    class_id: str,
    subject_id: Optional[str],
    teacher_id: str,
    day_of_week: str,
    period_number: int,
) -> Dict[str, Any]:
    """يُنشئ حصة جديدة في timetable_sessions ويتحقق من التعارضات والعزل بين المدارس."""
    import uuid
    from datetime import datetime, timezone
    from engines.sql_utils import gd_insert, gd_delete_one

    # 1) عزل المستأجر — تحقق أن المعلم/الفصل/المادة كلها تنتمي لنفس المدرسة
    teacher = await gd_find_one(session, "teachers", {"id": teacher_id})
    if not teacher or teacher.get("school_id") != school_id:
        return {
            "success": False,
            "error": "invalid_teacher",
            "message_ar": "المعلم غير موجود أو لا ينتمي لهذه المدرسة",
        }
    cls = await gd_find_one(session, "classes", {"id": class_id})
    if not cls or cls.get("school_id") != school_id:
        return {
            "success": False,
            "error": "invalid_class",
            "message_ar": "الفصل غير موجود أو لا ينتمي لهذه المدرسة",
        }
    subj = None
    if subject_id:
        subj = await gd_find_one(session, "subjects", {"id": subject_id})
        if not subj or (subj.get("school_id") and subj.get("school_id") != school_id and not subj.get("is_global")):
            return {
                "success": False,
                "error": "invalid_subject",
                "message_ar": "المادة غير موجودة أو لا تنتمي لهذه المدرسة",
            }
    subj = subj or {}

    # 2) فحص التعارض المسبق (best-effort قبل الإدراج)
    teacher_conflicts = await find_live_timetable_sessions(
        session,
        {
            "timetable_id": timetable_id,
            "teacher_id": teacher_id,
            "day_of_week": day_of_week,
            "period_number": period_number,
        },
        limit=1,
    )
    if teacher_conflicts:
        return {
            "success": False,
            "error": "teacher_conflict",
            "message_ar": "المعلم لديه حصة أخرى في هذا الوقت",
        }

    class_conflicts = await find_live_timetable_sessions(
        session,
        {
            "timetable_id": timetable_id,
            "class_id": class_id,
            "day_of_week": day_of_week,
            "period_number": period_number,
        },
        limit=1,
    )
    if class_conflicts:
        return {
            "success": False,
            "error": "class_conflict",
            "message_ar": "الفصل لديه حصة أخرى في هذا الوقت",
        }
    slot = await gd_find_one(session, "time_slots", {
        "school_id": school_id,
        "period_number": period_number,
        "is_break": {"$ne": True},
    })
    if not slot:
        slot = await gd_find_one(session, "time_slots", {
            "school_id": school_id,
            "slot_number": period_number,
            "is_break": {"$ne": True},
        })

    session_id = str(uuid.uuid4())
    doc = {
        "id": session_id,
        "timetable_id": timetable_id,
        "school_id": school_id,
        "class_id": class_id,
        "class_name": cls.get("name") or cls.get("name_ar"),
        "grade_id": cls.get("grade_id", ""),
        "subject_id": subject_id,
        "subject_name": subj.get("name") or subj.get("name_ar"),
        "teacher_id": teacher_id,
        "teacher_name": teacher.get("full_name") or teacher.get("name"),
        "day_of_week": day_of_week,
        "day": day_of_week,
        "period_number": period_number,
        "time_slot_id": (slot or {}).get("id"),
        "start_time": (slot or {}).get("start_time", ""),
        "end_time": (slot or {}).get("end_time", ""),
        "session_type": "class",
        "source_type": "candidate_picker",
        "status": "scheduled",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await gd_insert(session, "timetable_sessions", doc)

    # 3) Post-insert verification — يلتقط حالات السباق (concurrent assigns)
    # في حال وُجدت أكثر من حصة لنفس (timetable, class, day, period) أو نفس المعلم
    # في نفس الخانة، نتراجع عن إدراجنا الأخير ونعيد خطأ.
    class_count = await count_live_timetable_sessions(session, {
        "timetable_id": timetable_id,
        "class_id": class_id,
        "day_of_week": day_of_week,
        "period_number": period_number,
    })
    teacher_count = await count_live_timetable_sessions(session, {
        "timetable_id": timetable_id,
        "teacher_id": teacher_id,
        "day_of_week": day_of_week,
        "period_number": period_number,
    })
    if class_count > 1 or teacher_count > 1:
        await gd_delete_one(session, "timetable_sessions", {"id": session_id})
        return {
            "success": False,
            "error": "race_conflict",
            "message_ar": "تم اعتماد تعيين آخر بنفس الخانة في نفس اللحظة — حدّث الجدول وأعد المحاولة",
        }

    return {"success": True, "session_id": session_id, "session": doc}
