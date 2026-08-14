"""
Mfa Module
= NestJS @Module()

Wires together mfa controllers, services, and repository.
Register by calling register(api_router).
"""
import logging
from fastapi import APIRouter

logger = logging.getLogger("nassaq")


def register(api_router: APIRouter) -> None:
    """Register mfa routes into api_router."""
    from src.modules.mfa.controllers.mfa_routes import router as _mfa_routes_router
    api_router.include_router(_mfa_routes_router)
    logger.info("MfaModule: registered")
