"""
Portfolio Controller
= NestJS @Controller()

HTTP endpoints for Portfolio.
During Phase 4 migration: delegates to existing route files.
Target: inline all endpoints directly here.
"""
from fastapi import APIRouter

router = APIRouter(tags=["Portfolio"])

# ── Route delegation (Phase 4 migration — replace with inline endpoints) ────
    from src.modules.portfolio.controllers.portfolio_routes_mod import router as _portfolio_routes_mod_router
    router.include_router(_portfolio_routes_mod_router)
