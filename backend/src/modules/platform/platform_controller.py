"""
Platform Controller
= NestJS @Controller()

HTTP endpoints for Platform.
During Phase 4 migration: delegates to existing route files.
Target: inline all endpoints directly here.
"""
from fastapi import APIRouter

router = APIRouter(tags=["Platform"])

# ── Route delegation (Phase 4 migration — replace with inline endpoints) ────
    from src.modules.platform.controllers.platform_routes_mod import router as _platform_routes_mod_router
    router.include_router(_platform_routes_mod_router)
    from src.modules.platform.controllers.admin_routes_mod import router as _admin_routes_mod_router
    router.include_router(_admin_routes_mod_router)
    from src.modules.platform.controllers.product_hub_routes import router as _product_hub_routes_router
    router.include_router(_product_hub_routes_router)
    from src.modules.platform.controllers.platform_workspace_purge_routes import router as _platform_workspace_purge_routes_router
    router.include_router(_platform_workspace_purge_routes_router)
    from src.modules.platform.controllers.admin_dashboard_routes import router as _admin_dashboard_routes_router
    router.include_router(_admin_dashboard_routes_router)
