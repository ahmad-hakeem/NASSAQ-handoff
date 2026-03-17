"""
NASSAQ Core Services
خدمات النظام الأساسية المتكاملة

Provides:
- Unified Audit logging for all operations
- Automatic RBAC enforcement
- Tenant isolation integration
- Standardized CRUD operations
"""

from typing import Optional, Dict, Any, List, Callable
from datetime import datetime, timezone
from functools import wraps
import uuid
import logging

from ..middleware.rbac import RBACMiddleware, Permission, ROLE_PERMISSIONS
from ..middleware.tenant_isolation import TenantIsolation, PLATFORM_ROLES
from ..engines.audit_engine import AuditLogEngine, AuditAction, AuditSeverity

logger = logging.getLogger(__name__)


class NassaqCoreService:
    """
    Core service that integrates RBAC, Tenant Isolation, and Audit Logging
    """
    
    def __init__(self, db):
        self.db = db
        self.audit_engine = AuditLogEngine(db)
        
    # ============== AUDIT HELPERS ==============
    
    async def audit_action(
        self,
        action: str,
        user: Dict[str, Any],
        entity_type: str = None,
        entity_id: str = None,
        details: Dict[str, Any] = None,
        old_values: Dict[str, Any] = None,
        new_values: Dict[str, Any] = None,
        ip_address: str = None,
        user_agent: str = None,
        success: bool = True
    ) -> Dict[str, Any]:
        """
        Log an audit action with full context
        """
        user_id = str(user.get("id", "unknown"))
        tenant_id = user.get("tenant_id") or user.get("primary_tenant_id")
        
        audit_details = details or {}
        
        if old_values and new_values:
            audit_details["old_values"] = old_values
            audit_details["new_values"] = new_values
            audit_details["changed_fields"] = list(
                set(new_values.keys()) - set(old_values.keys() if old_values else [])
            )
        
        audit_details["success"] = success
        
        try:
            result = await self.audit_engine.log(
                action=action,
                performed_by=user_id,
                tenant_id=tenant_id,
                entity_type=entity_type,
                entity_id=entity_id,
                details=audit_details,
                ip_address=ip_address,
                user_agent=user_agent
            )
            return result
        except Exception as e:
            logger.error(f"Failed to log audit: {e}")
            return None

    # ============== RBAC HELPERS ==============
    
    def check_permission(
        self,
        user: Dict[str, Any],
        required_permission: str
    ) -> bool:
        """Check if user has permission"""
        return RBACMiddleware.has_permission(user, required_permission)
    
    def check_any_permission(
        self,
        user: Dict[str, Any],
        permissions: List[str]
    ) -> bool:
        """Check if user has any of the permissions"""
        return RBACMiddleware.has_any_permission(user, permissions)
    
    def get_user_permissions(self, user: Dict[str, Any]) -> List[str]:
        """Get all permissions for a user"""
        role = user.get("role") or user.get("primary_role")
        custom_perms = user.get("permissions", [])
        return RBACMiddleware.get_user_permissions(role, custom_perms)

    # ============== TENANT ISOLATION HELPERS ==============
    
    def is_platform_user(self, user: Dict[str, Any]) -> bool:
        """Check if user is a platform-level user"""
        return TenantIsolation.is_platform_user(user)
    
    def get_user_tenant(self, user: Dict[str, Any]) -> Optional[str]:
        """Get user's tenant ID"""
        return TenantIsolation.get_user_tenant_id(user)
    
    def can_access_tenant(self, user: Dict[str, Any], tenant_id: str) -> bool:
        """Check if user can access a specific tenant"""
        return TenantIsolation.validate_tenant_access(user, tenant_id)
    
    def apply_tenant_filter(
        self,
        query: Dict[str, Any],
        user: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Apply tenant filter to query"""
        return TenantIsolation.apply_tenant_filter(query, user)

    # ============== STANDARDIZED CRUD ==============
    
    async def create_entity(
        self,
        collection_name: str,
        data: Dict[str, Any],
        user: Dict[str, Any],
        audit_action: str,
        entity_type: str,
        required_permission: str = None,
        ip_address: str = None
    ) -> Dict[str, Any]:
        """
        Standardized create operation with full integration
        """
        # Check permission
        if required_permission and not self.check_permission(user, required_permission):
            raise PermissionError(f"ليس لديك صلاحية: {required_permission}")
        
        # Apply tenant isolation
        if not self.is_platform_user(user):
            user_tenant = self.get_user_tenant(user)
            if user_tenant:
                data["tenant_id"] = user_tenant
        
        # Generate ID and timestamps
        entity_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        
        data["id"] = entity_id
        data["created_at"] = now
        data["updated_at"] = now
        data["created_by"] = str(user.get("id"))
        
        # Insert
        collection = getattr(self.db, collection_name)
        await collection.insert_one(data)
        
        # Audit log
        await self.audit_action(
            action=audit_action,
            user=user,
            entity_type=entity_type,
            entity_id=entity_id,
            new_values=data,
            ip_address=ip_address,
            success=True
        )
        
        # Remove MongoDB _id before returning
        data.pop("_id", None)
        
        return data
    
    async def update_entity(
        self,
        collection_name: str,
        entity_id: str,
        updates: Dict[str, Any],
        user: Dict[str, Any],
        audit_action: str,
        entity_type: str,
        required_permission: str = None,
        ip_address: str = None
    ) -> Dict[str, Any]:
        """
        Standardized update operation with full integration
        """
        # Check permission
        if required_permission and not self.check_permission(user, required_permission):
            raise PermissionError(f"ليس لديك صلاحية: {required_permission}")
        
        collection = getattr(self.db, collection_name)
        
        # Build query with tenant isolation
        query = {"id": entity_id}
        query = self.apply_tenant_filter(query, user)
        
        # Get old values
        old_doc = await collection.find_one(query, {"_id": 0})
        if not old_doc:
            raise ValueError(f"العنصر غير موجود أو لا يمكنك الوصول إليه")
        
        # Apply updates
        updates["updated_at"] = datetime.now(timezone.utc).isoformat()
        updates["updated_by"] = str(user.get("id"))
        
        await collection.update_one(query, {"$set": updates})
        
        # Get updated doc
        updated_doc = await collection.find_one({"id": entity_id}, {"_id": 0})
        
        # Audit log
        await self.audit_action(
            action=audit_action,
            user=user,
            entity_type=entity_type,
            entity_id=entity_id,
            old_values=old_doc,
            new_values=updates,
            ip_address=ip_address,
            success=True
        )
        
        return updated_doc
    
    async def delete_entity(
        self,
        collection_name: str,
        entity_id: str,
        user: Dict[str, Any],
        audit_action: str,
        entity_type: str,
        required_permission: str = None,
        soft_delete: bool = True,
        ip_address: str = None
    ) -> bool:
        """
        Standardized delete operation with full integration
        """
        # Check permission
        if required_permission and not self.check_permission(user, required_permission):
            raise PermissionError(f"ليس لديك صلاحية: {required_permission}")
        
        collection = getattr(self.db, collection_name)
        
        # Build query with tenant isolation
        query = {"id": entity_id}
        query = self.apply_tenant_filter(query, user)
        
        # Get entity before delete
        entity = await collection.find_one(query, {"_id": 0})
        if not entity:
            raise ValueError(f"العنصر غير موجود أو لا يمكنك الوصول إليه")
        
        if soft_delete:
            # Soft delete
            await collection.update_one(query, {
                "$set": {
                    "deleted_at": datetime.now(timezone.utc).isoformat(),
                    "deleted_by": str(user.get("id")),
                    "is_deleted": True
                }
            })
        else:
            # Hard delete
            await collection.delete_one(query)
        
        # Audit log
        await self.audit_action(
            action=audit_action,
            user=user,
            entity_type=entity_type,
            entity_id=entity_id,
            old_values=entity,
            ip_address=ip_address,
            success=True,
            details={"soft_delete": soft_delete}
        )
        
        return True
    
    async def get_entity(
        self,
        collection_name: str,
        entity_id: str,
        user: Dict[str, Any],
        required_permission: str = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get single entity with tenant isolation
        """
        # Check permission
        if required_permission and not self.check_permission(user, required_permission):
            raise PermissionError(f"ليس لديك صلاحية: {required_permission}")
        
        collection = getattr(self.db, collection_name)
        
        # Build query with tenant isolation
        query = {"id": entity_id, "is_deleted": {"$ne": True}}
        query = self.apply_tenant_filter(query, user)
        
        entity = await collection.find_one(query, {"_id": 0})
        
        return entity
    
    async def list_entities(
        self,
        collection_name: str,
        user: Dict[str, Any],
        filters: Dict[str, Any] = None,
        required_permission: str = None,
        limit: int = 100,
        skip: int = 0,
        sort_by: str = "created_at",
        sort_order: int = -1
    ) -> List[Dict[str, Any]]:
        """
        List entities with tenant isolation and filters
        """
        # Check permission
        if required_permission and not self.check_permission(user, required_permission):
            raise PermissionError(f"ليس لديك صلاحية: {required_permission}")
        
        collection = getattr(self.db, collection_name)
        
        # Build query
        query = filters or {}
        query["is_deleted"] = {"$ne": True}
        
        # Apply tenant filter
        query = self.apply_tenant_filter(query, user)
        
        entities = await collection.find(
            query,
            {"_id": 0}
        ).sort(sort_by, sort_order).skip(skip).limit(limit).to_list(limit)
        
        return entities
    
    async def count_entities(
        self,
        collection_name: str,
        user: Dict[str, Any],
        filters: Dict[str, Any] = None,
        required_permission: str = None
    ) -> int:
        """
        Count entities with tenant isolation
        """
        # Check permission
        if required_permission and not self.check_permission(user, required_permission):
            raise PermissionError(f"ليس لديك صلاحية: {required_permission}")
        
        collection = getattr(self.db, collection_name)
        
        # Build query
        query = filters or {}
        query["is_deleted"] = {"$ne": True}
        
        # Apply tenant filter
        query = self.apply_tenant_filter(query, user)
        
        return await collection.count_documents(query)


# ============== DECORATOR FOR AUTOMATIC AUDIT ==============

def audited_action(
    action: str,
    entity_type: str,
    entity_id_param: str = None,
    log_details: bool = True
):
    """
    Decorator to automatically audit an action
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            current_user = kwargs.get("current_user")
            request = kwargs.get("request")
            
            # Extract entity_id if specified
            entity_id = kwargs.get(entity_id_param) if entity_id_param else None
            
            # Get IP and User-Agent
            ip_address = None
            user_agent = None
            if request:
                ip_address = getattr(request.client, "host", None) if request.client else None
                user_agent = request.headers.get("user-agent")
            
            try:
                # Execute the function
                result = await func(*args, **kwargs)
                
                # Log success
                if current_user:
                    db = kwargs.get("db") or (args[0] if args else None)
                    if db:
                        audit_engine = AuditLogEngine(db)
                        
                        details = {}
                        if log_details and isinstance(result, dict):
                            details["result_id"] = result.get("id")
                        
                        await audit_engine.log(
                            action=action,
                            performed_by=str(current_user.get("id")),
                            tenant_id=current_user.get("tenant_id") or current_user.get("primary_tenant_id"),
                            entity_type=entity_type,
                            entity_id=entity_id or (result.get("id") if isinstance(result, dict) else None),
                            details=details,
                            ip_address=ip_address,
                            user_agent=user_agent
                        )
                
                return result
                
            except Exception as e:
                # Log failure
                if current_user:
                    db = kwargs.get("db") or (args[0] if args else None)
                    if db:
                        audit_engine = AuditLogEngine(db)
                        await audit_engine.log(
                            action=action,
                            performed_by=str(current_user.get("id")),
                            tenant_id=current_user.get("tenant_id"),
                            entity_type=entity_type,
                            entity_id=entity_id,
                            details={"error": str(e), "success": False},
                            ip_address=ip_address,
                            user_agent=user_agent
                        )
                raise
        
        return wrapper
    return decorator


# ============== OPERATION RESULT HELPERS ==============

class OperationResult:
    """Standardized operation result"""
    
    @staticmethod
    def success(
        message: str = "تمت العملية بنجاح",
        data: Any = None,
        entity_id: str = None
    ) -> Dict[str, Any]:
        return {
            "success": True,
            "message": message,
            "data": data,
            "entity_id": entity_id
        }
    
    @staticmethod
    def error(
        message: str = "حدث خطأ أثناء العملية",
        error_code: str = None,
        details: Any = None
    ) -> Dict[str, Any]:
        return {
            "success": False,
            "message": message,
            "error_code": error_code,
            "details": details
        }


# Export
__all__ = [
    "NassaqCoreService",
    "audited_action",
    "OperationResult"
]
