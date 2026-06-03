"""
NASSAQ Global Error Handler Middleware
Catches unhandled exceptions, logs them, returns ApiResponse envelope.
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

# Canonical safe envelope for any unexpected server error. Shared with the
# app-level catch-all handler in backend/server.py so a 500 looks identical
# whether it is caught here (route exceptions) or by the outermost handler
# (exceptions raised in the surrounding middleware). The Arabic text lives in
# `error.message` because that is the field the frontend reads
# (frontend/src/utils/apiError.js) — never expose raw str(exc) to the client.
SAFE_ERROR_CODE = "INTERNAL_ERROR"
SAFE_ERROR_MESSAGE_AR = "حدث خطأ غير متوقع في الخادم، يرجى المحاولة مرة أخرى."


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
                    "success": False,
                    "error": {
                        "code": SAFE_ERROR_CODE,
                        "message": SAFE_ERROR_MESSAGE_AR,
                        "message_ar": SAFE_ERROR_MESSAGE_AR,
                    },
                    "meta": {
                        "error_id": request_id,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    },
                },
            )
