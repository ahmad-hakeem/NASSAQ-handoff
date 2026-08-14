"""
Bulk_import Module
= NestJS @Module()

Wires together bulk_import controllers, services, and repository.
Register by calling register(api_router).
"""
import logging
from fastapi import APIRouter

logger = logging.getLogger("nassaq")


def register(api_router: APIRouter) -> None:
    """Register bulk_import routes into api_router."""
    from src.modules.bulk_import.controllers.bulk_teacher_routes import router as _bulk_teacher_routes_router
    api_router.include_router(_bulk_teacher_routes_router)
    from src.modules.bulk_import.controllers.bulk_import_export_routes import router as _bulk_import_export_routes_router
    api_router.include_router(_bulk_import_export_routes_router)
    logger.info("Bulk_importModule: registered")
