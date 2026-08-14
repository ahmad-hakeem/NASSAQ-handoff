"""
Relationships Module
= NestJS @Module()

Wires together relationships controllers, services, and repository.
Register by calling register(api_router).
"""
import logging
from fastapi import APIRouter

logger = logging.getLogger("nassaq")


def register(api_router: APIRouter) -> None:
    """Register relationships routes into api_router."""
    from src.modules.relationships.controllers.relationship_routes_mod import router as _relationship_routes_mod_router
    api_router.include_router(_relationship_routes_mod_router)
    logger.info("RelationshipsModule: registered")
