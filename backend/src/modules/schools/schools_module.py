"""
Schools Module
= NestJS @Module()

Wires together Schools controllers, services, and repository.
Register by calling register(api_router).
"""
import logging
from fastapi import APIRouter

logger = logging.getLogger("nassaq")


def register(api_router: APIRouter) -> None:
    """Register Schools routes into api_router."""
    from src.modules.schools.schools_controller import router
    api_router.include_router(router)
    logger.info("SchoolsModule: registered")
