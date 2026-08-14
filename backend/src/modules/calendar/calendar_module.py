"""
Calendar Module
= NestJS @Module()

Wires together Calendar controllers, services, and repository.
Register by calling register(api_router).
"""
import logging
from fastapi import APIRouter

logger = logging.getLogger("nassaq")


def register(api_router: APIRouter) -> None:
    """Register Calendar routes into api_router."""
    from src.modules.calendar.calendar_controller import router
    api_router.include_router(router)
    logger.info("CalendarModule: registered")
