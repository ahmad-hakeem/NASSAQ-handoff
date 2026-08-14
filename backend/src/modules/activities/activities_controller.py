"""
Activities Controller
= NestJS @Controller()

HTTP endpoints for Activities.
During Phase 4 migration: delegates to existing route files.
Target: inline all endpoints directly here.
"""
from fastapi import APIRouter

router = APIRouter(tags=["Activities"])

# ── Route delegation (Phase 4 migration — replace with inline endpoints) ────
    from src.modules.activities.controllers.activities_routes_mod import router as _activities_routes_mod_router
    router.include_router(_activities_routes_mod_router)
