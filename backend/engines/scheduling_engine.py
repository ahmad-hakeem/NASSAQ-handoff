"""
NASSAQ Scheduling Engine
محرك الجداول الدراسية لمنصة نَسَّق

Handles:
- Master schedules management
- Time slots and periods
- Teacher assignments
- Schedule sessions
- Conflict detection
- Schedule optimization
"""

from typing import Optional, List, Dict, Any
from datetime import datetime, timezone, time
from enum import Enum
import uuid


class ScheduleStatus(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class SessionStatus(str, Enum):
    SCHEDULED = "scheduled"
    CANCELLED = "cancelled"
    SUBSTITUTE = "substitute"


class DayOfWeek(str, Enum):
    SUNDAY = "sunday"
    MONDAY = "monday"
    TUESDAY = "tuesday"
    WEDNESDAY = "wednesday"
    THURSDAY = "thursday"


class SchedulingEngine:
    """
    Core Scheduling Engine for NASSAQ
    Manages school schedules, sessions, and conflict detection
    """
    
    def __init__(self, db):
        self.db = db
        self.schedules_collection = db.schedules
        self.sessions_collection = db.schedule_sessions
        self.time_slots_collection = db.time_slots
        self.teacher_assignments_collection = db.teacher_assignments
        self.conflicts_collection = db.schedule_conflicts
        self.audit_collection = db.audit_logs
    
    # ============== TIME SLOTS ==============
    
    async def seed_default_time_slots(self, tenant_id: str, created_by: str) -> int:
        """Seed default time slots for a tenant"""
        default_slots = [
            {"period": 1, "start_time": "07:00", "end_time": "07:45", "type": "class"},
            {"period": 2, "start_time": "07:50", "end_time": "08:35", "type": "class"},
            {"period": 3, "start_time": "08:40", "end_time": "09:25", "type": "class"},
            {"period": 4, "start_time": "09:25", "end_time": "09:45", "type": "break", "name_ar": "الفسحة الأولى"},
            {"period": 5, "start_time": "09:45", "end_time": "10:30", "type": "class"},
            {"period": 6, "start_time": "10:35", "end_time": "11:20", "type": "class"},
            {"period": 7, "start_time": "11:25", "end_time": "12:10", "type": "class"},
            {"period": 8, "start_time": "12:10", "end_time": "12:55", "type": "prayer", "name_ar": "صلاة الظهر"},
            {"period": 9, "start_time": "12:55", "end_time": "13:40", "type": "class"},
        ]
        
        count = 0
        for slot in default_slots:
            existing = await self.time_slots_collection.find_one({
                "tenant_id": tenant_id,
                "period": slot["period"]
            })
            
            if not existing:
                slot_doc = {
                    "id": str(uuid.uuid4()),
                    "tenant_id": tenant_id,
                    **slot,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "created_by": created_by
                }
                await self.time_slots_collection.insert_one(slot_doc)
                count += 1
        
        return count
    
    async def get_time_slots(
        self,
        tenant_id: str,
        slot_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get time slots for a tenant"""
        query = {"tenant_id": tenant_id}
        
        if slot_type:
            query["type"] = slot_type
        
        slots = await self.time_slots_collection.find(
            query,
            {"_id": 0}
        ).sort("period", 1).to_list(50)
        
        return slots
    
    async def create_time_slot(
        self,
        tenant_id: str,
        period: int,
        start_time: str,
        end_time: str,
        slot_type: str,
        created_by: str,
        **kwargs
    ) -> Dict[str, Any]:
        """Create a new time slot"""
        slot_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        
        slot_doc = {
            "id": slot_id,
            "tenant_id": tenant_id,
            "period": period,
            "start_time": start_time,
            "end_time": end_time,
            "type": slot_type,
            "name_ar": kwargs.get("name_ar"),
            "name_en": kwargs.get("name_en"),
            "created_at": now,
            "created_by": created_by
        }
        
        await self.time_slots_collection.insert_one(slot_doc)
        return slot_doc
    
    async def update_time_slot(
        self,
        slot_id: str,
        updates: Dict[str, Any],
        updated_by: str
    ) -> Dict[str, Any]:
        """Update a time slot"""
        now = datetime.now(timezone.utc).isoformat()
        
        protected = ["id", "tenant_id", "created_at", "created_by"]
        for field in protected:
            updates.pop(field, None)
        
        updates["updated_at"] = now
        updates["updated_by"] = updated_by
        
        await self.time_slots_collection.update_one(
            {"id": slot_id},
            {"$set": updates}
        )
        
        return await self.time_slots_collection.find_one(
            {"id": slot_id},
            {"_id": 0}
        )
    
    # ============== MASTER SCHEDULES ==============
    
    async def create_schedule(
        self,
        tenant_id: str,
        name: str,
        academic_year: str,
        semester: int,
        created_by: str,
        **kwargs
    ) -> Dict[str, Any]:
        """Create a new master schedule"""
        schedule_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        
        schedule_doc = {
            "id": schedule_id,
            "tenant_id": tenant_id,
            "school_id": tenant_id,  # For backward compatibility
            "name": name,
            "name_en": kwargs.get("name_en"),
            "academic_year": academic_year,
            "semester": semester,
            "effective_from": kwargs.get("effective_from"),
            "effective_to": kwargs.get("effective_to"),
            "working_days": kwargs.get("working_days", ["sunday", "monday", "tuesday", "wednesday", "thursday"]),
            "status": ScheduleStatus.DRAFT.value,
            "periods_per_day": kwargs.get("periods_per_day", 7),
            "created_at": now,
            "created_by": created_by,
            "metadata": {
                "total_sessions": 0,
                "assigned_teachers": 0,
                "conflicts_count": 0
            }
        }
        
        await self.schedules_collection.insert_one(schedule_doc)
        
        # Log audit
        await self._log_audit(
            "schedule.created",
            schedule_id,
            created_by,
            tenant_id,
            {"name": name}
        )
        
        return schedule_doc
    
    async def get_schedules(
        self,
        tenant_id: str,
        status: Optional[str] = None,
        academic_year: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get schedules for a tenant"""
        query = {"tenant_id": tenant_id}
        
        if status:
            query["status"] = status
        if academic_year:
            query["academic_year"] = academic_year
        
        schedules = await self.schedules_collection.find(
            query,
            {"_id": 0}
        ).sort("created_at", -1).to_list(100)
        
        return schedules
    
    async def get_schedule_by_id(self, schedule_id: str) -> Optional[Dict[str, Any]]:
        """Get a schedule by ID"""
        return await self.schedules_collection.find_one(
            {"id": schedule_id},
            {"_id": 0}
        )
    
    async def update_schedule(
        self,
        schedule_id: str,
        updates: Dict[str, Any],
        updated_by: str
    ) -> Dict[str, Any]:
        """Update a schedule"""
        now = datetime.now(timezone.utc).isoformat()
        
        protected = ["id", "tenant_id", "school_id", "created_at", "created_by"]
        for field in protected:
            updates.pop(field, None)
        
        updates["updated_at"] = now
        updates["updated_by"] = updated_by
        
        await self.schedules_collection.update_one(
            {"id": schedule_id},
            {"$set": updates}
        )
        
        return await self.get_schedule_by_id(schedule_id)
    
    async def publish_schedule(
        self,
        schedule_id: str,
        published_by: str
    ) -> Dict[str, Any]:
        """Publish a schedule"""
        now = datetime.now(timezone.utc).isoformat()
        
        # Check for conflicts before publishing
        conflicts = await self.get_schedule_conflicts(schedule_id)
        if conflicts:
            raise ValueError(f"لا يمكن نشر الجدول - يوجد {len(conflicts)} تعارض")
        
        await self.schedules_collection.update_one(
            {"id": schedule_id},
            {
                "$set": {
                    "status": ScheduleStatus.PUBLISHED.value,
                    "published_at": now,
                    "published_by": published_by,
                    "updated_at": now
                }
            }
        )
        
        schedule = await self.get_schedule_by_id(schedule_id)
        
        # Log audit
        await self._log_audit(
            "schedule.published",
            schedule_id,
            published_by,
            schedule.get("tenant_id"),
            {}
        )
        
        return schedule
    
    async def archive_schedule(
        self,
        schedule_id: str,
        archived_by: str
    ) -> Dict[str, Any]:
        """Archive a schedule"""
        now = datetime.now(timezone.utc).isoformat()
        
        await self.schedules_collection.update_one(
            {"id": schedule_id},
            {
                "$set": {
                    "status": ScheduleStatus.ARCHIVED.value,
                    "archived_at": now,
                    "archived_by": archived_by,
                    "updated_at": now
                }
            }
        )
        
        return await self.get_schedule_by_id(schedule_id)
    
    async def delete_schedule(
        self,
        schedule_id: str,
        deleted_by: str
    ) -> bool:
        """Delete a schedule and its sessions"""
        schedule = await self.get_schedule_by_id(schedule_id)
        if not schedule:
            return False
        
        # Delete all sessions
        await self.sessions_collection.delete_many({"schedule_id": schedule_id})
        
        # Delete all conflicts
        await self.conflicts_collection.delete_many({"schedule_id": schedule_id})
        
        # Delete schedule
        await self.schedules_collection.delete_one({"id": schedule_id})
        
        # Log audit
        await self._log_audit(
            "schedule.deleted",
            schedule_id,
            deleted_by,
            schedule.get("tenant_id"),
            {"name": schedule.get("name")}
        )
        
        return True
    
    # ============== SCHEDULE SESSIONS ==============
    
    async def create_session(
        self,
        schedule_id: str,
        section_id: str,
        subject_id: str,
        teacher_id: str,
        day_of_week: str,
        period: int,
        created_by: str,
        **kwargs
    ) -> Dict[str, Any]:
        """Create a new schedule session"""
        # Get schedule info
        schedule = await self.get_schedule_by_id(schedule_id)
        if not schedule:
            raise ValueError("الجدول غير موجود")
        
        tenant_id = schedule.get("tenant_id")
        
        # Check for conflicts
        conflicts = await self._check_session_conflicts(
            tenant_id=tenant_id,
            schedule_id=schedule_id,
            day_of_week=day_of_week,
            period=period,
            teacher_id=teacher_id,
            section_id=section_id
        )
        
        session_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        
        session_doc = {
            "id": session_id,
            "schedule_id": schedule_id,
            "tenant_id": tenant_id,
            "section_id": section_id,
            "subject_id": subject_id,
            "teacher_id": teacher_id,
            "day_of_week": day_of_week,
            "period": period,
            "classroom_id": kwargs.get("classroom_id"),
            "status": SessionStatus.SCHEDULED.value,
            "is_recurring": kwargs.get("is_recurring", True),
            "has_conflicts": len(conflicts) > 0,
            "created_at": now,
            "created_by": created_by
        }
        
        await self.sessions_collection.insert_one(session_doc)
        
        # Store conflicts if any
        if conflicts:
            for conflict in conflicts:
                conflict["session_id"] = session_id
                conflict["schedule_id"] = schedule_id
                await self.conflicts_collection.insert_one(conflict)
        
        # Update schedule metadata
        await self._update_schedule_metadata(schedule_id)
        
        return session_doc
    
    async def get_sessions(
        self,
        schedule_id: str,
        section_id: Optional[str] = None,
        teacher_id: Optional[str] = None,
        day_of_week: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get sessions for a schedule"""
        query = {"schedule_id": schedule_id}
        
        if section_id:
            query["section_id"] = section_id
        if teacher_id:
            query["teacher_id"] = teacher_id
        if day_of_week:
            query["day_of_week"] = day_of_week
        
        sessions = await self.sessions_collection.find(
            query,
            {"_id": 0}
        ).sort([("day_of_week", 1), ("period", 1)]).to_list(1000)
        
        return sessions
    
    async def get_session_by_id(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get a session by ID"""
        return await self.sessions_collection.find_one(
            {"id": session_id},
            {"_id": 0}
        )
    
    async def update_session(
        self,
        session_id: str,
        updates: Dict[str, Any],
        updated_by: str
    ) -> Dict[str, Any]:
        """Update a session"""
        now = datetime.now(timezone.utc).isoformat()
        
        protected = ["id", "schedule_id", "tenant_id", "created_at", "created_by"]
        for field in protected:
            updates.pop(field, None)
        
        updates["updated_at"] = now
        updates["updated_by"] = updated_by
        
        # If changing day/period/teacher, recheck conflicts
        session = await self.get_session_by_id(session_id)
        if session and any(k in updates for k in ["day_of_week", "period", "teacher_id", "section_id"]):
            new_day = updates.get("day_of_week", session.get("day_of_week"))
            new_period = updates.get("period", session.get("period"))
            new_teacher = updates.get("teacher_id", session.get("teacher_id"))
            new_section = updates.get("section_id", session.get("section_id"))
            
            conflicts = await self._check_session_conflicts(
                tenant_id=session.get("tenant_id"),
                schedule_id=session.get("schedule_id"),
                day_of_week=new_day,
                period=new_period,
                teacher_id=new_teacher,
                section_id=new_section,
                exclude_session_id=session_id
            )
            
            updates["has_conflicts"] = len(conflicts) > 0
            
            # Update conflicts
            await self.conflicts_collection.delete_many({"session_id": session_id})
            if conflicts:
                for conflict in conflicts:
                    conflict["session_id"] = session_id
                    conflict["schedule_id"] = session.get("schedule_id")
                    await self.conflicts_collection.insert_one(conflict)
        
        await self.sessions_collection.update_one(
            {"id": session_id},
            {"$set": updates}
        )
        
        return await self.get_session_by_id(session_id)
    
    async def move_session(
        self,
        session_id: str,
        new_day: str,
        new_period: int,
        moved_by: str
    ) -> Dict[str, Any]:
        """Move a session to a new time slot"""
        return await self.update_session(
            session_id,
            {
                "day_of_week": new_day,
                "period": new_period
            },
            moved_by
        )
    
    async def delete_session(
        self,
        session_id: str,
        deleted_by: str
    ) -> bool:
        """Delete a session"""
        session = await self.get_session_by_id(session_id)
        if not session:
            return False
        
        # Delete conflicts
        await self.conflicts_collection.delete_many({"session_id": session_id})
        
        # Delete session
        await self.sessions_collection.delete_one({"id": session_id})
        
        # Update schedule metadata
        await self._update_schedule_metadata(session.get("schedule_id"))
        
        return True
    
    # ============== CONFLICT DETECTION ==============
    
    async def _check_session_conflicts(
        self,
        tenant_id: str,
        schedule_id: str,
        day_of_week: str,
        period: int,
        teacher_id: str,
        section_id: str,
        exclude_session_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Check for scheduling conflicts"""
        conflicts = []
        now = datetime.now(timezone.utc).isoformat()
        
        # Build base query
        base_query = {
            "schedule_id": schedule_id,
            "day_of_week": day_of_week,
            "period": period
        }
        
        if exclude_session_id:
            base_query["id"] = {"$ne": exclude_session_id}
        
        # Check teacher conflict
        teacher_query = {**base_query, "teacher_id": teacher_id}
        teacher_conflict = await self.sessions_collection.find_one(teacher_query, {"_id": 0})
        if teacher_conflict:
            conflicts.append({
                "id": str(uuid.uuid4()),
                "type": "teacher_overlap",
                "description_ar": "المعلم مشغول في هذا الوقت",
                "description_en": "Teacher is busy at this time",
                "conflicting_session_id": teacher_conflict.get("id"),
                "teacher_id": teacher_id,
                "day_of_week": day_of_week,
                "period": period,
                "detected_at": now
            })
        
        # Check section conflict
        section_query = {**base_query, "section_id": section_id}
        section_conflict = await self.sessions_collection.find_one(section_query, {"_id": 0})
        if section_conflict:
            conflicts.append({
                "id": str(uuid.uuid4()),
                "type": "section_overlap",
                "description_ar": "الشعبة لديها حصة أخرى في هذا الوقت",
                "description_en": "Section has another class at this time",
                "conflicting_session_id": section_conflict.get("id"),
                "section_id": section_id,
                "day_of_week": day_of_week,
                "period": period,
                "detected_at": now
            })
        
        return conflicts
    
    async def get_schedule_conflicts(
        self,
        schedule_id: str
    ) -> List[Dict[str, Any]]:
        """Get all conflicts for a schedule"""
        conflicts = await self.conflicts_collection.find(
            {"schedule_id": schedule_id},
            {"_id": 0}
        ).to_list(1000)
        
        return conflicts
    
    async def resolve_conflict(
        self,
        conflict_id: str,
        resolved_by: str,
        resolution_note: Optional[str] = None
    ) -> bool:
        """Mark a conflict as resolved"""
        now = datetime.now(timezone.utc).isoformat()
        
        result = await self.conflicts_collection.update_one(
            {"id": conflict_id},
            {
                "$set": {
                    "is_resolved": True,
                    "resolved_at": now,
                    "resolved_by": resolved_by,
                    "resolution_note": resolution_note
                }
            }
        )
        
        return result.modified_count > 0
    
    # ============== TEACHER ASSIGNMENTS ==============
    
    async def assign_teacher_to_subject(
        self,
        tenant_id: str,
        teacher_id: str,
        subject_id: str,
        section_ids: List[str],
        academic_year: str,
        assigned_by: str,
        **kwargs
    ) -> Dict[str, Any]:
        """Assign a teacher to teach a subject for specific sections"""
        assignment_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        
        assignment_doc = {
            "id": assignment_id,
            "tenant_id": tenant_id,
            "teacher_id": teacher_id,
            "subject_id": subject_id,
            "section_ids": section_ids,
            "academic_year": academic_year,
            "periods_per_week": kwargs.get("periods_per_week", 4),
            "is_active": True,
            "created_at": now,
            "assigned_by": assigned_by
        }
        
        await self.teacher_assignments_collection.insert_one(assignment_doc)
        
        return assignment_doc
    
    async def get_teacher_assignments(
        self,
        tenant_id: str,
        teacher_id: Optional[str] = None,
        subject_id: Optional[str] = None,
        academic_year: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get teacher assignments"""
        query = {"tenant_id": tenant_id, "is_active": True}
        
        if teacher_id:
            query["teacher_id"] = teacher_id
        if subject_id:
            query["subject_id"] = subject_id
        if academic_year:
            query["academic_year"] = academic_year
        
        assignments = await self.teacher_assignments_collection.find(
            query,
            {"_id": 0}
        ).to_list(1000)
        
        return assignments
    
    async def get_teacher_weekly_schedule(
        self,
        tenant_id: str,
        teacher_id: str,
        schedule_id: Optional[str] = None
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Get a teacher's weekly schedule"""
        query = {"tenant_id": tenant_id, "teacher_id": teacher_id}
        
        if schedule_id:
            query["schedule_id"] = schedule_id
        
        sessions = await self.sessions_collection.find(
            query,
            {"_id": 0}
        ).to_list(1000)
        
        # Group by day
        weekly = {day.value: [] for day in DayOfWeek}
        for session in sessions:
            day = session.get("day_of_week")
            if day in weekly:
                weekly[day].append(session)
        
        # Sort by period
        for day in weekly:
            weekly[day].sort(key=lambda x: x.get("period", 0))
        
        return weekly
    
    async def get_section_weekly_schedule(
        self,
        tenant_id: str,
        section_id: str,
        schedule_id: Optional[str] = None
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Get a section's weekly schedule"""
        query = {"tenant_id": tenant_id, "section_id": section_id}
        
        if schedule_id:
            query["schedule_id"] = schedule_id
        
        sessions = await self.sessions_collection.find(
            query,
            {"_id": 0}
        ).to_list(1000)
        
        # Group by day
        weekly = {day.value: [] for day in DayOfWeek}
        for session in sessions:
            day = session.get("day_of_week")
            if day in weekly:
                weekly[day].append(session)
        
        # Sort by period
        for day in weekly:
            weekly[day].sort(key=lambda x: x.get("period", 0))
        
        return weekly
    
    # ============== SCHEDULE STATISTICS ==============
    
    async def get_schedule_statistics(self, schedule_id: str) -> Dict[str, Any]:
        """Get statistics for a schedule"""
        sessions = await self.get_sessions(schedule_id)
        conflicts = await self.get_schedule_conflicts(schedule_id)
        
        # Unique teachers and sections
        teachers = set(s.get("teacher_id") for s in sessions if s.get("teacher_id"))
        sections = set(s.get("section_id") for s in sessions if s.get("section_id"))
        subjects = set(s.get("subject_id") for s in sessions if s.get("subject_id"))
        
        # Sessions per day
        sessions_per_day = {}
        for day in DayOfWeek:
            sessions_per_day[day.value] = len([s for s in sessions if s.get("day_of_week") == day.value])
        
        return {
            "schedule_id": schedule_id,
            "total_sessions": len(sessions),
            "unique_teachers": len(teachers),
            "unique_sections": len(sections),
            "unique_subjects": len(subjects),
            "total_conflicts": len(conflicts),
            "unresolved_conflicts": len([c for c in conflicts if not c.get("is_resolved")]),
            "sessions_per_day": sessions_per_day
        }
    
    # ============== HELPER METHODS ==============
    
    async def _update_schedule_metadata(self, schedule_id: str):
        """Update schedule metadata after changes"""
        stats = await self.get_schedule_statistics(schedule_id)
        
        await self.schedules_collection.update_one(
            {"id": schedule_id},
            {
                "$set": {
                    "metadata": {
                        "total_sessions": stats["total_sessions"],
                        "assigned_teachers": stats["unique_teachers"],
                        "conflicts_count": stats["total_conflicts"]
                    },
                    "updated_at": datetime.now(timezone.utc).isoformat()
                }
            }
        )
    
    async def _log_audit(
        self,
        action: str,
        entity_id: str,
        performed_by: str,
        tenant_id: str,
        details: Dict[str, Any]
    ):
        """Log an audit entry"""
        audit_doc = {
            "id": str(uuid.uuid4()),
            "action": action,
            "entity_type": "schedule",
            "entity_id": entity_id,
            "performed_by": performed_by,
            "tenant_id": tenant_id,
            "details": details,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        await self.audit_collection.insert_one(audit_doc)


# Export
__all__ = ["SchedulingEngine", "ScheduleStatus", "SessionStatus", "DayOfWeek"]
