"""
Events Controller
= NestJS @Controller()

HTTP endpoints for Events.
During Phase 4 migration: delegates to existing route files.
Target: inline all endpoints directly here.
"""
from fastapi import APIRouter

router = APIRouter(tags=["Events"])

# ── Route delegation (Phase 4 migration — replace with inline endpoints) ────
    from src.modules.events.controllers.event_workflow_routes_mod import router as _event_workflow_routes_mod_router
    router.include_router(_event_workflow_routes_mod_router)
