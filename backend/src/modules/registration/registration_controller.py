"""
Registration Controller
= NestJS @Controller()

HTTP endpoints for Registration.
During Phase 4 migration: delegates to existing route files.
Target: inline all endpoints directly here.
"""
from fastapi import APIRouter

router = APIRouter(tags=["Registration"])

# ── Route delegation (Phase 4 migration — replace with inline endpoints) ────
    from src.modules.registration.controllers.registration_routes_mod import router as _registration_routes_mod_router
    router.include_router(_registration_routes_mod_router)
