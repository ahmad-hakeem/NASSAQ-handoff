"""
NASSAQ Route Module: Scheduling engine, time slots, assignments, sessions, generation, conflicts, timetable
Auto-consolidated during Phase 8 modularization.
"""
from fastapi import APIRouter, HTTPException, Depends, status, Header, Query, Body, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import Response
from starlette.responses import StreamingResponse
from pydantic import BaseModel, Field, ConfigDict, EmailStr, model_validator
from typing import List, Optional, Any, Dict
from datetime import datetime, timezone, timedelta
from bson import ObjectId
import uuid, os, logging, json, random, re, io, base64

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
    await db.time_slots.insert_one(slot_doc)
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
    
    slots = await db.time_slots.find(query, {"_id": 0}).sort([("start_time", 1), ("slot_number", 1)]).to_list(50)
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
    result = await db.time_slots.update_one({"id": slot_id}, {"$set": {"is_active": False}})
    if result.modified_count == 0:
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
    
    existing = await db.teacher_assignments.find_one(duplicate_check)
    if existing:
        teacher_doc = await db.teachers.find_one({"id": assignment_data.teacher_id}, {"_id": 0, "full_name": 1, "full_name_ar": 1})
        subject_doc = await db.subjects.find_one({"id": assignment_data.subject_id}, {"_id": 0, "name_ar": 1, "name": 1})
        if not subject_doc:
            subject_doc = await db.reference_subjects.find_one({"id": assignment_data.subject_id}, {"_id": 0, "name_ar": 1, "name": 1})
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
        await db.teacher_assignments.insert_one(assignment_doc)
    except Exception as e:
        if "duplicate key" in str(e).lower() or "E11000" in str(e):
            raise HTTPException(
                status_code=409,
                detail="هذه المادة مسندة بالفعل لهذا المعلم. لا يمكن تكرار نفس الإسناد."
            )
        raise
    
    # Get names for response (support both naming conventions)
    teacher = await db.teachers.find_one({"id": assignment_data.teacher_id}, {"_id": 0, "full_name": 1, "full_name_ar": 1})
    class_doc = None
    if assignment_data.class_id:
        class_doc = await db.classes.find_one({"id": assignment_data.class_id}, {"_id": 0, "name": 1, "name_ar": 1})
    
    # Try to get subject from multiple collections
    subject = await db.subjects.find_one({"id": assignment_data.subject_id}, {"_id": 0, "name": 1, "name_ar": 1})
    if not subject:
        subject = await db.reference_subjects.find_one({"id": assignment_data.subject_id}, {"_id": 0, "name": 1, "name_ar": 1})
    if not subject:
        subject = await db.official_curriculum_subjects.find_one({"id": assignment_data.subject_id}, {"_id": 0, "name": 1, "name_ar": 1})
    
    # Audit log
    await db.audit_logs.insert_one({
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
    
    assignments = await db.teacher_assignments.find(query, {"_id": 0}).to_list(500)
    
    # Get all related entities
    teacher_ids = list(set(a.get("teacher_id") for a in assignments))
    class_ids = list(set(a.get("class_id") for a in assignments))
    subject_ids = list(set(a.get("subject_id") for a in assignments))
    
    teachers = await db.teachers.find({"id": {"$in": teacher_ids}}, {"_id": 0}).to_list(100)
    classes = await db.classes.find({"id": {"$in": class_ids}}, {"_id": 0}).to_list(100)
    
    # Try both subjects collection and reference_subjects
    subjects = await db.subjects.find({"id": {"$in": subject_ids}}, {"_id": 0}).to_list(100)
    if not subjects:
        subjects = await db.reference_subjects.find({"id": {"$in": subject_ids}}, {"_id": 0}).to_list(100)
    
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
        except Exception:
            pass
    
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
    assignment = await db.teacher_assignments.find_one({"id": assignment_id}, {"_id": 0})
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
    
    await db.teacher_assignments.update_one({"id": assignment_id}, {"$set": update_dict})
    
    return {"message": "تم تحديث الإسناد بنجاح"}

@router.delete("/teacher-assignments/{assignment_id}")
async def delete_teacher_assignment(
    assignment_id: str,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN]))
):
    """حذف إسناد معلم"""
    # Fetch before soft-deleting for audit log
    old_assignment = await db.teacher_assignments.find_one({"id": assignment_id}, {"_id": 0})
    result = await db.teacher_assignments.update_one(
        {"id": assignment_id},
        {"$set": {"is_active": False, "updated_at": datetime.now(timezone.utc).isoformat()}}
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="الإسناد غير موجود")
    # Audit log
    if old_assignment:
        await db.audit_logs.insert_one({
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
    await db.schedules.insert_one(schedule_doc)
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
    
    schedules = await db.schedules.find(query, {"_id": 0}).to_list(100)
    return [SchoolScheduleResponse(**s) for s in schedules]

@router.get("/schedules/{schedule_id}", response_model=SchoolScheduleResponse)
async def get_schedule(schedule_id: str, current_user: dict = Depends(get_current_user)):
    """الحصول على جدول محدد"""
    schedule = await db.schedules.find_one({"id": schedule_id}, {"_id": 0})
    if not schedule:
        raise HTTPException(status_code=404, detail="الجدول غير موجود")
    return SchoolScheduleResponse(**schedule)

@router.put("/schedules/{schedule_id}/publish")
async def publish_schedule(
    schedule_id: str,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN]))
):
    """نشر الجدول المدرسي"""
    result = await db.schedules.update_one(
        {"id": schedule_id},
        {"$set": {"status": ScheduleStatusEnum.PUBLISHED.value, "updated_at": datetime.now(timezone.utc).isoformat()}}
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="الجدول غير موجود")
    return {"message": "تم نشر الجدول"}

@router.delete("/schedules/{schedule_id}")
async def delete_schedule(
    schedule_id: str,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN]))
):
    """حذف جدول مدرسي"""
    # Delete all sessions first
    await db.schedule_sessions.delete_many({"schedule_id": schedule_id})
    
    result = await db.schedules.update_one(
        {"id": schedule_id},
        {"$set": {"status": ScheduleStatusEnum.ARCHIVED.value, "updated_at": datetime.now(timezone.utc).isoformat()}}
    )
    if result.modified_count == 0:
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
    existing = await db.schedule_sessions.find_one({
        "schedule_id": session_data.schedule_id,
        "day_of_week": session_data.day_of_week,
        "time_slot_id": session_data.time_slot_id,
        "assignment_id": session_data.assignment_id,
        "status": {"$ne": SessionStatusEnum.CANCELLED.value}
    })
    if existing:
        raise HTTPException(status_code=400, detail="هذه الحصة موجودة بالفعل")
    
    # Get assignment details
    assignment = await db.teacher_assignments.find_one({"id": session_data.assignment_id}, {"_id": 0})
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
    await db.schedule_sessions.insert_one(session_doc)
    
    # Update schedule session count
    await db.schedules.update_one(
        {"id": session_data.schedule_id},
        {"$inc": {"total_sessions": 1}}
    )
    
    # Get names for response
    teacher = await db.teachers.find_one({"id": assignment.get("teacher_id")}, {"_id": 0})
    class_doc = await db.classes.find_one({"id": assignment.get("class_id")}, {"_id": 0})
    subject = await db.subjects.find_one({"id": assignment.get("subject_id")}, {"_id": 0})
    time_slot = await db.time_slots.find_one({"id": session_data.time_slot_id}, {"_id": 0})
    
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
    
    sessions = await db.schedule_sessions.find(query, {"_id": 0}).to_list(1000)
    
    # Check if sessions use the new format (with assignment_id) or old format (direct fields)
    if sessions and sessions[0].get("assignment_id"):
        # New format - get related data from assignments
        assignment_ids = list(set(s.get("assignment_id") for s in sessions if s.get("assignment_id")))
        time_slot_ids = list(set(s.get("time_slot_id") for s in sessions if s.get("time_slot_id")))
        
        assignments = await db.teacher_assignments.find({"id": {"$in": assignment_ids}}, {"_id": 0}).to_list(100)
        time_slots = await db.time_slots.find({"id": {"$in": time_slot_ids}}, {"_id": 0}).to_list(20)
        
        assignment_map = {a.get("id"): a for a in assignments}
        slot_map = {s.get("id"): s for s in time_slots}
        
        teacher_ids = list(set(a.get("teacher_id") for a in assignments if a))
        class_ids_list = list(set(a.get("class_id") for a in assignments if a))
        subject_ids = list(set(a.get("subject_id") for a in assignments if a))
        
        teachers = await db.teachers.find({"id": {"$in": teacher_ids}}, {"_id": 0}).to_list(100)
        classes = await db.classes.find({"id": {"$in": class_ids_list}}, {"_id": 0}).to_list(100)
        subjects = await db.subjects.find({"id": {"$in": subject_ids}}, {"_id": 0}).to_list(100)
        
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
        result = []
        for s in sessions:
            # Filter by teacher_id or class_id if specified
            if teacher_id and s.get("teacher_id") != teacher_id:
                continue
            if class_id and s.get("class_id") != class_id:
                continue
            
            # Get time slot info if available
            time_slot = None
            if s.get("time_slot_id"):
                time_slot = await db.time_slots.find_one({"id": s.get("time_slot_id")}, {"_id": 0})
            
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
    session = await db.schedule_sessions.find_one({"id": session_id}, {"_id": 0})
    if not session:
        raise HTTPException(status_code=404, detail="الحصة غير موجودة")
    
    await db.schedule_sessions.update_one(
        {"id": session_id},
        {"$set": {"status": SessionStatusEnum.CANCELLED.value, "updated_at": datetime.now(timezone.utc).isoformat()}}
    )
    
    # Update schedule session count
    await db.schedules.update_one(
        {"id": session.get("schedule_id")},
        {"$inc": {"total_sessions": -1}}
    )
    
    return {"message": "تم حذف الحصة"}




# ============== SCHEDULE GENERATION (AI) ==============
@router.post("/schedules/{schedule_id}/generate")
async def generate_schedule_auto(
    schedule_id: str,
    respect_workload: bool = True,
    balance_daily: bool = True,
    avoid_consecutive: bool = True,
    max_daily_per_teacher: int = 6,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN]))
):
    """
    توليد الجدول تلقائياً بالذكاء الاصطناعي
    
    الميزات:
    - توزيع متوازن للحصص على أيام الأسبوع
    - مراعاة نصاب المعلم اليومي
    - تجنب التعارضات (معلم/فصل/قاعة)
    - تجنب الحصص المتتالية للمعلم بقدر الإمكان
    """
    import random
    from collections import defaultdict
    
    start_time = datetime.now(timezone.utc)
    
    schedule = await db.schedules.find_one({"id": schedule_id}, {"_id": 0})
    if not schedule:
        raise HTTPException(status_code=404, detail="الجدول غير موجود")
    
    school_id = schedule.get("school_id")
    working_days = schedule.get("working_days", ["sunday", "monday", "tuesday", "wednesday", "thursday"])
    
    # Get time slots
    time_slots = await db.time_slots.find(
        {"school_id": school_id, "is_active": True, "is_break": False},
        {"_id": 0}
    ).sort("slot_number", 1).to_list(20)
    
    if not time_slots:
        raise HTTPException(status_code=400, detail="لم يتم تعريف الفترات الزمنية")
    
    # Get assignments - try exact match first, then fallback to any active assignments
    schedule_academic_year = schedule.get("academic_year")
    schedule_semester = schedule.get("semester")
    
    assignments = await db.teacher_assignments.find({
        "school_id": school_id,
        "is_active": True,
        "academic_year": schedule_academic_year,
        "semester": schedule_semester
    }, {"_id": 0}).to_list(500)
    
    # If no assignments found with exact match, try without year/semester filter
    if not assignments:
        assignments = await db.teacher_assignments.find({
            "school_id": school_id,
            "is_active": True
        }, {"_id": 0}).to_list(500)
    
    if not assignments:
        raise HTTPException(status_code=400, detail="لم يتم العثور على إسنادات للمعلمين. يرجى إضافة إسنادات من صفحة الإعدادات -> تبويب الإسنادات")
    
    # Get teacher info for workload calculation
    teacher_ids = list(set(a.get("teacher_id") for a in assignments if a.get("teacher_id")))
    teachers = await db.teachers.find({"id": {"$in": teacher_ids}}, {"_id": 0, "id": 1, "rank": 1, "full_name": 1}).to_list(500)
    teacher_map = {t.get("id"): t for t in teachers}
    
    # Workload limits by rank
    workload_limits = {
        TeacherRankEnum.EXPERT.value: {"daily_max": 4, "weekly_max": 18},
        TeacherRankEnum.ADVANCED.value: {"daily_max": 5, "weekly_max": 20},
        TeacherRankEnum.PRACTITIONER.value: {"daily_max": 6, "weekly_max": 24},
        TeacherRankEnum.ASSISTANT.value: {"daily_max": 7, "weekly_max": 26},
    }
    
    # Clear existing sessions
    await db.schedule_sessions.delete_many({"schedule_id": schedule_id})
    
    # Build sessions to place with smart grouping
    sessions_to_place = []
    assignment_sessions = defaultdict(list)
    
    for assignment in assignments:
        weekly_sessions = assignment.get("weekly_sessions", 4)
        teacher_id = assignment.get("teacher_id")
        class_id = assignment.get("class_id")
        subject_id = assignment.get("subject_id")
        
        for i in range(weekly_sessions):
            session_data = {
                "assignment_id": assignment.get("id"),
                "teacher_id": teacher_id,
                "class_id": class_id,
                "subject_id": subject_id,
                "placed": False,
                "preferred_day_index": i % len(working_days)  # Distribute across days
            }
            sessions_to_place.append(session_data)
            assignment_sessions[assignment.get("id")].append(session_data)
    
    # Sort sessions: prioritize those with more constraints
    sessions_to_place.sort(key=lambda s: (
        -len([a for a in assignments if a.get("teacher_id") == s["teacher_id"]]),  # Teachers with more assignments first
        s["preferred_day_index"]
    ))
    
    # Track placements
    teacher_schedule = {d: {} for d in working_days}  # day -> {slot_id: teacher_id}
    class_schedule = {d: {} for d in working_days}    # day -> {slot_id: class_id}
    teacher_daily_count = {d: defaultdict(int) for d in working_days}  # day -> {teacher_id: count}
    teacher_last_slot = {d: {} for d in working_days}  # day -> {teacher_id: last_slot_number}
    
    sessions_created = 0
    placement_attempts = 0
    conflicts_avoided = 0
    
    generation_log = []
    
    for session_req in sessions_to_place:
        teacher_id = session_req["teacher_id"]
        class_id = session_req["class_id"]
        
        # Get teacher workload limits
        teacher_info = teacher_map.get(teacher_id, {})
        teacher_rank = teacher_info.get("rank", TeacherRankEnum.PRACTITIONER.value)
        limits = workload_limits.get(teacher_rank, workload_limits[TeacherRankEnum.PRACTITIONER.value])
        daily_max = min(max_daily_per_teacher, limits["daily_max"]) if respect_workload else max_daily_per_teacher
        
        placed = False
        
        # Try preferred day first, then others
        preferred_day = working_days[session_req["preferred_day_index"]]
        days_to_try = [preferred_day] + [d for d in working_days if d != preferred_day]
        
        if balance_daily:
            # Sort days by current teacher load (prefer days with fewer sessions)
            days_to_try.sort(key=lambda d: teacher_daily_count[d].get(teacher_id, 0))
        
        for day in days_to_try:
            if placed:
                break
            
            # Check daily limit
            if teacher_daily_count[day].get(teacher_id, 0) >= daily_max:
                continue
            
            slots_to_try = list(time_slots)
            
            if avoid_consecutive:
                # Prefer non-consecutive slots
                last_slot = teacher_last_slot[day].get(teacher_id)
                if last_slot is not None:
                    slots_to_try.sort(key=lambda s: abs(s.get("slot_number", 0) - last_slot) > 1, reverse=True)
            
            for slot in slots_to_try:
                placement_attempts += 1
                slot_id = slot.get("id")
                slot_number = slot.get("slot_number", 0)
                
                # Check teacher availability
                if teacher_schedule[day].get(slot_id) is not None:
                    conflicts_avoided += 1
                    continue
                
                # Check class availability
                if class_schedule[day].get(slot_id) is not None:
                    conflicts_avoided += 1
                    continue
                
                # Place session
                session_id = str(uuid.uuid4())
                session_doc = {
                    "id": session_id,
                    "school_id": school_id,
                    "schedule_id": schedule_id,
                    "assignment_id": session_req["assignment_id"],
                    "teacher_id": teacher_id,
                    "class_id": class_id,
                    "subject_id": session_req.get("subject_id"),
                    "day_of_week": day,
                    "time_slot_id": slot_id,
                    "room_id": None,
                    "status": SessionStatusEnum.SCHEDULED.value,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "updated_at": datetime.now(timezone.utc).isoformat()
                }
                await db.schedule_sessions.insert_one(session_doc)
                
                # Update tracking
                teacher_schedule[day][slot_id] = teacher_id
                class_schedule[day][slot_id] = class_id
                teacher_daily_count[day][teacher_id] += 1
                teacher_last_slot[day][teacher_id] = slot_number
                
                sessions_created += 1
                session_req["placed"] = True
                placed = True
                break
    
    end_time = datetime.now(timezone.utc)
    generation_duration = (end_time - start_time).total_seconds()
    
    # Calculate statistics
    unplaced = sum(1 for s in sessions_to_place if not s["placed"])
    total_requested = len(sessions_to_place)
    success_rate = (sessions_created / total_requested * 100) if total_requested > 0 else 0
    
    # Teacher distribution statistics
    teacher_stats = {}
    for teacher_id in teacher_ids:
        total_sessions = sum(teacher_daily_count[d].get(teacher_id, 0) for d in working_days)
        daily_distribution = {d: teacher_daily_count[d].get(teacher_id, 0) for d in working_days}
        teacher_info = teacher_map.get(teacher_id, {})
        teacher_stats[teacher_id] = {
            "name": teacher_info.get("full_name", "غير معروف"),
            "total_sessions": total_sessions,
            "daily_distribution": daily_distribution
        }
    
    # Update schedule
    await db.schedules.update_one(
        {"id": schedule_id},
        {"$set": {
            "total_sessions": sessions_created,
            "status": ScheduleStatusEnum.DRAFT.value,
            "generation_stats": {
                "generated_at": end_time.isoformat(),
                "duration_seconds": generation_duration,
                "success_rate": success_rate,
                "placement_attempts": placement_attempts,
                "conflicts_avoided": conflicts_avoided
            },
            "updated_at": end_time.isoformat()
        }}
    )
    
    # Generate recommendations based on results
    recommendations = []
    if unplaced > 0:
        if len(time_slots) * len(working_days) < total_requested / len(set(a.get('class_id') for a in assignments)):
            recommendations.append({
                "type": "insufficient_slots",
                "message_ar": f"عدد الفترات الزمنية ({len(time_slots)}) غير كافٍ لتغطية جميع الحصص المطلوبة",
                "message_en": f"Time slots ({len(time_slots)}) are insufficient for all requested sessions"
            })
        
        # Check for overloaded teachers
        overloaded_teachers = []
        for teacher_id, count in [(t, sum(teacher_daily_count[d].get(t, 0) for d in working_days)) for t in teacher_ids]:
            required = sum(a.get('weekly_sessions', 4) for a in assignments if a.get('teacher_id') == teacher_id)
            if count < required:
                teacher_info = teacher_map.get(teacher_id, {})
                overloaded_teachers.append({
                    "teacher_name": teacher_info.get("full_name", teacher_id),
                    "required": required,
                    "placed": count
                })
        
        if overloaded_teachers:
            recommendations.append({
                "type": "teacher_overload",
                "message_ar": "بعض المعلمين لديهم حصص أكثر مما يمكن جدولته بسبب التعارضات",
                "message_en": "Some teachers have more sessions than can be scheduled due to conflicts",
                "details": overloaded_teachers
            })
    
    return {
        "success": unplaced == 0,
        "schedule_id": schedule_id,
        "sessions_created": sessions_created,
        "sessions_requested": total_requested,
        "unplaced_sessions": unplaced,
        "success_rate": round(success_rate, 1),
        "generation_time_seconds": round(generation_duration, 2),
        "statistics": {
            "placement_attempts": placement_attempts,
            "conflicts_avoided": conflicts_avoided,
            "teachers_scheduled": len(teacher_ids),
            "days_used": len(working_days),
            "slots_per_day": len(time_slots),
            "total_available_slots": len(time_slots) * len(working_days)
        },
        "teacher_distribution": teacher_stats,
        "recommendations": recommendations,
        "message": f"تم إنشاء {sessions_created} من {total_requested} حصة ({success_rate:.0f}%)",
        "message_en": f"Created {sessions_created} of {total_requested} sessions ({success_rate:.0f}%)"
    }




# ============== SCHEDULE CONFLICTS CHECK (ADVANCED) ==============
@router.get("/schedules/{schedule_id}/conflicts")
async def check_schedule_conflicts(
    schedule_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    التحقق المتقدم من تعارضات الجدول
    يشمل: تعارض المعلم، تعارض الفصل، تعارض القاعة
    """
    conflicts = []
    statistics = {
        "teacher_conflicts": 0,
        "class_conflicts": 0,
        "room_conflicts": 0,
        "total_sessions": 0,
        "sessions_with_conflicts": 0
    }
    
    sessions = await db.schedule_sessions.find({
        "schedule_id": schedule_id,
        "status": {"$ne": SessionStatusEnum.CANCELLED.value}
    }, {"_id": 0}).to_list(1000)
    
    statistics["total_sessions"] = len(sessions)
    
    # Group by day and time slot
    by_day_slot = {}
    for session in sessions:
        key = (session.get("day_of_week"), session.get("time_slot_id"))
        if key not in by_day_slot:
            by_day_slot[key] = []
        by_day_slot[key].append(session)
    
    sessions_with_conflict = set()
    
    for (day, slot_id), slot_sessions in by_day_slot.items():
        if len(slot_sessions) < 2:
            continue
        
        assignment_ids = [s.get("assignment_id") for s in slot_sessions]
        assignments = await db.teacher_assignments.find(
            {"id": {"$in": assignment_ids}}, {"_id": 0}
        ).to_list(100)
        assignment_map = {a.get("id"): a for a in assignments}
        
        teachers_seen = {}
        classes_seen = {}
        rooms_seen = {}
        
        # Get time slot info
        time_slot = await db.time_slots.find_one({"id": slot_id}, {"_id": 0, "start_time": 1, "end_time": 1, "slot_number": 1})
        period_info = f"الحصة {time_slot.get('slot_number', '?')}" if time_slot else ""
        
        for session in slot_sessions:
            assignment = assignment_map.get(session.get("assignment_id"), {})
            teacher_id = assignment.get("teacher_id")
            class_id = assignment.get("class_id")
            room_id = session.get("room_id")
            session_id = session.get("id")
            
            # Check teacher conflict
            if teacher_id:
                if teacher_id in teachers_seen:
                    teacher = await db.teachers.find_one({"id": teacher_id}, {"_id": 0, "full_name": 1})
                    teacher_name = teacher.get("full_name") if teacher else "غير معروف"
                    conflicts.append({
                        "id": str(uuid.uuid4()),
                        "type": "teacher_overlap",
                        "day_of_week": day,
                        "time_slot_id": slot_id,
                        "period": time_slot.get("slot_number") if time_slot else None,
                        "teacher_id": teacher_id,
                        "teacher_name": teacher_name,
                        "conflicting_session_ids": [teachers_seen[teacher_id], session_id],
                        "description_ar": f"المعلم {teacher_name} مجدول في أكثر من حصة في نفس الوقت ({period_info})",
                        "description_en": f"Teacher {teacher_name} is double-booked at the same time",
                        "severity": "error",
                        "priority": 1
                    })
                    statistics["teacher_conflicts"] += 1
                    sessions_with_conflict.add(session_id)
                    sessions_with_conflict.add(teachers_seen[teacher_id])
                teachers_seen[teacher_id] = session_id
            
            # Check class conflict
            if class_id:
                if class_id in classes_seen:
                    class_doc = await db.classes.find_one({"id": class_id}, {"_id": 0, "name": 1})
                    class_name = class_doc.get("name") if class_doc else "غير معروف"
                    conflicts.append({
                        "id": str(uuid.uuid4()),
                        "type": "class_overlap",
                        "day_of_week": day,
                        "time_slot_id": slot_id,
                        "period": time_slot.get("slot_number") if time_slot else None,
                        "class_id": class_id,
                        "class_name": class_name,
                        "conflicting_session_ids": [classes_seen[class_id], session_id],
                        "description_ar": f"الفصل {class_name} مجدول في أكثر من حصة في نفس الوقت ({period_info})",
                        "description_en": f"Class {class_name} is double-booked at the same time",
                        "severity": "error",
                        "priority": 2
                    })
                    statistics["class_conflicts"] += 1
                    sessions_with_conflict.add(session_id)
                    sessions_with_conflict.add(classes_seen[class_id])
                classes_seen[class_id] = session_id
            
            # Check room/hall conflict (NEW)
            if room_id:
                if room_id in rooms_seen:
                    room_doc = await db.classrooms.find_one({"id": room_id}, {"_id": 0, "name": 1, "name_ar": 1})
                    room_name = room_doc.get("name_ar") or room_doc.get("name") if room_doc else "غير معروف"
                    conflicts.append({
                        "id": str(uuid.uuid4()),
                        "type": "room_overlap",
                        "day_of_week": day,
                        "time_slot_id": slot_id,
                        "period": time_slot.get("slot_number") if time_slot else None,
                        "room_id": room_id,
                        "room_name": room_name,
                        "conflicting_session_ids": [rooms_seen[room_id], session_id],
                        "description_ar": f"القاعة {room_name} مجدولة لأكثر من فصل في نفس الوقت ({period_info})",
                        "description_en": f"Room {room_name} is double-booked at the same time",
                        "severity": "warning",
                        "priority": 3
                    })
                    statistics["room_conflicts"] += 1
                    sessions_with_conflict.add(session_id)
                    sessions_with_conflict.add(rooms_seen[room_id])
                rooms_seen[room_id] = session_id
    
    statistics["sessions_with_conflicts"] = len(sessions_with_conflict)
    
    # Sort conflicts by priority
    conflicts.sort(key=lambda x: (x.get("priority", 99), x.get("day_of_week", ""), x.get("period", 0)))
    
    return {
        "schedule_id": schedule_id,
        "total_conflicts": len(conflicts),
        "conflicts": conflicts,
        "statistics": statistics,
        "has_blocking_conflicts": statistics["teacher_conflicts"] > 0 or statistics["class_conflicts"] > 0
    }





# ============== CONFLICT AUTO-RESOLUTION SUGGESTIONS ==============
@router.get("/schedules/{schedule_id}/conflicts/suggestions")
async def get_conflict_resolution_suggestions(
    schedule_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    الحصول على اقتراحات حل التعارضات تلقائياً
    
    يقوم بتحليل كل تعارض واقتراح حلول ممكنة مثل:
    - نقل الحصة لفترة زمنية أخرى في نفس اليوم
    - نقل الحصة ليوم آخر
    - تبديل معلم آخر (إذا متاح)
    """
    
    # Get schedule info
    schedule = await db.schedules.find_one({"id": schedule_id}, {"_id": 0})
    if not schedule:
        raise HTTPException(status_code=404, detail="الجدول غير موجود")
    
    school_id = schedule.get("school_id")
    working_days = schedule.get("working_days") or ["sunday", "monday", "tuesday", "wednesday", "thursday"]
    
    # Get all sessions
    sessions = await db.schedule_sessions.find({
        "schedule_id": schedule_id,
        "status": {"$ne": SessionStatusEnum.CANCELLED.value}
    }, {"_id": 0}).to_list(1000)
    
    # Get time slots
    time_slots = await db.time_slots.find(
        {"school_id": school_id, "is_active": True, "is_break": False},
        {"_id": 0}
    ).sort("slot_number", 1).to_list(20)
    
    slot_map = {s.get("id"): s for s in time_slots}
    
    # Build occupancy maps
    teacher_occupancy = {}  # {teacher_id: {day: {slot_id: session_id}}}
    class_occupancy = {}    # {class_id: {day: {slot_id: session_id}}}
    
    for session in sessions:
        teacher_id = session.get("teacher_id")
        class_id = session.get("class_id")
        day = session.get("day_of_week")
        slot_id = session.get("time_slot_id")
        session_id = session.get("id")
        
        if teacher_id:
            if teacher_id not in teacher_occupancy:
                teacher_occupancy[teacher_id] = {d: {} for d in working_days}
            if day in teacher_occupancy[teacher_id]:
                teacher_occupancy[teacher_id][day][slot_id] = session_id
        
        if class_id:
            if class_id not in class_occupancy:
                class_occupancy[class_id] = {d: {} for d in working_days}
            if day in class_occupancy[class_id]:
                class_occupancy[class_id][day][slot_id] = session_id
    
    # Detect conflicts and generate suggestions
    suggestions = []
    
    # Group sessions by day and slot for conflict detection
    by_day_slot = {}
    for session in sessions:
        key = (session.get("day_of_week"), session.get("time_slot_id"))
        if key not in by_day_slot:
            by_day_slot[key] = []
        by_day_slot[key].append(session)
    
    DAYS_AR = {
        "sunday": "الأحد", "monday": "الاثنين", "tuesday": "الثلاثاء",
        "wednesday": "الأربعاء", "thursday": "الخميس"
    }
    
    for (day, slot_id), slot_sessions in by_day_slot.items():
        if len(slot_sessions) < 2:
            continue
        
        teachers_seen = {}
        classes_seen = {}
        
        slot_info = slot_map.get(slot_id, {})
        period_num = slot_info.get("slot_number", "?")
        
        for session in slot_sessions:
            teacher_id = session.get("teacher_id")
            class_id = session.get("class_id")
            session_id = session.get("id")
            
            # Teacher conflict
            if teacher_id and teacher_id in teachers_seen:
                # Find alternative slots for this session
                teacher = await db.teachers.find_one({"id": teacher_id}, {"_id": 0, "full_name": 1})
                teacher_name = teacher.get("full_name") if teacher else "غير معروف"
                
                alternative_slots = []
                
                # Check same day, different slot
                for alt_slot in time_slots:
                    alt_slot_id = alt_slot.get("id")
                    if alt_slot_id == slot_id:
                        continue
                    
                    # Check if teacher and class are both free
                    teacher_free = teacher_occupancy.get(teacher_id, {}).get(day, {}).get(alt_slot_id) is None
                    class_free = class_occupancy.get(class_id, {}).get(day, {}).get(alt_slot_id) is None if class_id else True
                    
                    if teacher_free and class_free:
                        alternative_slots.append({
                            "type": "same_day_different_slot",
                            "day": day,
                            "day_ar": DAYS_AR.get(day, day),
                            "from_slot_id": slot_id,
                            "from_period": period_num,
                            "to_slot_id": alt_slot_id,
                            "to_period": alt_slot.get("slot_number"),
                            "to_time": alt_slot.get("start_time"),
                            "confidence": 95
                        })
                
                # Check different day, same slot
                for alt_day in working_days:
                    if alt_day == day:
                        continue
                    
                    teacher_free = teacher_occupancy.get(teacher_id, {}).get(alt_day, {}).get(slot_id) is None
                    class_free = class_occupancy.get(class_id, {}).get(alt_day, {}).get(slot_id) is None if class_id else True
                    
                    if teacher_free and class_free:
                        alternative_slots.append({
                            "type": "different_day_same_slot",
                            "day": alt_day,
                            "day_ar": DAYS_AR.get(alt_day, alt_day),
                            "from_slot_id": slot_id,
                            "from_period": period_num,
                            "to_slot_id": slot_id,
                            "to_period": period_num,
                            "to_time": slot_info.get("start_time"),
                            "confidence": 85
                        })
                
                if alternative_slots:
                    # Sort by confidence
                    alternative_slots.sort(key=lambda x: -x.get("confidence", 0))
                    best_suggestion = alternative_slots[0]
                    
                    suggestions.append({
                        "id": str(uuid.uuid4()),
                        "conflict_type": "teacher_overlap",
                        "session_id": session_id,
                        "teacher_id": teacher_id,
                        "teacher_name": teacher_name,
                        "current_day": day,
                        "current_day_ar": DAYS_AR.get(day, day),
                        "current_period": period_num,
                        "suggested_action": "move_session",
                        "suggestion_ar": f"نقل حصة المعلم {teacher_name} من {DAYS_AR.get(day, day)} الحصة {period_num} إلى {best_suggestion['day_ar']} الحصة {best_suggestion['to_period']}",
                        "suggestion_en": f"Move {teacher_name}'s session from {day} period {period_num} to {best_suggestion['day']} period {best_suggestion['to_period']}",
                        "target_day": best_suggestion["day"],
                        "target_slot_id": best_suggestion["to_slot_id"],
                        "target_period": best_suggestion["to_period"],
                        "confidence": best_suggestion["confidence"],
                        "alternatives_count": len(alternative_slots),
                        "all_alternatives": alternative_slots[:5]  # Top 5
                    })
            
            if teacher_id:
                teachers_seen[teacher_id] = session_id
            
            # Class conflict
            if class_id and class_id in classes_seen:
                class_doc = await db.classes.find_one({"id": class_id}, {"_id": 0, "name": 1})
                class_name = class_doc.get("name") if class_doc else "غير معروف"
                
                alternative_slots = []
                
                # Check same day, different slot
                for alt_slot in time_slots:
                    alt_slot_id = alt_slot.get("id")
                    if alt_slot_id == slot_id:
                        continue
                    
                    teacher_free = teacher_occupancy.get(teacher_id, {}).get(day, {}).get(alt_slot_id) is None if teacher_id else True
                    class_free = class_occupancy.get(class_id, {}).get(day, {}).get(alt_slot_id) is None
                    
                    if teacher_free and class_free:
                        alternative_slots.append({
                            "type": "same_day_different_slot",
                            "day": day,
                            "day_ar": DAYS_AR.get(day, day),
                            "from_slot_id": slot_id,
                            "from_period": period_num,
                            "to_slot_id": alt_slot_id,
                            "to_period": alt_slot.get("slot_number"),
                            "to_time": alt_slot.get("start_time"),
                            "confidence": 95
                        })
                
                if alternative_slots:
                    alternative_slots.sort(key=lambda x: -x.get("confidence", 0))
                    best_suggestion = alternative_slots[0]
                    
                    suggestions.append({
                        "id": str(uuid.uuid4()),
                        "conflict_type": "class_overlap",
                        "session_id": session_id,
                        "class_id": class_id,
                        "class_name": class_name,
                        "current_day": day,
                        "current_day_ar": DAYS_AR.get(day, day),
                        "current_period": period_num,
                        "suggested_action": "move_session",
                        "suggestion_ar": f"نقل حصة الفصل {class_name} من {DAYS_AR.get(day, day)} الحصة {period_num} إلى الحصة {best_suggestion['to_period']}",
                        "suggestion_en": f"Move {class_name}'s session from {day} period {period_num} to period {best_suggestion['to_period']}",
                        "target_day": best_suggestion["day"],
                        "target_slot_id": best_suggestion["to_slot_id"],
                        "target_period": best_suggestion["to_period"],
                        "confidence": best_suggestion["confidence"],
                        "alternatives_count": len(alternative_slots),
                        "all_alternatives": alternative_slots[:5]
                    })
            
            if class_id:
                classes_seen[class_id] = session_id
    
    return {
        "schedule_id": schedule_id,
        "total_suggestions": len(suggestions),
        "suggestions": suggestions,
        "can_auto_resolve": len(suggestions) > 0 and all(s.get("confidence", 0) >= 80 for s in suggestions)
    }


@router.post("/schedules/{schedule_id}/conflicts/apply-suggestion")
async def apply_conflict_suggestion(
    schedule_id: str,
    session_id: str,
    target_day: str,
    target_slot_id: str,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN]))
):
    """
    تطبيق اقتراح حل التعارض
    
    ينقل الحصة من موقعها الحالي إلى الموقع المقترح
    """
    
    # Validate schedule
    schedule = await db.schedules.find_one({"id": schedule_id}, {"_id": 0})
    if not schedule:
        raise HTTPException(status_code=404, detail="الجدول غير موجود")
    
    # Get session
    session = await db.schedule_sessions.find_one({"id": session_id, "schedule_id": schedule_id}, {"_id": 0})
    if not session:
        raise HTTPException(status_code=404, detail="الحصة غير موجودة")
    
    school_id = schedule.get("school_id")
    working_days = schedule.get("working_days") or ["sunday", "monday", "tuesday", "wednesday", "thursday"]
    
    # Validate target day
    if target_day not in working_days:
        raise HTTPException(status_code=400, detail="اليوم المحدد غير صالح")
    
    # Validate target slot exists
    target_slot = await db.time_slots.find_one({"id": target_slot_id, "school_id": school_id}, {"_id": 0})
    if not target_slot:
        raise HTTPException(status_code=400, detail="الفترة الزمنية غير موجودة")
    
    old_day = session.get("day_of_week")
    old_slot_id = session.get("time_slot_id")
    teacher_id = session.get("teacher_id")
    class_id = session.get("class_id")
    
    # Check if target slot is free for teacher
    if teacher_id:
        teacher_conflict = await db.schedule_sessions.find_one({
            "schedule_id": schedule_id,
            "teacher_id": teacher_id,
            "day_of_week": target_day,
            "time_slot_id": target_slot_id,
            "id": {"$ne": session_id},
            "status": {"$ne": SessionStatusEnum.CANCELLED.value}
        })
        if teacher_conflict:
            raise HTTPException(status_code=400, detail="المعلم مشغول في هذا الوقت")
    
    # Check if target slot is free for class
    if class_id:
        class_conflict = await db.schedule_sessions.find_one({
            "schedule_id": schedule_id,
            "class_id": class_id,
            "day_of_week": target_day,
            "time_slot_id": target_slot_id,
            "id": {"$ne": session_id},
            "status": {"$ne": SessionStatusEnum.CANCELLED.value}
        })
        if class_conflict:
            raise HTTPException(status_code=400, detail="الفصل مشغول في هذا الوقت")
    
    # Apply the move
    now = datetime.now(timezone.utc).isoformat()
    await db.schedule_sessions.update_one(
        {"id": session_id},
        {"$set": {
            "day_of_week": target_day,
            "time_slot_id": target_slot_id,
            "updated_at": now,
            "moved_by": current_user.get("id"),
            "moved_at": now,
            "move_history": {
                "from_day": old_day,
                "from_slot_id": old_slot_id,
                "to_day": target_day,
                "to_slot_id": target_slot_id,
                "moved_at": now
            }
        }}
    )
    
    # Get updated slot info for response
    old_slot = await db.time_slots.find_one({"id": old_slot_id}, {"_id": 0, "slot_number": 1})
    
    DAYS_AR = {
        "sunday": "الأحد", "monday": "الاثنين", "tuesday": "الثلاثاء",
        "wednesday": "الأربعاء", "thursday": "الخميس"
    }
    
    return {
        "success": True,
        "session_id": session_id,
        "message_ar": f"تم نقل الحصة من {DAYS_AR.get(old_day, old_day)} الحصة {old_slot.get('slot_number') if old_slot else '?'} إلى {DAYS_AR.get(target_day, target_day)} الحصة {target_slot.get('slot_number')}",
        "message_en": f"Session moved from {old_day} period {old_slot.get('slot_number') if old_slot else '?'} to {target_day} period {target_slot.get('slot_number')}",
        "from": {
            "day": old_day,
            "slot_id": old_slot_id,
            "period": old_slot.get("slot_number") if old_slot else None
        },
        "to": {
            "day": target_day,
            "slot_id": target_slot_id,
            "period": target_slot.get("slot_number")
        }
    }


@router.post("/schedules/{schedule_id}/conflicts/auto-resolve")
async def auto_resolve_all_conflicts(
    schedule_id: str,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN]))
):
    """
    حل جميع التعارضات تلقائياً
    
    يطبق جميع الاقتراحات ذات الثقة العالية (>= 80%)
    """
    
    # Get all suggestions
    suggestions_response = await get_conflict_resolution_suggestions(schedule_id, current_user)
    suggestions = suggestions_response.get("suggestions", [])
    
    if not suggestions:
        return {
            "success": True,
            "message_ar": "لا توجد تعارضات لحلها",
            "message_en": "No conflicts to resolve",
            "resolved_count": 0,
            "failed_count": 0
        }
    
    resolved = []
    failed = []
    
    for suggestion in suggestions:
        if suggestion.get("confidence", 0) < 80:
            failed.append({
                "session_id": suggestion.get("session_id"),
                "reason": "ثقة الاقتراح أقل من 80%"
            })
            continue
        
        try:
            result = await apply_conflict_suggestion(
                schedule_id=schedule_id,
                session_id=suggestion.get("session_id"),
                target_day=suggestion.get("target_day"),
                target_slot_id=suggestion.get("target_slot_id"),
                current_user=current_user
            )
            resolved.append({
                "session_id": suggestion.get("session_id"),
                "message": result.get("message_ar")
            })
        except HTTPException as e:
            failed.append({
                "session_id": suggestion.get("session_id"),
                "reason": e.detail
            })
    
    return {
        "success": len(failed) == 0,
        "message_ar": f"تم حل {len(resolved)} تعارض من أصل {len(suggestions)}",
        "message_en": f"Resolved {len(resolved)} of {len(suggestions)} conflicts",
        "resolved_count": len(resolved),
        "failed_count": len(failed),
        "resolved": resolved,
        "failed": failed
    }




# ============== TEACHER RANK UPDATE ==============
@router.put("/teachers/{teacher_id}/rank")
async def update_teacher_rank(
    teacher_id: str,
    rank: TeacherRankEnum,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN]))
):
    """تحديث رتبة المعلم"""
    result = await db.teachers.update_one(
        {"id": teacher_id},
        {"$set": {"rank": rank.value, "updated_at": datetime.now(timezone.utc).isoformat()}}
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="المعلم غير موجود")
    return {"message": "تم تحديث رتبة المعلم"}




# ============== TEACHER WORKLOAD ==============
@router.get("/teachers/{teacher_id}/workload")
async def get_teacher_workload(
    teacher_id: str,
    schedule_id: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """الحصول على نصاب المعلم"""
    teacher = await db.teachers.find_one({"id": teacher_id}, {"_id": 0})
    if not teacher:
        raise HTTPException(status_code=404, detail="المعلم غير موجود")
    
    rank_str = teacher.get("rank", TeacherRankEnum.PRACTITIONER.value)
    
    # Workload limits by rank
    workload_limits = {
        TeacherRankEnum.EXPERT.value: {"min": 12, "max": 18, "daily_max": 4},
        TeacherRankEnum.ADVANCED.value: {"min": 16, "max": 20, "daily_max": 5},
        TeacherRankEnum.PRACTITIONER.value: {"min": 18, "max": 24, "daily_max": 6},
        TeacherRankEnum.ASSISTANT.value: {"min": 20, "max": 26, "daily_max": 7},
    }
    
    limits = workload_limits.get(rank_str, workload_limits[TeacherRankEnum.PRACTITIONER.value])
    
    # Get assignments
    assignments = await db.teacher_assignments.find(
        {"teacher_id": teacher_id, "is_active": True}, {"_id": 0}
    ).to_list(50)
    
    total_weekly_sessions = sum(a.get("weekly_sessions", 0) for a in assignments)
    
    # Get actual sessions if schedule_id provided
    actual_sessions = 0
    sessions_by_day = {}
    if schedule_id:
        assignment_ids = [a.get("id") for a in assignments]
        sessions = await db.schedule_sessions.find({
            "schedule_id": schedule_id,
            "assignment_id": {"$in": assignment_ids},
            "status": {"$ne": SessionStatusEnum.CANCELLED.value}
        }, {"_id": 0}).to_list(200)
        
        actual_sessions = len(sessions)
        for s in sessions:
            day = s.get("day_of_week")
            if day not in sessions_by_day:
                sessions_by_day[day] = 0
            sessions_by_day[day] += 1
    
    return {
        "teacher_id": teacher_id,
        "teacher_name": teacher.get("full_name"),
        "rank": rank_str,
        "weekly_hours_min": limits["min"],
        "weekly_hours_max": limits["max"],
        "daily_sessions_max": limits["daily_max"],
        "total_assigned_sessions": total_weekly_sessions,
        "actual_scheduled_sessions": actual_sessions,
        "sessions_by_day": sessions_by_day,
        "is_overloaded": total_weekly_sessions > limits["max"],
        "is_underloaded": total_weekly_sessions < limits["min"],
        "assignments_count": len(assignments)
    }




# ============== SEED TIME SLOTS ==============
@router.post("/seed/time-slots/{school_id}")
async def seed_time_slots(
    school_id: str,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN]))
):
    """إنشاء فترات زمنية افتراضية للمدرسة"""
    # Check if slots already exist
    existing = await db.time_slots.count_documents({"school_id": school_id})
    if existing > 0:
        return {"message": "الفترات الزمنية موجودة بالفعل", "count": existing}
    
    # Default time slots for Saudi schools
    default_slots = [
        {"name": "الحصة الأولى", "name_en": "Period 1", "start_time": "07:00", "end_time": "07:45", "slot_number": 1, "is_break": False},
        {"name": "الحصة الثانية", "name_en": "Period 2", "start_time": "07:50", "end_time": "08:35", "slot_number": 2, "is_break": False},
        {"name": "الحصة الثالثة", "name_en": "Period 3", "start_time": "08:40", "end_time": "09:25", "slot_number": 3, "is_break": False},
        {"name": "الاستراحة", "name_en": "Break", "start_time": "09:25", "end_time": "09:45", "slot_number": 4, "is_break": True},
        {"name": "الحصة الرابعة", "name_en": "Period 4", "start_time": "09:45", "end_time": "10:30", "slot_number": 5, "is_break": False},
        {"name": "الحصة الخامسة", "name_en": "Period 5", "start_time": "10:35", "end_time": "11:20", "slot_number": 6, "is_break": False},
        {"name": "الحصة السادسة", "name_en": "Period 6", "start_time": "11:25", "end_time": "12:10", "slot_number": 7, "is_break": False},
        {"name": "الصلاة", "name_en": "Prayer", "start_time": "12:10", "end_time": "12:30", "slot_number": 8, "is_break": True},
        {"name": "الحصة السابعة", "name_en": "Period 7", "start_time": "12:30", "end_time": "13:15", "slot_number": 9, "is_break": False},
    ]
    
    created = 0
    for slot in default_slots:
        slot_id = str(uuid.uuid4())
        slot_doc = {
            "id": slot_id,
            "school_id": school_id,
            "duration_minutes": 45 if not slot["is_break"] else 20,
            "is_active": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            **slot
        }
        await db.time_slots.insert_one(slot_doc)
        created += 1
    
    return {"message": f"تم إنشاء {created} فترة زمنية", "count": created}





# ============== SMART SCHEDULING ENGINE APIs ==============

# --- Models for Smart Scheduling ---
class SmartTimetableGenerateRequest(BaseModel):
    """طلب توليد الجدول الذكي"""
    academic_year_id: Optional[str] = None
    term_id: Optional[str] = None


class SmartValidationResponse(BaseModel):
    """استجابة التحقق من جاهزية البيانات"""
    is_valid: bool
    can_proceed: bool
    issues: List[dict] = []
    summary: dict = {}


class SmartTimetableResponse(BaseModel):
    """استجابة الجدول"""
    model_config = ConfigDict(extra="ignore")
    id: str
    school_id: str
    name: str
    status: str
    is_published: bool
    version_number: int = 1
    created_at: str
    statistics: dict = {}


class SmartTimetableSessionResponse(BaseModel):
    """استجابة حصة في الجدول"""
    model_config = ConfigDict(extra="ignore")
    id: str
    timetable_id: str
    class_id: str
    grade_id: Optional[str] = None
    subject_id: str
    teacher_id: str
    day_of_week: str
    period_number: int
    start_time: str
    end_time: str
    session_type: str = "class"
    source_type: str = "ai_generated"
    status: str = "scheduled"


# --- Pre-Validation API ---
@router.get("/smart-scheduling/validate/{school_id}")
async def smart_validate_data_readiness(
    school_id: str,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN]))
):
    """
    التحقق من جاهزية البيانات قبل توليد الجدول
    Phase 1: Validate data readiness before timetable generation
    
    يتحقق من:
    - المدرسة والعام الدراسي
    - المراحل والصفوف والفصول
    - المواد الدراسية والإسنادات
    - المعلمين والتوافر
    - إعدادات اليوم الدراسي
    - القيود الإدارية
    """
    result = await smart_scheduling_engine.validate_data_readiness(school_id)
    
    return {
        "school_id": school_id,
        "is_valid": result.is_valid,
        "can_proceed": result.can_proceed,
        "issues": [i.model_dump() for i in result.issues],
        "summary": result.summary,
        "message_ar": "البيانات جاهزة للجدولة" if result.is_valid else f"يوجد {len(result.issues)} مشكلة تحتاج للمعالجة",
        "message_en": "Data is ready for scheduling" if result.is_valid else f"There are {len(result.issues)} issues that need attention"
    }


# --- Generate Timetable API ---
@router.post("/smart-scheduling/generate/{school_id}")
async def smart_generate_timetable(
    school_id: str,
    request: SmartTimetableGenerateRequest = None,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN]))
):
    """
    توليد الجدول الدراسي بالذكاء الاصطناعي
    Smart AI-Powered Timetable Generation
    
    المراحل:
    1. التحقق من جاهزية البيانات
    2. تحميل إعدادات المدرسة
    3. بناء مصفوفة الطلب الأكاديمي
    4. بناء مصفوفة الموارد المتاحة
    5. التحقق المسبق من التعارضات
    6. توليد مسودة الجدول
    7. اكتشاف التعارضات
    8. تحسين الجدول
    """
    request = request or SmartTimetableGenerateRequest()
    
    result = await smart_scheduling_engine.generate_timetable(
        school_id=school_id,
        academic_year_id=request.academic_year_id,
        term_id=request.term_id,
        created_by=current_user.get("id", "system")
    )
    
    return result.model_dump()


# --- Generate Timetable Smart API (Alternative endpoint for frontend) ---
@router.post("/timetable/generate-smart")
async def generate_timetable_smart(
    request: Request,
    current_user: dict = Depends(get_current_user)
):
    """
    توليد الجدول الدراسي بالذكاء الاصطناعي - نقطة نهاية بديلة
    Smart AI-Powered Timetable Generation - Alternative endpoint
    """
    try:
        body = await request.json()
        school_id = body.get("school_id")
        use_baseline = bool(body.get("use_baseline", False))
        
        if not school_id:
            school_id = request.headers.get("X-School-Context") or current_user.get("tenant_id")
        
        if not school_id:
            raise HTTPException(status_code=400, detail="school_id مطلوب")

        if not isinstance(school_id, str):
            raise HTTPException(status_code=400, detail="school_id يجب أن يكون نصاً")
        school_id = str(school_id).strip()
        
        # Get school settings
        settings = await db.school_settings.find_one({"school_id": school_id}, {"_id": 0})
        if not settings:
            raise HTTPException(status_code=404, detail="لم يتم العثور على إعدادات المدرسة")
        
        nested_settings = settings.get("settings", {})
        academic_year = nested_settings.get("academic_year") or settings.get("academicYear") or settings.get("academic_year")
        
        # Generate timetable
        result = await smart_scheduling_engine.generate_timetable(
            school_id=school_id,
            academic_year_id=academic_year,
            term_id=None,
            created_by=current_user.get("id", "system")
        )
        
        return result.model_dump()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="فشل في توليد الجدول")


# --- Get School Timetables API ---
@router.get("/smart-scheduling/timetables/{school_id}")
async def smart_get_school_timetables(
    school_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    الحصول على جميع الجداول للمدرسة
    Get all timetables for a school
    """
    timetables = await smart_scheduling_engine.get_school_timetables(school_id)
    return {
        "school_id": school_id,
        "total": len(timetables),
        "timetables": timetables
    }


# --- Timetable Versions List API (New - Must be before dynamic route) ---
@router.get("/smart-scheduling/timetable/versions")
async def get_timetable_versions(
    current_user: dict = Depends(get_current_user),
    x_school_context: Optional[str] = Header(None)
):
    """
    الحصول على جميع نسخ الجدول للمدرسة
    Get all timetable versions for the school
    """
    school_id = x_school_context or current_user.get("school_id")
    if not school_id:
        user_roles = current_user.get("roles", [])
        for role in user_roles:
            if role.get("school_id"):
                school_id = role.get("school_id")
                break
    
    if not school_id:
        raise HTTPException(status_code=400, detail="معرف المدرسة مطلوب")
    
    # Fetch all timetables
    timetables = await db.timetables.find(
        {"school_id": school_id},
        {"_id": 0}
    ).sort("created_at", -1).to_list(100)
    
    versions = []
    for tt in timetables:
        versions.append({
            "id": tt.get("id"),
            "versionName": tt.get("version_name") or tt.get("name") or f"نسخة {tt.get('id', '')[:6]}",
            "status": tt.get("status", "draft"),
            "generation_mode": tt.get("generation_mode", "full"),
            "quality_score": tt.get("quality_score", 0),
            "conflicts_count": tt.get("conflicts_count", 0),
            "warnings_count": tt.get("warnings_count", 0),
            "created_at": tt.get("created_at"),
            "published_at": tt.get("published_at"),
            "created_by": tt.get("created_by", "النظام"),
        })
    
    return {
        "school_id": school_id,
        "total": len(versions),
        "versions": versions
    }


# --- Active Timetable Sessions API (New - Must be before dynamic route) ---
@router.get("/smart-scheduling/timetable/active/sessions")
async def get_active_timetable_sessions(
    class_id: Optional[str] = None,
    teacher_id: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
    x_school_context: Optional[str] = Header(None)
):
    """
    الحصول على حصص الجدول النشط (المنشور أو المسودة)
    Get sessions for the active timetable
    """
    school_id = x_school_context or current_user.get("school_id")
    if not school_id:
        user_roles = current_user.get("roles", [])
        for role in user_roles:
            if role.get("school_id"):
                school_id = role.get("school_id")
                break
    
    if not school_id:
        raise HTTPException(status_code=400, detail="معرف المدرسة مطلوب")
    
    # Find active (published) timetable first, then draft
    timetable = await db.timetables.find_one(
        {"school_id": school_id, "status": "published"},
        {"_id": 0, "id": 1}
    )
    
    if not timetable:
        timetable = await db.timetables.find_one(
            {"school_id": school_id, "status": "draft"},
            {"_id": 0, "id": 1}
        )
    
    if not timetable:
        return {"sessions": [], "total": 0, "message": "لا يوجد جدول نشط"}
    
    # Build query
    query = {"timetable_id": timetable.get("id")}
    if class_id:
        query["class_id"] = class_id
    if teacher_id:
        query["teacher_id"] = teacher_id
    
    # Fetch sessions
    sessions = await db.timetable_sessions.find(query, {"_id": 0}).to_list(1000)
    
    # Enrich sessions
    enriched_sessions = []
    for session in sessions:
        # Get teacher name
        teacher = await db.teachers.find_one({"id": session.get("teacher_id")}, {"_id": 0, "full_name": 1})
        # Get class name
        cls = await db.classes.find_one({"id": session.get("class_id")}, {"_id": 0, "name": 1})
        # Get grade
        grade = await db.grades.find_one({"id": cls.get("grade_id") if cls else None}, {"_id": 0, "name_ar": 1})
        
        session["teacher_name"] = teacher.get("full_name") if teacher else ""
        session["class_name"] = f"{grade.get('name_ar', '')} - {cls.get('section', '') if cls else ''}" if grade else (cls.get("name", "") if cls else "")
        enriched_sessions.append(session)
    
    return {
        "timetable_id": timetable.get("id"),
        "total": len(enriched_sessions),
        "sessions": enriched_sessions
    }


# --- Get Timetable Details API ---
@router.get("/smart-scheduling/timetable/{timetable_id}")
async def smart_get_timetable(
    timetable_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    الحصول على تفاصيل جدول محدد
    Get specific timetable details
    """
    timetable = await smart_scheduling_engine.get_timetable(timetable_id)
    if not timetable:
        raise HTTPException(status_code=404, detail="الجدول غير موجود")
    
    return timetable


# --- Get Timetable Sessions API ---
@router.get("/smart-scheduling/timetable/{timetable_id}/sessions")
async def smart_get_timetable_sessions(
    timetable_id: str,
    class_id: Optional[str] = None,
    teacher_id: Optional[str] = None,
    day_of_week: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """
    الحصول على حصص الجدول
    Get timetable sessions with optional filters
    """
    sessions = await smart_scheduling_engine.get_timetable_sessions(
        timetable_id=timetable_id,
        class_id=class_id,
        teacher_id=teacher_id,
        day_of_week=day_of_week
    )
    
    # Enrich with names
    enriched_sessions = []
    for session in sessions:
        # Get teacher name
        teacher = await db.teachers.find_one({"id": session.get("teacher_id")}, {"_id": 0, "full_name": 1, "full_name_ar": 1})
        # Get class name
        cls = await db.classes.find_one({"id": session.get("class_id")}, {"_id": 0, "name": 1, "name_ar": 1})
        # Get subject name
        subject = await db.subjects.find_one({"id": session.get("subject_id")}, {"_id": 0, "name_ar": 1, "name_en": 1})
        if not subject:
            subject = await db.reference_subjects.find_one({"id": session.get("subject_id")}, {"_id": 0, "name_ar": 1, "name_en": 1})
        
        session["teacher_name"] = teacher.get("full_name") or teacher.get("full_name_ar") if teacher else ""
        session["class_name"] = cls.get("name") or cls.get("name_ar") if cls else ""
        session["subject_name"] = subject.get("name_ar", "") if subject else ""
        enriched_sessions.append(session)
    
    return {
        "timetable_id": timetable_id,
        "total": len(enriched_sessions),
        "sessions": enriched_sessions
    }


# --- Get Timetable Conflicts API ---
@router.get("/smart-scheduling/timetable/{timetable_id}/conflicts")
async def smart_get_timetable_conflicts(
    timetable_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    الحصول على تعارضات الجدول
    Get timetable conflicts
    """
    conflicts = await smart_scheduling_engine.get_timetable_conflicts(timetable_id)
    
    return {
        "timetable_id": timetable_id,
        "total": len(conflicts),
        "critical_count": len([c for c in conflicts if c.get("severity") == "critical"]),
        "high_count": len([c for c in conflicts if c.get("severity") == "high"]),
        "conflicts": conflicts
    }


# --- Get Run Logs API ---
@router.get("/smart-scheduling/run/{run_id}/logs")
async def smart_get_run_logs(
    run_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    الحصول على سجلات تشغيل المحرك
    Get scheduling engine run logs
    """
    logs = await smart_scheduling_engine.get_run_logs(run_id)
    
    return {
        "run_id": run_id,
        "total": len(logs),
        "logs": logs
    }


# --- Publish Timetable API ---
@router.post("/smart-scheduling/timetable/{timetable_id}/publish")
async def smart_publish_timetable(
    timetable_id: str,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN]))
):
    """
    نشر الجدول
    Publish the timetable (makes it visible to teachers and students)
    """
    success = await smart_scheduling_engine.publish_timetable(
        timetable_id=timetable_id,
        published_by=current_user.get("id", "system")
    )
    
    if not success:
        raise HTTPException(
            status_code=400,
            detail="لا يمكن نشر الجدول - يوجد تعارضات حرجة غير محلولة"
        )
    
    return {
        "success": True,
        "timetable_id": timetable_id,
        "message_ar": "تم نشر الجدول بنجاح",
        "message_en": "Timetable published successfully"
    }


# --- Archive Timetable API ---
@router.post("/smart-scheduling/timetable/{timetable_id}/archive")
async def smart_archive_timetable(
    timetable_id: str,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN]))
):
    """
    أرشفة الجدول
    Archive the timetable
    """
    success = await smart_scheduling_engine.archive_timetable(
        timetable_id=timetable_id,
        archived_by=current_user.get("id", "system")
    )
    
    if not success:
        raise HTTPException(status_code=404, detail="الجدول غير موجود")
    
    return {
        "success": True,
        "timetable_id": timetable_id,
        "message_ar": "تم أرشفة الجدول",
        "message_en": "Timetable archived"
    }


# --- Pre-Scheduling Check API ---
@router.get("/smart-scheduling/pre-check/{school_id}")
async def smart_pre_scheduling_check(
    school_id: str,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN]))
):
    """
    التحقق المسبق من إمكانية الجدولة
    Pre-scheduling feasibility check
    
    يحسب:
    - إجمالي الطلب الأكاديمي
    - إجمالي سعة المعلمين
    - المواد بدون معلمين
    - نسبة الاستخدام المتوقعة
    """
    # Load settings
    settings = await smart_scheduling_engine.load_school_settings(school_id)
    
    # Build demand and resources
    demands = await smart_scheduling_engine.build_academic_demand(school_id)
    resources = await smart_scheduling_engine.build_resource_availability(school_id, settings)
    
    # Run pre-check
    result = await smart_scheduling_engine.pre_scheduling_check(school_id, demands, resources, settings)
    
    return {
        "school_id": school_id,
        "can_schedule": result["can_schedule"],
        "warnings": result["warnings"],
        "errors": result["errors"],
        "statistics": result["statistics"],
        "message_ar": "يمكن بدء الجدولة" if result["can_schedule"] else "يوجد مشاكل تمنع الجدولة",
        "message_en": "Ready to schedule" if result["can_schedule"] else "Issues preventing scheduling"
    }


# --- Get Academic Demand Matrix API ---
@router.get("/smart-scheduling/demand-matrix/{school_id}")
async def smart_get_academic_demand(
    school_id: str,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN]))
):
    """
    الحصول على مصفوفة الطلب الأكاديمي
    Get Academic Demand Matrix (classes with their subjects and periods)
    """
    demands = await smart_scheduling_engine.build_academic_demand(school_id)
    
    # Enrich with names
    enriched = []
    for demand in demands:
        # Get subjects with names
        subjects_with_names = []
        for subj in demand.subjects:
            subject_doc = await db.subjects.find_one({"id": subj.get("subject_id")}, {"_id": 0, "name_ar": 1})
            if not subject_doc:
                subject_doc = await db.reference_subjects.find_one({"id": subj.get("subject_id")}, {"_id": 0, "name_ar": 1})
            
            subjects_with_names.append({
                **subj,
                "subject_name": subject_doc.get("name_ar", "") if subject_doc else ""
            })
        
        enriched.append({
            "class_id": demand.class_id,
            "class_name": demand.class_name,
            "grade_id": demand.grade_id,
            "subjects": subjects_with_names,
            "total_periods_required": demand.total_periods_required
        })
    
    return {
        "school_id": school_id,
        "total_classes": len(enriched),
        "total_demand_periods": sum(d["total_periods_required"] for d in enriched),
        "demands": enriched
    }


# --- Get Resource Availability Matrix API ---
@router.get("/smart-scheduling/resource-matrix/{school_id}")
async def smart_get_resource_availability(
    school_id: str,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN]))
):
    """
    الحصول على مصفوفة توافر الموارد
    Get Resource Availability Matrix (teachers with their availability)
    """
    settings = await smart_scheduling_engine.load_school_settings(school_id)
    resources = await smart_scheduling_engine.build_resource_availability(school_id, settings)
    
    # Convert to serializable format
    resources_data = []
    for r in resources:
        resources_data.append({
            "teacher_id": r.teacher_id,
            "teacher_name": r.teacher_name,
            "subject_ids": r.subject_ids,
            "weekly_load": r.weekly_load,
            "current_load": r.current_load,
            "availability": r.availability
        })
    
    return {
        "school_id": school_id,
        "total_teachers": len(resources_data),
        "total_capacity": sum(r["weekly_load"] for r in resources_data),
        "resources": resources_data
    }


# --- Delete Timetable API ---
@router.delete("/smart-scheduling/timetable/{timetable_id}")
async def smart_delete_timetable(
    timetable_id: str,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN]))
):
    """
    حذف الجدول
    Delete timetable and all its sessions
    """
    # Get timetable first
    timetable = await db.timetables.find_one({"id": timetable_id}, {"_id": 0})
    if not timetable:
        raise HTTPException(status_code=404, detail="الجدول غير موجود")
    
    # Don't delete published timetables
    if timetable.get("status") == TimetableStatus.PUBLISHED.value:
        raise HTTPException(status_code=400, detail="لا يمكن حذف جدول منشور - قم بأرشفته أولاً")
    
    # Delete sessions
    await db.timetable_sessions.delete_many({"timetable_id": timetable_id})
    
    # Delete conflicts
    await db.timetable_conflicts.delete_many({"timetable_id": timetable_id})
    
    # Delete unscheduled demands
    await db.timetable_unscheduled_demands.delete_many({"timetable_id": timetable_id})
    
    # Delete timetable
    await db.timetables.delete_one({"id": timetable_id})
    
    return {
        "success": True,
        "message_ar": "تم حذف الجدول بنجاح",
        "message_en": "Timetable deleted successfully"
    }





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
    session = await db.timetable_sessions.find_one({"id": session_id}, {"_id": 0})
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
        teacher_conflict = await db.timetable_sessions.find_one({
            "timetable_id": timetable_id,
            "teacher_id": new_teacher,
            "day_of_week": new_day,
            "period_number": new_period,
            "id": {"$ne": session_id}
        }, {"_id": 0})
        
        if teacher_conflict:
            conflicts.append({
                "type": "teacher_overlap",
                "message_ar": "المعلم لديه حصة أخرى في هذا الوقت",
                "message_en": "Teacher has another session at this time"
            })
        
        # Check class conflict
        class_conflict = await db.timetable_sessions.find_one({
            "timetable_id": timetable_id,
            "class_id": session.get("class_id"),
            "day_of_week": new_day,
            "period_number": new_period,
            "id": {"$ne": session_id}
        }, {"_id": 0})
        
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
            teacher_conflict = await db.timetable_sessions.find_one({
                "timetable_id": timetable_id,
                "teacher_id": request.teacher_id,
                "day_of_week": session.get("day_of_week"),
                "period_number": session.get("period_number"),
                "id": {"$ne": session_id}
            }, {"_id": 0})
            
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
    await db.timetable_sessions.update_one({"id": session_id}, {"$set": update_data})
    
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
    session = await db.timetable_sessions.find_one({"id": session_id}, {"_id": 0})
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
    
    await db.timetable_sessions.update_one({"id": session_id}, {"$set": update_data})
    
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
    session1 = await db.timetable_sessions.find_one({"id": request.session_id_1}, {"_id": 0})
    session2 = await db.timetable_sessions.find_one({"id": request.session_id_2}, {"_id": 0})
    
    if not session1 or not session2:
        raise HTTPException(status_code=404, detail="إحدى الحصتين غير موجودة")
    
    # Swap day and period
    now = datetime.now(timezone.utc).isoformat()
    
    await db.timetable_sessions.update_one(
        {"id": request.session_id_1},
        {"$set": {
            "day_of_week": session2.get("day_of_week"),
            "period_number": session2.get("period_number"),
            "source_type": "hybrid_adjusted",
            "updated_at": now
        }}
    )
    
    await db.timetable_sessions.update_one(
        {"id": request.session_id_2},
        {"$set": {
            "day_of_week": session1.get("day_of_week"),
            "period_number": session1.get("period_number"),
            "source_type": "hybrid_adjusted",
            "updated_at": now
        }}
    )
    
    return {
        "success": True,
        "message_ar": "تم تبديل الحصتين بنجاح",
        "message_en": "Sessions swapped successfully"
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
    session = await db.timetable_sessions.find_one({"id": session_id}, {"_id": 0})
    if not session:
        raise HTTPException(status_code=404, detail="الحصة غير موجودة")
    
    await db.timetable_sessions.delete_one({"id": session_id})
    
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
    timetable = await db.timetables.find_one({"id": timetable_id}, {"_id": 0})
    if not timetable:
        raise HTTPException(status_code=404, detail="الجدول غير موجود")
    
    school_id = timetable.get("school_id")
    
    # Get class info
    cls = await db.classes.find_one({"id": class_id}, {"_id": 0})
    grade_id = cls.get("grade_id", "") if cls else ""
    
    # Check for conflicts
    conflicts = []
    
    # Teacher conflict
    teacher_conflict = await db.timetable_sessions.find_one({
        "timetable_id": timetable_id,
        "teacher_id": teacher_id,
        "day_of_week": day_of_week,
        "period_number": period_number
    }, {"_id": 0})
    
    if teacher_conflict:
        conflicts.append({
            "type": "teacher_overlap",
            "message_ar": "المعلم لديه حصة أخرى في هذا الوقت"
        })
    
    # Class conflict
    class_conflict = await db.timetable_sessions.find_one({
        "timetable_id": timetable_id,
        "class_id": class_id,
        "day_of_week": day_of_week,
        "period_number": period_number
    }, {"_id": 0})
    
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
    
    await db.timetable_sessions.insert_one(session_doc)
    
    return {
        "success": True,
        "session_id": session_id,
        "message_ar": "تم إضافة الحصة بنجاح",
        "message_en": "Session added successfully"
    }





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
    await db.status_checks.insert_one(doc)
    return status_obj

@router.get("/status", response_model=List[StatusCheck])
async def get_status_checks():
    status_checks = await db.status_checks.find({}, {"_id": 0}).to_list(1000)
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
    session = await db.schedule_sessions.find_one({"id": session_id}, {"_id": 0})
    if not session:
        raise HTTPException(status_code=404, detail="الحصة غير موجودة")
    
    old_day = session.get("day_of_week")
    old_time_slot_id = session.get("time_slot_id")
    schedule_id = session.get("schedule_id")
    assignment_id = session.get("assignment_id")
    
    # Get assignment details
    assignment = await db.teacher_assignments.find_one({"id": assignment_id}, {"_id": 0})
    if not assignment:
        raise HTTPException(status_code=404, detail="الإسناد غير موجود")
    
    teacher_id = assignment.get("teacher_id")
    class_id = assignment.get("class_id")
    
    # Validate the new time slot exists
    new_slot = await db.time_slots.find_one({"id": move_data.new_time_slot_id}, {"_id": 0})
    if not new_slot:
        raise HTTPException(status_code=400, detail="الفترة الزمنية غير موجودة")
    
    # Check for conflicts at the new position
    conflicts = []
    is_hard_conflict = False
    
    # 1. Check teacher conflict
    teacher_conflict = await db.schedule_sessions.find_one({
        "schedule_id": schedule_id,
        "day_of_week": move_data.new_day_of_week,
        "time_slot_id": move_data.new_time_slot_id,
        "id": {"$ne": session_id},
        "status": {"$ne": SessionStatusEnum.CANCELLED.value}
    }, {"_id": 0})
    
    if teacher_conflict:
        conflict_assignment = await db.teacher_assignments.find_one(
            {"id": teacher_conflict.get("assignment_id")}, {"_id": 0}
        )
        if conflict_assignment:
            conflict_teacher_id = conflict_assignment.get("teacher_id")
            conflict_class_id = conflict_assignment.get("class_id")
            
            # Check if same teacher
            if conflict_teacher_id == teacher_id:
                teacher_doc = await db.teachers.find_one({"id": teacher_id}, {"_id": 0})
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
                class_doc = await db.classes.find_one({"id": class_id}, {"_id": 0})
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
    await db.schedule_sessions.update_one(
        {"id": session_id},
        {"$set": {
            "day_of_week": move_data.new_day_of_week,
            "time_slot_id": move_data.new_time_slot_id,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }}
    )
    
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



