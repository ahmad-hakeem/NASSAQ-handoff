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
            old_status = existing.get("status")
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
            existing["old_status"] = old_status
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
        """Record attendance for multiple students using batch operations"""
        results = {
            "processed": 0,
            "created": 0,
            "updated": 0,
            "errors": [],
            "transitions": []
        }
        now = datetime.now(timezone.utc).isoformat()

        valid_records = []
        for record in attendance_records:
            sid = record.get("student_id")
            if not sid:
                results["errors"].append({"error": "معرف الطالب مفقود"})
                continue
            valid_records.append(record)

        if not valid_records:
            return results

        student_ids = [r["student_id"] for r in valid_records]
        existing_rows = await self.attendance_collection.find(
            {
                "tenant_id": tenant_id,
                "section_id": section_id,
                "attendance_date": attendance_date,
                "student_id": {"$in": student_ids},
            },
            {"_id": 0},
        ).to_list(len(student_ids))
        existing_map = {row["student_id"]: row for row in existing_rows}

        to_insert = []
        for record in valid_records:
            try:
                student_id = record["student_id"]
                status = record.get("status", AttendanceStatus.PRESENT.value)
                existing = existing_map.get(student_id)

                if existing:
                    old_status = existing.get("status")
                    updates = {
                        "status": status,
                        "updated_at": now,
                        "updated_by": recorded_by,
                    }
                    if record.get("arrival_time"):
                        updates["arrival_time"] = record["arrival_time"]
                    if record.get("departure_time"):
                        updates["departure_time"] = record["departure_time"]
                    if record.get("notes"):
                        updates["notes"] = record["notes"]

                    await self.attendance_collection.update_one(
                        {"id": existing["id"]}, {"$set": updates}
                    )
                    results["updated"] += 1
                    results["transitions"].append({
                        "student_id": student_id,
                        "old_status": old_status,
                        "new_status": status,
                    })
                else:
                    doc = {
                        "id": str(uuid.uuid4()),
                        "tenant_id": tenant_id,
                        "student_id": student_id,
                        "section_id": section_id,
                        "attendance_date": attendance_date,
                        "status": status,
                        "arrival_time": record.get("arrival_time"),
                        "departure_time": record.get("departure_time"),
                        "notes": record.get("notes"),
                        "recorded_at": now,
                        "recorded_by": recorded_by,
                        "session_id": record.get("session_id"),
                        "period": record.get("period"),
                    }
                    to_insert.append(doc)
                    results["transitions"].append({
                        "student_id": student_id,
                        "old_status": None,
                        "new_status": status,
                    })
                results["processed"] += 1
            except Exception as e:
                results["errors"].append({
                    "student_id": record.get("student_id"),
                    "error": str(e),
                })

        if to_insert:
            await self.attendance_collection.insert_many(to_insert)
            results["created"] = len(to_insert)

        return results
    
    async def create_bulk_class_attendance(
        self,
        tenant_id: str,
        class_id: str,
        date_str: str,
        time_slot_id: str,
        subject_id: Optional[str],
        records: List[Dict[str, Any]],
        recorded_by: str,
    ) -> Dict[str, Any]:
        """Process bulk attendance for a class (route-delegated).

        Returns dict with created, updated, errors, transitions, and
        absent_late list for the route to send notifications.
        """
        now = datetime.now(timezone.utc).isoformat()

        seen: set = set()
        deduped = []
        for r in records:
            sid = r.get("student_id")
            if sid and sid not in seen:
                seen.add(sid)
                deduped.append(r)

        student_ids = list(seen)
        existing_rows = await self.attendance_collection.find(
            {
                "class_id": class_id,
                "date": date_str,
                "time_slot_id": time_slot_id,
                "student_id": {"$in": student_ids},
                "tenant_id": tenant_id,
            },
            {"_id": 0},
        ).to_list(len(student_ids))
        existing_map = {row["student_id"]: row for row in existing_rows}

        created = 0
        updated = 0
        errors: List[Dict] = []
        transitions: List[Dict] = []
        to_insert: List[Dict] = []
        to_insert_events: List[Dict] = []
        absent_late: List[tuple] = []

        for record in deduped:
            try:
                student_id = record.get("student_id")
                att_status = record.get("status", "present")
                notes = record.get("notes")

                existing = existing_map.get(student_id)
                if existing:
                    old_status = existing.get("status")
                    await self.attendance_collection.update_one(
                        {"id": existing["id"]},
                        {"$set": {
                            "status": att_status,
                            "notes": notes,
                            "recorded_by": recorded_by,
                            "recorded_at": now,
                        }},
                    )
                    updated += 1
                    transitions.append({"student_id": student_id, "old_status": old_status, "new_status": att_status})
                else:
                    doc = {
                        "id": str(uuid.uuid4()),
                        "student_id": student_id,
                        "class_id": class_id,
                        "subject_id": subject_id,
                        "teacher_id": recorded_by,
                        "date": date_str,
                        "time_slot_id": time_slot_id,
                        "status": att_status,
                        "notes": notes,
                        "recorded_by": recorded_by,
                        "recorded_at": now,
                        "tenant_id": tenant_id,
                    }
                    to_insert.append(doc)
                    transitions.append({"student_id": student_id, "old_status": None, "new_status": att_status})
                    created += 1

                    if att_status in ("absent", "late"):
                        to_insert_events.append({
                            "id": str(uuid.uuid4()),
                            "type": f"student_{att_status}",
                            "student_id": student_id,
                            "class_id": class_id,
                            "date": date_str,
                            "recorded_by": recorded_by,
                            "created_at": now,
                            "tenant_id": tenant_id,
                        })
                        absent_late.append((student_id, att_status))
            except Exception as e:
                errors.append({"student_id": record.get("student_id"), "error": str(e)})

        if to_insert:
            await self.attendance_collection.insert_many(to_insert)
        if to_insert_events:
            await self.db.events.insert_many(to_insert_events)

        return {
            "created": created,
            "updated": updated,
            "errors": errors,
            "transitions": transitions,
            "absent_late": absent_late,
            "total_records": len(records),
        }

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
        """Get daily attendance report using SQL aggregation for counts"""
        query = {
            "tenant_id": tenant_id,
            "attendance_date": attendance_date
        }
        if section_id:
            query["section_id"] = section_id

        counts = await self.attendance_collection.batched_counts({
            "total": query,
            "present": {**query, "status": AttendanceStatus.PRESENT.value},
            "absent": {**query, "status": AttendanceStatus.ABSENT.value},
            "late": {**query, "status": AttendanceStatus.LATE.value},
            "excused": {**query, "status": AttendanceStatus.EXCUSED.value},
            "left_early": {**query, "status": AttendanceStatus.LEFT_EARLY.value},
        })

        total = counts["total"]
        present = counts["present"]

        records = await self.attendance_collection.find(query, {"_id": 0}).to_list(1000)

        return {
            "date": attendance_date,
            "tenant_id": tenant_id,
            "section_id": section_id,
            "total_students": total,
            "present": present,
            "absent": counts["absent"],
            "late": counts["late"],
            "excused": counts["excused"],
            "left_early": counts["left_early"],
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
        """Get attendance summary for a student using SQL counts"""
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

        counts = await self.attendance_collection.batched_counts({
            "total": query,
            "present": {**query, "status": AttendanceStatus.PRESENT.value},
            "absent": {**query, "status": AttendanceStatus.ABSENT.value},
            "late": {**query, "status": AttendanceStatus.LATE.value},
            "excused": {**query, "status": AttendanceStatus.EXCUSED.value},
            "left_early": {**query, "status": AttendanceStatus.LEFT_EARLY.value},
        })
        total = counts["total"]
        present = counts["present"]
        absent = counts["absent"]
        late = counts["late"]

        return {
            "student_id": student_id,
            "total_days": total,
            "present_days": present,
            "absent_days": absent,
            "late_days": late,
            "excused_days": counts["excused"],
            "left_early_days": counts["left_early"],
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
        """Get attendance summary for a section over a period using aggregation"""
        query = {
            "tenant_id": tenant_id,
            "section_id": section_id,
            "attendance_date": {"$gte": start_date, "$lte": end_date}
        }

        pipeline = [
            {"$match": query},
            {"$group": {
                "_id": "$student_id",
                "total": {"$sum": 1},
                "present": {"$sum": {"$cond": [{"$eq": ["$status", AttendanceStatus.PRESENT.value]}, 1, 0]}},
                "absent": {"$sum": {"$cond": [{"$eq": ["$status", AttendanceStatus.ABSENT.value]}, 1, 0]}},
                "late": {"$sum": {"$cond": [{"$eq": ["$status", AttendanceStatus.LATE.value]}, 1, 0]}},
                "excused": {"$sum": {"$cond": [{"$eq": ["$status", AttendanceStatus.EXCUSED.value]}, 1, 0]}},
            }},
        ]
        rows = await self.attendance_collection.aggregate(pipeline).to_list(5000)

        student_stats = []
        total_records = 0
        total_present = 0
        for row in rows:
            t = row["total"]
            p = row["present"]
            total_records += t
            total_present += p
            student_stats.append({
                "student_id": row["_id"],
                "total": t,
                "present": p,
                "absent": row["absent"],
                "late": row["late"],
                "excused": row["excused"],
                "attendance_rate": round((p / t * 100) if t > 0 else 100, 2),
            })

        return {
            "section_id": section_id,
            "start_date": start_date,
            "end_date": end_date,
            "total_records": total_records,
            "overall_attendance_rate": round((total_present / total_records * 100) if total_records > 0 else 0, 2),
            "students": student_stats
        }
    
    async def get_tenant_attendance_overview(
        self,
        tenant_id: str,
        attendance_date: str
    ) -> Dict[str, Any]:
        """Get attendance overview for entire tenant using aggregation"""
        base_query = {"tenant_id": tenant_id, "attendance_date": attendance_date}

        import asyncio
        counts_coro = self.attendance_collection.batched_counts({
            "total": base_query,
            "present": {**base_query, "status": AttendanceStatus.PRESENT.value},
            "absent": {**base_query, "status": AttendanceStatus.ABSENT.value},
            "late": {**base_query, "status": AttendanceStatus.LATE.value},
        })
        sections_coro = self.attendance_collection.aggregate([
            {"$match": base_query},
            {"$group": {
                "_id": "$section_id",
                "total": {"$sum": 1},
                "present": {"$sum": {"$cond": [{"$eq": ["$status", AttendanceStatus.PRESENT.value]}, 1, 0]}},
                "absent": {"$sum": {"$cond": [{"$eq": ["$status", AttendanceStatus.ABSENT.value]}, 1, 0]}},
            }},
        ]).to_list(5000)

        counts, section_rows = await asyncio.gather(counts_coro, sections_coro)
        total = counts["total"]
        present = counts["present"]

        sections = [
            {"section_id": r["_id"], "total": r["total"], "present": r["present"], "absent": r["absent"]}
            for r in section_rows
        ]

        return {
            "tenant_id": tenant_id,
            "date": attendance_date,
            "total_students": total,
            "present": present,
            "absent": counts["absent"],
            "late": counts["late"],
            "attendance_rate": round((present / total * 100) if total > 0 else 0, 2),
            "sections_count": len(sections),
            "sections": sections
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
        """Get students with attendance rate below threshold using aggregation"""
        query = {"tenant_id": tenant_id}
        if start_date:
            query["attendance_date"] = {"$gte": start_date}
        if end_date:
            if "attendance_date" in query:
                query["attendance_date"]["$lte"] = end_date
            else:
                query["attendance_date"] = {"$lte": end_date}

        pipeline = [
            {"$match": query},
            {"$group": {
                "_id": "$student_id",
                "section_id": {"$first": "$section_id"},
                "total": {"$sum": 1},
                "present": {"$sum": {"$cond": [{"$eq": ["$status", AttendanceStatus.PRESENT.value]}, 1, 0]}},
            }},
        ]
        rows = await self.attendance_collection.aggregate(pipeline).to_list(10000)

        low_attendance = []
        for row in rows:
            t = row["total"]
            p = row["present"]
            rate = (p / t * 100) if t > 0 else 100
            if rate < threshold:
                low_attendance.append({
                    "student_id": row["_id"],
                    "section_id": row["section_id"],
                    "total": t,
                    "present": p,
                    "attendance_rate": round(rate, 2),
                    "absent_days": t - p,
                })

        low_attendance.sort(key=lambda x: x["attendance_rate"])
        return low_attendance
    
    async def get_consecutive_absences(
        self,
        tenant_id: str,
        min_days: int = 3
    ) -> List[Dict[str, Any]]:
        """Get students with consecutive absences (last 30 days).

        Two-step approach to minimise memory:
        1. Aggregate to find students with >= min_days total absences.
        2. Fetch only those students' absence dates for streak calculation.
        """
        end_dt = datetime.now(timezone.utc).date()
        start_dt = end_dt - timedelta(days=30)

        base_filter = {
            "tenant_id": tenant_id,
            "attendance_date": {"$gte": start_dt.isoformat(), "$lte": end_dt.isoformat()},
            "status": AttendanceStatus.ABSENT.value,
        }

        candidates = await self.attendance_collection.aggregate([
            {"$match": base_filter},
            {"$group": {"_id": "$student_id", "cnt": {"$sum": 1}}},
        ]).to_list(5000)

        candidate_ids = [c["_id"] for c in candidates if c.get("cnt", 0) >= min_days]
        if not candidate_ids:
            return []

        records = await self.attendance_collection.find(
            {**base_filter, "student_id": {"$in": candidate_ids}},
            {"_id": 0, "student_id": 1, "attendance_date": 1}
        ).sort([("student_id", 1), ("attendance_date", 1)]).to_list(len(candidate_ids) * 30)

        alerts = []
        current_student = None
        consecutive = 0
        last_date = None

        def _flush():
            if consecutive >= min_days:
                alerts.append({
                    "student_id": current_student,
                    "consecutive_days": consecutive,
                    "last_absence_date": last_date.isoformat() if last_date else None,
                })

        for record in records:
            sid = record.get("student_id")
            try:
                record_date = datetime.fromisoformat(record.get("attendance_date")).date()
            except (ValueError, TypeError):
                continue

            if sid != current_student:
                _flush()
                current_student = sid
                consecutive = 1
                last_date = record_date
            else:
                if last_date and (record_date - last_date).days <= 2:
                    consecutive += 1
                else:
                    _flush()
                    consecutive = 1
                last_date = record_date

        _flush()
        return alerts


# Export
__all__ = ["AttendanceEngine", "AttendanceStatus", "ExcuseType"]
