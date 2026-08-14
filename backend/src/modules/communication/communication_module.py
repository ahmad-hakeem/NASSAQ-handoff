"""
Communication Module
= NestJS @Module()

Wires together communication controllers, services, and repository.
Register by calling register(api_router).
"""
import logging
from fastapi import APIRouter

logger = logging.getLogger("nassaq")


def register(api_router: APIRouter) -> None:
    """Register communication routes into api_router."""
    from src.modules.communication.controllers.communication_routes import router as _communication_routes_router
    api_router.include_router(_communication_routes_router)
    logger.info("CommunicationModule: registered")
