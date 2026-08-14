"""
Portals Controller
= NestJS @Controller()

HTTP endpoints for Portals.
During Phase 4 migration: delegates to existing route files.
Target: inline all endpoints directly here.
"""
from fastapi import APIRouter

router = APIRouter(tags=["Portals"])

# ── Route delegation (Phase 4 migration — replace with inline endpoints) ────
    from src.modules.portals.controllers.parent_portal_routes import router as _parent_portal_routes_router
    router.include_router(_parent_portal_routes_router)
    from src.modules.portals.controllers.student_portal_routes import router as _student_portal_routes_router
    router.include_router(_student_portal_routes_router)
