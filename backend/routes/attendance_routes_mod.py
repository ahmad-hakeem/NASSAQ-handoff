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
from engines.sql_utils import gd_find, gd_find_one, gd_insert, gd_insert_many, gd_update_one, gd_update_many, gd_count, gd_delete_one, gd_delete_many, gd_distinct, _gd_aggregate
from auth_scope import require_request_school_id

from engines.attendance_engine import AttendanceEngine
from routes.notification_routes_mod import create_notification_internal
from utils.parent_resolution import resolve_students_parent_user_ids

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
    if current_user['role'] not in ['teacher', 'school_principal', 'school_sub_admin', 'platform_admin', 'independent_teacher']:
        raise HTTPException(status_code=403, detail="ليس لديك صلاحية لتسجيل الحضور")
    # IT callers carry tenant_id only on the JWT, not on the DB users row.
    from auth_scope import independent_workspace_id as _itw_id
    _eff_tenant = current_user.get('tenant_id') or _itw_id(current_user)

    # Security: fail-closed tenant resolution for non-platform callers.
    # Platform admins keep their own tenant_id (if set) or are allowed to
    # operate cross-tenant; every other caller must resolve a tenant or 403.
    _is_platform = current_user.get('role') == 'platform_admin'
    if not _is_platform and not _eff_tenant:
        raise HTTPException(status_code=403, detail="تعذّر التحقق من صلاحياتك — لا يوجد معرّف مؤسسة")

    # Tenant-pin student lookup; cross-tenant student_id → 404.
    # Soft-deleted students also return 404 so attendance cannot be
    # recorded against an inactive student.
    _student_query: dict = {"id": attendance.student_id, "is_active": True}
    if _eff_tenant:
        _student_query["$or"] = [
            {"school_id": _eff_tenant},
            {"tenant_id": _eff_tenant},
        ]
    student = await gd_find_one(db.session, "students", _student_query)
    if not student:
        raise HTTPException(status_code=404, detail="الطالب غير موجود")

    # Integrity: verify the student is actually enrolled in the submitted class.
    if student.get('class_id') and student['class_id'] != attendance.class_id:
        raise HTTPException(status_code=422, detail="الطالب غير مسجّل في هذا الفصل")

    # Tenant-pin class lookup; cross-tenant class_id → 404.
    _class_query: dict = {"id": attendance.class_id}
    if _eff_tenant and not _is_platform:
        _class_query["$or"] = [
            {"school_id": _eff_tenant},
            {"tenant_id": _eff_tenant},
        ]
    class_info = await gd_find_one(db.session, "classes", _class_query)
    if not class_info:
        raise HTTPException(status_code=404, detail="الفصل غير موجود")

    # Security: for teacher/independent_teacher callers verify they are
    # assigned to this class before allowing any write.
    if current_user['role'] in ('teacher', 'independent_teacher'):
        from utils.tenant_scope import can_view_class
        if not await can_view_class(db.session, current_user, attendance.class_id):
            raise HTTPException(status_code=403, detail="لا يمكنك تسجيل الحضور لفصل غير مرتبط بك")

    # Get subject info if provided
    subject_name = None
    if attendance.subject_id:
        subject = await gd_find_one(db.session, "subjects", {"id": attendance.subject_id})
        subject_name = subject.get('name') if subject else None
    
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    
    # Check if attendance already exists for this student, class, date
    # Tenant-pin the lookup to prevent overwriting foreign-tenant rows.
    _att_query: dict = {
        "student_id": attendance.student_id,
        "class_id": attendance.class_id,
        "date": today,
        "time_slot_id": attendance.time_slot_id,
    }
    if _eff_tenant:
        _att_query["tenant_id"] = _eff_tenant
    existing = await gd_find_one(db.session, "attendance", _att_query)
    
    if existing:
        old_status = existing.get('status')
        await gd_update_one(db.session, "attendance", {"id": existing['id']}, {
                "status": attendance.status,
                "notes": attendance.notes,
                "recorded_by": current_user['id'],
                "recorded_at": datetime.now(timezone.utc).isoformat()
            })
        
        await audit_engine.log(
            action=AuditAction.ATTENDANCE_RECORDED.value,
            performed_by=current_user['id'],
            tenant_id=_eff_tenant,
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
        
        updated = await gd_find_one(db.session, "attendance", {"id": existing['id']})
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
        "tenant_id": _eff_tenant
    }
    
    await gd_insert(db.session, "attendance", attendance_doc)
    
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
        "tenant_id": _eff_tenant
    }
    await gd_insert(db.session, "events", event_doc)
    
    await audit_engine.log(
        action=AuditAction.ATTENDANCE_RECORDED.value,
        performed_by=current_user['id'],
        tenant_id=_eff_tenant,
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
    if current_user['role'] not in ['teacher', 'school_principal', 'school_sub_admin', 'platform_admin', 'independent_teacher']:
        raise HTTPException(status_code=403, detail="Not authorized to record attendance")

    from auth_scope import independent_workspace_id as _itw_id
    t_id = current_user.get('tenant_id') or _itw_id(current_user)

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
        students_list = await gd_find(db.session, "students", {"id": {"$in": al_ids}, "tenant_id": t_id, "is_active": True}, limit=len(al_ids))
        student_map = {s["id"]: s for s in students_list}

        principal = await gd_find_one(db.session, "users", {
            "role": "school_principal",
            "tenant_id": t_id,
        })

        # Resolve parent user IDs in bulk — uses guardian_links first,
        # falls back to students.parent_id. No mutable phone/email matching.
        parent_uid_map = await resolve_students_parent_user_ids(al_ids, t_id)

        # IT-aware venue text resolved once per request to avoid re-querying
        # the users table for every absent student in the loop.
        _venue_ar = "في المدرسة"
        _venue_en = "at school"
        if isinstance(t_id, str) and t_id.startswith("itw_"):
            _owner = await gd_find_one(
                db.session, "users", {"id": t_id[len("itw_"):]}
            )
            _tname = (_owner or {}).get("full_name")
            if _tname:
                _venue_ar = f"لدى الأستاذ/ة {_tname}"
                _venue_en = f"with {_tname}"

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

                parent_uid = parent_uid_map.get(student_id)
                if parent_uid:
                    await create_notification_internal(
                        title=f"تنبيه حضور ابنك/ابنتك",
                        title_en=f"Attendance Alert for Your Child",
                        message=f"تم تسجيل {student_name} {status_ar} {_venue_ar} اليوم {bulk_data.date}",
                        message_en=f"{student_name} was marked {status_en} {_venue_en} on {bulk_data.date}",
                        recipient_id=parent_uid,
                        notification_type="attendance",
                        priority="high" if att_status == 'absent' else "medium",
                        sender_id=current_user['id'],
                        related_entity="student",
                        related_entity_id=student_id,
                        action_url="/parent/attendance",
                        school_id=t_id,
                    )
            except Exception as e:
                logging.getLogger(__name__).warning("Attendance notification failed for student %s: %s", student_id, e)

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

    try:
        from engines.portfolio_evidence_engine import PortfolioEvidenceEngine
        _pe = PortfolioEvidenceEngine(db)
        await _pe.capture_evidence(
            teacher_id=current_user["id"],
            school_id=t_id or "",
            evidence_type="attendance_record",
            title_ar=f"سجل حضور: {bulk_data.date}",
            title_en=f"Attendance Record: {bulk_data.date}",
            description_ar=f"تسجيل حضور {result['created']} طالب",
            description_en=f"Recorded attendance for {result['created']} students",
            source="auto", source_entity_type="attendance_bulk",
            source_entity_id=f"{bulk_data.class_id}_{bulk_data.date}",
            class_id=bulk_data.class_id,
            metadata={"created": result["created"], "updated": result["updated"]},
            event_date=bulk_data.date,
        )
    except Exception as _pe_err:
        logging.getLogger(__name__).debug("Portfolio evidence (bulk_attendance) failed: %s", _pe_err)

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
    # Security: parents and students must not be able to read class attendance.
    _allowed_read_roles = {'teacher', 'school_principal', 'school_sub_admin', 'school_admin', 'platform_admin', 'independent_teacher'}
    if current_user.get('role') not in _allowed_read_roles:
        raise HTTPException(status_code=403, detail="لا يمكنك الاطلاع على بيانات حضور الفصل")

    # Phase 0 §4.B-4 — IT users carry tenant_id=None on the JWT; scope to
    # their synthetic workspace via the canonical resolver so cross-IT
    # attendance never leaks even when a class id is guessed/shared.
    # Fail-closed: non-platform callers without a resolvable tenant get 403.
    _is_platform = current_user.get('role') == 'platform_admin'
    _eff_tenant = require_request_school_id(current_user) if not _is_platform else current_user.get('tenant_id')

    # Verify the class belongs to the caller's tenant before returning any data.
    _cls_q: dict = {"id": class_id}
    if _eff_tenant and not _is_platform:
        _cls_q["$or"] = [{"school_id": _eff_tenant}, {"tenant_id": _eff_tenant}]
    _cls = await gd_find_one(db.session, "classes", _cls_q)
    if not _cls:
        raise HTTPException(status_code=404, detail="الفصل غير موجود")

    # For teacher/IT callers, ensure they are actually assigned to this class.
    if current_user.get('role') in ('teacher', 'independent_teacher'):
        from utils.tenant_scope import can_view_class
        if not await can_view_class(db.session, current_user, class_id):
            raise HTTPException(status_code=403, detail="لا يمكنك الاطلاع على بيانات حضور هذا الفصل")

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

    if _eff_tenant:
        query['tenant_id'] = _eff_tenant
    
    limit = 10000 if (start_date or end_date) else 1000
    records = await gd_find(db.session, "attendance", query, limit=limit)
    
    student_ids = list({r['student_id'] for r in records if r.get('student_id')})
    class_ids = list({r['class_id'] for r in records if r.get('class_id')})
    teacher_ids = list({r['teacher_id'] for r in records if r.get('teacher_id')})
    subject_ids = list({r['subject_id'] for r in records if r.get('subject_id')})
    
    import asyncio
    
    async def _empty_list():
        return []
    
    students_coro = gd_find(db.session, "students", {"id": {"$in": student_ids}, "is_active": True}, limit=len(student_ids)) if student_ids else _empty_list()
    classes_coro = gd_find(db.session, "classes", {"id": {"$in": class_ids}, "is_active": {"$ne": False}}, limit=len(class_ids)) if class_ids else _empty_list()
    teachers_coro = gd_find(db.session, "users", {"id": {"$in": teacher_ids}}, limit=len(teacher_ids)) if teacher_ids else _empty_list()
    subjects_coro = gd_find(db.session, "subjects", {"id": {"$in": subject_ids}}, limit=len(subject_ids)) if subject_ids else _empty_list()
    
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
    # SECURITY (Task #203 + audit H-1):
    # 1) Tenant pin FIRST — cross-workspace lookups MUST 404 (spec §8
    #    invariant 3), never 403, so we don't confirm the existence of
    #    a student in another tenant.
    # 2) Same-tenant alone is not sufficient — also require an explicit
    #    guardian/teacher/admin/self relationship before exposing this
    #    student's attendance history.
    from auth_scope import require_request_school_id
    from utils.tenant_scope import can_view_student, require_can_view_student_sync_check
    tenant_id = require_request_school_id(current_user)
    student = await gd_find_one(
        db.session, "students",
        {"id": student_id, "school_id": tenant_id, "is_active": True},
    )
    if not student:
        # Fallback for legacy rows that pin tenant on the alternate column.
        student = await gd_find_one(
            db.session, "students",
            {"id": student_id, "tenant_id": tenant_id, "is_active": True},
        )
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    require_can_view_student_sync_check(
        await can_view_student(db.session, current_user, student_id)
    )
    
    query = {"student_id": student_id}
    if start_date:
        query['date'] = {"$gte": start_date}
    if end_date:
        if 'date' in query:
            query['date']['$lte'] = end_date
        else:
            query['date'] = {"$lte": end_date}
    
    records = await gd_find(db.session, "attendance", query, order_by="date", desc_order=True, limit=1000)
    
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
        class_info = await gd_find_one(db.session, "classes", {"id": record['class_id']})
        teacher = await gd_find_one(db.session, "users", {"id": record.get('teacher_id')})
        
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
    # Security: restrict to staff roles only.
    _allowed_report_roles = {'teacher', 'school_principal', 'school_sub_admin', 'school_admin', 'platform_admin', 'independent_teacher'}
    if current_user.get('role') not in _allowed_report_roles:
        raise HTTPException(status_code=403, detail="لا يمكنك الاطلاع على تقرير الحضور اليومي")

    # Fail-closed tenant resolution for non-platform callers.
    _is_platform = current_user.get('role') == 'platform_admin'
    _eff_tenant = require_request_school_id(current_user) if not _is_platform else current_user.get('tenant_id')

    # Tenant-pin the class lookup so cross-tenant class IDs 404 instead of leaking.
    _cls_q: dict = {"id": class_id}
    if _eff_tenant and not _is_platform:
        _cls_q["$or"] = [{"school_id": _eff_tenant}, {"tenant_id": _eff_tenant}]
    class_info = await gd_find_one(db.session, "classes", _cls_q)
    if not class_info:
        raise HTTPException(status_code=404, detail="الفصل غير موجود")

    # For teacher/IT callers, verify class assignment.
    if current_user.get('role') in ('teacher', 'independent_teacher'):
        from utils.tenant_scope import can_view_class
        if not await can_view_class(db.session, current_user, class_id):
            raise HTTPException(status_code=403, detail="لا يمكنك الاطلاع على تقرير هذا الفصل")

    if not date:
        date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    
    # Tenant-pin student and attendance queries.
    _students_q: dict = {"class_id": class_id, "is_active": True}
    _att_q: dict = {"class_id": class_id, "date": date}
    if _eff_tenant:
        _students_q["$or"] = [{"school_id": _eff_tenant}, {"tenant_id": _eff_tenant}]
        _att_q["tenant_id"] = _eff_tenant

    # Get all students in this class
    students = await gd_find(db.session, "students", _students_q, limit=100)
    total_students = len(students)
    
    # Get attendance records for this date
    records = await gd_find(db.session, "attendance", _att_q, limit=100)
    
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
        student = await gd_find_one(db.session, "students", {"id": record['student_id'], "is_active": True})
        teacher = await gd_find_one(db.session, "users", {"id": record.get('teacher_id')})
        
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
    """Get attendance summary for a period.

    SECURITY: School-wide attendance summaries are restricted to staff roles.
    Parents and students must not access aggregate reporting that belongs to
    authorized staff only.
    Teachers and independent teachers must supply a class_id that they own;
    they cannot access school-wide or arbitrary-class summaries.
    """
    _allowed_summary_roles = {
        "platform_admin", "school_admin", "school_principal",
        "school_sub_admin", "teacher", "independent_teacher",
    }
    _teacher_roles = {"teacher", "independent_teacher"}
    role = current_user.get("role")
    if role not in _allowed_summary_roles:
        raise HTTPException(status_code=403, detail="لا يمكنك الاطلاع على تقارير الحضور")
    # Task #155 (audit row #14, post-review): fail-closed scope. Previously
    # this endpoint allowed `query = {}` plus a tenant filter only when one
    # was present, leaking cross-tenant attendance summaries to any caller
    # whose `tenant_id` was missing. Use the canonical adapter instead.
    school_id = require_request_school_id(current_user)
    query = {'tenant_id': school_id}

    # Task #428: teachers must provide a class_id they are assigned to;
    # school-wide or cross-class queries are admin-only.
    if role in _teacher_roles:
        if not class_id:
            raise HTTPException(status_code=403, detail="يجب تحديد الفصل الدراسي للاطلاع على تقرير الحضور")
        from utils.tenant_scope import can_view_class
        if not await can_view_class(db.session, current_user, class_id):
            raise HTTPException(status_code=403, detail="لا يمكنك الاطلاع على بيانات هذا الفصل")

    if class_id:
        query['class_id'] = class_id
    
    if start_date:
        query['date'] = {"$gte": start_date}
    if end_date:
        if 'date' in query:
            query['date']['$lte'] = end_date
        else:
            query['date'] = {"$lte": end_date}
    
    records = await gd_find(db.session, "attendance", query, limit=10000)
    
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
    # Security: parents and students must not read other students' attendance.
    _allowed_sfc_roles = {'teacher', 'school_principal', 'school_sub_admin', 'school_admin', 'platform_admin', 'independent_teacher'}
    if current_user.get('role') not in _allowed_sfc_roles:
        raise HTTPException(status_code=403, detail="لا يمكنك الاطلاع على بيانات الفصل")

    # Fail-closed tenant resolution for non-platform callers.
    _is_platform = current_user.get('role') == 'platform_admin'
    _eff_tenant = require_request_school_id(current_user) if not _is_platform else current_user.get('tenant_id')

    # Tenant-pin the class lookup.
    _cls_q: dict = {"id": class_id}
    if _eff_tenant and not _is_platform:
        _cls_q["$or"] = [{"school_id": _eff_tenant}, {"tenant_id": _eff_tenant}]
    class_info = await gd_find_one(db.session, "classes", _cls_q)
    if not class_info:
        raise HTTPException(status_code=404, detail="الفصل غير موجود")

    # For teacher/IT callers, verify assignment to this class.
    if current_user.get('role') in ('teacher', 'independent_teacher'):
        from utils.tenant_scope import can_view_class
        if not await can_view_class(db.session, current_user, class_id):
            raise HTTPException(status_code=403, detail="لا يمكنك الاطلاع على بيانات هذا الفصل")

    if not date:
        date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Tenant-pin student and attendance queries.
    _students_q: dict = {"class_id": class_id, "is_active": True}
    _att_q: dict = {"class_id": class_id, "date": date}
    if _eff_tenant:
        _students_q["$or"] = [{"school_id": _eff_tenant}, {"tenant_id": _eff_tenant}]
        _att_q["tenant_id"] = _eff_tenant

    # Get all students in this class
    students = await gd_find(db.session, "students", _students_q, limit=100)
    
    # Get existing attendance records for today
    existing_records = await gd_find(db.session, "attendance", _att_q, limit=100)
    
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


# Task #466 — unify staff-side excuse endpoints on the `absence_excuses`
# table written by the parent portal (`POST /parent-portal/absence-excuse`).
# The legacy `attendance_excuses` table is left untouched (no migration) but
# is no longer read or written from this module. Field-name mapping is
# preserved at the API boundary so existing staff callers continue to use
# `student_id` / `date` while persistence uses `child_id` / `absence_date`.

_EXCUSE_TABLE = "absence_excuses"
_EXCUSE_REVIEW_ROLES = {
    "platform_admin", "school_admin", "school_principal", "school_sub_admin",
}
_EXCUSE_LIST_ROLES = _EXCUSE_REVIEW_ROLES | {"teacher", "independent_teacher"}
_EXCUSE_TEACHER_ROLES = {"teacher", "independent_teacher"}


def _serialize_excuse(row: dict, student: Optional[dict] = None) -> dict:
    """Project an `absence_excuses` row onto the principal-review shape.

    Exposes both the canonical parent-portal field names (`child_id`,
    `absence_date`) and the staff-side aliases (`student_id`, `date`) so
    existing API consumers keep working. Strips secret/internal fields.
    """
    if not row:
        return {}
    out = {
        "id": row.get("id"),
        "status": row.get("status"),
        "child_id": row.get("child_id") or row.get("student_id"),
        "child_name": row.get("child_name"),
        "parent_id": row.get("parent_id"),
        "parent_name": row.get("parent_name"),
        "absence_date": row.get("absence_date") or row.get("date"),
        "reason": row.get("reason"),
        "attachment_url": row.get("attachment_url"),
        "attachment_name": row.get("attachment_name"),
        "school_id": row.get("school_id"),
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
        "reviewed_by": row.get("reviewed_by"),
        "reviewed_at": row.get("reviewed_at"),
        "rejection_reason": row.get("rejection_reason"),
        "excuse_type": row.get("excuse_type"),
    }
    # Back-compat aliases used by older staff clients.
    out["student_id"] = out["child_id"]
    out["date"] = out["absence_date"]
    if student:
        out["student_name"] = student.get("full_name") or out.get("child_name")
        out["class_id"] = student.get("class_id")
        if not out.get("child_name"):
            out["child_name"] = student.get("full_name")
    return out


async def _teacher_scope_student_ids(
    current_user: dict, school_id: str
) -> Optional[List[str]]:
    """Return the set of `students.id` a teacher can see for this endpoint,
    or `None` if the teacher has no assigned classes (caller should return
    an empty result in that case)."""
    user_id = current_user.get("id")
    teacher_id = current_user.get("teacher_id") or user_id
    assigned_classes = await gd_find(
        db.session, "teacher_assignments", {"teacher_id": teacher_id}, limit=500
    )
    session_classes = await gd_find(
        db.session, "class_sessions", {"teacher_id": teacher_id}, limit=500
    )
    class_ids = list({
        row["class_id"]
        for row in (assigned_classes + session_classes)
        if row.get("class_id")
    })
    if not class_ids:
        return None
    teacher_students = await gd_find(
        db.session, "students",
        {"class_id": {"$in": class_ids}, "school_id": school_id},
        limit=5000,
    )
    return [s["id"] for s in teacher_students if s.get("id")]


@router.post("/attendance/excuse")
async def create_excuse(
    data: ExcuseCreate,
    current_user: dict = Depends(get_current_user)
):
    """Create an attendance excuse request from a staff/guardian surface.

    Task #466: writes to the unified `absence_excuses` table so the row is
    visible to both the parent excuse-history surface and the principal
    review surface.

    SECURITY: The caller must be the student's guardian, the student
    themselves, a teacher assigned to the student's class, or an admin
    role. Any authenticated tenant user could otherwise submit fraudulent
    excuses for unrelated students.
    """
    school_id = current_user.get("tenant_id")

    student = await gd_find_one(db.session, "students", {"id": data.student_id, "school_id": school_id, "is_active": True})
    if not student:
        raise HTTPException(status_code=404, detail="الطالب غير موجود")

    from utils.tenant_scope import can_view_student, require_can_view_student_sync_check
    allowed = await can_view_student(db.session, current_user, data.student_id)
    require_can_view_student_sync_check(allowed)

    excuse_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    excuse_doc = {
        "id": excuse_id,
        # Canonical parent-portal field names.
        "child_id": data.student_id,
        "child_name": student.get("full_name"),
        "school_id": school_id,
        "absence_date": data.date,
        "reason": data.reason,
        "attachment_url": data.attachment_url,
        "attachment_name": None,
        "status": ExcuseStatus.PENDING.value,
        # Staff-originated rows have no parent_id but record the actor.
        "parent_id": None,
        "parent_name": current_user.get("full_name", ""),
        "excuse_type": data.excuse_type.value,
        "created_by": current_user["id"],
        "created_at": now,
        "updated_at": now,
        "reviewed_by": None,
        "reviewed_at": None,
    }
    await gd_insert(db.session, _EXCUSE_TABLE, excuse_doc)
    excuse_doc.pop("_id", None)
    return _serialize_excuse(excuse_doc, student)


@router.put("/attendance/excuse/{excuse_id}/approve")
async def approve_excuse(
    excuse_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Approve an absence excuse and cascade to the matching attendance row."""
    role = current_user.get("role", "")
    if role not in _EXCUSE_REVIEW_ROLES:
        raise HTTPException(status_code=403, detail="ليس لديك صلاحية للموافقة على الأعذار")

    school_id = require_request_school_id(current_user)
    # §8 invariant: cross-tenant by-id reads must 404, never 403/200.
    excuse = await gd_find_one(db.session, _EXCUSE_TABLE, {"id": excuse_id, "school_id": school_id})
    if not excuse:
        raise HTTPException(status_code=404, detail="العذر غير موجود")

    if excuse.get("status") != ExcuseStatus.PENDING.value:
        raise HTTPException(status_code=400, detail="تم مراجعة هذا العذر مسبقاً")

    now = datetime.now(timezone.utc).isoformat()
    await gd_update_one(
        db.session, _EXCUSE_TABLE, {"id": excuse_id, "school_id": school_id},
        {
            "status": ExcuseStatus.APPROVED.value,
            "reviewed_by": current_user["id"],
            "reviewed_at": now,
            "updated_at": now,
        },
    )

    student_id = excuse.get("child_id") or excuse.get("student_id")
    absence_date = excuse.get("absence_date") or excuse.get("date")
    if student_id and absence_date:
        await gd_update_many(
            db.session, "attendance",
            {
                "student_id": student_id,
                "date": absence_date,
                "status": "absent",
                "school_id": school_id,
            },
            {
                "status": "excused",
                "is_excused": True,
                "excuse_reason": excuse.get("reason"),
                "updated_at": now,
            },
        )

    return {"message": "تمت الموافقة على العذر وتحديث سجل الحضور", "excuse_id": excuse_id}


class ExcuseRejectBody(BaseModel):
    reason: Optional[str] = None


@router.put("/attendance/excuse/{excuse_id}/reject")
async def reject_excuse(
    excuse_id: str,
    body: Optional[ExcuseRejectBody] = None,
    reason: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """Reject an absence excuse, optionally with a rejection reason."""
    role = current_user.get("role", "")
    if role not in _EXCUSE_REVIEW_ROLES:
        raise HTTPException(status_code=403, detail="ليس لديك صلاحية لرفض الأعذار")

    school_id = require_request_school_id(current_user)
    excuse = await gd_find_one(db.session, _EXCUSE_TABLE, {"id": excuse_id, "school_id": school_id})
    if not excuse:
        raise HTTPException(status_code=404, detail="العذر غير موجود")

    if excuse.get("status") != ExcuseStatus.PENDING.value:
        raise HTTPException(status_code=400, detail="تم مراجعة هذا العذر مسبقاً")

    effective_reason = (body.reason if body and body.reason is not None else reason)
    now = datetime.now(timezone.utc).isoformat()
    await gd_update_one(
        db.session, _EXCUSE_TABLE, {"id": excuse_id, "school_id": school_id},
        {
            "status": ExcuseStatus.REJECTED.value,
            "reviewed_by": current_user["id"],
            "reviewed_at": now,
            "updated_at": now,
            "rejection_reason": effective_reason,
        },
    )

    return {"message": "تم رفض العذر", "excuse_id": excuse_id}


@router.get("/attendance/excuses")
async def list_excuses(
    status_filter: Optional[str] = None,
    student_id: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """List absence excuses for the principal/teacher review surface.

    SECURITY: School-wide excuse listing is restricted to staff roles.
    Parents and students must not be able to enumerate other families'
    excuse records, absence reasons, or attachment URLs. Teachers and
    independent teachers are further restricted to students in their own
    assigned classes; they cannot enumerate excuses school-wide or for
    students in classes they do not teach.
    """
    role = current_user.get("role")
    if role not in _EXCUSE_LIST_ROLES:
        raise HTTPException(status_code=403, detail="لا يمكنك الاطلاع على سجلات الأعذار")
    school_id = require_request_school_id(current_user)

    query: Dict[str, Any] = {"school_id": school_id}
    if status_filter:
        query["status"] = status_filter

    # Map staff-side `student_id` filter onto persisted `child_id`.
    if role in _EXCUSE_TEACHER_ROLES:
        from utils.tenant_scope import can_view_student
        if student_id:
            allowed = await can_view_student(db.session, current_user, student_id)
            if not allowed:
                raise HTTPException(status_code=403, detail="لا يمكنك الاطلاع على بيانات هذا الطالب")
            query["child_id"] = student_id
        else:
            allowed_student_ids = await _teacher_scope_student_ids(current_user, school_id)
            if not allowed_student_ids:
                return []
            query["child_id"] = {"$in": allowed_student_ids}
    elif student_id:
        query["child_id"] = student_id

    excuses = await gd_find(
        db.session, _EXCUSE_TABLE, query,
        order_by="created_at", desc_order=True, limit=200,
    )
    if not excuses:
        return []

    # Bulk-load students in one query to avoid N+1.
    student_ids = list({e.get("child_id") for e in excuses if e.get("child_id")})
    student_rows = []
    if student_ids:
        student_rows = await gd_find(
            db.session, "students",
            {"id": {"$in": student_ids}, "school_id": school_id, "is_active": True},
            limit=len(student_ids) + 1,
        )
    student_by_id = {s["id"]: s for s in student_rows if s.get("id")}

    return [_serialize_excuse(e, student_by_id.get(e.get("child_id"))) for e in excuses]


@router.get("/attendance/excuses/pending-count")
async def pending_excuses_count(
    current_user: dict = Depends(get_current_user)
):
    """Lightweight badge endpoint — returns the count of pending excuses
    scoped to the caller's tenant + role-scope (mirrors `list_excuses`)."""
    role = current_user.get("role")
    if role not in _EXCUSE_LIST_ROLES:
        raise HTTPException(status_code=403, detail="لا يمكنك الاطلاع على سجلات الأعذار")
    school_id = require_request_school_id(current_user)

    query: Dict[str, Any] = {"school_id": school_id, "status": ExcuseStatus.PENDING.value}
    if role in _EXCUSE_TEACHER_ROLES:
        allowed_student_ids = await _teacher_scope_student_ids(current_user, school_id)
        if not allowed_student_ids:
            return {"count": 0}
        query["child_id"] = {"$in": allowed_student_ids}

    count = await gd_count(db.session, _EXCUSE_TABLE, query)
    return {"count": int(count or 0)}


# ============== ATTENDANCE ALERTS ==============

@router.get("/attendance/alerts")
async def get_attendance_alerts(
    current_user: dict = Depends(get_current_user)
):
    """Get attendance-based alerts (low attendance, consecutive absences).

    SECURITY: Teachers may only see alerts for students in their own assigned
    classes. School-wide alerts are restricted to admin/principal roles.
    """
    # Security: school-wide alert data must only be visible to staff.
    _allowed_alert_roles = {'teacher', 'school_principal', 'school_sub_admin', 'school_admin', 'platform_admin', 'independent_teacher'}
    if current_user.get('role') not in _allowed_alert_roles:
        raise HTTPException(status_code=403, detail="لا يمكنك الاطلاع على تنبيهات الحضور")
    # Task #155: replace the original tenantless fallback (`{} if not school_id`)
    # with a fail-closed adapter that 403's on resolution failure. See
    # docs/security/2026-05-ai-teacher-scope-audit.md row #1.
    school_id = require_request_school_id(current_user)
    q = {"school_id": school_id}

    # Teachers must only see alerts for students in their assigned classes.
    if current_user.get("role") in ("teacher", "independent_teacher"):
        teacher_id = current_user.get("teacher_id") or current_user.get("id")
        ta_rows = await gd_find(db.session, "teacher_assignments",
                                {"teacher_id": teacher_id}, limit=500)
        cs_rows = await gd_find(db.session, "class_sessions",
                                {"teacher_id": teacher_id}, limit=500)
        teacher_class_ids = list({r["class_id"] for r in ta_rows + cs_rows if r.get("class_id")})
        if not teacher_class_ids:
            return {"total_alerts": 0, "alerts": []}
        q = {**q, "class_id": {"$in": teacher_class_ids}}

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
    chronic_students = await _gd_aggregate(db.session, "attendance", consecutive_pipeline)

    for cs in chronic_students:
        student = await gd_find_one(db.session, "students", {"id": cs["_id"], "is_active": True})
        class_info = await gd_find_one(db.session, "classes", {"id": student.get("class_id")}) if student else None
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
    low_students = await _gd_aggregate(db.session, "attendance", low_att_pipeline)

    for ls in low_students:
        if any(a["student_id"] == ls["_id"] for a in alerts):
            continue
        student = await gd_find_one(db.session, "students", {"id": ls["_id"], "is_active": True})
        class_info = await gd_find_one(db.session, "classes", {"id": student.get("class_id")}) if student else None
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
    """Get comprehensive attendance statistics.

    SECURITY: Teachers and independent teachers must supply a class_id they
    own; school-wide or cross-class statistics are admin-only.
    """
    # Security: school-wide statistics must only be visible to staff.
    _allowed_stats_roles = {'teacher', 'school_principal', 'school_sub_admin', 'school_admin', 'platform_admin', 'independent_teacher'}
    _teacher_roles = {'teacher', 'independent_teacher'}
    role = current_user.get('role')
    if role not in _allowed_stats_roles:
        raise HTTPException(status_code=403, detail="لا يمكنك الاطلاع على إحصائيات الحضور")
    # Task #155: fail-closed school-id resolution; see audit row #2.
    school_id = require_request_school_id(current_user)
    q = {"school_id": school_id}

    # Task #428: teachers must provide and own the class_id they query;
    # same-school membership alone is not sufficient.
    if role in _teacher_roles:
        if not class_id:
            raise HTTPException(status_code=403, detail="يجب تحديد الفصل الدراسي للاطلاع على الإحصائيات")
        from utils.tenant_scope import can_view_class
        if not await can_view_class(db.session, current_user, class_id):
            raise HTTPException(status_code=403, detail="لا يمكنك الاطلاع على بيانات هذا الفصل")

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

    total = await gd_count(db.session, "attendance", q)
    present = await gd_count(db.session, "attendance", {**q, "status": "present"})
    absent = await gd_count(db.session, "attendance", {**q, "status": "absent"})
    late = await gd_count(db.session, "attendance", {**q, "status": "late"})
    excused = await gd_count(db.session, "attendance", {**q, "status": "excused"})

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
    daily_stats = await _gd_aggregate(db.session, "attendance", daily_pipeline)

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
