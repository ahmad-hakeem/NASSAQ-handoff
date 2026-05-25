"""
NASSAQ Route Module: School settings, work days, holidays, timing, breaks, constraints, teacher-class assignments
Auto-consolidated during Phase 8 modularization.
"""
from fastapi import APIRouter, HTTPException, Depends, status, Header, Query, Body, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import Response
from starlette.responses import StreamingResponse
from pydantic import BaseModel, Field, ConfigDict, EmailStr, model_validator, field_validator
from typing import List, Optional, Any, Dict
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

DEFAULT_SCHOOL_TZ = "Asia/Riyadh"

import uuid, os, logging, json, random, re, io, base64
from engines.sql_utils import gd_find, gd_find_one, gd_insert, gd_insert_many, gd_update_one, gd_update_many, gd_count, gd_delete_one, gd_delete_many, gd_distinct, gd_upsert, _gd_aggregate
from dependencies import (
    db, get_current_user, require_roles, UserRole, SchoolStatus,
    hash_password, verify_password, create_access_token,
    JWT_SECRET, JWT_ALGORITHM, ACCESS_TOKEN_EXPIRE, security, logger,
    audit_engine, AuditAction, AuditSeverity,
    smart_scheduling_engine, TimetableRunStatus, TimetableStatus,
    ConflictType, ConflictSeverity, PreValidationResult, GenerationResult,
    hakim_engine, reporting_engine, export_engine, session_engine,
    REPORT_TYPES, generate_student_qr_code
)

router = APIRouter()


async def regenerate_time_slots_from_settings(school_id: str):
    """
    Regenerate the time_slots collection from current school_settings.
    Reads dayStart, periodsPerDay, periodDuration, breaks from school_settings
    and rebuilds all time slots with proper breaks/prayer inserted.
    """
    settings = await gd_find_one(db.session, "school_settings", {"school_id": school_id})
    if not settings:
        return {"regenerated": False, "reason": "no_settings"}

    timing = settings.get("timing", {})
    cs = settings.get("custom_settings") or {}
    nested = settings.get("settings", {}) or {}
    day_start = (cs.get("school_day_start")
                 or settings.get("school_day_start")
                 or nested.get("school_day_start")
                 or settings.get("start_time")
                 or timing.get("start")
                 or "07:00")
    try:
        parts = day_start.split(":")
        if len(parts) != 2 or not (0 <= int(parts[0]) <= 23 and 0 <= int(parts[1]) <= 59):
            day_start = "07:00"
    except (ValueError, AttributeError):
        day_start = "07:00"

    periods = min(max(int(cs.get("periods_per_day") or settings.get("periods_per_day") or nested.get("periods_per_day") or 7), 1), 12)
    period_dur = min(max(int(cs.get("period_duration_minutes") or settings.get("period_duration_minutes") or nested.get("period_duration_minutes") or settings.get("period_duration") or 45), 20), 90)
    break_dur = min(max(int(cs.get("break_duration_minutes") or settings.get("break_duration_minutes") or nested.get("break_duration_minutes") or settings.get("break_duration") or 15), 5), 60)
    prayer_dur = min(max(int(cs.get("prayer_duration_minutes") or settings.get("prayer_duration_minutes") or nested.get("prayer_duration_minutes") or 20), 5), 60)

    saved_breaks = settings.get("breaks") or []
    break_after_map = {}
    for b in saved_breaks:
        after = b.get("afterPeriod") or b.get("after_period")
        if after:
            break_after_map[int(after)] = {
                "name": b.get("name", "استراحة"),
                "name_en": b.get("name_en", "Break"),
                "duration": int(b.get("duration", break_dur)),
                "is_prayer": b.get("type") == "prayer" or "صلا" in (b.get("name") or ""),
            }

    if not break_after_map:
        if periods >= 3:
            break_after_map[3] = {"name": "الاستراحة", "name_en": "Break", "duration": break_dur, "is_prayer": False}
        if periods >= 6:
            break_after_map[6] = {"name": "الصلاة", "name_en": "Prayer", "duration": prayer_dur, "is_prayer": True}

    passing_time = 5
    h, m = map(int, day_start.split(":"))
    current_minutes = h * 60 + m
    slots = []
    slot_number = 0
    period_count = 0

    for i in range(1, periods + 1):
        if i in break_after_map and i > 1:
            pass

        slot_number += 1
        period_count += 1
        start_h, start_m = divmod(current_minutes, 60)
        end_minutes = current_minutes + period_dur
        end_h, end_m = divmod(end_minutes, 60)
        slots.append({
            "id": str(uuid.uuid4()),
            "school_id": school_id,
            "name": f"الحصة {_arabic_ordinal(period_count)}",
            "name_en": f"Period {period_count}",
            "start_time": f"{start_h:02d}:{start_m:02d}",
            "end_time": f"{end_h:02d}:{end_m:02d}",
            "slot_number": slot_number,
            "period_number": period_count,
            "duration_minutes": period_dur,
            "type": "class",
            "is_break": False,
            "is_prayer": False,
            "is_active": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })
        current_minutes = end_minutes

        brk = break_after_map.get(i)
        if brk:
            slot_number += 1
            bs_h, bs_m = divmod(current_minutes, 60)
            be_minutes = current_minutes + brk["duration"]
            be_h, be_m = divmod(be_minutes, 60)
            slots.append({
                "id": str(uuid.uuid4()),
                "school_id": school_id,
                "name": brk["name"],
                "name_en": brk["name_en"],
                "start_time": f"{bs_h:02d}:{bs_m:02d}",
                "end_time": f"{be_h:02d}:{be_m:02d}",
                "slot_number": slot_number,
                "period_number": None,
                "duration_minutes": brk["duration"],
                "type": "prayer" if brk["is_prayer"] else "break",
                "is_break": True,
                "is_prayer": brk["is_prayer"],
                "is_active": True,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            })
            current_minutes = be_minutes
        else:
            current_minutes += passing_time

    await gd_delete_many(db.session, "time_slots", {"school_id": school_id})
    if slots:
        await gd_insert_many(db.session, "time_slots", slots)

    final_h, final_m = divmod(current_minutes, 60)
    day_end = f"{final_h:02d}:{final_m:02d}"
    await gd_update_one(db.session, "school_settings", {"school_id": school_id}, {
            "school_day_end": day_end,
            "settings.school_day_end": day_end,
        })

    return {"regenerated": True, "count": len(slots), "day_end": day_end}


def normalize_school_settings_doc(raw: dict) -> dict:
    """Translate a settings dict that may use new-style names (school_day_start,
    period_duration_minutes, break_duration_minutes, school_day_end, plus extras
    like prayer_duration_minutes, time_slots, working_days_ar/en, weekend_days_ar/en)
    into a doc that matches the SchoolSettings ORM columns (start_time, end_time,
    period_duration, break_duration, periods_per_day, working_days), with all
    extra keys merged into the `custom_settings` JSONB column. Use this before
    inserting/updating school_settings to avoid silent column-drop bugs."""
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


def _arabic_ordinal(n):
    ordinals = {1: "الأولى", 2: "الثانية", 3: "الثالثة", 4: "الرابعة", 5: "الخامسة", 6: "السادسة", 7: "السابعة", 8: "الثامنة", 9: "التاسعة", 10: "العاشرة", 11: "الحادية عشرة", 12: "الثانية عشرة"}
    return ordinals.get(n, str(n))


class SchoolInfoUpdate(BaseModel):
    name: Optional[str] = None
    name_ar: Optional[str] = None
    name_en: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    city: Optional[str] = None
    region: Optional[str] = None
    address: Optional[str] = None
    type: Optional[str] = None
    stage: Optional[str] = None
    principal_name: Optional[str] = None
    principal_mobile: Optional[str] = None
    educational_pathway: Optional[str] = None

    @field_validator("type", mode="before")
    @classmethod
    def _normalize_type(cls, v):
        # API exposes the column as ``type``; normalize the deprecated
        # "خاصة" alias (special / special_needs) to canonical "private"
        # at the API boundary so it never reaches the database.
        from utils.school_type import normalize_school_type
        return normalize_school_type(v)


class WorkDaysConfig(BaseModel):
    sunday: bool = True
    monday: bool = True
    tuesday: bool = True
    wednesday: bool = True
    thursday: bool = True
    friday: bool = False
    saturday: bool = False


class OfficialHoliday(BaseModel):
    name: str
    start_date: str
    end_date: Optional[str] = None


class ExceptionDay(BaseModel):
    date: str
    reason: str
    is_holiday: bool = True


class SchoolTiming(BaseModel):
    start: str = "07:00"
    end: str = "14:00"


class BreakPeriod(BaseModel):
    id: Optional[str] = None
    name: Optional[str] = None
    start: Optional[str] = None
    end: Optional[str] = None
    type: Optional[str] = None
    custom_type: Optional[str] = None
    duration: Optional[int] = None
    after_period: Optional[int] = None
    day: Optional[str] = None


class ActivityDay(BaseModel):
    date: str
    name: Optional[str] = None
    notes: Optional[str] = None


class TeachingLoadUpdate(BaseModel):
    teacher_id: str
    weekly_periods: int


class TeacherAvailability(BaseModel):
    teacher_id: str
    available_days: List[str] = []
    available_periods: Optional[List[int]] = None


class UnavailabilityCreate(BaseModel):
    entity_type: str
    entity_id: str
    entity_name: Optional[str] = None
    unavailability_type: str = "recurring"
    day: Optional[str] = None
    period: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    reason: Optional[str] = None
    # موقع بديل لطلاب الفصل عند تعطّله (مثلاً: المعمل / الساحة).
    # يخصّ سجلات الفصول فقط (entity_type == "class")؛ يتجاهَل لسجلات
    # المعلمين. اختياري — عند غيابه يبقى السلوك القديم بإرسال رسالة عامة.
    alternative_location: Optional[str] = None

    @model_validator(mode="after")
    def validate_unavailability_fields(self):
        if self.unavailability_type == "recurring":
            if not self.day or not self.period:
                raise ValueError("عدم التوفر المتكرر يتطلب تحديد اليوم والحصة")
        elif self.unavailability_type == "long_term":
            if not self.start_date or not self.end_date:
                raise ValueError("فترة عدم التوفر طويلة الأمد تتطلب تحديد تاريخ البداية والنهاية")
            if self.start_date > self.end_date:
                raise ValueError("تاريخ النهاية يجب أن يكون بعد تاريخ البداية")
        return self


class AdminConstraint(BaseModel):
    id: Optional[str] = None
    type: str
    teacher_id: Optional[str] = None
    day: Optional[str] = None
    period: Optional[int] = None
    description: Optional[str] = None


class EducationalStageCreate(BaseModel):
    name: str
    name_en: Optional[str] = None
    order: int = 1


class GradeCreate(BaseModel):
    name: str
    name_en: Optional[str] = None
    stage_id: Optional[str] = None


class SectionCreate(BaseModel):
    name: str
    grade_id: Optional[str] = None
    class_id: Optional[str] = None


class AcademicTermCreate(BaseModel):
    name: str
    name_en: Optional[str] = None
    start_date: str
    end_date: str
    is_active: bool = True


class SubjectCreateForSchool(BaseModel):
    name: str
    name_en: Optional[str] = None
    grade_id: Optional[str] = None
    weekly_periods: int = 4


class SchoolSettingsResponse(BaseModel):
    school_info: dict
    work_days: dict
    official_holidays: List[dict]
    exception_days: List[dict]
    periods_per_day: int
    timing: dict
    breaks: List[dict]
    activity_days: List[dict]
    teaching_loads: dict
    teacher_availability: dict
    constraints: List[dict]
    educational_stages: List[dict]
    grades: List[dict]
    sections: List[dict]
    academic_terms: List[dict]


class UpdatePeriodsRequest(BaseModel):
    periods_per_day: int


class TeacherClassAssignmentCreate(BaseModel):
    teacher_id: str
    class_id: str
    academic_year_id: Optional[str] = None


class TeacherClassAssignmentResponse(BaseModel):
    id: str
    teacher_id: str
    class_id: str
    school_id: str
    academic_year_id: Optional[str] = None
    teacher_name: Optional[str] = None
    class_name: Optional[str] = None
    created_at: Optional[str] = None


async def get_school_id_from_context(current_user: dict, x_school_context: str = None) -> str:
    """Resolve school_id from header, with strict tenant isolation.

    Delegates to `utils.tenant_scope.resolve_school_id` so that non-platform
    callers can never address another school's data via the X-School-Context
    header (mismatched override → 403).

    Platform admins may only use a cross-tenant override when their token
    carries is_impersonating=True (i.e., was minted by /role-switch/switch
    with MFA, reason capture, and an impersonation_sessions audit record).
    A plain platform-admin access token is rejected with 403 when an override
    is supplied.
    """
    from utils.tenant_scope import resolve_school_id
    return resolve_school_id(current_user, x_school_context)

@router.get("/school/info")
async def get_school_info(
    current_user: dict = Depends(get_current_user),
    x_school_context: str = Header(default=None, alias="X-School-Context")
):
    """Get school basic info - جلب معلومات المدرسة الأساسية"""
    school_id = await get_school_id_from_context(current_user, x_school_context)
    
    if not school_id:
        raise HTTPException(status_code=400, detail="School context required")
    
    school = await gd_find_one(db.session, "schools", {"id": school_id})
    if not school:
        return {}
    
    # Get school settings too
    settings = await gd_find_one(db.session, "school_settings", {"school_id": school_id})
    
    return {
        "id": school.get("id"),
        "name": school.get("name"),
        "name_ar": school.get("name_ar", school.get("name")),
        "school_name_ar": school.get("name_ar", school.get("name")),
        "name_en": school.get("name_en"),
        "type": school.get("school_type") or school.get("type"),
        "stage": school.get("stage"),
        "city": school.get("city"),
        "region": school.get("region"),
        "address": school.get("address"),
        "phone": school.get("phone"),
        "email": school.get("email"),
        "license_number": school.get("license_number"),
        "principal_name": school.get("principal_name"),
        "principal_mobile": school.get("principal_mobile"),
        "educational_pathway": school.get("educational_pathway"),
        "logo_url": school.get("logo_url"),
        "is_active": school.get("is_active", True),
        "updated_at": school.get("updated_at"),
        "settings": settings,
        "academicYear": settings.get("academic_year") if settings else None,
        "currentSemester": settings.get("current_semester") if settings else None,
        "workingDays": settings.get("working_days") if settings else None,
    }

@router.put("/school/info")
async def update_school_info_direct(
    data: SchoolInfoUpdate,
    current_user: dict = Depends(require_roles([
        UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN
    ])),
    x_school_context: str = Header(default=None, alias="X-School-Context")
):
    """Update school basic info - تحديث معلومات المدرسة الأساسية"""
    school_id = await get_school_id_from_context(current_user, x_school_context)
    if not school_id:
        raise HTTPException(status_code=400, detail="School context required")

    old_school = await gd_find_one(db.session, "schools", {"id": school_id})
    if not old_school:
        raise HTTPException(status_code=404, detail="المدرسة غير موجودة")

    update_data = {k: v for k, v in data.model_dump().items() if v is not None}
    update_data.pop("license_number", None)
    update_data.pop("id", None)
    if "principal_mobile" in update_data and not update_data["principal_mobile"].strip():
        raise HTTPException(status_code=422, detail="رقم جوال المدير مطلوب")
    if "stage" in update_data and update_data.get("stage") != "secondary_pathways":
        update_data["educational_pathway"] = None
    # The schools table column is `school_type`; the API exposes it as `type`.
    # Persist to both for backward compatibility so the value isn't dropped on save.
    if "type" in update_data:
        update_data["school_type"] = update_data["type"]
    if "name_ar" in update_data and "name" not in update_data:
        update_data["name"] = update_data["name_ar"]
    elif "name" in update_data and "name_ar" not in update_data:
        update_data["name_ar"] = update_data["name"]

    try:
        from services.translation_service import translate_fields, is_available
        if is_available():
            update_data = await translate_fields(update_data, ["name"])
    except Exception:
        pass

    update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
    await gd_update_one(db.session, "schools", {"id": school_id}, update_data)

    # Audit log
    await gd_insert(db.session, "audit_logs", {
        "id": str(uuid.uuid4()),
        "school_id": school_id,
        "action": "UPDATE",
        "entity_type": "school_basic_info",
        "entity_id": school_id,
        "old_data": {k: old_school.get(k) for k in update_data if k not in ["updated_at"]},
        "new_data": update_data,
        "performed_by": current_user.get("id"),
        "performed_by_email": current_user.get("email"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

    school = await gd_find_one(db.session, "schools", {"id": school_id})
    return {"success": True, "school": school, "message": "تم تحديث بيانات المدرسة بنجاح"}

@router.get("/school/day-status")
async def get_school_day_status(
    current_user: dict = Depends(get_current_user),
    x_school_context: str = Header(default=None, alias="X-School-Context")
):
    _neutral_payload = {
        "is_school_time": False,
        "is_working_day": False,
        "time_slots": [],
        "total_periods": 0,
        "current_period": 0,
        "progress": 0,
        "day_start": None,
        "day_end": None,
        "current_period_name": "",
        "is_break": False,
    }
    caller_role = (current_user or {}).get("role", "")
    caller_tenant = (current_user or {}).get("tenant_id") or (current_user or {}).get("school_id")
    if caller_role == "independent_teacher" or not caller_tenant:
        return _neutral_payload

    school_id = await get_school_id_from_context(current_user, x_school_context)
    if not school_id:
        raise HTTPException(status_code=400, detail="School context required")

    settings = await gd_find_one(db.session, "school_settings", {"school_id": school_id})
    nested = (settings or {}).get("settings", {}) if settings else {}

    cs = (settings or {}).get("custom_settings") or {}

    def _first(*candidates, default=None):
        for c in candidates:
            if c is not None and c != "":
                return c
        return default

    day_start_str = _first(
        cs.get("school_day_start"),
        nested.get("school_day_start"),
        (settings or {}).get("school_day_start"),
        (settings or {}).get("start_time"),
        default="07:00",
    )
    periods_per_day = int(_first(
        cs.get("periods_per_day"),
        nested.get("periods_per_day"),
        (settings or {}).get("periods_per_day"),
        default=7,
    ) or 7)
    period_duration = int(_first(
        cs.get("period_duration_minutes"),
        nested.get("period_duration_minutes"),
        (settings or {}).get("period_duration_minutes"),
        (settings or {}).get("period_duration"),
        default=45,
    ) or 45)
    break_duration = int(_first(
        cs.get("break_duration_minutes"),
        nested.get("break_duration_minutes"),
        (settings or {}).get("break_duration_minutes"),
        (settings or {}).get("break_duration"),
        default=20,
    ) or 20)

    time_slots_raw = await gd_find(db.session, "time_slots", {"school_id": school_id}, order_by="start_time", desc_order=False, limit=30)

    def parse_time(t):
        if not t or not isinstance(t, str) or ":" not in t:
            return None
        try:
            parts = t.split(":")
            return int(parts[0]) * 60 + int(parts[1])
        except (ValueError, IndexError):
            return None

    valid_slots = []
    for slot in time_slots_raw:
        st = parse_time(slot.get("start_time"))
        et = parse_time(slot.get("end_time"))
        if st is not None and et is not None:
            valid_slots.append(slot)

    period_slots = [s for s in valid_slots if not s.get("is_break", False)]
    total_periods = len(period_slots) if period_slots else int(periods_per_day)

    # Derive ``day_end`` from the live timing settings instead of trusting
    # a possibly-stale ``school_day_end`` row. When the principal edits
    # period count or duration without re-running slot generation, the
    # banner used to keep showing the old end time (e.g. "13:15" forever).
    # We now recompute it on the fly: end = start + periods*period_dur +
    # total break minutes. If real ``time_slots`` exist they win — they're
    # the most accurate source because they include passing time and the
    # actual prayer-break placement.
    start_minutes = parse_time(day_start_str) or 420
    if period_slots:
        computed_end_minutes = parse_time(period_slots[-1].get("end_time")) or (start_minutes + total_periods * period_duration + break_duration)
    else:
        # Approximate: total class time + a single block of break time.
        # Matches what the timing settings UI implies (one main break +
        # an optional prayer break), and is good enough for the banner
        # until the principal regenerates real slots.
        computed_end_minutes = start_minutes + (total_periods * period_duration) + break_duration
    end_h, end_m = divmod(computed_end_minutes, 60)
    day_end_str = f"{end_h % 24:02d}:{end_m:02d}"

    working_days = (settings or {}).get("working_days", nested.get("working_days", {}))
    day_names_map = {6: "sunday", 0: "monday", 1: "tuesday", 2: "wednesday", 3: "thursday", 4: "friday", 5: "saturday"}
    # Use the school's configured timezone (default Asia/Riyadh) so that
    # "current period" reflects local school time, not the server's UTC clock.
    tz_name = nested.get("timezone") or (settings or {}).get("timezone") or DEFAULT_SCHOOL_TZ
    try:
        school_tz = ZoneInfo(tz_name)
    except Exception:
        school_tz = ZoneInfo(DEFAULT_SCHOOL_TZ)
    now = datetime.now(school_tz)
    today_key = day_names_map.get(now.weekday(), "")
    is_working_day = True
    if isinstance(working_days, dict) and working_days:
        is_working_day = working_days.get(today_key, False)

    now_minutes = now.hour * 60 + now.minute

    if period_slots:
        first_start = parse_time(period_slots[0].get("start_time")) or parse_time(day_start_str) or 420
        last_end = parse_time(period_slots[-1].get("end_time")) or parse_time(day_end_str) or 795
    else:
        first_start = parse_time(day_start_str) or 420
        last_end = parse_time(day_end_str) or 795

    is_school_time = is_working_day and first_start <= now_minutes <= last_end

    current_period = 0
    current_period_name = ""
    is_break = False

    if is_school_time:
        for slot in valid_slots:
            s = parse_time(slot.get("start_time"))
            e = parse_time(slot.get("end_time"))
            if s is not None and e is not None and s <= now_minutes < e:
                if slot.get("is_break", False):
                    is_break = True
                    current_period_name = slot.get("name") or "استراحة"
                else:
                    current_period = period_slots.index(slot) + 1 if slot in period_slots else 0
                    current_period_name = slot.get("name") or f"الحصة {current_period}"
                break

        if current_period == 0 and not is_break:
            for i, slot in enumerate(period_slots):
                e = parse_time(slot.get("end_time"))
                if e is not None and now_minutes < e:
                    current_period = i + 1
                    break
            if current_period == 0:
                current_period = total_periods

    elapsed = max(0, now_minutes - first_start)
    total_duration = max(1, last_end - first_start)
    progress = min(100, max(0, round((elapsed / total_duration) * 100)))
    if not is_working_day:
        progress = 0

    slots_formatted = []
    for s in time_slots_raw:
        slots_formatted.append({
            "start_time": s.get("start_time"),
            "end_time": s.get("end_time"),
            "is_break": s.get("is_break", False),
            "name": s.get("name", ""),
            "name_en": s.get("name_en", ""),
        })

    return {
        "day_start": day_start_str,
        "day_end": day_end_str,
        "total_periods": total_periods,
        "current_period": current_period,
        "current_period_name": current_period_name,
        "is_break": is_break,
        "is_school_time": is_school_time,
        "is_working_day": is_working_day,
        "progress": progress,
        "time_slots": slots_formatted,
    }


_EN_TO_AR = {
    "sunday": "الأحد", "monday": "الإثنين", "tuesday": "الثلاثاء",
    "wednesday": "الأربعاء", "thursday": "الخميس", "friday": "الجمعة", "saturday": "السبت",
}

def _dict_to_active_ar(wd: dict) -> list:
    return [_EN_TO_AR[d] for d, active in wd.items() if active and d in _EN_TO_AR]

def _dict_to_inactive_ar(wd: dict) -> list:
    return [_EN_TO_AR[d] for d, active in wd.items() if not active and d in _EN_TO_AR]

def _resolve_working_days_ar(nested_settings: dict, settings: dict) -> list:
    for src in (nested_settings, settings):
        for key in ("working_days_ar", "working_days", "work_days"):
            val = src.get(key)
            if isinstance(val, list) and val:
                return val
            if isinstance(val, dict) and val:
                return _dict_to_active_ar(val)
    return []

def _resolve_weekend_days_ar(nested_settings: dict, settings: dict) -> list:
    for src in (nested_settings, settings):
        for key in ("weekend_days_ar", "weekend_days"):
            val = src.get(key)
            if isinstance(val, list) and val:
                return val
    for src in (nested_settings, settings):
        for key in ("working_days", "work_days"):
            val = src.get(key)
            if isinstance(val, dict) and val:
                return _dict_to_inactive_ar(val)
    return []


@router.get("/school/settings")
async def get_school_settings(
    current_user: dict = Depends(get_current_user),
    x_school_context: str = Header(default=None, alias="X-School-Context")
):
    """Get all school settings - جلب جميع إعدادات المدرسة"""
    school_id = await get_school_id_from_context(current_user, x_school_context)
    
    if not school_id:
        raise HTTPException(status_code=400, detail="School context required")
    
    # Get school info
    school = await gd_find_one(db.session, "schools", {"id": school_id})
    
    # Get school-specific settings
    settings = await gd_find_one(db.session, "school_settings", {"school_id": school_id})
    
    if not settings:
        # Get default settings template and create school-specific settings
        default_settings = await gd_find_one(db.session, "default_settings", {"id": "default-school-settings"})
        
        if default_settings:
            settings = {
                "school_id": school_id,
                "working_days": default_settings.get("working_days"),
                "working_days_ar": default_settings.get("working_days_ar"),
                "working_days_en": default_settings.get("working_days_en"),
                "weekend_days_ar": default_settings.get("weekend_days_ar"),
                "weekend_days_en": default_settings.get("weekend_days_en"),
                "periods_per_day": default_settings.get("periods_per_day"),
                "period_duration_minutes": default_settings.get("period_duration_minutes"),
                "break_duration_minutes": default_settings.get("break_duration_minutes"),
                "prayer_duration_minutes": default_settings.get("prayer_duration_minutes"),
                "school_day_start": default_settings.get("school_day_start"),
                "school_day_end": default_settings.get("school_day_end"),
                "time_slots": default_settings.get("time_slots"),
                "education_track": "track-general",
                "created_at": datetime.now(timezone.utc).isoformat()
            }
        else:
            # Fallback if no default settings exist
            settings = {
                "school_id": school_id,
                "working_days": {
                    "sunday": True, "monday": True, "tuesday": True,
                    "wednesday": True, "thursday": True, "friday": False, "saturday": False
                },
                "periods_per_day": 7,
                "school_day_start": "07:00",
                "school_day_end": "13:15",
                "created_at": datetime.now(timezone.utc).isoformat()
            }
        await gd_insert(db.session, "school_settings", settings)
    
    # Get reference data from academic structure
    academic_stages = await gd_find(db.session, "academic_stages", {"is_active": True}, order_by="order", desc_order=False, limit=10)
    academic_grades = await gd_find(db.session, "academic_grades", {"is_active": True}, order_by="order", desc_order=False, limit=50)
    education_tracks = await gd_find(db.session, "education_tracks", {"is_active": True}, limit=10)
    subjects = await gd_find(db.session, "subjects", {"is_active": True}, limit=50)
    teacher_ranks = await gd_find(db.session, "teacher_ranks", {"is_active": True}, order_by="order", desc_order=False, limit=20)
    admin_constraints = await gd_find(db.session, "admin_constraints", {"is_active": True}, limit=50)
    
    # Get school-specific data
    sections = await gd_find(db.session, "classes", {"school_id": school_id}, limit=200)
    terms = await gd_find(db.session, "academic_terms", {"school_id": school_id}, limit=10)
    
    # Extract settings nested values
    nested_settings = settings.get("settings", {})
    cs = settings.get("custom_settings") or {}

    def _pick(*candidates, default=None):
        for c in candidates:
            if c is not None and c != "":
                return c
        return default

    return {
        "school_info": school or {},
        "settings": settings,
        # Frontend-compatible field names - prefer custom_settings, then nested, then ORM columns
        "academicYear": _pick(cs.get("academic_year"), nested_settings.get("academic_year"), settings.get("academic_year"), default=""),
        "currentSemester": _pick(cs.get("current_semester"), nested_settings.get("current_semester"), settings.get("current_semester"), default=""),
        "dayStart": _pick(cs.get("school_day_start"), nested_settings.get("school_day_start"), settings.get("school_day_start"), settings.get("start_time"), default="07:00"),
        "dayEnd": _pick(cs.get("school_day_end"), nested_settings.get("school_day_end"), settings.get("school_day_end"), settings.get("end_time"), default="13:15"),
        "periodsPerDay": _pick(cs.get("periods_per_day"), nested_settings.get("periods_per_day"), settings.get("periods_per_day"), default=7),
        "periodDuration": _pick(cs.get("period_duration_minutes"), nested_settings.get("period_duration_minutes"), settings.get("period_duration_minutes"), settings.get("period_duration"), default=45),
        "breakDuration": _pick(cs.get("break_duration_minutes"), nested_settings.get("break_duration_minutes"), settings.get("break_duration_minutes"), settings.get("break_duration"), default=20),
        "workingDays": _resolve_working_days_ar(nested_settings, settings),
        "weekendDays": _resolve_weekend_days_ar(nested_settings, settings),
        "breaks": settings.get("breaks", []),
        "maxStandbyPerWeek": _pick(cs.get("max_standby_per_teacher_per_week"), nested_settings.get("max_standby_per_teacher_per_week"), default=5),
        "attendancePattern": _pick(cs.get("attendance_pattern"), nested_settings.get("attendance_pattern"), settings.get("attendance_pattern"), default="winter"),
        # Original field names for backward compatibility
        "working_days": settings.get("working_days", {}),
        "periods_per_day": _pick(cs.get("periods_per_day"), settings.get("periods_per_day"), default=7),
        "time_slots": _pick(cs.get("time_slots"), settings.get("time_slots"), default=[]),
        "school_day_start": _pick(cs.get("school_day_start"), settings.get("school_day_start"), settings.get("start_time"), default="07:00"),
        "school_day_end": _pick(cs.get("school_day_end"), settings.get("school_day_end"), settings.get("end_time"), default="13:15"),
        "academic_structure": {
            "stages": academic_stages,
            "grades": academic_grades,
            "tracks": education_tracks
        },
        "reference_data": {
            "subjects": subjects,
            "teacher_ranks": teacher_ranks,
            "admin_constraints": admin_constraints
        },
        "school_classes": sections,
        "academic_terms": terms,
        "last_sync": settings.get("updated_at", datetime.now(timezone.utc).isoformat())
    }


@router.get("/school/settings/audit-logs")
async def get_school_audit_logs(
    limit: int = 50,
    entity_type: Optional[str] = None,
    current_user: dict = Depends(require_roles([UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN])),
    x_school_context: str = Header(default=None, alias="X-School-Context")
):
    """Get school settings audit logs - سجل التدقيق لإعدادات المدرسة"""
    school_id = await get_school_id_from_context(current_user, x_school_context)
    
    if not school_id:
        raise HTTPException(status_code=400, detail="School context required")
    
    query = {"school_id": school_id}
    if entity_type:
        query["entity_type"] = entity_type
    
    logs = await gd_find(db.session, "audit_logs", query, order_by="timestamp", desc_order=True, limit=limit)
    
    return {"logs": logs, "total": len(logs)}


@router.put("/school/settings/info")
async def update_school_info(
    data: SchoolInfoUpdate,
    current_user: dict = Depends(require_roles([UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN])),
    x_school_context: str = Header(default=None, alias="X-School-Context")
):
    """Update school basic info - تحديث معلومات المدرسة الأساسية"""
    school_id = await get_school_id_from_context(current_user, x_school_context)
    
    if not school_id:
        raise HTTPException(status_code=400, detail="School context required")
    
    # Get old data for audit log
    old_school = await gd_find_one(db.session, "schools", {"id": school_id})
    
    update_data = {k: v for k, v in data.model_dump().items() if v is not None}
    if "type" in update_data:
        update_data["school_type"] = update_data["type"]
    update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
    update_data["updated_by"] = current_user["id"]
    
    await gd_update_one(db.session, "schools", {"id": school_id}, update_data)
    
    # Audit log
    audit_log = {
        "id": str(uuid.uuid4()),
        "school_id": school_id,
        "action": "update",
        "entity_type": "school_info",
        "entity_id": school_id,
        "old_data": {k: old_school.get(k) for k in update_data.keys() if k not in ["updated_at", "updated_by"]},
        "new_data": update_data,
        "performed_by": current_user["id"],
        "performed_by_name": current_user.get("full_name", ""),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "ip_address": None
    }
    await gd_insert(db.session, "audit_logs", audit_log)
    
    return {"message": "تم تحديث معلومات المدرسة بنجاح", "updated": update_data}


@router.put("/school/settings/work-days")
async def update_work_days(
    data: WorkDaysConfig,
    current_user: dict = Depends(require_roles([UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN])),
    x_school_context: str = Header(default=None, alias="X-School-Context")
):
    """Update work days - تحديث أيام العمل"""
    school_id = await get_school_id_from_context(current_user, x_school_context)
    
    if not school_id:
        raise HTTPException(status_code=400, detail="School context required")
    
    # Get old settings for audit log
    old_settings = await gd_find_one(db.session, "school_settings", {"school_id": school_id})
    old_work_days = old_settings.get("work_days", {}) if old_settings else {}
    
    # Convert to Arabic day names
    day_names_ar = {
        'sunday': 'الأحد', 'monday': 'الإثنين', 'tuesday': 'الثلاثاء',
        'wednesday': 'الأربعاء', 'thursday': 'الخميس', 'friday': 'الجمعة', 'saturday': 'السبت'
    }
    
    working_days_ar = [day_names_ar[day] for day, active in data.model_dump().items() if active]
    weekend_days_ar = [day_names_ar[day] for day, active in data.model_dump().items() if not active]
    
    working_days_dict = data.model_dump()
    await gd_upsert(db.session, "school_settings", {"school_id": school_id},
        {
            "work_days": working_days_dict,
            "working_days": working_days_dict,
            "working_days_ar": working_days_ar,
            "weekend_days_ar": weekend_days_ar,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "updated_by": current_user["id"]
        }
    )
    
    # Audit log
    audit_log = {
        "id": str(uuid.uuid4()),
        "school_id": school_id,
        "action": "update",
        "entity_type": "work_days",
        "entity_id": school_id,
        "old_data": old_work_days,
        "new_data": data.model_dump(),
        "performed_by": current_user["id"],
        "performed_by_name": current_user.get("full_name", ""),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "ip_address": None
    }
    await gd_insert(db.session, "audit_logs", audit_log)
    
    return {"message": "تم تحديث أيام العمل بنجاح", "work_days": data.model_dump(), "working_days_ar": working_days_ar}


@router.post("/school/settings/holidays")
async def add_official_holiday(
    data: OfficialHoliday,
    current_user: dict = Depends(require_roles([UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN])),
    x_school_context: str = Header(default=None, alias="X-School-Context")
):
    """Add official holiday - إضافة إجازة رسمية"""
    school_id = await get_school_id_from_context(current_user, x_school_context)
    
    if not school_id:
        raise HTTPException(status_code=400, detail="School context required")
    
    holiday = data.model_dump()
    holiday["id"] = str(uuid.uuid4())
    holiday["created_at"] = datetime.now(timezone.utc).isoformat()
    
    settings = await gd_find_one(db.session, "school_settings", {"school_id": school_id})
    if not settings:
        await gd_upsert(db.session, "school_settings", {"school_id": school_id}, {"official_holidays": [holiday]})
    else:
        existing = settings.get("official_holidays") or []
        existing.append(holiday)
        await gd_update_one(db.session, "school_settings", {"school_id": school_id}, {"official_holidays": existing})
    
    return {"message": "تم إضافة الإجازة الرسمية", "holiday": holiday}


@router.delete("/school/settings/holidays/{holiday_id}")
async def delete_official_holiday(
    holiday_id: str,
    current_user: dict = Depends(require_roles([UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN])),
    x_school_context: str = Header(default=None, alias="X-School-Context")
):
    """Delete official holiday - حذف إجازة رسمية"""
    school_id = await get_school_id_from_context(current_user, x_school_context)
    
    if not school_id:
        raise HTTPException(status_code=400, detail="School context required")
    
    settings = await gd_find_one(db.session, "school_settings", {"school_id": school_id})
    if settings:
        existing = [h for h in (settings.get("official_holidays") or []) if h.get("id") != holiday_id]
        await gd_update_one(db.session, "school_settings", {"school_id": school_id}, {"official_holidays": existing})
    
    return {"message": "تم حذف الإجازة الرسمية"}


@router.put("/school/settings")
async def update_school_settings_full(
    data: dict,
    current_user: dict = Depends(require_roles([UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN])),
    x_school_context: str = Header(default=None, alias="X-School-Context")
):
    """Update full school settings including time slots - تحديث إعدادات المدرسة الكاملة"""
    school_id = await get_school_id_from_context(current_user, x_school_context)
    
    if not school_id:
        raise HTTPException(status_code=400, detail="School context required")
    
    # Accept both formats: { settings: {...} } or direct { key: value }
    settings_data = data.get("settings", data)
    
    # Prepare update data - save to root level AND nested settings
    update_data = {
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    
    ar_to_en_days = {
        'الأحد': 'sunday', 'الإثنين': 'monday', 'الاثنين': 'monday',
        'الثلاثاء': 'tuesday', 'الأربعاء': 'wednesday',
        'الخميس': 'thursday', 'الجمعة': 'friday', 'السبت': 'saturday'
    }
    all_days = ['sunday', 'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday']

    if "workingDays" in settings_data and isinstance(settings_data["workingDays"], list):
        active_en = [ar_to_en_days.get(d, d) for d in settings_data["workingDays"]]
        working_days_dict = {day: (day in active_en) for day in all_days}
        update_data["working_days"] = working_days_dict
        update_data["settings.working_days_dict"] = working_days_dict
        update_data["work_days"] = working_days_dict

    # Map frontend field names to: (orm_column_or_none, custom_settings_key_or_none)
    # NOTE: SchoolSettings ORM columns are: start_time, end_time, period_duration,
    # break_duration, periods_per_day, working_days. Anything else MUST go into the
    # custom_settings JSONB column or it will be silently dropped by the ORM layer.
    field_mappings = {
        "academicYear":            (None, "academic_year"),
        "currentSemester":         (None, "current_semester"),
        "dayStart":                ("start_time", "school_day_start"),
        "dayEnd":                  ("end_time", "school_day_end"),
        "periodsPerDay":           ("periods_per_day", "periods_per_day"),
        "periodDuration":          ("period_duration", "period_duration_minutes"),
        "breakDuration":           ("break_duration", "break_duration_minutes"),
        "weekendDays":             (None, "weekend_days_ar"),
        # Also support direct snake_case keys
        "school_day_start":        ("start_time", "school_day_start"),
        "school_day_end":          ("end_time", "school_day_end"),
        "periods_per_day":         ("periods_per_day", "periods_per_day"),
        "period_duration_minutes": ("period_duration", "period_duration_minutes"),
        "break_duration_minutes":  ("break_duration", "break_duration_minutes"),
        "prayer_duration_minutes": (None, "prayer_duration_minutes"),
        "attendancePattern":       (None, "attendance_pattern"),
        "attendance_pattern":      (None, "attendance_pattern"),
        "maxStandbyPerWeek":             (None, "max_standby_per_teacher_per_week"),
        "max_standby_per_teacher_per_week": (None, "max_standby_per_teacher_per_week"),
    }

    # Validate new standby cap (1..20). Reject early with Arabic message.
    if "maxStandbyPerWeek" in settings_data or "max_standby_per_teacher_per_week" in settings_data:
        raw = settings_data.get("maxStandbyPerWeek",
                                settings_data.get("max_standby_per_teacher_per_week"))
        try:
            n = int(raw)
        except (TypeError, ValueError):
            raise HTTPException(status_code=400,
                detail="قيمة الحد الأقصى لحصص الانتظار يجب أن تكون رقماً صحيحاً")
        if n < 1 or n > 20:
            raise HTTPException(status_code=400,
                detail="الحد الأقصى لحصص الانتظار يجب أن يكون بين 1 و 20")

    # Load existing settings so we can merge custom_settings (JSONB) properly
    existing = await gd_find_one(db.session, "school_settings", {"school_id": school_id}) or {}
    custom_settings = dict(existing.get("custom_settings") or {})

    for frontend_key, (orm_col, cs_key) in field_mappings.items():
        if frontend_key not in settings_data:
            continue
        value = settings_data[frontend_key]
        if orm_col:
            update_data[orm_col] = value
        if cs_key:
            custom_settings[cs_key] = value

    # Special-case keys handled separately
    if "workingDays" in settings_data and isinstance(settings_data["workingDays"], list):
        custom_settings["working_days_ar"] = settings_data["workingDays"]
    if "time_slots" in settings_data:
        custom_settings["time_slots"] = settings_data["time_slots"]

    update_data["custom_settings"] = custom_settings
    
    if "breaks" in settings_data and isinstance(settings_data["breaks"], list):
        breaks_data = []
        key_map = {"afterPeriod": "after_period", "customType": "custom_type"}
        for b in settings_data["breaks"]:
            if not b.get("id"):
                b["id"] = str(uuid.uuid4())
            normalized = {}
            for k, v in b.items():
                normalized[key_map.get(k, k)] = v
            breaks_data.append(normalized)
        update_data["breaks"] = breaks_data

    # Get old settings for audit log
    old_settings = await gd_find_one(db.session, "school_settings", {"school_id": school_id}) or {}

    # Update school_settings collection
    await gd_upsert(db.session, "school_settings", {"school_id": school_id}, update_data)

    # Also update time_slots collection if time_slots provided
    if "time_slots" in settings_data:
        # Delete old time slots
        await gd_delete_many(db.session, "time_slots", {"school_id": school_id})

        # Insert new time slots
        for slot in settings_data["time_slots"]:
            slot_doc = {
                "id": str(uuid.uuid4()),
                "school_id": school_id,
                **slot,
                "created_at": datetime.now(timezone.utc).isoformat()
            }
            await gd_insert(db.session, "time_slots", slot_doc)

    # Audit log — record every settings save
    changed_keys = [k for k in update_data if k != "updated_at" and old_settings.get(k) != update_data[k]]
    if changed_keys or "soft_constraints" in settings_data:
        await gd_insert(db.session, "audit_logs", {
            "id": str(uuid.uuid4()),
            "school_id": school_id,
            "action": "UPDATE",
            "entity_type": "school_settings",
            "entity_id": school_id,
            "changed_keys": changed_keys,
            "old_data": {k: old_settings.get(k) for k in changed_keys},
            "new_data": {k: update_data[k] for k in changed_keys},
            "soft_constraints_saved": "soft_constraints" in settings_data,
            "performed_by": current_user.get("id"),
            "performed_by_email": current_user.get("email"),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    timing_fields = {"dayStart", "dayEnd", "periodsPerDay", "periodDuration", "breakDuration",
                     "breakAfterPeriod", "school_day_start", "periods_per_day", "period_duration_minutes",
                     "break_duration_minutes", "prayer_duration_minutes"}
    has_timing_change = any(k in settings_data for k in timing_fields)
    regen_result = None
    if has_timing_change and "time_slots" not in settings_data:
        regen_result = await regenerate_time_slots_from_settings(school_id)

    return {
        "message": "تم تحديث إعدادات المدرسة بنجاح",
        "settings": settings_data,
        "time_slots_regenerated": regen_result
    }


@router.get("/school/settings/hard-constraints")
async def get_hard_constraints(
    current_user: dict = Depends(require_roles([
        UserRole.SCHOOL_ADMIN, UserRole.SCHOOL_SUB_ADMIN, UserRole.SCHOOL_PRINCIPAL,
        UserRole.PLATFORM_ADMIN, UserRole.TEACHER
    ]))
):
    constraints = await gd_find(db.session, "timetable_hard_constraints", {"is_system": True}, order_by="order", desc_order=False, limit=50)

    categories = {}
    for c in constraints:
        cat = c.get("category", "other")
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(c)

    category_labels = {
        "resource_conflict": "تعارض الموارد",
        "time_boundary": "حدود الوقت",
        "capacity": "السعة",
        "workload": "نصاب العمل",
        "curriculum": "المنهج الدراسي",
        "distribution": "توزيع الحصص",
        "assignment": "الإسناد",
        "completeness": "اكتمال الجدول",
        "data_integrity": "صحة البيانات",
        "publishing": "النشر"
    }

    return {
        "success": True,
        "hard_constraints": constraints,
        "total": len(constraints),
        "categories": category_labels,
        "by_category": categories
    }


@router.get("/school/settings/soft-constraints")
async def get_soft_constraints(
    current_user: dict = Depends(require_roles([
        UserRole.SCHOOL_ADMIN, UserRole.SCHOOL_SUB_ADMIN, UserRole.SCHOOL_PRINCIPAL,
        UserRole.PLATFORM_ADMIN, UserRole.TEACHER
    ]))
):
    school_id = current_user.get("school_id") or current_user.get("tenant_id")
    # Fetch immutable global reference constraints
    global_constraints = await gd_find(db.session, "timetable_soft_constraints", {}, order_by="order", desc_order=False, limit=50)

    # Fetch per-school overrides (school-scoped mutable state)
    school_overrides: Dict[str, dict] = {}
    if school_id:
        overrides = await gd_find(db.session, "school_soft_constraint_overrides", {"school_id": school_id}, limit=200)
        school_overrides = {ov["code"]: ov for ov in overrides if ov.get("code")}

    # Merge: global defaults + per-school overrides (overrides win for is_active, weight, target_subject_ids)
    constraints = []
    for c in global_constraints:
        merged = dict(c)
        ov = school_overrides.get(c.get("code"))
        if ov:
            if "is_active" in ov:
                merged["is_active"] = ov["is_active"]
            if "weight" in ov:
                merged["weight"] = ov["weight"]
            if "target_subject_ids" in ov:
                merged["target_subject_ids"] = ov["target_subject_ids"]
        constraints.append(merged)

    categories = {}
    for c in constraints:
        cat = c.get("category", "other")
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(c)

    category_labels = {
        "distribution": "توزيع الحصص",
        "teacher_comfort": "راحة المعلم",
        "pedagogy": "الجانب التربوي",
        "fairness": "العدالة والتوازن"
    }

    return {
        "success": True,
        "soft_constraints": constraints,
        "total": len(constraints),
        "categories": category_labels,
        "by_category": categories
    }


@router.put("/school/settings/soft-constraints/{code}")
async def toggle_soft_constraint(
    code: str,
    data: dict,
    current_user: dict = Depends(require_roles([UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN]))
):
    school_id = current_user.get("school_id") or current_user.get("tenant_id")
    if not school_id:
        raise HTTPException(status_code=403, detail="المستخدم غير مرتبط بمدرسة")

    constraint = await gd_find_one(db.session, "timetable_soft_constraints", {"code": code})
    if not constraint:
        raise HTTPException(status_code=404, detail="القيد غير موجود")

    now = datetime.now(timezone.utc).isoformat()
    update: dict = {"code": code, "school_id": school_id, "updated_at": now}
    if "is_active" in data:
        update["is_active"] = data["is_active"]
    if "weight" in data:
        w = data["weight"]
        if isinstance(w, int) and 1 <= w <= 10:
            update["weight"] = w
    if "target_subject_ids" in data:
        val = data["target_subject_ids"]
        update["target_subject_ids"] = val if isinstance(val, list) else []

    # Upsert into school-scoped override collection — global timetable_soft_constraints is IMMUTABLE
    existing_ov = await gd_find_one(db.session, "school_soft_constraint_overrides", {"school_id": school_id, "code": code})
    if existing_ov:
        await gd_update_one(db.session, "school_soft_constraint_overrides", {"school_id": school_id, "code": code}, update)
    else:
        update["id"] = str(uuid.uuid4())
        update["created_at"] = now
        await gd_insert(db.session, "school_soft_constraint_overrides", update)

    return {"success": True, "message": "تم تحديث القيد التفضيلي بنجاح"}


# ============ CUSTOM SOFT CONSTRAINTS ============

@router.get("/school/settings/custom-soft-constraints")
async def get_custom_soft_constraints(
    current_user: dict = Depends(require_roles([UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN]))
):
    school_id = current_user.get("school_id") or current_user.get("tenant_id")
    if not school_id:
        raise HTTPException(status_code=403, detail="المستخدم غير مرتبط بمدرسة")
    constraints = await gd_find(db.session, "custom_soft_constraints", {"school_id": school_id}, order_by="created_at", desc_order=False, limit=100)
    return {"success": True, "constraints": constraints, "total": len(constraints)}


@router.post("/school/settings/custom-soft-constraints")
async def create_custom_soft_constraint(
    data: dict,
    current_user: dict = Depends(require_roles([UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN]))
):
    school_id = current_user.get("school_id") or current_user.get("tenant_id")
    if not school_id:
        raise HTTPException(status_code=403, detail="المستخدم غير مرتبط بمدرسة")

    name_ar = data.get("name_ar", "").strip()
    if not name_ar:
        raise HTTPException(status_code=400, detail="اسم القيد مطلوب")

    now = datetime.now(timezone.utc).isoformat()
    cid = str(uuid.uuid4())
    try:
        weight_val = max(1, min(10, int(data.get("weight", 5))))
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="قيمة الوزن غير صالحة — يجب أن تكون رقماً بين 1 و10")
    doc = {
        "id": cid,
        "school_id": school_id,
        "name_ar": name_ar,
        "description_ar": data.get("description_ar", ""),
        "pattern": data.get("pattern", ""),
        "pattern_code": data.get("pattern_code", "custom"),
        "weight": weight_val,
        "target_subject_ids": data.get("target_subject_ids", []),
        "applies_to": data.get("applies_to", "school"),
        "is_active": True,
        "is_custom": True,
        "created_by": current_user.get("email"),
        "created_at": now,
        "updated_at": now,
    }
    await gd_insert(db.session, "custom_soft_constraints", doc)
    created = await gd_find_one(db.session, "custom_soft_constraints", {"id": cid})
    return {"success": True, "constraint": created, "message": "تم إنشاء القيد التفضيلي بنجاح"}


@router.put("/school/settings/custom-soft-constraints/{constraint_id}")
async def update_custom_soft_constraint(
    constraint_id: str,
    data: dict,
    current_user: dict = Depends(require_roles([UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN]))
):
    school_id = current_user.get("school_id") or current_user.get("tenant_id")
    existing = await gd_find_one(db.session, "custom_soft_constraints", {"id": constraint_id, "school_id": school_id})
    if not existing:
        raise HTTPException(status_code=404, detail="القيد غير موجود")

    update = {"updated_at": datetime.now(timezone.utc).isoformat()}
    for field in ["name_ar", "description_ar", "pattern", "pattern_code", "applies_to"]:
        if field in data:
            update[field] = data[field]
    if "weight" in data:
        try:
            update["weight"] = max(1, min(10, int(data["weight"])))
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="قيمة الوزن غير صالحة — يجب أن تكون رقماً بين 1 و10")
    if "target_subject_ids" in data:
        update["target_subject_ids"] = data["target_subject_ids"] if isinstance(data["target_subject_ids"], list) else []
    if "is_active" in data:
        update["is_active"] = bool(data["is_active"])

    await gd_update_one(db.session, "custom_soft_constraints", {"id": constraint_id, "school_id": school_id}, update)
    updated = await gd_find_one(db.session, "custom_soft_constraints", {"id": constraint_id})
    return {"success": True, "constraint": updated, "message": "تم تحديث القيد بنجاح"}


@router.delete("/school/settings/custom-soft-constraints/{constraint_id}")
async def delete_custom_soft_constraint(
    constraint_id: str,
    current_user: dict = Depends(require_roles([UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN]))
):
    school_id = current_user.get("school_id") or current_user.get("tenant_id")
    existing = await gd_find_one(db.session, "custom_soft_constraints", {"id": constraint_id, "school_id": school_id})
    if not existing:
        raise HTTPException(status_code=404, detail="القيد غير موجود")
    await gd_delete_one(db.session, "custom_soft_constraints", {"id": constraint_id, "school_id": school_id})
    return {"success": True, "message": "تم حذف القيد بنجاح"}


# ============ CONSTRAINT PATTERNS ============

BUILTIN_CONSTRAINT_PATTERNS = [
    {"code": "no_consecutive", "name_ar": "منع التكرار المتتالي", "description_ar": "تجنب جدولة نفس المادة في حصتين متتاليتين"},
    {"code": "early_period_preference", "name_ar": "تفضيل الحصص المبكرة", "description_ar": "جدولة المواد في الحصص الأولى من اليوم"},
    {"code": "late_period_preference", "name_ar": "تفضيل الحصص المتأخرة", "description_ar": "جدولة المواد في الحصص الأخيرة من اليوم"},
    {"code": "balanced_distribution", "name_ar": "توزيع متوازن", "description_ar": "توزيع حصص المادة بالتساوي عبر أيام الأسبوع"},
    {"code": "after_break", "name_ar": "بعد الاستراحة", "description_ar": "جدولة المادة بعد فترة الاستراحة"},
    {"code": "before_break", "name_ar": "قبل الاستراحة", "description_ar": "جدولة المادة قبل فترة الاستراحة"},
    {"code": "minimize_gaps", "name_ar": "تقليل الفراغات", "description_ar": "تقليل الفترات الفارغة في الجدول"},
    {"code": "fair_distribution", "name_ar": "توزيع عادل", "description_ar": "توزيع الحصص بشكل عادل بين المعلمين"},
    {"code": "custom", "name_ar": "نمط مخصص", "description_ar": "نمط مخصص تعرّفه بنفسك"},
]


@router.get("/school/settings/constraint-patterns")
async def get_constraint_patterns(
    current_user: dict = Depends(require_roles([UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN]))
):
    school_id = current_user.get("school_id") or current_user.get("tenant_id")
    custom_patterns = await gd_find(db.session, "custom_constraint_patterns", {"school_id": school_id}, limit=50)
    return {
        "success": True,
        "builtin_patterns": BUILTIN_CONSTRAINT_PATTERNS,
        "custom_patterns": custom_patterns,
    }


@router.post("/school/settings/constraint-patterns")
async def create_constraint_pattern(
    data: dict,
    current_user: dict = Depends(require_roles([UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN]))
):
    school_id = current_user.get("school_id") or current_user.get("tenant_id")
    name_ar = data.get("name_ar", "").strip()
    if not name_ar:
        raise HTTPException(status_code=400, detail="اسم النمط مطلوب")
    now = datetime.now(timezone.utc).isoformat()
    pid = str(uuid.uuid4())
    doc = {
        "id": pid,
        "school_id": school_id,
        "code": f"custom_{pid[:8]}",
        "name_ar": name_ar,
        "description_ar": data.get("description_ar", ""),
        "created_by": current_user.get("email"),
        "created_at": now,
        "updated_at": now,
    }
    await gd_insert(db.session, "custom_constraint_patterns", doc)
    created = await gd_find_one(db.session, "custom_constraint_patterns", {"id": pid})
    return {"success": True, "pattern": created, "message": "تم إنشاء النمط بنجاح"}


@router.put("/school/settings/constraint-patterns/{pattern_id}")
async def update_constraint_pattern(
    pattern_id: str,
    data: dict,
    current_user: dict = Depends(require_roles([UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN]))
):
    school_id = current_user.get("school_id") or current_user.get("tenant_id")
    pattern = await gd_find_one(db.session, "custom_constraint_patterns", {"id": pattern_id, "school_id": school_id})
    if not pattern:
        raise HTTPException(status_code=404, detail="النمط غير موجود")
    allowed = {}
    if "name_ar" in data:
        allowed["name_ar"] = data["name_ar"].strip()
    if "description_ar" in data:
        allowed["description_ar"] = data["description_ar"]
    allowed["updated_at"] = datetime.now(timezone.utc).isoformat()
    await gd_update_one(db.session, "custom_constraint_patterns", {"id": pattern_id, "school_id": school_id}, {"$set": allowed})
    updated = await gd_find_one(db.session, "custom_constraint_patterns", {"id": pattern_id})
    return {"success": True, "pattern": updated, "message": "تم تحديث النمط بنجاح"}


@router.delete("/school/settings/constraint-patterns/{pattern_id}")
async def delete_constraint_pattern(
    pattern_id: str,
    current_user: dict = Depends(require_roles([UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN]))
):
    school_id = current_user.get("school_id") or current_user.get("tenant_id")
    pattern = await gd_find_one(db.session, "custom_constraint_patterns", {"id": pattern_id, "school_id": school_id})
    if not pattern:
        raise HTTPException(status_code=404, detail="النمط غير موجود")
    await gd_delete_one(db.session, "custom_constraint_patterns", {"id": pattern_id, "school_id": school_id})
    return {"success": True, "message": "تم حذف النمط بنجاح"}


# ============ OTHER DUTIES ============

@router.get("/school/settings/other-duties")
async def get_other_duties(
    current_user: dict = Depends(require_roles([UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN]))
):
    school_id = current_user.get("school_id") or current_user.get("tenant_id")
    if not school_id:
        raise HTTPException(status_code=403, detail="المستخدم غير مرتبط بمدرسة")
    duties = await gd_find(db.session, "teacher_other_duties", {"school_id": school_id}, order_by="created_at", desc_order=False, limit=200)
    return {"success": True, "duties": duties, "total": len(duties)}


@router.post("/school/settings/other-duties")
async def create_other_duty(
    data: dict,
    current_user: dict = Depends(require_roles([UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN]))
):
    school_id = current_user.get("school_id") or current_user.get("tenant_id")
    if not school_id:
        raise HTTPException(status_code=403, detail="المستخدم غير مرتبط بمدرسة")

    teacher_id = data.get("teacher_id", "").strip()
    duty_name = data.get("duty_name", "").strip()
    if not teacher_id or not duty_name:
        raise HTTPException(status_code=400, detail="teacher_id و duty_name مطلوبان")

    teacher = await gd_find_one(db.session, "teachers", {"id": teacher_id, "school_id": school_id})
    if not teacher:
        raise HTTPException(status_code=400, detail="المعلم غير موجود أو لا ينتمي إلى هذه المدرسة")

    try:
        equivalent_periods = max(0, int(data.get("equivalent_periods", 1)))
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="قيمة الحصص المعادلة غير صالحة — يجب أن تكون رقماً صحيحاً موجباً")
    now = datetime.now(timezone.utc).isoformat()
    did = str(uuid.uuid4())
    doc = {
        "id": did,
        "school_id": school_id,
        "teacher_id": teacher_id,
        "teacher_name": data.get("teacher_name", ""),
        "duty_name": duty_name,
        "equivalent_periods": equivalent_periods,
        "notes": data.get("notes", ""),
        "created_by": current_user.get("email"),
        "created_at": now,
        "updated_at": now,
    }
    await gd_insert(db.session, "teacher_other_duties", doc)
    created = await gd_find_one(db.session, "teacher_other_duties", {"id": did})
    return {"success": True, "duty": created, "message": "تم إضافة التكليف بنجاح"}


@router.put("/school/settings/other-duties/{duty_id}")
async def update_other_duty(
    duty_id: str,
    data: dict,
    current_user: dict = Depends(require_roles([UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN]))
):
    school_id = current_user.get("school_id") or current_user.get("tenant_id")
    existing = await gd_find_one(db.session, "teacher_other_duties", {"id": duty_id, "school_id": school_id})
    if not existing:
        raise HTTPException(status_code=404, detail="التكليف غير موجود")

    update = {"updated_at": datetime.now(timezone.utc).isoformat()}
    if "duty_name" in data:
        update["duty_name"] = data["duty_name"]
    if "equivalent_periods" in data:
        try:
            update["equivalent_periods"] = max(0, int(data["equivalent_periods"]))
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="قيمة الحصص المعادلة غير صالحة — يجب أن تكون رقماً صحيحاً موجباً")
    if "notes" in data:
        update["notes"] = data["notes"]

    await gd_update_one(db.session, "teacher_other_duties", {"id": duty_id, "school_id": school_id}, update)
    updated = await gd_find_one(db.session, "teacher_other_duties", {"id": duty_id})
    return {"success": True, "duty": updated, "message": "تم تحديث التكليف بنجاح"}


@router.delete("/school/settings/other-duties/{duty_id}")
async def delete_other_duty(
    duty_id: str,
    current_user: dict = Depends(require_roles([UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN]))
):
    school_id = current_user.get("school_id") or current_user.get("tenant_id")
    existing = await gd_find_one(db.session, "teacher_other_duties", {"id": duty_id, "school_id": school_id})
    if not existing:
        raise HTTPException(status_code=404, detail="التكليف غير موجود")
    await gd_delete_one(db.session, "teacher_other_duties", {"id": duty_id, "school_id": school_id})
    return {"success": True, "message": "تم حذف التكليف بنجاح"}


# ============ WORKLOAD CALCULATION ============

RANK_TOTAL_PERIODS = {
    "expert": 24,
    "advanced": 22,
    "practitioner": 20,
    "assistant": 18,
    "معلم خبير": 24,
    "معلم متقدم": 22,
    "معلم ممارس": 20,
    "معلم مساعد": 18,
}


@router.get("/school/settings/workload-summary")
async def get_workload_summary(
    current_user: dict = Depends(require_roles([UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN]))
):
    school_id = current_user.get("school_id") or current_user.get("tenant_id")
    if not school_id:
        raise HTTPException(status_code=403, detail="المستخدم غير مرتبط بمدرسة")

    teachers = await gd_find(db.session, "teachers", {"school_id": school_id, "is_active": True}, limit=200)
    assignments = await gd_find(db.session, "teacher_assignments", {"school_id": school_id}, limit=2000)
    duties = await gd_find(db.session, "teacher_other_duties", {"school_id": school_id}, limit=500)

    assignments_by_teacher: Dict[str, int] = {}
    for a in assignments:
        tid = a.get("teacher_id")
        if tid:
            sessions = int(a.get("periods_per_week") or a.get("weekly_sessions") or 0)
            assignments_by_teacher[tid] = assignments_by_teacher.get(tid, 0) + sessions

    duties_by_teacher: Dict[str, list] = {}
    for d in duties:
        tid = d.get("teacher_id")
        if tid:
            if tid not in duties_by_teacher:
                duties_by_teacher[tid] = []
            duties_by_teacher[tid].append(d)

    overrides = await gd_find(db.session, "teacher_workload_overrides", {"school_id": school_id}, limit=200)
    overrides_by_teacher: Dict[str, dict] = {o["teacher_id"]: o for o in overrides if o.get("teacher_id")}

    summary = []
    for teacher in teachers:
        tid = teacher.get("id")
        rank = teacher.get("rank", "")
        total_periods = RANK_TOTAL_PERIODS.get(rank, 20)
        teaching_periods = assignments_by_teacher.get(tid, 0)
        teacher_duties = duties_by_teacher.get(tid, [])
        other_duty_periods = sum(int(d.get("equivalent_periods", 0)) for d in teacher_duties)
        used_periods = teaching_periods + other_duty_periods
        override = overrides_by_teacher.get(tid, {})
        manual_override = override.get("standby_override")
        standby_periods = manual_override if manual_override is not None else max(0, total_periods - used_periods)

        summary.append({
            "teacher_id": tid,
            "teacher_name": teacher.get("full_name", ""),
            "rank": rank,
            "total_periods": total_periods,
            "teaching_periods": teaching_periods,
            "other_duty_periods": other_duty_periods,
            "other_duties": teacher_duties,
            "used_periods": used_periods,
            "standby_periods": standby_periods,
            "manual_override": manual_override is not None,
            "overload": used_periods > total_periods,
        })

    return {"success": True, "summary": summary, "total_teachers": len(summary)}


@router.put("/school/settings/workload-override/{teacher_id}")
async def set_workload_override(
    teacher_id: str,
    data: dict,
    current_user: dict = Depends(require_roles([UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN]))
):
    school_id = current_user.get("school_id") or current_user.get("tenant_id")
    if not school_id:
        raise HTTPException(status_code=403, detail="المستخدم غير مرتبط بمدرسة")

    teacher = await gd_find_one(db.session, "teachers", {"id": teacher_id, "school_id": school_id})
    if not teacher:
        raise HTTPException(status_code=404, detail="المعلم غير موجود")

    now = datetime.now(timezone.utc).isoformat()
    standby_override = data.get("standby_override")
    if standby_override is None:
        await gd_delete_one(db.session, "teacher_workload_overrides", {"teacher_id": teacher_id, "school_id": school_id})
        return {"success": True, "message": "تم إزالة التعديل اليدوي"}

    try:
        standby_override = int(standby_override)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="قيمة حصص الانتظار غير صالحة — يجب أن تكون رقماً صحيحاً")

    rank = teacher.get("rank", "")
    max_periods = RANK_TOTAL_PERIODS.get(rank, 24)
    if standby_override < 0 or standby_override > max_periods:
        raise HTTPException(
            status_code=400,
            detail=f"قيمة حصص الانتظار يجب أن تكون بين 0 و{max_periods}"
        )

    override_doc = {
        "teacher_id": teacher_id,
        "school_id": school_id,
        "standby_override": standby_override,
        "updated_by": current_user.get("email"),
        "updated_at": now,
    }
    existing = await gd_find_one(db.session, "teacher_workload_overrides", {"teacher_id": teacher_id, "school_id": school_id})
    if existing:
        await gd_update_one(db.session, "teacher_workload_overrides", {"teacher_id": teacher_id, "school_id": school_id}, override_doc)
    else:
        override_doc["id"] = str(uuid.uuid4())
        override_doc["created_at"] = now
        await gd_insert(db.session, "teacher_workload_overrides", override_doc)

    return {"success": True, "message": "تم تحديث حصص الانتظار اليدوية"}


@router.put("/school/constraints/{constraint_id}")
async def update_school_constraint(
    constraint_id: str,
    data: dict,
    current_user: dict = Depends(require_roles([UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN])),
    x_school_context: str = Header(default=None, alias="X-School-Context")
):
    """Toggle constraint active status - تبديل حالة القيد"""
    school_id = await get_school_id_from_context(current_user, x_school_context)
    
    if not school_id:
        raise HTTPException(status_code=400, detail="School context required")
    
    update_data = {"updated_at": datetime.now(timezone.utc).isoformat()}
    
    if "is_active" in data:
        update_data["is_active"] = data["is_active"]
    
    # Try to update in reference_admin_constraints first
    result = await gd_update_one(db.session, "reference_admin_constraints", {"id": constraint_id}, update_data)
    
    if result == 0:
        result = await gd_update_one(db.session, "admin_constraints", {"id": constraint_id}, update_data)
    
    if result == 0:
        raise HTTPException(status_code=404, detail="Constraint not found")
    
    return {"message": "تم تحديث القيد بنجاح", "is_active": data.get("is_active")}


@router.post("/school/settings/exception-days")
async def add_exception_day(
    data: ExceptionDay,
    current_user: dict = Depends(require_roles([UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN])),
    x_school_context: str = Header(default=None, alias="X-School-Context")
):
    """Add exception day - إضافة يوم استثناء"""
    school_id = await get_school_id_from_context(current_user, x_school_context)
    
    if not school_id:
        raise HTTPException(status_code=400, detail="School context required")
    
    exception = data.model_dump()
    exception["id"] = str(uuid.uuid4())
    exception["created_at"] = datetime.now(timezone.utc).isoformat()
    
    settings_doc = await gd_find_one(db.session, "school_settings", {"school_id": school_id})
    if not settings_doc:
        await gd_upsert(db.session, "school_settings", {"school_id": school_id}, {"exception_days": [exception]})
    else:
        existing = settings_doc.get("exception_days") or []
        existing.append(exception)
        await gd_update_one(db.session, "school_settings", {"school_id": school_id}, {"exception_days": existing})
    
    return {"message": "تم إضافة يوم الاستثناء", "exception": exception}


@router.delete("/school/settings/exception-days/{exception_id}")
async def delete_exception_day(
    exception_id: str,
    current_user: dict = Depends(require_roles([UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN])),
    x_school_context: str = Header(default=None, alias="X-School-Context")
):
    """Delete exception day - حذف يوم استثناء"""
    school_id = await get_school_id_from_context(current_user, x_school_context)
    
    if not school_id:
        raise HTTPException(status_code=400, detail="School context required")
    
    settings_doc = await gd_find_one(db.session, "school_settings", {"school_id": school_id})
    if settings_doc:
        existing = [e for e in (settings_doc.get("exception_days") or []) if e.get("id") != exception_id]
        await gd_update_one(db.session, "school_settings", {"school_id": school_id}, {"exception_days": existing})
    
    return {"message": "تم حذف يوم الاستثناء"}


class UpdatePeriodsRequest(BaseModel):
    periods_per_day: int

@router.put("/school/settings/periods-per-day")
async def update_periods_per_day(
    data: UpdatePeriodsRequest,
    current_user: dict = Depends(require_roles([UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN])),
    x_school_context: str = Header(default=None, alias="X-School-Context")
):
    """Update periods per day - تحديث عدد الحصص في اليوم"""
    school_id = await get_school_id_from_context(current_user, x_school_context)
    
    if not school_id:
        raise HTTPException(status_code=400, detail="School context required")
    
    periods = data.periods_per_day
    if periods < 1 or periods > 12:
        raise HTTPException(status_code=400, detail="عدد الحصص يجب أن يكون بين 1 و 12")
    
    await gd_upsert(db.session, "school_settings", {"school_id": school_id}, {
                "periods_per_day": periods,
                "updated_at": datetime.now(timezone.utc).isoformat()
            })
    
    regen_result = await regenerate_time_slots_from_settings(school_id)
    return {"message": "تم تحديث عدد الحصص", "periods_per_day": periods, "time_slots_regenerated": regen_result}


@router.put("/school/settings/timing")
async def update_school_timing(
    data: SchoolTiming,
    current_user: dict = Depends(require_roles([UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN])),
    x_school_context: str = Header(default=None, alias="X-School-Context")
):
    """Update school timing - تحديث بداية ونهاية اليوم الدراسي"""
    school_id = await get_school_id_from_context(current_user, x_school_context)
    
    if not school_id:
        raise HTTPException(status_code=400, detail="School context required")
    
    await gd_upsert(db.session, "school_settings", {"school_id": school_id}, {
                "timing": data.model_dump(),
                "school_day_start": data.start,
                "school_day_end": data.end,
                "settings.school_day_start": data.start,
                "settings.school_day_end": data.end,
                "updated_at": datetime.now(timezone.utc).isoformat()
            })
    
    regen_result = await regenerate_time_slots_from_settings(school_id)
    return {"message": "تم تحديث أوقات الدوام", "timing": data.model_dump(), "time_slots_regenerated": regen_result}


@router.put("/school/settings/breaks")
async def update_breaks(
    breaks: List[BreakPeriod],
    current_user: dict = Depends(require_roles([UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN])),
    x_school_context: str = Header(default=None, alias="X-School-Context")
):
    """Update break periods - تحديث فترات الاستراحة"""
    school_id = await get_school_id_from_context(current_user, x_school_context)
    
    if not school_id:
        raise HTTPException(status_code=400, detail="School context required")
    
    breaks_data = []
    for b in breaks:
        break_dict = b.model_dump()
        if not break_dict.get("id"):
            break_dict["id"] = str(uuid.uuid4())
        breaks_data.append(break_dict)
    
    await gd_upsert(db.session, "school_settings", {"school_id": school_id}, {
                "breaks": breaks_data,
                "updated_at": datetime.now(timezone.utc).isoformat()
            })
    
    regen_result = await regenerate_time_slots_from_settings(school_id)
    return {"message": "تم تحديث فترات الاستراحة", "breaks": breaks_data, "time_slots_regenerated": regen_result}


@router.get("/time-slots")
async def list_time_slots(
    school_id: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
    x_school_context: str = Header(default=None, alias="X-School-Context")
):
    """List time slots for a school. Used by SchedulePageNew and other schedule UIs.
    Accepts ?school_id=... and falls back to the user's school context."""
    resolved_school_id = school_id or await get_school_id_from_context(current_user, x_school_context)
    if not resolved_school_id:
        raise HTTPException(status_code=400, detail="School context required")

    user_school = current_user.get("school_id")
    if (current_user.get("role") != UserRole.PLATFORM_ADMIN.value
            and user_school and user_school != resolved_school_id):
        raise HTTPException(status_code=403, detail="Cross-school access denied")

    slots = await gd_find(db.session, "time_slots", {"school_id": resolved_school_id}, limit=500)
    slots.sort(key=lambda s: (s.get("period_number") if s.get("period_number") is not None
                              else (s.get("slot_number") if s.get("slot_number") is not None else 99)))
    return slots


@router.post("/school/settings/regenerate-time-slots")
async def regenerate_time_slots_endpoint(
    current_user: dict = Depends(require_roles([UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN])),
    x_school_context: str = Header(default=None, alias="X-School-Context")
):
    school_id = await get_school_id_from_context(current_user, x_school_context)
    if not school_id:
        raise HTTPException(status_code=400, detail="School context required")
    result = await regenerate_time_slots_from_settings(school_id)
    if not result.get("regenerated"):
        raise HTTPException(status_code=400, detail="لا توجد إعدادات للمدرسة")
    return {"message": f"تم إعادة توليد {result['count']} فترة زمنية", **result}


@router.post("/school/settings/activity-days")
async def add_activity_day(
    data: ActivityDay,
    current_user: dict = Depends(require_roles([UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN])),
    x_school_context: str = Header(default=None, alias="X-School-Context")
):
    """Add activity day - إضافة يوم نشاط"""
    school_id = await get_school_id_from_context(current_user, x_school_context)
    
    if not school_id:
        raise HTTPException(status_code=400, detail="School context required")
    
    activity = data.model_dump()
    activity["id"] = str(uuid.uuid4())
    activity["created_at"] = datetime.now(timezone.utc).isoformat()
    
    settings_doc = await gd_find_one(db.session, "school_settings", {"school_id": school_id})
    if not settings_doc:
        await gd_upsert(db.session, "school_settings", {"school_id": school_id}, {"activity_days": [activity]})
    else:
        existing = settings_doc.get("activity_days") or []
        existing.append(activity)
        await gd_update_one(db.session, "school_settings", {"school_id": school_id}, {"activity_days": existing})
    
    return {"message": "تم إضافة يوم النشاط", "activity": activity}


@router.delete("/school/settings/activity-days/{activity_id}")
async def delete_activity_day(
    activity_id: str,
    current_user: dict = Depends(require_roles([UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN])),
    x_school_context: str = Header(default=None, alias="X-School-Context")
):
    """Delete activity day - حذف يوم نشاط"""
    school_id = await get_school_id_from_context(current_user, x_school_context)
    
    if not school_id:
        raise HTTPException(status_code=400, detail="School context required")
    
    settings_doc = await gd_find_one(db.session, "school_settings", {"school_id": school_id})
    if settings_doc:
        existing = [a for a in (settings_doc.get("activity_days") or []) if a.get("id") != activity_id]
        await gd_update_one(db.session, "school_settings", {"school_id": school_id}, {"activity_days": existing})
    
    return {"message": "تم حذف يوم النشاط"}


@router.put("/school/settings/teaching-loads")
async def update_teaching_loads(
    loads: dict,
    current_user: dict = Depends(require_roles([UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN])),
    x_school_context: str = Header(default=None, alias="X-School-Context")
):
    """Update teaching loads - تحديث الأنصبة التدريسية"""
    school_id = await get_school_id_from_context(current_user, x_school_context)
    
    if not school_id:
        raise HTTPException(status_code=400, detail="School context required")
    
    await gd_upsert(db.session, "school_settings", {"school_id": school_id}, {
                "teaching_loads": loads,
                "updated_at": datetime.now(timezone.utc).isoformat()
            })
    
    return {"message": "تم تحديث الأنصبة التدريسية", "teaching_loads": loads}


@router.put("/school/settings/teacher-availability")
async def update_teacher_availability(
    data: TeacherAvailability,
    current_user: dict = Depends(require_roles([UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN])),
    x_school_context: str = Header(default=None, alias="X-School-Context")
):
    """Update teacher availability - تحديث توفر المعلم"""
    school_id = await get_school_id_from_context(current_user, x_school_context)
    
    if not school_id:
        raise HTTPException(status_code=400, detail="School context required")
    
    await gd_upsert(db.session, "school_settings", {"school_id": school_id}, {
                f"teacher_availability.{data.teacher_id}": {
                    "available_days": data.available_days,
                    "available_periods": data.available_periods
                },
                "updated_at": datetime.now(timezone.utc).isoformat()
            })
    
    return {"message": "تم تحديث توفر المعلم"}


@router.post("/school/settings/unavailability")
async def create_unavailability(
    data: UnavailabilityCreate,
    current_user: dict = Depends(require_roles([UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN])),
    x_school_context: str = Header(default=None, alias="X-School-Context")
):
    school_id = await get_school_id_from_context(current_user, x_school_context)

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
        # نخزّن الموقع البديل فقط لسجلات الفصول؛ لا معنى له للمعلمين.
        "alternative_location": (data.alternative_location or None) if data.entity_type == "class" else None,
        # سجل المستلمين والمؤكدين للاطلاع — يُملأ أدناه عند إرسال إشعارات
        # النقل، ويبقى فارغاً للسجلات بدون موقع بديل (لا حاجة لتأكيد استلام).
        "recipient_ids": [],
        "acknowledged_by": [],
        "created_at": now,
        "created_by": current_user.get("id"),
    }

    await gd_insert(db.session, "unavailability", doc)

    notifications_sent = 0
    if data.entity_type == "class":
        from routes.notification_routes_mod import create_notification_internal

        # Period-aware recipient resolution: instead of notifying every teacher
        # ever assigned to this class, only notify teachers who actually have a
        # session in this class during the affected day/period (recurring) or
        # any session in this class within the date range (long-term). We pull
        # from the latest published/draft timetable so substitutions and stale
        # assignments don't pollute the recipient list.
        active_timetable = await gd_find_one(
            db.session,
            "timetables",
            {"school_id": school_id, "status": {"$in": ["published", "draft"]}},
            sort=[("updated_at", -1)],
        )

        affected_sessions: list[dict] = []
        if active_timetable:
            session_query = {
                "timetable_id": active_timetable.get("id"),
                "class_id": data.entity_id,
            }
            all_class_sessions = await gd_find(
                db.session, "timetable_sessions", session_query, limit=2000
            )
            if data.unavailability_type == "recurring":
                # Sessions store day in English (sunday..thursday); the modal
                # writes the Arabic name. Translate before comparing so we
                # don't silently miss the affected slots.
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
                # long_term: only notify teachers whose sessions actually fall
                # on a weekday inside [start_date, end_date]. Without this the
                # principal would also page teachers who teach the class on
                # days outside the closure window — e.g. a one-day Monday
                # closure would still wake every Sunday/Tuesday teacher.
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
                    # Cap iteration so a malformed multi-year window can't
                    # spin the worker; a year is more than enough for the
                    # set to saturate to all 7 weekday names.
                    for _ in range(min((e_dt - s_dt).days + 1, 366)):
                        window_days.add(weekday_names[cursor.weekday()])
                        cursor += _td(days=1)
                if window_days:
                    for sess in all_class_sessions:
                        sess_day = (sess.get("day_of_week") or sess.get("day") or "").lower()
                        if sess_day in window_days:
                            affected_sessions.append(sess)
                else:
                    # Couldn't parse the window — fall back to the broader set
                    # so we don't silently drop notifications.
                    affected_sessions = all_class_sessions

        # Fallback: if there's no active timetable yet (e.g. school setting
        # things up before generating), keep the legacy "notify everyone
        # assigned" behaviour so principals still hear back about the change.
        if not affected_sessions and not active_timetable:
            class_assignments = await gd_find(db.session, "teacher_class_assignments", {
                "school_id": school_id,
                "class_id": data.entity_id
            }, limit=500)
            teacher_ids = list({a.get("teacher_id") for a in class_assignments if a.get("teacher_id")})
        else:
            teacher_ids = list({s.get("teacher_id") for s in affected_sessions if s.get("teacher_id")})

        # Resolve teachers.id → users.id before notifying. ``notifications.user_id``
        # is FK→users.id, while ``timetable_sessions.teacher_id`` and
        # ``teacher_class_assignments.teacher_id`` reference ``teachers.id``.
        # Passing the teacher PK straight through used to trip
        # ``notifications_user_id_fkey`` for any teacher whose linked user was
        # deleted (or never linked), aborting the whole transaction and
        # surfacing as "حدث خطأ أثناء حفظ فترة عدم التوفر" even though the
        # ``unavailability`` row itself was valid. We now drop unresolved
        # teachers silently so the unavailability still saves; the count of
        # successful notifications is reported back to the UI.
        recipient_user_ids: list[str] = []
        if teacher_ids:
            teacher_rows = await gd_find(
                db.session,
                "teachers",
                {"id": {"$in": list(teacher_ids)}, "school_id": school_id},
                limit=len(teacher_ids),
            )
            candidate_user_ids = list({
                t.get("user_id") for t in teacher_rows if t.get("user_id")
            })
            if candidate_user_ids:
                # Confirm the user rows still exist — guards against stale
                # ``teachers.user_id`` pointing at a deleted user row.
                existing_users = await gd_find(
                    db.session,
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
            message_ar = (
                f"تم نقل طلاب فصل {class_label} في {period_desc} إلى {data.alternative_location}."
            )
            message_en = (
                f"Students of class {class_label} have been relocated to {data.alternative_location} during {period_desc}."
            )
        else:
            title_ar = "تنبيه: عدم توفر فصل دراسي"
            title_en = "Alert: Classroom Unavailable"
            message_ar = (
                f"الفصل '{class_label}' غير متوفر ({period_desc}). يرجى نقل الطلاب إلى فصل بديل."
            )
            message_en = (
                f"Classroom '{class_label}' is unavailable ({period_desc}). Please relocate students to an alternative classroom."
            )

        # Only carry the relocation extras when there's actually an
        # alternative location to acknowledge. Plain "غير متوفر" alerts
        # remain a one-way nudge — no ack button, no audit panel.
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

        # Persist the resolved recipients on the unavailability doc so the
        # ack endpoint can authorize teachers and the audit panel can show
        # an accurate denominator without re-scanning the timetable. We store
        # the user_ids actually notified (not the raw teacher_ids) so the ack
        # check matches ``current_user.id`` directly.
        if data.alternative_location and recipient_user_ids:
            await gd_update_one(
                db.session,
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


@router.delete("/school/settings/unavailability/{unavailability_id}")
async def delete_unavailability(
    unavailability_id: str,
    current_user: dict = Depends(require_roles([UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN])),
    x_school_context: str = Header(default=None, alias="X-School-Context")
):
    school_id = await get_school_id_from_context(current_user, x_school_context)
    if not school_id:
        raise HTTPException(status_code=400, detail="School context required")
    result = await gd_delete_one(db.session, "unavailability", {"id": unavailability_id, "school_id": school_id})
    if not result:
        raise HTTPException(status_code=404, detail="سجل عدم التوفر غير موجود")
    return {"success": True, "message": "تم حذف فترة عدم التوفر"}


@router.get("/school/settings/unavailability")
async def get_unavailability(
    entity_type: Optional[str] = None,
    current_user: dict = Depends(require_roles([UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN])),
    x_school_context: str = Header(default=None, alias="X-School-Context")
):
    school_id = await get_school_id_from_context(current_user, x_school_context)

    if not school_id:
        raise HTTPException(status_code=400, detail="School context required")

    query = {"school_id": school_id}
    if entity_type:
        query["entity_type"] = entity_type

    items = await gd_find(db.session, "unavailability", query, limit=1000)
    # Surface ack progress for relocation rows so the school-settings audit
    # panel can render "تم الاطلاع: M / N" without an extra round-trip per
    # row. Non-relocation rows expose 0/0 — the frontend just hides the
    # badge in that case.
    for item in items:
        recipients = item.get("recipient_ids") or []
        acked = item.get("acknowledged_by") or []
        item["recipient_count"] = len(recipients) if isinstance(recipients, list) else 0
        item["acknowledged_count"] = len(acked) if isinstance(acked, list) else 0
    return {"items": items}


@router.post("/school/settings/unavailability/{unavailability_id}/acknowledge")
async def acknowledge_unavailability(
    unavailability_id: str,
    current_user: dict = Depends(get_current_user),
    x_school_context: str = Header(default=None, alias="X-School-Context"),
):
    """Mark a relocation alert as acknowledged by the current user.

    Authorized callers are the teachers listed in ``recipient_ids`` (i.e. the
    same teachers the principal notified when the unavailability was saved).
    The endpoint is idempotent — re-acking just refreshes ``acknowledged_at``
    on the user's notifications and is a no-op on the unavailability doc."""
    school_id = await get_school_id_from_context(current_user, x_school_context)
    if not school_id:
        raise HTTPException(status_code=400, detail="School context required")

    record = await gd_find_one(db.session, "unavailability", {"id": unavailability_id, "school_id": school_id})
    if not record:
        raise HTTPException(status_code=404, detail="سجل عدم التوفر غير موجود")

    if not record.get("alternative_location"):
        raise HTTPException(status_code=400, detail="لا يلزم تأكيد الاستلام لهذا السجل")

    user_id = current_user.get("id")
    recipients = record.get("recipient_ids") or []
    if not isinstance(recipients, list):
        recipients = []

    # Allow recipients to ack; allow principals/admins to ack on behalf of
    # themselves only if they were also a recipient. We deliberately don't
    # let admins fake acks for teachers — the audit count must reflect who
    # actually saw the change.
    if user_id not in recipients:
        raise HTTPException(status_code=403, detail="غير مخوّل لتأكيد استلام هذا الإشعار")

    acked = record.get("acknowledged_by") or []
    if not isinstance(acked, list):
        acked = []
    if user_id not in acked:
        acked.append(user_id)
        await gd_update_one(
            db.session,
            "unavailability",
            {"id": unavailability_id, "school_id": school_id},
            {"acknowledged_by": acked},
        )

    # Mark the user's matching notifications as read + acknowledged. We
    # filter the user's recent schedule notifications in Python because the
    # ORM filter pipeline can't query JSONB-only fields like
    # ``unavailability_id`` directly.
    now_iso = datetime.now(timezone.utc).isoformat()
    user_notifs = await gd_find(
        db.session,
        "notifications",
        {"user_id": user_id, "type": "schedule"},
        limit=500,
    )
    for n in user_notifs:
        if n.get("unavailability_id") != unavailability_id:
            continue
        await gd_update_one(
            db.session,
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


@router.get("/school/settings/unavailability/{unavailability_id}/acknowledgements")
async def list_unavailability_acknowledgements(
    unavailability_id: str,
    current_user: dict = Depends(require_roles([UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN])),
    x_school_context: str = Header(default=None, alias="X-School-Context"),
):
    """Return per-recipient ack status for a relocation unavailability.

    The audit panel uses this to render names and timestamps; the summary
    counts are also embedded in ``GET /school/settings/unavailability`` so
    a list view doesn't need to fan out to this endpoint per row."""
    school_id = await get_school_id_from_context(current_user, x_school_context)
    if not school_id:
        raise HTTPException(status_code=400, detail="School context required")

    record = await gd_find_one(db.session, "unavailability", {"id": unavailability_id, "school_id": school_id})
    if not record:
        raise HTTPException(status_code=404, detail="سجل عدم التوفر غير موجود")

    recipients = record.get("recipient_ids") or []
    acked = record.get("acknowledged_by") or []
    if not isinstance(recipients, list):
        recipients = []
    if not isinstance(acked, list):
        acked = []
    acked_set = set(acked)

    # Build a single name lookup for everyone we need to render.
    user_ids = list({*recipients, *acked})
    user_map: dict[str, str] = {}
    if user_ids:
        users = await gd_find(db.session, "users", {"id": {"$in": user_ids}}, limit=len(user_ids))
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


@router.put("/school/settings/constraints")
async def update_constraints(
    constraints: List[AdminConstraint],
    current_user: dict = Depends(require_roles([UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN])),
    x_school_context: str = Header(default=None, alias="X-School-Context")
):
    """Update administrative constraints - تحديث القيود الإدارية"""
    school_id = await get_school_id_from_context(current_user, x_school_context)
    
    if not school_id:
        raise HTTPException(status_code=400, detail="School context required")
    
    constraints_data = []
    for c in constraints:
        c_dict = c.model_dump()
        if not c_dict.get("id"):
            c_dict["id"] = str(uuid.uuid4())
        constraints_data.append(c_dict)
    
    await gd_upsert(db.session, "school_settings", {"school_id": school_id}, {
                "constraints": constraints_data,
                "updated_at": datetime.now(timezone.utc).isoformat()
            })
    
    return {"message": "تم تحديث القيود الإدارية", "constraints": constraints_data}


# [EXTRACTED] edu_stages_routes.py -> routes/extracted/edu_stages_routes.py
# [EXTRACTED] grades_ep_routes.py -> routes/extracted/grades_ep_routes.py
# [EXTRACTED] sections_routes.py -> routes/extracted/sections_routes.py
# [EXTRACTED] academic_terms_routes.py -> routes/extracted/academic_terms_routes.py
# [EXTRACTED] subjects_sched_routes.py -> routes/extracted/subjects_sched_routes.py
# [EXTRACTED] teacher_module_routes.py -> routes/extracted/teacher_module_routes.py
# [EXTRACTED] teacher_session_ep_routes.py -> routes/extracted/teacher_session_ep_routes.py
# ============================================
# Teacher Class Assignments APIs
# إسناد المعلمين للفصول
# ============================================

class TeacherClassAssignmentCreate(BaseModel):
    teacher_id: str
    class_id: str
    academic_year_id: Optional[str] = None

class TeacherClassAssignmentResponse(BaseModel):
    id: str
    teacher_id: str
    class_id: str
    school_id: str
    academic_year_id: Optional[str] = None
    teacher_name: Optional[str] = None
    class_name: Optional[str] = None
    created_at: Optional[str] = None

async def _auto_populate_teacher_class_assignments(school_id: str):
    """
    Auto-populate teacher-class assignments: all teachers linked to all classes by default.
    Runs ONLY ONCE per school, on first touch (when no assignments exist at all).
    Subsequent additions of new teachers/classes are handled by `_ensure_teacher_linked_to_all_classes`
    and `_ensure_class_linked_to_all_teachers` at create time.

    This guarantees that if a principal/admin deletes an assignment, it stays
    deleted — we will not silently recreate it on the next page load.

    IMPORTANT: this runs from a GET handler. The pg_session_middleware rolls
    back GET-request transactions to defend against accidental writes, which
    means inserts on db.session would vanish at end-of-request. We use a
    dedicated session with an explicit commit so the auto-populated rows
    actually persist.
    """
    from db import async_session_factory

    async with async_session_factory() as ses:
        existing_count = await gd_count(ses, "teacher_class_assignments", {"school_id": school_id})
        if existing_count > 0:
            # School has already been initialized — never re-populate.
            return 0

        teachers = await gd_find(ses, "teachers", {"school_id": school_id, "is_active": {"$ne": False}}, limit=2000)
        classes = await gd_find(ses, "classes", {"school_id": school_id, "is_active": {"$ne": False}}, limit=500)

        if not teachers or not classes:
            return 0

        now = datetime.now(timezone.utc).isoformat()
        upserted = 0
        for t in teachers:
            for c in classes:
                filt = {"school_id": school_id, "teacher_id": t["id"], "class_id": c["id"]}
                doc = {
                    "id": str(uuid.uuid4()),
                    "school_id": school_id,
                    "teacher_id": t["id"],
                    "class_id": c["id"],
                    "is_active": True,
                    "created_at": now,
                }
                try:
                    async with ses.begin_nested():
                        await gd_upsert(ses, "teacher_class_assignments", filt, doc)
                    upserted += 1
                except Exception as e:
                    logger.warning(f"auto-populate upsert failed for teacher={t['id']} class={c['id']}: {e}")
        try:
            await ses.commit()
        except Exception as e:
            logger.warning(f"auto-populate commit failed for school {school_id}: {e}")
            await ses.rollback()
            return 0
        return upserted


async def _ensure_teacher_linked_to_all_classes(school_id: str, teacher_id: str):
    """When a new teacher is created, auto-assign to all classes via bulk upsert."""
    classes = await gd_find(db.session, "classes", {"school_id": school_id, "is_active": {"$ne": False}}, limit=500)
    if not classes:
        return

    settings = await gd_find_one(db.session, "school_settings", {"school_id": school_id})
    academic_year_id = None
    if settings:
        nested = settings.get("settings", {})
        academic_year_id = nested.get("academic_year") or settings.get("academicYear")

    now = datetime.now(timezone.utc).isoformat()
    for c in classes:
        filt = {"school_id": school_id, "teacher_id": teacher_id, "class_id": c["id"]}
        doc = {
            "id": str(uuid.uuid4()),
            "teacher_id": teacher_id,
            "class_id": c["id"],
            "school_id": school_id,
            "is_active": True,
            "created_at": now,
        }
        try:
            async with db.session.begin_nested():
                await gd_upsert(db.session, "teacher_class_assignments", filt, doc)
        except Exception as e:
            logger.warning(f"_ensure_teacher_linked upsert failed teacher={teacher_id} class={c['id']}: {e}")


async def _ensure_class_linked_to_all_teachers(school_id: str, class_id: str):
    """When a new class is created, auto-assign all teachers to it via bulk upsert."""
    teachers = await gd_find(db.session, "teachers", {"school_id": school_id, "is_active": {"$ne": False}}, limit=2000)
    if not teachers:
        return

    settings = await gd_find_one(db.session, "school_settings", {"school_id": school_id})
    academic_year_id = None
    if settings:
        nested = settings.get("settings", {})
        academic_year_id = nested.get("academic_year") or settings.get("academicYear")

    now = datetime.now(timezone.utc).isoformat()
    for t in teachers:
        filt = {"school_id": school_id, "teacher_id": t["id"], "class_id": class_id}
        doc = {
            "id": str(uuid.uuid4()),
            "teacher_id": t["id"],
            "class_id": class_id,
            "school_id": school_id,
            "is_active": True,
            "created_at": now,
        }
        try:
            async with db.session.begin_nested():
                await gd_upsert(db.session, "teacher_class_assignments", filt, doc)
        except Exception as e:
            logger.warning(f"_ensure_class_linked upsert failed teacher={t['id']} class={class_id}: {e}")


@router.get("/teacher-class-assignments")
async def get_teacher_class_assignments(
    current_user: dict = Depends(get_current_user),
    x_school_context: str = Header(default=None, alias="X-School-Context"),
    page: int = Query(1, ge=1),
    page_size: int = Query(200, ge=1, le=50000),
    teacher_id: str = Query(None),
    class_id: str = Query(None),
):
    """
    جلب إسنادات المعلمين للفصول مع ترقيم الصفحات
    Get teacher-class assignments for the school (paginated).
    Auto-populates all teacher×class pairs on first access.
    """
    school_id = await get_school_id_from_context(current_user, x_school_context)
    if not school_id:
        raise HTTPException(status_code=400, detail="Missing school context")
    
    created = await _auto_populate_teacher_class_assignments(school_id)
    if created > 0:
        logger.info(f"Auto-populated {created} teacher-class assignments for school {school_id}")

    query_filter = {"school_id": school_id}
    if teacher_id:
        query_filter["teacher_id"] = teacher_id
    if class_id:
        query_filter["class_id"] = class_id

    total = await gd_count(db.session, "teacher_class_assignments", query_filter)
    skip = (page - 1) * page_size

    assignments = await gd_find(db.session, "teacher_class_assignments", query_filter, offset=skip, limit=page_size)

    t_ids = list({a.get("teacher_id") for a in assignments if a.get("teacher_id")})
    c_ids = list({a.get("class_id") for a in assignments if a.get("class_id")})

    teachers_list = await gd_find(db.session, "teachers", {"id": {"$in": t_ids}}, limit=len(t_ids) + 1) if t_ids else []
    classes_list = await gd_find(db.session, "classes", {"id": {"$in": c_ids}}, limit=len(c_ids) + 1) if c_ids else []

    teacher_map = {t["id"]: t for t in teachers_list}
    class_map = {c["id"]: c for c in classes_list}

    result = []
    for assignment in assignments:
        tid = assignment.get("teacher_id")
        cid = assignment.get("class_id")
        teacher = teacher_map.get(tid)
        class_doc = class_map.get(cid)

        result.append({
            "id": assignment.get("id"),
            "teacher_id": tid,
            "class_id": cid,
            "school_id": assignment.get("school_id"),
            "academic_year_id": assignment.get("academic_year_id"),
            "teacher_name": teacher.get("full_name") if teacher else None,
            "class_name": f"{class_doc.get('name', '')} - {class_doc.get('section', '')}" if class_doc else None,
            "auto_assigned": assignment.get("auto_assigned", False),
            "created_at": assignment.get("created_at")
        })

    return {
        "data": result,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size
    }

@router.post("/teacher-class-assignments")
async def create_teacher_class_assignment(
    assignment: TeacherClassAssignmentCreate,
    current_user: dict = Depends(get_current_user),
    x_school_context: str = Header(default=None, alias="X-School-Context"),
):
    """
    إنشاء إسناد جديد للمعلم بالفصل
    Create a new teacher-class assignment
    """
    school_id = await get_school_id_from_context(current_user, x_school_context)
    if not school_id:
        raise HTTPException(status_code=400, detail="Missing school context")

    # Verify referenced objects belong to the resolved school
    teacher = await gd_find_one(db.session, "teachers", {"id": assignment.teacher_id, "school_id": school_id})
    if not teacher:
        raise HTTPException(status_code=404, detail="المعلم غير موجود في هذه المدرسة")
    class_doc = await gd_find_one(db.session, "classes", {"id": assignment.class_id, "school_id": school_id})
    if not class_doc:
        raise HTTPException(status_code=404, detail="الفصل غير موجود في هذه المدرسة")
    
    # Check if assignment already exists (model has no academic_year_id column)
    existing = await gd_find_one(db.session, "teacher_class_assignments", {
        "school_id": school_id,
        "teacher_id": assignment.teacher_id,
        "class_id": assignment.class_id,
    })
    
    if existing:
        raise HTTPException(status_code=400, detail="هذا الإسناد موجود بالفعل")
    
    # Get settings for academic year if not provided
    academic_year_id = assignment.academic_year_id
    if not academic_year_id:
        settings = await gd_find_one(db.session, "school_settings", {"school_id": school_id})
        if settings:
            nested = settings.get("settings", {})
            academic_year_id = nested.get("academic_year") or settings.get("academicYear")
    
    # Create new assignment (model has no academic_year_id / updated_at columns)
    new_assignment = {
        "id": str(uuid.uuid4()),
        "teacher_id": assignment.teacher_id,
        "class_id": assignment.class_id,
        "school_id": school_id,
        "is_active": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    
    await gd_insert(db.session, "teacher_class_assignments", new_assignment)
    
    return {
        "message": "تم إنشاء الإسناد بنجاح",
        "assignment": {
            "id": new_assignment["id"],
            "teacher_id": new_assignment["teacher_id"],
            "class_id": new_assignment["class_id"],
            "school_id": new_assignment["school_id"],
            "academic_year_id": academic_year_id,
            "teacher_name": teacher.get("full_name") if teacher else None,
            "class_name": f"{class_doc.get('name', '')} - {class_doc.get('section', '')}" if class_doc else None,
            "created_at": new_assignment["created_at"]
        }
    }

@router.delete("/teacher-class-assignments/{assignment_id}")
async def delete_teacher_class_assignment(
    assignment_id: str,
    current_user: dict = Depends(get_current_user),
    x_school_context: str = Header(default=None, alias="X-School-Context"),
):
    """
    حذف إسناد معلم من فصل
    Delete a teacher-class assignment
    """
    school_id = await get_school_id_from_context(current_user, x_school_context)
    if not school_id:
        raise HTTPException(status_code=400, detail="Missing school context")
    
    result = await gd_delete_one(db.session, "teacher_class_assignments", {
        "id": assignment_id,
        "school_id": school_id
    })
    
    if result == 0:
        raise HTTPException(status_code=404, detail="الإسناد غير موجود")
    
    return {"message": "تم حذف الإسناد بنجاح"}

@router.get("/teacher-class-assignments/classes-without-teachers")
async def get_classes_without_teachers(
    current_user: dict = Depends(get_current_user),
    x_school_context: str = Header(default=None, alias="X-School-Context"),
):
    """
    جلب الفصول التي ليس لها معلمون مسندون
    Get classes without any teacher assignments
    """
    school_id = await get_school_id_from_context(current_user, x_school_context)
    if not school_id:
        raise HTTPException(status_code=400, detail="Missing school context")
    
    # Get all classes
    all_classes = await gd_find(db.session, "classes", {"school_id": school_id}, limit=500)
    
    assigned_class_ids = set(await gd_distinct(db.session, "teacher_class_assignments", "class_id", {"school_id": school_id}))
    
    # Filter unassigned classes
    unassigned = []
    for c in all_classes:
        if c.get("id") not in assigned_class_ids:
            unassigned.append({
                "id": c.get("id"),
                "name": c.get("name"),
                "section": c.get("section"),
                "grade_id": c.get("grade_id")
            })
    
    return {
        "count": len(unassigned),
        "classes": unassigned
    }


# ---------------------------------------------------------------------------
# Teacher ↔ Subject assignments  (collection: teacher_assignments)
# ---------------------------------------------------------------------------

class TeacherSubjectAssignmentCreate(BaseModel):
    teacher_id: str
    subject_id: str
    school_id: Optional[str] = None


@router.get("/teacher-assignments")
async def list_teacher_subject_assignments(
    current_user: dict = Depends(get_current_user),
    x_school_context: str = Header(default=None, alias="X-School-Context"),
    teacher_id: Optional[str] = Query(None),
    subject_id: Optional[str] = Query(None),
):
    """قائمة إسنادات المعلمين بالمواد — Teacher ↔ Subject assignments."""
    school_id = await get_school_id_from_context(current_user, x_school_context)
    if not school_id:
        raise HTTPException(status_code=400, detail="Missing school context")

    query_filter: Dict[str, Any] = {"school_id": school_id, "is_active": True}
    if teacher_id:
        query_filter["teacher_id"] = teacher_id
    if subject_id:
        query_filter["subject_id"] = subject_id

    assignments = await gd_find(db.session, "teacher_assignments", query_filter, limit=5000)

    t_ids = list({a.get("teacher_id") for a in assignments if a.get("teacher_id")})
    s_ids = list({a.get("subject_id") for a in assignments if a.get("subject_id")})
    teachers_list = await gd_find(db.session, "teachers", {"id": {"$in": t_ids}}, limit=len(t_ids) + 1) if t_ids else []
    subjects_list = await gd_find(db.session, "subjects", {"id": {"$in": s_ids}}, limit=len(s_ids) + 1) if s_ids else []
    teacher_map = {t["id"]: t for t in teachers_list}
    subject_map = {s["id"]: s for s in subjects_list}

    result = []
    for a in assignments:
        t = teacher_map.get(a.get("teacher_id"))
        s = subject_map.get(a.get("subject_id"))
        result.append({
            "id": a.get("id"),
            "teacher_id": a.get("teacher_id"),
            "subject_id": a.get("subject_id"),
            "school_id": a.get("school_id"),
            "teacher_name": t.get("full_name") if t else None,
            "subject_name": (s.get("name_ar") or s.get("name")) if s else None,
            "created_at": a.get("created_at"),
        })
    return result


@router.post("/teacher-assignments")
async def create_teacher_subject_assignment(
    payload: TeacherSubjectAssignmentCreate,
    current_user: dict = Depends(get_current_user),
    x_school_context: str = Header(default=None, alias="X-School-Context"),
):
    """إنشاء إسناد مادة لمعلم — Assign a subject to a teacher."""
    school_id = await get_school_id_from_context(current_user, x_school_context)
    if not school_id:
        raise HTTPException(status_code=400, detail="Missing school context")

    # Verify referenced objects belong to the resolved school
    teacher = await gd_find_one(db.session, "teachers", {"id": payload.teacher_id, "school_id": school_id})
    if not teacher:
        raise HTTPException(status_code=404, detail="المعلم غير موجود في هذه المدرسة")
    subject = await gd_find_one(db.session, "subjects", {
        "id": payload.subject_id,
        "$or": [{"school_id": school_id}, {"is_global": True}],
    })
    if not subject:
        raise HTTPException(status_code=404, detail="المادة غير موجودة في هذه المدرسة")

    existing = await gd_find_one(db.session, "teacher_assignments", {
        "school_id": school_id,
        "teacher_id": payload.teacher_id,
        "subject_id": payload.subject_id,
        "is_active": True,
    })
    if existing:
        return {
            "message": "هذا الإسناد موجود بالفعل",
            "assignment": {
                "id": existing.get("id"),
                "teacher_id": existing.get("teacher_id"),
                "subject_id": existing.get("subject_id"),
                "school_id": existing.get("school_id"),
            },
        }

    new_assignment = {
        "id": str(uuid.uuid4()),
        "teacher_id": payload.teacher_id,
        "subject_id": payload.subject_id,
        "school_id": school_id,
        "teacher_name": teacher.get("full_name") if teacher else None,
        "subject_name": (subject.get("name_ar") or subject.get("name")) if subject else None,
        "is_active": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await gd_insert(db.session, "teacher_assignments", new_assignment)

    return {
        "message": "تم إنشاء الإسناد بنجاح",
        "assignment": new_assignment,
    }


@router.delete("/teacher-assignments/{assignment_id}")
async def delete_teacher_subject_assignment(
    assignment_id: str,
    current_user: dict = Depends(get_current_user),
    x_school_context: str = Header(default=None, alias="X-School-Context"),
):
    """حذف إسناد مادة من معلم — Remove a teacher↔subject assignment."""
    school_id = await get_school_id_from_context(current_user, x_school_context)
    if not school_id:
        raise HTTPException(status_code=400, detail="Missing school context")

    result = await gd_delete_one(db.session, "teacher_assignments", {
        "id": assignment_id,
        "school_id": school_id,
    })
    if result == 0:
        raise HTTPException(status_code=404, detail="الإسناد غير موجود")
    return {"message": "تم حذف الإسناد بنجاح"}


@router.get("/teacher-class-assignments/teacher/{teacher_id}")
async def get_teacher_assignments(
    teacher_id: str,
    current_user: dict = Depends(get_current_user),
    x_school_context: str = Header(default=None, alias="X-School-Context"),
):
    """
    جلب الفصول المسندة لمعلم معين
    Get all class assignments for a specific teacher
    """
    school_id = await get_school_id_from_context(current_user, x_school_context)
    if not school_id:
        raise HTTPException(status_code=400, detail="Missing school context")
    
    assignments = await gd_find(db.session, "teacher_class_assignments", {
        "school_id": school_id,
        "teacher_id": teacher_id
    }, limit=500)
    
    class_ids = list({a.get("class_id") for a in assignments if a.get("class_id")})
    classes_docs = await gd_find(db.session, "classes", {"id": {"$in": class_ids}}, limit=500) if class_ids else []
    class_map = {c["id"]: c for c in classes_docs}

    result = []
    for assignment in assignments:
        class_doc = class_map.get(assignment.get("class_id"))
        if class_doc:
            result.append({
                "id": assignment.get("id"),
                "class_id": assignment.get("class_id"),
                "class_name": class_doc.get("name"),
                "section": class_doc.get("section"),
                "grade_id": class_doc.get("grade_id")
            })

    return result

