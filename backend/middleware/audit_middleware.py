"""
NASSAQ Audit Middleware
Middleware للتسجيل التلقائي الشامل لجميع الأحداث
"""

from typing import Callable, Dict, Any, Optional
from datetime import datetime, timezone
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
import time
import uuid
import re
import logging

logger = logging.getLogger(__name__)

# Paths to skip entirely (no audit value)
SKIP_PATHS = {
    "/api/auth/me",
    "/api/public/",
    "/api/health",
    "/api/system/health",
    "/api/notifications/unread-count",
    "/ws",
    "/api/ws/",
    "/__replco",
    "/static/",
    "/favicon",
}

# GET paths worth auditing (data access/export)
AUDIT_GET_PATHS = (
    "/api/export",
    "/api/bulk-export",
    "/api/reports/generate",
    "/api/audit/export",
)

# Method → default action prefix mapping
METHOD_ACTIONS = {
    "POST": "created",
    "PUT": "updated",
    "PATCH": "updated",
    "DELETE": "deleted",
}

# Path segment → entity type (used for action naming)
PATH_ENTITY_MAP = {
    "users": "user",
    "schools": "school",
    "tenants": "tenant",
    "students": "student",
    "teachers": "teacher",
    "classes": "class",
    "schedules": "schedule",
    "attendance": "attendance",
    "grades": "grade",
    "assessments": "assessment",
    "behaviour": "behaviour",
    "notifications": "notification",
    "messages": "message",
    "settings": "settings",
    "registration": "registration",
    "auth": "auth",
    "products": "product",
    "issues": "issue",
    "reports": "report",
    "export": "export",
    "import": "import",
    "bulk-import": "bulk_import",
    "bulk-export": "bulk_export",
    "roles": "role",
    "permissions": "permission",
    "invitations": "invitation",
    "sessions": "session",
    "platform": "platform",
    "admin": "admin",
    "security": "security",
}

# Method → severity
METHOD_SEVERITY = {
    "DELETE": "high",
    "POST": "medium",
    "PUT": "low",
    "PATCH": "low",
    "GET": "info",
}

# Override severity for specific patterns
HIGH_SEVERITY_PATTERNS = (
    "/auth/login",
    "/auth/password",
    "/users/suspend",
    "/users/delete",
    "/schools/suspend",
    "/security/",
    "/platform/",
    "/admin/",
)

CRITICAL_SEVERITY_PATTERNS = (
    "/tenants/delete",
    "/schools/delete",
    "/bulk-import",
    "/system/",
)


def parse_device_info(user_agent: Optional[str]) -> Dict[str, str]:
    """Parse user-agent string into structured device info"""
    if not user_agent:
        return {"browser": "غير معروف", "os": "غير معروف", "device_type": "حاسوب", "raw": ""}

    ua = user_agent.lower()

    # Browser detection
    if "edg/" in ua or "edghtml" in ua:
        browser = "Edge"
    elif "opr/" in ua or "opera" in ua:
        browser = "Opera"
    elif "chrome/" in ua and "chromium" not in ua:
        browser = "Chrome"
    elif "firefox/" in ua:
        browser = "Firefox"
    elif "safari/" in ua and "chrome" not in ua:
        browser = "Safari"
    elif "curl/" in ua:
        browser = "cURL"
    elif "python" in ua or "httpx" in ua or "requests" in ua:
        browser = "API Client"
    elif "postman" in ua:
        browser = "Postman"
    else:
        browser = "غير معروف"

    # OS detection
    if "windows nt" in ua:
        match = re.search(r"windows nt (\d+\.\d+)", ua)
        version = match.group(1) if match else ""
        versions = {"10.0": "10/11", "6.3": "8.1", "6.2": "8", "6.1": "7"}
        os_name = f"Windows {versions.get(version, version)}"
    elif "iphone" in ua:
        os_name = "iOS (iPhone)"
    elif "ipad" in ua:
        os_name = "iOS (iPad)"
    elif "android" in ua:
        match = re.search(r"android (\d+\.?\d*)", ua)
        ver = match.group(1) if match else ""
        os_name = f"Android {ver}"
    elif "mac os x" in ua or "macos" in ua:
        os_name = "macOS"
    elif "linux" in ua:
        os_name = "Linux"
    elif "cros" in ua:
        os_name = "ChromeOS"
    else:
        os_name = "غير معروف"

    # Device type
    if "mobile" in ua or "iphone" in ua:
        device_type = "هاتف محمول"
    elif "tablet" in ua or "ipad" in ua:
        device_type = "لوحي"
    elif browser in ("cURL", "API Client", "Postman"):
        device_type = "API"
    else:
        device_type = "حاسوب"

    return {
        "browser": browser,
        "os": os_name,
        "device_type": device_type,
        "raw": user_agent[:300],
    }


def _derive_action(method: str, path: str) -> str:
    """Derive a meaningful action string from HTTP method + path"""
    # Specific overrides first
    if "/auth/login" in path:
        return "auth.login"
    if "/auth/logout" in path:
        return "auth.logout"
    if "/auth/register" in path:
        return "auth.register"
    if "/auth/password" in path:
        return "auth.password_changed"
    if "/export" in path:
        return "data.exported"
    if "/import" in path:
        return "data.imported"
    if "/bulk-import" in path:
        return "data.bulk_imported"
    if "/generate" in path and "schedule" in path:
        return "schedule.generated"
    if "/publish" in path and "schedule" in path:
        return "schedule.published"
    if "/suspend" in path:
        return f"{'user' if 'user' in path else 'tenant'}.suspended"
    if "/activate" in path:
        return f"{'user' if 'user' in path else 'tenant'}.activated"
    if "/reports/generate" in path:
        return "report.generated"

    # Generic: entity + action
    parts = [p for p in path.split("/") if p and not p.startswith("{") and p != "api"]
    entity = "system"
    for part in parts:
        if part in PATH_ENTITY_MAP:
            entity = PATH_ENTITY_MAP[part]
            break

    verb = METHOD_ACTIONS.get(method, "accessed")
    return f"{entity}.{verb}"


def _derive_severity(method: str, path: str, status_code: int) -> str:
    """Assign severity based on method, path, and response status"""
    if status_code >= 500:
        return "high"
    if status_code >= 400:
        return "medium"

    # Check critical patterns first
    for pattern in CRITICAL_SEVERITY_PATTERNS:
        if pattern in path:
            return "critical"

    # High severity patterns
    for pattern in HIGH_SEVERITY_PATTERNS:
        if pattern in path:
            return "high"

    return METHOD_SEVERITY.get(method, "info")


def _should_audit(method: str, path: str) -> bool:
    """Decide whether this request should be audited"""
    # Skip health checks, websockets, static assets
    for skip in SKIP_PATHS:
        if path.startswith(skip):
            return False

    # Always audit write operations on /api/
    if method in ("POST", "PUT", "PATCH", "DELETE") and path.startswith("/api/"):
        return True

    # Audit specific GET paths
    if method == "GET":
        for audit_path in AUDIT_GET_PATHS:
            if path.startswith(audit_path):
                return True

    return False


def _extract_real_ip(request: Request) -> str:
    """Extract real IP, accounting for proxies"""
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip
    return request.client.host if request.client else "غير معروف"


class AuditMiddleware(BaseHTTPMiddleware):
    """Comprehensive audit middleware — logs ALL system events automatically"""

    def __init__(self, app, db=None):
        super().__init__(app)
        self.db = db

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.time()

        method = request.method
        path = request.url.path

        if not _should_audit(method, path):
            return await call_next(request)

        response = await call_next(request)
        duration_ms = round((time.time() - start_time) * 1000, 1)

        if self.db:
            try:
                await self._log_event(request, response, method, path, duration_ms)
            except Exception as e:
                logger.error(f"Audit middleware log failed: {e}")

        response.headers["X-Response-Time"] = f"{duration_ms:.0f}ms"
        return response

    async def _log_event(
        self,
        request: Request,
        response: Response,
        method: str,
        path: str,
        duration_ms: float,
    ):
        """Build and persist the audit log entry"""

        # ── User identity ──────────────────────────────────────
        user_id = None
        user_name = None
        user_role = None
        user_email = None
        tenant_id = None

        if hasattr(request.state, "user") and request.state.user:
            u = request.state.user
            user_id = str(u.get("id", u.get("user_id", ""))) or None
            user_name = u.get("full_name") or u.get("name")
            user_role = u.get("role")
            user_email = u.get("email")
            tenant_id = u.get("tenant_id")
        else:
            # Try to decode JWT for name/role without full validation
            try:
                auth_header = request.headers.get("authorization", "")
                if auth_header.startswith("Bearer "):
                    import jose.jwt as _jwt
                    from config import JWT_SECRET, JWT_ALGORITHM
                    token = auth_header[7:]
                    payload = _jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
                    user_id = payload.get("sub")
                    user_role = payload.get("role")
                    user_email = payload.get("email")
                    tenant_id = payload.get("tenant_id")
                    # Try to resolve name
                    if user_id and self.db:
                        u_doc = await self.db.users.find_one(
                            {"id": user_id},
                            {"full_name": 1, "email": 1, "role": 1, "tenant_id": 1}
                        )
                        if u_doc:
                            user_name = u_doc.get("full_name")
                            user_email = u_doc.get("email") or user_email
                            user_role = u_doc.get("role") or user_role
                            tenant_id = u_doc.get("tenant_id") or tenant_id
            except Exception as e:
                logger.debug(f"Failed to resolve user details from token: {e}")

        # ── Device info ────────────────────────────────────────
        raw_ua = request.headers.get("user-agent", "")
        device_info = parse_device_info(raw_ua)
        ip_address = _extract_real_ip(request)

        # ── Action & severity ──────────────────────────────────
        action = _derive_action(method, path)
        severity = _derive_severity(method, path, response.status_code)

        # ── Build doc ──────────────────────────────────────────
        audit_doc = {
            "id": str(uuid.uuid4()),
            "action": action,
            "severity": severity,
            "performed_by": user_id,
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
                "query_params": dict(request.query_params),
                "status_code": response.status_code,
                "duration_ms": duration_ms,
                "success": 200 <= response.status_code < 400,
            },
        }

        await self.db.audit_logs.insert_one(audit_doc)


def create_audit_middleware(db):
    return AuditMiddleware(app=None, db=db)


__all__ = ["AuditMiddleware", "create_audit_middleware", "parse_device_info"]
