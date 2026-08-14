"""
Audit Module
= NestJS @Module()

Wires together Audit controllers, services, and repository.
Register by calling register(api_router).
"""
import logging
from fastapi import APIRouter

logger = logging.getLogger("nassaq")


def register(api_router: APIRouter) -> None:
    """Register Audit routes into api_router."""
    from src.modules.audit.audit_controller import router
    api_router.include_router(router)
    logger.info("AuditModule: registered")
