"""
Consent_privacy Module
= NestJS @Module()

Wires together consent_privacy controllers, services, and repository.
Register by calling register(api_router).
"""
import logging
from fastapi import APIRouter

logger = logging.getLogger("nassaq")


def register(api_router: APIRouter) -> None:
    """Register consent_privacy routes into api_router."""
    from src.modules.consent_privacy.controllers.consent_privacy_routes_mod import router as _consent_privacy_routes_mod_router
    api_router.include_router(_consent_privacy_routes_mod_router)
    logger.info("Consent_privacyModule: registered")
