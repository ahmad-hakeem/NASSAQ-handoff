"""
Attendance Module
= NestJS @Module()

Wires together attendance controllers, services, and repository.
Register by calling register(api_router).
"""
import logging
from fastapi import APIRouter

logger = logging.getLogger("nassaq")


def register(api_router: APIRouter) -> None:
    """Register attendance routes into api_router."""
    from src.modules.attendance.controllers.attendance_routes import router as _attendance_routes_router
    api_router.include_router(_attendance_routes_router)
    from src.modules.attendance.controllers.teacher_attendance_routes import router as _teacher_attendance_routes_router
    api_router.include_router(_teacher_attendance_routes_router)
    from src.modules.attendance.controllers.attendance_routes_mod import router as _attendance_routes_mod_router
    api_router.include_router(_attendance_routes_mod_router)
    logger.info("AttendanceModule: registered")
