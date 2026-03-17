"""
NASSAQ Global Error Handler Middleware
Catches unhandled exceptions, logs them, returns safe error responses.
"""
import traceback
import time
import uuid
from datetime import datetime, timezone
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
import logging

logger = logging.getLogger("nassaq.errors")


class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        request_id = str(uuid.uuid4())[:8]

        try:
            response = await call_next(request)
            duration_ms = round((time.time() - start_time) * 1000, 2)

            if response.status_code >= 500:
                logger.error(
                    f"[{request_id}] {request.method} {request.url.path} -> {response.status_code} ({duration_ms}ms)"
                )

            return response

        except Exception as exc:
            duration_ms = round((time.time() - start_time) * 1000, 2)
            logger.error(
                f"[{request_id}] UNHANDLED {request.method} {request.url.path} ({duration_ms}ms): {type(exc).__name__}: {exc}"
            )
            logger.error(f"[{request_id}] Traceback: {traceback.format_exc()}")

            return JSONResponse(
                status_code=500,
                content={
                    "detail": "حدث خطأ داخلي في الخادم",
                    "error_id": request_id,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            )
