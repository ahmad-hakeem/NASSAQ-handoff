"""
Student_management Module
= NestJS @Module()

Wires together student_management controllers, services, and repository.
Register by calling register(api_router).
"""
import logging
from fastapi import APIRouter

logger = logging.getLogger("nassaq")


def register(api_router: APIRouter) -> None:
    """Register student_management routes into api_router."""
    from src.modules.student_management.controllers.student_management_routes import router as _student_management_routes_router
    api_router.include_router(_student_management_routes_router)
    from src.modules.student_management.controllers.student_creation_routes import router as _student_creation_routes_router
    api_router.include_router(_student_creation_routes_router)
    logger.info("Student_managementModule: registered")
