"""
Participation Controller
= NestJS @Controller()

HTTP endpoints for Participation.
During Phase 4 migration: delegates to existing route files.
Target: inline all endpoints directly here.
"""
from fastapi import APIRouter

router = APIRouter(tags=["Participation"])

# ── Route delegation (Phase 4 migration — replace with inline endpoints) ────
    from src.modules.participation.controllers.participation_routes_mod import router as _participation_routes_mod_router
    router.include_router(_participation_routes_mod_router)
