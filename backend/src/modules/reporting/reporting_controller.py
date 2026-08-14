"""
Reporting Controller
= NestJS @Controller()

HTTP endpoints for Reporting.
During Phase 4 migration: delegates to existing route files.
Target: inline all endpoints directly here.
"""
from fastapi import APIRouter

router = APIRouter(tags=["Reporting"])

# ── Route delegation (Phase 4 migration — replace with inline endpoints) ────
    from src.modules.reporting.controllers.reporting_routes_mod import router as _reporting_routes_mod_router
    router.include_router(_reporting_routes_mod_router)
