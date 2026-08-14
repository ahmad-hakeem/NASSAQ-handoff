"""
Portfolio Module
= NestJS @Module()

Wires together portfolio controllers, services, and repository.
Register by calling register(api_router).
"""
import logging
from fastapi import APIRouter

logger = logging.getLogger("nassaq")


def register(api_router: APIRouter) -> None:
    """Register portfolio routes into api_router."""
    from src.modules.portfolio.controllers.portfolio_routes_mod import router as _portfolio_routes_mod_router
    api_router.include_router(_portfolio_routes_mod_router)
    logger.info("PortfolioModule: registered")
