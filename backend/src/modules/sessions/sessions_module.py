"""
Sessions Module
= NestJS @Module()

Wires together Sessions controllers, services, and repository.
Register by calling register(api_router).
"""
import logging
from fastapi import APIRouter

logger = logging.getLogger("nassaq")


def register(api_router: APIRouter) -> None:
    """Register Sessions routes into api_router."""
    from src.modules.sessions.sessions_controller import router
    api_router.include_router(router)
    logger.info("SessionsModule: registered")
