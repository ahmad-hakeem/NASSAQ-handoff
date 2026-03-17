"""
NASSAQ Middleware Package
طبقة الوسيط لمنصة نَسَّق
"""

from middleware.rbac import (
    Permission,
    ROLE_PERMISSIONS,
    RBACMiddleware,
    require_permission,
    require_any_permission,
    require_tenant_access,
)

from middleware.tenant_isolation import (
    PLATFORM_ROLES,
    TenantIsolation,
    tenant_scoped,
    validate_resource_tenant,
    TenantAwareQuery,
)

__all__ = [
    # RBAC
    "Permission",
    "ROLE_PERMISSIONS",
    "RBACMiddleware",
    "require_permission",
    "require_any_permission",
    "require_tenant_access",
    
    # Tenant Isolation
    "PLATFORM_ROLES",
    "TenantIsolation",
    "tenant_scoped",
    "validate_resource_tenant",
    "TenantAwareQuery",
]
