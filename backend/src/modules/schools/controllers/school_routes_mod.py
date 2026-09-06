"""
NASSAQ Route Module: School CRUD, Dashboard, and Platform Public Metrics
Controller layer delegating business logic to SchoolCrudService and SchoolDashboardService.
"""
from fastapi import APIRouter, HTTPException, Depends, Request
from typing import List, Optional, Union

from dependencies import (
    db, get_current_user, require_roles, UserRole, SchoolStatus,
    require_recent_mfa,
)
from src.modules.schools.dto.school_dto import (
    SchoolCreate, SchoolResponse, SchoolPaginatedResponse, SchoolStatusChangeRequest, SchoolCredentialsRequest,
)
from src.modules.schools.services.school_crud_service import (
    SchoolCrudService,
    normalize_school as _normalize_school,
    active_principal_counts_by_tenant as _active_principal_counts_by_tenant,
    live_entity_counts_by_tenant as _live_entity_counts_by_tenant,
)
from src.modules.schools.services.school_dashboard_service import (
    SchoolDashboardService,
    bucket_display as _bucket_display,
)

router = APIRouter()


# ============== SCHOOLS (TENANTS) ROUTES ==============

@router.post("/schools", response_model=SchoolResponse)
async def create_school(
    school_data: SchoolCreate,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))
):
    return await SchoolCrudService.create_school(db.session, school_data, current_user)


@router.post("/schools/draft", response_model=SchoolResponse)
async def create_school_draft(
    school_data: SchoolCreate,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))
):
    """Create a school as draft (setup status) - does not create principal account"""
    return await SchoolCrudService.create_school_draft(db.session, school_data, current_user)


@router.delete("/schools/{school_id}/draft")
async def delete_school_draft(
    school_id: str,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))
):
    """Delete a school draft (only if status is 'setup')"""
    return await SchoolCrudService.delete_school_draft(db.session, school_id, current_user)


@router.put("/schools/{school_id}/draft", response_model=SchoolResponse)
async def update_school_draft(
    school_id: str,
    school_data: SchoolCreate,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))
):
    """Update a school draft (status stays setup)"""
    return await SchoolCrudService.update_school_draft(db.session, school_id, school_data, current_user)


@router.post("/schools/{school_id}/finalize-draft")
async def finalize_school_draft(
    school_id: str,
    school_data: SchoolCreate,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))
):
    """Finalize a school draft to active status and create principal credentials"""
    return await SchoolCrudService.finalize_school_draft(db.session, school_id, school_data, current_user)


@router.get("/schools", response_model=Union[SchoolPaginatedResponse, List[SchoolResponse]])
async def get_schools(
    page: Optional[int] = None,
    limit: Optional[int] = None,
    status: Optional[str] = None,
    search: Optional[str] = None,
    city: Optional[str] = None,
    school_type: Optional[str] = None,
    stage: Optional[str] = None,
    sort_by: Optional[str] = None,
    paginate: Optional[bool] = None,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.MINISTRY_REP, UserRole.PLATFORM_SUB_ADMIN]))
):
    """List schools. If page, limit, or paginate=True is specified, returns paginated response; otherwise returns full list."""
    if paginate is True or page is not None or limit is not None:
        p = page or 1
        l = limit or 10
        return await SchoolCrudService.get_schools_paginated(
            db.session,
            page=p,
            limit=l,
            status=status,
            search=search,
            city=city,
            school_type=school_type,
            stage=stage,
            sort_by=sort_by,
        )
    return await SchoolCrudService.get_schools_list(db.session, status=status)


@router.get("/schools/numbers")
@router.get("/schools/stats")
async def get_schools_numbers(
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.PLATFORM_OPERATIONS_MANAGER, UserRole.PLATFORM_SUB_ADMIN, UserRole.MINISTRY_REP]))
):
    """Get aggregated numbers and platform metrics for the schools module."""
    return await SchoolCrudService.get_schools_numbers(db.session)


@router.get("/schools/draft", response_model=List[SchoolResponse])
@router.get("/schools/drafts", response_model=List[SchoolResponse])
async def get_school_drafts(
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.MINISTRY_REP, UserRole.PLATFORM_SUB_ADMIN]))
):
    """Get all draft schools (setup status) in the schools module."""
    return await SchoolCrudService.get_draft_schools(db.session)


@router.get("/schools/{school_id}", response_model=SchoolResponse)
async def get_school(school_id: str, current_user: dict = Depends(get_current_user)):
    return await SchoolCrudService.get_school_by_id(db.session, school_id, current_user)


@router.put("/schools/{school_id}/status")
async def update_school_status(
    school_id: str,
    status: SchoolStatus,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))
):
    return await SchoolCrudService.update_status(db.session, school_id, status)


@router.post("/schools/{school_id}/suspend")
async def suspend_school(
    school_id: str,
    body: Optional[SchoolStatusChangeRequest] = None,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.PLATFORM_OPERATIONS_MANAGER])),
):
    """Suspend a school with reason - logs full audit trail"""
    req_body = body or SchoolStatusChangeRequest()
    return await SchoolCrudService.suspend_school(db.session, school_id, req_body, current_user)


@router.post("/schools/{school_id}/activate")
async def activate_school(
    school_id: str,
    body: Optional[SchoolStatusChangeRequest] = None,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.PLATFORM_OPERATIONS_MANAGER])),
):
    """Activate a suspended school with reason - logs full audit trail"""
    req_body = body or SchoolStatusChangeRequest(reason="إعادة تفعيل المدرسة")
    return await SchoolCrudService.activate_school(db.session, school_id, req_body, current_user)


@router.get("/schools/{school_id}/detail")
async def get_school_detail(
    school_id: str,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))
):
    """Get comprehensive school detail for Platform Admin"""
    return await SchoolCrudService.get_school_detail(db.session, school_id, current_user)


@router.post("/schools/{school_id}/credentials")
async def manage_school_credentials(
    school_id: str,
    body: SchoolCredentialsRequest,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN])),
    _mfa: dict = Depends(require_recent_mfa()),
):
    """Create or update the school principal account credentials (email + password)"""
    return await SchoolCrudService.manage_school_credentials(db.session, school_id, body, current_user)


@router.patch("/schools/{school_id}")
async def patch_school(
    school_id: str,
    data: dict,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN]))
):
    """Patch school fields (status, ai_enabled, etc.)"""
    return await SchoolCrudService.patch_school(db.session, school_id, data, current_user)


@router.put("/schools/{school_id}")
async def update_school(
    school_id: str,
    data: dict,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN]))
):
    """Update school information"""
    return await SchoolCrudService.update_school(db.session, school_id, data, current_user)


# ============== SCHOOL DASHBOARD API ==============

@router.get("/school/dashboard")
async def get_school_dashboard(
    current_user: dict = Depends(get_current_user)
):
    """Get comprehensive dashboard data for the school principal - LIVE DATA"""
    return await SchoolDashboardService.get_school_dashboard_data(db.session, current_user)


# ============== PUBLIC LANDING METRICS ==============

@router.get("/public/schools-count")
async def get_public_schools_count():
    return await SchoolDashboardService.get_public_schools_count(db.session)


@router.get("/public/growth-indicators")
async def get_public_growth_indicators():
    return await SchoolDashboardService.get_public_growth_indicators(db.session)


@router.get("/public/stats")
async def get_public_stats(current_user: dict = Depends(get_current_user)):
    return await SchoolDashboardService.get_public_stats(db.session, current_user)
