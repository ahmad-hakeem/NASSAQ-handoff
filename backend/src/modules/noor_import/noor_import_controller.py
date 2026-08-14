"""
NoorImport Controller
= NestJS @Controller()

HTTP endpoints for NoorImport.
During Phase 4 migration: delegates to existing route files.
Target: inline all endpoints directly here.
"""
from fastapi import APIRouter

router = APIRouter(tags=["NoorImport"])

# ── Route delegation (Phase 4 migration — replace with inline endpoints) ────
    from src.modules.noor_import.controllers.noor_import_routes import router as _noor_import_routes_router
    router.include_router(_noor_import_routes_router)
