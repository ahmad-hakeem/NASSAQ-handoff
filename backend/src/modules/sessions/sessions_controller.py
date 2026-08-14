"""
Sessions Controller
= NestJS @Controller()

HTTP endpoints for Sessions.
During Phase 4 migration: delegates to existing route files.
Target: inline all endpoints directly here.
"""
from fastapi import APIRouter

router = APIRouter(tags=["Sessions"])

# ── Route delegation (Phase 4 migration — replace with inline endpoints) ────
    from src.modules.portals.controllers.role_dashboards_mod import router as _role_dashboards_mod_router
    router.include_router(_role_dashboards_mod_router)
