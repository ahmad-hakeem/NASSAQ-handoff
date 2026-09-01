"""
School Settings Service
Handles School configuration, school info, working days/weekends, official holidays,
exception days, activity days, timing/breaks, and settings audit logs.
"""
from fastapi import HTTPException
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
import uuid
import logging

from dependencies import (
    audit_engine, AuditAction,
)
from engines.sql_utils import (
    gd_find, gd_find_one, gd_insert, gd_update_one, gd_delete_one,
)
from src.modules.schools.dto.school_dto import SchoolInfoUpdate
from src.modules.schools.dto.settings_dto import (
    WorkDaysConfig, OfficialHoliday, ExceptionDay, ActivityDay,
    SchoolTiming, BreakPeriod, UpdatePeriodsRequest
)

logger = logging.getLogger("nassaq")


def normalize_school_settings_doc(raw: dict) -> dict:
    """Translate a settings dict to match SchoolSettings ORM columns."""
    out = {}
    cs = dict(raw.get("custom_settings") or {})

    orm_map = {
        "school_day_start": "start_time",
        "school_day_end": "end_time",
        "period_duration_minutes": "period_duration",
        "break_duration_minutes": "break_duration",
    }
    passthrough_orm = {"id", "school_id", "working_days", "periods_per_day",
                       "start_time", "end_time", "period_duration", "break_duration",
                       "grading_system", "language", "calendar",
                       "notification_preferences", "features", "custom_settings",
                       "created_at", "updated_at", "education_track"}
    extras_to_cs = {"prayer_duration_minutes", "time_slots",
                    "working_days_ar", "working_days_en",
                    "weekend_days_ar", "weekend_days_en",
                    "academic_year", "current_semester", "attendance_pattern"}

    for k, v in raw.items():
        if k == "custom_settings":
            continue
        if k in orm_map:
            out[orm_map[k]] = v
            cs[k] = v
        elif k in passthrough_orm:
            out[k] = v
        elif k in extras_to_cs:
            cs[k] = v
        else:
            cs[k] = v

    out["custom_settings"] = cs
    return out


def dict_to_active_ar(wd: dict) -> list:
    day_map = {"sunday": "الأحد", "monday": "الإثنين", "tuesday": "الثلاثاء", "wednesday": "الأربعاء", "thursday": "الخميس", "friday": "الجمعة", "saturday": "السبت"}
    return [name for key, name in day_map.items() if wd.get(key) is True]


def dict_to_inactive_ar(wd: dict) -> list:
    day_map = {"sunday": "الأحد", "monday": "الإثنين", "tuesday": "الثلاثاء", "wednesday": "الأربعاء", "thursday": "الخميس", "friday": "الجمعة", "saturday": "السبت"}
    return [name for key, name in day_map.items() if wd.get(key) is False]


def resolve_working_days_ar(nested_settings: dict, settings: dict) -> list:
    cs = settings.get("custom_settings") or {}
    for source in (cs, nested_settings, settings):
        val = source.get("working_days_ar")
        if isinstance(val, list) and val:
            return val
    wd = cs.get("working_days") or nested_settings.get("working_days") or settings.get("working_days")
    if isinstance(wd, dict):
        return dict_to_active_ar(wd)
    return ["الأحد", "الإثنين", "الثلاثاء", "الأربعاء", "الخميس"]


def resolve_weekend_days_ar(nested_settings: dict, settings: dict) -> list:
    cs = settings.get("custom_settings") or {}
    for source in (cs, nested_settings, settings):
        val = source.get("weekend_days_ar")
        if isinstance(val, list) and val:
            return val
    wd = cs.get("working_days") or nested_settings.get("working_days") or settings.get("working_days")
    if isinstance(wd, dict):
        return dict_to_inactive_ar(wd)
    return ["الجمعة", "السبت"]


async def resolve_school_context(current_user: dict, x_school_context: str = None) -> str:
    """Resolve school_id from header or current user tenant."""
    from src.common.utils.tenant_scope import resolve_school_id
    return resolve_school_id(current_user, x_school_context)


class SchoolSettingsService:
    """Service handling School settings, days, periods, and timing."""

    @staticmethod
    async def get_school_info(session, current_user: dict, x_school_context: str = None) -> dict:
        school_id = await resolve_school_context(current_user, x_school_context)
        if not school_id:
            raise HTTPException(status_code=400, detail="Missing school context")

        school = await gd_find_one(session, "schools", {"id": school_id})
        if not school:
            raise HTTPException(status_code=404, detail="المدرسة غير موجودة")

        principal = await gd_find_one(session, "users", {
            "tenant_id": school_id,
            "role": "school_principal"
        })

        principal_phone = school.get("principal_phone") or (principal.get("phone") if principal else "")
        school_type = school.get("school_type") or school.get("type") or "public"

        return {
            "id": school.get("id"),
            "name": school.get("name"),
            "name_ar": school.get("name_ar") or school.get("name"),
            "name_en": school.get("name_en") or "",
            "code": school.get("code"),
            "type": school_type,
            "stage": school.get("stage") or "primary",
            "education_track": school.get("education_track") or "track-general",
            "email": school.get("email"),
            "phone": school.get("phone") or principal_phone,
            "city": school.get("city"),
            "region": school.get("region"),
            "address": school.get("address"),
            "principal_name": (principal.get("full_name") or principal.get("name")) if principal else school.get("principal_name", ""),
            "principal_phone": principal_phone,
            "principal_mobile": principal_phone,
            "principal_email": principal.get("email") if principal else school.get("principal_email", ""),
            "educational_pathway": school.get("educational_pathway", ""),
            "gender": school.get("gender") or "boys",
            "status": school.get("status") or "active",
        }

    @staticmethod
    async def update_school_info_direct(session, school_info: SchoolInfoUpdate, current_user: dict, x_school_context: str = None) -> dict:
        school_id = await resolve_school_context(current_user, x_school_context)
        if not school_id:
            raise HTTPException(status_code=400, detail="Missing school context")

        update_data = {
            "updated_at": datetime.now(timezone.utc).isoformat()
        }

        if school_info.name is not None:
            update_data["name"] = school_info.name
        if school_info.name_ar is not None:
            update_data["name_ar"] = school_info.name_ar
        if school_info.name_en is not None:
            update_data["name_en"] = school_info.name_en
        if school_info.email is not None:
            update_data["email"] = school_info.email
        if school_info.phone is not None:
            update_data["phone"] = school_info.phone
        if school_info.city is not None:
            update_data["city"] = school_info.city
        if school_info.region is not None:
            update_data["region"] = school_info.region
        if school_info.address is not None:
            update_data["address"] = school_info.address
        if school_info.type is not None:
            update_data["school_type"] = school_info.type
        if school_info.stage is not None:
            update_data["stage"] = school_info.stage
        if school_info.principal_name is not None:
            update_data["principal_name"] = school_info.principal_name
        resolved_phone = school_info.principal_mobile or school_info.principal_phone
        if resolved_phone is not None:
            update_data["principal_phone"] = resolved_phone
        if school_info.educational_pathway is not None:
            update_data["educational_pathway"] = school_info.educational_pathway

        await gd_update_one(session, "schools", {"id": school_id}, update_data)

        if resolved_phone is not None or school_info.principal_name is not None:
            principal_update = {"updated_at": datetime.now(timezone.utc).isoformat()}
            if resolved_phone is not None:
                principal_update["phone"] = resolved_phone
            if school_info.principal_name is not None:
                principal_update["full_name"] = school_info.principal_name
            await gd_update_one(session, "users", {
                "tenant_id": school_id,
                "role": "school_principal"
            }, principal_update)

        return {"success": True, "message": "تم تحديث بيانات المدرسة بنجاح"}

    @staticmethod
    async def get_school_settings(session, current_user: dict, x_school_context: str = None) -> dict:
        school_id = await resolve_school_context(current_user, x_school_context)
        if not school_id:
            raise HTTPException(status_code=400, detail="Missing school context")

        settings = await gd_find_one(session, "school_settings", {"school_id": school_id})
        default_settings = await gd_find_one(session, "default_settings", {"id": "default-school-settings"})

        if not settings and default_settings:
            settings_to_insert = normalize_school_settings_doc({
                "id": f"settings-{school_id}",
                "school_id": school_id,
                **{k: v for k, v in default_settings.items() if k != "id" and k != "_id"},
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat()
            })
            await gd_insert(session, "school_settings", settings_to_insert)
            settings = await gd_find_one(session, "school_settings", {"school_id": school_id})

        if not settings:
            settings = {}

        nested_settings = settings.get("settings", {}) or {}
        cs = settings.get("custom_settings") or {}

        def _pick(*candidates, default=None):
            for val in candidates:
                if val is not None:
                    return val
            return default

        start_t = _pick(
            cs.get("school_day_start"),
            settings.get("school_day_start"),
            nested_settings.get("school_day_start"),
            settings.get("start_time"),
            nested_settings.get("start_time"),
            (default_settings or {}).get("school_day_start"),
            (default_settings or {}).get("start_time"),
            default="07:00"
        )
        end_t = _pick(
            cs.get("school_day_end"),
            settings.get("school_day_end"),
            nested_settings.get("school_day_end"),
            settings.get("end_time"),
            nested_settings.get("end_time"),
            (default_settings or {}).get("school_day_end"),
            (default_settings or {}).get("end_time"),
            default="14:00"
        )

        timing = settings.get("timing") or nested_settings.get("timing") or {}
        if not timing:
            timing = {"start": start_t, "end": end_t}
        else:
            if "start" not in timing:
                timing["start"] = start_t
            if "end" not in timing:
                timing["end"] = end_t

        breaks = _pick(
            cs.get("breaks"),
            settings.get("breaks"),
            nested_settings.get("breaks"),
            (default_settings or {}).get("breaks"),
            default=[]
        )

        periods_pd = _pick(
            cs.get("periods_per_day"),
            settings.get("periods_per_day"),
            nested_settings.get("periods_per_day"),
            (default_settings or {}).get("periods_per_day"),
            default=7
        )

        period_dur = _pick(
            cs.get("period_duration_minutes"),
            settings.get("period_duration_minutes"),
            nested_settings.get("period_duration_minutes"),
            settings.get("period_duration"),
            (default_settings or {}).get("period_duration_minutes"),
            default=45
        )

        break_dur = _pick(
            cs.get("break_duration_minutes"),
            settings.get("break_duration_minutes"),
            nested_settings.get("break_duration_minutes"),
            settings.get("break_duration"),
            (default_settings or {}).get("break_duration_minutes"),
            default=15
        )

        prayer_dur = _pick(
            cs.get("prayer_duration_minutes"),
            settings.get("prayer_duration_minutes"),
            nested_settings.get("prayer_duration_minutes"),
            (default_settings or {}).get("prayer_duration_minutes"),
            default=20
        )

        clean_settings = {
            **settings,
            "school_day_start": start_t,
            "school_day_end": end_t,
            "timing": timing,
            "periods_per_day": periods_pd,
            "period_duration_minutes": period_dur,
            "break_duration_minutes": break_dur,
            "prayer_duration_minutes": prayer_dur,
            "breaks": breaks,
            "working_days_ar": resolve_working_days_ar(nested_settings, settings),
            "weekend_days_ar": resolve_weekend_days_ar(nested_settings, settings),
            "custom_settings": cs,
        }
        return clean_settings

    @staticmethod
    async def get_school_audit_logs(session, current_user: dict, x_school_context: str = None) -> list:
        school_id = await resolve_school_context(current_user, x_school_context)
        if not school_id:
            raise HTTPException(status_code=400, detail="Missing school context")

        logs = await gd_find(
            session, "audit_logs",
            {"tenant_id": school_id},
            order_by="timestamp",
            desc_order=True,
            limit=50
        )
        return logs

    @staticmethod
    async def update_school_info(session, info_data: dict, current_user: dict, x_school_context: str = None) -> dict:
        school_id = await resolve_school_context(current_user, x_school_context)
        if not school_id:
            raise HTTPException(status_code=400, detail="Missing school context")

        now = datetime.now(timezone.utc).isoformat()
        school_update = {"updated_at": now}
        if "name" in info_data:
            school_update["name"] = info_data["name"]
        if "name_ar" in info_data:
            school_update["name_ar"] = info_data["name_ar"]
        if "education_track" in info_data:
            school_update["education_track"] = info_data["education_track"]
        if "school_type" in info_data or "type" in info_data:
            from src.common.utils.school_type import normalize_school_type
            school_update["school_type"] = normalize_school_type(info_data.get("school_type") or info_data.get("type"))
        if "stage" in info_data:
            school_update["stage"] = info_data["stage"]
        if "gender" in info_data:
            school_update["gender"] = info_data["gender"]
        if "city" in info_data:
            school_update["city"] = info_data["city"]
        if "region" in info_data:
            school_update["region"] = info_data["region"]
        if "address" in info_data:
            school_update["address"] = info_data["address"]
        if "phone" in info_data:
            school_update["phone"] = info_data["phone"]
        if "email" in info_data:
            school_update["email"] = info_data["email"]

        await gd_update_one(session, "schools", {"id": school_id}, school_update)

        settings_update = normalize_school_settings_doc({
            "education_track": info_data.get("education_track", "track-general"),
            "school_info": info_data,
            "updated_at": now
        })
        await gd_update_one(session, "school_settings", {"school_id": school_id}, settings_update)
        return {"success": True, "message": "تم تحديث معلومات المدرسة بنجاح"}

    @staticmethod
    async def update_work_days(session, config: WorkDaysConfig, current_user: dict, x_school_context: str = None) -> dict:
        school_id = await resolve_school_context(current_user, x_school_context)
        if not school_id:
            raise HTTPException(status_code=400, detail="Missing school context")

        day_map = {
            "sunday": "الأحد",
            "monday": "الإثنين",
            "tuesday": "الثلاثاء",
            "wednesday": "الأربعاء",
            "thursday": "الخميس",
            "friday": "الجمعة",
            "saturday": "السبت"
        }
        working_days_ar = [name for key, name in day_map.items() if getattr(config, key)]
        weekend_days_ar = [name for key, name in day_map.items() if not getattr(config, key)]
        working_days_en = [key for key in day_map.keys() if getattr(config, key)]
        weekend_days_en = [key for key in day_map.keys() if not getattr(config, key)]

        now = datetime.now(timezone.utc).isoformat()
        normalized = normalize_school_settings_doc({
            "working_days": config.dict(),
            "working_days_ar": working_days_ar,
            "working_days_en": working_days_en,
            "weekend_days_ar": weekend_days_ar,
            "weekend_days_en": weekend_days_en,
            "updated_at": now
        })
        await gd_update_one(session, "school_settings", {"school_id": school_id}, normalized)
        return {"success": True, "message": "تم تحديث أيام العمل بنجاح"}

    @staticmethod
    async def add_official_holiday(session, holiday: OfficialHoliday, current_user: dict, x_school_context: str = None) -> dict:
        school_id = await resolve_school_context(current_user, x_school_context)
        if not school_id:
            raise HTTPException(status_code=400, detail="Missing school context")

        now = datetime.now(timezone.utc).isoformat()
        holiday_doc = {
            "id": str(uuid.uuid4()),
            "name": holiday.name,
            "start_date": holiday.start_date,
            "end_date": holiday.end_date or holiday.start_date,
            "created_at": now
        }
        settings = await gd_find_one(session, "school_settings", {"school_id": school_id})
        holidays = (settings.get("custom_settings") or {}).get("official_holidays") or settings.get("official_holidays") or []
        holidays.append(holiday_doc)
        normalized = normalize_school_settings_doc({
            "official_holidays": holidays,
            "updated_at": now
        })
        await gd_update_one(session, "school_settings", {"school_id": school_id}, normalized)
        return {"success": True, "holiday": holiday_doc, "message": "تم إضافة الإجازة بنجاح"}

    @staticmethod
    async def delete_official_holiday(session, holiday_id: str, current_user: dict, x_school_context: str = None) -> dict:
        school_id = await resolve_school_context(current_user, x_school_context)
        if not school_id:
            raise HTTPException(status_code=400, detail="Missing school context")

        settings = await gd_find_one(session, "school_settings", {"school_id": school_id})
        holidays = (settings.get("custom_settings") or {}).get("official_holidays") or settings.get("official_holidays") or []
        updated = [h for h in holidays if h.get("id") != holiday_id]
        now = datetime.now(timezone.utc).isoformat()
        normalized = normalize_school_settings_doc({
            "official_holidays": updated,
            "updated_at": now
        })
        await gd_update_one(session, "school_settings", {"school_id": school_id}, normalized)
        return {"success": True, "message": "تم حذف الإجازة بنجاح"}

    @staticmethod
    async def add_exception_day(session, exc: ExceptionDay, current_user: dict, x_school_context: str = None) -> dict:
        school_id = await resolve_school_context(current_user, x_school_context)
        if not school_id:
            raise HTTPException(status_code=400, detail="Missing school context")

        now = datetime.now(timezone.utc).isoformat()
        exc_doc = {
            "id": str(uuid.uuid4()),
            "date": exc.date,
            "reason": exc.reason,
            "is_holiday": exc.is_holiday,
            "created_at": now
        }
        settings = await gd_find_one(session, "school_settings", {"school_id": school_id})
        exceptions = (settings.get("custom_settings") or {}).get("exception_days") or settings.get("exception_days") or []
        exceptions.append(exc_doc)
        normalized = normalize_school_settings_doc({
            "exception_days": exceptions,
            "updated_at": now
        })
        await gd_update_one(session, "school_settings", {"school_id": school_id}, normalized)
        return {"success": True, "exception_day": exc_doc, "message": "تم إضافة اليوم الاستثنائي بنجاح"}

    @staticmethod
    async def delete_exception_day(session, exception_id: str, current_user: dict, x_school_context: str = None) -> dict:
        school_id = await resolve_school_context(current_user, x_school_context)
        if not school_id:
            raise HTTPException(status_code=400, detail="Missing school context")

        settings = await gd_find_one(session, "school_settings", {"school_id": school_id})
        exceptions = (settings.get("custom_settings") or {}).get("exception_days") or settings.get("exception_days") or []
        updated = [e for e in exceptions if e.get("id") != exception_id]
        now = datetime.now(timezone.utc).isoformat()
        normalized = normalize_school_settings_doc({
            "exception_days": updated,
            "updated_at": now
        })
        await gd_update_one(session, "school_settings", {"school_id": school_id}, normalized)
        return {"success": True, "message": "تم حذف اليوم الاستثنائي بنجاح"}

    @staticmethod
    async def add_activity_day(session, act: ActivityDay, current_user: dict, x_school_context: str = None) -> dict:
        school_id = await resolve_school_context(current_user, x_school_context)
        if not school_id:
            raise HTTPException(status_code=400, detail="Missing school context")

        now = datetime.now(timezone.utc).isoformat()
        act_doc = {
            "id": str(uuid.uuid4()),
            "date": act.date,
            "name": act.name,
            "notes": act.notes,
            "created_at": now
        }
        settings = await gd_find_one(session, "school_settings", {"school_id": school_id})
        activities = (settings.get("custom_settings") or {}).get("activity_days") or settings.get("activity_days") or []
        activities.append(act_doc)
        normalized = normalize_school_settings_doc({
            "activity_days": activities,
            "updated_at": now
        })
        await gd_update_one(session, "school_settings", {"school_id": school_id}, normalized)
        return {"success": True, "activity_day": act_doc, "message": "تم إضافة يوم النشاط بنجاح"}

    @staticmethod
    async def delete_activity_day(session, activity_id: str, current_user: dict, x_school_context: str = None) -> dict:
        school_id = await resolve_school_context(current_user, x_school_context)
        if not school_id:
            raise HTTPException(status_code=400, detail="Missing school context")

        settings = await gd_find_one(session, "school_settings", {"school_id": school_id})
        activities = (settings.get("custom_settings") or {}).get("activity_days") or settings.get("activity_days") or []
        updated = [a for a in activities if a.get("id") != activity_id]
        now = datetime.now(timezone.utc).isoformat()
        normalized = normalize_school_settings_doc({
            "activity_days": updated,
            "updated_at": now
        })
        await gd_update_one(session, "school_settings", {"school_id": school_id}, normalized)
        return {"success": True, "message": "تم حذف يوم النشاط بنجاح"}

    @staticmethod
    async def update_periods_per_day(session, req: UpdatePeriodsRequest, current_user: dict, x_school_context: str = None) -> dict:
        school_id = await resolve_school_context(current_user, x_school_context)
        if not school_id:
            raise HTTPException(status_code=400, detail="Missing school context")

        now = datetime.now(timezone.utc).isoformat()
        normalized = normalize_school_settings_doc({
            "periods_per_day": req.periods_per_day,
            "updated_at": now
        })
        await gd_update_one(session, "school_settings", {"school_id": school_id}, normalized)
        from src.modules.schools.services.time_slots_service import TimeSlotsService
        await TimeSlotsService.regenerate_time_slots(session, school_id)
        return {"success": True, "periods_per_day": req.periods_per_day, "message": "تم تحديث عدد الحصص وإعادة توليد الفترات بنجاح"}

    @staticmethod
    async def update_school_timing(session, timing: SchoolTiming, current_user: dict, x_school_context: str = None) -> dict:
        school_id = await resolve_school_context(current_user, x_school_context)
        if not school_id:
            raise HTTPException(status_code=400, detail="Missing school context")

        now = datetime.now(timezone.utc).isoformat()
        normalized = normalize_school_settings_doc({
            "school_day_start": timing.start,
            "school_day_end": timing.end,
            "timing": timing.dict(),
            "updated_at": now
        })
        await gd_update_one(session, "school_settings", {"school_id": school_id}, normalized)
        from src.modules.schools.services.time_slots_service import TimeSlotsService
        await TimeSlotsService.regenerate_time_slots(session, school_id)
        return {"success": True, "timing": timing.dict(), "message": "تم تحديث التوقيت وإعادة توليد الفترات بنجاح"}

    @staticmethod
    async def update_breaks(session, breaks: List[BreakPeriod], current_user: dict, x_school_context: str = None) -> dict:
        school_id = await resolve_school_context(current_user, x_school_context)
        if not school_id:
            raise HTTPException(status_code=400, detail="Missing school context")

        now = datetime.now(timezone.utc).isoformat()
        breaks_list = [b.dict() for b in breaks]
        normalized = normalize_school_settings_doc({
            "breaks": breaks_list,
            "updated_at": now
        })
        await gd_update_one(session, "school_settings", {"school_id": school_id}, normalized)
        from src.modules.schools.services.time_slots_service import TimeSlotsService
        await TimeSlotsService.regenerate_time_slots(session, school_id)
        return {"success": True, "breaks": breaks_list, "message": "تم تحديث الاستراحات وإعادة توليد الفترات بنجاح"}

    @staticmethod
    async def update_school_settings_full(session, new_settings: dict, current_user: dict, x_school_context: str = None) -> dict:
        school_id = await resolve_school_context(current_user, x_school_context)
        if not school_id:
            raise HTTPException(status_code=400, detail="Missing school context")

        now = datetime.now(timezone.utc).isoformat()
        existing = await gd_find_one(session, "school_settings", {"school_id": school_id})
        cs = dict(existing.get("custom_settings") or {}) if existing else {}

        if "working_days" in new_settings and isinstance(new_settings["working_days"], dict):
            day_map = {"sunday": "الأحد", "monday": "الإثنين", "tuesday": "الثلاثاء", "wednesday": "الأربعاء", "thursday": "الخميس", "friday": "الجمعة", "saturday": "السبت"}
            wd = new_settings["working_days"]
            new_settings["working_days_ar"] = [name for key, name in day_map.items() if wd.get(key)]
            new_settings["weekend_days_ar"] = [name for key, name in day_map.items() if not wd.get(key)]

        normalized = normalize_school_settings_doc({
            **cs,
            **new_settings,
            "school_id": school_id,
            "updated_at": now
        })

        if existing:
            await gd_update_one(session, "school_settings", {"school_id": school_id}, normalized)
        else:
            normalized["id"] = f"settings-{school_id}"
            normalized["created_at"] = now
            await gd_insert(session, "school_settings", normalized)

        from src.modules.schools.services.time_slots_service import TimeSlotsService
        await TimeSlotsService.regenerate_time_slots(session, school_id)

        await audit_engine.log_data_change(
            action=AuditAction.TENANT_UPDATED.value,
            performed_by=current_user.get("id", current_user.get("user_id")),
            entity_type="school_settings",
            entity_id=school_id,
            tenant_id=school_id,
            new_values={"action": "UPDATE_SETTINGS"}
        )

        return {"success": True, "message": "تم تحديث إعدادات المدرسة بالكامل بنجاح"}
