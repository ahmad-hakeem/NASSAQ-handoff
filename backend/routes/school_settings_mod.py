"""
NASSAQ Route Module: School settings, work days, holidays, timing, breaks, constraints, teacher-class assignments
Auto-consolidated during Phase 8 modularization.
"""
from fastapi import APIRouter, HTTPException, Depends, status, Header, Query, Body, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import Response
from starlette.responses import StreamingResponse
from pydantic import BaseModel, Field, ConfigDict, EmailStr, model_validator
from typing import List, Optional, Any, Dict
from datetime import datetime, timezone, timedelta
from bson_compat import ObjectId
import uuid, os, logging, json, random, re, io, base64
from bson_compat import UpdateOne

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
    settings = await db.school_settings.find_one({"school_id": school_id}, {"_id": 0})
    if not settings:
        return {"regenerated": False, "reason": "no_settings"}

    timing = settings.get("timing", {})
    day_start = (settings.get("school_day_start")
                 or settings.get("settings", {}).get("school_day_start")
                 or timing.get("start")
                 or "07:00")
    try:
        parts = day_start.split(":")
        if len(parts) != 2 or not (0 <= int(parts[0]) <= 23 and 0 <= int(parts[1]) <= 59):
            day_start = "07:00"
    except (ValueError, AttributeError):
        day_start = "07:00"

    periods = min(max(int(settings.get("periods_per_day") or settings.get("settings", {}).get("periods_per_day") or 7), 1), 12)
    period_dur = min(max(int(settings.get("period_duration_minutes") or settings.get("settings", {}).get("period_duration_minutes") or 45), 20), 90)
    break_dur = min(max(int(settings.get("break_duration_minutes") or settings.get("settings", {}).get("break_duration_minutes") or 15), 5), 60)
    prayer_dur = min(max(int(settings.get("prayer_duration_minutes") or settings.get("settings", {}).get("prayer_duration_minutes") or 20), 5), 60)

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

    await db.time_slots.delete_many({"school_id": school_id})
    if slots:
        await db.time_slots.insert_many(slots)

    final_h, final_m = divmod(current_minutes, 60)
    day_end = f"{final_h:02d}:{final_m:02d}"
    await db.school_settings.update_one(
        {"school_id": school_id},
        {"$set": {
            "school_day_end": day_end,
            "settings.school_day_end": day_end,
        }}
    )

    return {"regenerated": True, "count": len(slots), "day_end": day_end}


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
    principal_name: Optional[str] = None


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
    start: str
    end: str


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
    if x_school_context:
        return x_school_context
    return current_user.get("tenant_id")

@router.get("/school/info")
async def get_school_info(
    current_user: dict = Depends(get_current_user),
    x_school_context: str = Header(default=None, alias="X-School-Context")
):
    """Get school basic info - جلب معلومات المدرسة الأساسية"""
    school_id = await get_school_id_from_context(current_user, x_school_context)
    
    if not school_id:
        raise HTTPException(status_code=400, detail="School context required")
    
    school = await db.schools.find_one({"id": school_id}, {"_id": 0})
    if not school:
        return {}
    
    # Get school settings too
    settings = await db.school_settings.find_one({"school_id": school_id}, {"_id": 0})
    
    return {
        "id": school.get("id"),
        "name": school.get("name"),
        "name_ar": school.get("name_ar", school.get("name")),
        "school_name_ar": school.get("name_ar", school.get("name")),
        "name_en": school.get("name_en"),
        "type": school.get("type"),
        "stage": school.get("stage"),
        "city": school.get("city"),
        "region": school.get("region"),
        "address": school.get("address"),
        "phone": school.get("phone"),
        "email": school.get("email"),
        "license_number": school.get("license_number"),
        "principal_name": school.get("principal_name"),
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

    old_school = await db.schools.find_one({"id": school_id}, {"_id": 0})
    if not old_school:
        raise HTTPException(status_code=404, detail="المدرسة غير موجودة")

    update_data = {k: v for k, v in data.model_dump().items() if v is not None}
    # school code (license_number) is read-only — never allow changing it
    update_data.pop("license_number", None)
    update_data.pop("id", None)
    # Keep name_ar and name in sync
    if "name_ar" in update_data and "name" not in update_data:
        update_data["name"] = update_data["name_ar"]
    elif "name" in update_data and "name_ar" not in update_data:
        update_data["name_ar"] = update_data["name"]

    update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
    await db.schools.update_one({"id": school_id}, {"$set": update_data})

    # Audit log
    await db.audit_logs.insert_one({
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

    school = await db.schools.find_one({"id": school_id}, {"_id": 0})
    return {"success": True, "school": school, "message": "تم تحديث بيانات المدرسة بنجاح"}

@router.get("/school/day-status")
async def get_school_day_status(
    current_user: dict = Depends(get_current_user),
    x_school_context: str = Header(default=None, alias="X-School-Context")
):
    school_id = await get_school_id_from_context(current_user, x_school_context)
    if not school_id:
        raise HTTPException(status_code=400, detail="School context required")

    settings = await db.school_settings.find_one({"school_id": school_id}, {"_id": 0})
    nested = (settings or {}).get("settings", {}) if settings else {}

    day_start_str = nested.get("school_day_start") or (settings or {}).get("school_day_start") or "07:00"
    day_end_str = nested.get("school_day_end") or (settings or {}).get("school_day_end") or "13:15"
    periods_per_day = nested.get("periods_per_day") or (settings or {}).get("periods_per_day") or 7

    time_slots_raw = await db.time_slots.find(
        {"school_id": school_id},
        {"_id": 0, "start_time": 1, "end_time": 1, "is_break": 1, "name": 1, "name_en": 1, "order": 1}
    ).sort("start_time", 1).to_list(30)

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

    working_days = (settings or {}).get("working_days", nested.get("working_days", {}))
    day_names_map = {6: "sunday", 0: "monday", 1: "tuesday", 2: "wednesday", 3: "thursday", 4: "friday", 5: "saturday"}
    now = datetime.now()
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
    school = await db.schools.find_one({"id": school_id}, {"_id": 0})
    
    # Get school-specific settings
    settings = await db.school_settings.find_one({"school_id": school_id}, {"_id": 0})
    
    if not settings:
        # Get default settings template and create school-specific settings
        default_settings = await db.default_settings.find_one({"id": "default-school-settings"}, {"_id": 0})
        
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
        await db.school_settings.insert_one(settings)
    
    # Get reference data from academic structure
    academic_stages = await db.academic_stages.find({"is_active": True}, {"_id": 0}).sort("order", 1).to_list(10)
    academic_grades = await db.academic_grades.find({"is_active": True}, {"_id": 0}).sort("order", 1).to_list(50)
    education_tracks = await db.education_tracks.find({"is_active": True}, {"_id": 0}).to_list(10)
    subjects = await db.subjects.find({"is_active": True}, {"_id": 0}).to_list(50)
    teacher_ranks = await db.teacher_ranks.find({"is_active": True}, {"_id": 0}).sort("order", 1).to_list(20)
    admin_constraints = await db.admin_constraints.find({"is_active": True}, {"_id": 0}).to_list(50)
    
    # Get school-specific data
    sections = await db.classes.find({"school_id": school_id}, {"_id": 0}).to_list(200)
    terms = await db.academic_terms.find({"school_id": school_id}, {"_id": 0}).to_list(10)
    
    # Extract settings nested values
    nested_settings = settings.get("settings", {})
    
    return {
        "school_info": school or {},
        "settings": settings,
        # Frontend-compatible field names - try nested first, then direct
        "academicYear": nested_settings.get("academic_year") or settings.get("academic_year", ""),
        "currentSemester": nested_settings.get("current_semester") or settings.get("current_semester", ""),
        "dayStart": nested_settings.get("school_day_start") or settings.get("school_day_start", "07:00"),
        "dayEnd": nested_settings.get("school_day_end") or settings.get("school_day_end", "13:15"),
        "periodsPerDay": nested_settings.get("periods_per_day") or settings.get("periods_per_day", 7),
        "periodDuration": nested_settings.get("period_duration_minutes") or settings.get("period_duration_minutes", 45),
        "breakDuration": nested_settings.get("break_duration_minutes") or settings.get("break_duration_minutes", 20),
        "workingDays": nested_settings.get("working_days") or settings.get("working_days_ar", []),
        "weekendDays": nested_settings.get("weekend_days") or settings.get("weekend_days_ar", []),
        "breaks": settings.get("breaks", []),
        # Original field names for backward compatibility
        "working_days": settings.get("working_days", {}),
        "periods_per_day": settings.get("periods_per_day", 7),
        "time_slots": settings.get("time_slots", []),
        "school_day_start": settings.get("school_day_start", "07:00"),
        "school_day_end": settings.get("school_day_end", "13:15"),
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
    
    logs = await db.audit_logs.find(
        query, 
        {"_id": 0}
    ).sort("timestamp", -1).limit(limit).to_list(limit)
    
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
    old_school = await db.schools.find_one({"id": school_id}, {"_id": 0})
    
    update_data = {k: v for k, v in data.model_dump().items() if v is not None}
    update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
    update_data["updated_by"] = current_user["id"]
    
    await db.schools.update_one(
        {"id": school_id},
        {"$set": update_data}
    )
    
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
    await db.audit_logs.insert_one(audit_log)
    
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
    old_settings = await db.school_settings.find_one({"school_id": school_id}, {"_id": 0})
    old_work_days = old_settings.get("work_days", {}) if old_settings else {}
    
    # Convert to Arabic day names
    day_names_ar = {
        'sunday': 'الأحد', 'monday': 'الإثنين', 'tuesday': 'الثلاثاء',
        'wednesday': 'الأربعاء', 'thursday': 'الخميس', 'friday': 'الجمعة', 'saturday': 'السبت'
    }
    
    working_days_ar = [day_names_ar[day] for day, active in data.model_dump().items() if active]
    weekend_days_ar = [day_names_ar[day] for day, active in data.model_dump().items() if not active]
    
    working_days_dict = data.model_dump()
    await db.school_settings.update_one(
        {"school_id": school_id},
        {
            "$set": {
                "work_days": working_days_dict,
                "working_days": working_days_dict,
                "working_days_ar": working_days_ar,
                "weekend_days_ar": weekend_days_ar,
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "updated_by": current_user["id"]
            }
        },
        upsert=True
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
    await db.audit_logs.insert_one(audit_log)
    
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
    
    await db.school_settings.update_one(
        {"school_id": school_id},
        {"$push": {"official_holidays": holiday}},
        upsert=True
    )
    
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
    
    await db.school_settings.update_one(
        {"school_id": school_id},
        {"$pull": {"official_holidays": {"id": holiday_id}}}
    )
    
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

    # Map frontend field names to both locations (root and nested settings)
    field_mappings = {
        "academicYear": ("settings.academic_year", "academic_year"),
        "currentSemester": ("settings.current_semester", "current_semester"),
        "dayStart": ("settings.school_day_start", "school_day_start"),
        "dayEnd": ("settings.school_day_end", "school_day_end"),
        "periodsPerDay": ("settings.periods_per_day", "periods_per_day"),
        "periodDuration": ("settings.period_duration_minutes", "period_duration_minutes"),
        "breakDuration": ("settings.break_duration_minutes", "break_duration_minutes"),
        "workingDays": ("settings.working_days_ar", "working_days_ar"),
        "weekendDays": ("settings.weekend_days", "weekend_days_ar"),
        # Also support direct settings.* keys
        "school_day_start": ("settings.school_day_start", "school_day_start"),
        "school_day_end": ("settings.school_day_end", "school_day_end"),
        "periods_per_day": ("settings.periods_per_day", "periods_per_day"),
        "period_duration_minutes": ("settings.period_duration_minutes", "period_duration_minutes"),
        "break_duration_minutes": ("settings.break_duration_minutes", "break_duration_minutes"),
        "prayer_duration_minutes": ("settings.prayer_duration_minutes", "prayer_duration_minutes"),
        "time_slots": ("settings.time_slots", "time_slots"),
    }
    
    for frontend_key, (nested_key, root_key) in field_mappings.items():
        if frontend_key in settings_data:
            update_data[nested_key] = settings_data[frontend_key]
            update_data[root_key] = settings_data[frontend_key]
    
    if "breaks" in settings_data and isinstance(settings_data["breaks"], list):
        breaks_data = []
        for b in settings_data["breaks"]:
            if not b.get("id"):
                b["id"] = str(uuid.uuid4())
            breaks_data.append(b)
        update_data["breaks"] = breaks_data

    # Get old settings for audit log
    old_settings = await db.school_settings.find_one({"school_id": school_id}, {"_id": 0}) or {}

    # Update school_settings collection
    await db.school_settings.update_one(
        {"school_id": school_id},
        {"$set": update_data},
        upsert=True
    )

    # Also update time_slots collection if time_slots provided
    if "time_slots" in settings_data:
        # Delete old time slots
        await db.time_slots.delete_many({"school_id": school_id})

        # Insert new time slots
        for slot in settings_data["time_slots"]:
            slot_doc = {
                "id": str(uuid.uuid4()),
                "school_id": school_id,
                **slot,
                "created_at": datetime.now(timezone.utc).isoformat()
            }
            await db.time_slots.insert_one(slot_doc)

    # Audit log — record every settings save
    changed_keys = [k for k in update_data if k != "updated_at" and old_settings.get(k) != update_data[k]]
    if changed_keys or "soft_constraints" in settings_data:
        await db.audit_logs.insert_one({
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
    constraints = await db.timetable_hard_constraints.find(
        {"is_system": True},
        {"_id": 0}
    ).sort("order", 1).to_list(50)

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
    constraints = await db.timetable_soft_constraints.find(
        {},
        {"_id": 0}
    ).sort("order", 1).to_list(50)

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
    constraint = await db.timetable_soft_constraints.find_one({"code": code})
    if not constraint:
        raise HTTPException(status_code=404, detail="القيد غير موجود")

    update = {"updated_at": datetime.now(timezone.utc).isoformat()}
    if "is_active" in data:
        update["is_active"] = data["is_active"]
    if "weight" in data:
        w = data["weight"]
        if isinstance(w, int) and 1 <= w <= 10:
            update["weight"] = w

    await db.timetable_soft_constraints.update_one({"code": code}, {"$set": update})
    return {"success": True, "message": "تم تحديث القيد التفضيلي بنجاح"}


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
    result = await db.reference_admin_constraints.update_one(
        {"id": constraint_id},
        {"$set": update_data}
    )
    
    if result.matched_count == 0:
        # Try admin_constraints collection
        result = await db.admin_constraints.update_one(
            {"id": constraint_id},
            {"$set": update_data}
        )
    
    if result.matched_count == 0:
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
    
    await db.school_settings.update_one(
        {"school_id": school_id},
        {"$push": {"exception_days": exception}},
        upsert=True
    )
    
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
    
    await db.school_settings.update_one(
        {"school_id": school_id},
        {"$pull": {"exception_days": {"id": exception_id}}}
    )
    
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
    
    await db.school_settings.update_one(
        {"school_id": school_id},
        {
            "$set": {
                "periods_per_day": periods,
                "updated_at": datetime.now(timezone.utc).isoformat()
            }
        },
        upsert=True
    )
    
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
    
    await db.school_settings.update_one(
        {"school_id": school_id},
        {
            "$set": {
                "timing": data.model_dump(),
                "school_day_start": data.start,
                "school_day_end": data.end,
                "settings.school_day_start": data.start,
                "settings.school_day_end": data.end,
                "updated_at": datetime.now(timezone.utc).isoformat()
            }
        },
        upsert=True
    )
    
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
    
    await db.school_settings.update_one(
        {"school_id": school_id},
        {
            "$set": {
                "breaks": breaks_data,
                "updated_at": datetime.now(timezone.utc).isoformat()
            }
        },
        upsert=True
    )
    
    regen_result = await regenerate_time_slots_from_settings(school_id)
    return {"message": "تم تحديث فترات الاستراحة", "breaks": breaks_data, "time_slots_regenerated": regen_result}


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
    
    await db.school_settings.update_one(
        {"school_id": school_id},
        {"$push": {"activity_days": activity}},
        upsert=True
    )
    
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
    
    await db.school_settings.update_one(
        {"school_id": school_id},
        {"$pull": {"activity_days": {"id": activity_id}}}
    )
    
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
    
    await db.school_settings.update_one(
        {"school_id": school_id},
        {
            "$set": {
                "teaching_loads": loads,
                "updated_at": datetime.now(timezone.utc).isoformat()
            }
        },
        upsert=True
    )
    
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
    
    await db.school_settings.update_one(
        {"school_id": school_id},
        {
            "$set": {
                f"teacher_availability.{data.teacher_id}": {
                    "available_days": data.available_days,
                    "available_periods": data.available_periods
                },
                "updated_at": datetime.now(timezone.utc).isoformat()
            }
        },
        upsert=True
    )
    
    return {"message": "تم تحديث توفر المعلم"}


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
    
    await db.school_settings.update_one(
        {"school_id": school_id},
        {
            "$set": {
                "constraints": constraints_data,
                "updated_at": datetime.now(timezone.utc).isoformat()
            }
        },
        upsert=True
    )
    
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
    Uses bulk upsert for concurrency safety (idempotent).
    """
    teachers = await db.teachers.find(
        {"school_id": school_id, "is_active": {"$ne": False}},
        {"id": 1, "_id": 0}
    ).to_list(2000)
    classes = await db.classes.find(
        {"school_id": school_id, "is_active": {"$ne": False}},
        {"id": 1, "_id": 0}
    ).to_list(500)

    if not teachers or not classes:
        return 0

    existing_count = await db.teacher_class_assignments.count_documents({"school_id": school_id})
    expected_total = len(teachers) * len(classes)
    if existing_count >= expected_total:
        return 0

    settings = await db.school_settings.find_one({"school_id": school_id})
    academic_year_id = None
    if settings:
        nested = settings.get("settings", {})
        academic_year_id = nested.get("academic_year") or settings.get("academicYear")

    now = datetime.now(timezone.utc).isoformat()
    ops = []
    for t in teachers:
        for c in classes:
            filt = {"school_id": school_id, "teacher_id": t["id"], "class_id": c["id"]}
            ops.append(UpdateOne(
                filt,
                {"$setOnInsert": {
                    "id": str(uuid.uuid4()),
                    "school_id": school_id,
                    "teacher_id": t["id"],
                    "class_id": c["id"],
                    "academic_year_id": academic_year_id,
                    "auto_assigned": True,
                    "created_at": now,
                    "updated_at": now,
                }},
                upsert=True,
            ))

    if ops:
        result = await db.teacher_class_assignments.bulk_write(ops, ordered=False)
        return result.upserted_count
    return 0


async def _ensure_teacher_linked_to_all_classes(school_id: str, teacher_id: str):
    """When a new teacher is created, auto-assign to all classes via bulk upsert."""
    classes = await db.classes.find(
        {"school_id": school_id, "is_active": {"$ne": False}},
        {"id": 1, "_id": 0}
    ).to_list(500)
    if not classes:
        return

    settings = await db.school_settings.find_one({"school_id": school_id})
    academic_year_id = None
    if settings:
        nested = settings.get("settings", {})
        academic_year_id = nested.get("academic_year") or settings.get("academicYear")

    now = datetime.now(timezone.utc).isoformat()
    ops = []
    for c in classes:
        filt = {"school_id": school_id, "teacher_id": teacher_id, "class_id": c["id"]}
        ops.append(UpdateOne(
            filt,
            {"$setOnInsert": {
                "id": str(uuid.uuid4()),
                "teacher_id": teacher_id,
                "class_id": c["id"],
                "school_id": school_id,
                "academic_year_id": academic_year_id,
                "auto_assigned": True,
                "created_at": now,
                "updated_at": now,
            }},
            upsert=True,
        ))
    if ops:
        await db.teacher_class_assignments.bulk_write(ops, ordered=False)


async def _ensure_class_linked_to_all_teachers(school_id: str, class_id: str):
    """When a new class is created, auto-assign all teachers to it via bulk upsert."""
    teachers = await db.teachers.find(
        {"school_id": school_id, "is_active": {"$ne": False}},
        {"id": 1, "_id": 0}
    ).to_list(2000)
    if not teachers:
        return

    settings = await db.school_settings.find_one({"school_id": school_id})
    academic_year_id = None
    if settings:
        nested = settings.get("settings", {})
        academic_year_id = nested.get("academic_year") or settings.get("academicYear")

    now = datetime.now(timezone.utc).isoformat()
    ops = []
    for t in teachers:
        filt = {"school_id": school_id, "teacher_id": t["id"], "class_id": class_id}
        ops.append(UpdateOne(
            filt,
            {"$setOnInsert": {
                "id": str(uuid.uuid4()),
                "teacher_id": t["id"],
                "class_id": class_id,
                "school_id": school_id,
                "academic_year_id": academic_year_id,
                "auto_assigned": True,
                "created_at": now,
                "updated_at": now,
            }},
            upsert=True,
        ))
    if ops:
        await db.teacher_class_assignments.bulk_write(ops, ordered=False)


@router.get("/teacher-class-assignments")
async def get_teacher_class_assignments(
    request: Request,
    current_user: dict = Depends(get_current_user)
):
    """
    جلب جميع إسنادات المعلمين للفصول
    Get all teacher-class assignments for the school.
    Auto-populates all teacher×class pairs on first access.
    """
    school_id = request.headers.get("X-School-Context") or current_user.get("tenant_id")
    if not school_id:
        raise HTTPException(status_code=400, detail="Missing school context")
    
    created = await _auto_populate_teacher_class_assignments(school_id)
    if created > 0:
        logger.info(f"Auto-populated {created} teacher-class assignments for school {school_id}")

    assignments = await db.teacher_class_assignments.find(
        {"school_id": school_id}
    ).to_list(50000)

    teacher_ids = list({a.get("teacher_id") for a in assignments if a.get("teacher_id")})
    class_ids = list({a.get("class_id") for a in assignments if a.get("class_id")})

    teachers_list = await db.teachers.find({"id": {"$in": teacher_ids}}).to_list(2000) if teacher_ids else []
    classes_list = await db.classes.find({"id": {"$in": class_ids}}).to_list(500) if class_ids else []

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

    return result

@router.post("/teacher-class-assignments")
async def create_teacher_class_assignment(
    assignment: TeacherClassAssignmentCreate,
    request: Request,
    current_user: dict = Depends(get_current_user)
):
    """
    إنشاء إسناد جديد للمعلم بالفصل
    Create a new teacher-class assignment
    """
    school_id = request.headers.get("X-School-Context") or current_user.get("tenant_id")
    if not school_id:
        raise HTTPException(status_code=400, detail="Missing school context")
    
    # Check if assignment already exists
    existing = await db.teacher_class_assignments.find_one({
        "school_id": school_id,
        "teacher_id": assignment.teacher_id,
        "class_id": assignment.class_id,
        "academic_year_id": assignment.academic_year_id
    })
    
    if existing:
        raise HTTPException(status_code=400, detail="هذا الإسناد موجود بالفعل")
    
    # Get settings for academic year if not provided
    academic_year_id = assignment.academic_year_id
    if not academic_year_id:
        settings = await db.school_settings.find_one({"school_id": school_id})
        if settings:
            nested = settings.get("settings", {})
            academic_year_id = nested.get("academic_year") or settings.get("academicYear")
    
    # Create new assignment
    new_assignment = {
        "id": str(uuid.uuid4()),
        "teacher_id": assignment.teacher_id,
        "class_id": assignment.class_id,
        "school_id": school_id,
        "academic_year_id": academic_year_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.teacher_class_assignments.insert_one(new_assignment)
    
    # Get teacher and class names for response
    teacher = await db.teachers.find_one({"id": assignment.teacher_id})
    class_doc = await db.classes.find_one({"id": assignment.class_id})
    
    return {
        "message": "تم إنشاء الإسناد بنجاح",
        "assignment": {
            "id": new_assignment["id"],
            "teacher_id": new_assignment["teacher_id"],
            "class_id": new_assignment["class_id"],
            "school_id": new_assignment["school_id"],
            "academic_year_id": new_assignment["academic_year_id"],
            "teacher_name": teacher.get("full_name") if teacher else None,
            "class_name": f"{class_doc.get('name', '')} - {class_doc.get('section', '')}" if class_doc else None,
            "created_at": new_assignment["created_at"]
        }
    }

@router.delete("/teacher-class-assignments/{assignment_id}")
async def delete_teacher_class_assignment(
    assignment_id: str,
    request: Request,
    current_user: dict = Depends(get_current_user)
):
    """
    حذف إسناد معلم من فصل
    Delete a teacher-class assignment
    """
    school_id = request.headers.get("X-School-Context") or current_user.get("tenant_id")
    if not school_id:
        raise HTTPException(status_code=400, detail="Missing school context")
    
    result = await db.teacher_class_assignments.delete_one({
        "id": assignment_id,
        "school_id": school_id
    })
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="الإسناد غير موجود")
    
    return {"message": "تم حذف الإسناد بنجاح"}

@router.get("/teacher-class-assignments/classes-without-teachers")
async def get_classes_without_teachers(
    request: Request,
    current_user: dict = Depends(get_current_user)
):
    """
    جلب الفصول التي ليس لها معلمون مسندون
    Get classes without any teacher assignments
    """
    school_id = request.headers.get("X-School-Context") or current_user.get("tenant_id")
    if not school_id:
        raise HTTPException(status_code=400, detail="Missing school context")
    
    # Get all classes
    all_classes = await db.classes.find({"school_id": school_id}).to_list(500)
    
    assigned_class_ids = set(await db.teacher_class_assignments.distinct("class_id", {"school_id": school_id}))
    
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

@router.get("/teacher-class-assignments/teacher/{teacher_id}")
async def get_teacher_assignments(
    teacher_id: str,
    request: Request,
    current_user: dict = Depends(get_current_user)
):
    """
    جلب الفصول المسندة لمعلم معين
    Get all class assignments for a specific teacher
    """
    school_id = request.headers.get("X-School-Context") or current_user.get("tenant_id")
    if not school_id:
        raise HTTPException(status_code=400, detail="Missing school context")
    
    assignments = await db.teacher_class_assignments.find({
        "school_id": school_id,
        "teacher_id": teacher_id
    }).to_list(500)
    
    class_ids = list({a.get("class_id") for a in assignments if a.get("class_id")})
    classes_docs = await db.classes.find(
        {"id": {"$in": class_ids}},
        {"_id": 0, "id": 1, "name": 1, "section": 1, "grade_id": 1}
    ).to_list(500) if class_ids else []
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

