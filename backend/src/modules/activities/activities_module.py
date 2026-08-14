"""
Activities Module
= NestJS @Module()

Wires together activities controllers, services, and repository.
Register by calling register(api_router).
"""
import logging
from fastapi import APIRouter

logger = logging.getLogger("nassaq")


def register(api_router: APIRouter) -> None:
    """Register activities routes into api_router."""
    from src.modules.activities.controllers.activities_routes_mod import router as _activities_routes_mod_router
    api_router.include_router(_activities_routes_mod_router)
    logger.info("ActivitiesModule: registered")
