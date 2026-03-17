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
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime, date
import logging

logger = logging.getLogger("nassaq.attendance_routes")


# ============== MODELS ==============

class AttendanceRecord(BaseModel):
    student_id: str
    status: str = "present"
    arrival_time: Optional[str] = None
    departure_time: Optional[str] = None
    notes: Optional[str] = None


class AttendanceCreate(BaseModel):
    student_id: str
    section_id: str
    attendance_date: str
    status: str = "present"
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
            UserRole.TEACHER
        ]))
    ):
        """Record attendance for a single student"""
        tenant_id = current_user.get("tenant_id") or current_user.get("primary_tenant_id")
        
        if not tenant_id:
            raise HTTPException(status_code=400, detail="يجب تحديد المدرسة")
        
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
        
        return record
    
    @router.post("/bulk")
    async def record_bulk_attendance(
        data: BulkAttendanceCreate,
        current_user: dict = Depends(require_roles([
            UserRole.PLATFORM_ADMIN,
            UserRole.SCHOOL_PRINCIPAL,
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
            UserRole.TEACHER
        ]))
    ):
        """Mark all students in a class as present"""
        tenant_id = current_user.get("tenant_id") or current_user.get("primary_tenant_id")
        
        if not tenant_id:
            raise HTTPException(status_code=400, detail="يجب تحديد المدرسة")
        
        results = await engine.mark_class_present(
            tenant_id=tenant_id,
            section_id=data.section_id,
            attendance_date=data.attendance_date,
            recorded_by=current_user["id"],
            student_ids=data.student_ids
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
        """Get attendance records for a student"""
        tenant_id = current_user.get("tenant_id") or current_user.get("primary_tenant_id")
        
        if not tenant_id:
            raise HTTPException(status_code=400, detail="يجب تحديد المدرسة")
        
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
        current_user: dict = Depends(get_current_user)
    ):
        """Get attendance for a section on a specific date"""
        tenant_id = current_user.get("tenant_id") or current_user.get("primary_tenant_id")
        
        if not tenant_id:
            raise HTTPException(status_code=400, detail="يجب تحديد المدرسة")
        
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
        current_user: dict = Depends(get_current_user)
    ):
        """Get daily attendance report"""
        tenant_id = current_user.get("tenant_id") or current_user.get("primary_tenant_id")
        
        if not tenant_id:
            raise HTTPException(status_code=400, detail="يجب تحديد المدرسة")
        
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
        current_user: dict = Depends(get_current_user)
    ):
        """Get attendance summary for a section"""
        tenant_id = current_user.get("tenant_id") or current_user.get("primary_tenant_id")
        
        if not tenant_id:
            raise HTTPException(status_code=400, detail="يجب تحديد المدرسة")
        
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
        """Create an attendance excuse"""
        tenant_id = current_user.get("tenant_id") or current_user.get("primary_tenant_id")
        
        if not tenant_id:
            raise HTTPException(status_code=400, detail="يجب تحديد المدرسة")
        
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
        """Get students with attendance below threshold"""
        tenant_id = current_user.get("tenant_id") or current_user.get("primary_tenant_id")
        
        if not tenant_id:
            raise HTTPException(status_code=400, detail="يجب تحديد المدرسة")
        
        students = await engine.get_students_with_low_attendance(
            tenant_id=tenant_id,
            threshold=threshold,
            start_date=start_date,
            end_date=end_date
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
        """Get students with consecutive absences"""
        tenant_id = current_user.get("tenant_id") or current_user.get("primary_tenant_id")
        
        if not tenant_id:
            raise HTTPException(status_code=400, detail="يجب تحديد المدرسة")
        
        alerts = await engine.get_consecutive_absences(
            tenant_id=tenant_id,
            min_days=min_days
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
        
        records = await db.teacher_attendance.find(query, {"_id": 0}).to_list(1000)
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
            existing = await db.teacher_attendance.find_one({
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
                await db.teacher_attendance.update_one(
                    {"id": existing["id"]},
                    {"$set": attendance_data}
                )
            else:
                attendance_data["created_at"] = datetime.now(timezone.utc).isoformat()
                await db.teacher_attendance.insert_one(attendance_data)
            
            saved.append(attendance_data)
        
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
        records = await db.teacher_attendance.find(
            {"school_id": tenant_id}, 
            {"_id": 0}
        ).to_list(10000)
        
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
