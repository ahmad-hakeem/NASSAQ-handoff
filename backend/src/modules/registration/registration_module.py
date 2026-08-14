"""
Registration Module
= NestJS @Module()

Wires together Registration controllers, services, and repository.
Register by calling register(api_router).
"""
import logging
from fastapi import APIRouter

logger = logging.getLogger("nassaq")


def register(api_router: APIRouter) -> None:
    """Register Registration routes into api_router."""
    from src.modules.registration.registration_controller import router
    api_router.include_router(router)
    logger.info("RegistrationModule: registered")
