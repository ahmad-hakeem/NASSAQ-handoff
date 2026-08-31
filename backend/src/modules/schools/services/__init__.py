"""
Schools Module Services
"""
from src.modules.schools.services.school_crud_service import (
    SchoolCrudService,
    normalize_school,
    active_principal_counts_by_tenant,
    live_entity_counts_by_tenant,
)
from src.modules.schools.services.school_dashboard_service import (
    SchoolDashboardService,
    bucket_display,
)
from src.modules.schools.services.school_settings_service import (
    SchoolSettingsService,
    normalize_school_settings_doc,
    dict_to_active_ar,
    dict_to_inactive_ar,
    resolve_working_days_ar,
    resolve_weekend_days_ar,
    resolve_school_context,
)
from src.modules.schools.services.time_slots_service import (
    TimeSlotsService,
    arabic_ordinal,
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
from src.modules.schools.services.system_settings_service import (
    SystemSettingsService,
    jti_from_creds,
    revoke_session_refresh_chain,
    format_session,
)

__all__ = [
    "SchoolCrudService",
    "normalize_school",
    "active_principal_counts_by_tenant",
    "live_entity_counts_by_tenant",
    "SchoolDashboardService",
    "bucket_display",
    "SchoolSettingsService",
    "normalize_school_settings_doc",
    "dict_to_active_ar",
    "dict_to_inactive_ar",
    "resolve_working_days_ar",
    "resolve_weekend_days_ar",
    "resolve_school_context",
    "TimeSlotsService",
    "arabic_ordinal",
    "ConstraintsService",
    "RANK_TOTAL_PERIODS",
    "TeacherUnavailabilityService",
    "TeacherAssignmentsService",
    "SystemSettingsService",
    "jti_from_creds",
    "revoke_session_refresh_chain",
    "format_session",
]
