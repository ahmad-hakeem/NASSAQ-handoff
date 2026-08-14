"""
StudentManagement Module
= NestJS @Module()

Wires together StudentManagement controllers, services, and repository.
Register by calling register(api_router).
"""
import logging
from fastapi import APIRouter

logger = logging.getLogger("nassaq")


def register(api_router: APIRouter) -> None:
    """Register StudentManagement routes into api_router."""
    from src.modules.student_management.student_management_controller import router
    api_router.include_router(router)
    logger.info("StudentManagementModule: registered")
