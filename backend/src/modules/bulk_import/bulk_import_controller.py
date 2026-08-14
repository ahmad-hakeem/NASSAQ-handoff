"""
BulkImport Controller
= NestJS @Controller()

HTTP endpoints for BulkImport.
During Phase 4 migration: delegates to existing route files.
Target: inline all endpoints directly here.
"""
from fastapi import APIRouter

router = APIRouter(tags=["BulkImport"])

# ── Route delegation (Phase 4 migration — replace with inline endpoints) ────
    from src.modules.bulk_import.controllers.bulk_import_export_routes import router as _bulk_import_export_routes_router
    router.include_router(_bulk_import_export_routes_router)
    from src.modules.bulk_import.controllers.bulk_teacher_routes import router as _bulk_teacher_routes_router
    router.include_router(_bulk_teacher_routes_router)
