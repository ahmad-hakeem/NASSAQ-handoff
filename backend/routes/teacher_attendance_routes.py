"""
NASSAQ - Teacher Attendance Routes
Teacher attendance management endpoints (for Principal use)
"""
from fastapi import APIRouter, HTTPException, Depends
from typing import Optional, List
from datetime import datetime, timezone
from pydantic import BaseModel
import uuid
from engines.sql_utils import gd_find, gd_find_one, gd_insert, gd_insert_many, gd_update_one, gd_update_many, gd_count, gd_delete_one, gd_delete_many, gd_distinct

import logging

logger = logging.getLogger("nassaq.teacher_attendance_routes")


class TeacherAttendanceRecord(BaseModel):
    teacher_id: str
    date: str
    status: str  # present, absent, late, excused
    check_in_time: Optional[str] = None
    notes: Optional[str] = None


class BulkTeacherAttendance(BaseModel):
    records: List[TeacherAttendanceRecord]


def create_teacher_attendance_routes(db, get_current_user, require_roles, UserRole):
    """Create teacher attendance router"""
    router = APIRouter(prefix="/teacher-attendance", tags=["Teacher Attendance"])
    
    @router.get("")
    async def get_teacher_attendance(
        date: str,
        current_user: dict = Depends(get_current_user)
    ):
        """Get teacher attendance for a specific date"""
        # Get school_id from user's tenant
        school_id = current_user.get("tenant_id")
        if not school_id and current_user["role"] != "platform_admin":
            raise HTTPException(status_code=403, detail="No school association")
        
        query = {"date": date}
        if school_id:
            query["school_id"] = school_id
        
        records = await gd_find(db.session, "teacher_attendance", query, limit=1000)
        return records
    
    @router.post("/bulk")
    async def save_bulk_teacher_attendance(
        data: BulkTeacherAttendance,
        current_user: dict = Depends(require_roles([UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN]))
    ):
        """Save bulk teacher attendance records"""
        school_id = current_user.get("tenant_id")
        if not school_id and current_user["role"] != "platform_admin":
            raise HTTPException(status_code=403, detail="No school association")
        
        saved_count = 0
        updated_count = 0
        
        for record in data.records:
            # Check if record already exists
            existing = await gd_find_one(db.session, "teacher_attendance", {
                "teacher_id": record.teacher_id,
                "date": record.date,
                "school_id": school_id
            })
            
            attendance_doc = {
                "teacher_id": record.teacher_id,
                "date": record.date,
                "status": record.status,
                "check_in_time": record.check_in_time,
                "notes": record.notes,
                "school_id": school_id,
                "recorded_by": current_user["id"],
                "updated_at": datetime.now(timezone.utc).isoformat()
            }
            
            if existing:
                await gd_update_one(db.session, "teacher_attendance", {"_id": existing["_id"]}, attendance_doc)
                updated_count += 1
            else:
                attendance_doc["id"] = str(uuid.uuid4())
                attendance_doc["created_at"] = datetime.now(timezone.utc).isoformat()
                await gd_insert(db.session, "teacher_attendance", attendance_doc)
                saved_count += 1
        
        return {
            "message": "تم حفظ الحضور بنجاح",
            "saved": saved_count,
            "updated": updated_count
        }
    
    @router.get("/report/summary")
    async def get_teacher_attendance_summary(
        current_user: dict = Depends(get_current_user)
    ):
        """Get teacher attendance summary report"""
        school_id = current_user.get("tenant_id")
        if not school_id and current_user["role"] != "platform_admin":
            raise HTTPException(status_code=403, detail="No school association")
        
        query = {}
        if school_id:
            query["school_id"] = school_id
        
        # Get all records for this school
        all_records = await gd_find(db.session, "teacher_attendance", query, limit=10000)
        
        # Calculate stats
        present = sum(1 for r in all_records if r.get("status") == "present")
        absent = sum(1 for r in all_records if r.get("status") == "absent")
        late = sum(1 for r in all_records if r.get("status") == "late")
        excused = sum(1 for r in all_records if r.get("status") == "excused")
        total = len(all_records)
        
        attendance_rate = 0
        if total > 0:
            attendance_rate = round((present + late) / total * 100, 1)
        
        # Group by date for daily trend
        daily_stats = {}
        for record in all_records:
            date = record.get("date", "unknown")
            if date not in daily_stats:
                daily_stats[date] = {"present": 0, "absent": 0, "late": 0, "excused": 0, "total": 0}
            daily_stats[date][record.get("status", "present")] += 1
            daily_stats[date]["total"] += 1
        
        daily = []
        for date, stats in sorted(daily_stats.items(), reverse=True)[:30]:
            rate = 0
            if stats["total"] > 0:
                rate = round((stats["present"] + stats["late"]) / stats["total"] * 100, 1)
            daily.append({
                "date": date,
                "present": stats["present"],
                "absent": stats["absent"],
                "late": stats["late"],
                "excused": stats["excused"],
                "total": stats["total"],
                "attendance_rate": rate
            })
        
        return {
            "overall": {
                "attendance_rate": attendance_rate,
                "total_records": total,
                "present": present,
                "absent": absent,
                "late": late,
                "excused": excused
            },
            "daily": daily
        }
    
    @router.get("/teacher/{teacher_id}")
    async def get_teacher_attendance_history(
        teacher_id: str,
        current_user: dict = Depends(get_current_user)
    ):
        """Get attendance history for a specific teacher"""
        school_id = current_user.get("tenant_id")
        
        query = {"teacher_id": teacher_id}
        if school_id:
            query["school_id"] = school_id
        
        records = await gd_find(db.session, "teacher_attendance", query, order_by="date", desc_order=True, limit=100)
        
        # Calculate stats
        present = sum(1 for r in records if r.get("status") == "present")
        absent = sum(1 for r in records if r.get("status") == "absent")
        late = sum(1 for r in records if r.get("status") == "late")
        total = len(records)
        
        attendance_rate = 0
        if total > 0:
            attendance_rate = round((present + late) / total * 100, 1)
        
        return {
            "teacher_id": teacher_id,
            "total_days": total,
            "present": present,
            "absent": absent,
            "late": late,
            "attendance_rate": attendance_rate,
            "records": records[:30]  # Last 30 records
        }
    
    return router
