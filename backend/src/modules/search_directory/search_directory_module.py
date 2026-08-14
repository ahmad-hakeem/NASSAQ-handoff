"""
SearchDirectory Module
= NestJS @Module()

Wires together SearchDirectory controllers, services, and repository.
Register by calling register(api_router).
"""
import logging
from fastapi import APIRouter

logger = logging.getLogger("nassaq")


def register(api_router: APIRouter) -> None:
    """Register SearchDirectory routes into api_router."""
    from src.modules.search_directory.search_directory_controller import router
    api_router.include_router(router)
    logger.info("SearchDirectoryModule: registered")
