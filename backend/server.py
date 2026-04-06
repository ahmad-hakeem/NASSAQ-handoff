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
- server.py            — App factory (create_app)
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

from fastapi import FastAPI, APIRouter, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


def create_app() -> FastAPI:
    _is_production = os.environ.get("ENVIRONMENT", "development") == "production"
    application = FastAPI(
        title="NASSAQ - نَسَّق",
        description="نظام إدارة المدارس الذكي المتعدد المستأجرين",
        version="3.0.0",
        docs_url=None if _is_production else "/docs",
        redoc_url=None if _is_production else "/redoc",
        openapi_url=None if _is_production else "/openapi.json",
    )

    @application.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "success": False,
                "error": {
                    "code": f"HTTP_{exc.status_code}",
                    "message": detail,
                },
            },
        )

    @application.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        errors = [
            {"field": ".".join(str(loc) for loc in e["loc"]), "message": e["msg"]}
            for e in exc.errors()
        ]
        return JSONResponse(
            status_code=422,
            content={
                "success": False,
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Request validation failed",
                },
                "meta": {"validation_errors": errors},
            },
        )

    from app.middleware import register_middleware
    register_middleware(application)

    api_router = APIRouter(prefix="/api")

    from app.routes import register_routes
    register_routes(application, api_router)

    from app.lifecycle import startup_tasks, shutdown_tasks
    application.add_event_handler("startup", startup_tasks)
    application.add_event_handler("shutdown", shutdown_tasks)

    return application


app = create_app()
