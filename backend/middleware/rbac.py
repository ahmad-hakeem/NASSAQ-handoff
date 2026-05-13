"""
NASSAQ RBAC Middleware
نظام الصلاحيات والتحكم في الوصول

Provides:
- Role-based access control
- Permission-level authorization
- Tenant-scoped access
- Action-level permissions
"""

from typing import List, Optional, Dict, Any, Callable
from functools import wraps
from fastapi import HTTPException, Depends, Request
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class Permission(str, Enum):
    """Fine-grained permissions"""
    # User Management
    USERS_VIEW = "users.view"
    USERS_CREATE = "users.create"
    USERS_EDIT = "users.edit"
    USERS_DELETE = "users.delete"
    USERS_SUSPEND = "users.suspend"
    USERS_MANAGE_ROLES = "users.manage_roles"
    
    # School/Tenant Management
    TENANTS_VIEW = "tenants.view"
    TENANTS_CREATE = "tenants.create"
    TENANTS_EDIT = "tenants.edit"
    TENANTS_DELETE = "tenants.delete"
    TENANTS_SUSPEND = "tenants.suspend"
    TENANTS_MANAGE_AI = "tenants.manage_ai"
    
    # Academic Management
    ACADEMIC_VIEW = "academic.view"
    ACADEMIC_MANAGE_STAGES = "academic.manage_stages"
    ACADEMIC_MANAGE_GRADES = "academic.manage_grades"
    ACADEMIC_MANAGE_SECTIONS = "academic.manage_sections"
    ACADEMIC_MANAGE_SUBJECTS = "academic.manage_subjects"
    
    # Scheduling
    SCHEDULE_VIEW = "schedule.view"
    SCHEDULE_CREATE = "schedule.create"
    SCHEDULE_EDIT = "schedule.edit"
    SCHEDULE_PUBLISH = "schedule.publish"
    SCHEDULE_DELETE = "schedule.delete"
    
    # Attendance
    ATTENDANCE_VIEW = "attendance.view"
    ATTENDANCE_RECORD = "attendance.record"
    ATTENDANCE_EDIT = "attendance.edit"
    ATTENDANCE_APPROVE_EXCUSE = "attendance.approve_excuse"
    ATTENDANCE_REPORTS = "attendance.reports"
    
    # Assessments & Grades
    ASSESSMENTS_VIEW = "assessments.view"
    ASSESSMENTS_CREATE = "assessments.create"
    ASSESSMENTS_EDIT = "assessments.edit"
    ASSESSMENTS_DELETE = "assessments.delete"
    ASSESSMENTS_GRADE = "assessments.grade"
    ASSESSMENTS_PUBLISH = "assessments.publish"
    
    # Behaviour
    BEHAVIOUR_VIEW = "behaviour.view"
    BEHAVIOUR_RECORD = "behaviour.record"
    BEHAVIOUR_EDIT = "behaviour.edit"
    BEHAVIOUR_REVIEW = "behaviour.review"
    BEHAVIOUR_DISCIPLINARY = "behaviour.disciplinary"
    
    # Notifications
    NOTIFICATIONS_VIEW = "notifications.view"
    NOTIFICATIONS_SEND = "notifications.send"
    NOTIFICATIONS_BULK = "notifications.bulk"
    NOTIFICATIONS_MANAGE_TEMPLATES = "notifications.manage_templates"
    
    # Settings
    SETTINGS_VIEW = "settings.view"
    SETTINGS_EDIT = "settings.edit"
    SETTINGS_SECURITY = "settings.security"
    SETTINGS_API_KEYS = "settings.api_keys"
    
    # Analytics & Reports
    ANALYTICS_VIEW = "analytics.view"
    ANALYTICS_EXPORT = "analytics.export"
    ANALYTICS_AI = "analytics.ai"
    
    # Audit
    AUDIT_VIEW = "audit.view"
    AUDIT_EXPORT = "audit.export"
    # Task #248 — IT workspace audit-log view. Granted to
    # `independent_teacher` only; the route layer pins
    # ``school_id == itw_{user_id}`` on every read and strips
    # sensitive keys from ``details`` before serialisation.
    AUDIT_READ_OWN_WORKSPACE = "audit.read_own_workspace"
    # Task #273 — IT analytics dashboard. Read-only; the route pins
    # ``tenant_id == itw_{user_id}`` on every aggregation query and
    # never widens scope by request param.
    ANALYTICS_READ_OWN_WORKSPACE = "analytics.read_own_workspace"
    
    # Students (workspace-scoped capabilities)
    STUDENTS_BULK_IMPORT_WORKSPACE = "students.bulk_import_workspace"

    # System
    SYSTEM_MONITOR = "system.monitor"
    SYSTEM_CONFIGURE = "system.configure"
    SYSTEM_INTEGRATIONS = "system.integrations"

    # Calendar / Events — IT Phase 2 §6.3 personal events.
    # `events.author_own` lets the holder create/read/update/delete only the
    # events they own inside their own workspace. It is intentionally NOT a
    # superset of school-wide calendar permissions used by principals.
    EVENTS_AUTHOR_OWN = "events.author_own"
    # Phase 2 §6.4 (Task #209) — IT light AI lesson-planning assistant.
    # Granted to `independent_teacher` only; the route layer enforces
    # workspace pinning + daily quota. No MFA step-up (low-sensitivity).
    AI_LESSON_PLANS = "ai.lesson_plans"

    # IT §6.7 — Cross-workspace co-teaching (Task #210). The ONLY
    # sanctioned cross-tenant data path. Granted to the host IT so they
    # can invite/revoke a collaborator on a per-class basis. The receiving
    # IT is gated by their own role + the row's collaborator_school_id;
    # they do not need this permission to accept or to read shared data.
    WORKSPACE_COLLAB_MANAGE = "workspace.collab_manage"

    # IT §6.8 — Workspace lifecycle (export + soft-delete)
    WORKSPACE_EXPORT = "workspace.export"
    WORKSPACE_SOFT_DELETE = "workspace.soft_delete"


# Role to Permissions Mapping
ROLE_PERMISSIONS: Dict[str, List[str]] = {
    "platform_admin": [p.value for p in Permission],  # All permissions
    
    "platform_operations_manager": [
        Permission.TENANTS_VIEW.value,
        Permission.TENANTS_CREATE.value,
        Permission.TENANTS_EDIT.value,
        Permission.TENANTS_SUSPEND.value,
        Permission.USERS_VIEW.value,
        Permission.USERS_CREATE.value,
        Permission.ANALYTICS_VIEW.value,
        Permission.SYSTEM_MONITOR.value,
    ],
    
    "platform_technical_admin": [
        Permission.SYSTEM_MONITOR.value,
        Permission.SYSTEM_CONFIGURE.value,
        Permission.SYSTEM_INTEGRATIONS.value,
        Permission.SETTINGS_VIEW.value,
        Permission.SETTINGS_EDIT.value,
        Permission.AUDIT_VIEW.value,
    ],
    
    "platform_support_specialist": [
        Permission.USERS_VIEW.value,
        Permission.TENANTS_VIEW.value,
        Permission.NOTIFICATIONS_SEND.value,
        Permission.AUDIT_VIEW.value,
    ],
    
    "platform_data_analyst": [
        Permission.ANALYTICS_VIEW.value,
        Permission.ANALYTICS_EXPORT.value,
        Permission.ANALYTICS_AI.value,
        Permission.AUDIT_VIEW.value,
    ],
    
    "platform_security_officer": [
        Permission.AUDIT_VIEW.value,
        Permission.AUDIT_EXPORT.value,
        Permission.SETTINGS_SECURITY.value,
        Permission.USERS_VIEW.value,
        Permission.USERS_SUSPEND.value,
    ],
    
    "school_principal": [
        # Full school management
        Permission.USERS_VIEW.value,
        Permission.USERS_CREATE.value,
        Permission.USERS_EDIT.value,
        Permission.USERS_SUSPEND.value,
        Permission.ACADEMIC_VIEW.value,
        Permission.ACADEMIC_MANAGE_STAGES.value,
        Permission.ACADEMIC_MANAGE_GRADES.value,
        Permission.ACADEMIC_MANAGE_SECTIONS.value,
        Permission.ACADEMIC_MANAGE_SUBJECTS.value,
        Permission.SCHEDULE_VIEW.value,
        Permission.SCHEDULE_CREATE.value,
        Permission.SCHEDULE_EDIT.value,
        Permission.SCHEDULE_PUBLISH.value,
        Permission.ATTENDANCE_VIEW.value,
        Permission.ATTENDANCE_REPORTS.value,
        Permission.ATTENDANCE_APPROVE_EXCUSE.value,
        Permission.ASSESSMENTS_VIEW.value,
        Permission.BEHAVIOUR_VIEW.value,
        Permission.BEHAVIOUR_REVIEW.value,
        Permission.BEHAVIOUR_DISCIPLINARY.value,
        Permission.NOTIFICATIONS_SEND.value,
        Permission.NOTIFICATIONS_BULK.value,
        Permission.ANALYTICS_VIEW.value,
        Permission.ANALYTICS_EXPORT.value,
    ],
    
    "school_admin": [
        Permission.USERS_VIEW.value,
        Permission.USERS_CREATE.value,
        Permission.USERS_EDIT.value,
        Permission.ACADEMIC_VIEW.value,
        Permission.ACADEMIC_MANAGE_SECTIONS.value,
        Permission.SCHEDULE_VIEW.value,
        Permission.ATTENDANCE_VIEW.value,
        Permission.ATTENDANCE_REPORTS.value,
        Permission.NOTIFICATIONS_SEND.value,
    ],
    
    "teacher": [
        Permission.ACADEMIC_VIEW.value,
        Permission.SCHEDULE_VIEW.value,
        Permission.ATTENDANCE_VIEW.value,
        Permission.ATTENDANCE_RECORD.value,
        Permission.ASSESSMENTS_VIEW.value,
        Permission.ASSESSMENTS_CREATE.value,
        Permission.ASSESSMENTS_EDIT.value,
        Permission.ASSESSMENTS_GRADE.value,
        Permission.BEHAVIOUR_VIEW.value,
        Permission.BEHAVIOUR_RECORD.value,
        Permission.NOTIFICATIONS_VIEW.value,
        Permission.NOTIFICATIONS_SEND.value,
    ],
    
    "independent_teacher": [
        Permission.WORKSPACE_EXPORT.value,
        Permission.WORKSPACE_SOFT_DELETE.value,
        Permission.SCHEDULE_VIEW.value,
        Permission.ATTENDANCE_VIEW.value,
        Permission.ATTENDANCE_RECORD.value,
        Permission.ASSESSMENTS_VIEW.value,
        Permission.ASSESSMENTS_CREATE.value,
        Permission.ASSESSMENTS_EDIT.value,
        Permission.ASSESSMENTS_GRADE.value,
        Permission.BEHAVIOUR_VIEW.value,
        Permission.BEHAVIOUR_RECORD.value,
        Permission.NOTIFICATIONS_VIEW.value,
        # Phase 1 §5.6 (Task #198) — IT may send notifications, but only
        # to the two cohorts exposed by /independent-teacher/communication
        # /recipients. The send paths in notification_routes_mod.py
        # enforce per-recipient tenant validation; recipient_role is
        # rejected outright for IT callers.
        Permission.NOTIFICATIONS_SEND.value,
        # Phase 2 §6.3 (Task #208) — IT personal calendar events. Scope
        # is enforced at the route layer (workspace tenant + caller as
        # author); the permission only signals UI eligibility.
        Permission.EVENTS_AUTHOR_OWN.value,
        # Phase 2 §6.1 (#207) — workspace-aware bulk student import.
        # Backend gates the actual /commit path with require_recent_mfa_403.
        Permission.STUDENTS_BULK_IMPORT_WORKSPACE.value,
        # §6.7 — host IT may invite/revoke a single collaborator per class.
        Permission.WORKSPACE_COLLAB_MANAGE.value,
        # Phase 2 §6.4 (#209) — light AI lesson-planning assistant.
        # No MFA step-up (low-sensitivity); daily quota enforced server-side.
        Permission.AI_LESSON_PLANS.value,
        # Task #248 — IT workspace audit-log view. Read-only; the route
        # pins school_id == itw_{user_id} and strips sensitive keys from
        # details before serialisation.
        Permission.AUDIT_READ_OWN_WORKSPACE.value,
        # Task #273 — IT analytics dashboard. Read-only aggregations
        # over the caller's own workspace; the route pins
        # ``tenant_id == itw_{user_id}`` and never honours cross-ws ids.
        Permission.ANALYTICS_READ_OWN_WORKSPACE.value,
    ],
    
    "student": [
        Permission.SCHEDULE_VIEW.value,
        Permission.ASSESSMENTS_VIEW.value,
        Permission.ATTENDANCE_VIEW.value,
        Permission.NOTIFICATIONS_VIEW.value,
    ],
    
    "parent": [
        Permission.ATTENDANCE_VIEW.value,
        Permission.ASSESSMENTS_VIEW.value,
        Permission.BEHAVIOUR_VIEW.value,
        Permission.NOTIFICATIONS_VIEW.value,
    ],
    
    "testing_account": [
        Permission.USERS_VIEW.value,
        Permission.TENANTS_VIEW.value,
    ],
}


class RBACMiddleware:
    """
    Role-Based Access Control Middleware
    """
    
    @staticmethod
    def get_user_permissions(role: str, custom_permissions: List[str] = None) -> List[str]:
        """Get all permissions for a user based on role and custom permissions"""
        base_permissions = ROLE_PERMISSIONS.get(role, [])
        
        if custom_permissions:
            # Merge with custom permissions
            all_permissions = list(set(base_permissions + custom_permissions))
            return all_permissions
        
        return base_permissions
    
    @staticmethod
    def has_permission(user: Dict[str, Any], required_permission: str) -> bool:
        """Check if user has a specific permission"""
        role = user.get("role") or user.get("primary_role")
        custom_permissions = user.get("permissions", [])
        
        user_permissions = RBACMiddleware.get_user_permissions(role, custom_permissions)
        
        return required_permission in user_permissions
    
    @staticmethod
    def has_any_permission(user: Dict[str, Any], permissions: List[str]) -> bool:
        """Check if user has any of the specified permissions"""
        for perm in permissions:
            if RBACMiddleware.has_permission(user, perm):
                return True
        return False
    
    @staticmethod
    def has_all_permissions(user: Dict[str, Any], permissions: List[str]) -> bool:
        """Check if user has all specified permissions"""
        for perm in permissions:
            if not RBACMiddleware.has_permission(user, perm):
                return False
        return True
    
    @staticmethod
    def check_tenant_access(user: Dict[str, Any], tenant_id: str) -> bool:
        """Check if user has access to a specific tenant"""
        user_tenant = user.get("tenant_id") or user.get("primary_tenant_id")
        user_role = user.get("role") or user.get("primary_role")
        
        # Platform admins and platform roles have access to all tenants
        platform_roles = [
            "platform_admin",
            "platform_operations_manager",
            "platform_technical_admin",
            "platform_support_specialist",
            "platform_data_analyst",
            "platform_security_officer",
        ]
        
        if user_role in platform_roles:
            return True
        
        # Other users can only access their own tenant
        return user_tenant == tenant_id


def require_permission(permission: str):
    """Decorator to require a specific permission"""
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Get current_user from kwargs
            current_user = kwargs.get("current_user")
            
            if not current_user:
                raise HTTPException(status_code=401, detail="غير مصادق")
            
            if not RBACMiddleware.has_permission(current_user, permission):
                logger.warning(
                    f"Permission denied: {current_user.get('id')} attempted {permission}"
                )
                raise HTTPException(
                    status_code=403,
                    detail=f"ليس لديك صلاحية: {permission}"
                )
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator


def require_any_permission(permissions: List[str]):
    """Decorator to require any of the specified permissions"""
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            current_user = kwargs.get("current_user")
            
            if not current_user:
                raise HTTPException(status_code=401, detail="غير مصادق")
            
            if not RBACMiddleware.has_any_permission(current_user, permissions):
                logger.warning(
                    f"Permission denied: {current_user.get('id')} needs one of {permissions}"
                )
                raise HTTPException(
                    status_code=403,
                    detail="ليس لديك الصلاحيات المطلوبة"
                )
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator


def require_tenant_access(tenant_id_param: str = "tenant_id"):
    """Decorator to ensure user has access to the specified tenant"""
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            current_user = kwargs.get("current_user")
            tenant_id = kwargs.get(tenant_id_param)
            
            if not current_user:
                raise HTTPException(status_code=401, detail="غير مصادق")
            
            if tenant_id and not RBACMiddleware.check_tenant_access(current_user, tenant_id):
                logger.warning(
                    f"Tenant access denied: {current_user.get('id')} to tenant {tenant_id}"
                )
                raise HTTPException(
                    status_code=403,
                    detail="لا يمكنك الوصول إلى بيانات هذه المدرسة"
                )
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator


# Export
__all__ = [
    "Permission",
    "ROLE_PERMISSIONS",
    "RBACMiddleware",
    "require_permission",
    "require_any_permission",
    "require_tenant_access",
]
