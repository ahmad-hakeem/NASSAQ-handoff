"""
Class Management Routes - مسارات إدارة الفصول
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional, List
from pydantic import BaseModel, Field
from enum import Enum
import logging

from src.core.guards.tenant_guard import require_request_school_id
from quotas.independent_teacher import enforce_class_quota

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
    # Optional canonical stage token (primary|middle|high or Arabic name).
    # When supplied, the backend enforces stage↔grade consistency.
    stage: Optional[str] = None
    class_type: ClassType = ClassType.regular
    # Nullable legacy metadata; class rosters have no configurable maximum.
    capacity: Optional[int] = None
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

        # Canonical workspace-id resolution (Phase 0 §4.B-1). The lazy
        # materialiser is gone; the IT workspace must be bootstrapped
        # explicitly (Phase 1 §5.1).
        tenant_id = require_request_school_id(current_user)

        # v1 IT workspace quota (Phase 0 §4.B-5).
        await enforce_class_quota(db.session, current_user)

        # Stage/grade hierarchy enforcement (matches student creation).
        # Stage is optional on this surface for back-compat; when sent the
        # backend rejects mismatched grade ids with a safe Arabic message.
        from src.common.utils.stage_grade import validate_stage_grade_pair
        await validate_stage_grade_pair(
            db.session, tenant_id,
            request.stage, request.grade_id,
            require_stage=False,
        )

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
        assigned_only: bool = Query(False),
        current_user: dict = Depends(get_current_user)
    ):
        tenant_id = require_request_school_id(current_user)
        # Task #1089 — the lesson-plan assistant class picker must show a
        # regular school teacher ONLY their own assigned classes (not the
        # whole school). When ``assigned_only`` is requested by a school
        # teacher, narrow to the canonical assignment set. Independent
        # Teachers are intentionally NOT narrowed: they own every class in
        # their workspace, so the IT experience stays byte-for-byte
        # identical. Admin/leadership roles are likewise unaffected.
        allowed_class_ids = None
        if assigned_only:
            from src.core.guards.tenant_guard import is_independent_teacher
            from dependencies import UserRole
            if (
                not is_independent_teacher(current_user)
                and (current_user.get("role") or "").lower() == UserRole.TEACHER.value
            ):
                from src.common.utils.tenant_scope import get_teacher_allowed_class_ids
                teacher_id = current_user.get("teacher_id") or current_user.get("id")
                allowed_class_ids = await get_teacher_allowed_class_ids(db.session, teacher_id)
        return await engine.list_classes(
            tenant_id,
            grade_id=grade_id,
            search=search,
            skip=skip,
            limit=limit,
            allowed_class_ids=allowed_class_ids,
        )

    @router.get("/{class_id}")
    async def get_class(class_id: str, current_user: dict = Depends(get_current_user)):
        tenant_id = require_request_school_id(current_user)
        result = await engine.get_class(class_id, tenant_id)
        if not result:
            raise HTTPException(status_code=404, detail="Class not found")
        return result

    return router
