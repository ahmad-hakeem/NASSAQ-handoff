"""
NASSAQ Identity Engine
محرك الهوية لمنصة نَسَّق

Handles:
- User identity management
- Multi-role support
- Role switching
- User relationships
- Permission management
"""

from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
import uuid

from models.foundation import (
    UserIdentity, UserRelationship, LinkedRole,
    UserRole, AccountStatus, RelationshipType, PermissionScope,
    AuditLog, AuditAction
)


class IdentityEngine:
    """
    Core Identity Engine for NASSAQ
    Manages user identities, roles, and relationships
    """
    
    def __init__(self, db):
        self.db = db
        self.users_collection = db.users
        self.relationships_collection = db.user_relationships
        self.audit_collection = db.audit_logs
    
    # ============== USER MANAGEMENT ==============
    
    async def create_user(
        self,
        email: str,
        password_hash: str,
        full_name: str,
        primary_role: UserRole,
        created_by: Optional[str] = None,
        tenant_id: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Create a new user identity
        """
        user_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        
        # Check for existing email
        existing = await self.users_collection.find_one({"email": email})
        if existing:
            raise ValueError("البريد الإلكتروني مستخدم مسبقاً")
        
        # Check for existing phone if provided
        phone = kwargs.get("phone")
        if phone:
            existing_phone = await self.users_collection.find_one({"phone": phone})
            if existing_phone:
                raise ValueError("رقم الهاتف مستخدم مسبقاً")
        
        # Check for existing national_id if provided
        national_id = kwargs.get("national_id")
        if national_id:
            existing_id = await self.users_collection.find_one({"national_id": national_id})
            if existing_id:
                raise ValueError("رقم الهوية مستخدم مسبقاً")
        
        user_doc = {
            "id": user_id,
            "email": email,
            "password_hash": password_hash,
            "full_name": full_name,
            "full_name_en": kwargs.get("full_name_en"),
            "phone": phone,
            "national_id": national_id,
            "primary_role": primary_role.value if isinstance(primary_role, UserRole) else primary_role,
            "status": AccountStatus.ACTIVE.value,
            "is_active": True,
            "must_change_password": kwargs.get("must_change_password", True),
            "primary_tenant_id": tenant_id,
            "linked_roles": [],
            "preferred_language": kwargs.get("preferred_language", "ar"),
            "preferred_theme": kwargs.get("preferred_theme", "light"),
            "avatar_url": kwargs.get("avatar_url"),
            "email_verified": False,
            "phone_verified": False,
            "failed_login_attempts": 0,
            "created_at": now,
            "updated_at": now,
            "created_by": created_by,
        }
        
        # Add initial linked role
        if tenant_id:
            user_doc["linked_roles"].append({
                "role": primary_role.value if isinstance(primary_role, UserRole) else primary_role,
                "tenant_id": tenant_id,
                "scope_id": None,
                "is_active": True,
                "assigned_at": now,
                "assigned_by": created_by,
            })
        
        await self.users_collection.insert_one(user_doc)
        
        # Audit log
        await self._log_action(
            AuditAction.USER_CREATED,
            actor_id=created_by or "system",
            actor_name="System" if not created_by else "",
            target_type="user",
            target_id=user_id,
            target_name=full_name,
            tenant_id=tenant_id,
            details={"role": primary_role.value if isinstance(primary_role, UserRole) else primary_role}
        )
        
        # Remove password_hash from response
        del user_doc["password_hash"]
        return user_doc
    
    async def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user by ID"""
        user = await self.users_collection.find_one(
            {"id": user_id},
            {"_id": 0, "password_hash": 0}
        )
        return user
    
    async def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Get user by email (includes password_hash for auth)"""
        return await self.users_collection.find_one(
            {"email": email},
            {"_id": 0}
        )
    
    async def update_user(
        self,
        user_id: str,
        updates: Dict[str, Any],
        updated_by: str
    ) -> Dict[str, Any]:
        """Update user information"""
        now = datetime.now(timezone.utc).isoformat()
        
        # Get current state for audit
        current_user = await self.get_user_by_id(user_id)
        if not current_user:
            raise ValueError("المستخدم غير موجود")
        
        # Prepare updates
        updates["updated_at"] = now
        
        # Prevent updating certain fields directly
        protected_fields = ["id", "email", "password_hash", "created_at", "created_by"]
        for field in protected_fields:
            updates.pop(field, None)
        
        await self.users_collection.update_one(
            {"id": user_id},
            {"$set": updates}
        )
        
        # Audit log
        await self._log_action(
            AuditAction.USER_UPDATED,
            actor_id=updated_by,
            target_type="user",
            target_id=user_id,
            target_name=current_user.get("full_name"),
            tenant_id=current_user.get("primary_tenant_id"),
            previous_state={k: current_user.get(k) for k in updates.keys() if k != "updated_at"},
            new_state=updates
        )
        
        return await self.get_user_by_id(user_id)
    
    async def update_user_status(
        self,
        user_id: str,
        status: AccountStatus,
        updated_by: str,
        reason: Optional[str] = None
    ) -> Dict[str, Any]:
        """Update user account status"""
        now = datetime.now(timezone.utc).isoformat()
        
        current_user = await self.get_user_by_id(user_id)
        if not current_user:
            raise ValueError("المستخدم غير موجود")
        
        is_active = status in [AccountStatus.ACTIVE]
        
        await self.users_collection.update_one(
            {"id": user_id},
            {
                "$set": {
                    "status": status.value,
                    "is_active": is_active,
                    "updated_at": now
                }
            }
        )
        
        # Determine audit action
        if status == AccountStatus.SUSPENDED:
            action = AuditAction.USER_SUSPENDED
        elif status == AccountStatus.ACTIVE:
            action = AuditAction.USER_ACTIVATED
        else:
            action = AuditAction.USER_UPDATED
        
        await self._log_action(
            action,
            actor_id=updated_by,
            target_type="user",
            target_id=user_id,
            target_name=current_user.get("full_name"),
            tenant_id=current_user.get("primary_tenant_id"),
            details={"new_status": status.value, "reason": reason}
        )
        
        return await self.get_user_by_id(user_id)
    
    # ============== MULTI-ROLE MANAGEMENT ==============
    
    async def add_role_to_user(
        self,
        user_id: str,
        role: UserRole,
        tenant_id: Optional[str] = None,
        scope_id: Optional[str] = None,
        assigned_by: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Add an additional role to a user
        Enables multi-role capability
        """
        now = datetime.now(timezone.utc).isoformat()
        
        user = await self.get_user_by_id(user_id)
        if not user:
            raise ValueError("المستخدم غير موجود")
        
        # Check if role already exists for this tenant
        existing_roles = user.get("linked_roles", [])
        for existing in existing_roles:
            if (existing.get("role") == role.value and 
                existing.get("tenant_id") == tenant_id and
                existing.get("is_active")):
                raise ValueError("هذا الدور موجود مسبقاً للمستخدم")
        
        new_role = {
            "role": role.value,
            "tenant_id": tenant_id,
            "scope_id": scope_id,
            "is_active": True,
            "assigned_at": now,
            "assigned_by": assigned_by,
        }
        
        await self.users_collection.update_one(
            {"id": user_id},
            {
                "$push": {"linked_roles": new_role},
                "$set": {"updated_at": now}
            }
        )
        
        await self._log_action(
            AuditAction.ROLE_ASSIGNED,
            actor_id=assigned_by or "system",
            target_type="user",
            target_id=user_id,
            target_name=user.get("full_name"),
            tenant_id=tenant_id,
            details={"role": role.value, "scope_id": scope_id}
        )
        
        return await self.get_user_by_id(user_id)
    
    async def remove_role_from_user(
        self,
        user_id: str,
        role: UserRole,
        removed_by: str,
        tenant_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Remove a role from a user"""
        now = datetime.now(timezone.utc).isoformat()
        
        user = await self.get_user_by_id(user_id)
        if not user:
            raise ValueError("المستخدم غير موجود")
        
        # Don't remove primary role
        if user.get("primary_role") == role.value and not tenant_id:
            raise ValueError("لا يمكن إزالة الدور الأساسي")
        
        # Mark role as inactive (soft delete)
        await self.users_collection.update_one(
            {
                "id": user_id,
                "linked_roles.role": role.value,
                "linked_roles.tenant_id": tenant_id
            },
            {
                "$set": {
                    "linked_roles.$.is_active": False,
                    "updated_at": now
                }
            }
        )
        
        await self._log_action(
            AuditAction.ROLE_REMOVED,
            actor_id=removed_by,
            target_type="user",
            target_id=user_id,
            target_name=user.get("full_name"),
            tenant_id=tenant_id,
            details={"role": role.value}
        )
        
        return await self.get_user_by_id(user_id)
    
    async def get_user_roles(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all active roles for a user"""
        user = await self.get_user_by_id(user_id)
        if not user:
            return []
        
        roles = []
        
        # Add primary role
        roles.append({
            "role": user.get("primary_role"),
            "tenant_id": user.get("primary_tenant_id"),
            "is_primary": True,
            "is_active": True
        })
        
        # Add linked roles
        for linked in user.get("linked_roles", []):
            if linked.get("is_active"):
                roles.append({
                    "role": linked.get("role"),
                    "tenant_id": linked.get("tenant_id"),
                    "scope_id": linked.get("scope_id"),
                    "is_primary": False,
                    "is_active": True
                })
        
        return roles
    
    async def switch_role(
        self,
        user_id: str,
        target_role: UserRole,
        target_tenant_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Switch user's active role context
        Returns new token context
        """
        user = await self.get_user_by_id(user_id)
        if not user:
            raise ValueError("المستخدم غير موجود")
        
        # Verify user has this role
        available_roles = await self.get_user_roles(user_id)
        role_valid = False
        
        for role in available_roles:
            if (role.get("role") == target_role.value and 
                role.get("tenant_id") == target_tenant_id):
                role_valid = True
                break
        
        if not role_valid:
            raise ValueError("ليس لديك صلاحية الوصول لهذا الدور")
        
        await self._log_action(
            AuditAction.ROLE_SWITCHED,
            actor_id=user_id,
            actor_name=user.get("full_name"),
            target_type="user",
            target_id=user_id,
            tenant_id=target_tenant_id,
            details={
                "from_role": user.get("primary_role"),
                "to_role": target_role.value
            }
        )
        
        return {
            "user_id": user_id,
            "active_role": target_role.value,
            "active_tenant_id": target_tenant_id,
            "full_name": user.get("full_name"),
            "email": user.get("email")
        }
    
    # ============== RELATIONSHIP MANAGEMENT ==============
    
    async def create_relationship(
        self,
        relationship_type: RelationshipType,
        user_id_1: str,
        user_id_2: str,
        created_by: Optional[str] = None,
        is_verified: bool = False,
        detected_automatically: bool = False,
        detection_method: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a relationship between two users"""
        now = datetime.now(timezone.utc).isoformat()
        
        # Verify both users exist
        user1 = await self.get_user_by_id(user_id_1)
        user2 = await self.get_user_by_id(user_id_2)
        
        if not user1 or not user2:
            raise ValueError("أحد المستخدمين غير موجود")
        
        # Check for existing relationship
        existing = await self.relationships_collection.find_one({
            "user_id_1": user_id_1,
            "user_id_2": user_id_2,
            "relationship_type": relationship_type.value,
            "is_active": True
        })
        
        if existing:
            raise ValueError("هذه العلاقة موجودة مسبقاً")
        
        relationship_id = str(uuid.uuid4())
        relationship_doc = {
            "id": relationship_id,
            "relationship_type": relationship_type.value,
            "user_id_1": user_id_1,
            "user_id_2": user_id_2,
            "is_active": True,
            "is_verified": is_verified,
            "detected_automatically": detected_automatically,
            "detection_method": detection_method,
            "created_at": now,
            "created_by": created_by,
        }
        
        if is_verified and created_by:
            relationship_doc["verified_by"] = created_by
            relationship_doc["verified_at"] = now
        
        await self.relationships_collection.insert_one(relationship_doc)
        
        return relationship_doc
    
    async def get_user_relationships(
        self,
        user_id: str,
        relationship_type: Optional[RelationshipType] = None
    ) -> List[Dict[str, Any]]:
        """Get all relationships for a user"""
        query = {
            "$or": [
                {"user_id_1": user_id},
                {"user_id_2": user_id}
            ],
            "is_active": True
        }
        
        if relationship_type:
            query["relationship_type"] = relationship_type.value
        
        relationships = await self.relationships_collection.find(
            query,
            {"_id": 0}
        ).to_list(1000)
        
        # Enrich with user info
        for rel in relationships:
            other_user_id = rel["user_id_2"] if rel["user_id_1"] == user_id else rel["user_id_1"]
            other_user = await self.get_user_by_id(other_user_id)
            if other_user:
                rel["related_user"] = {
                    "id": other_user.get("id"),
                    "full_name": other_user.get("full_name"),
                    "role": other_user.get("primary_role")
                }
        
        return relationships
    
    async def detect_relationships(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Automatically detect potential relationships based on:
        - Matching phone numbers
        - Matching national_id patterns
        - Same email domain for school accounts
        """
        user = await self.get_user_by_id(user_id)
        if not user:
            return []
        
        potential_relationships = []
        
        # Check by phone
        phone = user.get("phone")
        if phone:
            similar_phone_users = await self.users_collection.find(
                {
                    "phone": phone,
                    "id": {"$ne": user_id}
                },
                {"_id": 0, "password_hash": 0}
            ).to_list(10)
            
            for similar in similar_phone_users:
                potential_relationships.append({
                    "user": similar,
                    "detection_method": "phone",
                    "confidence": 0.9
                })
        
        # Check by national_id family pattern (simplified)
        national_id = user.get("national_id")
        if national_id and len(national_id) >= 10:
            # In Saudi Arabia, family members often have similar national ID prefixes
            prefix = national_id[:4]
            similar_id_users = await self.users_collection.find(
                {
                    "national_id": {"$regex": f"^{prefix}"},
                    "id": {"$ne": user_id}
                },
                {"_id": 0, "password_hash": 0}
            ).to_list(20)
            
            for similar in similar_id_users:
                # Avoid duplicates
                if not any(p["user"]["id"] == similar["id"] for p in potential_relationships):
                    potential_relationships.append({
                        "user": similar,
                        "detection_method": "national_id_pattern",
                        "confidence": 0.6
                    })
        
        return potential_relationships
    
    async def verify_relationship(
        self,
        relationship_id: str,
        verified_by: str
    ) -> Dict[str, Any]:
        """Admin verification of a relationship"""
        now = datetime.now(timezone.utc).isoformat()
        
        await self.relationships_collection.update_one(
            {"id": relationship_id},
            {
                "$set": {
                    "is_verified": True,
                    "verified_by": verified_by,
                    "verified_at": now
                }
            }
        )
        
        return await self.relationships_collection.find_one(
            {"id": relationship_id},
            {"_id": 0}
        )
    
    # ============== PASSWORD MANAGEMENT ==============
    
    async def record_failed_login(self, user_id: str) -> int:
        """Record a failed login attempt"""
        result = await self.users_collection.find_one_and_update(
            {"id": user_id},
            {"$inc": {"failed_login_attempts": 1}},
            return_document=True
        )
        
        attempts = result.get("failed_login_attempts", 0) if result else 0
        
        # Lock account after 5 failed attempts
        if attempts >= 5:
            lock_until = datetime.now(timezone.utc).isoformat()
            await self.users_collection.update_one(
                {"id": user_id},
                {
                    "$set": {
                        "status": AccountStatus.LOCKED.value,
                        "locked_until": lock_until
                    }
                }
            )
        
        return attempts
    
    async def reset_failed_login(self, user_id: str):
        """Reset failed login counter after successful login"""
        await self.users_collection.update_one(
            {"id": user_id},
            {
                "$set": {
                    "failed_login_attempts": 0,
                    "last_login": datetime.now(timezone.utc).isoformat()
                },
                "$unset": {"locked_until": ""}
            }
        )
    
    async def change_password(
        self,
        user_id: str,
        new_password_hash: str,
        changed_by: Optional[str] = None
    ):
        """Change user password"""
        now = datetime.now(timezone.utc).isoformat()
        
        await self.users_collection.update_one(
            {"id": user_id},
            {
                "$set": {
                    "password_hash": new_password_hash,
                    "must_change_password": False,
                    "last_password_change": now,
                    "updated_at": now
                }
            }
        )
        
        await self._log_action(
            AuditAction.PASSWORD_CHANGED,
            actor_id=changed_by or user_id,
            target_type="user",
            target_id=user_id,
            details={"changed_by_self": changed_by == user_id or changed_by is None}
        )
    
    # ============== AUDIT LOGGING ==============
    
    async def _log_action(
        self,
        action: AuditAction,
        actor_id: str,
        target_type: str,
        target_id: str,
        actor_name: str = "",
        target_name: Optional[str] = None,
        tenant_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        previous_state: Optional[Dict[str, Any]] = None,
        new_state: Optional[Dict[str, Any]] = None
    ):
        """Log an action to audit trail"""
        log_entry = {
            "id": str(uuid.uuid4()),
            "action": action.value,
            "action_category": "identity",
            "actor_id": actor_id,
            "actor_name": actor_name,
            "actor_role": "",
            "target_type": target_type,
            "target_id": target_id,
            "target_name": target_name,
            "tenant_id": tenant_id,
            "details": details or {},
            "previous_state": previous_state,
            "new_state": new_state,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        await self.audit_collection.insert_one(log_entry)


# Export
__all__ = ["IdentityEngine"]
