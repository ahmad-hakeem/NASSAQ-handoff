"""
Scheduling Service for NASSAQ Platform
خدمة الجدولة لمنصة نَسَّق

This service handles:
- Schedule validation and conflict detection
- Automatic schedule generation
- Teacher workload calculations
"""

import random
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timezone
import uuid

from models.scheduling import (
    TeacherRank,
    DayOfWeek,
    SessionStatus,
    ScheduleStatus,
    ScheduleConflict,
    ScheduleGenerationResult,
    DEFAULT_WORKLOAD_CONFIGS
)


class SchedulingService:
    """خدمة الجدولة الذكية"""
    
    def __init__(self, db):
        self.db = db
    
    async def validate_session(
        self,
        school_id: str,
        schedule_id: str,
        assignment_id: str,
        day: DayOfWeek,
        time_slot_id: str,
        exclude_session_id: Optional[str] = None
    ) -> List[ScheduleConflict]:
        """
        التحقق من صحة حصة مقترحة
        Validate a proposed session for conflicts
        """
        conflicts = []
        
        # Get assignment details
        assignment = await self.db.teacher_assignments.find_one(
            {"id": assignment_id}, {"_id": 0}
        )
        if not assignment:
            conflicts.append(ScheduleConflict(
                conflict_type="invalid_assignment",
                message="Assignment not found",
                message_ar="الإسناد غير موجود",
                day=day,
                time_slot_id=time_slot_id,
                severity="error"
            ))
            return conflicts
        
        teacher_id = assignment.get("teacher_id")
        class_id = assignment.get("class_id")
        
        # Build query for existing sessions
        base_query = {
            "schedule_id": schedule_id,
            "day_of_week": day.value,
            "time_slot_id": time_slot_id,
            "status": {"$ne": SessionStatus.CANCELLED.value}
        }
        
        if exclude_session_id:
            base_query["id"] = {"$ne": exclude_session_id}
        
        existing_sessions = await self.db.schedule_sessions.find(
            base_query, {"_id": 0}
        ).to_list(100)
        
        for session in existing_sessions:
            session_assignment = await self.db.teacher_assignments.find_one(
                {"id": session.get("assignment_id")}, {"_id": 0}
            )
            if not session_assignment:
                continue
            
            # Check teacher double booking
            if session_assignment.get("teacher_id") == teacher_id:
                teacher = await self.db.teachers.find_one(
                    {"id": teacher_id}, {"_id": 0, "full_name": 1}
                )
                teacher_name = teacher.get("full_name", "Unknown") if teacher else "Unknown"
                conflicts.append(ScheduleConflict(
                    conflict_type="teacher_double_booking",
                    message=f"Teacher {teacher_name} is already scheduled at this time",
                    message_ar=f"المعلم {teacher_name} مجدول بالفعل في هذا الوقت",
                    day=day,
                    time_slot_id=time_slot_id,
                    conflicting_sessions=[session.get("id")],
                    severity="error"
                ))
            
            # Check class double booking
            if session_assignment.get("class_id") == class_id:
                class_doc = await self.db.classes.find_one(
                    {"id": class_id}, {"_id": 0, "name": 1}
                )
                class_name = class_doc.get("name", "Unknown") if class_doc else "Unknown"
                conflicts.append(ScheduleConflict(
                    conflict_type="class_double_booking",
                    message=f"Class {class_name} is already scheduled at this time",
                    message_ar=f"الفصل {class_name} مجدول بالفعل في هذا الوقت",
                    day=day,
                    time_slot_id=time_slot_id,
                    conflicting_sessions=[session.get("id")],
                    severity="error"
                ))
        
        return conflicts
    
    async def calculate_teacher_workload(
        self,
        teacher_id: str,
        schedule_id: str
    ) -> Dict:
        """
        حساب النصاب الفعلي للمعلم
        Calculate teacher's actual workload in a schedule
        """
        # Get teacher info with rank
        teacher = await self.db.teachers.find_one(
            {"id": teacher_id}, {"_id": 0}
        )
        if not teacher:
            return {"error": "Teacher not found"}
        
        rank_str = teacher.get("rank", TeacherRank.PRACTITIONER.value)
        try:
            rank = TeacherRank(rank_str)
        except ValueError:
            rank = TeacherRank.PRACTITIONER
        
        workload_config = DEFAULT_WORKLOAD_CONFIGS.get(rank)
        
        # Get teacher's assignments
        assignments = await self.db.teacher_assignments.find(
            {"teacher_id": teacher_id, "is_active": True}, {"_id": 0}
        ).to_list(100)
        
        assignment_ids = [a.get("id") for a in assignments]
        
        # Count sessions in schedule
        sessions = await self.db.schedule_sessions.find({
            "schedule_id": schedule_id,
            "assignment_id": {"$in": assignment_ids},
            "status": {"$ne": SessionStatus.CANCELLED.value}
        }, {"_id": 0}).to_list(200)
        
        # Group by day
        sessions_by_day = {}
        for session in sessions:
            day = session.get("day_of_week")
            if day not in sessions_by_day:
                sessions_by_day[day] = []
            sessions_by_day[day].append(session)
        
        total_weekly_sessions = len(sessions)
        max_daily_sessions = max(len(s) for s in sessions_by_day.values()) if sessions_by_day else 0
        
        return {
            "teacher_id": teacher_id,
            "teacher_name": teacher.get("full_name"),
            "rank": rank.value,
            "weekly_sessions": total_weekly_sessions,
            "weekly_hours_min": workload_config.weekly_hours_min if workload_config else 18,
            "weekly_hours_max": workload_config.weekly_hours_max if workload_config else 24,
            "max_daily_sessions": max_daily_sessions,
            "daily_sessions_limit": workload_config.daily_sessions_max if workload_config else 6,
            "sessions_by_day": {k: len(v) for k, v in sessions_by_day.items()},
            "is_overloaded": total_weekly_sessions > (workload_config.weekly_hours_max if workload_config else 24),
            "is_underloaded": total_weekly_sessions < (workload_config.weekly_hours_min if workload_config else 18)
        }
    
    async def detect_all_conflicts(
        self,
        schedule_id: str
    ) -> List[ScheduleConflict]:
        """
        اكتشاف جميع التعارضات في الجدول
        Detect all conflicts in a schedule
        """
        conflicts = []
        
        # Get all sessions
        sessions = await self.db.schedule_sessions.find({
            "schedule_id": schedule_id,
            "status": {"$ne": SessionStatus.CANCELLED.value}
        }, {"_id": 0}).to_list(1000)
        
        # Group by day and time slot
        by_day_slot = {}
        for session in sessions:
            key = (session.get("day_of_week"), session.get("time_slot_id"))
            if key not in by_day_slot:
                by_day_slot[key] = []
            by_day_slot[key].append(session)
        
        # Check for conflicts in each time slot
        for (day, slot_id), slot_sessions in by_day_slot.items():
            if len(slot_sessions) < 2:
                continue
            
            # Get all assignments for these sessions
            assignment_ids = [s.get("assignment_id") for s in slot_sessions]
            assignments = await self.db.teacher_assignments.find(
                {"id": {"$in": assignment_ids}}, {"_id": 0}
            ).to_list(100)
            assignment_map = {a.get("id"): a for a in assignments}
            
            # Check teacher conflicts
            teachers_in_slot = {}
            classes_in_slot = {}
            
            for session in slot_sessions:
                assignment = assignment_map.get(session.get("assignment_id"), {})
                teacher_id = assignment.get("teacher_id")
                class_id = assignment.get("class_id")
                
                if teacher_id:
                    if teacher_id not in teachers_in_slot:
                        teachers_in_slot[teacher_id] = []
                    teachers_in_slot[teacher_id].append(session.get("id"))
                
                if class_id:
                    if class_id not in classes_in_slot:
                        classes_in_slot[class_id] = []
                    classes_in_slot[class_id].append(session.get("id"))
            
            # Report teacher conflicts
            for teacher_id, session_ids in teachers_in_slot.items():
                if len(session_ids) > 1:
                    teacher = await self.db.teachers.find_one(
                        {"id": teacher_id}, {"_id": 0, "full_name": 1}
                    )
                    name = teacher.get("full_name", "Unknown") if teacher else "Unknown"
                    conflicts.append(ScheduleConflict(
                        conflict_type="teacher_double_booking",
                        message=f"Teacher {name} has multiple sessions",
                        message_ar=f"المعلم {name} لديه أكثر من حصة في نفس الوقت",
                        day=DayOfWeek(day),
                        time_slot_id=slot_id,
                        conflicting_sessions=session_ids,
                        severity="error"
                    ))
            
            # Report class conflicts
            for class_id, session_ids in classes_in_slot.items():
                if len(session_ids) > 1:
                    class_doc = await self.db.classes.find_one(
                        {"id": class_id}, {"_id": 0, "name": 1}
                    )
                    name = class_doc.get("name", "Unknown") if class_doc else "Unknown"
                    conflicts.append(ScheduleConflict(
                        conflict_type="class_double_booking",
                        message=f"Class {name} has multiple sessions",
                        message_ar=f"الفصل {name} لديه أكثر من حصة في نفس الوقت",
                        day=DayOfWeek(day),
                        time_slot_id=slot_id,
                        conflicting_sessions=session_ids,
                        severity="error"
                    ))
        
        return conflicts
    
    async def generate_schedule(
        self,
        school_id: str,
        schedule_id: str,
        respect_workload: bool = True,
        max_iterations: int = 1000
    ) -> ScheduleGenerationResult:
        """
        توليد الجدول تلقائياً
        Automatically generate schedule
        """
        warnings = []
        
        # Get schedule info
        schedule = await self.db.schedules.find_one(
            {"id": schedule_id}, {"_id": 0}
        )
        if not schedule:
            return ScheduleGenerationResult(
                success=False,
                schedule_id=schedule_id,
                message="Schedule not found",
                message_ar="الجدول غير موجود"
            )
        
        # Get working days
        working_days = schedule.get("working_days", [
            DayOfWeek.SUNDAY.value, DayOfWeek.MONDAY.value, DayOfWeek.TUESDAY.value,
            DayOfWeek.WEDNESDAY.value, DayOfWeek.THURSDAY.value
        ])
        
        # Get time slots
        time_slots = await self.db.time_slots.find(
            {"school_id": school_id, "is_active": True, "is_break": False},
            {"_id": 0}
        ).to_list(20)
        
        if not time_slots:
            return ScheduleGenerationResult(
                success=False,
                schedule_id=schedule_id,
                message="No time slots defined",
                message_ar="لم يتم تعريف الفترات الزمنية"
            )
        
        # Sort time slots by slot_number
        time_slots.sort(key=lambda x: x.get("slot_number", 0))
        
        # Get active assignments for this school
        assignments = await self.db.teacher_assignments.find(
            {
                "school_id": school_id,
                "is_active": True,
                "academic_year": schedule.get("academic_year"),
                "semester": schedule.get("semester")
            },
            {"_id": 0}
        ).to_list(500)
        
        if not assignments:
            return ScheduleGenerationResult(
                success=False,
                schedule_id=schedule_id,
                message="No teacher assignments found",
                message_ar="لم يتم العثور على إسنادات للمعلمين"
            )
        
        # Clear existing sessions for this schedule
        await self.db.schedule_sessions.delete_many({
            "schedule_id": schedule_id
        })
        
        # Build placement requirements
        # Each assignment needs weekly_sessions distributed across days
        sessions_to_place = []
        for assignment in assignments:
            weekly_sessions = assignment.get("weekly_sessions", 4)
            for i in range(weekly_sessions):
                sessions_to_place.append({
                    "assignment_id": assignment.get("id"),
                    "teacher_id": assignment.get("teacher_id"),
                    "class_id": assignment.get("class_id"),
                    "subject_id": assignment.get("subject_id"),
                    "placed": False
                })
        
        # Shuffle for randomness
        random.shuffle(sessions_to_place)
        
        # Track placements
        teacher_schedule = {}  # teacher_id -> {day -> [slot_ids]}
        class_schedule = {}    # class_id -> {day -> [slot_ids]}
        sessions_created = 0
        
        # Try to place each session
        for session_req in sessions_to_place:
            teacher_id = session_req["teacher_id"]
            class_id = session_req["class_id"]
            assignment_id = session_req["assignment_id"]
            
            if teacher_id not in teacher_schedule:
                teacher_schedule[teacher_id] = {d: [] for d in working_days}
            if class_id not in class_schedule:
                class_schedule[class_id] = {d: [] for d in working_days}
            
            # Try to find a valid slot
            placed = False
            days_tried = list(working_days)
            random.shuffle(days_tried)
            
            for day in days_tried:
                if placed:
                    break
                
                for slot in time_slots:
                    slot_id = slot.get("id")
                    
                    # Check if teacher is free
                    if slot_id in teacher_schedule[teacher_id].get(day, []):
                        continue
                    
                    # Check if class is free
                    if slot_id in class_schedule[class_id].get(day, []):
                        continue
                    
                    # Check workload limits if enabled
                    if respect_workload:
                        daily_count = len(teacher_schedule[teacher_id].get(day, []))
                        if daily_count >= 6:  # Max daily sessions
                            continue
                    
                    # Place the session
                    session_id = str(uuid.uuid4())
                    session_doc = {
                        "id": session_id,
                        "school_id": school_id,
                        "schedule_id": schedule_id,
                        "assignment_id": assignment_id,
                        "day_of_week": day,
                        "time_slot_id": slot_id,
                        "room_id": None,
                        "status": SessionStatus.SCHEDULED.value,
                        "created_at": datetime.now(timezone.utc).isoformat(),
                        "updated_at": datetime.now(timezone.utc).isoformat()
                    }
                    
                    await self.db.schedule_sessions.insert_one(session_doc)
                    
                    # Update tracking
                    teacher_schedule[teacher_id][day].append(slot_id)
                    class_schedule[class_id][day].append(slot_id)
                    sessions_created += 1
                    session_req["placed"] = True
                    placed = True
                    break
            
            if not placed:
                warnings.append(f"Could not place session for assignment {assignment_id}")
        
        # Detect any remaining conflicts
        conflicts = await self.detect_all_conflicts(schedule_id)
        
        # Update schedule status
        await self.db.schedules.update_one(
            {"id": schedule_id},
            {
                "$set": {
                    "total_sessions": sessions_created,
                    "status": ScheduleStatus.DRAFT.value,
                    "updated_at": datetime.now(timezone.utc).isoformat()
                }
            }
        )
        
        unplaced = sum(1 for s in sessions_to_place if not s["placed"])
        
        return ScheduleGenerationResult(
            success=len(conflicts) == 0 and unplaced == 0,
            schedule_id=schedule_id,
            sessions_created=sessions_created,
            conflicts=conflicts,
            warnings=warnings + ([f"{unplaced} sessions could not be placed"] if unplaced > 0 else []),
            message=f"Generated {sessions_created} sessions with {len(conflicts)} conflicts",
            message_ar=f"تم إنشاء {sessions_created} حصة مع {len(conflicts)} تعارض"
        )
