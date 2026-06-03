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
        # Routes may raise HTTPException(detail={...}) with a structured
        # payload (e.g. require_recent_mfa returns
        # {code: "MFA_STEPUP_REQUIRED", message, challenge_endpoint, ...}).
        # Stringifying that would break the frontend interceptor's ability
        # to dispatch on the machine-readable code, so when detail is a
        # dict we splice its fields into the standard envelope and surface
        # the dict itself under `error.detail` for clients that want raw
        # access.
        if isinstance(exc.detail, dict):
            err = {
                "code": exc.detail.get("code") or f"HTTP_{exc.status_code}",
                "message": exc.detail.get("message") or "",
                "detail": exc.detail,
            }
            for k, v in exc.detail.items():
                if k not in err:
                    err[k] = v
        else:
            err = {
                "code": f"HTTP_{exc.status_code}",
                "message": exc.detail if isinstance(exc.detail, str) else str(exc.detail),
            }
        # Preserve any explicit response headers the route attached to
        # the HTTPException (e.g. ``Retry-After`` on 429s from the IT
        # lesson-plan burst limiter, Task #221). Without this passthrough
        # the headers would be silently dropped by JSONResponse.
        return JSONResponse(
            status_code=exc.status_code,
            content={"success": False, "error": err},
            headers=getattr(exc, "headers", None) or None,
        )

    @application.exception_handler(IntegrityError)
    async def integrity_exception_handler(request: Request, exc: IntegrityError):
        # Convert race-condition unique/foreign-key violations into a clean 409
        # instead of leaking a 500 to the client. Map known PG constraint
        # names to actionable, field-specific Arabic messages so the UI can
        # tell the user exactly what's wrong.
        from app.integrity_messages import describe_integrity_error
        msg = str(getattr(exc, "orig", exc))
        code, user_msg = describe_integrity_error(msg)
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
        # Log for triage — request validation failures are otherwise opaque
        # at the access-log level and the frontend can only show a generic
        # message to the user.
        import logging as _logging
        _logging.getLogger("nassaq.validation").warning(
            "validation failed: method=%s path=%s errors=%s",
            request.method, request.url.path, errors,
        )
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

    @application.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        # Catch-all for any exception that escapes a route without being
        # handled by the more specific handlers above. Starlette dispatches
        # to the most-specific registered handler by exception type, so
        # StarletteHTTPException / IntegrityError / RequestValidationError
        # still win for their own types; this only fires for genuinely
        # unexpected errors (e.g. a DB error outside a route's try/except).
        #
        # Without this, Starlette renders such errors as an unparseable
        # plain-text HTTP 500, which the frontend write-error classifier
        # (frontend/src/utils/apiError.js) cannot read — collapsing into a
        # cause-hiding generic popup. Returning the canonical envelope with a
        # safe Arabic message keeps the UI informative without ever exposing
        # raw str(exc) to the client.
        from middleware.error_handler import SAFE_ERROR_CODE, SAFE_ERROR_MESSAGE_AR
        logger.exception(
            "Unhandled exception on %s %s",
            request.method, request.url.path,
        )
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": {
                    "code": SAFE_ERROR_CODE,
                    "message": SAFE_ERROR_MESSAGE_AR,
                },
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
