"""
TeacherManagement Module
= NestJS @Module()

Wires together TeacherManagement controllers, services, and repository.
Register by calling register(api_router).
"""
import logging
from fastapi import APIRouter

logger = logging.getLogger("nassaq")


def register(api_router: APIRouter) -> None:
    """Register TeacherManagement routes into api_router."""
    from src.modules.teacher_management.teacher_management_controller import router
    api_router.include_router(router)
    logger.info("TeacherManagementModule: registered")
