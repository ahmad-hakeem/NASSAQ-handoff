"""
NASSAQ Scheduling Sub-module
"""
from fastapi import APIRouter, HTTPException, Depends, status, Header, Query, Body, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import Response
from starlette.responses import StreamingResponse
from pydantic import BaseModel, Field, ConfigDict, EmailStr, model_validator
from typing import List, Optional, Any, Dict
from datetime import datetime, timezone, timedelta
import uuid, os, logging, json, random, re, io, base64

logger = logging.getLogger("nassaq.scheduling")

from dependencies import (
    db, get_current_user, require_roles, UserRole, SchoolStatus,
    hash_password, verify_password, create_access_token,
    JWT_SECRET, JWT_ALGORITHM, ACCESS_TOKEN_EXPIRE, security,
    audit_engine, AuditAction, AuditSeverity,
    smart_scheduling_engine, TimetableRunStatus, TimetableStatus,
    ConflictType, ConflictSeverity, PreValidationResult, GenerationResult,
    hakim_engine, reporting_engine, export_engine, session_engine,
    REPORT_TYPES, generate_student_qr_code
)
from engines.sql_utils import gd_find, gd_find_one, gd_insert, gd_insert_many, gd_update_one, gd_update_many, gd_count, gd_delete_one, gd_delete_many, gd_distinct


from shared_models import (
    StatusCheck, StatusCheckCreate, TeacherRankEnum, SessionStatusEnum, ScheduleStatusEnum, TimeSlotCreate, TimeSlotResponse, TeacherAssignmentCreate, TeacherAssignmentResponse, SchoolScheduleCreate, SchoolScheduleResponse, ScheduleSessionCreate, ScheduleSessionResponse
)

router = APIRouter()

# ============== SMART TIMETABLE SESSION MANAGEMENT APIs ==============

class UpdateSmartSessionRequest(BaseModel):
    """طلب تعديل حصة في الجدول الذكي"""
    teacher_id: Optional[str] = None
    subject_id: Optional[str] = None
    day_of_week: Optional[str] = None
    period_number: Optional[int] = None


class SwapSessionsRequest(BaseModel):
    """طلب تبديل حصتين"""
    session_id_1: str
    session_id_2: str


@router.put("/smart-scheduling/session/{session_id}")
async def update_smart_session(
    session_id: str,
    request: UpdateSmartSessionRequest,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN]))
):
    """
    تعديل حصة في الجدول الذكي
    Update a session in the smart timetable
    """
    # Get current session
    session = await gd_find_one(db.session, "timetable_sessions", {"id": session_id})
    if not session:
        raise HTTPException(status_code=404, detail="الحصة غير موجودة")
    
    timetable_id = session.get("timetable_id")
    school_id = session.get("school_id")
    
    # Build update
    update_data = {"source_type": "hybrid_adjusted", "updated_at": datetime.now(timezone.utc).isoformat()}
    conflicts = []
    
    new_day = request.day_of_week or session.get("day_of_week")
    new_period = request.period_number or session.get("period_number")
    new_teacher = request.teacher_id or session.get("teacher_id")
    
    # Check for conflicts if moving to new slot
    if request.day_of_week or request.period_number:
        # Check teacher conflict
        teacher_conflict = await gd_find_one(db.session, "timetable_sessions", {
            "timetable_id": timetable_id,
            "teacher_id": new_teacher,
            "day_of_week": new_day,
            "period_number": new_period,
            "id": {"$ne": session_id}
        })
        
        if teacher_conflict:
            conflicts.append({
                "type": "teacher_overlap",
                "message_ar": "المعلم لديه حصة أخرى في هذا الوقت",
                "message_en": "Teacher has another session at this time"
            })
        
        # Check class conflict
        class_conflict = await gd_find_one(db.session, "timetable_sessions", {
            "timetable_id": timetable_id,
            "class_id": session.get("class_id"),
            "day_of_week": new_day,
            "period_number": new_period,
            "id": {"$ne": session_id}
        })
        
        if class_conflict:
            conflicts.append({
                "type": "class_overlap",
                "message_ar": "الفصل لديه حصة أخرى في هذا الوقت",
                "message_en": "Class has another session at this time"
            })
        
        update_data["day_of_week"] = new_day
        update_data["period_number"] = new_period
    
    if request.teacher_id:
        update_data["teacher_id"] = request.teacher_id
        
        # Check teacher conflict with new teacher
        if not request.day_of_week and not request.period_number:
            teacher_conflict = await gd_find_one(db.session, "timetable_sessions", {
                "timetable_id": timetable_id,
                "teacher_id": request.teacher_id,
                "day_of_week": session.get("day_of_week"),
                "period_number": session.get("period_number"),
                "id": {"$ne": session_id}
            })
            
            if teacher_conflict:
                conflicts.append({
                    "type": "teacher_overlap",
                    "message_ar": "المعلم الجديد لديه حصة أخرى في هذا الوقت",
                    "message_en": "New teacher has another session at this time"
                })
    
    if request.subject_id:
        update_data["subject_id"] = request.subject_id
    
    # If there are critical conflicts, return warning but allow override
    if conflicts:
        return {
            "success": False,
            "session_id": session_id,
            "conflicts": conflicts,
            "message_ar": "يوجد تعارضات - يمكنك تأكيد التعديل أو إلغاؤه",
            "message_en": "Conflicts detected - you can confirm or cancel"
        }
    
    # Apply update
    await gd_update_one(db.session, "timetable_sessions", {"id": session_id}, update_data)
    
    return {
        "success": True,
        "session_id": session_id,
        "conflicts": [],
        "message_ar": "تم تعديل الحصة بنجاح",
        "message_en": "Session updated successfully"
    }


@router.put("/smart-scheduling/session/{session_id}/force")
async def force_update_smart_session(
    session_id: str,
    request: UpdateSmartSessionRequest,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN]))
):
    """
    تعديل حصة بالقوة (تجاهل التعارضات)
    Force update a session (ignore conflicts)
    """
    session = await gd_find_one(db.session, "timetable_sessions", {"id": session_id})
    if not session:
        raise HTTPException(status_code=404, detail="الحصة غير موجودة")
    
    update_data = {"source_type": "hybrid_adjusted", "updated_at": datetime.now(timezone.utc).isoformat()}
    
    if request.day_of_week:
        update_data["day_of_week"] = request.day_of_week
    if request.period_number:
        update_data["period_number"] = request.period_number
    if request.teacher_id:
        update_data["teacher_id"] = request.teacher_id
    if request.subject_id:
        update_data["subject_id"] = request.subject_id
    
    await gd_update_one(db.session, "timetable_sessions", {"id": session_id}, update_data)
    
    return {
        "success": True,
        "session_id": session_id,
        "message_ar": "تم تعديل الحصة بالقوة",
        "message_en": "Session force updated"
    }


@router.post("/smart-scheduling/sessions/swap")
async def swap_smart_sessions(
    request: SwapSessionsRequest,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN]))
):
    """
    تبديل حصتين
    Swap two sessions
    """
    session1 = await gd_find_one(db.session, "timetable_sessions", {"id": request.session_id_1})
    session2 = await gd_find_one(db.session, "timetable_sessions", {"id": request.session_id_2})
    
    if not session1 or not session2:
        raise HTTPException(status_code=404, detail="إحدى الحصتين غير موجودة")

    tt_id = session1.get("timetable_id")
    if tt_id != session2.get("timetable_id"):
        raise HTTPException(status_code=400, detail="لا يمكن تبديل حصص من جداول مختلفة")

    school_id = session1.get("school_id")
    user_tenant = current_user.get("tenant_id") or current_user.get("school_id")
    user_role = current_user.get("role", "")
    if user_tenant and school_id != user_tenant and user_role != UserRole.PLATFORM_ADMIN.value:
        raise HTTPException(status_code=403, detail="غير مصرح بالتعديل على هذه المدرسة")

    tt = await gd_find_one(db.session, "timetables", {"id": tt_id})
    if tt and tt.get("status") == "published":
        raise HTTPException(status_code=400, detail="لا يمكن تعديل جدول منشور")

    s1_day = session1.get("day_of_week") or session1.get("day")
    s1_period = session1.get("period_number")
    s1_slot = session1.get("time_slot_id")
    s1_start = session1.get("start_time")
    s1_end = session1.get("end_time")

    s2_day = session2.get("day_of_week") or session2.get("day")
    s2_period = session2.get("period_number")
    s2_slot = session2.get("time_slot_id")
    s2_start = session2.get("start_time")
    s2_end = session2.get("end_time")

    exclude_ids = [request.session_id_1, request.session_id_2]

    t1_conflict = await gd_find_one(db.session, "timetable_sessions", {
        "timetable_id": tt_id,
        "teacher_id": session1.get("teacher_id"),
        "day_of_week": s2_day, "period_number": s2_period,
        "id": {"$nin": exclude_ids}
    })
    if t1_conflict:
        raise HTTPException(status_code=409, detail=f"تعارض: المعلم {session1.get('teacher_name', '')} لديه حصة أخرى في الخانة المستهدفة")

    c1_conflict = await gd_find_one(db.session, "timetable_sessions", {
        "timetable_id": tt_id,
        "class_id": session1.get("class_id"),
        "day_of_week": s2_day, "period_number": s2_period,
        "id": {"$nin": exclude_ids}
    })
    if c1_conflict:
        raise HTTPException(status_code=409, detail=f"تعارض: الفصل {session1.get('class_name', '')} لديه حصة أخرى في الخانة المستهدفة")

    t2_conflict = await gd_find_one(db.session, "timetable_sessions", {
        "timetable_id": tt_id,
        "teacher_id": session2.get("teacher_id"),
        "day_of_week": s1_day, "period_number": s1_period,
        "id": {"$nin": exclude_ids}
    })
    if t2_conflict:
        raise HTTPException(status_code=409, detail=f"تعارض: المعلم {session2.get('teacher_name', '')} لديه حصة أخرى في الخانة المستهدفة")

    c2_conflict = await gd_find_one(db.session, "timetable_sessions", {
        "timetable_id": tt_id,
        "class_id": session2.get("class_id"),
        "day_of_week": s1_day, "period_number": s1_period,
        "id": {"$nin": exclude_ids}
    })
    if c2_conflict:
        raise HTTPException(status_code=409, detail=f"تعارض: الفصل {session2.get('class_name', '')} لديه حصة أخرى في الخانة المستهدفة")

    now = datetime.now(timezone.utc).isoformat()
    
    await gd_update_one(db.session, "timetable_sessions", {"id": request.session_id_1}, {
            "day_of_week": s2_day, "day": s2_day,
            "period_number": s2_period,
            "time_slot_id": s2_slot,
            "start_time": s2_start, "end_time": s2_end,
            "source_type": "hybrid_adjusted",
            "updated_at": now
        })
    
    await gd_update_one(db.session, "timetable_sessions", {"id": request.session_id_2}, {
            "day_of_week": s1_day, "day": s1_day,
            "period_number": s1_period,
            "time_slot_id": s1_slot,
            "start_time": s1_start, "end_time": s1_end,
            "source_type": "hybrid_adjusted",
            "updated_at": now
        })
    
    return {
        "success": True,
        "message_ar": "تم تبديل الحصتين بنجاح",
        "message_en": "Sessions swapped successfully"
    }


class SmartMoveRequest(BaseModel):
    session_id: str
    new_day: str
    new_period: int

@router.post("/smart-scheduling/sessions/move")
async def move_smart_session(
    request: SmartMoveRequest,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN]))
):
    session = await gd_find_one(db.session, "timetable_sessions", {"id": request.session_id})
    if not session:
        raise HTTPException(status_code=404, detail="الحصة غير موجودة")

    tt_id = session.get("timetable_id")
    school_id = session.get("school_id")

    user_tenant = current_user.get("tenant_id") or current_user.get("school_id")
    user_role = current_user.get("role", "")
    if user_tenant and school_id != user_tenant and user_role != UserRole.PLATFORM_ADMIN.value:
        raise HTTPException(status_code=403, detail="غير مصرح بالتعديل على هذه المدرسة")

    tt = await gd_find_one(db.session, "timetables", {"id": tt_id})
    if tt and tt.get("status") == "published":
        raise HTTPException(status_code=400, detail="لا يمكن تعديل جدول منشور")

    teacher_conflict = await gd_find_one(db.session, "timetable_sessions", {
        "timetable_id": tt_id,
        "teacher_id": session.get("teacher_id"),
        "day_of_week": request.new_day,
        "period_number": request.new_period,
        "id": {"$ne": request.session_id}
    })
    if teacher_conflict:
        raise HTTPException(status_code=409, detail=f"تعارض: المعلم {session.get('teacher_name', '')} لديه حصة في نفس الوقت")

    class_conflict = await gd_find_one(db.session, "timetable_sessions", {
        "timetable_id": tt_id,
        "class_id": session.get("class_id"),
        "day_of_week": request.new_day,
        "period_number": request.new_period,
        "id": {"$ne": request.session_id}
    })
    if class_conflict:
        raise HTTPException(status_code=409, detail=f"تعارض: الفصل {session.get('class_name', '')} لديه حصة في نفس الوقت")

    slot = await gd_find_one(db.session, "time_slots", {
        "school_id": school_id,
        "period_number": request.new_period,
        "is_break": {"$ne": True},
        "is_prayer": {"$ne": True}
    })
    if not slot:
        slot = await gd_find_one(db.session, "time_slots", {
            "school_id": school_id,
            "slot_number": request.new_period,
            "is_break": {"$ne": True},
            "is_prayer": {"$ne": True}
        })

    now = datetime.now(timezone.utc).isoformat()
    update_fields = {
        "day_of_week": request.new_day,
        "day": request.new_day,
        "period_number": request.new_period,
        "source_type": "hybrid_adjusted",
        "updated_at": now
    }
    if slot:
        update_fields["time_slot_id"] = slot.get("id")
        update_fields["start_time"] = slot.get("start_time")
        update_fields["end_time"] = slot.get("end_time")

    await gd_update_one(db.session, "timetable_sessions", {"id": request.session_id}, update_fields)

    return {
        "success": True,
        "message_ar": "تم نقل الحصة بنجاح",
        "message_en": "Session moved successfully"
    }


@router.delete("/smart-scheduling/session/{session_id}")
async def delete_smart_session(
    session_id: str,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN]))
):
    """
    حذف حصة من الجدول
    Delete a session from the timetable
    """
    session = await gd_find_one(db.session, "timetable_sessions", {"id": session_id})
    if not session:
        raise HTTPException(status_code=404, detail="الحصة غير موجودة")
    
    await gd_delete_one(db.session, "timetable_sessions", {"id": session_id})
    
    return {
        "success": True,
        "message_ar": "تم حذف الحصة بنجاح",
        "message_en": "Session deleted successfully"
    }


@router.post("/smart-scheduling/session/add")
async def add_smart_session(
    timetable_id: str,
    class_id: str,
    subject_id: str,
    teacher_id: str,
    day_of_week: str,
    period_number: int,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN]))
):
    """
    إضافة حصة يدوية للجدول
    Add a manual session to the timetable
    """
    import uuid
    
    # Get timetable
    timetable = await gd_find_one(db.session, "timetables", {"id": timetable_id})
    if not timetable:
        raise HTTPException(status_code=404, detail="الجدول غير موجود")
    
    school_id = timetable.get("school_id")
    
    # Get class info
    cls = await gd_find_one(db.session, "classes", {"id": class_id})
    grade_id = cls.get("grade_id", "") if cls else ""
    
    # Check for conflicts
    conflicts = []
    
    # Teacher conflict
    teacher_conflict = await gd_find_one(db.session, "timetable_sessions", {
        "timetable_id": timetable_id,
        "teacher_id": teacher_id,
        "day_of_week": day_of_week,
        "period_number": period_number
    })
    
    if teacher_conflict:
        conflicts.append({
            "type": "teacher_overlap",
            "message_ar": "المعلم لديه حصة أخرى في هذا الوقت"
        })
    
    # Class conflict
    class_conflict = await gd_find_one(db.session, "timetable_sessions", {
        "timetable_id": timetable_id,
        "class_id": class_id,
        "day_of_week": day_of_week,
        "period_number": period_number
    })
    
    if class_conflict:
        conflicts.append({
            "type": "class_overlap",
            "message_ar": "الفصل لديه حصة أخرى في هذا الوقت"
        })
    
    if conflicts:
        return {
            "success": False,
            "conflicts": conflicts,
            "message_ar": "يوجد تعارضات - لا يمكن إضافة الحصة"
        }
    
    # Create session
    session_id = str(uuid.uuid4())
    session_doc = {
        "id": session_id,
        "timetable_id": timetable_id,
        "school_id": school_id,
        "class_id": class_id,
        "grade_id": grade_id,
        "subject_id": subject_id,
        "teacher_id": teacher_id,
        "day_of_week": day_of_week,
        "period_number": period_number,
        "start_time": "",
        "end_time": "",
        "session_type": "class",
        "source_type": "manual",
        "status": "scheduled",
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await gd_insert(db.session, "timetable_sessions", session_doc)
    
    return {
        "success": True,
        "session_id": session_id,
        "message_ar": "تم إضافة الحصة بنجاح",
        "message_en": "Session added successfully"
    }





# ============== SESSION SETTINGS (per-subject evaluation pattern) ==============

class SessionSettingsRequest(BaseModel):
    subject_id: str
    participation_enabled: bool = True
    homework_enabled: bool = False
    homework_mode: Optional[str] = "didnt_submit"
    recitation_enabled: bool = False
    recitation_attempts: int = 1
    skills_enabled: bool = False
    custom_skills: List[str] = []

class SessionSettingsResponse(BaseModel):
    id: str
    teacher_id: str
    subject_id: str
    participation_enabled: bool
    homework_enabled: bool
    homework_mode: Optional[str]
    recitation_enabled: bool
    recitation_attempts: int
    skills_enabled: bool
    custom_skills: List[str]


def _verify_teacher_access(teacher_id: str, current_user: dict):
    uid = current_user.get("id", "")
    tid = current_user.get("teacher_id", "")
    role = current_user.get("role", "")
    if role in ("super_admin", "school_admin", "school_sub_admin"):
        return
    if uid != teacher_id and tid != teacher_id:
        raise HTTPException(status_code=403, detail="غير مصرح بالوصول إلى إعدادات معلم آخر")


@router.get("/teacher/{teacher_id}/session-settings")
async def get_session_settings(
    teacher_id: str,
    subject_id: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
):
    _verify_teacher_access(teacher_id, current_user)
    query = {"teacher_id": teacher_id}
    if subject_id:
        query["subject_id"] = subject_id
    settings = await gd_find(db.session, "session_settings", query, limit=100)
    if subject_id and settings:
        return settings[0]
    return settings


@router.put("/teacher/{teacher_id}/session-settings")
async def save_session_settings(
    teacher_id: str,
    request: SessionSettingsRequest,
    current_user: dict = Depends(get_current_user),
):
    _verify_teacher_access(teacher_id, current_user)
    existing = await gd_find_one(db.session, "session_settings", {
        "teacher_id": teacher_id,
        "subject_id": request.subject_id,
    })
    data = {
        "teacher_id": teacher_id,
        "subject_id": request.subject_id,
        "participation_enabled": request.participation_enabled,
        "homework_enabled": request.homework_enabled,
        "homework_mode": request.homework_mode,
        "recitation_enabled": request.recitation_enabled,
        "recitation_attempts": request.recitation_attempts,
        "skills_enabled": request.skills_enabled,
        "custom_skills": request.custom_skills,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    if existing:
        await gd_update_one(db.session, "session_settings", {"id": existing["id"]}, data)
        return {**data, "id": existing["id"]}
    else:
        doc_id = str(uuid.uuid4())
        data["id"] = doc_id
        data["created_at"] = datetime.now(timezone.utc).isoformat()
        await gd_insert(db.session, "session_settings", data)
        return data


# ============== LEGACY ROUTES ==============
@router.get("/")
async def root():
    return {"message": "مرحباً بك في نَسَّق - نظام إدارة المدارس الذكي"}

@router.post("/status", response_model=StatusCheck)
async def create_status_check(input: StatusCheckCreate):
    status_dict = input.model_dump()
    status_obj = StatusCheck(**status_dict)
    doc = status_obj.model_dump()
    doc['timestamp'] = doc['timestamp'].isoformat()
    await gd_insert(db.session, "status_checks", doc)
    return status_obj

@router.get("/status", response_model=List[StatusCheck])
async def get_status_checks():
    status_checks = await gd_find(db.session, "status_checks", {}, limit=1000)
    for check in status_checks:
        if isinstance(check['timestamp'], str):
            check['timestamp'] = datetime.fromisoformat(check['timestamp'])
    return status_checks

# Include the router in the main app



# ============== SESSION MOVE API (Drag & Drop) ==============
class MoveSessionRequest(BaseModel):
    """طلب نقل حصة"""
    new_day_of_week: str
    new_time_slot_id: str

class MoveSessionResponse(BaseModel):
    """استجابة نقل حصة"""
    success: bool
    session_id: str
    old_day: str
    old_time_slot_id: str
    new_day: str
    new_time_slot_id: str
    conflicts: List[dict] = []
    status: str  # 'success', 'conflict_warning', 'hard_conflict'
    message: str
    message_en: str

@router.put("/schedule-sessions/{session_id}/move", response_model=MoveSessionResponse)
async def move_schedule_session(
    session_id: str,
    move_data: MoveSessionRequest,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.SCHOOL_SUB_ADMIN]))
):
    """
    نقل حصة من موقع إلى آخر (Drag & Drop)
    
    يتحقق من:
    1. تعارض المعلم
    2. تعارض الفصل
    3. تعارض القاعة (إن وجدت)
    
    يُرجع:
    - success: تم النقل بنجاح
    - conflict_warning: تم النقل مع وجود تعارض يحتاج مراجعة
    - hard_conflict: تم رفض النقل وإرجاع الحصة
    """
    # Get the session
    session = await gd_find_one(db.session, "schedule_sessions", {"id": session_id})
    if not session:
        raise HTTPException(status_code=404, detail="الحصة غير موجودة")
    
    old_day = session.get("day_of_week")
    old_time_slot_id = session.get("time_slot_id")
    schedule_id = session.get("schedule_id")
    assignment_id = session.get("assignment_id")
    
    # Get assignment details
    assignment = await gd_find_one(db.session, "teacher_assignments", {"id": assignment_id})
    if not assignment:
        raise HTTPException(status_code=404, detail="الإسناد غير موجود")
    
    teacher_id = assignment.get("teacher_id")
    class_id = assignment.get("class_id")
    
    # Validate the new time slot exists
    new_slot = await gd_find_one(db.session, "time_slots", {"id": move_data.new_time_slot_id})
    if not new_slot:
        raise HTTPException(status_code=400, detail="الفترة الزمنية غير موجودة")
    
    # Check for conflicts at the new position
    conflicts = []
    is_hard_conflict = False
    
    # 1. Check teacher conflict
    teacher_conflict = await gd_find_one(db.session, "schedule_sessions", {
        "schedule_id": schedule_id,
        "day_of_week": move_data.new_day_of_week,
        "time_slot_id": move_data.new_time_slot_id,
        "id": {"$ne": session_id},
        "status": {"$ne": SessionStatusEnum.CANCELLED.value}
    })
    
    if teacher_conflict:
        conflict_assignment = await gd_find_one(db.session, "teacher_assignments", {"id": teacher_conflict.get("assignment_id")})
        if conflict_assignment:
            conflict_teacher_id = conflict_assignment.get("teacher_id")
            conflict_class_id = conflict_assignment.get("class_id")
            
            # Check if same teacher
            if conflict_teacher_id == teacher_id:
                teacher_doc = await gd_find_one(db.session, "teachers", {"id": teacher_id})
                teacher_name = teacher_doc.get("full_name", "المعلم") if teacher_doc else "المعلم"
                conflicts.append({
                    "type": "teacher_double_booking",
                    "message": f"المعلم {teacher_name} لديه حصة أخرى في نفس الوقت",
                    "message_en": f"Teacher {teacher_name} has another session at the same time",
                    "severity": "hard",
                    "conflicting_session_id": teacher_conflict.get("id")
                })
                is_hard_conflict = True
            
            # Check if same class
            if conflict_class_id == class_id:
                class_doc = await gd_find_one(db.session, "classes", {"id": class_id})
                class_name = class_doc.get("name", "الفصل") if class_doc else "الفصل"
                conflicts.append({
                    "type": "class_double_booking",
                    "message": f"الفصل {class_name} لديه حصة أخرى في نفس الوقت",
                    "message_en": f"Class {class_name} has another session at the same time",
                    "severity": "hard",
                    "conflicting_session_id": teacher_conflict.get("id")
                })
                is_hard_conflict = True
    
    # If hard conflict, reject the move
    if is_hard_conflict:
        return MoveSessionResponse(
            success=False,
            session_id=session_id,
            old_day=old_day,
            old_time_slot_id=old_time_slot_id,
            new_day=move_data.new_day_of_week,
            new_time_slot_id=move_data.new_time_slot_id,
            conflicts=conflicts,
            status="hard_conflict",
            message="لا يمكن نقل الحصة بسبب تعارض. تم إرجاع الحصة إلى مكانها السابق.",
            message_en="Cannot move session due to conflict. Session returned to original position."
        )
    
    # Perform the move
    await gd_update_one(db.session, "schedule_sessions", {"id": session_id}, {
            "day_of_week": move_data.new_day_of_week,
            "time_slot_id": move_data.new_time_slot_id,
            "updated_at": datetime.now(timezone.utc).isoformat()
        })
    
    # Determine response status
    if conflicts:
        status = "conflict_warning"
        message = "تم نقل الحصة مع وجود تحذيرات. يرجى مراجعة التعارضات."
        message_en = "Session moved with warnings. Please review conflicts."
    else:
        status = "success"
        message = "تم نقل الحصة بنجاح"
        message_en = "Session moved successfully"
    
    return MoveSessionResponse(
        success=True,
        session_id=session_id,
        old_day=old_day,
        old_time_slot_id=old_time_slot_id,
        new_day=move_data.new_day_of_week,
        new_time_slot_id=move_data.new_time_slot_id,
        conflicts=conflicts,
        status=status,
        message=message,
        message_en=message_en
    )



