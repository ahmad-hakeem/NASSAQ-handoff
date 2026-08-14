"""
Participation Module
= NestJS @Module()

Wires together participation controllers, services, and repository.
Register by calling register(api_router).
"""
import logging
from fastapi import APIRouter

logger = logging.getLogger("nassaq")


def register(api_router: APIRouter) -> None:
    """Register participation routes into api_router."""
    from src.modules.participation.controllers.participation_routes_mod import router as _participation_routes_mod_router
    api_router.include_router(_participation_routes_mod_router)
    logger.info("ParticipationModule: registered")
