"""
Attendance Controller
= NestJS @Controller()

HTTP endpoints for Attendance.
During Phase 4 migration: delegates to existing route files.
Target: inline all endpoints directly here.
"""
from fastapi import APIRouter

router = APIRouter(tags=["Attendance"])

# ── Route delegation (Phase 4 migration — replace with inline endpoints) ────
    from src.modules.attendance.controllers.attendance_routes_mod import router as _attendance_routes_mod_router
    router.include_router(_attendance_routes_mod_router)
    from src.modules.attendance.controllers.teacher_attendance_routes import router as _teacher_attendance_routes_router
    router.include_router(_teacher_attendance_routes_router)
