"""
Reporting Module
= NestJS @Module()

Wires together reporting controllers, services, and repository.
Register by calling register(api_router).
"""
import logging
from fastapi import APIRouter

logger = logging.getLogger("nassaq")


def register(api_router: APIRouter) -> None:
    """Register reporting routes into api_router."""
    from src.modules.reporting.controllers.reporting_routes_mod import router as _reporting_routes_mod_router
    api_router.include_router(_reporting_routes_mod_router)
    logger.info("ReportingModule: registered")
