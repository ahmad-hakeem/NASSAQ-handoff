"""
NASSAQ Scheduling Sub-module
"""
from fastapi import APIRouter, HTTPException, Depends, status, Header, Query, Body, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import Response
from starlette.responses import StreamingResponse
from pydantic import BaseModel, Field, ConfigDict, EmailStr, model_validator
from typing import List, Optional, Any, Dict
from datetime import datetime, timezone, timedelta
import uuid, os, logging, json, random, re, io, base64

logger = logging.getLogger("nassaq.scheduling")

from dependencies import (
    db, get_current_user, require_roles, UserRole, SchoolStatus,
    hash_password, verify_password, create_access_token,
    JWT_SECRET, JWT_ALGORITHM, ACCESS_TOKEN_EXPIRE, security,
    audit_engine, AuditAction, AuditSeverity,
    smart_scheduling_engine, TimetableRunStatus, TimetableStatus,
    ConflictType, ConflictSeverity, PreValidationResult, GenerationResult,
    hakim_engine, reporting_engine, export_engine, session_engine,
    REPORT_TYPES, generate_student_qr_code
)
from engines.sql_utils import gd_find, gd_find_one, gd_insert, gd_insert_many, gd_update_one, gd_update_many, gd_count, gd_delete_one, gd_delete_many, gd_distinct
from utils.tenant_scope import assert_school_access


from shared_models import (
    StatusCheck, StatusCheckCreate, TeacherRankEnum, SessionStatusEnum, ScheduleStatusEnum, TimeSlotCreate, TimeSlotResponse, TeacherAssignmentCreate, TeacherAssignmentResponse, SchoolScheduleCreate, SchoolScheduleResponse, ScheduleSessionCreate, ScheduleSessionResponse
)

router = APIRouter()

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
    
    schedule = await gd_find_one(db.session, "schedules", {"id": schedule_id})
    if not schedule:
        raise HTTPException(status_code=404, detail="الجدول غير موجود")
    assert_school_access(current_user, str(schedule.get("school_id")))
    
    school_id = schedule.get("school_id")
    working_days = schedule.get("working_days", ["sunday", "monday", "tuesday", "wednesday", "thursday"])
    
    # Get time slots
    time_slots = await gd_find(db.session, "time_slots", {"school_id": school_id, "is_active": True, "is_break": False}, order_by="slot_number", desc_order=False, limit=20)
    
    if not time_slots:
        raise HTTPException(status_code=400, detail="لم يتم تعريف الفترات الزمنية")
    
    # Get assignments - try exact match first, then fallback to any active assignments
    schedule_academic_year = schedule.get("academic_year")
    schedule_semester = schedule.get("semester")
    
    assignments = await gd_find(db.session, "teacher_assignments", {
        "school_id": school_id,
        "is_active": True,
        "academic_year": schedule_academic_year,
        "semester": schedule_semester
    }, limit=500)
    
    # If no assignments found with exact match, try without year/semester filter
    if not assignments:
        assignments = await gd_find(db.session, "teacher_assignments", {
            "school_id": school_id,
            "is_active": True
        }, limit=500)
    
    if not assignments:
        raise HTTPException(status_code=400, detail="لم يتم العثور على إسنادات للمعلمين. يرجى إضافة إسنادات من صفحة الإعدادات -> تبويب الإسنادات")
    
    # Get teacher info for workload calculation
    teacher_ids = list(set(a.get("teacher_id") for a in assignments if a.get("teacher_id")))
    teachers = await gd_find(db.session, "teachers", {"id": {"$in": teacher_ids}}, limit=500)
    teacher_map = {t.get("id"): t for t in teachers}
    
    # Workload limits by rank
    workload_limits = {
        TeacherRankEnum.EXPERT.value: {"daily_max": 4, "weekly_max": 18},
        TeacherRankEnum.ADVANCED.value: {"daily_max": 5, "weekly_max": 20},
        TeacherRankEnum.PRACTITIONER.value: {"daily_max": 6, "weekly_max": 24},
        TeacherRankEnum.ASSISTANT.value: {"daily_max": 7, "weekly_max": 26},
    }
    
    # Clear existing sessions
    await gd_delete_many(db.session, "schedule_sessions", {"schedule_id": schedule_id})
    
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
                await gd_insert(db.session, "schedule_sessions", session_doc)
                
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
    await gd_update_one(db.session, "schedules", {"id": schedule_id}, {
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
        })
    
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
    
    sessions = await gd_find(db.session, "schedule_sessions", {
        "schedule_id": schedule_id,
        "status": {"$ne": SessionStatusEnum.CANCELLED.value}
    }, limit=1000)
    
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
        assignments = await gd_find(db.session, "teacher_assignments", {"id": {"$in": assignment_ids}}, limit=100)
        assignment_map = {a.get("id"): a for a in assignments}
        
        teachers_seen = {}
        classes_seen = {}
        rooms_seen = {}
        
        # Get time slot info
        time_slot = await gd_find_one(db.session, "time_slots", {"id": slot_id})
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
                    teacher = await gd_find_one(db.session, "teachers", {"id": teacher_id})
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
                    class_doc = await gd_find_one(db.session, "classes", {"id": class_id})
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
                    room_doc = await gd_find_one(db.session, "classrooms", {"id": room_id})
                    room_name = (room_doc.get("name_ar") or room_doc.get("name")) if room_doc else "غير معروف"
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
    schedule = await gd_find_one(db.session, "schedules", {"id": schedule_id})
    if not schedule:
        raise HTTPException(status_code=404, detail="الجدول غير موجود")
    
    school_id = schedule.get("school_id")
    working_days = schedule.get("working_days") or ["sunday", "monday", "tuesday", "wednesday", "thursday"]
    
    # Get all sessions
    sessions = await gd_find(db.session, "schedule_sessions", {
        "schedule_id": schedule_id,
        "status": {"$ne": SessionStatusEnum.CANCELLED.value}
    }, limit=1000)
    
    # Get time slots
    time_slots = await gd_find(db.session, "time_slots", {"school_id": school_id, "is_active": True, "is_break": False}, order_by="slot_number", desc_order=False, limit=20)
    
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
                teacher = await gd_find_one(db.session, "teachers", {"id": teacher_id})
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
                class_doc = await gd_find_one(db.session, "classes", {"id": class_id})
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
    schedule = await gd_find_one(db.session, "schedules", {"id": schedule_id})
    if not schedule:
        raise HTTPException(status_code=404, detail="الجدول غير موجود")
    
    # Get session
    session = await gd_find_one(db.session, "schedule_sessions", {"id": session_id, "schedule_id": schedule_id})
    if not session:
        raise HTTPException(status_code=404, detail="الحصة غير موجودة")
    
    school_id = schedule.get("school_id")
    working_days = schedule.get("working_days") or ["sunday", "monday", "tuesday", "wednesday", "thursday"]
    
    # Validate target day
    if target_day not in working_days:
        raise HTTPException(status_code=400, detail="اليوم المحدد غير صالح")
    
    # Validate target slot exists
    target_slot = await gd_find_one(db.session, "time_slots", {"id": target_slot_id, "school_id": school_id})
    if not target_slot:
        raise HTTPException(status_code=400, detail="الفترة الزمنية غير موجودة")
    
    old_day = session.get("day_of_week")
    old_slot_id = session.get("time_slot_id")
    teacher_id = session.get("teacher_id")
    class_id = session.get("class_id")
    
    # Check if target slot is free for teacher
    if teacher_id:
        teacher_conflict = await gd_find_one(db.session, "schedule_sessions", {
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
        class_conflict = await gd_find_one(db.session, "schedule_sessions", {
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
    await gd_update_one(db.session, "schedule_sessions", {"id": session_id}, {
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
        })
    
    # Get updated slot info for response
    old_slot = await gd_find_one(db.session, "time_slots", {"id": old_slot_id})
    
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
    result = await gd_update_one(db.session, "teachers", {"id": teacher_id}, {"rank": rank.value, "updated_at": datetime.now(timezone.utc).isoformat()})
    if result == 0:
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
    teacher = await gd_find_one(db.session, "teachers", {"id": teacher_id})
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
    assignments = await gd_find(db.session, "teacher_assignments", {"teacher_id": teacher_id, "is_active": True}, limit=50)
    
    total_weekly_sessions = sum(a.get("weekly_sessions", 0) for a in assignments)
    
    # Get actual sessions if schedule_id provided
    actual_sessions = 0
    sessions_by_day = {}
    if schedule_id:
        assignment_ids = [a.get("id") for a in assignments]
        sessions = await gd_find(db.session, "schedule_sessions", {
            "schedule_id": schedule_id,
            "assignment_id": {"$in": assignment_ids},
            "status": {"$ne": SessionStatusEnum.CANCELLED.value}
        }, limit=200)
        
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
    existing = await gd_count(db.session, "time_slots", {"school_id": school_id})
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
        await gd_insert(db.session, "time_slots", slot_doc)
        created += 1
    
    return {"message": f"تم إنشاء {created} فترة زمنية", "count": created}





