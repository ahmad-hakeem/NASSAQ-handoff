"""
NASSAQ Scheduling Routes
مسارات API للجدولة

Endpoints:
- Time slots management
- Master schedules
- Schedule sessions
- Conflict detection
- Teacher assignments
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime
from enum import Enum
import logging

logger = logging.getLogger("nassaq.scheduling_routes")

# Import from parent - these will be injected
# from engines.scheduling_engine import SchedulingEngine
# from middleware.rbac import require_permission, Permission


# ============== MODELS ==============

class TimeSlotCreate(BaseModel):
    period: int
    start_time: str
    end_time: str
    slot_type: str = "class"
    name_ar: Optional[str] = None
    name_en: Optional[str] = None


class TimeSlotResponse(BaseModel):
    id: str
    tenant_id: str
    period: int
    start_time: str
    end_time: str
    type: str
    name_ar: Optional[str] = None
    name_en: Optional[str] = None
    created_at: str


class ScheduleCreate(BaseModel):
    name: str
    name_en: Optional[str] = None
    academic_year: str
    semester: int
    effective_from: Optional[str] = None
    effective_to: Optional[str] = None
    working_days: List[str] = ["sunday", "monday", "tuesday", "wednesday", "thursday"]
    periods_per_day: int = 7


class ScheduleResponse(BaseModel):
    id: str
    tenant_id: str
    name: str
    name_en: Optional[str] = None
    academic_year: str
    semester: int
    status: str
    effective_from: Optional[str] = None
    effective_to: Optional[str] = None
    working_days: List[str]
    periods_per_day: int
    created_at: str
    metadata: Optional[dict] = None


class SessionCreate(BaseModel):
    schedule_id: str
    section_id: str
    subject_id: str
    teacher_id: str
    day_of_week: str
    period: int
    classroom_id: Optional[str] = None
    is_recurring: bool = True


class SessionResponse(BaseModel):
    id: str
    schedule_id: str
    tenant_id: str
    section_id: str
    subject_id: str
    teacher_id: str
    day_of_week: str
    period: int
    classroom_id: Optional[str] = None
    status: str
    has_conflicts: bool = False
    created_at: str


class SessionMoveRequest(BaseModel):
    new_day: str
    new_period: int


class TeacherAssignmentCreate(BaseModel):
    teacher_id: str
    subject_id: str
    section_ids: List[str]
    academic_year: str
    periods_per_week: int = 4


class ConflictResponse(BaseModel):
    id: str
    type: str
    description_ar: str
    description_en: str
    session_id: str
    day_of_week: str
    period: int
    is_resolved: bool = False


def create_scheduling_router(db, get_current_user, require_roles, UserRole):
    """Factory function to create scheduling router with dependencies"""
    
    router = APIRouter(prefix="/scheduling", tags=["Scheduling"])
    
    # Initialize engine
    from engines.scheduling_engine import SchedulingEngine
    engine = SchedulingEngine(db)
    
    # ============== TIME SLOTS ==============
    
    @router.post("/time-slots/seed-defaults")
    async def seed_default_time_slots(
        current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL]))
    ):
        """Seed default time slots for tenant"""
        tenant_id = current_user.get("tenant_id") or current_user.get("primary_tenant_id")
        
        if not tenant_id and current_user.get("role") != "platform_admin":
            raise HTTPException(status_code=400, detail="يجب تحديد المدرسة")
        
        # For platform admin, require explicit tenant_id
        if not tenant_id:
            raise HTTPException(status_code=400, detail="يجب تحديد معرف المدرسة")
        
        count = await engine.seed_default_time_slots(tenant_id, current_user["id"])
        
        return {
            "message": f"تم إضافة {count} فترة زمنية",
            "added": count
        }
    
    @router.get("/time-slots", response_model=List[TimeSlotResponse])
    async def get_time_slots(
        slot_type: Optional[str] = None,
        current_user: dict = Depends(get_current_user)
    ):
        """Get time slots for tenant"""
        tenant_id = current_user.get("tenant_id") or current_user.get("primary_tenant_id")
        
        if not tenant_id:
            raise HTTPException(status_code=400, detail="يجب تحديد المدرسة")
        
        slots = await engine.get_time_slots(tenant_id, slot_type)
        return slots
    
    @router.post("/time-slots", response_model=TimeSlotResponse)
    async def create_time_slot(
        data: TimeSlotCreate,
        current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL]))
    ):
        """Create a new time slot"""
        tenant_id = current_user.get("tenant_id") or current_user.get("primary_tenant_id")
        
        if not tenant_id:
            raise HTTPException(status_code=400, detail="يجب تحديد المدرسة")
        
        slot = await engine.create_time_slot(
            tenant_id=tenant_id,
            period=data.period,
            start_time=data.start_time,
            end_time=data.end_time,
            slot_type=data.slot_type,
            created_by=current_user["id"],
            name_ar=data.name_ar,
            name_en=data.name_en
        )
        
        return slot
    
    # ============== SCHEDULES ==============
    
    @router.post("/schedules", response_model=ScheduleResponse)
    async def create_schedule(
        data: ScheduleCreate,
        current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL]))
    ):
        """Create a new master schedule"""
        tenant_id = current_user.get("tenant_id") or current_user.get("primary_tenant_id")
        
        if not tenant_id:
            raise HTTPException(status_code=400, detail="يجب تحديد المدرسة")
        
        schedule = await engine.create_schedule(
            tenant_id=tenant_id,
            name=data.name,
            academic_year=data.academic_year,
            semester=data.semester,
            created_by=current_user["id"],
            name_en=data.name_en,
            effective_from=data.effective_from,
            effective_to=data.effective_to,
            working_days=data.working_days,
            periods_per_day=data.periods_per_day
        )
        
        return schedule
    
    @router.get("/schedules", response_model=List[ScheduleResponse])
    async def get_schedules(
        status: Optional[str] = None,
        academic_year: Optional[str] = None,
        current_user: dict = Depends(get_current_user)
    ):
        """Get schedules for tenant"""
        tenant_id = current_user.get("tenant_id") or current_user.get("primary_tenant_id")
        
        if not tenant_id:
            raise HTTPException(status_code=400, detail="يجب تحديد المدرسة")
        
        schedules = await engine.get_schedules(tenant_id, status, academic_year)
        return schedules
    
    @router.get("/schedules/{schedule_id}", response_model=ScheduleResponse)
    async def get_schedule(
        schedule_id: str,
        current_user: dict = Depends(get_current_user)
    ):
        """Get schedule by ID"""
        schedule = await engine.get_schedule_by_id(schedule_id)
        
        if not schedule:
            raise HTTPException(status_code=404, detail="الجدول غير موجود")
        
        return schedule
    
    @router.put("/schedules/{schedule_id}/publish")
    async def publish_schedule(
        schedule_id: str,
        current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL]))
    ):
        """Publish a schedule"""
        try:
            schedule = await engine.publish_schedule(schedule_id, current_user["id"])
            return {"message": "تم نشر الجدول بنجاح", "schedule": schedule}
        except ValueError as e:
            raise HTTPException(status_code=400, detail="خطأ في صيغة البيانات المرسلة")
    
    @router.delete("/schedules/{schedule_id}")
    async def delete_schedule(
        schedule_id: str,
        current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL]))
    ):
        """Delete a schedule"""
        success = await engine.delete_schedule(schedule_id, current_user["id"])
        
        if not success:
            raise HTTPException(status_code=404, detail="الجدول غير موجود")
        
        return {"message": "تم حذف الجدول بنجاح"}
    
    # ============== SESSIONS ==============
    
    @router.post("/sessions", response_model=SessionResponse)
    async def create_session(
        data: SessionCreate,
        current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL]))
    ):
        """Create a new schedule session"""
        try:
            session = await engine.create_session(
                schedule_id=data.schedule_id,
                section_id=data.section_id,
                subject_id=data.subject_id,
                teacher_id=data.teacher_id,
                day_of_week=data.day_of_week,
                period=data.period,
                created_by=current_user["id"],
                classroom_id=data.classroom_id,
                is_recurring=data.is_recurring
            )
            return session
        except ValueError as e:
            raise HTTPException(status_code=400, detail="خطأ في بيانات الحصة — تأكد من عدم وجود تعارض")
    
    @router.get("/sessions", response_model=List[SessionResponse])
    async def get_sessions(
        schedule_id: str,
        section_id: Optional[str] = None,
        teacher_id: Optional[str] = None,
        day_of_week: Optional[str] = None,
        current_user: dict = Depends(get_current_user)
    ):
        """Get sessions for a schedule"""
        sessions = await engine.get_sessions(
            schedule_id=schedule_id,
            section_id=section_id,
            teacher_id=teacher_id,
            day_of_week=day_of_week
        )
        return sessions
    
    @router.put("/sessions/{session_id}/move")
    async def move_session(
        session_id: str,
        data: SessionMoveRequest,
        current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL]))
    ):
        """Move a session to a new time slot"""
        session = await engine.move_session(
            session_id=session_id,
            new_day=data.new_day,
            new_period=data.new_period,
            moved_by=current_user["id"]
        )
        
        if not session:
            raise HTTPException(status_code=404, detail="الحصة غير موجودة")
        
        return {"message": "تم نقل الحصة بنجاح", "session": session}
    
    @router.delete("/sessions/{session_id}")
    async def delete_session(
        session_id: str,
        current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL]))
    ):
        """Delete a session"""
        success = await engine.delete_session(session_id, current_user["id"])
        
        if not success:
            raise HTTPException(status_code=404, detail="الحصة غير موجودة")
        
        return {"message": "تم حذف الحصة بنجاح"}
    
    # ============== CONFLICTS ==============
    
    @router.get("/schedules/{schedule_id}/conflicts", response_model=List[ConflictResponse])
    async def get_schedule_conflicts(
        schedule_id: str,
        current_user: dict = Depends(get_current_user)
    ):
        """Get conflicts for a schedule"""
        conflicts = await engine.get_schedule_conflicts(schedule_id)
        return conflicts
    
    @router.post("/conflicts/{conflict_id}/resolve")
    async def resolve_conflict(
        conflict_id: str,
        resolution_note: Optional[str] = None,
        current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL]))
    ):
        """Mark a conflict as resolved"""
        success = await engine.resolve_conflict(
            conflict_id=conflict_id,
            resolved_by=current_user["id"],
            resolution_note=resolution_note
        )
        
        if not success:
            raise HTTPException(status_code=404, detail="التعارض غير موجود")
        
        return {"message": "تم حل التعارض"}
    
    # ============== TEACHER SCHEDULES ==============
    
    @router.get("/teacher/{teacher_id}/weekly")
    async def get_teacher_weekly_schedule(
        teacher_id: str,
        schedule_id: Optional[str] = None,
        current_user: dict = Depends(get_current_user)
    ):
        """Get teacher's weekly schedule"""
        tenant_id = current_user.get("tenant_id") or current_user.get("primary_tenant_id")
        
        weekly = await engine.get_teacher_weekly_schedule(
            tenant_id=tenant_id,
            teacher_id=teacher_id,
            schedule_id=schedule_id
        )
        
        return {"teacher_id": teacher_id, "weekly_schedule": weekly}
    
    @router.get("/section/{section_id}/weekly")
    async def get_section_weekly_schedule(
        section_id: str,
        schedule_id: Optional[str] = None,
        current_user: dict = Depends(get_current_user)
    ):
        """Get section's weekly schedule"""
        tenant_id = current_user.get("tenant_id") or current_user.get("primary_tenant_id")
        
        weekly = await engine.get_section_weekly_schedule(
            tenant_id=tenant_id,
            section_id=section_id,
            schedule_id=schedule_id
        )
        
        return {"section_id": section_id, "weekly_schedule": weekly}
    
    # ============== STATISTICS ==============
    
    @router.get("/schedules/{schedule_id}/stats")
    async def get_schedule_statistics(
        schedule_id: str,
        current_user: dict = Depends(get_current_user)
    ):
        """Get statistics for a schedule"""
        stats = await engine.get_schedule_statistics(schedule_id)
        return stats
    
    # ============== TEACHER ASSIGNMENTS ==============
    
    @router.post("/teacher-assignments")
    async def assign_teacher_to_subject(
        data: TeacherAssignmentCreate,
        current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL]))
    ):
        """Assign teacher to teach a subject"""
        tenant_id = current_user.get("tenant_id") or current_user.get("primary_tenant_id")
        
        if not tenant_id:
            raise HTTPException(status_code=400, detail="يجب تحديد المدرسة")
        
        assignment = await engine.assign_teacher_to_subject(
            tenant_id=tenant_id,
            teacher_id=data.teacher_id,
            subject_id=data.subject_id,
            section_ids=data.section_ids,
            academic_year=data.academic_year,
            assigned_by=current_user["id"],
            periods_per_week=data.periods_per_week
        )
        
        return {"message": "تم تعيين المعلم بنجاح", "assignment": assignment}
    
    @router.get("/teacher-assignments")
    async def get_teacher_assignments(
        teacher_id: Optional[str] = None,
        subject_id: Optional[str] = None,
        academic_year: Optional[str] = None,
        current_user: dict = Depends(get_current_user)
    ):
        """Get teacher assignments"""
        tenant_id = current_user.get("tenant_id") or current_user.get("primary_tenant_id")
        
        if not tenant_id:
            raise HTTPException(status_code=400, detail="يجب تحديد المدرسة")
        
        assignments = await engine.get_teacher_assignments(
            tenant_id=tenant_id,
            teacher_id=teacher_id,
            subject_id=subject_id,
            academic_year=academic_year
        )
        
        return {"assignments": assignments, "total": len(assignments)}
    
    return router


# Export
__all__ = ["create_scheduling_router"]
