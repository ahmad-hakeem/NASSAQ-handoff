"""
NASSAQ Audit Middleware
Middleware للتسجيل التلقائي للعمليات

Provides:
- Automatic request/response logging for sensitive endpoints
- Performance monitoring
- Error tracking
"""

from typing import Callable, Dict, Any
from datetime import datetime, timezone
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
import time
import json
import logging

logger = logging.getLogger(__name__)

# Endpoints that should be audited automatically
AUDITED_ENDPOINTS = {
    # Auth
    "POST:/api/auth/login": "auth.login",
    "POST:/api/auth/logout": "auth.logout",
    "POST:/api/auth/register": "auth.register",
    
    # Users
    "POST:/api/users/create": "user.created",
    "PUT:/api/users/": "user.updated",
    "DELETE:/api/users/": "user.deleted",
    
    # Tenants/Schools
    "POST:/api/tenants/create": "tenant.created",
    "PUT:/api/tenants/": "tenant.updated",
    "DELETE:/api/tenants/": "tenant.deleted",
    
    # Schedules
    "POST:/api/schedules/generate": "schedule.created",
    "PUT:/api/schedules/publish": "schedule.published",
    
    # Attendance
    "POST:/api/attendance/record": "attendance.recorded",
    "POST:/api/attendance/bulk": "attendance.bulk_recorded",
    
    # Assessments
    "POST:/api/assessments/create": "academic.assessment_created",
    "POST:/api/grades/record": "academic.grade_recorded",
    
    # Behaviour
    "POST:/api/behaviour/note": "behaviour.note_created",
    "POST:/api/behaviour/disciplinary": "behaviour.action_created",
    
    # Import
    "POST:/api/import/students": "data.imported",
    
    # Settings
    "PUT:/api/settings/": "settings.updated",
    
    # Export
    "GET:/api/export/": "data.exported",
}


class AuditMiddleware(BaseHTTPMiddleware):
    """
    Middleware for automatic audit logging
    """
    
    def __init__(self, app, db=None):
        super().__init__(app)
        self.db = db
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.time()
        
        # Get request details
        method = request.method
        path = request.url.path
        endpoint_key = f"{method}:{path}"
        
        # Check if this endpoint should be audited
        should_audit = False
        audit_action = None
        
        for pattern, action in AUDITED_ENDPOINTS.items():
            pattern_method, pattern_path = pattern.split(":", 1)
            if method == pattern_method and path.startswith(pattern_path):
                should_audit = True
                audit_action = action
                break
        
        # Process request
        response = await call_next(request)
        
        # Calculate duration
        duration = time.time() - start_time
        
        # Log if needed
        if should_audit and self.db:
            try:
                await self._log_request(
                    request=request,
                    response=response,
                    action=audit_action,
                    duration=duration
                )
            except Exception as e:
                logger.error(f"Failed to log audit: {e}")
        
        # Add timing header
        response.headers["X-Response-Time"] = f"{duration:.3f}s"
        
        return response
    
    async def _log_request(
        self,
        request: Request,
        response: Response,
        action: str,
        duration: float
    ):
        """Log request to audit collection"""
        
        # Extract user from request state if available
        user_id = None
        tenant_id = None
        
        if hasattr(request.state, "user"):
            user = request.state.user
            user_id = str(user.get("id")) if user else None
            tenant_id = user.get("tenant_id") if user else None
        
        # Get IP and User-Agent
        ip_address = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")
        
        audit_doc = {
            "id": f"req_{datetime.now(timezone.utc).timestamp()}",
            "action": action,
            "severity": "low",
            "performed_by": user_id,
            "tenant_id": tenant_id,
            "entity_type": "request",
            "details": {
                "method": request.method,
                "path": str(request.url.path),
                "query_params": dict(request.query_params),
                "status_code": response.status_code,
                "duration_seconds": round(duration, 3),
                "success": 200 <= response.status_code < 400
            },
            "ip_address": ip_address,
            "user_agent": user_agent,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        if self.db:
            await self.db.audit_logs.insert_one(audit_doc)


def create_audit_middleware(db):
    """Factory function to create middleware with database"""
    return AuditMiddleware(app=None, db=db)


# Export
__all__ = ["AuditMiddleware", "create_audit_middleware", "AUDITED_ENDPOINTS"]
