"""
Scheduling Module
= NestJS @Module()

Wires together scheduling controllers, services, and repository.
Register by calling register(api_router).
"""
import logging
from fastapi import APIRouter

logger = logging.getLogger("nassaq")


def register(api_router: APIRouter) -> None:
    """Register scheduling routes into api_router."""
    from src.modules.scheduling.controllers.timetable_readiness_routes import router as _timetable_readiness_routes_router
    api_router.include_router(_timetable_readiness_routes_router)
    from src.modules.scheduling.controllers.scheduling_smart_engine_routes import router as _scheduling_smart_engine_routes_router
    api_router.include_router(_scheduling_smart_engine_routes_router)
    from src.modules.scheduling.controllers._publish_gate import router as __publish_gate_router
    api_router.include_router(__publish_gate_router)
    from src.modules.scheduling.controllers.schedule_candidates_routes import router as _schedule_candidates_routes_router
    api_router.include_router(_schedule_candidates_routes_router)
    from src.modules.scheduling.controllers.scheduling_smart_session_routes import router as _scheduling_smart_session_routes_router
    api_router.include_router(_scheduling_smart_session_routes_router)
    from src.modules.scheduling.controllers.standby_routes import router as _standby_routes_router
    api_router.include_router(_standby_routes_router)
    from src.modules.scheduling.controllers.schedule_master_grid_routes import router as _schedule_master_grid_routes_router
    api_router.include_router(_schedule_master_grid_routes_router)
    logger.info("SchedulingModule: registered")
