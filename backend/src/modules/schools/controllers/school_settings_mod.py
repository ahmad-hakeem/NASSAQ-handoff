"""
NASSAQ Route Module: School Settings, Timing, Constraints, Unavailability, and Teacher Assignments.
Clean Controller delegating logic to domain services while preserving all route endpoints and exported symbols.
"""
from fastapi import APIRouter, HTTPException, Depends, Header, Query
from typing import List, Optional, Any, Dict

from dependencies import (
    db, get_current_user, require_roles, UserRole,
)
from src.modules.schools.dto.school_dto import SchoolInfoUpdate
from src.modules.schools.dto.settings_dto import (
    WorkDaysConfig, OfficialHoliday, ExceptionDay, ActivityDay,
    SchoolTiming, BreakPeriod, UpdatePeriodsRequest,
)
from src.modules.schools.dto.constraints_dto import (
    AdminConstraint,
)
from src.modules.schools.dto.assignments_dto import (
    TeacherClassAssignmentCreate, TeacherSubjectAssignmentCreate,
    TeacherClassBulkUnassignTeacher, TeacherClassBulkUnassignAll,
)
from src.modules.schools.dto.unavailability_dto import (
    UnavailabilityCreate,
)
from src.modules.schools.services.school_settings_service import (
    SchoolSettingsService,
    normalize_school_settings_doc,
    resolve_school_context,
)
from src.modules.schools.services.time_slots_service import (
    TimeSlotsService,
)
from src.modules.schools.services.constraints_service import (
    ConstraintsService,
    RANK_TOTAL_PERIODS,
)
from src.modules.schools.services.teacher_unavailability_service import (
    TeacherUnavailabilityService,
)
from src.modules.schools.services.teacher_assignments_service import (
    TeacherAssignmentsService,
)

router = APIRouter()
time_slots_router = APIRouter()


# Legacy & cross-module backward-compatibility aliases
async def get_school_id_from_context(current_user: dict, x_school_context: str = None) -> str:
    return await resolve_school_context(current_user, x_school_context)


async def regenerate_time_slots_from_settings(school_id: str):
    return await TimeSlotsService.regenerate_time_slots(db.session, school_id)


async def _auto_populate_teacher_class_assignments(school_id: str):
    return await TeacherAssignmentsService.auto_populate_teacher_class_assignments(school_id)


async def _ensure_teacher_linked_to_all_classes(school_id: str, teacher_id: str):
    return await TeacherAssignmentsService.ensure_teacher_linked_to_all_classes(school_id, teacher_id)


async def _ensure_class_linked_to_all_teachers(school_id: str, class_id: str):
    return await TeacherAssignmentsService.ensure_class_linked_to_all_teachers(school_id, class_id)


# ============ SCHOOL INFO ROUTES ============

@router.get("/school/info")
async def get_school_info(
    current_user: dict = Depends(get_current_user),
    x_school_context: str = Header(default=None, alias="X-School-Context")
):
    return await SchoolSettingsService.get_school_info(db.session, current_user, x_school_context)


@router.put("/school/info")
async def update_school_info_direct(
    school_info: SchoolInfoUpdate,
    current_user: dict = Depends(require_roles([UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN])),
    x_school_context: str = Header(default=None, alias="X-School-Context")
):
    return await SchoolSettingsService.update_school_info_direct(db.session, school_info, current_user, x_school_context)


# ============ TIME SLOTS & DAY STATUS ============

@time_slots_router.get("/school/day-status")
async def get_school_day_status(
    current_user: dict = Depends(get_current_user),
    x_school_context: str = Header(default=None, alias="X-School-Context")
):
    return await TimeSlotsService.get_school_day_status(db.session, current_user, x_school_context)


@time_slots_router.get("/time-slots")
async def list_time_slots(
    current_user: dict = Depends(get_current_user),
    x_school_context: str = Header(default=None, alias="X-School-Context")
):
    """جلب الحصص والفترات للمدرسة الحالية"""
    return await TimeSlotsService.list_time_slots(db.session, current_user, x_school_context)


@router.post("/school/settings/regenerate-time-slots")
async def regenerate_time_slots_endpoint(
    current_user: dict = Depends(require_roles([UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN])),
    x_school_context: str = Header(default=None, alias="X-School-Context")
):
    school_id = await resolve_school_context(current_user, x_school_context)
    if not school_id:
        raise HTTPException(status_code=400, detail="Missing school context")
    return await TimeSlotsService.regenerate_time_slots(db.session, school_id)


# ============ SCHOOL SETTINGS & AUDIT ============

@router.get("/school/settings")
async def get_school_settings(
    current_user: dict = Depends(get_current_user),
    x_school_context: str = Header(default=None, alias="X-School-Context")
):
    return await SchoolSettingsService.get_school_settings(db.session, current_user, x_school_context)


@router.get("/school/settings/audit-logs")
async def get_school_audit_logs(
    current_user: dict = Depends(require_roles([UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN])),
    x_school_context: str = Header(default=None, alias="X-School-Context")
):
    return await SchoolSettingsService.get_school_audit_logs(db.session, current_user, x_school_context)


@router.put("/school/settings/info")
async def update_school_info(
    info_data: dict,
    current_user: dict = Depends(require_roles([UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN])),
    x_school_context: str = Header(default=None, alias="X-School-Context")
):
    return await SchoolSettingsService.update_school_info(db.session, info_data, current_user, x_school_context)


@router.put("/school/settings/work-days")
async def update_work_days(
    config: WorkDaysConfig,
    expected_version: Optional[int] = Query(default=None, ge=0),
    current_user: dict = Depends(require_roles([UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN])),
    x_school_context: str = Header(default=None, alias="X-School-Context")
):
    payload = {"working_days": config.dict()}
    if expected_version is not None:
        payload["expected_version"] = expected_version
    return await SchoolSettingsService.update_school_settings_full(
        db.session, payload, current_user, x_school_context
    )


@router.post("/school/settings/holidays")
async def add_official_holiday(
    holiday: OfficialHoliday,
    current_user: dict = Depends(require_roles([UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN])),
    x_school_context: str = Header(default=None, alias="X-School-Context")
):
    return await SchoolSettingsService.add_official_holiday(db.session, holiday, current_user, x_school_context)


@router.delete("/school/settings/holidays/{holiday_id}")
async def delete_official_holiday(
    holiday_id: str,
    current_user: dict = Depends(require_roles([UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN])),
    x_school_context: str = Header(default=None, alias="X-School-Context")
):
    return await SchoolSettingsService.delete_official_holiday(db.session, holiday_id, current_user, x_school_context)


@router.post("/school/settings/exception-days")
async def add_exception_day(
    exc: ExceptionDay,
    current_user: dict = Depends(require_roles([UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN])),
    x_school_context: str = Header(default=None, alias="X-School-Context")
):
    return await SchoolSettingsService.add_exception_day(db.session, exc, current_user, x_school_context)


@router.delete("/school/settings/exception-days/{exception_id}")
async def delete_exception_day(
    exception_id: str,
    current_user: dict = Depends(require_roles([UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN])),
    x_school_context: str = Header(default=None, alias="X-School-Context")
):
    return await SchoolSettingsService.delete_exception_day(db.session, exception_id, current_user, x_school_context)


@router.post("/school/settings/activity-days")
async def add_activity_day(
    act: ActivityDay,
    current_user: dict = Depends(require_roles([UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN])),
    x_school_context: str = Header(default=None, alias="X-School-Context")
):
    return await SchoolSettingsService.add_activity_day(db.session, act, current_user, x_school_context)


@router.delete("/school/settings/activity-days/{activity_id}")
async def delete_activity_day(
    activity_id: str,
    current_user: dict = Depends(require_roles([UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN])),
    x_school_context: str = Header(default=None, alias="X-School-Context")
):
    return await SchoolSettingsService.delete_activity_day(db.session, activity_id, current_user, x_school_context)


@router.put("/school/settings/periods-per-day")
async def update_periods_per_day(
    req: UpdatePeriodsRequest,
    expected_version: Optional[int] = Query(default=None, ge=0),
    current_user: dict = Depends(require_roles([UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN])),
    x_school_context: str = Header(default=None, alias="X-School-Context")
):
    payload = {"periods_per_day": req.periods_per_day}
    if expected_version is not None:
        payload["expected_version"] = expected_version
    return await SchoolSettingsService.update_school_settings_full(
        db.session, payload, current_user, x_school_context
    )


@router.put("/school/settings/timing")
async def update_school_timing(
    timing: SchoolTiming,
    expected_version: Optional[int] = Query(default=None, ge=0),
    current_user: dict = Depends(require_roles([UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN])),
    x_school_context: str = Header(default=None, alias="X-School-Context")
):
    payload = {"start_time": timing.start, "end_time": timing.end}
    if expected_version is not None:
        payload["expected_version"] = expected_version
    return await SchoolSettingsService.update_school_settings_full(
        db.session, payload, current_user, x_school_context
    )


@router.put("/school/settings/breaks")
async def update_breaks(
    breaks: List[BreakPeriod],
    expected_version: Optional[int] = Query(default=None, ge=0),
    current_user: dict = Depends(require_roles([UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN])),
    x_school_context: str = Header(default=None, alias="X-School-Context")
):
    payload = {"breaks": [break_period.dict() for break_period in breaks]}
    if expected_version is not None:
        payload["expected_version"] = expected_version
    return await SchoolSettingsService.update_school_settings_full(
        db.session, payload, current_user, x_school_context
    )


@router.put("/school/settings")
async def update_school_settings_full(
    new_settings: dict,
    current_user: dict = Depends(require_roles([UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN])),
    x_school_context: str = Header(default=None, alias="X-School-Context")
):
    return await SchoolSettingsService.update_school_settings_full(db.session, new_settings, current_user, x_school_context)


# ============ TIMETABLE CONSTRAINTS ============

@router.get("/school/settings/hard-constraints")
async def get_hard_constraints(
    current_user: dict = Depends(require_roles([
        UserRole.SCHOOL_ADMIN, UserRole.SCHOOL_SUB_ADMIN, UserRole.SCHOOL_PRINCIPAL,
        UserRole.PLATFORM_ADMIN, UserRole.TEACHER
    ]))
):
    return await ConstraintsService.get_hard_constraints(db.session, current_user)


@router.get("/school/settings/soft-constraints")
async def get_soft_constraints(
    current_user: dict = Depends(require_roles([
        UserRole.SCHOOL_ADMIN, UserRole.SCHOOL_SUB_ADMIN, UserRole.SCHOOL_PRINCIPAL,
        UserRole.PLATFORM_ADMIN, UserRole.TEACHER
    ]))
):
    return await ConstraintsService.get_soft_constraints(db.session, current_user)


@router.put("/school/settings/soft-constraints/{code}")
async def toggle_soft_constraint(
    code: str,
    data: dict,
    current_user: dict = Depends(require_roles([UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN]))
):
    return await ConstraintsService.toggle_soft_constraint(db.session, code, data, current_user)


@router.put("/school/settings/hard-constraints/{code}")
async def toggle_hard_constraint(
    code: str,
    data: dict,
    current_user: dict = Depends(require_roles([UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN]))
):
    return await ConstraintsService.toggle_hard_constraint(db.session, code, data, current_user)


@router.get("/school/settings/custom-soft-constraints")
async def get_custom_soft_constraints(
    current_user: dict = Depends(require_roles([UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN]))
):
    return await ConstraintsService.get_custom_soft_constraints(db.session, current_user)


@router.post("/school/settings/custom-soft-constraints")
async def create_custom_soft_constraint(
    data: dict,
    current_user: dict = Depends(require_roles([UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN]))
):
    return await ConstraintsService.create_custom_soft_constraint(db.session, data, current_user)


@router.put("/school/settings/custom-soft-constraints/{constraint_id}")
async def update_custom_soft_constraint(
    constraint_id: str,
    data: dict,
    current_user: dict = Depends(require_roles([UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN]))
):
    return await ConstraintsService.update_custom_soft_constraint(db.session, constraint_id, data, current_user)


@router.delete("/school/settings/custom-soft-constraints/{constraint_id}")
async def delete_custom_soft_constraint(
    constraint_id: str,
    current_user: dict = Depends(require_roles([UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN]))
):
    return await ConstraintsService.delete_custom_soft_constraint(db.session, constraint_id, current_user)


@router.get("/school/settings/constraint-patterns")
async def get_constraint_patterns(
    current_user: dict = Depends(require_roles([UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN]))
):
    return await ConstraintsService.get_constraint_patterns(db.session, current_user)


@router.post("/school/settings/constraint-patterns")
async def create_constraint_pattern(
    data: dict,
    current_user: dict = Depends(require_roles([UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN]))
):
    return await ConstraintsService.create_constraint_pattern(db.session, data, current_user)


@router.put("/school/settings/constraint-patterns/{pattern_id}")
async def update_constraint_pattern(
    pattern_id: str,
    data: dict,
    current_user: dict = Depends(require_roles([UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN]))
):
    return await ConstraintsService.update_constraint_pattern(db.session, pattern_id, data, current_user)


@router.delete("/school/settings/constraint-patterns/{pattern_id}")
async def delete_constraint_pattern(
    pattern_id: str,
    current_user: dict = Depends(require_roles([UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN]))
):
    return await ConstraintsService.delete_constraint_pattern(db.session, pattern_id, current_user)


@router.get("/school/settings/other-duties")
async def get_other_duties(
    current_user: dict = Depends(require_roles([UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN]))
):
    return await ConstraintsService.get_other_duties(db.session, current_user)


@router.post("/school/settings/other-duties")
async def create_other_duty(
    data: dict,
    current_user: dict = Depends(require_roles([UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN]))
):
    return await ConstraintsService.create_other_duty(db.session, data, current_user)


@router.put("/school/settings/other-duties/{duty_id}")
async def update_other_duty(
    duty_id: str,
    data: dict,
    current_user: dict = Depends(require_roles([UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN]))
):
    return await ConstraintsService.update_other_duty(db.session, duty_id, data, current_user)


@router.delete("/school/settings/other-duties/{duty_id}")
async def delete_other_duty(
    duty_id: str,
    current_user: dict = Depends(require_roles([UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN]))
):
    return await ConstraintsService.delete_other_duty(db.session, duty_id, current_user)


@router.get("/school/settings/workload-summary")
async def get_workload_summary(
    current_user: dict = Depends(require_roles([UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN]))
):
    return await ConstraintsService.get_workload_summary(db.session, current_user)


@router.put("/school/settings/workload-override/{teacher_id}")
async def set_workload_override(
    teacher_id: str,
    data: dict,
    current_user: dict = Depends(require_roles([UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN]))
):
    return await ConstraintsService.set_workload_override(db.session, teacher_id, data, current_user)


@router.put("/school/constraints/{constraint_id}")
async def update_school_constraint(
    constraint_id: str,
    data: dict,
    current_user: dict = Depends(require_roles([UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN])),
    x_school_context: str = Header(default=None, alias="X-School-Context")
):
    return await ConstraintsService.update_school_constraint(db.session, constraint_id, data, current_user, x_school_context)


@router.put("/school/settings/constraints")
async def update_constraints(
    constraints: List[AdminConstraint],
    current_user: dict = Depends(require_roles([UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN])),
    x_school_context: str = Header(default=None, alias="X-School-Context")
):
    school_id = await resolve_school_context(current_user, x_school_context)
    if not school_id:
        raise HTTPException(status_code=400, detail="Missing school context")
    constraints_list = [c.dict() for c in constraints]
    normalized = normalize_school_settings_doc({
        "constraints": constraints_list,
        "updated_at": datetime.now(timezone.utc).isoformat()
    })
    await gd_update_one(db.session, "school_settings", {"school_id": school_id}, normalized)
    return {"success": True, "message": "تم تحديث القيود بنجاح"}


# ============ UNAVAILABILITY & TEACHER AVAILABILITY ============

@router.put("/school/settings/teaching-loads")
async def update_teaching_loads(
    loads: dict,
    current_user: dict = Depends(require_roles([UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN])),
    x_school_context: str = Header(default=None, alias="X-School-Context")
):
    return await TeacherUnavailabilityService.update_teaching_loads(db.session, loads, current_user, x_school_context)


@router.put("/school/settings/teacher-availability")
async def update_teacher_availability(
    availability: dict,
    current_user: dict = Depends(require_roles([UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN])),
    x_school_context: str = Header(default=None, alias="X-School-Context")
):
    return await TeacherUnavailabilityService.update_teacher_availability(db.session, availability, current_user, x_school_context)


@router.post("/school/settings/unavailability")
async def create_unavailability(
    data: UnavailabilityCreate,
    current_user: dict = Depends(require_roles([UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN])),
    x_school_context: str = Header(default=None, alias="X-School-Context")
):
    return await TeacherUnavailabilityService.create_unavailability(db.session, data, current_user, x_school_context)


@router.delete("/school/settings/unavailability/{unavailability_id}")
async def delete_unavailability(
    unavailability_id: str,
    current_user: dict = Depends(require_roles([UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN])),
    x_school_context: str = Header(default=None, alias="X-School-Context")
):
    return await TeacherUnavailabilityService.delete_unavailability(db.session, unavailability_id, current_user, x_school_context)


@router.get("/school/settings/unavailability")
async def get_unavailability(
    entity_type: Optional[str] = None,
    current_user: dict = Depends(require_roles([UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN])),
    x_school_context: str = Header(default=None, alias="X-School-Context")
):
    return await TeacherUnavailabilityService.get_unavailability(db.session, entity_type, current_user, x_school_context)


@router.post("/school/settings/unavailability/{unavailability_id}/acknowledge")
async def acknowledge_unavailability(
    unavailability_id: str,
    current_user: dict = Depends(get_current_user),
    x_school_context: str = Header(default=None, alias="X-School-Context"),
):
    return await TeacherUnavailabilityService.acknowledge_unavailability(db.session, unavailability_id, current_user, x_school_context)


@router.get("/school/settings/unavailability/{unavailability_id}/acknowledgements")
async def list_unavailability_acknowledgements(
    unavailability_id: str,
    current_user: dict = Depends(require_roles([UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN])),
    x_school_context: str = Header(default=None, alias="X-School-Context"),
):
    return await TeacherUnavailabilityService.list_unavailability_acknowledgements(db.session, unavailability_id, current_user, x_school_context)


# ============ TEACHER ASSIGNMENTS ============

@router.get("/teacher-class-assignments")
async def get_teacher_class_assignments(
    current_user: dict = Depends(get_current_user),
    x_school_context: str = Header(default=None, alias="X-School-Context"),
    page: int = Query(1, ge=1),
    page_size: int = Query(200, ge=1, le=50000),
    teacher_id: str = Query(None),
    class_id: str = Query(None),
):
    return await TeacherAssignmentsService.get_teacher_class_assignments(
        db.session, current_user, x_school_context, page, page_size, teacher_id, class_id
    )


@router.post("/teacher-class-assignments")
async def create_teacher_class_assignment(
    assignment: TeacherClassAssignmentCreate,
    current_user: dict = Depends(get_current_user),
    x_school_context: str = Header(default=None, alias="X-School-Context"),
):
    return await TeacherAssignmentsService.create_teacher_class_assignment(
        db.session, assignment, current_user, x_school_context
    )


_ASSIGNMENT_LEADERSHIP_ROLES = [
    UserRole.SCHOOL_PRINCIPAL,
    UserRole.SCHOOL_ADMIN,
    UserRole.SCHOOL_SUB_ADMIN,
    UserRole.PLATFORM_ADMIN,
]


@router.post("/teacher-class-assignments/unassign-teacher")
async def unassign_teacher_class_assignments(
    payload: TeacherClassBulkUnassignTeacher,
    current_user: dict = Depends(require_roles(_ASSIGNMENT_LEADERSHIP_ROLES)),
    x_school_context: str = Header(default=None, alias="X-School-Context"),
):
    return await TeacherAssignmentsService.bulk_unassign_class_assignments(
        db.session, current_user, x_school_context, teacher_id=payload.teacher_id
    )


@router.post("/teacher-class-assignments/unassign-all")
async def unassign_all_teacher_class_assignments(
    payload: TeacherClassBulkUnassignAll,
    current_user: dict = Depends(require_roles(_ASSIGNMENT_LEADERSHIP_ROLES)),
    x_school_context: str = Header(default=None, alias="X-School-Context"),
):
    return await TeacherAssignmentsService.bulk_unassign_class_assignments(
        db.session, current_user, x_school_context
    )


@router.delete("/teacher-class-assignments/{assignment_id}")
async def delete_teacher_class_assignment(
    assignment_id: str,
    current_user: dict = Depends(get_current_user),
    x_school_context: str = Header(default=None, alias="X-School-Context"),
):
    return await TeacherAssignmentsService.delete_teacher_class_assignment(
        db.session, assignment_id, current_user, x_school_context
    )


@router.get("/teacher-class-assignments/classes-without-teachers")
async def get_classes_without_teachers(
    current_user: dict = Depends(get_current_user),
    x_school_context: str = Header(default=None, alias="X-School-Context"),
):
    return await TeacherAssignmentsService.get_classes_without_teachers(
        db.session, current_user, x_school_context
    )


@router.get("/teacher-assignments")
async def get_teacher_subject_assignments(
    teacher_id: Optional[str] = None,
    subject_id: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
    x_school_context: str = Header(default=None, alias="X-School-Context"),
):
    return await TeacherAssignmentsService.get_teacher_subject_assignments(
        db.session, teacher_id, subject_id, current_user, x_school_context
    )


@router.post("/teacher-assignments")
async def create_teacher_subject_assignment(
    payload: TeacherSubjectAssignmentCreate,
    current_user: dict = Depends(get_current_user),
    x_school_context: str = Header(default=None, alias="X-School-Context"),
):
    return await TeacherAssignmentsService.create_teacher_subject_assignment(
        db.session, payload, current_user, x_school_context
    )


@router.delete("/teacher-assignments/{assignment_id}")
async def delete_teacher_subject_assignment(
    assignment_id: str,
    current_user: dict = Depends(get_current_user),
    x_school_context: str = Header(default=None, alias="X-School-Context"),
):
    return await TeacherAssignmentsService.delete_teacher_subject_assignment(
        db.session, assignment_id, current_user, x_school_context
    )


@router.get("/teacher-class-assignments/teacher/{teacher_id}")
async def get_teacher_assignments(
    teacher_id: str,
    current_user: dict = Depends(get_current_user),
    x_school_context: str = Header(default=None, alias="X-School-Context"),
):
    return await TeacherAssignmentsService.get_teacher_assigned_classes(
        db.session, teacher_id, current_user, x_school_context
    )
