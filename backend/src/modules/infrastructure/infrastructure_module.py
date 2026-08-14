"""
Infrastructure Module
= NestJS @Module()
"""
import logging
from fastapi import FastAPI, APIRouter

logger = logging.getLogger("nassaq")


def register(app: FastAPI, api_router: APIRouter) -> None:
    """Register Infrastructure routes."""
    from src.modules.infrastructure.controllers.health_routes import router as health_router
    from src.modules.infrastructure.controllers.monitoring_routes import router as monitoring_router
    
    app.include_router(health_router)
    app.include_router(monitoring_router)
    api_router.include_router(monitoring_router)
    logger.info("InfrastructureModule: registered")
