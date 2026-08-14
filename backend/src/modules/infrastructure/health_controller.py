"""
Health Controller
= NestJS @Controller() for health probe endpoints.

Re-exports the existing health_routes router.
During migration, endpoints will be moved here directly.
"""
# Delegate to existing route file — will be inlined in Phase 4 cleanup
from src.modules.infrastructure.controllers.health_routes import router  # noqa: F401
