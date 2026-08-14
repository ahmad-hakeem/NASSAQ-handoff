"""
Notifications Module
= NestJS @Module()

Wires together notifications controllers, services, and repository.
Register by calling register(api_router).
"""
import logging
from fastapi import APIRouter

logger = logging.getLogger("nassaq")


def register(api_router: APIRouter) -> None:
    """Register notifications routes into api_router."""
    from src.modules.notifications.controllers.notification_routes_mod import router as _notification_routes_mod_router
    api_router.include_router(_notification_routes_mod_router)
    from src.modules.notifications.controllers.websocket_routes import router as _websocket_routes_router
    api_router.include_router(_websocket_routes_router)
    from src.modules.notifications.controllers.notification_routes import router as _notification_routes_router
    api_router.include_router(_notification_routes_router)
    logger.info("NotificationsModule: registered")
