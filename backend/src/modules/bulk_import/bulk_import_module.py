"""
BulkImport Module
= NestJS @Module()

Wires together BulkImport controllers, services, and repository.
Register by calling register(api_router).
"""
import logging
from fastapi import APIRouter

logger = logging.getLogger("nassaq")


def register(api_router: APIRouter) -> None:
    """Register BulkImport routes into api_router."""
    from src.modules.bulk_import.bulk_import_controller import router
    api_router.include_router(router)
    logger.info("BulkImportModule: registered")
