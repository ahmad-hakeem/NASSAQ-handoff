"""
Platform Module
= NestJS @Module()

Wires together platform controllers, services, and repository.
Register by calling register(api_router).
"""
import logging
from fastapi import APIRouter

logger = logging.getLogger("nassaq")


def register(api_router: APIRouter) -> None:
    """Register platform routes into api_router."""
    from src.modules.platform.controllers.admin_dashboard_routes import router as _admin_dashboard_routes_router
    api_router.include_router(_admin_dashboard_routes_router)
    from src.modules.platform.controllers.admin_routes_mod import router as _admin_routes_mod_router
    api_router.include_router(_admin_routes_mod_router)
    from src.modules.platform.controllers.platform_workspace_purge_routes import router as _platform_workspace_purge_routes_router
    api_router.include_router(_platform_workspace_purge_routes_router)
    from src.modules.platform.controllers.product_hub_routes import router as _product_hub_routes_router
    api_router.include_router(_product_hub_routes_router)
    from src.modules.platform.controllers.platform_routes_mod import router as _platform_routes_mod_router
    api_router.include_router(_platform_routes_mod_router)
    logger.info("PlatformModule: registered")
