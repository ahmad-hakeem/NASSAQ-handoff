"""
Auth Module
= NestJS @Module()

Wires together auth controllers, services, and repository.
Register by calling register(api_router).
"""
import logging
from fastapi import APIRouter

logger = logging.getLogger("nassaq")


def register(api_router: APIRouter) -> None:
    """Register auth routes into api_router."""
    from src.modules.auth.controllers.security_routes import router as _security_routes_router
    api_router.include_router(_security_routes_router)
    from src.modules.auth.controllers.auth_routes_mod import router as _auth_routes_mod_router
    api_router.include_router(_auth_routes_mod_router)
    logger.info("AuthModule: registered")
