"""
Scheduling Controller
= NestJS @Controller()

HTTP endpoints for Scheduling.
During Phase 4 migration: delegates to existing route files.
Target: inline all endpoints directly here.
"""
from fastapi import APIRouter

router = APIRouter(tags=["Scheduling"])

# ── Route delegation (Phase 4 migration — replace with inline endpoints) ────
    from src.modules.scheduling.controllers.scheduling_smart_engine_routes import router as _scheduling_smart_engine_routes_router
    router.include_router(_scheduling_smart_engine_routes_router)
    from src.modules.scheduling.controllers.scheduling_smart_session_routes import router as _scheduling_smart_session_routes_router
    router.include_router(_scheduling_smart_session_routes_router)
    from src.modules.scheduling.controllers.schedule_master_grid_routes import router as _schedule_master_grid_routes_router
    router.include_router(_schedule_master_grid_routes_router)
    from src.modules.scheduling.controllers.schedule_candidates_routes import router as _schedule_candidates_routes_router
    router.include_router(_schedule_candidates_routes_router)
    from src.modules.scheduling.controllers.timetable_readiness_routes import router as _timetable_readiness_routes_router
    router.include_router(_timetable_readiness_routes_router)
    from src.modules.scheduling.controllers.standby_routes import router as _standby_routes_router
    router.include_router(_standby_routes_router)
