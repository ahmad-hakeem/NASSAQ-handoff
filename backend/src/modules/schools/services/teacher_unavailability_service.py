"""
Teacher Unavailability & Relocation Service
Handles teacher/class unavailability records, relocation alerts, and recipient acknowledgment tracking.
"""
from fastapi import HTTPException
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
import uuid
import logging

from engines.sql_utils import (
    gd_find, gd_find_one, gd_insert, gd_update_one, gd_delete_one,
)
from engines.timetable_session_lifecycle import find_live_timetable_sessions
from src.modules.schools.dto.unavailability_dto import UnavailabilityCreate

logger = logging.getLogger("nassaq")


class TeacherUnavailabilityService:
    """Service handling unavailability creation, deletion, queries, and relocation acknowledgments."""

    @staticmethod
    async def update_teaching_loads(session, loads_data: dict, current_user: dict, x_school_context: str = None) -> dict:
        from src.modules.schools.services.school_settings_service import resolve_school_context, normalize_school_settings_doc
        school_id = await resolve_school_context(current_user, x_school_context)
        if not school_id:
            raise HTTPException(status_code=400, detail="Missing school context")

        now = datetime.now(timezone.utc).isoformat()
        normalized = normalize_school_settings_doc({
            "teaching_loads": loads_data,
            "updated_at": now
        })
        await gd_update_one(session, "school_settings", {"school_id": school_id}, normalized)
        return {"message": "تم تحديث أنصبة المعلمين"}

    @staticmethod
    async def update_teacher_availability(session, avail_data: dict, current_user: dict, x_school_context: str = None) -> dict:
        from src.modules.schools.services.school_settings_service import resolve_school_context, normalize_school_settings_doc
        school_id = await resolve_school_context(current_user, x_school_context)
        if not school_id:
            raise HTTPException(status_code=400, detail="Missing school context")

        now = datetime.now(timezone.utc).isoformat()
        normalized = normalize_school_settings_doc({
            "teacher_availability": avail_data,
            "updated_at": now
        })
        await gd_update_one(session, "school_settings", {"school_id": school_id}, normalized)
        return {"message": "تم تحديث توفر المعلم"}

    @staticmethod
    async def create_unavailability(session, data: UnavailabilityCreate, current_user: dict, x_school_context: str = None) -> dict:
        from src.modules.schools.services.school_settings_service import resolve_school_context
        school_id = await resolve_school_context(current_user, x_school_context)
        if not school_id:
            raise HTTPException(status_code=400, detail="School context required")

        unavailability_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        doc = {
            "id": unavailability_id,
            "school_id": school_id,
            "entity_type": data.entity_type,
            "entity_id": data.entity_id,
            "entity_name": data.entity_name,
            "unavailability_type": data.unavailability_type,
            "day": data.day,
            "period": data.period,
            "start_date": data.start_date,
            "end_date": data.end_date,
            "reason": data.reason,
            "alternative_location": (data.alternative_location or None) if data.entity_type == "class" else None,
            "recipient_ids": [],
            "acknowledged_by": [],
            "created_at": now,
            "created_by": current_user.get("id"),
        }

        await gd_insert(session, "unavailability", doc)

        notifications_sent = 0
        if data.entity_type == "class":
            from src.modules.notifications.controllers.notification_routes_mod import create_notification_internal

            active_timetable = await gd_find_one(
                session,
                "timetables",
                {"school_id": school_id, "status": {"$in": ["published", "draft"]}},
                sort=[("updated_at", -1)],
            )

            affected_sessions: list[dict] = []
            if active_timetable:
                session_query = {
                    "school_id": school_id,
                    "timetable_id": active_timetable.get("id"),
                    "class_id": data.entity_id,
                }
                all_class_sessions = await find_live_timetable_sessions(
                    session, session_query, limit=2000
                )
                if data.unavailability_type == "recurring":
                    ar_to_en = {
                        "الأحد": "sunday",
                        "الإثنين": "monday",
                        "الاثنين": "monday",
                        "الثلاثاء": "tuesday",
                        "الأربعاء": "wednesday",
                        "الخميس": "thursday",
                        "الجمعة": "friday",
                        "السبت": "saturday",
                    }
                    target_day = ar_to_en.get((data.day or "").strip(), (data.day or "").strip().lower())
                    try:
                        target_period = int(data.period) if data.period is not None else None
                    except (TypeError, ValueError):
                        target_period = None
                    for sess in all_class_sessions:
                        sess_day = (sess.get("day_of_week") or sess.get("day") or "").lower()
                        try:
                            sess_period = int(sess.get("period_number"))
                        except (TypeError, ValueError):
                            continue
                        if sess_day == target_day and sess_period == target_period:
                            affected_sessions.append(sess)
                else:
                    from datetime import date as _date, timedelta as _td
                    weekday_names = ["monday", "tuesday", "wednesday", "thursday",
                                     "friday", "saturday", "sunday"]
                    window_days: set[str] = set()
                    try:
                        s_dt = _date.fromisoformat((data.start_date or "").strip())
                        e_dt = _date.fromisoformat((data.end_date or "").strip())
                    except (TypeError, ValueError):
                        s_dt = e_dt = None
                    if s_dt and e_dt and s_dt <= e_dt:
                        cursor = s_dt
                        for _ in range(min((e_dt - s_dt).days + 1, 366)):
                            window_days.add(weekday_names[cursor.weekday()])
                            cursor += _td(days=1)
                    if window_days:
                        for sess in all_class_sessions:
                            sess_day = (sess.get("day_of_week") or sess.get("day") or "").lower()
                            if sess_day in window_days:
                                affected_sessions.append(sess)
                    else:
                        affected_sessions = all_class_sessions

            if not affected_sessions and not active_timetable:
                class_assignments = await gd_find(session, "teacher_assignments", {
                    "school_id": school_id,
                    "class_id": data.entity_id,
                    "is_active": True,
                }, limit=500)
                teacher_ids = list({a.get("teacher_id") for a in class_assignments if a.get("teacher_id")})
            else:
                teacher_ids = list({s.get("teacher_id") for s in affected_sessions if s.get("teacher_id")})

            recipient_user_ids: list[str] = []
            if teacher_ids:
                teacher_rows = await gd_find(
                    session,
                    "teachers",
                    {"id": {"$in": list(teacher_ids)}, "school_id": school_id},
                    limit=len(teacher_ids),
                )
                candidate_user_ids = list({
                    t.get("user_id") for t in teacher_rows if t.get("user_id")
                })
                if candidate_user_ids:
                    existing_users = await gd_find(
                        session,
                        "users",
                        {"id": {"$in": candidate_user_ids}},
                        limit=len(candidate_user_ids),
                    )
                    recipient_user_ids = [u.get("id") for u in existing_users if u.get("id")]

            if data.unavailability_type == "long_term":
                period_desc = f"من {data.start_date} إلى {data.end_date}"
            else:
                period_desc = f"يوم {data.day} - الحصة {data.period}"

            class_label = data.entity_name or data.entity_id
            if data.alternative_location:
                title_ar = "تم نقل طلاب الفصل إلى موقع بديل"
                title_en = "Class students relocated to alternative location"
                message_ar = f"تم نقل طلاب فصل {class_label} في {period_desc} إلى {data.alternative_location}."
                message_en = f"Students of class {class_label} have been relocated to {data.alternative_location} during {period_desc}."
            else:
                title_ar = "تنبيه: عدم توفر فصل دراسي"
                title_en = "Alert: Classroom Unavailable"
                message_ar = f"الفصل '{class_label}' غير متوفر ({period_desc}). يرجى نقل الطلاب إلى فصل بديل."
                message_en = f"Classroom '{class_label}' is unavailable ({period_desc}). Please relocate students to an alternative classroom."

            relocation_extra = None
            if data.alternative_location:
                relocation_extra = {
                    "unavailability_id": unavailability_id,
                    "class_id": data.entity_id,
                    "alternative_location": data.alternative_location,
                }

            for user_id in recipient_user_ids:
                await create_notification_internal(
                    title=title_ar,
                    message=message_ar,
                    recipient_id=user_id,
                    notification_type="schedule",
                    priority="high",
                    sender_id=current_user.get("id"),
                    related_entity="class",
                    related_entity_id=data.entity_id,
                    school_id=school_id,
                    title_en=title_en,
                    message_en=message_en,
                    action_url="/school/schedule" if data.alternative_location else None,
                    extra_data=relocation_extra,
                )

            notifications_sent = len(recipient_user_ids)

            if data.alternative_location and recipient_user_ids:
                await gd_update_one(
                    session,
                    "unavailability",
                    {"id": unavailability_id},
                    {"recipient_ids": list(recipient_user_ids)},
                )

        return {
            "success": True,
            "id": unavailability_id,
            "message": "تم حفظ فترة عدم التوفر بنجاح",
            "notifications_sent": notifications_sent
        }

    @staticmethod
    async def delete_unavailability(session, unavailability_id: str, current_user: dict, x_school_context: str = None) -> dict:
        from src.modules.schools.services.school_settings_service import resolve_school_context
        school_id = await resolve_school_context(current_user, x_school_context)
        if not school_id:
            raise HTTPException(status_code=400, detail="School context required")
        result = await gd_delete_one(session, "unavailability", {"id": unavailability_id, "school_id": school_id})
        if not result:
            raise HTTPException(status_code=404, detail="سجل عدم التوفر غير موجود")
        return {"success": True, "message": "تم حذف فترة عدم التوفر"}

    @staticmethod
    async def get_unavailability(session, entity_type: Optional[str], current_user: dict, x_school_context: str = None) -> dict:
        from src.modules.schools.services.school_settings_service import resolve_school_context
        school_id = await resolve_school_context(current_user, x_school_context)
        if not school_id:
            raise HTTPException(status_code=400, detail="School context required")

        query = {"school_id": school_id}
        if entity_type:
            query["entity_type"] = entity_type

        items = await gd_find(session, "unavailability", query, limit=1000)
        for item in items:
            recipients = item.get("recipient_ids") or []
            acked = item.get("acknowledged_by") or []
            item["recipient_count"] = len(recipients) if isinstance(recipients, list) else 0
            item["acknowledged_count"] = len(acked) if isinstance(acked, list) else 0
        return {"items": items}

    @staticmethod
    async def acknowledge_unavailability(session, unavailability_id: str, current_user: dict, x_school_context: str = None) -> dict:
        from src.modules.schools.services.school_settings_service import resolve_school_context
        school_id = await resolve_school_context(current_user, x_school_context)
        if not school_id:
            raise HTTPException(status_code=400, detail="School context required")

        record = await gd_find_one(session, "unavailability", {"id": unavailability_id, "school_id": school_id})
        if not record:
            raise HTTPException(status_code=404, detail="سجل عدم التوفر غير موجود")

        if not record.get("alternative_location"):
            raise HTTPException(status_code=400, detail="لا يلزم تأكيد الاستلام لهذا السجل")

        user_id = current_user.get("id")
        recipients = record.get("recipient_ids") or []
        if not isinstance(recipients, list):
            recipients = []

        if user_id not in recipients:
            raise HTTPException(status_code=403, detail="غير مخوّل لتأكيد استلام هذا الإشعار")

        acked = record.get("acknowledged_by") or []
        if not isinstance(acked, list):
            acked = []
        if user_id not in acked:
            acked.append(user_id)
            await gd_update_one(
                session,
                "unavailability",
                {"id": unavailability_id, "school_id": school_id},
                {"acknowledged_by": acked},
            )

        now_iso = datetime.now(timezone.utc).isoformat()
        user_notifs = await gd_find(
            session,
            "notifications",
            {"user_id": user_id, "type": "schedule"},
            limit=500,
        )
        for n in user_notifs:
            if n.get("unavailability_id") != unavailability_id:
                continue
            await gd_update_one(
                session,
                "notifications",
                {"id": n["id"]},
                {
                    "is_read": True,
                    "read_at": datetime.now(timezone.utc),
                    "is_acknowledged": True,
                    "acknowledged_at": now_iso,
                },
            )

        return {
            "success": True,
            "acknowledged_count": len(acked),
            "recipient_count": len(recipients),
        }

    @staticmethod
    async def list_unavailability_acknowledgements(session, unavailability_id: str, current_user: dict, x_school_context: str = None) -> dict:
        from src.modules.schools.services.school_settings_service import resolve_school_context
        school_id = await resolve_school_context(current_user, x_school_context)
        if not school_id:
            raise HTTPException(status_code=400, detail="School context required")

        record = await gd_find_one(session, "unavailability", {"id": unavailability_id, "school_id": school_id})
        if not record:
            raise HTTPException(status_code=404, detail="سجل عدم التوفر غير موجود")

        recipients = record.get("recipient_ids") or []
        acked = record.get("acknowledged_by") or []
        if not isinstance(recipients, list):
            recipients = []
        if not isinstance(acked, list):
            acked = []
        acked_set = set(acked)

        user_ids = list({*recipients, *acked})
        user_map: dict[str, str] = {}
        if user_ids:
            users = await gd_find(session, "users", {"id": {"$in": user_ids}}, limit=len(user_ids))
            user_map = {u.get("id"): (u.get("full_name") or "") for u in users}

        items = []
        for uid in recipients:
            items.append({
                "user_id": uid,
                "name": user_map.get(uid, ""),
                "acknowledged": uid in acked_set,
            })

        return {
            "recipient_count": len(recipients),
            "acknowledged_count": len(acked),
            "items": items,
        }
