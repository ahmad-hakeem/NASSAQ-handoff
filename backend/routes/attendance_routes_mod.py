"""
NASSAQ Route Module: Attendance engine and endpoints
Auto-consolidated during Phase 8 modularization.
"""
from fastapi import APIRouter, HTTPException, Depends, status, Header, Query, Body, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import Response
from starlette.responses import StreamingResponse
from pydantic import BaseModel, Field, ConfigDict, EmailStr, model_validator
from typing import List, Optional, Any, Dict
from datetime import datetime, timezone, timedelta
import uuid, os, logging, json, random, re, io, base64
from enum import Enum

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
from engines.attendance_engine import AttendanceEngine

_attendance_engine = AttendanceEngine(db)

router = APIRouter()



# ============== ATTENDANCE ENGINE ==============

# Attendance Status Enum
class AttendanceStatus(str, Enum):
    PRESENT = "present"
    ABSENT = "absent"
    LATE = "late"
    EXCUSED = "excused"

# Attendance Models
class AttendanceRecord(BaseModel):
    student_id: str
    class_id: str
    subject_id: Optional[str] = None
    teacher_id: str
    date: str  # Format: YYYY-MM-DD
    time_slot_id: Optional[str] = None
    status: AttendanceStatus
    notes: Optional[str] = None
    recorded_by: str
    recorded_at: str

class AttendanceCreate(BaseModel):
    student_id: str
    class_id: str
    subject_id: Optional[str] = None
    time_slot_id: Optional[str] = None
    status: AttendanceStatus
    notes: Optional[str] = None

class BulkAttendanceCreate(BaseModel):
    class_id: str
    subject_id: Optional[str] = None
    time_slot_id: Optional[str] = None
    date: str  # Format: YYYY-MM-DD
    records: List[dict]  # List of {student_id, status, notes}

class AttendanceResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    student_id: str
    student_name: Optional[str] = None
    class_id: str
    class_name: Optional[str] = None
    subject_id: Optional[str] = None
    subject_name: Optional[str] = None
    teacher_id: Optional[str] = None
    teacher_name: Optional[str] = None
    date: str
    time_slot_id: Optional[str] = None
    status: AttendanceStatus
    notes: Optional[str] = None
    recorded_by: Optional[str] = None
    recorded_at: Optional[str] = None

class AttendanceSummary(BaseModel):
    total_students: int
    present: int
    absent: int
    late: int
    excused: int
    attendance_rate: float

class StudentAttendanceHistory(BaseModel):
    student_id: str
    student_name: str
    total_days: int
    present_days: int
    absent_days: int
    late_days: int
    excused_days: int
    attendance_rate: float
    records: List[AttendanceResponse]

class DailyAttendanceReport(BaseModel):
    date: str
    class_id: str
    class_name: str
    summary: AttendanceSummary
    records: List[AttendanceResponse]




# ============== ATTENDANCE ENDPOINTS ==============

@router.post("/attendance", response_model=AttendanceResponse)
async def create_attendance(
    attendance: AttendanceCreate,
    current_user: dict = Depends(get_current_user)
):
    """Create a single attendance record"""
    if current_user['role'] not in ['teacher', 'school_principal', 'school_sub_admin', 'platform_admin']:
        raise HTTPException(status_code=403, detail="Not authorized to record attendance")
    
    # Get student info
    student = await db.students.find_one({"id": attendance.student_id}, {"_id": 0})
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    
    # Get class info
    class_info = await db.classes.find_one({"id": attendance.class_id}, {"_id": 0})
    
    # Get subject info if provided
    subject_name = None
    if attendance.subject_id:
        subject = await db.subjects.find_one({"id": attendance.subject_id}, {"_id": 0})
        subject_name = subject.get('name') if subject else None
    
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    
    # Check if attendance already exists for this student, class, date
    existing = await db.attendance.find_one({
        "student_id": attendance.student_id,
        "class_id": attendance.class_id,
        "date": today,
        "time_slot_id": attendance.time_slot_id
    })
    
    if existing:
        old_status = existing.get('status')
        await db.attendance.update_one(
            {"id": existing['id']},
            {"$set": {
                "status": attendance.status,
                "notes": attendance.notes,
                "recorded_by": current_user['id'],
                "recorded_at": datetime.now(timezone.utc).isoformat()
            }}
        )
        
        await audit_engine.log(
            action=AuditAction.ATTENDANCE_RECORDED.value,
            performed_by=current_user['id'],
            tenant_id=current_user.get('tenant_id'),
            entity_type="attendance",
            entity_id=existing['id'],
            details={
                "student_id": attendance.student_id,
                "class_id": attendance.class_id,
                "date": today,
                "old_status": old_status,
                "new_status": attendance.status.value,
            },
            actor_name=current_user.get("full_name"),
            actor_role=current_user.get("role"),
            actor_email=current_user.get("email"),
        )
        
        updated = await db.attendance.find_one({"id": existing['id']}, {"_id": 0})
        updated['student_name'] = student.get('full_name')
        updated['class_name'] = class_info.get('name') if class_info else None
        updated['subject_name'] = subject_name
        updated['teacher_name'] = current_user.get('full_name')
        return AttendanceResponse(**updated)
    
    # Create new record
    attendance_id = str(uuid.uuid4())
    attendance_doc = {
        "id": attendance_id,
        "student_id": attendance.student_id,
        "class_id": attendance.class_id,
        "subject_id": attendance.subject_id,
        "teacher_id": current_user['id'],
        "date": today,
        "time_slot_id": attendance.time_slot_id,
        "status": attendance.status,
        "notes": attendance.notes,
        "recorded_by": current_user['id'],
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "tenant_id": current_user.get('tenant_id')
    }
    
    await db.attendance.insert_one(attendance_doc)
    
    # Create attendance event for notifications/analytics
    event_doc = {
        "id": str(uuid.uuid4()),
        "type": "attendance_recorded",
        "student_id": attendance.student_id,
        "class_id": attendance.class_id,
        "status": attendance.status,
        "recorded_by": current_user['id'],
        "date": today,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "tenant_id": current_user.get('tenant_id')
    }
    await db.events.insert_one(event_doc)
    
    await audit_engine.log(
        action=AuditAction.ATTENDANCE_RECORDED.value,
        performed_by=current_user['id'],
        tenant_id=current_user.get('tenant_id'),
        entity_type="attendance",
        entity_id=attendance_id,
        details={
            "student_id": attendance.student_id,
            "class_id": attendance.class_id,
            "date": today,
            "old_status": None,
            "new_status": attendance.status.value,
        },
        actor_name=current_user.get("full_name"),
        actor_role=current_user.get("role"),
        actor_email=current_user.get("email"),
    )
    
    return AttendanceResponse(
        id=attendance_id,
        student_id=attendance.student_id,
        student_name=student.get('full_name'),
        class_id=attendance.class_id,
        class_name=class_info.get('name') if class_info else None,
        subject_id=attendance.subject_id,
        subject_name=subject_name,
        teacher_id=current_user['id'],
        teacher_name=current_user.get('full_name'),
        date=today,
        time_slot_id=attendance.time_slot_id,
        status=attendance.status,
        notes=attendance.notes,
        recorded_by=current_user['id'],
        recorded_at=attendance_doc['recorded_at']
    )

@router.post("/attendance/bulk")
async def create_bulk_attendance(
    bulk_data: BulkAttendanceCreate,
    current_user: dict = Depends(get_current_user)
):
    """Create multiple attendance records at once (for a whole class)"""
    if current_user['role'] not in ['teacher', 'school_principal', 'school_sub_admin', 'platform_admin']:
        raise HTTPException(status_code=403, detail="Not authorized to record attendance")

    t_id = current_user.get('tenant_id')

    result = await _attendance_engine.create_bulk_class_attendance(
        tenant_id=t_id,
        class_id=bulk_data.class_id,
        date_str=bulk_data.date,
        time_slot_id=bulk_data.time_slot_id,
        subject_id=bulk_data.subject_id,
        records=bulk_data.records,
        recorded_by=current_user['id'],
    )

    absent_late = result.get("absent_late", [])
    if absent_late:
        al_ids = [s[0] for s in absent_late]
        students_list = await db.students.find(
            {"id": {"$in": al_ids}, "tenant_id": t_id}, {"_id": 0, "id": 1, "full_name": 1, "parent_phone": 1}
        ).to_list(len(al_ids))
        student_map = {s["id"]: s for s in students_list}

        principal = await db.users.find_one({
            "role": "school_principal",
            "tenant_id": t_id,
        }, {"_id": 0, "id": 1})

        for student_id, att_status in absent_late:
            try:
                si = student_map.get(student_id)
                if not si:
                    continue
                student_name = si.get('full_name', 'طالب')
                status_ar = 'غائب' if att_status == 'absent' else 'متأخر'
                status_en = att_status

                if principal:
                    await create_notification_internal(
                        title=f"تنبيه حضور: {student_name}",
                        title_en=f"Attendance Alert: {student_name}",
                        message=f"الطالب {student_name} تم تسجيله {status_ar} في تاريخ {bulk_data.date}",
                        message_en=f"Student {student_name} was marked {status_en} on {bulk_data.date}",
                        recipient_id=principal['id'],
                        notification_type="attendance",
                        priority="high" if att_status == 'absent' else "medium",
                        sender_id=current_user['id'],
                        related_entity="student",
                        related_entity_id=student_id,
                        action_url="/admin/attendance",
                        school_id=t_id,
                    )

                if si.get('parent_phone'):
                    parent_user = await db.users.find_one({
                        "phone": si['parent_phone'], "role": "parent"
                    }, {"_id": 0, "id": 1})
                    if parent_user:
                        await create_notification_internal(
                            title=f"تنبيه حضور ابنك/ابنتك",
                            title_en=f"Attendance Alert for Your Child",
                            message=f"تم تسجيل {student_name} {status_ar} في المدرسة اليوم {bulk_data.date}",
                            message_en=f"{student_name} was marked {status_en} at school on {bulk_data.date}",
                            recipient_id=parent_user['id'],
                            notification_type="attendance",
                            priority="high" if att_status == 'absent' else "medium",
                            sender_id=current_user['id'],
                            related_entity="student",
                            related_entity_id=student_id,
                            action_url="/parent/attendance",
                            school_id=t_id,
                        )
            except Exception:
                pass

    await audit_engine.log(
        action=AuditAction.ATTENDANCE_BULK_RECORDED.value,
        performed_by=current_user['id'],
        tenant_id=t_id,
        entity_type="attendance",
        entity_id=bulk_data.class_id,
        details={
            "class_id": bulk_data.class_id,
            "date": bulk_data.date,
            "total_records": result["total_records"],
            "created": result["created"],
            "updated": result["updated"],
            "errors_count": len(result["errors"]),
            "transitions": result["transitions"],
        },
        actor_name=current_user.get("full_name"),
        actor_role=current_user.get("role"),
        actor_email=current_user.get("email"),
    )

    return {
        "message": "تم تسجيل الحضور بنجاح",
        "message_en": "Attendance recorded successfully",
        "created": result["created"],
        "updated": result["updated"],
        "errors": result["errors"],
        "date": bulk_data.date,
        "class_id": bulk_data.class_id
    }

@router.get("/attendance/class/{class_id}", response_model=List[AttendanceResponse])
async def get_class_attendance(
    class_id: str,
    date: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """Get attendance records for a class on a specific date or date range"""
    query = {"class_id": class_id}
    if start_date or end_date:
        date_filter = {}
        if start_date:
            date_filter["$gte"] = start_date
        if end_date:
            date_filter["$lte"] = end_date
        query["date"] = date_filter
    elif date:
        query["date"] = date
    else:
        query["date"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if current_user.get('tenant_id'):
        query['tenant_id'] = current_user['tenant_id']
    
    limit = 10000 if (start_date or end_date) else 1000
    records = await db.attendance.find(query, {"_id": 0}).to_list(limit)
    
    student_ids = list({r['student_id'] for r in records if r.get('student_id')})
    class_ids = list({r['class_id'] for r in records if r.get('class_id')})
    teacher_ids = list({r['teacher_id'] for r in records if r.get('teacher_id')})
    subject_ids = list({r['subject_id'] for r in records if r.get('subject_id')})
    
    import asyncio
    
    async def _empty_list():
        return []
    
    students_coro = db.students.find({"id": {"$in": student_ids}}, {"_id": 0, "id": 1, "full_name": 1}).to_list(len(student_ids)) if student_ids else _empty_list()
    classes_coro = db.classes.find({"id": {"$in": class_ids}}, {"_id": 0, "id": 1, "name": 1}).to_list(len(class_ids)) if class_ids else _empty_list()
    teachers_coro = db.users.find({"id": {"$in": teacher_ids}}, {"_id": 0, "id": 1, "full_name": 1}).to_list(len(teacher_ids)) if teacher_ids else _empty_list()
    subjects_coro = db.subjects.find({"id": {"$in": subject_ids}}, {"_id": 0, "id": 1, "name": 1}).to_list(len(subject_ids)) if subject_ids else _empty_list()
    
    students_list, classes_list, teachers_list, subjects_list = await asyncio.gather(
        students_coro, classes_coro, teachers_coro, subjects_coro
    )
    
    student_map = {s["id"]: s.get("full_name") for s in students_list}
    class_map = {c["id"]: c.get("name") for c in classes_list}
    teacher_map = {t["id"]: t.get("full_name") for t in teachers_list}
    subject_map = {s["id"]: s.get("name") for s in subjects_list}
    
    result = []
    for record in records:
        record['student_name'] = student_map.get(record.get('student_id'))
        record['class_name'] = class_map.get(record.get('class_id'))
        record['teacher_name'] = teacher_map.get(record.get('teacher_id'))
        if record.get('subject_id'):
            record['subject_name'] = subject_map.get(record['subject_id'])
        result.append(AttendanceResponse(**record))
    
    return result

@router.get("/attendance/student/{student_id}", response_model=StudentAttendanceHistory)
async def get_student_attendance_history(
    student_id: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """Get attendance history for a specific student"""
    student = await db.students.find_one({"id": student_id}, {"_id": 0})
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    
    query = {"student_id": student_id}
    if start_date:
        query['date'] = {"$gte": start_date}
    if end_date:
        if 'date' in query:
            query['date']['$lte'] = end_date
        else:
            query['date'] = {"$lte": end_date}
    
    records = await db.attendance.find(query, {"_id": 0}).sort("date", -1).to_list(1000)
    
    # Calculate statistics
    total_days = len(set(r['date'] for r in records))
    present_days = len([r for r in records if r['status'] == 'present'])
    absent_days = len([r for r in records if r['status'] == 'absent'])
    late_days = len([r for r in records if r['status'] == 'late'])
    excused_days = len([r for r in records if r['status'] == 'excused'])
    
    attendance_rate = (present_days + late_days) / total_days * 100 if total_days > 0 else 0
    
    # Enrich records
    enriched_records = []
    for record in records:
        class_info = await db.classes.find_one({"id": record['class_id']}, {"_id": 0})
        teacher = await db.users.find_one({"id": record.get('teacher_id')}, {"_id": 0})
        
        record['student_name'] = student.get('full_name')
        record['class_name'] = class_info.get('name') if class_info else None
        record['teacher_name'] = teacher.get('full_name') if teacher else None
        
        enriched_records.append(AttendanceResponse(**record))
    
    return StudentAttendanceHistory(
        student_id=student_id,
        student_name=student.get('full_name', ''),
        total_days=total_days,
        present_days=present_days,
        absent_days=absent_days,
        late_days=late_days,
        excused_days=excused_days,
        attendance_rate=round(attendance_rate, 2),
        records=enriched_records
    )

@router.get("/attendance/report/daily/{class_id}", response_model=DailyAttendanceReport)
async def get_daily_attendance_report(
    class_id: str,
    date: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """Get daily attendance report for a class"""
    if not date:
        date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    
    class_info = await db.classes.find_one({"id": class_id}, {"_id": 0})
    if not class_info:
        raise HTTPException(status_code=404, detail="Class not found")
    
    # Get all students in this class
    students = await db.students.find({"class_id": class_id}, {"_id": 0}).to_list(100)
    total_students = len(students)
    
    # Get attendance records for this date
    records = await db.attendance.find({"class_id": class_id, "date": date}, {"_id": 0}).to_list(100)
    
    # Calculate summary
    present = len([r for r in records if r['status'] == 'present'])
    absent = len([r for r in records if r['status'] == 'absent'])
    late = len([r for r in records if r['status'] == 'late'])
    excused = len([r for r in records if r['status'] == 'excused'])
    
    recorded_students = present + absent + late + excused
    attendance_rate = (present + late) / total_students * 100 if total_students > 0 else 0
    
    # Enrich records
    enriched_records = []
    for record in records:
        student = await db.students.find_one({"id": record['student_id']}, {"_id": 0})
        teacher = await db.users.find_one({"id": record.get('teacher_id')}, {"_id": 0})
        
        record['student_name'] = student.get('full_name') if student else None
        record['class_name'] = class_info.get('name')
        record['teacher_name'] = teacher.get('full_name') if teacher else None
        
        enriched_records.append(AttendanceResponse(**record))
    
    return DailyAttendanceReport(
        date=date,
        class_id=class_id,
        class_name=class_info.get('name', ''),
        summary=AttendanceSummary(
            total_students=total_students,
            present=present,
            absent=absent,
            late=late,
            excused=excused,
            attendance_rate=round(attendance_rate, 2)
        ),
        records=enriched_records
    )

@router.get("/attendance/report/summary")
async def get_attendance_summary(
    class_id: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """Get attendance summary for a period"""
    query = {}
    
    if class_id:
        query['class_id'] = class_id
    
    if current_user.get('tenant_id'):
        query['tenant_id'] = current_user['tenant_id']
    
    if start_date:
        query['date'] = {"$gte": start_date}
    if end_date:
        if 'date' in query:
            query['date']['$lte'] = end_date
        else:
            query['date'] = {"$lte": end_date}
    
    records = await db.attendance.find(query, {"_id": 0}).to_list(10000)
    
    # Group by date
    dates = list(set(r['date'] for r in records))
    dates.sort(reverse=True)
    
    daily_summaries = []
    for date in dates[:30]:  # Last 30 days
        day_records = [r for r in records if r['date'] == date]
        present = len([r for r in day_records if r['status'] == 'present'])
        absent = len([r for r in day_records if r['status'] == 'absent'])
        late = len([r for r in day_records if r['status'] == 'late'])
        excused = len([r for r in day_records if r['status'] == 'excused'])
        total = present + absent + late + excused
        
        daily_summaries.append({
            "date": date,
            "total": total,
            "present": present,
            "absent": absent,
            "late": late,
            "excused": excused,
            "attendance_rate": round((present + late) / total * 100, 2) if total > 0 else 0
        })
    
    # Overall summary
    total_records = len(records)
    overall_present = len([r for r in records if r['status'] == 'present'])
    overall_absent = len([r for r in records if r['status'] == 'absent'])
    overall_late = len([r for r in records if r['status'] == 'late'])
    overall_excused = len([r for r in records if r['status'] == 'excused'])
    
    return {
        "overall": {
            "total_records": total_records,
            "present": overall_present,
            "absent": overall_absent,
            "late": overall_late,
            "excused": overall_excused,
            "attendance_rate": round((overall_present + overall_late) / total_records * 100, 2) if total_records > 0 else 0
        },
        "daily": daily_summaries,
        "period": {
            "start": start_date or (dates[-1] if dates else None),
            "end": end_date or (dates[0] if dates else None)
        }
    }

@router.get("/attendance/students-for-class/{class_id}")
async def get_students_for_attendance(
    class_id: str,
    date: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """Get students with their attendance status for a class"""
    if not date:
        date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    
    # Get class info
    class_info = await db.classes.find_one({"id": class_id}, {"_id": 0})
    if not class_info:
        raise HTTPException(status_code=404, detail="Class not found")
    
    # Get all students in this class
    students = await db.students.find({"class_id": class_id}, {"_id": 0}).to_list(100)
    
    # Get existing attendance records for today
    existing_records = await db.attendance.find(
        {"class_id": class_id, "date": date},
        {"_id": 0}
    ).to_list(100)
    
    # Create a map of student_id -> status
    attendance_map = {r['student_id']: r for r in existing_records}
    
    # Build result with attendance status
    result = []
    for student in students:
        student_id = student['id']
        attendance_record = attendance_map.get(student_id)
        
        result.append({
            "id": student_id,
            "student_code": student.get('student_code'),
            "full_name": student.get('full_name'),
            "full_name_en": student.get('full_name_en'),
            "avatar_url": student.get('avatar_url'),
            "gender": student.get('gender'),
            "attendance_status": attendance_record.get('status') if attendance_record else None,
            "attendance_notes": attendance_record.get('notes') if attendance_record else None,
            "attendance_id": attendance_record.get('id') if attendance_record else None
        })
    
    return {
        "class_id": class_id,
        "class_name": class_info.get('name'),
        "date": date,
        "total_students": len(students),
        "recorded_count": len(existing_records),
        "students": result
    }


# ============== EXCUSE MANAGEMENT ==============

class ExcuseType(str, Enum):
    MEDICAL = "medical"
    FAMILY = "family"
    OFFICIAL = "official"
    OTHER = "other"

class ExcuseStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"

class ExcuseCreate(BaseModel):
    student_id: str
    date: str
    excuse_type: ExcuseType = ExcuseType.OTHER
    reason: Optional[str] = None
    attachment_url: Optional[str] = None

@router.post("/attendance/excuse")
async def create_excuse(
    data: ExcuseCreate,
    current_user: dict = Depends(get_current_user)
):
    """Create an attendance excuse request"""
    school_id = current_user.get("tenant_id")

    student = await db.students.find_one({"id": data.student_id, "school_id": school_id}, {"_id": 0})
    if not student:
        raise HTTPException(status_code=404, detail="الطالب غير موجود")

    excuse_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    excuse_doc = {
        "id": excuse_id,
        "student_id": data.student_id,
        "school_id": school_id,
        "date": data.date,
        "excuse_type": data.excuse_type.value,
        "reason": data.reason,
        "attachment_url": data.attachment_url,
        "status": ExcuseStatus.PENDING.value,
        "created_by": current_user["id"],
        "created_at": now,
        "reviewed_by": None,
        "reviewed_at": None
    }
    await db.attendance_excuses.insert_one(excuse_doc)
    excuse_doc.pop("_id", None)
    return excuse_doc

@router.put("/attendance/excuse/{excuse_id}/approve")
async def approve_excuse(
    excuse_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Approve an attendance excuse and update attendance record"""
    role = current_user.get("role", "")
    allowed = {"platform_admin", "school_admin", "school_principal", "school_sub_admin"}
    if role not in allowed:
        raise HTTPException(status_code=403, detail="ليس لديك صلاحية للموافقة على الأعذار")

    school_id = current_user.get("tenant_id")
    excuse = await db.attendance_excuses.find_one({"id": excuse_id, "school_id": school_id}, {"_id": 0})
    if not excuse:
        raise HTTPException(status_code=404, detail="العذر غير موجود")

    if excuse["status"] != ExcuseStatus.PENDING.value:
        raise HTTPException(status_code=400, detail="تم مراجعة هذا العذر مسبقاً")

    now = datetime.now(timezone.utc).isoformat()
    await db.attendance_excuses.update_one(
        {"id": excuse_id},
        {"$set": {"status": ExcuseStatus.APPROVED.value, "reviewed_by": current_user["id"], "reviewed_at": now}}
    )

    await db.attendance.update_many(
        {"student_id": excuse["student_id"], "date": excuse["date"], "status": "absent", "school_id": school_id},
        {"$set": {"status": "excused", "excuse_id": excuse_id, "updated_at": now}}
    )

    return {"message": "تمت الموافقة على العذر وتحديث سجل الحضور", "excuse_id": excuse_id}

@router.put("/attendance/excuse/{excuse_id}/reject")
async def reject_excuse(
    excuse_id: str,
    reason: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """Reject an attendance excuse"""
    role = current_user.get("role", "")
    allowed = {"platform_admin", "school_admin", "school_principal", "school_sub_admin"}
    if role not in allowed:
        raise HTTPException(status_code=403, detail="ليس لديك صلاحية لرفض الأعذار")

    school_id = current_user.get("tenant_id")
    excuse = await db.attendance_excuses.find_one({"id": excuse_id, "school_id": school_id}, {"_id": 0})
    if not excuse:
        raise HTTPException(status_code=404, detail="العذر غير موجود")

    now = datetime.now(timezone.utc).isoformat()
    await db.attendance_excuses.update_one(
        {"id": excuse_id, "school_id": school_id},
        {"$set": {"status": ExcuseStatus.REJECTED.value, "reviewed_by": current_user["id"], "reviewed_at": now, "rejection_reason": reason}}
    )

    return {"message": "تم رفض العذر", "excuse_id": excuse_id}

@router.get("/attendance/excuses")
async def list_excuses(
    status_filter: Optional[str] = None,
    student_id: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """List attendance excuses"""
    school_id = current_user.get("tenant_id")
    query = {}
    if school_id:
        query["school_id"] = school_id
    if status_filter:
        query["status"] = status_filter
    if student_id:
        query["student_id"] = student_id

    excuses = await db.attendance_excuses.find(query, {"_id": 0}).sort("created_at", -1).to_list(100)

    for excuse in excuses:
        student = await db.students.find_one({"id": excuse["student_id"]}, {"_id": 0, "full_name": 1, "class_id": 1})
        if student:
            excuse["student_name"] = student.get("full_name")
            excuse["class_id"] = student.get("class_id")

    return excuses


# ============== ATTENDANCE ALERTS ==============

@router.get("/attendance/alerts")
async def get_attendance_alerts(
    current_user: dict = Depends(get_current_user)
):
    """Get attendance-based alerts (low attendance, consecutive absences)"""
    school_id = current_user.get("tenant_id")
    q = {"school_id": school_id} if school_id else {}
    alerts = []
    today = datetime.now(timezone.utc)
    week_ago_str = (today - timedelta(days=7)).strftime("%Y-%m-%d")
    month_ago_str = (today - timedelta(days=30)).strftime("%Y-%m-%d")

    consecutive_pipeline = [
        {"$match": {**q, "status": "absent", "date": {"$gte": week_ago_str}}},
        {"$group": {"_id": "$student_id", "count": {"$sum": 1}, "dates": {"$push": "$date"}}},
        {"$match": {"count": {"$gte": 3}}},
        {"$sort": {"count": -1}},
        {"$limit": 20}
    ]
    chronic_students = await db.attendance.aggregate(consecutive_pipeline).to_list(20)

    for cs in chronic_students:
        student = await db.students.find_one({"id": cs["_id"]}, {"_id": 0, "full_name": 1, "class_id": 1})
        class_info = await db.classes.find_one({"id": student.get("class_id")}, {"_id": 0, "name": 1}) if student else None
        alerts.append({
            "id": str(uuid.uuid4())[:8],
            "type": "consecutive_absence",
            "severity": "critical" if cs["count"] >= 5 else "high",
            "student_id": cs["_id"],
            "student_name": student.get("full_name", "غير معروف") if student else "غير معروف",
            "class_name": class_info.get("name", "") if class_info else "",
            "absent_days": cs["count"],
            "dates": cs["dates"],
            "message": f"غاب {cs['count']} أيام خلال الأسبوع الماضي"
        })

    low_att_pipeline = [
        {"$match": {**q, "date": {"$gte": month_ago_str}}},
        {"$group": {
            "_id": "$student_id",
            "total": {"$sum": 1},
            "present": {"$sum": {"$cond": [{"$eq": ["$status", "present"]}, 1, 0]}}
        }},
        {"$addFields": {"rate": {"$multiply": [{"$divide": ["$present", "$total"]}, 100]}}},
        {"$match": {"rate": {"$lt": 75}, "total": {"$gte": 5}}},
        {"$sort": {"rate": 1}},
        {"$limit": 20}
    ]
    low_students = await db.attendance.aggregate(low_att_pipeline).to_list(20)

    for ls in low_students:
        if any(a["student_id"] == ls["_id"] for a in alerts):
            continue
        student = await db.students.find_one({"id": ls["_id"]}, {"_id": 0, "full_name": 1, "class_id": 1})
        class_info = await db.classes.find_one({"id": student.get("class_id")}, {"_id": 0, "name": 1}) if student else None
        rate = round(ls["rate"], 1)
        alerts.append({
            "id": str(uuid.uuid4())[:8],
            "type": "low_attendance",
            "severity": "critical" if rate < 60 else "high",
            "student_id": ls["_id"],
            "student_name": student.get("full_name", "غير معروف") if student else "غير معروف",
            "class_name": class_info.get("name", "") if class_info else "",
            "attendance_rate": rate,
            "total_days": ls["total"],
            "present_days": ls["present"],
            "message": f"نسبة الحضور {rate}% خلال 30 يوماً"
        })

    return {
        "total_alerts": len(alerts),
        "alerts": alerts
    }


# ============== ATTENDANCE STATISTICS ==============

@router.get("/attendance/statistics")
async def get_attendance_statistics(
    period: str = "month",
    class_id: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """Get comprehensive attendance statistics"""
    school_id = current_user.get("tenant_id")
    q = {"school_id": school_id} if school_id else {}
    if class_id:
        q["class_id"] = class_id

    today = datetime.now(timezone.utc)
    if period == "week":
        start = (today - timedelta(days=7)).strftime("%Y-%m-%d")
    elif period == "month":
        start = (today - timedelta(days=30)).strftime("%Y-%m-%d")
    elif period == "term":
        start = (today - timedelta(days=90)).strftime("%Y-%m-%d")
    else:
        start = (today - timedelta(days=30)).strftime("%Y-%m-%d")

    q["date"] = {"$gte": start}

    total = await db.attendance.count_documents(q)
    present = await db.attendance.count_documents({**q, "status": "present"})
    absent = await db.attendance.count_documents({**q, "status": "absent"})
    late = await db.attendance.count_documents({**q, "status": "late"})
    excused = await db.attendance.count_documents({**q, "status": "excused"})

    daily_pipeline = [
        {"$match": q},
        {"$group": {
            "_id": "$date",
            "total": {"$sum": 1},
            "present": {"$sum": {"$cond": [{"$eq": ["$status", "present"]}, 1, 0]}},
            "absent": {"$sum": {"$cond": [{"$eq": ["$status", "absent"]}, 1, 0]}}
        }},
        {"$sort": {"_id": 1}}
    ]
    daily_stats = await db.attendance.aggregate(daily_pipeline).to_list(90)

    return {
        "period": period,
        "start_date": start,
        "totals": {
            "total": total,
            "present": present,
            "absent": absent,
            "late": late,
            "excused": excused,
            "attendance_rate": round((present / total * 100), 1) if total > 0 else 0,
            "absence_rate": round((absent / total * 100), 1) if total > 0 else 0
        },
        "daily": [
            {
                "date": d["_id"],
                "total": d["total"],
                "present": d["present"],
                "absent": d["absent"],
                "rate": round((d["present"] / d["total"] * 100), 1) if d["total"] > 0 else 0
            }
            for d in daily_stats
        ]
    }
