"""
Class Management Routes - مسارات إدارة الفصول
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional, List
from pydantic import BaseModel, Field
from enum import Enum
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/classes", tags=["Classes"])

class ClassType(str, Enum):
    regular = "regular"
    advanced = "advanced"
    special_needs = "special_needs"

class CreateClassRequest(BaseModel):
    name_ar: str = Field(..., min_length=1)
    name_en: Optional[str] = None
    grade_id: str
    class_type: ClassType = ClassType.regular
    capacity: int = Field(default=30, ge=1, le=50)
    homeroom_teacher_id: Optional[str] = None
    room_number: Optional[str] = None
    floor: Optional[int] = None
    building: Optional[str] = None
    student_ids: Optional[List[str]] = None
    notes: Optional[str] = None

def get_class_engine(db):
    from engines.class_management_engine import ClassManagementEngine
    return ClassManagementEngine(db)

def create_class_management_routes(db, get_current_user):
    engine = get_class_engine(db)
    
    @router.post("/create")
    async def create_class(
        request: CreateClassRequest,
        current_user: dict = Depends(get_current_user)
    ):
        tenant_id = current_user.get("tenant_id")
        if not tenant_id:
            raise HTTPException(status_code=400, detail="Tenant ID required")
        
        allowed_roles = ["platform_admin", "school_principal", "school_sub_admin"]
        if current_user.get("role") not in allowed_roles:
            raise HTTPException(status_code=403, detail="Permission denied")
        
        from engines.class_management_engine import CreateClassRequest as EngineRequest, ClassType as EngineClassType
        
        engine_request = EngineRequest(
            name_ar=request.name_ar,
            name_en=request.name_en,
            grade_id=request.grade_id,
            class_type=EngineClassType(request.class_type.value),
            capacity=request.capacity,
            homeroom_teacher_id=request.homeroom_teacher_id,
            room_number=request.room_number,
            floor=request.floor,
            building=request.building,
            student_ids=request.student_ids,
            notes=request.notes,
        )
        
        result = await engine.create_class(
            engine_request,
            tenant_id,
            str(current_user.get("_id", current_user.get("id", "system")))
        )
        
        if not result.get("success"):
            raise HTTPException(status_code=400, detail=result.get("error"))
        return result
    
    @router.get("/")
    async def list_classes(
        grade_id: Optional[str] = Query(None),
        search: Optional[str] = Query(None),
        skip: int = Query(0, ge=0),
        limit: int = Query(50, ge=1, le=100),
        current_user: dict = Depends(get_current_user)
    ):
        tenant_id = current_user.get("tenant_id")
        if not tenant_id:
            raise HTTPException(status_code=400, detail="Tenant ID required")
        return await engine.list_classes(tenant_id, grade_id, search, skip, limit)
    
    @router.get("/{class_id}")
    async def get_class(class_id: str, current_user: dict = Depends(get_current_user)):
        tenant_id = current_user.get("tenant_id")
        if not tenant_id:
            raise HTTPException(status_code=400, detail="Tenant ID required")
        result = await engine.get_class(class_id, tenant_id)
        if not result:
            raise HTTPException(status_code=404, detail="Class not found")
        return result
    
    return router
