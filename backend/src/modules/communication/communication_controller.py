"""
Communication Controller
= NestJS @Controller()

HTTP endpoints for Communication.
During Phase 4 migration: delegates to existing route files.
Target: inline all endpoints directly here.
"""
from fastapi import APIRouter

router = APIRouter(tags=["Communication"])

# ── Route delegation (Phase 4 migration — replace with inline endpoints) ────
    from src.modules.communication.controllers.communication_routes import router as _communication_routes_router
    router.include_router(_communication_routes_router)
