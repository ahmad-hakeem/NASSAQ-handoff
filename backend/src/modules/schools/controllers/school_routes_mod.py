"""
NASSAQ Route Module: School CRUD, dashboard, updates
Backward-compatible shim re-exporting from src.modules.schools.schools_controller
"""
from src.modules.schools.schools_controller import *  # noqa: F401, F403
from src.modules.schools.schools_controller import router  # noqa: F401
