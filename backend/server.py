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

import json
import logging
import os
import sys


class StructuredJsonFormatter(logging.Formatter):
    """Emit each log record as a single JSON line for structured log ingestion."""

    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "ts": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "request_id": getattr(record, "request_id", "-"),
        }
        for key in ("user_id", "tenant_id", "method", "path", "status_code", "duration_ms"):
            val = getattr(record, key, None)
            if val is not None:
                entry[key] = val
        if record.exc_info and record.exc_info[1]:
            entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(entry, ensure_ascii=False, default=str)


_handler = logging.StreamHandler(sys.stdout)
_handler.setFormatter(StructuredJsonFormatter(datefmt="%Y-%m-%dT%H:%M:%S"))

from middleware.request_tracing import RequestIdFilter
_handler.addFilter(RequestIdFilter())

logging.basicConfig(level=logging.INFO, handlers=[_handler])
logger = logging.getLogger("nassaq")

from fastapi import FastAPI, APIRouter, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from sqlalchemy.exc import IntegrityError


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

    @application.exception_handler(IntegrityError)
    async def integrity_exception_handler(request: Request, exc: IntegrityError):
        # Convert race-condition unique/foreign-key violations into a clean 409
        # instead of leaking a 500 to the client.
        msg = str(getattr(exc, "orig", exc))
        lower = msg.lower()
        if "unique" in lower or "duplicate" in lower:
            code = "DUPLICATE_RECORD"
            user_msg = "هذا السجل موجود مسبقاً"
        elif "foreign key" in lower:
            code = "INVALID_REFERENCE"
            user_msg = "مرجع غير صالح في البيانات المُرسَلة"
        else:
            code = "DATA_CONFLICT"
            user_msg = "تعارض في البيانات"
        logger.warning(
            "IntegrityError on %s %s: %s",
            request.method, request.url.path, msg,
        )
        return JSONResponse(
            status_code=409,
            content={
                "success": False,
                "error": {"code": code, "message": user_msg},
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
