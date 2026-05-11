"""
NASSAQ Rate Limiter Middleware

In-memory sliding-window rate limiting for critical endpoints.

PRODUCTION NOTE:
  This store is **process-local**. When running behind multiple workers
  (e.g. ``gunicorn -w 4``) each worker keeps its own counter, so
  effective limits are multiplied by the worker count. For strict
  distributed rate limiting, swap ``RateLimitStore`` for a Redis-backed
  implementation (e.g. redis INCR + EXPIRE).  The current design is
  intentional for single-worker Replit deployments.
"""
import time
import asyncio
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
import logging

logger = logging.getLogger("nassaq.ratelimit")


class RateLimitStore:
    MAX_KEYS = 50_000

    def __init__(self):
        self._store: dict[str, list[float]] = {}
        self._lock = asyncio.Lock()

    async def is_rate_limited(self, key: str, max_requests: int, window_seconds: int) -> tuple[bool, int, int]:
        async with self._lock:
            now = time.time()
            cutoff = now - window_seconds

            if key in self._store:
                self._store[key] = [t for t in self._store[key] if t > cutoff]
            else:
                if len(self._store) >= self.MAX_KEYS:
                    await self._evict_expired(now)
                    if len(self._store) >= self.MAX_KEYS:
                        return False, max_requests, window_seconds
                self._store[key] = []

            current = len(self._store[key])
            remaining = max(0, max_requests - current)

            if current >= max_requests:
                oldest = min(self._store[key]) if self._store[key] else now
                retry_after = int(oldest + window_seconds - now) + 1
                return True, remaining, retry_after

            self._store[key].append(now)
            remaining = max(0, max_requests - current - 1)
            return False, remaining, window_seconds

    async def _evict_expired(self, now: float):
        expired = [k for k, v in self._store.items() if not v or max(v) < now - 3600]
        for k in expired:
            del self._store[k]

    async def cleanup(self):
        async with self._lock:
            now = time.time()
            await self._evict_expired(now)


rate_store = RateLimitStore()

RATE_LIMITS = {
    "/api/auth/login": {"max": 10, "window": 60},
    "/api/auth/register": {"max": 5, "window": 60},
    "/api/registration-requests": {"max": 10, "window": 60},
    "/api/reports/export": {"max": 10, "window": 120},
    "/api/hakim/analyze": {"max": 5, "window": 60},
    "/api/auth/change-password": {"max": 5, "window": 300},
    # SECURITY (audit H-3): per-IP brute-force/enumeration limit on the
    # password recovery surface. Per-email limits are layered inside the
    # handlers (mirrors the `login_account:` pattern).
    "/api/auth/forgot-password": {"max": 20, "window": 3600},
    "/api/auth/reset-password": {"max": 20, "window": 3600},
    "/api/teachers/create": {"max": 20, "window": 60},
    "/api/classes/create": {"max": 30, "window": 60},
    "/api/student-wizard/create": {"max": 30, "window": 60},
    "/api/student-wizard/check-parent": {"max": 60, "window": 60},
    "/api/student-wizard/search-parents": {"max": 60, "window": 60},
}


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        # Security: never trust client-controlled X-Forwarded-For for rate-limit
        # keying. An attacker can rotate that header freely to bypass limits.
        # Always key on the actual TCP-level peer address which cannot be spoofed
        # by the client itself.
        client_ip = request.client.host if request.client else "unknown"

        matched_limits = None
        for pattern, limits in RATE_LIMITS.items():
            if path.startswith(pattern):
                matched_limits = limits
                key = f"{client_ip}:{pattern}"
                limited, remaining, retry_after = await rate_store.is_rate_limited(
                    key, limits["max"], limits["window"]
                )
                if limited:
                    logger.warning(f"Rate limited: {client_ip} on {pattern}")
                    return JSONResponse(
                        status_code=429,
                        content={
                            "success": False,
                            "error": {
                                "code": "RATE_LIMITED",
                                "message": "Too many requests",
                                "message_ar": "عدد الطلبات تجاوز الحد المسموح. يرجى المحاولة لاحقاً",
                            },
                        },
                        headers={
                            "X-RateLimit-Limit": str(limits["max"]),
                            "X-RateLimit-Remaining": "0",
                            "Retry-After": str(retry_after),
                        },
                    )
                break

        response = await call_next(request)

        if matched_limits is not None:
            response.headers["X-RateLimit-Limit"] = str(matched_limits["max"])
            response.headers["X-RateLimit-Remaining"] = str(remaining)

        return response
