"""
NASSAQ Attendance Engine
محرك الحضور والغياب لمنصة نَسَّق

Handles:
- Student attendance recording
- Bulk attendance operations
- Attendance reports and statistics
- Excuse management
- Late arrivals and early departures
"""

from typing import Optional, List, Dict, Any
from datetime import datetime, timezone, date, timedelta
from enum import Enum
import uuid


class AttendanceStatus(str, Enum):
    PRESENT = "present"
    ABSENT = "absent"
    LATE = "late"
    EXCUSED = "excused"
    LEFT_EARLY = "left_early"
    PENDING_VERIFICATION = "pending_verification"


class ExcuseType(str, Enum):
    MEDICAL = "medical"
    FAMILY = "family"
    OFFICIAL = "official"
    OTHER = "other"


class AttendanceEngine:
    """
    Core Attendance Engine for NASSAQ
    Manages student attendance tracking and reporting
    """
    
    def __init__(self, db):
        self.db = db
        self.attendance_collection = db.attendance
        self.excuses_collection = db.attendance_excuses
        self.attendance_settings_collection = db.attendance_settings
        self.audit_collection = db.audit_logs
    
    # ============== ATTENDANCE RECORDING ==============
    
    async def record_attendance(
        self,
        tenant_id: str,
        student_id: str,
        section_id: str,
        attendance_date: str,
        status: str,
        recorded_by: str,
        **kwargs
    ) -> Dict[str, Any]:
        """Record attendance for a single student"""
        now = datetime.now(timezone.utc).isoformat()
        
        # Check if attendance already exists for this student/date
        existing = await self.attendance_collection.find_one({
            "tenant_id": tenant_id,
            "student_id": student_id,
            "attendance_date": attendance_date
        })
        
        if existing:
            # Update existing record
            updates = {
                "status": status,
                "updated_at": now,
                "updated_by": recorded_by
            }
            
            if kwargs.get("arrival_time"):
                updates["arrival_time"] = kwargs["arrival_time"]
            if kwargs.get("departure_time"):
                updates["departure_time"] = kwargs["departure_time"]
            if kwargs.get("notes"):
                updates["notes"] = kwargs["notes"]
            
            await self.attendance_collection.update_one(
                {"id": existing["id"]},
                {"$set": updates}
            )
            
            existing.update(updates)
            existing.pop("_id", None)
            return existing
        
        # Create new record
        attendance_id = str(uuid.uuid4())
        
        attendance_doc = {
            "id": attendance_id,
            "tenant_id": tenant_id,
            "student_id": student_id,
            "section_id": section_id,
            "attendance_date": attendance_date,
            "status": status,
            "arrival_time": kwargs.get("arrival_time"),
            "departure_time": kwargs.get("departure_time"),
            "notes": kwargs.get("notes"),
            "recorded_at": now,
            "recorded_by": recorded_by,
            "session_id": kwargs.get("session_id"),  # For per-session attendance
            "period": kwargs.get("period")
        }
        
        await self.attendance_collection.insert_one(attendance_doc)
        
        return attendance_doc
    
    async def record_bulk_attendance(
        self,
        tenant_id: str,
        section_id: str,
        attendance_date: str,
        attendance_records: List[Dict[str, Any]],
        recorded_by: str
    ) -> Dict[str, Any]:
        """Record attendance for multiple students at once"""
        results = {
            "processed": 0,
            "created": 0,
            "updated": 0,
            "errors": []
        }
        
        for record in attendance_records:
            try:
                student_id = record.get("student_id")
                status = record.get("status", AttendanceStatus.PRESENT.value)
                
                if not student_id:
                    results["errors"].append({"error": "معرف الطالب مفقود"})
                    continue
                
                await self.record_attendance(
                    tenant_id=tenant_id,
                    student_id=student_id,
                    section_id=section_id,
                    attendance_date=attendance_date,
                    status=status,
                    recorded_by=recorded_by,
                    arrival_time=record.get("arrival_time"),
                    departure_time=record.get("departure_time"),
                    notes=record.get("notes"),
                    session_id=record.get("session_id"),
                    period=record.get("period")
                )
                
                results["processed"] += 1
                
            except Exception as e:
                results["errors"].append({
                    "student_id": record.get("student_id"),
                    "error": str(e)
                })
        
        return results
    
    async def mark_class_present(
        self,
        tenant_id: str,
        section_id: str,
        attendance_date: str,
        recorded_by: str,
        student_ids: List[str]
    ) -> Dict[str, Any]:
        """Mark all students in a class as present"""
        records = [
            {"student_id": sid, "status": AttendanceStatus.PRESENT.value}
            for sid in student_ids
        ]
        
        return await self.record_bulk_attendance(
            tenant_id=tenant_id,
            section_id=section_id,
            attendance_date=attendance_date,
            attendance_records=records,
            recorded_by=recorded_by
        )
    
    # ============== ATTENDANCE RETRIEVAL ==============
    
    async def get_student_attendance(
        self,
        tenant_id: str,
        student_id: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get attendance records for a student"""
        query = {
            "tenant_id": tenant_id,
            "student_id": student_id
        }
        
        if start_date:
            query["attendance_date"] = {"$gte": start_date}
        if end_date:
            if "attendance_date" in query:
                query["attendance_date"]["$lte"] = end_date
            else:
                query["attendance_date"] = {"$lte": end_date}
        if status:
            query["status"] = status
        
        records = await self.attendance_collection.find(
            query,
            {"_id": 0}
        ).sort("attendance_date", -1).to_list(1000)
        
        return records
    
    async def get_section_attendance(
        self,
        tenant_id: str,
        section_id: str,
        attendance_date: str
    ) -> List[Dict[str, Any]]:
        """Get attendance for a section on a specific date"""
        records = await self.attendance_collection.find(
            {
                "tenant_id": tenant_id,
                "section_id": section_id,
                "attendance_date": attendance_date
            },
            {"_id": 0}
        ).to_list(1000)
        
        return records
    
    async def get_daily_attendance_report(
        self,
        tenant_id: str,
        attendance_date: str,
        section_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get daily attendance report"""
        query = {
            "tenant_id": tenant_id,
            "attendance_date": attendance_date
        }
        
        if section_id:
            query["section_id"] = section_id
        
        records = await self.attendance_collection.find(
            query,
            {"_id": 0}
        ).to_list(10000)
        
        # Calculate statistics
        total = len(records)
        present = len([r for r in records if r.get("status") == AttendanceStatus.PRESENT.value])
        absent = len([r for r in records if r.get("status") == AttendanceStatus.ABSENT.value])
        late = len([r for r in records if r.get("status") == AttendanceStatus.LATE.value])
        excused = len([r for r in records if r.get("status") == AttendanceStatus.EXCUSED.value])
        left_early = len([r for r in records if r.get("status") == AttendanceStatus.LEFT_EARLY.value])
        
        return {
            "date": attendance_date,
            "tenant_id": tenant_id,
            "section_id": section_id,
            "total_students": total,
            "present": present,
            "absent": absent,
            "late": late,
            "excused": excused,
            "left_early": left_early,
            "attendance_rate": round((present / total * 100) if total > 0 else 0, 2),
            "records": records
        }
    
    # ============== ATTENDANCE STATISTICS ==============
    
    async def get_student_attendance_summary(
        self,
        tenant_id: str,
        student_id: str,
        academic_year: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get attendance summary for a student"""
        query = {
            "tenant_id": tenant_id,
            "student_id": student_id
        }
        
        if start_date:
            query["attendance_date"] = {"$gte": start_date}
        if end_date:
            if "attendance_date" in query:
                query["attendance_date"]["$lte"] = end_date
            else:
                query["attendance_date"] = {"$lte": end_date}
        
        records = await self.attendance_collection.find(
            query,
            {"_id": 0}
        ).to_list(10000)
        
        total = len(records)
        present = len([r for r in records if r.get("status") == AttendanceStatus.PRESENT.value])
        absent = len([r for r in records if r.get("status") == AttendanceStatus.ABSENT.value])
        late = len([r for r in records if r.get("status") == AttendanceStatus.LATE.value])
        excused = len([r for r in records if r.get("status") == AttendanceStatus.EXCUSED.value])
        left_early = len([r for r in records if r.get("status") == AttendanceStatus.LEFT_EARLY.value])
        
        return {
            "student_id": student_id,
            "total_days": total,
            "present_days": present,
            "absent_days": absent,
            "late_days": late,
            "excused_days": excused,
            "left_early_days": left_early,
            "attendance_rate": round((present / total * 100) if total > 0 else 100, 2),
            "absence_rate": round((absent / total * 100) if total > 0 else 0, 2),
            "late_rate": round((late / total * 100) if total > 0 else 0, 2)
        }
    
    async def get_section_attendance_summary(
        self,
        tenant_id: str,
        section_id: str,
        start_date: str,
        end_date: str
    ) -> Dict[str, Any]:
        """Get attendance summary for a section over a period"""
        query = {
            "tenant_id": tenant_id,
            "section_id": section_id,
            "attendance_date": {"$gte": start_date, "$lte": end_date}
        }
        
        records = await self.attendance_collection.find(
            query,
            {"_id": 0}
        ).to_list(100000)
        
        # Group by student
        student_stats = {}
        for record in records:
            sid = record.get("student_id")
            if sid not in student_stats:
                student_stats[sid] = {
                    "student_id": sid,
                    "total": 0,
                    "present": 0,
                    "absent": 0,
                    "late": 0,
                    "excused": 0
                }
            
            student_stats[sid]["total"] += 1
            status = record.get("status")
            if status == AttendanceStatus.PRESENT.value:
                student_stats[sid]["present"] += 1
            elif status == AttendanceStatus.ABSENT.value:
                student_stats[sid]["absent"] += 1
            elif status == AttendanceStatus.LATE.value:
                student_stats[sid]["late"] += 1
            elif status == AttendanceStatus.EXCUSED.value:
                student_stats[sid]["excused"] += 1
        
        # Calculate rates
        for sid in student_stats:
            total = student_stats[sid]["total"]
            present = student_stats[sid]["present"]
            student_stats[sid]["attendance_rate"] = round((present / total * 100) if total > 0 else 100, 2)
        
        # Overall section stats
        total_records = len(records)
        total_present = len([r for r in records if r.get("status") == AttendanceStatus.PRESENT.value])
        
        return {
            "section_id": section_id,
            "start_date": start_date,
            "end_date": end_date,
            "total_records": total_records,
            "overall_attendance_rate": round((total_present / total_records * 100) if total_records > 0 else 0, 2),
            "students": list(student_stats.values())
        }
    
    async def get_tenant_attendance_overview(
        self,
        tenant_id: str,
        attendance_date: str
    ) -> Dict[str, Any]:
        """Get attendance overview for entire tenant"""
        records = await self.attendance_collection.find(
            {
                "tenant_id": tenant_id,
                "attendance_date": attendance_date
            },
            {"_id": 0}
        ).to_list(100000)
        
        total = len(records)
        present = len([r for r in records if r.get("status") == AttendanceStatus.PRESENT.value])
        absent = len([r for r in records if r.get("status") == AttendanceStatus.ABSENT.value])
        late = len([r for r in records if r.get("status") == AttendanceStatus.LATE.value])
        
        # Group by section
        sections = {}
        for record in records:
            sid = record.get("section_id")
            if sid not in sections:
                sections[sid] = {"section_id": sid, "total": 0, "present": 0, "absent": 0}
            sections[sid]["total"] += 1
            if record.get("status") == AttendanceStatus.PRESENT.value:
                sections[sid]["present"] += 1
            elif record.get("status") == AttendanceStatus.ABSENT.value:
                sections[sid]["absent"] += 1
        
        return {
            "tenant_id": tenant_id,
            "date": attendance_date,
            "total_students": total,
            "present": present,
            "absent": absent,
            "late": late,
            "attendance_rate": round((present / total * 100) if total > 0 else 0, 2),
            "sections_count": len(sections),
            "sections": list(sections.values())
        }
    
    # ============== EXCUSE MANAGEMENT ==============
    
    async def create_excuse(
        self,
        tenant_id: str,
        student_id: str,
        excuse_type: str,
        start_date: str,
        end_date: str,
        reason: str,
        created_by: str,
        **kwargs
    ) -> Dict[str, Any]:
        """Create an attendance excuse"""
        excuse_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        
        excuse_doc = {
            "id": excuse_id,
            "tenant_id": tenant_id,
            "student_id": student_id,
            "excuse_type": excuse_type,
            "start_date": start_date,
            "end_date": end_date,
            "reason": reason,
            "attachment_url": kwargs.get("attachment_url"),
            "is_approved": False,
            "created_at": now,
            "created_by": created_by
        }
        
        await self.excuses_collection.insert_one(excuse_doc)
        
        return excuse_doc
    
    async def approve_excuse(
        self,
        excuse_id: str,
        approved_by: str,
        apply_to_attendance: bool = True
    ) -> Dict[str, Any]:
        """Approve an attendance excuse"""
        now = datetime.now(timezone.utc).isoformat()
        
        excuse = await self.excuses_collection.find_one(
            {"id": excuse_id},
            {"_id": 0}
        )
        
        if not excuse:
            raise ValueError("العذر غير موجود")
        
        # Update excuse
        await self.excuses_collection.update_one(
            {"id": excuse_id},
            {
                "$set": {
                    "is_approved": True,
                    "approved_at": now,
                    "approved_by": approved_by
                }
            }
        )
        
        # Update attendance records if requested
        if apply_to_attendance:
            await self.attendance_collection.update_many(
                {
                    "tenant_id": excuse.get("tenant_id"),
                    "student_id": excuse.get("student_id"),
                    "attendance_date": {
                        "$gte": excuse.get("start_date"),
                        "$lte": excuse.get("end_date")
                    },
                    "status": AttendanceStatus.ABSENT.value
                },
                {
                    "$set": {
                        "status": AttendanceStatus.EXCUSED.value,
                        "excuse_id": excuse_id,
                        "updated_at": now,
                        "updated_by": approved_by
                    }
                }
            )
        
        excuse["is_approved"] = True
        excuse["approved_at"] = now
        excuse["approved_by"] = approved_by
        
        return excuse
    
    async def get_student_excuses(
        self,
        tenant_id: str,
        student_id: str,
        pending_only: bool = False
    ) -> List[Dict[str, Any]]:
        """Get excuses for a student"""
        query = {
            "tenant_id": tenant_id,
            "student_id": student_id
        }
        
        if pending_only:
            query["is_approved"] = False
        
        excuses = await self.excuses_collection.find(
            query,
            {"_id": 0}
        ).sort("created_at", -1).to_list(1000)
        
        return excuses
    
    # ============== ATTENDANCE ALERTS ==============
    
    async def get_students_with_low_attendance(
        self,
        tenant_id: str,
        threshold: float = 85.0,
        start_date: str = None,
        end_date: str = None
    ) -> List[Dict[str, Any]]:
        """Get students with attendance rate below threshold"""
        # Get all records for the period
        query = {"tenant_id": tenant_id}
        
        if start_date:
            query["attendance_date"] = {"$gte": start_date}
        if end_date:
            if "attendance_date" in query:
                query["attendance_date"]["$lte"] = end_date
            else:
                query["attendance_date"] = {"$lte": end_date}
        
        records = await self.attendance_collection.find(
            query,
            {"_id": 0}
        ).to_list(100000)
        
        # Group by student
        student_stats = {}
        for record in records:
            sid = record.get("student_id")
            if sid not in student_stats:
                student_stats[sid] = {
                    "student_id": sid,
                    "section_id": record.get("section_id"),
                    "total": 0,
                    "present": 0
                }
            
            student_stats[sid]["total"] += 1
            if record.get("status") == AttendanceStatus.PRESENT.value:
                student_stats[sid]["present"] += 1
        
        # Find students below threshold
        low_attendance = []
        for sid, stats in student_stats.items():
            rate = (stats["present"] / stats["total"] * 100) if stats["total"] > 0 else 100
            if rate < threshold:
                stats["attendance_rate"] = round(rate, 2)
                stats["absent_days"] = stats["total"] - stats["present"]
                low_attendance.append(stats)
        
        # Sort by attendance rate
        low_attendance.sort(key=lambda x: x["attendance_rate"])
        
        return low_attendance
    
    async def get_consecutive_absences(
        self,
        tenant_id: str,
        min_days: int = 3
    ) -> List[Dict[str, Any]]:
        """Get students with consecutive absences"""
        # Get recent attendance (last 30 days)
        end_date = datetime.now(timezone.utc).date()
        start_date = end_date - timedelta(days=30)
        
        records = await self.attendance_collection.find(
            {
                "tenant_id": tenant_id,
                "attendance_date": {
                    "$gte": start_date.isoformat(),
                    "$lte": end_date.isoformat()
                },
                "status": AttendanceStatus.ABSENT.value
            },
            {"_id": 0}
        ).sort([("student_id", 1), ("attendance_date", 1)]).to_list(100000)
        
        # Find consecutive absences
        alerts = []
        current_student = None
        consecutive = 0
        last_date = None
        
        for record in records:
            sid = record.get("student_id")
            record_date = datetime.fromisoformat(record.get("attendance_date")).date()
            
            if sid != current_student:
                # Check if previous student had enough consecutive days
                if consecutive >= min_days:
                    alerts.append({
                        "student_id": current_student,
                        "consecutive_days": consecutive,
                        "last_absence_date": last_date.isoformat() if last_date else None
                    })
                
                current_student = sid
                consecutive = 1
                last_date = record_date
            else:
                # Check if this is consecutive
                if last_date and (record_date - last_date).days <= 2:  # Allow weekends
                    consecutive += 1
                else:
                    consecutive = 1
                last_date = record_date
        
        # Check last student
        if consecutive >= min_days:
            alerts.append({
                "student_id": current_student,
                "consecutive_days": consecutive,
                "last_absence_date": last_date.isoformat() if last_date else None
            })
        
        return alerts


# Export
__all__ = ["AttendanceEngine", "AttendanceStatus", "ExcuseType"]
