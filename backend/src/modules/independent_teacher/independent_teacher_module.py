"""
Independent_teacher Module
= NestJS @Module()

Wires together independent_teacher controllers, services, and repository.
Register by calling register(api_router).
"""
import logging
from fastapi import APIRouter

logger = logging.getLogger("nassaq")


def register(api_router: APIRouter) -> None:
    """Register independent_teacher routes into api_router."""
    from src.modules.independent_teacher.controllers.independent_teacher_bulk_import_routes import router as _independent_teacher_bulk_import_routes_router
    api_router.include_router(_independent_teacher_bulk_import_routes_router)
    from src.modules.independent_teacher.controllers.independent_teacher_schedule_routes import router as _independent_teacher_schedule_routes_router
    api_router.include_router(_independent_teacher_schedule_routes_router)
    from src.modules.independent_teacher.controllers.independent_teacher_notifications_routes import router as _independent_teacher_notifications_routes_router
    api_router.include_router(_independent_teacher_notifications_routes_router)
    from src.modules.independent_teacher.controllers.independent_teacher_workspace_settings_routes import router as _independent_teacher_workspace_settings_routes_router
    api_router.include_router(_independent_teacher_workspace_settings_routes_router)
    from src.modules.independent_teacher.controllers.independent_teacher_lesson_plans_routes import router as _independent_teacher_lesson_plans_routes_router
    api_router.include_router(_independent_teacher_lesson_plans_routes_router)
    from src.modules.independent_teacher.controllers.independent_teacher_onboarding_routes import router as _independent_teacher_onboarding_routes_router
    api_router.include_router(_independent_teacher_onboarding_routes_router)
    from src.modules.independent_teacher.controllers.independent_teacher_workspace_lifecycle_routes import router as _independent_teacher_workspace_lifecycle_routes_router
    api_router.include_router(_independent_teacher_workspace_lifecycle_routes_router)
    from src.modules.independent_teacher.controllers.independent_teacher_communication_routes import router as _independent_teacher_communication_routes_router
    api_router.include_router(_independent_teacher_communication_routes_router)
    from src.modules.independent_teacher.controllers.independent_teacher_workspace_excel_export_routes import router as _independent_teacher_workspace_excel_export_routes_router
    api_router.include_router(_independent_teacher_workspace_excel_export_routes_router)
    from src.modules.independent_teacher.controllers.independent_teacher_analytics_routes import router as _independent_teacher_analytics_routes_router
    api_router.include_router(_independent_teacher_analytics_routes_router)
    from src.modules.independent_teacher.controllers.independent_teacher_audit_routes import router as _independent_teacher_audit_routes_router
    api_router.include_router(_independent_teacher_audit_routes_router)
    from src.modules.independent_teacher.controllers.independent_teacher_search_routes import router as _independent_teacher_search_routes_router
    api_router.include_router(_independent_teacher_search_routes_router)
    from src.modules.independent_teacher.controllers.independent_teacher_parents_routes import router as _independent_teacher_parents_routes_router
    api_router.include_router(_independent_teacher_parents_routes_router)
    from src.modules.independent_teacher.controllers.independent_teacher_calendar_routes import router as _independent_teacher_calendar_routes_router
    api_router.include_router(_independent_teacher_calendar_routes_router)
    from src.modules.independent_teacher.controllers.independent_teacher_collab_routes import router as _independent_teacher_collab_routes_router
    api_router.include_router(_independent_teacher_collab_routes_router)
    from src.modules.independent_teacher.controllers.independent_teacher_bulk_extensions_routes import router as _independent_teacher_bulk_extensions_routes_router
    api_router.include_router(_independent_teacher_bulk_extensions_routes_router)
    from src.modules.independent_teacher.controllers.independent_teacher_invite_parent_routes import router as _independent_teacher_invite_parent_routes_router
    api_router.include_router(_independent_teacher_invite_parent_routes_router)
    from src.modules.independent_teacher.controllers.independent_teacher_bootstrap_routes import router as _independent_teacher_bootstrap_routes_router
    api_router.include_router(_independent_teacher_bootstrap_routes_router)
    from src.modules.independent_teacher.controllers.independent_teacher_reports_routes import router as _independent_teacher_reports_routes_router
    api_router.include_router(_independent_teacher_reports_routes_router)
    from src.modules.independent_teacher.controllers.independent_teacher_invitation_routes import router as _independent_teacher_invitation_routes_router
    api_router.include_router(_independent_teacher_invitation_routes_router)
    logger.info("Independent_teacherModule: registered")
