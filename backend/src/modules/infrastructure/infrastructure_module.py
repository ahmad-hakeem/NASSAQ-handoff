"""
Infrastructure Module
Equivalent to NestJS @Module({ controllers: [HealthController, MonitoringController] })

Registers:
- HealthController   → /health, /ready, /live
- MonitoringController → /v1/monitoring/*
"""
import logging
from fastapi import FastAPI, APIRouter

logger = logging.getLogger("nassaq")


def register(app: FastAPI, api_router: APIRouter) -> None:
    """Register infrastructure routes."""
    from src.modules.infrastructure.health_controller import router as health_router
    from src.modules.infrastructure.monitoring_controller import router as monitoring_router

    # Health: root-mounted (no /api prefix) — for load balancers / k8s probes
    app.include_router(health_router)

    # Monitoring: also exposed under /api for internal callers
    app.include_router(monitoring_router)
    api_router.include_router(monitoring_router)

    logger.info("InfrastructureModule: registered")
