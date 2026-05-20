"""
NASSAQ Rate Limiter Middleware

In-memory sliding-window rate limiting for critical endpoints.

PRODUCTION NOTE:
  This store is **process-local**. When running behind multiple workers
  (e.g. ``gunicorn -w 4``) each worker keeps its own counter, so
  effective limits are multiplied by the worker count. For strict
  distributed rate limiting, swap ``RateLimitStore`` for a Redis-backed
  implementation (e.g. redis INCR + EXPIRE).  The current design is
  intentional for single-worker Replit deployments. The Phase 2 audit
  (item M-3) tracks the move to a shared store; this module is wired to
  the new ``utils.trusted_proxy.extract_client_ip`` helper so that work
  can drop in without re-touching the keying logic.
"""
import time
import asyncio
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
import logging

from utils.trusted_proxy import extract_client_ip

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
    # ----- Task #169 Step 8 — MFA brute-force / abuse limits ----------
    # These are PER-IP outer limits. Per-identity (per-user, per-challenge)
    # caps are enforced inside the handlers (challenge attempts counter,
    # OTP send budget, recovery-code first-50-rows ceiling, etc.); both
    # layers are required because a single attacker can spread guesses
    # across many accounts but is bounded by their IP, while a credential
    # stuffer rotating IPs is bounded by the per-identity counters.
    "/api/auth/mfa/verify": {"max": 30, "window": 300},
    "/api/auth/mfa/email-otp/send": {"max": 6, "window": 300},
    "/api/auth/mfa/stepup/start": {"max": 30, "window": 300},
    "/api/auth/mfa/stepup/verify": {"max": 30, "window": 300},
    "/api/auth/mfa/webauthn/register/begin": {"max": 20, "window": 300},
    "/api/auth/mfa/webauthn/register/finish": {"max": 20, "window": 300},
    "/api/auth/mfa/webauthn/verify/begin": {"max": 30, "window": 300},
    "/api/auth/mfa/webauthn/verify/finish": {"max": 30, "window": 300},
    "/api/auth/mfa/totp/enroll/begin": {"max": 20, "window": 300},
    "/api/auth/mfa/totp/enroll/confirm": {"max": 20, "window": 300},
    "/api/auth/mfa/recovery-codes/regenerate": {"max": 5, "window": 3600},
    # NDJSON export is platform-admin only, but cap it anyway to prevent
    # accidental loops from hammering the DB.
    "/api/audit/mfa-export": {"max": 10, "window": 3600},
    "/api/audit/mfa-verify-chain": {"max": 30, "window": 3600},
    "/api/teachers/create": {"max": 20, "window": 60},
    "/api/classes/create": {"max": 30, "window": 60},
    "/api/student-wizard/create": {"max": 30, "window": 60},
    "/api/student-wizard/check-parent": {"max": 60, "window": 60},
    "/api/student-wizard/search-parents": {"max": 60, "window": 60},
    # SECURITY (task #438): parent-portal child routes include AI-backed
    # endpoints (insights, weekly-story) that trigger LLM calls on every
    # request.  A per-IP outer limit prevents a single parent account from
    # running a tight loop and burning shared model quota or degrading
    # portal responsiveness for other users.  Per-child AI caching
    # (inside the handler) provides a second, complementary defence.
    "/api/parent-portal/child/": {"max": 20, "window": 60},
    # SECURITY (task #446): the Hakim chat endpoint calls the live LLM on
    # every request and was previously unthrottled — any authenticated user
    # could script a tight loop and burn shared model quota.  20 requests
    # per 60 s is generous for interactive chat (≈ 1 message every 3 s)
    # while still bounding the blast radius of a single abusive account.
    # This mirrors the `/api/parent-portal/child/` limit applied in #438.
    "/api/hakim/chat": {"max": 20, "window": 60},
}


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        # SECURITY (audit C-1): we used to refuse XFF entirely, which made
        # per-IP limits useless behind Replit's edge (every request collapsed
        # to the proxy IP). The trusted-proxy helper honours XFF only when
        # the immediate peer is itself in the configured allow-list
        # (`TRUSTED_PROXY_CIDRS`); otherwise it falls back to the un-spoofable
        # peer address.
        client_ip = extract_client_ip(request)

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
