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
from engines.sql_utils import gd_find, gd_find_one, gd_insert, gd_insert_many, gd_update_one, gd_update_many, gd_count, gd_delete_one, gd_delete_many, gd_distinct, _gd_inc


from shared_models import (
    StatusCheck, StatusCheckCreate, TeacherRankEnum, SessionStatusEnum, ScheduleStatusEnum, TimeSlotCreate, TimeSlotResponse, TeacherAssignmentCreate, TeacherAssignmentResponse, SchoolScheduleCreate, SchoolScheduleResponse, ScheduleSessionCreate, ScheduleSessionResponse
)

router = APIRouter()

# ============== TIME SLOTS ROUTES ==============
@router.post("/time-slots", response_model=TimeSlotResponse)
async def create_time_slot(
    slot_data: TimeSlotCreate,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.SCHOOL_SUB_ADMIN]))
):
    """إنشاء فترة زمنية جديدة"""
    slot_id = str(uuid.uuid4())
    slot_doc = {
        "id": slot_id,
        "school_id": slot_data.school_id,
        "name": slot_data.name,
        "name_en": slot_data.name_en,
        "start_time": slot_data.start_time,
        "end_time": slot_data.end_time,
        "slot_number": slot_data.slot_number,
        "duration_minutes": slot_data.duration_minutes,
        "is_break": slot_data.is_break,
        "is_active": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    await gd_insert(db.session, "time_slots", slot_doc)
    return TimeSlotResponse(**slot_doc)

@router.get("/time-slots", response_model=List[TimeSlotResponse])
async def get_time_slots(
    school_id: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """الحصول على الفترات الزمنية"""
    query = {}
    if school_id:
        query["school_id"] = school_id
    elif current_user.get("role") != UserRole.PLATFORM_ADMIN.value:
        query["school_id"] = current_user.get("tenant_id")
    
    slots = await gd_find(db.session, "time_slots", query, order_by="start_time", desc_order=False, limit=50)
    overall_counter = 0
    period_counter = 0
    for s in slots:
        overall_counter += 1
        if not s.get("is_break", False):
            period_counter += 1
            if not s.get("slot_number"):
                s["slot_number"] = overall_counter
            if not s.get("period_number"):
                s["period_number"] = period_counter
        else:
            if not s.get("slot_number"):
                s["slot_number"] = overall_counter
    return [TimeSlotResponse(**s) for s in slots]

@router.delete("/time-slots/{slot_id}")
async def delete_time_slot(
    slot_id: str,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN]))
):
    """حذف فترة زمنية"""
    result = await gd_update_one(db.session, "time_slots", {"id": slot_id}, {"is_active": False})
    if result == 0:
        raise HTTPException(status_code=404, detail="الفترة الزمنية غير موجودة")
    return {"message": "تم حذف الفترة الزمنية"}




# ============== TEACHER ASSIGNMENTS ROUTES ==============
@router.post("/teacher-assignments", response_model=TeacherAssignmentResponse)
async def create_teacher_assignment(
    assignment_data: TeacherAssignmentCreate,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.SCHOOL_SUB_ADMIN]))
):
    """إسناد معلم لفصل ومادة"""
    school_id = assignment_data.school_id or current_user.get("tenant_id") or current_user.get("school_id")
    
    duplicate_check = {
        "teacher_id": assignment_data.teacher_id,
        "subject_id": assignment_data.subject_id,
        "school_id": school_id,
        "is_active": True
    }
    
    existing = await gd_find_one(db.session, "teacher_assignments", duplicate_check)
    if existing:
        teacher_doc = await gd_find_one(db.session, "teachers", {"id": assignment_data.teacher_id})
        subject_doc = await gd_find_one(db.session, "subjects", {"id": assignment_data.subject_id})
        if not subject_doc:
            subject_doc = await gd_find_one(db.session, "reference_subjects", {"id": assignment_data.subject_id})
        teacher_name = (teacher_doc.get("full_name_ar") or teacher_doc.get("full_name")) if teacher_doc else "المعلم"
        subject_name = (subject_doc.get("name_ar") or subject_doc.get("name")) if subject_doc else "المادة"
        raise HTTPException(
            status_code=409,
            detail=f"هذه المادة ({subject_name}) مسندة بالفعل لهذا المعلم ({teacher_name}). لا يمكن تكرار نفس الإسناد."
        )
    
    assignment_id = str(uuid.uuid4())
    assignment_doc = {
        "id": assignment_id,
        "school_id": school_id,  # already resolved above
        "teacher_id": assignment_data.teacher_id,
        "class_id": assignment_data.class_id,  # Can be None
        "subject_id": assignment_data.subject_id,
        "weekly_sessions": assignment_data.weekly_sessions,
        "academic_year": assignment_data.academic_year,
        "semester": assignment_data.semester,
        "is_active": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    try:
        await gd_insert(db.session, "teacher_assignments", assignment_doc)
    except Exception as e:
        if "duplicate key" in str(e).lower() or "E11000" in str(e):
            raise HTTPException(
                status_code=409,
                detail="هذه المادة مسندة بالفعل لهذا المعلم. لا يمكن تكرار نفس الإسناد."
            )
        raise
    
    # Get names for response (support both naming conventions)
    teacher = await gd_find_one(db.session, "teachers", {"id": assignment_data.teacher_id})
    class_doc = None
    if assignment_data.class_id:
        class_doc = await gd_find_one(db.session, "classes", {"id": assignment_data.class_id})
    
    # Try to get subject from multiple collections
    subject = await gd_find_one(db.session, "subjects", {"id": assignment_data.subject_id})
    if not subject:
        subject = await gd_find_one(db.session, "reference_subjects", {"id": assignment_data.subject_id})
    if not subject:
        subject = await gd_find_one(db.session, "official_curriculum_subjects", {"id": assignment_data.subject_id})
    
    # Audit log
    await gd_insert(db.session, "audit_logs", {
        "id": str(uuid.uuid4()),
        "school_id": school_id,
        "action": "CREATE",
        "entity_type": "teacher_assignment",
        "entity_id": assignment_id,
        "new_data": {
            "teacher_id": assignment_data.teacher_id,
            "subject_id": assignment_data.subject_id,
            "class_id": assignment_data.class_id,
        },
        "performed_by": current_user.get("id"),
        "performed_by_email": current_user.get("email"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

    if "_id" in assignment_doc:
        del assignment_doc["_id"]
    if "periods_per_week" not in assignment_doc:
        assignment_doc["periods_per_week"] = assignment_doc.get("weekly_sessions", 0)

    return TeacherAssignmentResponse(
        **assignment_doc,
        teacher_name=teacher.get("full_name") or teacher.get("full_name_ar") if teacher else None,
        class_name=class_doc.get("name") or class_doc.get("name_ar") if class_doc else None,
        subject_name=subject.get("name") or subject.get("name_ar") if subject else None
    )

@router.get("/teacher-assignments", response_model=List[TeacherAssignmentResponse])
async def get_teacher_assignments(
    school_id: Optional[str] = None,
    teacher_id: Optional[str] = None,
    class_id: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """الحصول على إسنادات المعلمين"""
    query = {"is_active": True}
    if school_id:
        query["school_id"] = school_id
    elif current_user.get("role") != UserRole.PLATFORM_ADMIN.value:
        query["school_id"] = current_user.get("tenant_id")
    
    if teacher_id:
        query["teacher_id"] = teacher_id
    if class_id:
        query["class_id"] = class_id
    
    assignments = await gd_find(db.session, "teacher_assignments", query, limit=500)
    
    # Get all related entities
    teacher_ids = list(set(a.get("teacher_id") for a in assignments))
    class_ids = list(set(a.get("class_id") for a in assignments))
    subject_ids = list(set(a.get("subject_id") for a in assignments))
    
    teachers = await gd_find(db.session, "teachers", {"id": {"$in": teacher_ids}}, limit=100)
    classes = await gd_find(db.session, "classes", {"id": {"$in": class_ids}}, limit=100)
    
    # Try both subjects collection and reference_subjects
    subjects = await gd_find(db.session, "subjects", {"id": {"$in": subject_ids}}, limit=100)
    if not subjects:
        subjects = await gd_find(db.session, "reference_subjects", {"id": {"$in": subject_ids}}, limit=100)
    
    # Support both naming conventions
    teacher_map = {t.get("id"): t.get("full_name") or t.get("full_name_ar") for t in teachers}
    class_map = {c.get("id"): c.get("name") or c.get("name_ar") for c in classes}
    subject_map = {s.get("id"): s.get("name") or s.get("name_ar") for s in subjects}
    
    result = []
    for a in assignments:
        assignment_data = {k: v for k, v in a.items() if k not in ['teacher_name', 'class_name', 'subject_name']}
        semester_val = assignment_data.get("semester", 1)
        if isinstance(semester_val, str):
            semester_map = {"first": 1, "second": 2, "الفصل الأول": 1, "الفصل الثاني": 2, "1": 1, "2": 2}
            semester_val = semester_map.get(semester_val.lower(), 1)
        assignment_data["semester"] = semester_val
        if "periods_per_week" not in assignment_data:
            assignment_data["periods_per_week"] = assignment_data.get("weekly_periods", assignment_data.get("weekly_hours", 0))
        try:
            result.append(TeacherAssignmentResponse(
                **assignment_data,
                teacher_name=teacher_map.get(a.get("teacher_id")),
                class_name=class_map.get(a.get("class_id")),
                subject_name=subject_map.get(a.get("subject_id"))
            ))
        except Exception as e:
            logger.warning(f"Failed to serialize teacher assignment {a.get('id', 'unknown')}: {e}")
    
    return result

class TeacherAssignmentUpdate(BaseModel):
    teacher_id: Optional[str] = None
    class_id: Optional[str] = None
    subject_id: Optional[str] = None
    weekly_sessions: Optional[int] = None
    is_active: Optional[bool] = None

@router.put("/teacher-assignments/{assignment_id}")
async def update_teacher_assignment(
    assignment_id: str,
    update_data: TeacherAssignmentUpdate,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN]))
):
    """تحديث إسناد معلم"""
    assignment = await gd_find_one(db.session, "teacher_assignments", {"id": assignment_id})
    if not assignment:
        raise HTTPException(status_code=404, detail="الإسناد غير موجود")
    
    update_dict = {"updated_at": datetime.now(timezone.utc).isoformat()}
    if update_data.teacher_id is not None:
        update_dict["teacher_id"] = update_data.teacher_id
    if update_data.class_id is not None:
        update_dict["class_id"] = update_data.class_id
    if update_data.subject_id is not None:
        update_dict["subject_id"] = update_data.subject_id
    if update_data.weekly_sessions is not None:
        update_dict["weekly_sessions"] = update_data.weekly_sessions
    if update_data.is_active is not None:
        update_dict["is_active"] = update_data.is_active
    
    await gd_update_one(db.session, "teacher_assignments", {"id": assignment_id}, update_dict)
    
    return {"message": "تم تحديث الإسناد بنجاح"}

@router.delete("/teacher-assignments/{assignment_id}")
async def delete_teacher_assignment(
    assignment_id: str,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN]))
):
    """حذف إسناد معلم"""
    # Fetch before soft-deleting for audit log
    old_assignment = await gd_find_one(db.session, "teacher_assignments", {"id": assignment_id})
    result = await gd_update_one(db.session, "teacher_assignments", {"id": assignment_id}, {"is_active": False, "updated_at": datetime.now(timezone.utc).isoformat()})
    if result == 0:
        raise HTTPException(status_code=404, detail="الإسناد غير موجود")
    # Audit log
    if old_assignment:
        await gd_insert(db.session, "audit_logs", {
            "id": str(uuid.uuid4()),
            "school_id": old_assignment.get("school_id"),
            "action": "DELETE",
            "entity_type": "teacher_assignment",
            "entity_id": assignment_id,
            "old_data": {
                "teacher_id": old_assignment.get("teacher_id"),
                "subject_id": old_assignment.get("subject_id"),
                "class_id": old_assignment.get("class_id"),
            },
            "performed_by": current_user.get("id"),
            "performed_by_email": current_user.get("email"),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
    return {"message": "تم حذف الإسناد"}




# ============== SCHOOL SCHEDULES ROUTES ==============
@router.post("/schedules", response_model=SchoolScheduleResponse)
async def create_schedule(
    schedule_data: SchoolScheduleCreate,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.SCHOOL_SUB_ADMIN]))
):
    """إنشاء جدول مدرسي جديد"""
    schedule_id = str(uuid.uuid4())
    schedule_doc = {
        "id": schedule_id,
        "school_id": schedule_data.school_id,
        "name": schedule_data.name,
        "name_en": schedule_data.name_en,
        "academic_year": schedule_data.academic_year,
        "semester": schedule_data.semester,
        "effective_from": schedule_data.effective_from,
        "effective_to": schedule_data.effective_to,
        "working_days": schedule_data.working_days,
        "status": ScheduleStatusEnum.DRAFT.value,
        "total_sessions": 0,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    await gd_insert(db.session, "schedules", schedule_doc)
    return SchoolScheduleResponse(**schedule_doc)

@router.get("/schedules", response_model=List[SchoolScheduleResponse])
async def get_schedules(
    school_id: Optional[str] = None,
    status: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """الحصول على الجداول المدرسية"""
    query = {}
    if school_id:
        query["school_id"] = school_id
    elif current_user.get("role") != UserRole.PLATFORM_ADMIN.value:
        query["school_id"] = current_user.get("tenant_id")
    
    if status:
        query["status"] = status
    
    schedules = await gd_find(db.session, "schedules", query, limit=100)
    return [SchoolScheduleResponse(**s) for s in schedules]

@router.get("/schedules/{schedule_id}", response_model=SchoolScheduleResponse)
async def get_schedule(schedule_id: str, current_user: dict = Depends(get_current_user)):
    """الحصول على جدول محدد"""
    schedule = await gd_find_one(db.session, "schedules", {"id": schedule_id})
    if not schedule:
        raise HTTPException(status_code=404, detail="الجدول غير موجود")
    return SchoolScheduleResponse(**schedule)

@router.put("/schedules/{schedule_id}/publish")
async def publish_schedule(
    schedule_id: str,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN]))
):
    """نشر الجدول المدرسي"""
    result = await gd_update_one(db.session, "schedules", {"id": schedule_id}, {"status": ScheduleStatusEnum.PUBLISHED.value, "updated_at": datetime.now(timezone.utc).isoformat()})
    if result == 0:
        raise HTTPException(status_code=404, detail="الجدول غير موجود")
    return {"message": "تم نشر الجدول"}

@router.delete("/schedules/{schedule_id}")
async def delete_schedule(
    schedule_id: str,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN]))
):
    """حذف جدول مدرسي"""
    # Delete all sessions first
    await gd_delete_many(db.session, "schedule_sessions", {"schedule_id": schedule_id})
    
    result = await gd_update_one(db.session, "schedules", {"id": schedule_id}, {"status": ScheduleStatusEnum.ARCHIVED.value, "updated_at": datetime.now(timezone.utc).isoformat()})
    if result == 0:
        raise HTTPException(status_code=404, detail="الجدول غير موجود")
    return {"message": "تم حذف الجدول"}




# ============== SCHEDULE SESSIONS ROUTES ==============
@router.post("/schedule-sessions", response_model=ScheduleSessionResponse)
async def create_schedule_session(
    session_data: ScheduleSessionCreate,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.SCHOOL_SUB_ADMIN]))
):
    """إضافة حصة للجدول"""
    # Check for conflicts
    existing = await gd_find_one(db.session, "schedule_sessions", {
        "schedule_id": session_data.schedule_id,
        "day_of_week": session_data.day_of_week,
        "time_slot_id": session_data.time_slot_id,
        "assignment_id": session_data.assignment_id,
        "status": {"$ne": SessionStatusEnum.CANCELLED.value}
    })
    if existing:
        raise HTTPException(status_code=400, detail="هذه الحصة موجودة بالفعل")
    
    # Get assignment details
    assignment = await gd_find_one(db.session, "teacher_assignments", {"id": session_data.assignment_id})
    if not assignment:
        raise HTTPException(status_code=404, detail="الإسناد غير موجود")
    
    session_id = str(uuid.uuid4())
    session_doc = {
        "id": session_id,
        "school_id": session_data.school_id,
        "schedule_id": session_data.schedule_id,
        "assignment_id": session_data.assignment_id,
        "day_of_week": session_data.day_of_week,
        "time_slot_id": session_data.time_slot_id,
        "room_id": session_data.room_id,
        "status": SessionStatusEnum.SCHEDULED.value,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    await gd_insert(db.session, "schedule_sessions", session_doc)
    
    # Update schedule session count
    await _gd_inc(db.session, "schedules", {"id": session_data.schedule_id}, {"total_sessions": 1})
    
    # Get names for response
    teacher = await gd_find_one(db.session, "teachers", {"id": assignment.get("teacher_id")})
    class_doc = await gd_find_one(db.session, "classes", {"id": assignment.get("class_id")})
    subject = await gd_find_one(db.session, "subjects", {"id": assignment.get("subject_id")})
    time_slot = await gd_find_one(db.session, "time_slots", {"id": session_data.time_slot_id})
    
    return ScheduleSessionResponse(
        **session_doc,
        teacher_id=assignment.get("teacher_id"),
        teacher_name=teacher.get("full_name") if teacher else None,
        class_id=assignment.get("class_id"),
        class_name=class_doc.get("name") if class_doc else None,
        subject_id=assignment.get("subject_id"),
        subject_name=subject.get("name") if subject else None,
        time_slot_name=time_slot.get("name") if time_slot else None,
        start_time=time_slot.get("start_time") if time_slot else None,
        end_time=time_slot.get("end_time") if time_slot else None
    )

@router.get("/schedule-sessions", response_model=List[ScheduleSessionResponse])
async def get_schedule_sessions(
    schedule_id: str,
    day_of_week: Optional[str] = None,
    teacher_id: Optional[str] = None,
    class_id: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """الحصول على حصص الجدول"""
    query = {"schedule_id": schedule_id}
    
    if day_of_week:
        # Support both 'day' and 'day_of_week' field names
        query["$or"] = [{"day_of_week": day_of_week}, {"day": day_of_week}]
    
    sessions = await gd_find(db.session, "schedule_sessions", query, limit=1000)
    
    if sessions and sessions[0].get("assignment_id"):
        # New format - get related data from assignments
        assignment_ids = list(set(s.get("assignment_id") for s in sessions if s.get("assignment_id")))
        time_slot_ids = list(set(s.get("time_slot_id") for s in sessions if s.get("time_slot_id")))
        
        assignments = await gd_find(db.session, "teacher_assignments", {"id": {"$in": assignment_ids}}, limit=100)
        time_slots = await gd_find(db.session, "time_slots", {"id": {"$in": time_slot_ids}}, limit=20)
        
        assignment_map = {a.get("id"): a for a in assignments}
        slot_map = {s.get("id"): s for s in time_slots}
        
        teacher_ids = list(set(a.get("teacher_id") for a in assignments if a))
        class_ids_list = list(set(a.get("class_id") for a in assignments if a))
        subject_ids = list(set(a.get("subject_id") for a in assignments if a))
        
        teachers = await gd_find(db.session, "teachers", {"id": {"$in": teacher_ids}}, limit=100)
        classes = await gd_find(db.session, "classes", {"id": {"$in": class_ids_list}}, limit=100)
        subjects = await gd_find(db.session, "subjects", {"id": {"$in": subject_ids}}, limit=100)
        
        teacher_map = {t.get("id"): t.get("full_name") or t.get("full_name_ar") for t in teachers}
        class_map = {c.get("id"): c.get("name") or c.get("name_ar") for c in classes}
        subject_map = {s.get("id"): s.get("name") or s.get("name_ar") for s in subjects}
        
        result = []
        for s in sessions:
            assignment = assignment_map.get(s.get("assignment_id"), {})
            
            if teacher_id and assignment.get("teacher_id") != teacher_id:
                continue
            if class_id and assignment.get("class_id") != class_id:
                continue
            
            slot = slot_map.get(s.get("time_slot_id"), {})
            
            # Get names from assignment or lookup tables
            t_name = assignment.get("teacher_name") or teacher_map.get(assignment.get("teacher_id"))
            c_name = assignment.get("class_name") or class_map.get(assignment.get("class_id"))
            s_name = assignment.get("subject_name") or subject_map.get(assignment.get("subject_id"))
            
            result.append(ScheduleSessionResponse(
                id=s.get("id"),
                school_id=s.get("school_id"),
                schedule_id=s.get("schedule_id"),
                assignment_id=s.get("assignment_id"),
                day_of_week=s.get("day_of_week") or s.get("day"),
                day=s.get("day") or s.get("day_of_week"),
                time_slot_id=s.get("time_slot_id"),
                slot_number=s.get("slot_number") or slot.get("slot_number"),
                status=s.get("status", "active"),
                teacher_id=assignment.get("teacher_id"),
                teacher_name=t_name,
                class_id=assignment.get("class_id"),
                class_name=c_name,
                subject_id=assignment.get("subject_id"),
                subject_name=s_name,
                time_slot_name=slot.get("name") or slot.get("name_ar"),
                start_time=slot.get("start_time"),
                end_time=slot.get("end_time")
            ))
        return result
    else:
        # Old format (demo data) - data is directly in session
        ts_ids = list(set(s.get("time_slot_id") for s in sessions if s.get("time_slot_id")))
        ts_map = {}
        if ts_ids:
            ts_docs = await gd_find(db.session, "time_slots", {"id": {"$in": ts_ids}}, limit=len(ts_ids) + 5)
            ts_map = {t["id"]: t for t in ts_docs}
        
        result = []
        for s in sessions:
            if teacher_id and s.get("teacher_id") != teacher_id:
                continue
            if class_id and s.get("class_id") != class_id:
                continue
            
            time_slot = ts_map.get(s.get("time_slot_id"))
            
            result.append(ScheduleSessionResponse(
                id=s.get("id"),
                school_id=s.get("school_id"),
                schedule_id=s.get("schedule_id"),
                assignment_id=s.get("assignment_id"),
                teacher_id=s.get("teacher_id"),
                teacher_name=s.get("teacher_name"),
                class_id=s.get("class_id"),
                class_name=s.get("class_name"),
                subject_id=s.get("subject_id"),
                subject_name=s.get("subject_name"),
                day_of_week=s.get("day_of_week") or s.get("day"),
                day=s.get("day") or s.get("day_of_week"),
                time_slot_id=s.get("time_slot_id"),
                slot_number=s.get("slot_number"),
                time_slot_name=time_slot.get("name") if time_slot else None,
                start_time=time_slot.get("start_time") if time_slot else s.get("start_time"),
                end_time=time_slot.get("end_time") if time_slot else s.get("end_time"),
                room_id=s.get("room_id"),
                room=s.get("room"),
                status=s.get("status", "active"),
                created_at=s.get("created_at")
            ))
        return result

@router.delete("/schedule-sessions/{session_id}")
async def delete_schedule_session(
    session_id: str,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN]))
):
    """حذف حصة من الجدول"""
    session = await gd_find_one(db.session, "schedule_sessions", {"id": session_id})
    if not session:
        raise HTTPException(status_code=404, detail="الحصة غير موجودة")
    
    await gd_update_one(db.session, "schedule_sessions", {"id": session_id}, {"status": SessionStatusEnum.CANCELLED.value, "updated_at": datetime.now(timezone.utc).isoformat()})
    
    # Update schedule session count
    await _gd_inc(db.session, "schedules", {"id": session.get("schedule_id")}, {"total_sessions": -1})
    
    return {"message": "تم حذف الحصة"}




