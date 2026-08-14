"""
Events Module
= NestJS @Module()

Wires together Events controllers, services, and repository.
Register by calling register(api_router).
"""
import logging
from fastapi import APIRouter

logger = logging.getLogger("nassaq")


def register(api_router: APIRouter) -> None:
    """Register Events routes into api_router."""
    from src.modules.events.events_controller import router
    api_router.include_router(router)
    logger.info("EventsModule: registered")
