"""
Noor_import Module
= NestJS @Module()

Wires together noor_import controllers, services, and repository.
Register by calling register(api_router).
"""
import logging
from fastapi import APIRouter

logger = logging.getLogger("nassaq")


def register(api_router: APIRouter) -> None:
    """Register noor_import routes into api_router."""
    from src.modules.noor_import.controllers.noor_import_routes import router as _noor_import_routes_router
    api_router.include_router(_noor_import_routes_router)
    logger.info("Noor_importModule: registered")
