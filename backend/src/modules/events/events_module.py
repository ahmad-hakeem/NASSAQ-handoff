"""
Events Module
= NestJS @Module()

Wires together events controllers, services, and repository.
Register by calling register(api_router).
"""
import logging
from fastapi import APIRouter

logger = logging.getLogger("nassaq")


def register(api_router: APIRouter) -> None:
    """Register events routes into api_router."""
    from src.modules.events.controllers.event_workflow_routes_mod import router as _event_workflow_routes_mod_router
    api_router.include_router(_event_workflow_routes_mod_router)
    logger.info("EventsModule: registered")
