"""
Behaviour Controller
= NestJS @Controller()

HTTP endpoints for Behaviour.
During Phase 4 migration: delegates to existing route files.
Target: inline all endpoints directly here.
"""
from fastapi import APIRouter

router = APIRouter(tags=["Behaviour"])

# ── Route delegation (Phase 4 migration — replace with inline endpoints) ────
    from src.modules.behaviour.controllers.behaviour_routes_mod import router as _behaviour_routes_mod_router
    router.include_router(_behaviour_routes_mod_router)
