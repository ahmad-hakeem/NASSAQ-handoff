"""
Audit Controller
= NestJS @Controller()

HTTP endpoints for Audit.
During Phase 4 migration: delegates to existing route files.
Target: inline all endpoints directly here.
"""
from fastapi import APIRouter

router = APIRouter(tags=["Audit"])

# ── Route delegation (Phase 4 migration — replace with inline endpoints) ────
    from src.modules.audit.controllers.audit_routes import router as _audit_routes_router
    router.include_router(_audit_routes_router)
