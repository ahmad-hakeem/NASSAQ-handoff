"""
Notifications Controller
= NestJS @Controller()

HTTP endpoints for Notifications.
During Phase 4 migration: delegates to existing route files.
Target: inline all endpoints directly here.
"""
from fastapi import APIRouter

router = APIRouter(tags=["Notifications"])

# ── Route delegation (Phase 4 migration — replace with inline endpoints) ────
    from src.modules.notifications.controllers.notification_routes_mod import router as _notification_routes_mod_router
    router.include_router(_notification_routes_mod_router)
    from src.modules.notifications.controllers.notification_routes import router as _notification_routes_router
    router.include_router(_notification_routes_router)
    from src.modules.notifications.controllers.websocket_routes import router as _websocket_routes_router
    router.include_router(_websocket_routes_router)
