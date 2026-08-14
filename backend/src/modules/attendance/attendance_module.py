"""
Attendance Module
= NestJS @Module()

Wires together Attendance controllers, services, and repository.
Register by calling register(api_router).
"""
import logging
from fastapi import APIRouter

logger = logging.getLogger("nassaq")


def register(api_router: APIRouter) -> None:
    """Register Attendance routes into api_router."""
    from src.modules.attendance.attendance_controller import router
    api_router.include_router(router)
    logger.info("AttendanceModule: registered")
