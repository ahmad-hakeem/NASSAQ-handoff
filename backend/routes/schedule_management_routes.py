"""
Schedule Management Routes - مسارات إدارة الجداول
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional, List
from pydantic import BaseModel, Field
from enum import Enum
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/schedules", tags=["Schedules"])

class DayOfWeek(str, Enum):
    sunday = "sunday"
    monday = "monday"
    tuesday = "tuesday"
    wednesday = "wednesday"
    thursday = "thursday"

class PeriodSlotRequest(BaseModel):
    period_number: int = Field(ge=1, le=10)
    subject_id: str
    teacher_id: str
    class_id: str
    start_time: str
    end_time: str

class DayScheduleRequest(BaseModel):
    day: DayOfWeek
    periods: List[PeriodSlotRequest]

class CreateScheduleRequest(BaseModel):
    name_ar: str = Field(..., min_length=1)
    name_en: Optional[str] = None
    grade_id: str
    class_id: str
    academic_year: str = "2025-2026"
    semester: int = Field(default=1, ge=1, le=2)
    days: List[DayScheduleRequest]
    effective_from: Optional[str] = None
    effective_to: Optional[str] = None

def get_schedule_engine(db):
    from engines.schedule_management_engine import ScheduleManagementEngine
    return ScheduleManagementEngine(db)

def create_schedule_management_routes(db, get_current_user):
    engine = get_schedule_engine(db)
    
    # ==================== Options ====================
    
    @router.get("/options/periods")
    async def get_default_periods():
        return {"periods": await engine.get_default_periods()}
    
    @router.get("/options/days")
    async def get_days():
        return {"days": await engine.get_days()}
    
    @router.get("/options/teachers")
    async def get_teachers(current_user: dict = Depends(get_current_user)):
        tenant_id = current_user.get("tenant_id")
        if not tenant_id:
            raise HTTPException(status_code=400, detail="Tenant ID required")
        return {"teachers": await engine.get_teachers(tenant_id)}
    
    @router.get("/options/subjects")
    async def get_subjects(current_user: dict = Depends(get_current_user)):
        tenant_id = current_user.get("tenant_id")
        if not tenant_id:
            raise HTTPException(status_code=400, detail="Tenant ID required")
        return {"subjects": await engine.get_subjects(tenant_id)}
    
    @router.get("/options/classes")
    async def get_classes(current_user: dict = Depends(get_current_user)):
        tenant_id = current_user.get("tenant_id")
        if not tenant_id:
            raise HTTPException(status_code=400, detail="Tenant ID required")
        return {"classes": await engine.get_classes(tenant_id)}
    
    # ==================== CRUD ====================
    
    @router.post("/create")
    async def create_schedule(
        request: CreateScheduleRequest,
        current_user: dict = Depends(get_current_user)
    ):
        tenant_id = current_user.get("tenant_id")
        if not tenant_id:
            raise HTTPException(status_code=400, detail="Tenant ID required")
        
        allowed_roles = ["platform_admin", "school_principal", "school_sub_admin"]
        if current_user.get("role") not in allowed_roles:
            raise HTTPException(status_code=403, detail="Permission denied")
        
        from engines.schedule_management_engine import (
            CreateScheduleRequest as EngineRequest,
            DaySchedule,
            PeriodSlot,
            DayOfWeek as EngineDayOfWeek
        )
        
        days = []
        for day_req in request.days:
            periods = []
            for period_req in day_req.periods:
                periods.append(PeriodSlot(
                    period_number=period_req.period_number,
                    subject_id=period_req.subject_id,
                    teacher_id=period_req.teacher_id,
                    class_id=period_req.class_id,
                    start_time=period_req.start_time,
                    end_time=period_req.end_time,
                ))
            days.append(DaySchedule(day=EngineDayOfWeek(day_req.day.value), periods=periods))
        
        engine_request = EngineRequest(
            name_ar=request.name_ar,
            name_en=request.name_en,
            grade_id=request.grade_id,
            class_id=request.class_id,
            academic_year=request.academic_year,
            semester=request.semester,
            days=days,
            effective_from=request.effective_from,
            effective_to=request.effective_to,
        )
        
        result = await engine.create_schedule(
            engine_request,
            tenant_id,
            str(current_user.get("id", "system"))
        )
        
        if not result.get("success"):
            raise HTTPException(status_code=400, detail=result.get("error"))
        return result
    
    @router.get("/")
    async def list_schedules(
        class_id: Optional[str] = Query(None),
        grade_id: Optional[str] = Query(None),
        skip: int = Query(0, ge=0),
        limit: int = Query(50, ge=1, le=100),
        current_user: dict = Depends(get_current_user)
    ):
        tenant_id = current_user.get("tenant_id")
        if not tenant_id:
            raise HTTPException(status_code=400, detail="Tenant ID required")
        return await engine.list_schedules(tenant_id, class_id, grade_id, skip, limit)
    
    @router.get("/class/{class_id}")
    async def get_class_schedule(
        class_id: str,
        current_user: dict = Depends(get_current_user)
    ):
        tenant_id = current_user.get("tenant_id")
        if not tenant_id:
            raise HTTPException(status_code=400, detail="Tenant ID required")
        schedule = await engine.get_class_schedule(class_id, tenant_id)
        if not schedule:
            raise HTTPException(status_code=404, detail="Schedule not found")
        return schedule
    
    @router.get("/{schedule_id}")
    async def get_schedule(
        schedule_id: str,
        current_user: dict = Depends(get_current_user)
    ):
        tenant_id = current_user.get("tenant_id")
        if not tenant_id:
            raise HTTPException(status_code=400, detail="Tenant ID required")
        schedule = await engine.get_schedule(schedule_id, tenant_id)
        if not schedule:
            raise HTTPException(status_code=404, detail="Schedule not found")
        return schedule
    
    # ==================== Live Sessions ====================
    
    @router.get("/sessions/current")
    async def get_current_sessions(current_user: dict = Depends(get_current_user)):
        """Get all currently running sessions"""
        tenant_id = current_user.get("tenant_id")
        if not tenant_id:
            raise HTTPException(status_code=400, detail="Tenant ID required")
        sessions = await engine.get_current_sessions(tenant_id)
        return {"sessions": sessions, "count": len(sessions)}
    
    @router.get("/sessions/today")
    async def get_today_schedule(
        class_id: Optional[str] = Query(None),
        current_user: dict = Depends(get_current_user)
    ):
        """Get today's schedule"""
        tenant_id = current_user.get("tenant_id")
        if not tenant_id:
            raise HTTPException(status_code=400, detail="Tenant ID required")
        sessions = await engine.get_today_schedule(tenant_id, class_id)
        return {"sessions": sessions, "count": len(sessions)}
    
    return router
