"""
NASSAQ — Middleware configuration.
"""
import logging
from fastapi import FastAPI, Request
from starlette.middleware.cors import CORSMiddleware

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

    @app.middleware("http")
    async def add_security_headers(request: Request, call_next):
        if request.url.path == "/api/ws/notifications" or request.url.path == "/ws":
            return await call_next(request)
        response = await call_next(request)
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=(), payment=()"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com data:; "
            "img-src 'self' data: blob: https:; "
            "media-src 'self' https:; "
            "connect-src 'self' wss: ws:; "
            "frame-ancestors 'none';"
        )
        return response

    @app.middleware("http")
    async def audit_log_middleware(request: Request, call_next):
        from middleware.audit_middleware import _should_audit, _derive_action, _derive_severity, parse_device_info, _extract_real_ip, _sanitize_query_params as _sanitize_qp
        import asyncio, time, uuid as _uuid
        from datetime import datetime, timezone

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
            user_id = user_name = user_role = user_email = tenant_id = None
            if hasattr(request.state, "user") and request.state.user:
                u = request.state.user
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
