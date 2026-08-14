"""
MFA Controller
= NestJS @Controller()

HTTP endpoints for MFA.
During Phase 4 migration: delegates to existing route files.
Target: inline all endpoints directly here.
"""
from fastapi import APIRouter

router = APIRouter(tags=["MFA"])

# ── Route delegation (Phase 4 migration — replace with inline endpoints) ────
    from src.modules.mfa.controllers.mfa_routes import router as _mfa_routes_router
    router.include_router(_mfa_routes_router)
