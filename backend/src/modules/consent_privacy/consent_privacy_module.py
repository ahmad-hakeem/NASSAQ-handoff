"""
ConsentPrivacy Module
= NestJS @Module()

Wires together ConsentPrivacy controllers, services, and repository.
Register by calling register(api_router).
"""
import logging
from fastapi import APIRouter

logger = logging.getLogger("nassaq")


def register(api_router: APIRouter) -> None:
    """Register ConsentPrivacy routes into api_router."""
    from src.modules.consent_privacy.consent_privacy_controller import router
    api_router.include_router(router)
    logger.info("ConsentPrivacyModule: registered")
