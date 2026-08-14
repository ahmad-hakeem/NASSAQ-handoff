"""
AI (Hakim) Module
= NestJS @Module()

Wires together AI (Hakim) controllers, services, and repository.
Register by calling register(api_router).
"""
import logging
from fastapi import APIRouter

logger = logging.getLogger("nassaq")


def register(api_router: APIRouter) -> None:
    """Register AI (Hakim) routes into api_router."""
    from src.modules.ai.ai_controller import router
    api_router.include_router(router)
    logger.info("AI (Hakim)Module: registered")
