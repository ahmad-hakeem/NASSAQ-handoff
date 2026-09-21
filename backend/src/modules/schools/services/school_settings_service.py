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
import re

from sqlalchemy import text

from dependencies import (
    audit_engine, AuditAction, SchoolStatus,
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


# The database columns below are the only source of truth for timetable
# settings.  The camelCase names are wire aliases used by the principal UI;
# they must never become a second, competing copy in custom_settings.
_CANONICAL_ALIASES = {
    "start_time": ("start_time", "school_day_start", "dayStart", "schoolDayStart"),
    "end_time": ("end_time", "school_day_end", "dayEnd", "schoolDayEnd"),
    "periods_per_day": ("periods_per_day", "periodsPerDay", "numberOfPeriods"),
    "period_duration": (
        "period_duration", "period_duration_minutes", "periodDuration",
        "lessonDuration", "lesson_duration_minutes",
    ),
    "break_duration": (
        "break_duration", "break_duration_minutes", "breakDuration",
        "baseBreakDuration",
    ),
    "working_days": ("working_days", "workingDays", "activeWeekdays"),
}
_ALL_CANONICAL_INPUT_KEYS = {
    alias for aliases in _CANONICAL_ALIASES.values() for alias in aliases
}
_DAY_MAP = {
    "sunday": "الأحد", "monday": "الإثنين", "tuesday": "الثلاثاء",
    "wednesday": "الأربعاء", "thursday": "الخميس", "friday": "الجمعة",
    "saturday": "السبت",
}
_AR_TO_DAY = {value: key for key, value in _DAY_MAP.items()}
_DIGIT_TRANSLATION = str.maketrans(
    "٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹",
    "01234567890123456789",
)
_TIMING_ERROR_CODE = "TIMING_VALIDATION_ERROR"
_TIMING_PROFILE_NAMES = {"summer", "winter", "ramadan"}
_TIMING_PROFILE_FIELDS = {
    "dayStart", "dayEnd", "periodsPerDay", "periodDuration",
    "breakDuration", "breakAfterPeriod", "breaks",
}


def _timing_error(reason: str, field: str, message: str, **metadata) -> HTTPException:
    """Build the stable validation contract consumed by timetable settings."""
    return HTTPException(
        status_code=422,
        detail={
            "code": _TIMING_ERROR_CODE,
            "reason": reason,
            "field": field,
            **metadata,
            "message": message,
        },
    )


def normalize_school_settings_doc(raw: dict) -> dict:
    """Translate a settings dict to match SchoolSettings ORM columns."""
    out = {}
    cs = dict(raw.get("custom_settings") or {})
    for key in _ALL_CANONICAL_INPUT_KEYS:
        cs.pop(key, None)

    alias_to_canonical = {
        alias: canonical
        for canonical, aliases in _CANONICAL_ALIASES.items()
        for alias in aliases
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
        if k in alias_to_canonical:
            out[alias_to_canonical[k]] = v
        elif k in passthrough_orm:
            out[k] = v
        elif k in extras_to_cs:
            cs[k] = v
        else:
            cs[k] = v

    out["custom_settings"] = cs
    return out


def _first_present(payload: dict, aliases: tuple):
    for key in aliases:
        if key in payload:
            return payload[key]
    return None


def _resolve_canonical_value(
    settings: Optional[dict], canonical: str, default: Any = None
) -> Any:
    """Read one canonical setting with the same precedence everywhere.

    Real ORM columns are authoritative when populated.  The remaining
    locations are read-only compatibility fallbacks for legacy rows.
    """
    settings = settings or {}
    nested = settings.get("settings") or {}
    custom = settings.get("custom_settings") or {}
    aliases = _CANONICAL_ALIASES[canonical]
    candidates = [settings.get(canonical)]
    candidates.extend(settings.get(alias) for alias in aliases if alias != canonical)
    candidates.extend(nested.get(alias) for alias in aliases)
    candidates.extend(custom.get(alias) for alias in aliases)
    for value in candidates:
        if value is not None:
            return value
    return default


def _resolve_breaks(settings: Optional[dict]) -> list:
    settings = settings or {}
    nested = settings.get("settings") or {}
    custom = settings.get("custom_settings") or {}
    for source in (settings, nested, custom):
        value = source.get("breaks")
        if value is not None:
            return value
    return []


def _has_breaks_setting(settings: Optional[dict]) -> bool:
    settings = settings or {}
    return any(
        "breaks" in source
        for source in (
            settings,
            settings.get("settings") or {},
            settings.get("custom_settings") or {},
        )
    )


def _parse_int(value: Any, field: str, minimum: int, maximum: int) -> int:
    if isinstance(value, bool):
        raise _timing_error(
            "invalid_integer", field, f"{field} must be an integer."
        )
    normalized = value.translate(_DIGIT_TRANSLATION) if isinstance(value, str) else value
    try:
        parsed = int(normalized)
    except (TypeError, ValueError):
        raise _timing_error(
            "invalid_integer", field, f"{field} must be an integer."
        )
    if isinstance(value, float) and not value.is_integer():
        raise _timing_error(
            "invalid_integer", field, f"{field} must be an integer."
        )
    if isinstance(normalized, str) and not re.fullmatch(r"[+-]?\d+", normalized.strip()):
        raise _timing_error(
            "invalid_integer", field, f"{field} must be an integer."
        )
    if not minimum <= parsed <= maximum:
        raise _timing_error(
            "out_of_range",
            field,
            f"{field} must be between {minimum} and {maximum}.",
            minimum=minimum,
            maximum=maximum,
            actual=parsed,
        )
    return parsed


def _parse_time(value: Any, field: str) -> tuple[str, int]:
    normalized = value.translate(_DIGIT_TRANSLATION) if isinstance(value, str) else value
    if not isinstance(normalized, str) or not re.fullmatch(
        r"(?:[01]\d|2[0-3]):[0-5]\d", normalized
    ):
        raise _timing_error(
            "invalid_time_format", field, f"{field} must use local HH:mm format."
        )
    if normalized == "00:00":
        raise _timing_error(
            "midnight_not_allowed",
            field,
            "School-day times cannot be midnight or cross midnight.",
        )
    hours, minutes = (int(part) for part in normalized.split(":"))
    return normalized, hours * 60 + minutes


def _current_timing_profile(settings: Optional[dict], custom: Optional[dict] = None) -> dict:
    """Project the effective canonical columns into the seasonal wire contract."""
    settings = settings or {}
    custom = custom if custom is not None else (settings.get("custom_settings") or {})
    periods = _resolve_canonical_value(settings, "periods_per_day", 7)
    raw_break_after = custom.get(
        "breakAfterPeriod", custom.get("break_after_period", 3)
    )
    try:
        break_after = min(max(int(raw_break_after), 1), max(int(periods), 1))
    except (TypeError, ValueError):
        break_after = min(3, max(int(periods), 1))
    return {
        "dayStart": _resolve_canonical_value(settings, "start_time", "07:00"),
        "dayEnd": _resolve_canonical_value(settings, "end_time", "14:00"),
        "periodsPerDay": periods,
        "periodDuration": _resolve_canonical_value(settings, "period_duration", 45),
        "breakDuration": _resolve_canonical_value(settings, "break_duration", 15),
        "breakAfterPeriod": break_after,
        "breaks": _resolve_breaks(settings),
    }


def _normalize_timing_profile(
    value: Any, base: dict, field: str, *, canonical_errors: bool = False
) -> dict:
    """Validate and complete one allowlisted profile without leaking metadata."""
    canonical_fields = {
        "dayStart": "start_time",
        "dayEnd": "end_time",
        "periodsPerDay": "periods_per_day",
        "periodDuration": "period_duration",
        "breakDuration": "break_duration",
        "breakAfterPeriod": "breakAfterPeriod",
        "breaks": "breaks",
    }

    def error_field(name: str) -> str:
        return canonical_fields[name] if canonical_errors else f"{field}.{name}"

    if not isinstance(value, dict):
        raise _timing_error(
            "invalid_timing_profile", field, f"{field} must be an object."
        )
    unknown = set(value) - _TIMING_PROFILE_FIELDS
    if unknown:
        invalid = sorted(unknown)[0]
        raise _timing_error(
            "invalid_timing_profile_field",
            f"{field}.{invalid}",
            f"{field} contains an unsupported field.",
        )

    merged = {key: value.get(key, base.get(key)) for key in _TIMING_PROFILE_FIELDS}
    merged["periodsPerDay"] = _parse_int(
        merged["periodsPerDay"], error_field("periodsPerDay"), 1, 12
    )
    merged["periodDuration"] = _parse_int(
        merged["periodDuration"], error_field("periodDuration"), 20, 90
    )
    merged["breakDuration"] = _parse_int(
        merged["breakDuration"], error_field("breakDuration"), 0, 60
    )
    if (
        "breakAfterPeriod" not in value
        and merged["breakAfterPeriod"] > merged["periodsPerDay"]
    ):
        merged["breakAfterPeriod"] = merged["periodsPerDay"]
    merged["breakAfterPeriod"] = _parse_int(
        merged["breakAfterPeriod"],
        error_field("breakAfterPeriod"),
        1,
        merged["periodsPerDay"],
    )
    merged["dayStart"], start_minutes = _parse_time(
        merged["dayStart"], error_field("dayStart")
    )
    merged["dayEnd"], end_minutes = _parse_time(
        merged["dayEnd"], error_field("dayEnd")
    )
    if end_minutes <= start_minutes:
        raise _timing_error(
            "invalid_time_order",
            error_field("dayEnd"),
            "dayEnd must be after dayStart; overnight school days are not supported.",
        )

    breaks = merged.get("breaks")
    if breaks is None:
        breaks = []
    if not isinstance(breaks, list):
        raise _timing_error(
            "invalid_breaks", error_field("breaks"), f"{field}.breaks must be a list."
        )
    normalized_breaks = []
    seen_after = set()
    break_minutes = 0
    for index, raw_item in enumerate(breaks):
        item_field = (
            f"breaks[{index}]" if canonical_errors
            else f"{field}.breaks[{index}]"
        )
        if not isinstance(raw_item, dict):
            raise _timing_error(
                "invalid_break", item_field, f"{item_field} must be an object."
            )
        item = dict(raw_item)
        day = item.get("day")
        if day not in (None, "", "all"):
            raise _timing_error(
                "unsupported_break_day",
                f"{item_field}.day",
                "Day-specific breaks are not supported by shared time slots.",
                day=str(day),
            )
        raw_after = item.get("afterPeriod", item.get("after_period"))
        if raw_after is None:
            raise _timing_error(
                "missing_break_position",
                f"{item_field}.afterPeriod",
                f"{item_field}.afterPeriod is required.",
            )
        after = _parse_int(
            raw_after, f"{item_field}.afterPeriod", 1, merged["periodsPerDay"]
        )
        if after in seen_after:
            raise _timing_error(
                "duplicate_break_position",
                f"{item_field}.afterPeriod",
                "Only one break is allowed after each period.",
                after_period=after,
            )
        seen_after.add(after)
        raw_duration = item.get("duration")
        duration = merged["breakDuration"] if raw_duration is None else _parse_int(
            raw_duration, f"{item_field}.duration", 0, 180
        )
        item["afterPeriod"] = after
        item["duration"] = None if raw_duration is None else duration
        normalized_breaks.append(item)
        break_minutes += duration
    merged["breaks"] = normalized_breaks

    available_minutes = end_minutes - start_minutes
    lesson_minutes = merged["periodsPerDay"] * merged["periodDuration"]
    required_minutes = lesson_minutes + break_minutes
    if required_minutes > available_minutes:
        raise _timing_error(
            "school_day_too_short",
            error_field("dayEnd"),
            "School day is too short for the configured lessons and breaks.",
            available_minutes=available_minutes,
            lesson_minutes=lesson_minutes,
            break_minutes=break_minutes,
            required_minutes=required_minutes,
            shortage_minutes=required_minutes - available_minutes,
        )
    return merged


def _normalize_working_days(value: Any) -> dict:
    if isinstance(value, dict):
        invalid = set(value) - set(_DAY_MAP)
        if invalid:
            raise _timing_error(
                "invalid_weekday",
                "working_days",
                "working_days contains an invalid weekday.",
                weekday=sorted(invalid)[0],
            )
        if any(type(active) is not bool for active in value.values()):
            raise _timing_error(
                "invalid_weekday_value",
                "working_days",
                "Each working_days value must be boolean.",
            )
        result = {day: value.get(day, False) for day in _DAY_MAP}
    elif isinstance(value, list):
        if not value:
            raise _timing_error(
                "no_working_days",
                "working_days",
                "At least one working day is required.",
            )
        resolved = []
        for day in value:
            key = day if day in _DAY_MAP else _AR_TO_DAY.get(day)
            if not key:
                raise _timing_error(
                    "invalid_weekday",
                    "working_days",
                    "working_days contains an invalid weekday.",
                    weekday=str(day),
                )
            if key in resolved:
                raise _timing_error(
                    "duplicate_weekday",
                    "working_days",
                    "working_days cannot contain duplicate weekdays.",
                    weekday=key,
                )
            resolved.append(key)
        result = {day: day in resolved for day in _DAY_MAP}
    else:
        raise _timing_error(
            "invalid_working_days",
            "working_days",
            "working_days must be an object or list.",
        )
    if not any(result.values()):
        raise _timing_error(
            "no_working_days",
            "working_days",
            "At least one working day is required.",
        )
    return result


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
            # Display-only projection of the authoritative lifecycle column.
            # Never infer activation from missing/legacy values, setup, or users.
            # "unknown" is a response sentinel, not a persisted lifecycle state.
            "status": (
                school["status"]
                if school.get("status") in {status.value for status in SchoolStatus}
                else "unknown"
            ),
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
        # ``""`` is an intentional clear operation, not a missing alias.
        resolved_phone = (
            school_info.principal_mobile
            if school_info.principal_mobile is not None
            else school_info.principal_phone
        )
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

        # Use the same resolver as partial-update validation, so a legacy-only
        # row cannot display one value and validate/regenerate with another.
        start_t = _resolve_canonical_value(
            settings, "start_time",
            (default_settings or {}).get("school_day_start"),
        )
        if start_t is None:
            start_t = (default_settings or {}).get("start_time") or "07:00"
        end_t = _resolve_canonical_value(
            settings, "end_time",
            (default_settings or {}).get("school_day_end"),
        )
        if end_t is None:
            end_t = (default_settings or {}).get("end_time") or "14:00"

        timing = settings.get("timing") or nested_settings.get("timing") or {}
        if not timing:
            timing = {"start": start_t, "end": end_t}
        else:
            if "start" not in timing:
                timing["start"] = start_t
            if "end" not in timing:
                timing["end"] = end_t

        breaks = _resolve_breaks(settings)
        if not _has_breaks_setting(settings):
            breaks = (default_settings or {}).get("breaks") or []

        periods_pd = _resolve_canonical_value(
            settings, "periods_per_day",
            (default_settings or {}).get("periods_per_day"),
        )
        if periods_pd is None:
            periods_pd = 7

        period_dur = _resolve_canonical_value(
            settings, "period_duration",
            (default_settings or {}).get("period_duration_minutes"),
        )
        if period_dur is None:
            period_dur = 45

        break_dur = _resolve_canonical_value(
            settings, "break_duration",
            (default_settings or {}).get("break_duration_minutes"),
        )
        if break_dur is None:
            break_dur = 15

        prayer_dur = _pick(
            cs.get("prayer_duration_minutes"),
            settings.get("prayer_duration_minutes"),
            nested_settings.get("prayer_duration_minutes"),
            (default_settings or {}).get("prayer_duration_minutes"),
            default=20
        )

        working_days = _resolve_canonical_value(settings, "working_days")
        if not isinstance(working_days, dict):
            try:
                working_days = _normalize_working_days(working_days)
            except HTTPException:
                working_days = {day: day not in {"friday", "saturday"} for day in _DAY_MAP}
        working_days_ar = [
            arabic for day, arabic in _DAY_MAP.items() if working_days.get(day)
        ]
        settings_version = cs.get("settings_version", 0)
        if not isinstance(settings_version, int) or isinstance(settings_version, bool):
            settings_version = 0
        attendance_pattern = cs.get(
            "attendancePattern", cs.get("attendance_pattern", "winter")
        )
        if attendance_pattern not in _TIMING_PROFILE_NAMES:
            attendance_pattern = "winter"
        active_profile = {
            "dayStart": start_t,
            "dayEnd": end_t,
            "periodsPerDay": periods_pd,
            "periodDuration": period_dur,
            "breakDuration": break_dur,
            "breakAfterPeriod": cs.get(
                "breakAfterPeriod", cs.get("break_after_period", 3)
            ),
            "breaks": breaks,
        }
        timing_profiles = {}
        stored_profiles = cs.get("timingProfiles")
        if isinstance(stored_profiles, dict):
            for name, profile in stored_profiles.items():
                if name in _TIMING_PROFILE_NAMES and isinstance(profile, dict):
                    timing_profiles[name] = {
                        **active_profile,
                        **{
                            key: profile[key]
                            for key in _TIMING_PROFILE_FIELDS
                            if key in profile
                        },
                    }
        # Canonical columns remain authoritative for the selected profile.
        timing_profiles[attendance_pattern] = active_profile
        response_cs = dict(cs)
        response_cs["attendancePattern"] = attendance_pattern
        response_cs.pop("attendance_pattern", None)
        response_cs["timingProfiles"] = timing_profiles

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
            "working_days": working_days,
            "working_days_ar": working_days_ar,
            "weekend_days_ar": [
                arabic for day, arabic in _DAY_MAP.items() if not working_days.get(day)
            ],
            "settings_version": settings_version,
            # Current principal UI aliases.  They are projections of the
            # canonical values above, not separately persisted values.
            "dayStart": start_t,
            "dayEnd": end_t,
            "periodsPerDay": periods_pd,
            "periodDuration": period_dur,
            "breakDuration": break_dur,
            "workingDays": working_days_ar,
            "academicYear": cs.get("academicYear", cs.get("academic_year", "1446")),
            "currentSemester": cs.get("currentSemester", cs.get("current_semester", "1")),
            "breakAfterPeriod": cs.get("breakAfterPeriod", cs.get("break_after_period", 3)),
            "attendancePattern": attendance_pattern,
            "timingProfiles": timing_profiles,
            "maxStandbyPerWeek": cs.get("maxStandbyPerWeek", cs.get("max_standby_per_week", 5)),
            "custom_settings": response_cs,
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
        return await SchoolSettingsService.update_school_settings_full(
            session, {"working_days": config.dict()}, current_user, x_school_context
        )

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
        return await SchoolSettingsService.update_school_settings_full(
            session, {"periods_per_day": req.periods_per_day}, current_user, x_school_context
        )

    @staticmethod
    async def update_school_timing(session, timing: SchoolTiming, current_user: dict, x_school_context: str = None) -> dict:
        return await SchoolSettingsService.update_school_settings_full(
            session,
            {"start_time": timing.start, "end_time": timing.end},
            current_user,
            x_school_context,
        )

    @staticmethod
    async def update_breaks(session, breaks: List[BreakPeriod], current_user: dict, x_school_context: str = None) -> dict:
        return await SchoolSettingsService.update_school_settings_full(
            session,
            {"breaks": [b.dict() for b in breaks]},
            current_user,
            x_school_context,
        )

    @staticmethod
    async def update_school_settings_full(session, new_settings: dict, current_user: dict, x_school_context: str = None) -> dict:
        school_id = await resolve_school_context(current_user, x_school_context)
        if not school_id:
            raise HTTPException(status_code=400, detail="Missing school context")
        if not isinstance(new_settings, dict):
            raise HTTPException(status_code=422, detail="Settings payload must be an object")

        payload = dict(new_settings)
        expected_version = payload.pop("expected_version", payload.pop("expectedVersion", None))
        payload.pop("settings_version", None)

        # This is the same transaction lock used by draft ensure/publish/
        # unpublish, so a settings edit cannot race a lifecycle transition.
        await session.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:lock_key))"),
            {"lock_key": f"sched_draft_ensure:{school_id}"},
        )

        existing = await gd_find_one(session, "school_settings", {"school_id": school_id})
        cs = dict(existing.get("custom_settings") or {}) if existing else {}
        current_version = cs.get("settings_version", 0)
        if not isinstance(current_version, int) or isinstance(current_version, bool):
            current_version = 0
        if expected_version is not None:
            expected_version = _parse_int(expected_version, "expected_version", 0, 2_147_483_647)
            if expected_version != current_version:
                raise HTTPException(
                    status_code=409,
                    detail={
                        "code": "settings_version_conflict",
                        "message": "Settings changed in another session; reload and try again.",
                        "settings_version": current_version,
                    },
                )
        # Omission remains supported only for legacy API clients.  The current
        # settings UI always echoes GET.settings_version as expected_version;
        # all writes, including legacy ones, still serialize on the school
        # advisory lock and advance the version.

        current_pattern = cs.get(
            "attendancePattern", cs.get("attendance_pattern", "winter")
        )
        if current_pattern not in _TIMING_PROFILE_NAMES:
            current_pattern = "winter"
        requested_pattern = payload.pop(
            "attendancePattern", payload.pop("attendance_pattern", current_pattern)
        )
        if requested_pattern not in _TIMING_PROFILE_NAMES:
            raise _timing_error(
                "invalid_timing_profile",
                "attendancePattern",
                "attendancePattern must be summer, winter, or ramadan.",
            )
        pattern_changed = requested_pattern != current_pattern

        breaks_were_explicit = _has_breaks_setting(existing)
        flat_breaks_supplied = "breaks" in payload
        supplied_profiles = payload.pop("timingProfiles", None)
        if supplied_profiles is not None and not isinstance(supplied_profiles, dict):
            raise _timing_error(
                "invalid_timing_profiles",
                "timingProfiles",
                "timingProfiles must be an object.",
            )
        supplied_profiles = supplied_profiles or {}
        unknown_profile_names = set(supplied_profiles) - _TIMING_PROFILE_NAMES
        if unknown_profile_names:
            invalid = sorted(unknown_profile_names)[0]
            raise _timing_error(
                "invalid_timing_profile",
                f"timingProfiles.{invalid}",
                "Unknown timing profile; expected summer, winter, or ramadan.",
            )

        current_profile = _normalize_timing_profile(
            _current_timing_profile(existing, cs),
            _current_timing_profile(existing, cs),
            f"timingProfiles.{current_pattern}",
        )
        raw_stored_profiles = cs.get("timingProfiles")
        stored_profiles = {}
        if isinstance(raw_stored_profiles, dict):
            for profile_name, raw_profile in raw_stored_profiles.items():
                if profile_name in _TIMING_PROFILE_NAMES and isinstance(raw_profile, dict):
                    stored_profiles[profile_name] = {
                        key: value
                        for key, value in raw_profile.items()
                        if key in _TIMING_PROFILE_FIELDS
                    }
        # Always snapshot the outgoing canonical timings before resolving the
        # selected season. This is what makes switching away and back lossless.
        stored_profiles[current_pattern] = current_profile

        for profile_name, raw_profile in supplied_profiles.items():
            stored_base = stored_profiles.get(profile_name)
            if isinstance(stored_base, dict):
                stored_base = {
                    key: value
                    for key, value in stored_base.items()
                    if key in _TIMING_PROFILE_FIELDS
                }
                stored_base = {**current_profile, **stored_base}
            else:
                stored_base = current_profile
            stored_profiles[profile_name] = _normalize_timing_profile(
                raw_profile,
                stored_base,
                f"timingProfiles.{profile_name}",
            )

        selected_base = stored_profiles.get(requested_pattern)
        if isinstance(selected_base, dict):
            selected_base = {
                key: value
                for key, value in selected_base.items()
                if key in _TIMING_PROFILE_FIELDS
            }
            selected_base = {**current_profile, **selected_base}
        else:
            # A never-edited target inherits the school's current timings.
            # Seasonal defaults would silently invent operating hours.
            selected_base = current_profile
        flat_profile_overrides = {}
        profile_aliases = {
            "dayStart": _CANONICAL_ALIASES["start_time"],
            "dayEnd": _CANONICAL_ALIASES["end_time"],
            "periodsPerDay": _CANONICAL_ALIASES["periods_per_day"],
            "periodDuration": _CANONICAL_ALIASES["period_duration"],
            "breakDuration": _CANONICAL_ALIASES["break_duration"],
        }
        for profile_field, aliases in profile_aliases.items():
            if any(alias in payload for alias in aliases):
                flat_profile_overrides[profile_field] = _first_present(payload, aliases)
        if "breakAfterPeriod" in payload:
            flat_profile_overrides["breakAfterPeriod"] = payload["breakAfterPeriod"]
        elif "break_after_period" in payload:
            flat_profile_overrides["breakAfterPeriod"] = payload["break_after_period"]
        if "breaks" in payload:
            flat_profile_overrides["breaks"] = payload["breaks"]
        selected_profile = _normalize_timing_profile(
            flat_profile_overrides,
            selected_base,
            f"timingProfiles.{requested_pattern}",
            canonical_errors=True,
        )
        stored_profiles[requested_pattern] = selected_profile
        selected_profile_breaks_supplied = (
            isinstance(supplied_profiles.get(requested_pattern), dict)
            and "breaks" in supplied_profiles[requested_pattern]
        )
        materialize_selected_breaks = (
            breaks_were_explicit
            or flat_breaks_supplied
            or selected_profile_breaks_supplied
            or (
                pattern_changed
                and isinstance(raw_stored_profiles, dict)
                and requested_pattern in raw_stored_profiles
            )
        )
        legacy_break_position_changed = (
            not breaks_were_explicit
            and current_profile["breakAfterPeriod"]
            != selected_profile["breakAfterPeriod"]
        )

        # Hydrate canonical columns from the selected profile. Explicit flat
        # fields have already won above, preserving the legacy PUT contract.
        payload.update({
            "dayStart": selected_profile["dayStart"],
            "dayEnd": selected_profile["dayEnd"],
            "periodsPerDay": selected_profile["periodsPerDay"],
            "periodDuration": selected_profile["periodDuration"],
            "breakDuration": selected_profile["breakDuration"],
            "breakAfterPeriod": selected_profile["breakAfterPeriod"],
        })
        if materialize_selected_breaks:
            payload["breaks"] = selected_profile["breaks"]

        canonical_updates = {}
        for canonical, aliases in _CANONICAL_ALIASES.items():
            if any(alias in payload for alias in aliases):
                canonical_updates[canonical] = _first_present(payload, aliases)
            elif existing and existing.get(canonical) is None:
                # A partial edit of a legacy-only row must not erase the old
                # camel/nested value when duplicate aliases are cleaned from
                # custom_settings.  Promote it into its canonical column in
                # the same transaction.
                legacy_value = _resolve_canonical_value(existing, canonical)
                if legacy_value is not None:
                    canonical_updates[canonical] = legacy_value

        if "periods_per_day" in canonical_updates:
            canonical_updates["periods_per_day"] = _parse_int(
                canonical_updates["periods_per_day"], "periods_per_day", 1, 12
            )
        if "period_duration" in canonical_updates:
            canonical_updates["period_duration"] = _parse_int(
                canonical_updates["period_duration"], "period_duration", 20, 90
            )
        if "break_duration" in canonical_updates:
            canonical_updates["break_duration"] = _parse_int(
                canonical_updates["break_duration"], "break_duration", 0, 60
            )
        if "working_days" in canonical_updates:
            canonical_updates["working_days"] = _normalize_working_days(
                canonical_updates["working_days"]
            )
        for field in ("start_time", "end_time"):
            if field in canonical_updates:
                canonical_updates[field] = _parse_time(
                    canonical_updates[field], field
                )[0]

        periods = _parse_int(
            canonical_updates.get(
                "periods_per_day",
                _resolve_canonical_value(existing, "periods_per_day", 7),
            ),
            "periods_per_day",
            1,
            12,
        )
        period_duration = _parse_int(
            canonical_updates.get(
                "period_duration",
                _resolve_canonical_value(existing, "period_duration", 45),
            ),
            "period_duration",
            20,
            90,
        )
        break_duration = _parse_int(
            canonical_updates.get(
                "break_duration",
                _resolve_canonical_value(existing, "break_duration", 15),
            ),
            "break_duration",
            0,
            60,
        )
        start_time = canonical_updates.get(
            "start_time", _resolve_canonical_value(existing, "start_time", "07:00")
        )
        end_time = canonical_updates.get(
            "end_time", _resolve_canonical_value(existing, "end_time", "14:00")
        )
        _, start_minutes = _parse_time(start_time, "start_time")
        _, end_minutes = _parse_time(end_time, "end_time")
        if end_minutes <= start_minutes:
            raise _timing_error(
                "invalid_time_order",
                "end_time",
                "end_time must be after start_time; overnight school days are not supported.",
                start_minutes=start_minutes,
                end_minutes=end_minutes,
            )

        breaks = payload.get("breaks", _resolve_breaks(existing))
        if breaks is None:
            breaks = []
        if not isinstance(breaks, list):
            raise _timing_error(
                "invalid_breaks", "breaks", "breaks must be a list."
            )
        normalized_breaks = []
        break_minutes = 0
        seen_after = set()
        for index, item in enumerate(breaks):
            if not isinstance(item, dict):
                raise _timing_error(
                    "invalid_break",
                    f"breaks[{index}]",
                    f"breaks[{index}] must be an object.",
                )
            item = dict(item)
            day = item.get("day")
            if day not in (None, "", "all"):
                raise _timing_error(
                    "unsupported_break_day",
                    f"breaks[{index}].day",
                    "Day-specific breaks are not supported by shared time slots.",
                    day=str(day),
                )
            raw_after = item.get("afterPeriod", item.get("after_period"))
            if raw_after is None:
                raise _timing_error(
                    "missing_break_position",
                    f"breaks[{index}].afterPeriod",
                    f"breaks[{index}].afterPeriod is required.",
                )
            after = _parse_int(raw_after, f"breaks[{index}].afterPeriod", 1, periods)
            if after in seen_after:
                raise _timing_error(
                    "duplicate_break_position",
                    f"breaks[{index}].afterPeriod",
                    "Only one break is allowed after each period.",
                    after_period=after,
                )
            seen_after.add(after)
            raw_duration = item.get("duration")
            # A null duration means BASE break duration.  Use ``is None``
            # rather than truthiness so a deliberate zero-minute break works.
            duration = break_duration if raw_duration is None else _parse_int(
                raw_duration, f"breaks[{index}].duration", 0, 180
            )
            item["afterPeriod"] = after
            # Preserve null as "inherit BASE break duration".  Persisting the
            # currently resolved number would freeze the break at that value,
            # so a later BASE 25 -> 30 edit would incorrectly keep 25.
            item["duration"] = None if raw_duration is None else duration
            normalized_breaks.append(item)
            break_minutes += duration

        if "breaks" in payload:
            payload["breaks"] = normalized_breaks

        lesson_minutes = periods * period_duration
        required_minutes = lesson_minutes + break_minutes
        available_minutes = end_minutes - start_minutes
        if required_minutes > available_minutes:
            raise _timing_error(
                "school_day_too_short",
                "end_time",
                "School day is too short for the configured lessons and breaks.",
                available_minutes=available_minutes,
                lesson_minutes=lesson_minutes,
                break_minutes=break_minutes,
                required_minutes=required_minutes,
                shortage_minutes=required_minutes - available_minutes,
            )

        timing_fields = {
            "start_time", "end_time", "periods_per_day",
            "period_duration", "break_duration", "working_days",
        }
        timing_changed = pattern_changed or legacy_break_position_changed or any(
            _resolve_canonical_value(existing, field) != value
            for field, value in canonical_updates.items()
            if field in timing_fields
        ) or ("breaks" in payload and normalized_breaks != _resolve_breaks(existing))

        if timing_changed:
            published = (
                await gd_find_one(session, "timetables", {
                    "school_id": school_id, "status": "published",
                })
                or await gd_find_one(session, "timetables", {
                    "school_id": school_id, "is_published": True,
                })
            )
            if published:
                raise HTTPException(
                    status_code=409,
                    detail={
                        "code": "published_timetable_requires_unpublish",
                        "message": (
                            "Unpublish the current timetable before changing timing settings. "
                            "The published timetable was not modified."
                        ),
                    },
                )

        now = datetime.now(timezone.utc).isoformat()
        extras = {
            key: value for key, value in payload.items()
            if key not in _ALL_CANONICAL_INPUT_KEYS
        }
        if "breaks" in payload:
            extras["breaks"] = normalized_breaks
        clean_cs = {
            key: value for key, value in cs.items()
            if key not in _ALL_CANONICAL_INPUT_KEYS
        }
        clean_cs.update(extras)
        clean_cs["attendancePattern"] = requested_pattern
        clean_cs.pop("attendance_pattern", None)
        clean_cs["timingProfiles"] = stored_profiles
        clean_cs["settings_version"] = current_version + 1
        normalized = normalize_school_settings_doc({
            **canonical_updates,
            "custom_settings": clean_cs,
            "school_id": school_id,
            "updated_at": now,
        })

        try:
            async with session.begin_nested():
                if existing:
                    await gd_update_one(
                        session, "school_settings", {"school_id": school_id}, normalized
                    )
                else:
                    normalized["id"] = f"settings-{school_id}"
                    normalized["created_at"] = now
                    await gd_insert(session, "school_settings", normalized)

                regeneration = {"regenerated": False, "reason": "timing_unchanged"}
                reconciliation = {
                    "remapped_sessions": 0,
                    "archived_drafts": 0,
                    "excluded_sessions": 0,
                    "editable_draft_id": None,
                }
                cancelled_generation_runs = 0
                if timing_changed:
                    from services.timetable_generation_fence import (
                        cancel_active_generation_runs,
                    )
                    from src.modules.schools.services.time_slots_service import TimeSlotsService
                    cancelled_generation_runs = await cancel_active_generation_runs(
                        session, school_id
                    )
                    regeneration = await TimeSlotsService.regenerate_time_slots(session, school_id)
                    reconciliation = regeneration["draft_reconciliation"]

                await audit_engine.log_data_change(
                    action=AuditAction.TENANT_UPDATED.value,
                    performed_by=current_user.get("id", current_user.get("user_id")),
                    entity_type="school_settings",
                    entity_id=school_id,
                    tenant_id=school_id,
                    new_values={
                        "action": "UPDATE_SETTINGS_AND_RECONCILE_DRAFT",
                        "settings_version": current_version + 1,
                        "draft_reconciliation": reconciliation,
                        "cancelled_generation_runs": cancelled_generation_runs,
                    },
                )
                saved = await SchoolSettingsService.get_school_settings(
                    session, current_user, x_school_context
                )
            await session.commit()
        except HTTPException:
            raise
        except Exception:
            logger.exception("Failed to persist settings for school %s", school_id)
            raise HTTPException(status_code=500, detail="Settings were not saved")

        return {
            "success": True,
            "message": "تم تحديث إعدادات المدرسة بالكامل بنجاح",
            "settings": saved,
            "time_slots_regenerated": regeneration,
            "draft_reconciliation": reconciliation,
            "cancelled_generation_runs": cancelled_generation_runs,
        }
