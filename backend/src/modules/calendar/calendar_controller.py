"""
Calendar Controller
= NestJS @Controller()

HTTP endpoints for Calendar.
During Phase 4 migration: delegates to existing route files.
Target: inline all endpoints directly here.
"""
from fastapi import APIRouter

router = APIRouter(tags=["Calendar"])

# ── Route delegation (Phase 4 migration — replace with inline endpoints) ────
    from src.modules.calendar.controllers.calendar_routes_mod import router as _calendar_routes_mod_router
    router.include_router(_calendar_routes_mod_router)
