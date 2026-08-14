"""
Relationships Controller
= NestJS @Controller()

HTTP endpoints for Relationships.
During Phase 4 migration: delegates to existing route files.
Target: inline all endpoints directly here.
"""
from fastapi import APIRouter

router = APIRouter(tags=["Relationships"])

# ── Route delegation (Phase 4 migration — replace with inline endpoints) ────
    from src.modules.relationships.controllers.relationship_routes_mod import router as _relationship_routes_mod_router
    router.include_router(_relationship_routes_mod_router)
