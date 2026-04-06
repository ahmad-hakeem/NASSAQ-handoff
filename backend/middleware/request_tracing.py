"""
NASSAQ — Request tracing middleware.

Generates a UUID request_id for every HTTP request and attaches it to all log
entries via a ContextVar.  Also emits a structured JSON access log line with:
  request_id, user_id, tenant_id, method, path, status_code, duration_ms.
"""
import logging
import time
import uuid
from contextvars import ContextVar
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("nassaq.access")

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")


class RequestIdFilter(logging.Filter):
    """Inject *request_id* into every log record automatically."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get("-")
        return True


class RequestTracingMiddleware(BaseHTTPMiddleware):
    """Assign a unique request_id and log structured access info."""

    _SKIP_PREFIXES = ("/api/ws/", "/ws")

    async def dispatch(self, request: Request, call_next) -> Response:
        for pfx in self._SKIP_PREFIXES:
            if request.url.path.startswith(pfx):
                return await call_next(request)

        rid = uuid.uuid4().hex[:16]
        token = request_id_var.set(rid)
        request.state.request_id = rid

        start = time.perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            response.headers["X-Request-Id"] = rid
            return response
        except Exception:
            raise
        finally:
            duration_ms = round((time.perf_counter() - start) * 1000, 1)
            user_id = tenant_id = None
            if hasattr(request.state, "user") and request.state.user:
                u = request.state.user
                user_id = u.get("id") or u.get("user_id")
                tenant_id = u.get("tenant_id")
            logger.info(
                "request",
                extra={
                    "request_id": rid,
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": status_code,
                    "duration_ms": duration_ms,
                    "user_id": user_id,
                    "tenant_id": tenant_id,
                },
            )
            request_id_var.reset(token)
