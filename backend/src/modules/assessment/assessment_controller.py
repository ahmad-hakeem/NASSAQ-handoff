"""
Assessment Controller
= NestJS @Controller()

HTTP endpoints for Assessment.
During Phase 4 migration: delegates to existing route files.
Target: inline all endpoints directly here.
"""
from fastapi import APIRouter

router = APIRouter(tags=["Assessment"])

# ── Route delegation (Phase 4 migration — replace with inline endpoints) ────
    from src.modules.assessment.controllers.assessment_routes_mod import router as _assessment_routes_mod_router
    router.include_router(_assessment_routes_mod_router)
    from src.modules.assessment.controllers.assessment_routes import router as _assessment_routes_router
    router.include_router(_assessment_routes_router)
