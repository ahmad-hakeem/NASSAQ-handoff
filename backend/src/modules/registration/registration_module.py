"""
Registration Module
= NestJS @Module()

Wires together registration controllers, services, and repository.
Register by calling register(api_router).
"""
import logging
from fastapi import APIRouter

logger = logging.getLogger("nassaq")


def register(api_router: APIRouter) -> None:
    """Register registration routes into api_router."""
    from src.modules.registration.controllers.registration_routes_mod import router as _registration_routes_mod_router
    api_router.include_router(_registration_routes_mod_router)
    logger.info("RegistrationModule: registered")
