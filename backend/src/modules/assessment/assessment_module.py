"""
Assessment Module
= NestJS @Module()

Wires together assessment controllers, services, and repository.
Register by calling register(api_router).
"""
import logging
from fastapi import APIRouter

logger = logging.getLogger("nassaq")


def register(api_router: APIRouter) -> None:
    """Register assessment routes into api_router."""
    from src.modules.assessment.controllers.assessment_routes_mod import router as _assessment_routes_mod_router
    api_router.include_router(_assessment_routes_mod_router)
    from src.modules.assessment.controllers.assessment_routes import router as _assessment_routes_router
    api_router.include_router(_assessment_routes_router)
    logger.info("AssessmentModule: registered")
