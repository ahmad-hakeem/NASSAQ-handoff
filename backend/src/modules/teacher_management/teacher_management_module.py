"""
Teacher_management Module
= NestJS @Module()

Wires together teacher_management controllers, services, and repository.
Register by calling register(api_router).
"""
import logging
from fastapi import APIRouter

logger = logging.getLogger("nassaq")


def register(api_router: APIRouter) -> None:
    """Register teacher_management routes into api_router."""
    from src.modules.teacher_management.controllers.teacher_registration_routes import router as _teacher_registration_routes_router
    api_router.include_router(_teacher_registration_routes_router)
    from src.modules.teacher_management.controllers.teacher_management_routes import router as _teacher_management_routes_router
    api_router.include_router(_teacher_management_routes_router)
    from src.modules.teacher_management.controllers.principal_management_routes import router as _principal_management_routes_router
    api_router.include_router(_principal_management_routes_router)
    logger.info("Teacher_managementModule: registered")
