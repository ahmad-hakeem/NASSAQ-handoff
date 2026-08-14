"""
ConsentPrivacy Controller
= NestJS @Controller()

HTTP endpoints for ConsentPrivacy.
During Phase 4 migration: delegates to existing route files.
Target: inline all endpoints directly here.
"""
from fastapi import APIRouter

router = APIRouter(tags=["ConsentPrivacy"])

# ── Route delegation (Phase 4 migration — replace with inline endpoints) ────
    from src.modules.consent_privacy.controllers.consent_privacy_routes_mod import router as _consent_privacy_routes_mod_router
    router.include_router(_consent_privacy_routes_mod_router)
