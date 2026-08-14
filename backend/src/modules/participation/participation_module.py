"""
Participation Module
= NestJS @Module()

Wires together Participation controllers, services, and repository.
Register by calling register(api_router).
"""
import logging
from fastapi import APIRouter

logger = logging.getLogger("nassaq")


def register(api_router: APIRouter) -> None:
    """Register Participation routes into api_router."""
    from src.modules.participation.participation_controller import router
    api_router.include_router(router)
    logger.info("ParticipationModule: registered")
