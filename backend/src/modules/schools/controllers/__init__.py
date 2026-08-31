"""
Schools Module Controllers
"""
from src.modules.schools.controllers.school_routes_mod import router as school_routes_router
from src.modules.schools.controllers.school_settings_mod import (
    router as school_settings_router,
    time_slots_router,
)
from src.modules.schools.controllers.settings_routes import (
    router as settings_router,
    setup_settings_routes,
)

__all__ = [
    "school_routes_router",
    "school_settings_router",
    "time_slots_router",
    "settings_router",
    "setup_settings_routes",
]
