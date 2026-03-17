"""
NASSAQ Rate Limiter Middleware
Token-bucket style rate limiting for critical endpoints.
"""
import time
import asyncio
from collections import defaultdict
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
import logging

logger = logging.getLogger("nassaq.ratelimit")


class RateLimitStore:
    def __init__(self):
        self._store = defaultdict(list)
        self._lock = asyncio.Lock()

    async def is_rate_limited(self, key: str, max_requests: int, window_seconds: int) -> bool:
        async with self._lock:
            now = time.time()
            cutoff = now - window_seconds
            self._store[key] = [t for t in self._store[key] if t > cutoff]
            if len(self._store[key]) >= max_requests:
                return True
            self._store[key].append(now)
            return False

    async def cleanup(self):
        async with self._lock:
            now = time.time()
            expired = [k for k, v in self._store.items() if not v or max(v) < now - 3600]
            for k in expired:
                del self._store[k]


rate_store = RateLimitStore()

RATE_LIMITS = {
    "/api/auth/login": {"max": 10, "window": 60},
    "/api/auth/register": {"max": 5, "window": 60},
    "/api/registration-requests": {"max": 10, "window": 60},
    "/api/reports/export": {"max": 10, "window": 120},
    "/api/hakim/analyze": {"max": 5, "window": 60},
    "/api/auth/change-password": {"max": 5, "window": 300},
}


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        client_ip = request.client.host if request.client else "unknown"

        for pattern, limits in RATE_LIMITS.items():
            if path.startswith(pattern):
                key = f"{client_ip}:{pattern}"
                if await rate_store.is_rate_limited(key, limits["max"], limits["window"]):
                    logger.warning(f"Rate limited: {client_ip} on {pattern}")
                    return JSONResponse(
                        status_code=429,
                        content={"detail": "عدد الطلبات تجاوز الحد المسموح. يرجى المحاولة لاحقاً"}
                    )
                break

        response = await call_next(request)
        return response
