"""
Monitoring Controller
= NestJS @Controller() for system monitoring endpoints.

Re-exports the existing monitoring_routes router.
"""
# Delegate to existing route file — will be inlined in Phase 4 cleanup
from src.modules.infrastructure.controllers.monitoring_routes import router  # noqa: F401
