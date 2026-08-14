"""
NASSAQ — Root App Module
= NestJS AppModule

Registers all feature modules and controllers into the api_router.
Single source of truth for modular route registration.
"""
import logging
from fastapi import FastAPI, APIRouter

logger = logging.getLogger("nassaq")


def register_all_modules(app: FastAPI, api_router: APIRouter) -> None:
    """
    Register all feature modules into the application.
    """
    from app.routes import register_routes
    register_routes(app, api_router)
    logger.info("AppModule: all feature modules and controllers registered successfully")
