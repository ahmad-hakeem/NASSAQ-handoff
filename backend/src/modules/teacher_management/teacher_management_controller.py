"""
TeacherManagement Controller
= NestJS @Controller()

HTTP endpoints for TeacherManagement.
During Phase 4 migration: delegates to existing route files.
Target: inline all endpoints directly here.
"""
from fastapi import APIRouter

router = APIRouter(tags=["TeacherManagement"])

# ── Route delegation (Phase 4 migration — replace with inline endpoints) ────
    from src.modules.teacher_management.controllers.teacher_management_routes import router as _teacher_management_routes_router
    router.include_router(_teacher_management_routes_router)
    from src.modules.teacher_management.controllers.teacher_registration_routes import router as _teacher_registration_routes_router
    router.include_router(_teacher_registration_routes_router)
    from src.modules.teacher_management.controllers.principal_management_routes import router as _principal_management_routes_router
    router.include_router(_principal_management_routes_router)
