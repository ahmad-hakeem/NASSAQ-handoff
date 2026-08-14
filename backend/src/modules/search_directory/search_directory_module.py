"""
Search_directory Module
= NestJS @Module()

Wires together search_directory controllers, services, and repository.
Register by calling register(api_router).
"""
import logging
from fastapi import APIRouter

logger = logging.getLogger("nassaq")


def register(api_router: APIRouter) -> None:
    """Register search_directory routes into api_router."""
    from src.modules.search_directory.controllers.search_directory_routes_mod import router as _search_directory_routes_mod_router
    api_router.include_router(_search_directory_routes_mod_router)
    logger.info("Search_directoryModule: registered")
