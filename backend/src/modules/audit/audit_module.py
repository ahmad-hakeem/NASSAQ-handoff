"""
Audit Module
= NestJS @Module()

Wires together audit controllers, services, and repository.
Register by calling register(api_router).
"""
import logging
from fastapi import APIRouter

logger = logging.getLogger("nassaq")


def register(api_router: APIRouter) -> None:
    """Register audit routes into api_router."""
    from src.modules.audit.controllers.audit_routes import router as _audit_routes_router
    api_router.include_router(_audit_routes_router)
    logger.info("AuditModule: registered")
