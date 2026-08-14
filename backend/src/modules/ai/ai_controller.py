"""
AI (Hakim) Controller
= NestJS @Controller()

HTTP endpoints for AI (Hakim).
During Phase 4 migration: delegates to existing route files.
Target: inline all endpoints directly here.
"""
from fastapi import APIRouter

router = APIRouter(tags=["AI (Hakim)"])

# ── Route delegation (Phase 4 migration — replace with inline endpoints) ────
    from src.modules.ai.controllers.ai_routes_mod import router as _ai_routes_mod_router
    router.include_router(_ai_routes_mod_router)
    from src.modules.ai.controllers.hakeem_plan_routes_mod import router as _hakeem_plan_routes_mod_router
    router.include_router(_hakeem_plan_routes_mod_router)
