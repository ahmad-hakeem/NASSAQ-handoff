"""
Ai Module
= NestJS @Module()

Wires together ai controllers, services, and repository.
Register by calling register(api_router).
"""
import logging
from fastapi import APIRouter

logger = logging.getLogger("nassaq")


def register(api_router: APIRouter) -> None:
    """Register ai routes into api_router."""
    from src.modules.ai.controllers.hakeem_plan_routes_mod import router as _hakeem_plan_routes_mod_router
    api_router.include_router(_hakeem_plan_routes_mod_router)
    from src.modules.ai.controllers.ai_routes_mod import router as _ai_routes_mod_router
    api_router.include_router(_ai_routes_mod_router)
    logger.info("AiModule: registered")
