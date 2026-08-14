"""
Behaviour Module
= NestJS @Module()

Wires together behaviour controllers, services, and repository.
Register by calling register(api_router).
"""
import logging
from fastapi import APIRouter

logger = logging.getLogger("nassaq")


def register(api_router: APIRouter) -> None:
    """Register behaviour routes into api_router."""
    from src.modules.behaviour.controllers.behaviour_routes_mod import router as _behaviour_routes_mod_router
    api_router.include_router(_behaviour_routes_mod_router)
    logger.info("BehaviourModule: registered")
