"""
Users Controller
= NestJS @Controller()

HTTP endpoints for Users.
During Phase 4 migration: delegates to existing route files.
Target: inline all endpoints directly here.
"""
from fastapi import APIRouter

router = APIRouter(tags=["Users"])

# ── Route delegation (Phase 4 migration — replace with inline endpoints) ────
    from src.modules.users.controllers.user_routes_mod import router as _user_routes_mod_router
    router.include_router(_user_routes_mod_router)
    from src.modules.users.controllers.user_roles_routes import router as _user_roles_routes_router
    router.include_router(_user_roles_routes_router)
