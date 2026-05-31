"""
NASSAQ Attendance Routes
مسارات API للحضور والغياب

Endpoints:
- Record attendance
- Bulk attendance
- Attendance reports
- Excuse management
- Alerts
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional, Literal
from pydantic import BaseModel
from datetime import datetime, date
import logging

# Canonical student-attendance status set — mirrors
# `backend/models/enums.py::AttendanceStatus`. Pydantic Literal rejects
# unknown statuses at the API boundary with 422 before they reach the
# attendance engine or the database.
AttendanceStatusLiteral = Literal["present", "absent", "late", "excused"]

from dependencies import audit_engine, AuditAction

logger = logging.getLogger("nassaq.attendance_routes")
from engines.sql_utils import gd_find, gd_find_one, gd_insert, gd_insert_many, gd_update_one, gd_update_many, gd_count, gd_delete_one, gd_delete_many, gd_distinct



# ============== MODELS ==============

class AttendanceRecord(BaseModel):
    student_id: str
    status: AttendanceStatusLiteral = "present"
    arrival_time: Optional[str] = None
    departure_time: Optional[str] = None
    notes: Optional[str] = None


class AttendanceCreate(BaseModel):
    student_id: str
    section_id: str
    attendance_date: str
    status: AttendanceStatusLiteral = "present"
    arrival_time: Optional[str] = None
    departure_time: Optional[str] = None
    notes: Optional[str] = None
    session_id: Optional[str] = None
    period: Optional[int] = None


class BulkAttendanceCreate(BaseModel):
    section_id: str
    attendance_date: str
    records: List[AttendanceRecord]


class MarkAllPresentRequest(BaseModel):
    section_id: str
    attendance_date: str
    student_ids: List[str]


class ExcuseCreate(BaseModel):
    student_id: str
    excuse_type: str
    start_date: str
    end_date: str
    reason: str
    attachment_url: Optional[str] = None


class AttendanceResponse(BaseModel):
    id: str
    tenant_id: str
    student_id: str
    section_id: str
    attendance_date: str
    status: str
    arrival_time: Optional[str] = None
    departure_time: Optional[str] = None
    notes: Optional[str] = None
    recorded_at: str
    recorded_by: str


class AttendanceSummary(BaseModel):
    student_id: str
    total_days: int
    present_days: int
    absent_days: int
    late_days: int
    excused_days: int
    attendance_rate: float
    absence_rate: float
    late_rate: float


def create_attendance_router(db, get_current_user, require_roles, UserRole):
    """Factory function to create attendance router with dependencies"""
    
    router = APIRouter(prefix="/attendance", tags=["Attendance"])
    
    # Initialize engine
    from engines.attendance_engine import AttendanceEngine
    engine = AttendanceEngine(db)
    
    # ============== RECORDING ==============
    
    @router.post("/record", response_model=AttendanceResponse)
    async def record_attendance(
        data: AttendanceCreate,
        current_user: dict = Depends(require_roles([
            UserRole.PLATFORM_ADMIN,
            UserRole.SCHOOL_PRINCIPAL,
            UserRole.SCHOOL_ADMIN,
            UserRole.TEACHER
        ]))
    ):
        """Record attendance for a single student"""
        tenant_id = current_user.get("tenant_id") or current_user.get("primary_tenant_id")
        
        if not tenant_id:
            raise HTTPException(status_code=400, detail="يجب تحديد المدرسة")

        # Task #428: teachers must own the target section/class before writing
        # attendance. Same-school membership alone is not sufficient.
        # Additionally, the target student must belong to that section so a
        # teacher cannot use their own valid class_id but supply a foreign
        # student_id to tamper with another class's records.
        _teacher_write_roles = {UserRole.TEACHER.value}
        if current_user.get("role") in _teacher_write_roles:
            from utils.tenant_scope import can_view_class
            if not await can_view_class(db.session, current_user, data.section_id):
                raise HTTPException(status_code=403, detail="لا يمكنك تسجيل الحضور لهذا الفصل")
            # Verify student is enrolled in the supplied section (class).
            _target_student = await gd_find_one(
                db.session, "students",
                {"id": data.student_id, "school_id": tenant_id, "class_id": data.section_id}
            )
            if not _target_student:
                raise HTTPException(status_code=403, detail="الطالب غير مسجل في هذا الفصل")

        record = await engine.record_attendance(
            tenant_id=tenant_id,
            student_id=data.student_id,
            section_id=data.section_id,
            attendance_date=data.attendance_date,
            status=data.status,
            recorded_by=current_user["id"],
            arrival_time=data.arrival_time,
            departure_time=data.departure_time,
            notes=data.notes,
            session_id=data.session_id,
            period=data.period
        )
        
        await audit_engine.log(
            action=AuditAction.ATTENDANCE_RECORDED.value,
            performed_by=current_user["id"],
            tenant_id=tenant_id,
            entity_type="attendance",
            entity_id=record.get("id", ""),
            details={
                "student_id": data.student_id,
                "section_id": data.section_id,
                "date": data.attendance_date,
                "old_status": record.get("old_status"),
                "new_status": data.status,
            },
            actor_name=current_user.get("full_name"),
            actor_role=current_user.get("role"),
            actor_email=current_user.get("email"),
        )
        
        return record
    
    @router.post("/bulk")
    async def record_bulk_attendance(
        data: BulkAttendanceCreate,
        current_user: dict = Depends(require_roles([
            UserRole.PLATFORM_ADMIN,
            UserRole.SCHOOL_PRINCIPAL,
            UserRole.SCHOOL_ADMIN,
            UserRole.TEACHER
        ]))
    ):
        """Record attendance for multiple students"""
        tenant_id = current_user.get("tenant_id") or current_user.get("primary_tenant_id")
        
        if not tenant_id:
            raise HTTPException(status_code=400, detail="يجب تحديد المدرسة")
        
        results = await engine.record_bulk_attendance(
            tenant_id=tenant_id,
            section_id=data.section_id,
            attendance_date=data.attendance_date,
            attendance_records=[r.dict() for r in data.records],
            recorded_by=current_user["id"]
        )
        
        await audit_engine.log(
            action=AuditAction.ATTENDANCE_BULK_RECORDED.value,
            performed_by=current_user["id"],
            tenant_id=tenant_id,
            entity_type="attendance",
            entity_id=data.section_id,
            details={
                "section_id": data.section_id,
                "date": data.attendance_date,
                "total_records": len(data.records),
                "processed": results.get("processed", 0),
                "created": results.get("created", 0),
                "updated": results.get("updated", 0),
                "transitions": results.get("transitions", []),
            },
            actor_name=current_user.get("full_name"),
            actor_role=current_user.get("role"),
            actor_email=current_user.get("email"),
        )
        
        return {
            "message": f"تم تسجيل حضور {results['processed']} طالب",
            "results": results
        }
    
    @router.post("/mark-all-present")
    async def mark_class_present(
        data: MarkAllPresentRequest,
        current_user: dict = Depends(require_roles([
            UserRole.PLATFORM_ADMIN,
            UserRole.SCHOOL_PRINCIPAL,
            UserRole.SCHOOL_ADMIN,
            UserRole.TEACHER
        ]))
    ):
        """Mark all students in a class as present"""
        tenant_id = current_user.get("tenant_id") or current_user.get("primary_tenant_id")
        
        if not tenant_id:
            raise HTTPException(status_code=400, detail="يجب تحديد المدرسة")

        # Task #428: teachers must own the target section/class before bulk-writing
        # attendance. Same-school membership alone is not sufficient.
        # Additionally all submitted student_ids must belong to that section so a
        # teacher cannot use their own valid class_id but inject foreign student_ids.
        _teacher_write_roles = {UserRole.TEACHER.value}
        if current_user.get("role") in _teacher_write_roles:
            from utils.tenant_scope import can_view_class
            if not await can_view_class(db.session, current_user, data.section_id):
                raise HTTPException(status_code=403, detail="لا يمكنك تسجيل الحضور لهذا الفصل")
            if data.student_ids:
                # Fetch students that are enrolled in this section within this tenant.
                _enrolled = await gd_find(
                    db.session, "students",
                    {"class_id": data.section_id, "school_id": tenant_id},
                    limit=5000,
                )
                _enrolled_ids = {s["id"] for s in _enrolled if s.get("id")}
                _foreign_ids = [sid for sid in data.student_ids if sid not in _enrolled_ids]
                if _foreign_ids:
                    raise HTTPException(status_code=403, detail="بعض الطلاب غير مسجلين في هذا الفصل")

        results = await engine.mark_class_present(
            tenant_id=tenant_id,
            section_id=data.section_id,
            attendance_date=data.attendance_date,
            recorded_by=current_user["id"],
            student_ids=data.student_ids
        )
        
        await audit_engine.log(
            action=AuditAction.ATTENDANCE_BULK_RECORDED.value,
            performed_by=current_user["id"],
            tenant_id=tenant_id,
            entity_type="attendance",
            entity_id=data.section_id,
            details={
                "section_id": data.section_id,
                "date": data.attendance_date,
                "new_status": "present",
                "student_count": len(data.student_ids),
                "processed": results.get("processed", 0),
                "created": results.get("created", 0),
                "updated": results.get("updated", 0),
                "transitions": results.get("transitions", []),
            },
            actor_name=current_user.get("full_name"),
            actor_role=current_user.get("role"),
            actor_email=current_user.get("email"),
        )
        
        return {
            "message": f"تم تسجيل حضور {results['processed']} طالب",
            "results": results
        }
    
    # ============== RETRIEVAL ==============
    
    @router.get("/student/{student_id}", response_model=List[AttendanceResponse])
    async def get_student_attendance(
        student_id: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        status: Optional[str] = None,
        current_user: dict = Depends(get_current_user)
    ):
        """Get attendance records for a student.

        SECURITY (audit H-1): same-tenant alone is not enough. The caller must
        be the student themselves, a guardian of the student, a teacher
        assigned to the student's class, or an admin role within the tenant.
        """
        tenant_id = current_user.get("tenant_id") or current_user.get("primary_tenant_id")

        if not tenant_id:
            raise HTTPException(status_code=400, detail="يجب تحديد المدرسة")

        from utils.tenant_scope import can_view_student, require_can_view_student_sync_check
        allowed = await can_view_student(db.session, current_user, student_id, permission_type="attendance")
        require_can_view_student_sync_check(allowed)

        records = await engine.get_student_attendance(
            tenant_id=tenant_id,
            student_id=student_id,
            start_date=start_date,
            end_date=end_date,
            status=status
        )

        return records
    
    @router.get("/section/{section_id}")
    async def get_section_attendance(
        section_id: str,
        attendance_date: str,
        current_user: dict = Depends(require_roles([
            UserRole.PLATFORM_ADMIN,
            UserRole.SCHOOL_PRINCIPAL,
            UserRole.SCHOOL_ADMIN,
            UserRole.SCHOOL_SUB_ADMIN,
            UserRole.TEACHER,
            UserRole.INDEPENDENT_TEACHER,
        ]))
    ):
        """Get attendance for a section on a specific date.

        SECURITY: Restricted to staff roles only. Section-level attendance
        records contain data for every student in the class and must not be
        accessible to parents, students, or other low-privilege accounts.
        Teachers must additionally be assigned to the requested section/class.
        """
        tenant_id = current_user.get("tenant_id") or current_user.get("primary_tenant_id")
        
        if not tenant_id:
            raise HTTPException(status_code=400, detail="يجب تحديد المدرسة")

        from utils.tenant_scope import can_view_class, require_can_view_class_sync_check
        cls_allowed = await can_view_class(db.session, current_user, section_id)
        require_can_view_class_sync_check(cls_allowed)

        records = await engine.get_section_attendance(
            tenant_id=tenant_id,
            section_id=section_id,
            attendance_date=attendance_date
        )
        
        return {"section_id": section_id, "date": attendance_date, "records": records}
    
    # ============== REPORTS ==============
    
    @router.get("/reports/daily")
    async def get_daily_report(
        attendance_date: str,
        section_id: Optional[str] = None,
        current_user: dict = Depends(require_roles([
            UserRole.PLATFORM_ADMIN,
            UserRole.SCHOOL_PRINCIPAL,
            UserRole.SCHOOL_ADMIN,
            UserRole.SCHOOL_SUB_ADMIN,
            UserRole.TEACHER,
            UserRole.INDEPENDENT_TEACHER,
        ]))
    ):
        """Get daily attendance report.

        SECURITY: Restricted to staff roles only. Daily reports expose
        aggregate class-level records that must not be accessible to
        parents or students. Teachers are further restricted: they must
        supply a specific section_id and be assigned to that section.
        School-wide daily reports (no section_id) are admin-only.
        """
        tenant_id = current_user.get("tenant_id") or current_user.get("primary_tenant_id")
        
        if not tenant_id:
            raise HTTPException(status_code=400, detail="يجب تحديد المدرسة")

        role = current_user.get("role", "")
        _TEACHER_ROLES = {UserRole.TEACHER.value, UserRole.INDEPENDENT_TEACHER.value}
        if role in _TEACHER_ROLES:
            if not section_id:
                raise HTTPException(
                    status_code=403,
                    detail="يجب تحديد الفصل الدراسي للوصول إلى تقرير الحضور اليومي"
                )
            from utils.tenant_scope import can_view_class, require_can_view_class_sync_check
            cls_allowed = await can_view_class(db.session, current_user, section_id)
            require_can_view_class_sync_check(cls_allowed)

        report = await engine.get_daily_attendance_report(
            tenant_id=tenant_id,
            attendance_date=attendance_date,
            section_id=section_id
        )
        
        return report
    
    @router.get("/summary/student/{student_id}", response_model=AttendanceSummary)
    async def get_student_summary(
        student_id: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        current_user: dict = Depends(get_current_user)
    ):
        """Get attendance summary for a student"""
        tenant_id = current_user.get("tenant_id") or current_user.get("primary_tenant_id")
        
        if not tenant_id:
            raise HTTPException(status_code=400, detail="يجب تحديد المدرسة")

        from utils.tenant_scope import can_view_student, require_can_view_student_sync_check
        allowed = await can_view_student(db.session, current_user, student_id, permission_type="attendance")
        require_can_view_student_sync_check(allowed)

        summary = await engine.get_student_attendance_summary(
            tenant_id=tenant_id,
            student_id=student_id,
            start_date=start_date,
            end_date=end_date
        )
        
        return summary
    
    @router.get("/summary/section/{section_id}")
    async def get_section_summary(
        section_id: str,
        start_date: str,
        end_date: str,
        current_user: dict = Depends(require_roles([
            UserRole.PLATFORM_ADMIN,
            UserRole.SCHOOL_PRINCIPAL,
            UserRole.SCHOOL_ADMIN,
            UserRole.SCHOOL_SUB_ADMIN,
            UserRole.TEACHER,
            UserRole.INDEPENDENT_TEACHER,
        ]))
    ):
        """Get attendance summary for a section.

        SECURITY: Restricted to staff roles only. Section-level summaries
        expose per-student attendance statistics for the whole class and
        must not be accessible to parents or students. Teachers must
        additionally be assigned to the requested section/class.
        """
        tenant_id = current_user.get("tenant_id") or current_user.get("primary_tenant_id")
        
        if not tenant_id:
            raise HTTPException(status_code=400, detail="يجب تحديد المدرسة")

        from utils.tenant_scope import can_view_class, require_can_view_class_sync_check
        cls_allowed = await can_view_class(db.session, current_user, section_id)
        require_can_view_class_sync_check(cls_allowed)

        summary = await engine.get_section_attendance_summary(
            tenant_id=tenant_id,
            section_id=section_id,
            start_date=start_date,
            end_date=end_date
        )
        
        return summary
    
    @router.get("/overview")
    async def get_tenant_overview(
        attendance_date: str,
        current_user: dict = Depends(require_roles([
            UserRole.PLATFORM_ADMIN,
            UserRole.SCHOOL_PRINCIPAL
        ]))
    ):
        """Get attendance overview for entire school"""
        tenant_id = current_user.get("tenant_id") or current_user.get("primary_tenant_id")
        
        if not tenant_id:
            raise HTTPException(status_code=400, detail="يجب تحديد المدرسة")
        
        overview = await engine.get_tenant_attendance_overview(
            tenant_id=tenant_id,
            attendance_date=attendance_date
        )
        
        return overview
    
    # ============== EXCUSES ==============
    
    @router.post("/excuses")
    async def create_excuse(
        data: ExcuseCreate,
        current_user: dict = Depends(get_current_user)
    ):
        """Create an attendance excuse.

        SECURITY: The caller must be authorized to act on the target student
        (admin, assigned teacher, or the student's guardian). Any authenticated
        tenant user could otherwise file fraudulent excuses for unrelated
        students.
        """
        tenant_id = current_user.get("tenant_id") or current_user.get("primary_tenant_id")
        
        if not tenant_id:
            raise HTTPException(status_code=400, detail="يجب تحديد المدرسة")

        from utils.tenant_scope import can_view_student, require_can_view_student_sync_check
        allowed = await can_view_student(db.session, current_user, data.student_id, permission_type="attendance")
        require_can_view_student_sync_check(allowed)

        excuse = await engine.create_excuse(
            tenant_id=tenant_id,
            student_id=data.student_id,
            excuse_type=data.excuse_type,
            start_date=data.start_date,
            end_date=data.end_date,
            reason=data.reason,
            created_by=current_user["id"],
            attachment_url=data.attachment_url
        )
        
        return {"message": "تم إنشاء العذر بنجاح", "excuse": excuse}
    
    @router.post("/excuses/{excuse_id}/approve")
    async def approve_excuse(
        excuse_id: str,
        apply_to_attendance: bool = True,
        current_user: dict = Depends(require_roles([
            UserRole.PLATFORM_ADMIN,
            UserRole.SCHOOL_PRINCIPAL
        ]))
    ):
        """Approve an attendance excuse"""
        try:
            excuse = await engine.approve_excuse(
                excuse_id=excuse_id,
                approved_by=current_user["id"],
                apply_to_attendance=apply_to_attendance
            )
            return {"message": "تم قبول العذر", "excuse": excuse}
        except ValueError as e:
            raise HTTPException(status_code=404, detail="العنصر المطلوب غير موجود")
    
    @router.get("/excuses/student/{student_id}")
    async def get_student_excuses(
        student_id: str,
        pending_only: bool = False,
        current_user: dict = Depends(get_current_user)
    ):
        """Get excuses for a student"""
        tenant_id = current_user.get("tenant_id") or current_user.get("primary_tenant_id")
        
        if not tenant_id:
            raise HTTPException(status_code=400, detail="يجب تحديد المدرسة")

        from utils.tenant_scope import can_view_student, require_can_view_student_sync_check
        allowed = await can_view_student(db.session, current_user, student_id, permission_type="attendance")
        require_can_view_student_sync_check(allowed)

        excuses = await engine.get_student_excuses(
            tenant_id=tenant_id,
            student_id=student_id,
            pending_only=pending_only
        )
        
        return {"excuses": excuses, "total": len(excuses)}
    
    # ============== ALERTS ==============
    
    @router.get("/alerts/low-attendance")
    async def get_low_attendance_students(
        threshold: float = 85.0,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        current_user: dict = Depends(require_roles([
            UserRole.PLATFORM_ADMIN,
            UserRole.SCHOOL_PRINCIPAL,
            UserRole.TEACHER
        ]))
    ):
        """Get students with attendance below threshold.

        SECURITY: Teachers may only see alerts for students in their own
        assigned classes. School-wide alerts are restricted to admin roles.
        """
        tenant_id = current_user.get("tenant_id") or current_user.get("primary_tenant_id")

        if not tenant_id:
            raise HTTPException(status_code=400, detail="يجب تحديد المدرسة")

        section_ids_filter = None
        if current_user.get("role") == UserRole.TEACHER.value:
            teacher_id = current_user.get("teacher_id") or current_user.get("id")
            ta_rows = await gd_find(db.session, "teacher_assignments",
                                    {"teacher_id": teacher_id}, limit=500)
            cs_rows = await gd_find(db.session, "class_sessions",
                                    {"teacher_id": teacher_id}, limit=500)
            section_ids_filter = list({r["class_id"] for r in ta_rows + cs_rows if r.get("class_id")})
            if not section_ids_filter:
                return {"threshold": threshold, "students": [], "total": 0}

        students = await engine.get_students_with_low_attendance(
            tenant_id=tenant_id,
            threshold=threshold,
            start_date=start_date,
            end_date=end_date,
            section_ids=section_ids_filter,
        )

        return {
            "threshold": threshold,
            "students": students,
            "total": len(students)
        }

    @router.get("/alerts/consecutive-absences")
    async def get_consecutive_absences(
        min_days: int = 3,
        current_user: dict = Depends(require_roles([
            UserRole.PLATFORM_ADMIN,
            UserRole.SCHOOL_PRINCIPAL,
            UserRole.TEACHER
        ]))
    ):
        """Get students with consecutive absences.

        SECURITY: Teachers may only see alerts for students in their own
        assigned classes. School-wide alerts are restricted to admin roles.
        """
        tenant_id = current_user.get("tenant_id") or current_user.get("primary_tenant_id")

        if not tenant_id:
            raise HTTPException(status_code=400, detail="يجب تحديد المدرسة")

        section_ids_filter = None
        if current_user.get("role") == UserRole.TEACHER.value:
            teacher_id = current_user.get("teacher_id") or current_user.get("id")
            ta_rows = await gd_find(db.session, "teacher_assignments",
                                    {"teacher_id": teacher_id}, limit=500)
            cs_rows = await gd_find(db.session, "class_sessions",
                                    {"teacher_id": teacher_id}, limit=500)
            section_ids_filter = list({r["class_id"] for r in ta_rows + cs_rows if r.get("class_id")})
            if not section_ids_filter:
                return {"min_days": min_days, "alerts": [], "total": 0}

        alerts = await engine.get_consecutive_absences(
            tenant_id=tenant_id,
            min_days=min_days,
            section_ids=section_ids_filter,
        )

        return {
            "min_days": min_days,
            "alerts": alerts,
            "total": len(alerts)
        }
    
    # ============== TEACHER ATTENDANCE ==============
    
    @router.get("/teacher-attendance")
    async def get_teacher_attendance(
        date: str = Query(None),
        current_user: dict = Depends(require_roles([
            UserRole.PLATFORM_ADMIN,
            UserRole.SCHOOL_PRINCIPAL,
            UserRole.SCHOOL_SUB_ADMIN
        ]))
    ):
        """Get teacher attendance records for a specific date"""
        import uuid
        from datetime import datetime, timezone
        
        tenant_id = current_user.get("tenant_id") or current_user.get("primary_tenant_id")
        
        if not tenant_id:
            raise HTTPException(status_code=400, detail="يجب تحديد المدرسة")
        
        query = {"school_id": tenant_id}
        if date:
            query["date"] = date
        
        records = await gd_find(db.session, "teacher_attendance", query, limit=1000)
        return records
    
    @router.post("/teacher-attendance/bulk")
    async def record_teacher_attendance_bulk(
        data: dict,
        current_user: dict = Depends(require_roles([
            UserRole.PLATFORM_ADMIN,
            UserRole.SCHOOL_PRINCIPAL,
            UserRole.SCHOOL_SUB_ADMIN
        ]))
    ):
        """Record attendance for multiple teachers"""
        import uuid
        from datetime import datetime, timezone
        
        tenant_id = current_user.get("tenant_id") or current_user.get("primary_tenant_id")
        
        if not tenant_id:
            raise HTTPException(status_code=400, detail="يجب تحديد المدرسة")
        
        records = data.get("records", [])
        if not records:
            raise HTTPException(status_code=400, detail="لا يوجد سجلات للحفظ")
        
        saved = []
        for record in records:
            # Check if record exists for this teacher on this date
            existing = await gd_find_one(db.session, "teacher_attendance", {
                "school_id": tenant_id,
                "teacher_id": record["teacher_id"],
                "date": record["date"]
            })
            
            attendance_data = {
                "id": existing.get("id") if existing else str(uuid.uuid4()),
                "school_id": tenant_id,
                "teacher_id": record["teacher_id"],
                "date": record["date"],
                "status": record["status"],
                "check_in_time": record.get("check_in_time"),
                "notes": record.get("notes"),
                "recorded_by": current_user.get("id"),
                "updated_at": datetime.now(timezone.utc).isoformat()
            }
            
            if existing:
                await gd_update_one(db.session, "teacher_attendance", {"id": existing["id"]}, attendance_data)
            else:
                attendance_data["created_at"] = datetime.now(timezone.utc).isoformat()
                await gd_insert(db.session, "teacher_attendance", attendance_data)
            
            saved.append(attendance_data)
        
        await audit_engine.log(
            action=AuditAction.ATTENDANCE_BULK_RECORDED.value,
            performed_by=current_user.get("id"),
            tenant_id=tenant_id,
            entity_type="teacher_attendance",
            entity_id=tenant_id,
            details={
                "date": records[0].get("date") if records else None,
                "teacher_count": len(records),
                "saved_count": len(saved),
            },
            actor_name=current_user.get("full_name"),
            actor_role=current_user.get("role"),
            actor_email=current_user.get("email"),
        )
        
        return {"message": "تم حفظ الحضور بنجاح", "count": len(saved)}
    
    @router.get("/teacher-attendance/report/summary")
    async def get_teacher_attendance_summary(
        current_user: dict = Depends(require_roles([
            UserRole.PLATFORM_ADMIN,
            UserRole.SCHOOL_PRINCIPAL,
            UserRole.SCHOOL_SUB_ADMIN
        ]))
    ):
        """Get teacher attendance summary report"""
        tenant_id = current_user.get("tenant_id") or current_user.get("primary_tenant_id")
        
        if not tenant_id:
            raise HTTPException(status_code=400, detail="يجب تحديد المدرسة")
        
        # Get all records for this school
        records = await gd_find(db.session, "teacher_attendance", {"school_id": tenant_id}, limit=10000)
        
        # Calculate summary
        present = len([r for r in records if r.get("status") == "present"])
        absent = len([r for r in records if r.get("status") == "absent"])
        late = len([r for r in records if r.get("status") == "late"])
        excused = len([r for r in records if r.get("status") == "excused"])
        total = present + absent + late + excused
        
        attendance_rate = round((present + late) / total * 100, 1) if total > 0 else 0
        
        return {
            "overall": {
                "attendance_rate": attendance_rate,
                "total_records": total,
                "present": present,
                "absent": absent,
                "late": late,
                "excused": excused
            },
            "daily": []
        }
    
    return router


# Export
__all__ = ["create_attendance_router"]
