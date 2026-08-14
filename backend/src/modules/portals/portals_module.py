"""
Portals Module
= NestJS @Module()

Wires together portals controllers, services, and repository.
Register by calling register(api_router).
"""
import logging
from fastapi import APIRouter

logger = logging.getLogger("nassaq")


def register(api_router: APIRouter) -> None:
    """Register portals routes into api_router."""
    from src.modules.portals.controllers.role_dashboards_mod import router as _role_dashboards_mod_router
    api_router.include_router(_role_dashboards_mod_router)
    from src.modules.portals.controllers.student_portal_routes import router as _student_portal_routes_router
    api_router.include_router(_student_portal_routes_router)
    from src.modules.portals.controllers.dashboard_routes_mod import router as _dashboard_routes_mod_router
    api_router.include_router(_dashboard_routes_mod_router)
    from src.modules.portals.controllers.parent_portal_routes import router as _parent_portal_routes_router
    api_router.include_router(_parent_portal_routes_router)
    logger.info("PortalsModule: registered")
