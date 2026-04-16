"""
Class Management Routes - مسارات إدارة الفصول
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional, List
from pydantic import BaseModel, Field
from enum import Enum
from datetime import datetime, timezone
import logging

from sqlalchemy import select
from pg_models import School

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/classes", tags=["Classes"])


INDEPENDENT_TEACHER_ROLES = {"independent_teacher"}


async def _resolve_tenant_id(db, current_user: dict) -> Optional[str]:
    """
    Resolve a tenant (school) id for the current user.
    For independent teachers (no school affiliation), lazily create a
    personal workspace "school" tied to their user id and return its id.
    """
    tenant_id = current_user.get("tenant_id") or current_user.get("school_id")
    if tenant_id:
        return tenant_id

    role = current_user.get("role")
    account_type = current_user.get("account_type") or (current_user.get("data") or {}).get("account_type")
    is_independent = (
        role in INDEPENDENT_TEACHER_ROLES
        or account_type == "independent_teacher"
    )
    if not is_independent:
        return None

    user_id = current_user.get("id") or current_user.get("_id")
    if not user_id:
        return None

    workspace_id = f"itw_{user_id}"
    session = db.session
    existing = (await session.execute(select(School).where(School.id == workspace_id))).scalars().first()
    if existing:
        return workspace_id

    now = datetime.now(timezone.utc)
    full_name = current_user.get("full_name") or current_user.get("email") or "Independent Teacher"
    workspace_name = f"مساحة {full_name}"
    workspace = School(
        id=workspace_id,
        name=workspace_name,
        name_en=f"Workspace - {full_name}",
        code=workspace_id,
        status="active",
        school_type="independent_teacher_workspace",
        tenant_type="independent_teacher_workspace",
        created_by=str(user_id),
        created_at=now,
        updated_at=now,
    )
    session.add(workspace)
    try:
        await session.flush()
    except Exception as e:
        logger.error(f"Failed to create personal workspace for {user_id}: {e}")
        await session.rollback()
        return None
    return workspace_id

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
        allowed_roles = ["platform_admin", "school_principal", "school_sub_admin", "teacher", "independent_teacher", "school_admin"]
        if current_user.get("role") not in allowed_roles:
            raise HTTPException(status_code=403, detail="Permission denied")

        tenant_id = await _resolve_tenant_id(db, current_user)
        if not tenant_id:
            raise HTTPException(status_code=400, detail="Tenant ID required")
        
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
        tenant_id = await _resolve_tenant_id(db, current_user)
        if not tenant_id:
            raise HTTPException(status_code=400, detail="Tenant ID required")
        return await engine.list_classes(tenant_id, grade_id, search, skip, limit)
    
    @router.get("/{class_id}")
    async def get_class(class_id: str, current_user: dict = Depends(get_current_user)):
        tenant_id = await _resolve_tenant_id(db, current_user)
        if not tenant_id:
            raise HTTPException(status_code=400, detail="Tenant ID required")
        result = await engine.get_class(class_id, tenant_id)
        if not result:
            raise HTTPException(status_code=404, detail="Class not found")
        return result
    
    return router
