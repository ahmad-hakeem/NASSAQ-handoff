"""
Communication Module
= NestJS @Module()

Wires together Communication controllers, services, and repository.
Register by calling register(api_router).
"""
import logging
from fastapi import APIRouter

logger = logging.getLogger("nassaq")


def register(api_router: APIRouter) -> None:
    """Register Communication routes into api_router."""
    from src.modules.communication.communication_controller import router
    api_router.include_router(router)
    logger.info("CommunicationModule: registered")
