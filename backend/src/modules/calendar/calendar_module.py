"""
Calendar Module
= NestJS @Module()

Wires together calendar controllers, services, and repository.
Register by calling register(api_router).
"""
import logging
from fastapi import APIRouter

logger = logging.getLogger("nassaq")


def register(api_router: APIRouter) -> None:
    """Register calendar routes into api_router."""
    from src.modules.calendar.controllers.calendar_routes_mod import router as _calendar_routes_mod_router
    api_router.include_router(_calendar_routes_mod_router)
    logger.info("CalendarModule: registered")
