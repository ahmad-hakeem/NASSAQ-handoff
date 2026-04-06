"""
NASSAQ - نَسَّق
نظام إدارة المدارس الذكي المتعدد المستأجرين
Smart Multi-Tenant School Management System

Architecture (Phase 9 – Clean Layers):
- /dependencies.py    — Shared db, auth, engines, helpers
- /shared_models.py   — All Pydantic request/response models
- /routes/*_mod.py    — Consolidated route modules
- /routes/*.py        — Factory-pattern route modules (legacy, still active)
- /engines            — Core business engines
- /app/middleware.py   — HTTP middleware stack
- /app/lifecycle.py    — Startup / shutdown hooks
- /app/routes.py       — Centralized router registration
- server.py            — Thin orchestrator (app creation only)
"""

import logging
import os
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger("nassaq")

from fastapi import FastAPI, APIRouter

_is_production = os.environ.get("ENVIRONMENT", "development") == "production"
app = FastAPI(
    title="NASSAQ - نَسَّق",
    description="نظام إدارة المدارس الذكي المتعدد المستأجرين",
    version="3.0.0",
    docs_url=None if _is_production else "/docs",
    redoc_url=None if _is_production else "/redoc",
    openapi_url=None if _is_production else "/openapi.json",
)

from app.middleware import register_middleware
register_middleware(app)

api_router = APIRouter(prefix="/api")

from app.routes import register_routes
register_routes(app, api_router)

from app.lifecycle import startup_tasks, shutdown_tasks
app.add_event_handler("startup", startup_tasks)
app.add_event_handler("shutdown", shutdown_tasks)
