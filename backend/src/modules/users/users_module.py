"""
Users Module
= NestJS @Module()

Wires together users controllers, services, and repository.
Register by calling register(api_router).
"""
import logging
from fastapi import APIRouter

logger = logging.getLogger("nassaq")


def register(api_router: APIRouter) -> None:
    """Register users routes into api_router."""
    from src.modules.users.controllers.user_routes_mod import router as _user_routes_mod_router
    api_router.include_router(_user_routes_mod_router)
    from src.modules.users.controllers.user_roles_routes import router as _user_roles_routes_router
    api_router.include_router(_user_roles_routes_router)
    logger.info("UsersModule: registered")
