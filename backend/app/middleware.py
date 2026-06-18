"""
NASSAQ — Middleware configuration.
"""
import asyncio
import logging
import time
import uuid as _uuid
from datetime import datetime, timezone

from fastapi import FastAPI, Request
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from db import async_session_factory
from dependencies import db, JWT_SECRET, JWT_ALGORITHM
from middleware.rate_limiter import RateLimitMiddleware
from middleware.error_handler import ErrorHandlerMiddleware
from middleware.request_tracing import RequestTracingMiddleware

logger = logging.getLogger("nassaq")


def register_middleware(app: FastAPI):
    app.add_middleware(ErrorHandlerMiddleware)
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(RequestTracingMiddleware)

    @app.middleware("http")
    async def pg_session_middleware(request: Request, call_next):
        _p = request.url.path
        if _p.startswith("/api/ws/") or _p == "/ws":
            return await call_next(request)

        import os as _os
        if _os.environ.get("TESTING") == "1":
            existing = db.session
            if existing is not None:
                try:
                    await existing.flush()
                except Exception:
                    pass
                return await call_next(request)

        async with async_session_factory() as session:
            db.set_session(session)
            try:
                response = await call_next(request)
                if not session.in_transaction():
                    return response
                if request.method in ("GET", "HEAD", "OPTIONS"):
                    await session.rollback()
                    return response
                if session.is_active and not session.in_nested_transaction():
                    try:
                        await session.commit()
                    except Exception:
                        await session.rollback()
                        raise
                else:
                    await session.rollback()
                return response
            except Exception:
                try:
                    await session.rollback()
                except Exception:
                    pass
                raise
            finally:
                db.set_session(None)

    _PRIVATE_NOINDEX_PREFIXES = (
        "/principal/",
        "/admin/",
        "/teacher/",
        "/parent/",
        "/school/",
        "/api/",
    )

    @app.middleware("http")
    async def add_security_headers(request: Request, call_next):
        path = request.url.path
        if path == "/api/ws/notifications" or path == "/ws":
            return await call_next(request)
        response = await call_next(request)
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        if any(path.startswith(p) for p in _PRIVATE_NOINDEX_PREFIXES):
            response.headers["X-Robots-Tag"] = "noindex, nofollow, noarchive, nosnippet"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        # B-20: X-XSS-Protection is deprecated and can introduce vulnerabilities;
        # modern browsers ignore it. Removed in favour of CSP.
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=(), payment=()"
        # B-02: Removed 'unsafe-eval' (CRA build doesn't need it).
        # 'unsafe-inline' for scripts retained until the SPA migrates to nonces;
        # CSS still needs unsafe-inline because Tailwind/CRA inject inline style attrs.
        # SECURITY (audit H-4): tactical CSP tightening — adds object-src,
        # base-uri, form-action, and trims connect-src. 'unsafe-inline' for
        # scripts is intentionally retained until the SPA migrates to nonces
        # (Phase 3 — see docs/security/PHASE1_REPORT.md).
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com data:; "
            "img-src 'self' data: blob: https:; "
            "media-src 'self' https:; "
            "connect-src 'self' wss: ws:; "
            "object-src 'none'; "
            "frame-src blob:; "
            "base-uri 'none'; "
            "form-action 'self'; "
            "frame-ancestors 'none';"
        )
        # B-03: aggressive cache for hashed/static asset bundles. CRA writes
        # files with content hashes (e.g. main.25304d41.js) so they are
        # safe to cache for a year.
        if path.startswith("/static/"):
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return response

    @app.middleware("http")
    async def audit_log_middleware(request: Request, call_next):
        # B-26: imports moved to module top
        from middleware.audit_middleware import _should_audit, _derive_action, _derive_severity, parse_device_info, _extract_real_ip, _sanitize_query_params as _sanitize_qp

        method = request.method
        path = request.url.path

        if path.startswith("/api/ws/") or path == "/ws":
            return await call_next(request)

        if not _should_audit(method, path):
            return await call_next(request)

        start = time.time()
        response = await call_next(request)
        duration_ms = round((time.time() - start) * 1000, 1)

        try:
            # B-08: prefer cached user from request.state (populated by
            # get_current_user / RequestTracingMiddleware) and only re-decode
            # the JWT as a last resort. Avoids duplicate per-request crypto.
            user_id = user_name = user_role = user_email = tenant_id = None
            cached = getattr(request.state, "user", None) or getattr(request.state, "auth_user", None)
            if cached:
                u = cached
                user_id = str(u.get("id") or u.get("user_id") or "")
                user_name = u.get("full_name") or u.get("name")
                user_role = u.get("role")
                user_email = u.get("email")
                tenant_id = u.get("tenant_id")
            else:
                try:
                    auth_hdr = request.headers.get("authorization", "")
                    if auth_hdr.startswith("Bearer "):
                        import jwt as _jwt
                        payload = _jwt.decode(auth_hdr[7:], JWT_SECRET, algorithms=[JWT_ALGORITHM])
                        user_id = payload.get("sub")
                        user_role = payload.get("role")
                        user_email = payload.get("email")
                        tenant_id = payload.get("tenant_id")
                        # Cache for any later middleware in this request
                        request.state.auth_user = {
                            "id": user_id, "role": user_role,
                            "email": user_email, "tenant_id": tenant_id,
                        }
                except Exception as e:
                    logger.debug(f"Audit middleware: failed to resolve user details from token: {e}")

            raw_ua = request.headers.get("user-agent", "")
            device_info = parse_device_info(raw_ua)
            ip_address = _extract_real_ip(request)
            action = _derive_action(method, path)
            severity = _derive_severity(method, path, response.status_code)

            audit_doc = {
                "id": str(_uuid.uuid4()),
                "action": action,
                "severity": severity,
                "performed_by": user_id or None,
                "actor_name": user_name,
                "actor_role": user_role,
                "actor_email": user_email,
                "tenant_id": tenant_id,
                "entity_type": action.split(".")[0] if "." in action else "system",
                "ip_address": ip_address,
                "user_agent": raw_ua,
                "device_info": device_info,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "details": {
                    "method": method,
                    "path": path,
                    "query_params": _sanitize_qp(dict(request.query_params)),
                    "status_code": response.status_code,
                    "duration_ms": duration_ms,
                    "success": 200 <= response.status_code < 400,
                },
            }

            async def _persist_audit(doc):
                try:
                    from repositories import Repos
                    async with async_session_factory() as audit_session:
                        audit_repos = Repos(audit_session)
                        await audit_repos.audit_logs.insert_one(doc)
                        await audit_session.commit()
                except Exception as _e:
                    import logging as _lg
                    _lg.getLogger("nassaq.audit").debug(f"Audit persist failed: {_e}")

            task = asyncio.create_task(_persist_audit(audit_doc))
            task.add_done_callback(lambda t: t.exception())
        except Exception as _e:
            import logging as _lg
            _lg.getLogger("nassaq.audit").debug(f"Audit middleware: {_e}")

        return response

    from config import config as _cfg
    _cors_origins = _cfg.CORS_ORIGINS
    _allow_creds = _cors_origins != ["*"]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins,
        allow_credentials=_allow_creds,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # B-22: wire ALLOWED_HOSTS into Starlette's TrustedHostMiddleware so the
    # config setting is actually enforced. Wildcard ("*") = no restriction.
    _allowed_hosts = _cfg.ALLOWED_HOSTS
    if _allowed_hosts and _allowed_hosts != ["*"]:
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=_allowed_hosts)
