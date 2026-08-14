"""
Portals Module
= NestJS @Module()

Wires together Portals controllers, services, and repository.
Register by calling register(api_router).
"""
import logging
from fastapi import APIRouter

logger = logging.getLogger("nassaq")


def register(api_router: APIRouter) -> None:
    """Register Portals routes into api_router."""
    from src.modules.portals.portals_controller import router
    api_router.include_router(router)
    logger.info("PortalsModule: registered")
