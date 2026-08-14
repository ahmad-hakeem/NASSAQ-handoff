"""
NASSAQ — Root App Module
= NestJS AppModule

Registers all feature modules into the api_router.
This is the single source of truth for route registration.

Usage (in app/routes.py or main.py):
    from src.app_module import register_all_modules
    register_all_modules(app, api_router)
"""
import logging
from fastapi import FastAPI, APIRouter

logger = logging.getLogger("nassaq")


def register_all_modules(app: FastAPI, api_router: APIRouter) -> None:
    """
    Register all feature modules — replaces the old register_routes() function.
    Modules are in dependency order (infrastructure first, features last).
    """

    # ── Infrastructure ────────────────────────────────────────────────────────
    from src.modules.infrastructure.infrastructure_module import register as infra_register
    infra_register(app, api_router)

    # ── Auth & Security ───────────────────────────────────────────────────────
    from src.modules.auth.auth_module import register as auth_register
    auth_register(api_router)

    from src.modules.mfa.mfa_module import register as mfa_register
    mfa_register(api_router)

    # ── Users & Schools ───────────────────────────────────────────────────────
    from src.modules.users.users_module import register as users_register
    users_register(api_router)

    from src.modules.schools.schools_module import register as schools_register
    schools_register(api_router)

    from src.modules.registration.registration_module import register as registration_register
    registration_register(api_router)

    # ── Academics ─────────────────────────────────────────────────────────────
    from src.modules.academics.academics_module import register as academics_register
    academics_register(api_router)

    from src.modules.student_management.student_management_module import register as student_mgmt_register
    student_mgmt_register(api_router)

    from src.modules.teacher_management.teacher_management_module import register as teacher_mgmt_register
    teacher_mgmt_register(api_router)

    # ── Scheduling & Timetable ────────────────────────────────────────────────
    from src.modules.scheduling.scheduling_module import register as scheduling_register
    scheduling_register(api_router)

    # ── Session & Classroom ───────────────────────────────────────────────────
    from src.modules.sessions.sessions_module import register as sessions_register
    sessions_register(api_router)

    from src.modules.attendance.attendance_module import register as attendance_register
    attendance_register(api_router)

    from src.modules.assessment.assessment_module import register as assessment_register
    assessment_register(api_router)

    from src.modules.behaviour.behaviour_module import register as behaviour_register
    behaviour_register(api_router)

    from src.modules.participation.participation_module import register as participation_register
    participation_register(api_router)

    # ── Communication & Notifications ─────────────────────────────────────────
    from src.modules.communication.communication_module import register as communication_register
    communication_register(api_router)

    from src.modules.notifications.notifications_module import register as notifications_register
    notifications_register(api_router)

    from src.modules.calendar.calendar_module import register as calendar_register
    calendar_register(api_router)

    from src.modules.events.events_module import register as events_register
    events_register(api_router)

    # ── AI & Analytics ────────────────────────────────────────────────────────
    from src.modules.ai.ai_module import register as ai_register
    ai_register(api_router)

    # ── Reporting & Portfolio ─────────────────────────────────────────────────
    from src.modules.reporting.reporting_module import register as reporting_register
    reporting_register(api_router)

    from src.modules.portfolio.portfolio_module import register as portfolio_register
    portfolio_register(api_router)

    # ── Dashboards & Portals ──────────────────────────────────────────────────
    from src.modules.portals.portals_module import register as portals_register
    portals_register(api_router)

    # ── Independent Teacher Workspace ─────────────────────────────────────────
    from src.modules.independent_teacher.independent_teacher_module import register as it_register
    it_register(api_router)

    # ── Platform Admin ────────────────────────────────────────────────────────
    from src.modules.platform.platform_module import register as platform_register
    platform_register(api_router)

    # ── Data Import/Export ────────────────────────────────────────────────────
    from src.modules.noor_import.noor_import_module import register as noor_register
    noor_register(api_router)

    from src.modules.bulk_import.bulk_import_module import register as bulk_register
    bulk_register(api_router)

    # ── Audit & Security ──────────────────────────────────────────────────────
    from src.modules.audit.audit_module import register as audit_register
    audit_register(api_router)

    from src.modules.consent_privacy.consent_privacy_module import register as consent_register
    consent_register(api_router)

    # ── Search & Discovery ────────────────────────────────────────────────────
    from src.modules.search_directory.search_directory_module import register as search_register
    search_register(api_router)

    from src.modules.relationships.relationships_module import register as relationships_register
    relationships_register(api_router)

    from src.modules.activities.activities_module import register as activities_register
    activities_register(api_router)

    logger.info("AppModule: all modules registered")
