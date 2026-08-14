"""
StudentManagement Controller
= NestJS @Controller()

HTTP endpoints for StudentManagement.
During Phase 4 migration: delegates to existing route files.
Target: inline all endpoints directly here.
"""
from fastapi import APIRouter

router = APIRouter(tags=["StudentManagement"])

# ── Route delegation (Phase 4 migration — replace with inline endpoints) ────
    from src.modules.student_management.controllers.student_creation_routes import router as _student_creation_routes_router
    router.include_router(_student_creation_routes_router)
    from src.modules.student_management.controllers.student_management_routes import router as _student_management_routes_router
    router.include_router(_student_management_routes_router)
    from src.modules.portals.controllers.student_portal_routes import router as _student_portal_routes_router
    router.include_router(_student_portal_routes_router)
