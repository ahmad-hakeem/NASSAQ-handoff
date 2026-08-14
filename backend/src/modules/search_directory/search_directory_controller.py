"""
SearchDirectory Controller
= NestJS @Controller()

HTTP endpoints for SearchDirectory.
During Phase 4 migration: delegates to existing route files.
Target: inline all endpoints directly here.
"""
from fastapi import APIRouter

router = APIRouter(tags=["SearchDirectory"])

# ── Route delegation (Phase 4 migration — replace with inline endpoints) ────
    from src.modules.search_directory.controllers.search_directory_routes_mod import router as _search_directory_routes_mod_router
    router.include_router(_search_directory_routes_mod_router)
