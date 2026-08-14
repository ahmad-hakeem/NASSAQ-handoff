"""
Auth Controller
= NestJS @Controller()

HTTP endpoints for Auth.
During Phase 4 migration: delegates to existing route files.
Target: inline all endpoints directly here.
"""
from fastapi import APIRouter

router = APIRouter(tags=["Auth"])

# ── Route delegation (Phase 4 migration — replace with inline endpoints) ────
    from src.modules.auth.controllers.auth_routes_mod import router as _auth_routes_mod_router
    router.include_router(_auth_routes_mod_router)
    from src.modules.auth.controllers.security_routes import router as _security_routes_router
    router.include_router(_security_routes_router)
