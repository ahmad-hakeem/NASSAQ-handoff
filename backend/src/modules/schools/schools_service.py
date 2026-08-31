"""
Schools Service
Central business logic façade for Schools Module.
Aggregates specialized sub-services (CRUD, Dashboard, Settings, TimeSlots, Constraints, Assignments, Unavailability, SystemSettings).
"""
import logging
from src.modules.schools.services.school_crud_service import SchoolCrudService
from src.modules.schools.services.school_dashboard_service import SchoolDashboardService
from src.modules.schools.services.school_settings_service import SchoolSettingsService
from src.modules.schools.services.time_slots_service import TimeSlotsService
from src.modules.schools.services.constraints_service import ConstraintsService
from src.modules.schools.services.teacher_unavailability_service import TeacherUnavailabilityService
from src.modules.schools.services.teacher_assignments_service import TeacherAssignmentsService
from src.modules.schools.services.system_settings_service import SystemSettingsService

logger = logging.getLogger("nassaq")


class SchoolsService:
    """Unified façade service for the Schools domain."""

    crud = SchoolCrudService
    dashboard = SchoolDashboardService
    settings = SchoolSettingsService
    time_slots = TimeSlotsService
    constraints = ConstraintsService
    unavailability = TeacherUnavailabilityService
    assignments = TeacherAssignmentsService
    system_settings = SystemSettingsService
