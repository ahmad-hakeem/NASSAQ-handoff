"""
NoorImport Module
= NestJS @Module()

Wires together NoorImport controllers, services, and repository.
Register by calling register(api_router).
"""
import logging
from fastapi import APIRouter

logger = logging.getLogger("nassaq")


def register(api_router: APIRouter) -> None:
    """Register NoorImport routes into api_router."""
    from src.modules.noor_import.noor_import_controller import router
    api_router.include_router(router)
    logger.info("NoorImportModule: registered")
