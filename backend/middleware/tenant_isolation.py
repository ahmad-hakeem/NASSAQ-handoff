"""
NASSAQ Tenant Isolation Middleware
نظام عزل البيانات بين المستأجرين

Provides:
- Automatic tenant filtering for queries
- Data leakage prevention
- Cross-tenant access control
"""

from typing import Dict, Any, Optional, List
from fastapi import HTTPException, Request
from functools import wraps
import logging

logger = logging.getLogger(__name__)


# Platform-level roles that can access all tenants
PLATFORM_ROLES = [
    "platform_admin",
    "platform_operations_manager",
    "platform_technical_admin",
    "platform_support_specialist",
    "platform_data_analyst",
    "platform_security_officer",
]


class TenantIsolation:
    """
    Tenant Isolation Service
    Ensures data is properly scoped to tenants
    """
    
    @staticmethod
    def get_user_tenant_id(user: Dict[str, Any]) -> Optional[str]:
        """Extract tenant ID from user"""
        return user.get("tenant_id") or user.get("primary_tenant_id")
    
    @staticmethod
    def is_platform_user(user: Dict[str, Any]) -> bool:
        """Check if user is a platform-level user"""
        role = user.get("role") or user.get("primary_role")
        return role in PLATFORM_ROLES
    
    @staticmethod
    def get_accessible_tenant_ids(user: Dict[str, Any]) -> List[str]:
        """Get list of tenant IDs the user can access"""
        if TenantIsolation.is_platform_user(user):
            # Platform users can access all tenants (return None to indicate no filter)
            return None
        
        tenant_id = TenantIsolation.get_user_tenant_id(user)
        
        # Check for linked roles with different tenants
        linked_roles = user.get("linked_roles", [])
        tenant_ids = [tenant_id] if tenant_id else []
        
        for role in linked_roles:
            role_tenant = role.get("tenant_id")
            if role_tenant and role_tenant not in tenant_ids:
                tenant_ids.append(role_tenant)
        
        return tenant_ids if tenant_ids else None
    
    @staticmethod
    def apply_tenant_filter(
        query: Dict[str, Any],
        user: Dict[str, Any],
        tenant_field: str = "tenant_id"
    ) -> Dict[str, Any]:
        """
        Apply tenant filter to a MongoDB query
        Returns modified query with tenant restriction
        """
        if TenantIsolation.is_platform_user(user):
            # Platform users see all data
            return query
        
        accessible_tenants = TenantIsolation.get_accessible_tenant_ids(user)
        
        if not accessible_tenants:
            # No tenant access - return empty result query
            logger.warning(f"User {user.get('id')} has no tenant access")
            return {**query, tenant_field: {"$in": []}}
        
        if len(accessible_tenants) == 1:
            # Single tenant
            query[tenant_field] = accessible_tenants[0]
        else:
            # Multiple tenants
            query[tenant_field] = {"$in": accessible_tenants}
        
        return query
    
    @staticmethod
    def validate_tenant_access(
        user: Dict[str, Any],
        resource_tenant_id: str
    ) -> bool:
        """
        Validate user can access a resource from specific tenant
        """
        if TenantIsolation.is_platform_user(user):
            return True
        
        accessible_tenants = TenantIsolation.get_accessible_tenant_ids(user)
        
        if not accessible_tenants:
            return False
        
        return resource_tenant_id in accessible_tenants
    
    @staticmethod
    def enforce_tenant_on_create(
        data: Dict[str, Any],
        user: Dict[str, Any],
        allow_override: bool = False
    ) -> Dict[str, Any]:
        """
        Enforce tenant_id on create operations
        """
        if TenantIsolation.is_platform_user(user) and allow_override:
            # Platform users can specify tenant_id
            if "tenant_id" not in data:
                # Default to no tenant for platform resources
                pass
            return data
        
        # Non-platform users must use their own tenant
        user_tenant = TenantIsolation.get_user_tenant_id(user)
        
        if not user_tenant:
            raise ValueError("المستخدم غير مرتبط بمدرسة")
        
        # Override any provided tenant_id with user's tenant
        data["tenant_id"] = user_tenant
        
        return data


def tenant_scoped(tenant_field: str = "tenant_id", allow_platform_override: bool = False):
    """
    Decorator to automatically apply tenant scoping
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            current_user = kwargs.get("current_user")
            
            if not current_user:
                raise HTTPException(status_code=401, detail="غير مصادق")
            
            # Add tenant context to kwargs
            kwargs["_tenant_context"] = {
                "user_tenant_id": TenantIsolation.get_user_tenant_id(current_user),
                "is_platform_user": TenantIsolation.is_platform_user(current_user),
                "accessible_tenants": TenantIsolation.get_accessible_tenant_ids(current_user),
            }
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator


def validate_resource_tenant(resource_tenant_id_param: str = "tenant_id"):
    """
    Decorator to validate user can access a resource's tenant
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            current_user = kwargs.get("current_user")
            resource_tenant_id = kwargs.get(resource_tenant_id_param)
            
            if not current_user:
                raise HTTPException(status_code=401, detail="غير مصادق")
            
            if resource_tenant_id:
                if not TenantIsolation.validate_tenant_access(current_user, resource_tenant_id):
                    logger.warning(
                        f"Tenant isolation violation: User {current_user.get('id')} "
                        f"attempted to access tenant {resource_tenant_id}"
                    )
                    raise HTTPException(
                        status_code=403,
                        detail="لا يمكنك الوصول إلى بيانات هذه المدرسة"
                    )
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator


class TenantAwareQuery:
    """
    Helper class for building tenant-aware queries
    """
    
    def __init__(self, db, user: Dict[str, Any]):
        self.db = db
        self.user = user
        self.is_platform = TenantIsolation.is_platform_user(user)
        self.accessible_tenants = TenantIsolation.get_accessible_tenant_ids(user)
    
    def build_query(
        self,
        base_query: Dict[str, Any] = None,
        tenant_field: str = "tenant_id"
    ) -> Dict[str, Any]:
        """Build a tenant-filtered query"""
        query = base_query or {}
        
        if self.is_platform:
            return query
        
        if not self.accessible_tenants:
            # Return impossible query
            return {**query, tenant_field: {"$in": []}}
        
        if len(self.accessible_tenants) == 1:
            query[tenant_field] = self.accessible_tenants[0]
        else:
            query[tenant_field] = {"$in": self.accessible_tenants}
        
        return query
    
    async def find(
        self,
        collection_name: str,
        query: Dict[str, Any] = None,
        projection: Dict[str, Any] = None,
        limit: int = 100
    ):
        """Execute a tenant-filtered find query"""
        filtered_query = self.build_query(query or {})
        
        collection = getattr(self.db, collection_name)
        
        if projection is None:
            projection = {"_id": 0}
        
        return await collection.find(
            filtered_query,
            projection
        ).to_list(limit)
    
    async def find_one(
        self,
        collection_name: str,
        query: Dict[str, Any],
        projection: Dict[str, Any] = None
    ):
        """Execute a tenant-filtered find_one query"""
        filtered_query = self.build_query(query)
        
        collection = getattr(self.db, collection_name)
        
        if projection is None:
            projection = {"_id": 0}
        
        return await collection.find_one(filtered_query, projection)
    
    async def count(
        self,
        collection_name: str,
        query: Dict[str, Any] = None
    ) -> int:
        """Execute a tenant-filtered count query"""
        filtered_query = self.build_query(query or {})
        
        collection = getattr(self.db, collection_name)
        
        return await collection.count_documents(filtered_query)


# Export
__all__ = [
    "PLATFORM_ROLES",
    "TenantIsolation",
    "tenant_scoped",
    "validate_resource_tenant",
    "TenantAwareQuery",
]
