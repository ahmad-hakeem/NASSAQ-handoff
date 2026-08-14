"""
Schools Module
= NestJS @Module()

Wires together schools controllers, services, and repository.
Register by calling register(api_router).
"""
import logging
from fastapi import APIRouter

logger = logging.getLogger("nassaq")


def register(api_router: APIRouter) -> None:
    """Register schools routes into api_router."""
    from src.modules.schools.controllers.settings_routes import router as _settings_routes_router
    api_router.include_router(_settings_routes_router)
    from src.modules.schools.controllers.school_settings_mod import router as _school_settings_mod_router
    api_router.include_router(_school_settings_mod_router)
    from src.modules.schools.controllers.school_routes_mod import router as _school_routes_mod_router
    api_router.include_router(_school_routes_mod_router)
    logger.info("SchoolsModule: registered")
