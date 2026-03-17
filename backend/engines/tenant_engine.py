"""
NASSAQ Tenant Engine
محرك المستأجرين (المدارس) لمنصة نَسَّق

Handles:
- Multi-tenant isolation
- Tenant lifecycle management
- Tenant configuration
- Data scoping
"""

from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
import uuid

from models.foundation import (
    Tenant, TenantConfiguration, TenantStatus, TenantType,
    AuditLog, AuditAction
)


class TenantEngine:
    """
    Core Tenant Engine for NASSAQ
    Manages multi-tenant isolation and tenant lifecycle
    """
    
    def __init__(self, db):
        self.db = db
        self.tenants_collection = db.schools  # schools collection is our tenants
        self.audit_collection = db.audit_logs
    
    # ============== TENANT CRUD ==============
    
    async def create_tenant(
        self,
        name_ar: str,
        created_by: str,
        name_en: Optional[str] = None,
        tenant_type: TenantType = TenantType.PRODUCTION,
        **kwargs
    ) -> Dict[str, Any]:
        """Create a new tenant (school)"""
        tenant_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        
        # Generate unique code
        code = kwargs.get("code")
        if not code:
            code = f"SCH-{str(uuid.uuid4())[:8].upper()}"
        
        # Check for duplicate code
        existing = await self.tenants_collection.find_one({"code": code})
        if existing:
            raise ValueError("كود المدرسة مستخدم مسبقاً")
        
        # Default configuration
        config = TenantConfiguration()
        if kwargs.get("configuration"):
            config = TenantConfiguration(**kwargs["configuration"])
        
        tenant_doc = {
            "id": tenant_id,
            "name_ar": name_ar,
            "name_en": name_en,
            "code": code,
            "tenant_type": tenant_type.value,
            "status": TenantStatus.PENDING.value,
            "school_type": kwargs.get("school_type", "private"),
            "gender": kwargs.get("gender"),
            "email": kwargs.get("email"),
            "phone": kwargs.get("phone"),
            "website": kwargs.get("website"),
            "region": kwargs.get("region"),
            "city": kwargs.get("city"),
            "district": kwargs.get("district"),
            "address": kwargs.get("address"),
            "ministry_id": kwargs.get("ministry_id"),
            "license_number": kwargs.get("license_number"),
            "student_capacity": kwargs.get("student_capacity"),
            "current_student_count": 0,
            "current_teacher_count": 0,
            "configuration": config.model_dump(),
            "setup_completed": False,
            "setup_steps_completed": [],
            "health_score": None,
            "last_health_check": None,
            "subscription_start": kwargs.get("subscription_start"),
            "subscription_end": kwargs.get("subscription_end"),
            "trial_end": kwargs.get("trial_end"),
            "principal_id": kwargs.get("principal_id"),
            "created_at": now,
            "updated_at": now,
            "created_by": created_by,
        }
        
        await self.tenants_collection.insert_one(tenant_doc)
        
        # Audit log
        await self._log_action(
            AuditAction.TENANT_CREATED,
            actor_id=created_by,
            target_id=tenant_id,
            target_name=name_ar,
            details={"code": code, "tenant_type": tenant_type.value}
        )
        
        return tenant_doc
    
    async def get_tenant_by_id(self, tenant_id: str) -> Optional[Dict[str, Any]]:
        """Get tenant by ID"""
        return await self.tenants_collection.find_one(
            {"id": tenant_id},
            {"_id": 0}
        )
    
    async def get_tenant_by_code(self, code: str) -> Optional[Dict[str, Any]]:
        """Get tenant by code"""
        return await self.tenants_collection.find_one(
            {"code": code},
            {"_id": 0}
        )
    
    async def list_tenants(
        self,
        status: Optional[TenantStatus] = None,
        tenant_type: Optional[TenantType] = None,
        region: Optional[str] = None,
        skip: int = 0,
        limit: int = 100
    ) -> Dict[str, Any]:
        """List tenants with filters"""
        query = {}
        
        if status:
            query["status"] = status.value
        if tenant_type:
            query["tenant_type"] = tenant_type.value
        if region:
            query["region"] = region
        
        total = await self.tenants_collection.count_documents(query)
        
        tenants = await self.tenants_collection.find(
            query,
            {"_id": 0}
        ).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
        
        return {
            "tenants": tenants,
            "total": total,
            "skip": skip,
            "limit": limit
        }
    
    async def update_tenant(
        self,
        tenant_id: str,
        updates: Dict[str, Any],
        updated_by: str
    ) -> Dict[str, Any]:
        """Update tenant information"""
        now = datetime.now(timezone.utc).isoformat()
        
        current = await self.get_tenant_by_id(tenant_id)
        if not current:
            raise ValueError("المدرسة غير موجودة")
        
        # Protected fields
        protected = ["id", "code", "created_at", "created_by"]
        for field in protected:
            updates.pop(field, None)
        
        updates["updated_at"] = now
        
        await self.tenants_collection.update_one(
            {"id": tenant_id},
            {"$set": updates}
        )
        
        await self._log_action(
            AuditAction.TENANT_UPDATED,
            actor_id=updated_by,
            target_id=tenant_id,
            target_name=current.get("name_ar"),
            tenant_id=tenant_id,
            previous_state={k: current.get(k) for k in updates.keys() if k != "updated_at"},
            new_state=updates
        )
        
        return await self.get_tenant_by_id(tenant_id)
    
    async def update_tenant_status(
        self,
        tenant_id: str,
        status: TenantStatus,
        updated_by: str,
        reason: Optional[str] = None
    ) -> Dict[str, Any]:
        """Update tenant status"""
        now = datetime.now(timezone.utc).isoformat()
        
        current = await self.get_tenant_by_id(tenant_id)
        if not current:
            raise ValueError("المدرسة غير موجودة")
        
        old_status = current.get("status")
        
        await self.tenants_collection.update_one(
            {"id": tenant_id},
            {
                "$set": {
                    "status": status.value,
                    "updated_at": now
                }
            }
        )
        
        # Determine audit action
        if status == TenantStatus.SUSPENDED:
            action = AuditAction.TENANT_SUSPENDED
        elif status == TenantStatus.ACTIVE:
            action = AuditAction.TENANT_ACTIVATED
        else:
            action = AuditAction.TENANT_UPDATED
        
        await self._log_action(
            action,
            actor_id=updated_by,
            target_id=tenant_id,
            target_name=current.get("name_ar"),
            tenant_id=tenant_id,
            details={
                "old_status": old_status,
                "new_status": status.value,
                "reason": reason
            }
        )
        
        return await self.get_tenant_by_id(tenant_id)
    
    # ============== CONFIGURATION MANAGEMENT ==============
    
    async def update_tenant_configuration(
        self,
        tenant_id: str,
        config_updates: Dict[str, Any],
        updated_by: str
    ) -> Dict[str, Any]:
        """Update tenant configuration"""
        now = datetime.now(timezone.utc).isoformat()
        
        current = await self.get_tenant_by_id(tenant_id)
        if not current:
            raise ValueError("المدرسة غير موجودة")
        
        current_config = current.get("configuration", {})
        
        # Merge updates
        for key, value in config_updates.items():
            current_config[key] = value
        
        await self.tenants_collection.update_one(
            {"id": tenant_id},
            {
                "$set": {
                    "configuration": current_config,
                    "updated_at": now
                }
            }
        )
        
        # Log AI feature toggles specifically
        ai_keys = ["ai_enabled", "ai_hakim_enabled", "ai_analytics_enabled", "ai_import_enabled"]
        for key in ai_keys:
            if key in config_updates:
                await self._log_action(
                    AuditAction.AI_FEATURE_TOGGLED,
                    actor_id=updated_by,
                    target_id=tenant_id,
                    target_name=current.get("name_ar"),
                    tenant_id=tenant_id,
                    details={
                        "feature": key,
                        "enabled": config_updates[key]
                    },
                    is_sensitive=True
                )
        
        return await self.get_tenant_by_id(tenant_id)
    
    # ============== SETUP TRACKING ==============
    
    async def complete_setup_step(
        self,
        tenant_id: str,
        step: str,
        completed_by: str
    ) -> Dict[str, Any]:
        """Mark a setup step as completed"""
        now = datetime.now(timezone.utc).isoformat()
        
        current = await self.get_tenant_by_id(tenant_id)
        if not current:
            raise ValueError("المدرسة غير موجودة")
        
        completed_steps = current.get("setup_steps_completed", [])
        if step not in completed_steps:
            completed_steps.append(step)
        
        # Check if all required steps are completed
        required_steps = [
            "basic_info",
            "principal_assigned",
            "academic_structure",
            "initial_teachers",
            "initial_students"
        ]
        
        setup_completed = all(s in completed_steps for s in required_steps)
        
        updates = {
            "setup_steps_completed": completed_steps,
            "updated_at": now
        }
        
        if setup_completed and not current.get("setup_completed"):
            updates["setup_completed"] = True
            updates["status"] = TenantStatus.ACTIVE.value
        
        await self.tenants_collection.update_one(
            {"id": tenant_id},
            {"$set": updates}
        )
        
        return await self.get_tenant_by_id(tenant_id)
    
    # ============== HEALTH & METRICS ==============
    
    async def update_health_score(
        self,
        tenant_id: str,
        health_score: float,
        health_details: Optional[Dict[str, Any]] = None
    ):
        """Update tenant health score"""
        now = datetime.now(timezone.utc).isoformat()
        
        await self.tenants_collection.update_one(
            {"id": tenant_id},
            {
                "$set": {
                    "health_score": health_score,
                    "last_health_check": now,
                    "health_details": health_details or {}
                }
            }
        )
    
    async def update_counts(
        self,
        tenant_id: str,
        student_count: Optional[int] = None,
        teacher_count: Optional[int] = None
    ):
        """Update student/teacher counts"""
        updates = {}
        
        if student_count is not None:
            updates["current_student_count"] = student_count
        if teacher_count is not None:
            updates["current_teacher_count"] = teacher_count
        
        if updates:
            await self.tenants_collection.update_one(
                {"id": tenant_id},
                {"$set": updates}
            )
    
    async def get_tenant_stats(self, tenant_id: str) -> Dict[str, Any]:
        """Get comprehensive stats for a tenant"""
        tenant = await self.get_tenant_by_id(tenant_id)
        if not tenant:
            raise ValueError("المدرسة غير موجودة")
        
        # Get counts from related collections
        student_count = await self.db.students.count_documents({"school_id": tenant_id})
        teacher_count = await self.db.teachers.count_documents({"school_id": tenant_id})
        class_count = await self.db.classes.count_documents({"school_id": tenant_id})
        
        # Update stored counts
        await self.update_counts(tenant_id, student_count, teacher_count)
        
        return {
            "tenant_id": tenant_id,
            "name": tenant.get("name_ar"),
            "status": tenant.get("status"),
            "student_count": student_count,
            "teacher_count": teacher_count,
            "class_count": class_count,
            "student_capacity": tenant.get("student_capacity"),
            "capacity_usage": (student_count / tenant.get("student_capacity", 1)) * 100 if tenant.get("student_capacity") else None,
            "health_score": tenant.get("health_score"),
            "setup_completed": tenant.get("setup_completed"),
            "setup_progress": len(tenant.get("setup_steps_completed", [])) / 5 * 100
        }
    
    # ============== TENANT ISOLATION ==============
    
    def get_tenant_query(self, tenant_id: str) -> Dict[str, Any]:
        """
        Get query filter for tenant isolation
        Use this in all tenant-scoped queries
        """
        return {"school_id": tenant_id}
    
    async def verify_tenant_access(
        self,
        user_tenant_id: Optional[str],
        target_tenant_id: str,
        user_role: str
    ) -> bool:
        """
        Verify user has access to a specific tenant
        Platform admins can access all tenants
        """
        platform_roles = ["platform_admin", "platform_operations_manager", "ministry_rep"]
        
        if user_role in platform_roles:
            return True
        
        return user_tenant_id == target_tenant_id
    
    # ============== DEMO/TRIAL MANAGEMENT ==============
    
    async def is_demo_tenant(self, tenant_id: str) -> bool:
        """Check if tenant is a demo/trial account"""
        tenant = await self.get_tenant_by_id(tenant_id)
        if not tenant:
            return False
        
        return tenant.get("tenant_type") in [
            TenantType.DEMO.value,
            TenantType.TRIAL.value,
            TenantType.MARKETING.value,
            TenantType.TESTING.value
        ]
    
    async def get_production_tenants_only(self) -> List[Dict[str, Any]]:
        """Get only production tenants (exclude demo/trial)"""
        return await self.tenants_collection.find(
            {
                "tenant_type": TenantType.PRODUCTION.value,
                "status": {"$ne": TenantStatus.ARCHIVED.value}
            },
            {"_id": 0}
        ).to_list(1000)
    
    # ============== AUDIT LOGGING ==============
    
    async def _log_action(
        self,
        action: AuditAction,
        actor_id: str,
        target_id: str,
        target_name: Optional[str] = None,
        tenant_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        previous_state: Optional[Dict[str, Any]] = None,
        new_state: Optional[Dict[str, Any]] = None,
        is_sensitive: bool = False
    ):
        """Log an action to audit trail"""
        log_entry = {
            "id": str(uuid.uuid4()),
            "action": action.value,
            "action_category": "tenant",
            "actor_id": actor_id,
            "actor_name": "",
            "actor_role": "",
            "target_type": "tenant",
            "target_id": target_id,
            "target_name": target_name,
            "tenant_id": tenant_id or target_id,
            "details": details or {},
            "previous_state": previous_state,
            "new_state": new_state,
            "is_sensitive": is_sensitive,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        await self.audit_collection.insert_one(log_entry)


# Export
__all__ = ["TenantEngine"]
