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

from sqlalchemy import select, and_, func, desc as sa_desc

from pg_models import School, AuditLog, Student, Teacher, Class
from engines.sql_utils import model_to_dict, models_to_dicts, dict_to_model, apply_updates

from models.foundation import (
    TenantConfiguration, TenantStatus, TenantType,
    AuditAction,
)


class TenantEngine:
    """
    Core Tenant Engine for NASSAQ
    Manages multi-tenant isolation and tenant lifecycle
    """

    def __init__(self, db):
        self.db = db

    @property
    def session(self):
        return self.db.session

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

        code = kwargs.get("code")
        if not code:
            code = f"SCH-{str(uuid.uuid4())[:8].upper()}"

        stmt = select(School).where(School.code == code).limit(1)
        result = await self.session.execute(stmt)
        if result.scalars().first():
            raise ValueError("كود المدرسة مستخدم مسبقاً")

        config = TenantConfiguration()
        if kwargs.get("configuration"):
            config = TenantConfiguration(**kwargs["configuration"])

        obj = dict_to_model(School, {
            "id": tenant_id,
            "name": name_ar,
            "name_en": name_en,
            "code": code,
            "status": TenantStatus.PENDING.value,
            "school_type": kwargs.get("school_type", "private"),
            "email": kwargs.get("email"),
            "phone": kwargs.get("phone"),
            "region": kwargs.get("region"),
            "city": kwargs.get("city"),
            "district": kwargs.get("district"),
            "address": kwargs.get("address"),
            "student_capacity": kwargs.get("student_capacity"),
            "current_students": 0,
            "current_teachers": 0,
            "tenant_type": tenant_type.value,
            "gender": kwargs.get("gender"),
            "website": kwargs.get("website"),
            "ministry_id": kwargs.get("ministry_id"),
            "license_number": kwargs.get("license_number"),
            "configuration": config.model_dump(),
            "setup_completed": False,
            "setup_steps_completed": [],
            "principal_id": kwargs.get("principal_id"),
            "subscription_start": kwargs.get("subscription_start"),
            "subscription_end": kwargs.get("subscription_end"),
            "trial_end": kwargs.get("trial_end"),
            "created_at": now,
            "updated_at": now,
            "created_by": created_by,
        })
        self.session.add(obj)
        await self.session.flush()

        await self._log_action(
            AuditAction.TENANT_CREATED,
            actor_id=created_by,
            target_id=tenant_id,
            target_name=name_ar,
            details={"code": code, "tenant_type": tenant_type.value}
        )

        return model_to_dict(obj)

    async def get_tenant_by_id(self, tenant_id: str) -> Optional[Dict[str, Any]]:
        """Get tenant by ID"""
        stmt = select(School).where(School.id == tenant_id).limit(1)
        result = await self.session.execute(stmt)
        row = result.scalars().first()
        if not row:
            return None
        d = model_to_dict(row)
        d.pop("_id", None)
        return d

    async def get_tenant_by_code(self, code: str) -> Optional[Dict[str, Any]]:
        """Get tenant by code"""
        stmt = select(School).where(School.code == code).limit(1)
        result = await self.session.execute(stmt)
        row = result.scalars().first()
        if not row:
            return None
        d = model_to_dict(row)
        d.pop("_id", None)
        return d

    async def list_tenants(
        self,
        status: Optional[TenantStatus] = None,
        tenant_type: Optional[TenantType] = None,
        region: Optional[str] = None,
        skip: int = 0,
        limit: int = 100
    ) -> Dict[str, Any]:
        """List tenants with filters"""
        conditions = []
        if status:
            conditions.append(School.status == status.value)
        if region:
            conditions.append(School.region == region)

        count_stmt = select(func.count(School.id))
        if conditions:
            count_stmt = count_stmt.where(and_(*conditions))
        total = (await self.session.execute(count_stmt)).scalar() or 0

        stmt = select(School)
        if conditions:
            stmt = stmt.where(and_(*conditions))
        stmt = stmt.order_by(sa_desc(School.created_at)).offset(skip).limit(limit)

        result = await self.session.execute(stmt)
        tenants = []
        for row in result.scalars().all():
            d = model_to_dict(row)
            d.pop("_id", None)
            tenants.append(d)

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

        protected = ["id", "code", "created_at", "created_by"]
        for field in protected:
            updates.pop(field, None)

        updates["updated_at"] = now

        stmt = select(School).where(School.id == tenant_id).limit(1)
        result = await self.session.execute(stmt)
        obj = result.scalars().first()
        if obj:
            apply_updates(obj, updates)
            await self.session.flush()

        await self._log_action(
            AuditAction.TENANT_UPDATED,
            actor_id=updated_by,
            target_id=tenant_id,
            target_name=current.get("name"),
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

        stmt = select(School).where(School.id == tenant_id).limit(1)
        result = await self.session.execute(stmt)
        obj = result.scalars().first()
        if obj:
            obj.status = status.value
            obj.updated_at = now
            await self.session.flush()

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
            target_name=current.get("name"),
            tenant_id=tenant_id,
            details={
                "old_status": old_status,
                "new_status": status.value,
                "reason": reason
            }
        )

        return await self.get_tenant_by_id(tenant_id)

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

        for key, value in config_updates.items():
            current_config[key] = value

        stmt = select(School).where(School.id == tenant_id).limit(1)
        result = await self.session.execute(stmt)
        obj = result.scalars().first()
        if obj:
            apply_updates(obj, {"configuration": current_config, "updated_at": now})
            await self.session.flush()

        ai_keys = ["ai_enabled", "ai_hakim_enabled", "ai_analytics_enabled", "ai_import_enabled"]
        for key in ai_keys:
            if key in config_updates:
                await self._log_action(
                    AuditAction.AI_FEATURE_TOGGLED,
                    actor_id=updated_by,
                    target_id=tenant_id,
                    target_name=current.get("name"),
                    tenant_id=tenant_id,
                    details={
                        "feature": key,
                        "enabled": config_updates[key]
                    },
                    is_sensitive=True
                )

        return await self.get_tenant_by_id(tenant_id)

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
            "updated_at": now,
        }

        if setup_completed and not current.get("setup_completed"):
            updates["setup_completed"] = True
            updates["status"] = TenantStatus.ACTIVE.value

        stmt = select(School).where(School.id == tenant_id).limit(1)
        result = await self.session.execute(stmt)
        obj = result.scalars().first()
        if obj:
            apply_updates(obj, updates)
            await self.session.flush()

        return await self.get_tenant_by_id(tenant_id)

    async def update_health_score(
        self,
        tenant_id: str,
        health_score: float,
        health_details: Optional[Dict[str, Any]] = None
    ):
        """Update tenant health score"""
        now = datetime.now(timezone.utc).isoformat()
        stmt = select(School).where(School.id == tenant_id).limit(1)
        result = await self.session.execute(stmt)
        obj = result.scalars().first()
        if obj:
            apply_updates(obj, {
                "health_score": health_score,
                "last_health_check": now,
                "health_details": health_details or {},
            })
            await self.session.flush()

    async def update_counts(
        self,
        tenant_id: str,
        student_count: Optional[int] = None,
        teacher_count: Optional[int] = None
    ):
        """Update student/teacher counts"""
        updates = {}
        if student_count is not None:
            updates["current_students"] = student_count
        if teacher_count is not None:
            updates["current_teachers"] = teacher_count

        if updates:
            stmt = select(School).where(School.id == tenant_id).limit(1)
            result = await self.session.execute(stmt)
            obj = result.scalars().first()
            if obj:
                apply_updates(obj, updates)
                await self.session.flush()

    async def get_tenant_stats(self, tenant_id: str) -> Dict[str, Any]:
        """Get comprehensive stats for a tenant"""
        tenant = await self.get_tenant_by_id(tenant_id)
        if not tenant:
            raise ValueError("المدرسة غير موجودة")

        sc = select(func.count(Student.id)).where(Student.school_id == tenant_id)
        student_count = (await self.session.execute(sc)).scalar() or 0

        tc = select(func.count(Teacher.id)).where(Teacher.school_id == tenant_id)
        teacher_count = (await self.session.execute(tc)).scalar() or 0

        cc = select(func.count(Class.id)).where(Class.school_id == tenant_id)
        class_count = (await self.session.execute(cc)).scalar() or 0

        await self.update_counts(tenant_id, student_count, teacher_count)

        capacity = tenant.get("student_capacity")
        return {
            "tenant_id": tenant_id,
            "name": tenant.get("name"),
            "status": tenant.get("status"),
            "student_count": student_count,
            "teacher_count": teacher_count,
            "class_count": class_count,
            "student_capacity": capacity,
            "capacity_usage": (student_count / capacity) * 100 if capacity else None,
            "health_score": tenant.get("health_score"),
            "setup_completed": tenant.get("setup_completed"),
            "setup_progress": len(tenant.get("setup_steps_completed", [])) / 5 * 100
        }

    def get_tenant_query(self, tenant_id: str) -> Dict[str, Any]:
        """Get query filter for tenant isolation"""
        return {"school_id": tenant_id}

    async def verify_tenant_access(
        self,
        user_tenant_id: Optional[str],
        target_tenant_id: str,
        user_role: str
    ) -> bool:
        """Verify user has access to a specific tenant"""
        platform_roles = ["platform_admin", "platform_operations_manager", "ministry_rep"]
        if user_role in platform_roles:
            return True
        return user_tenant_id == target_tenant_id

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
        stmt = select(School).where(
            and_(School.status != TenantStatus.ARCHIVED.value)
        )
        result = await self.session.execute(stmt)
        tenants = []
        for row in result.scalars().all():
            d = model_to_dict(row)
            d.pop("_id", None)
            if d.get("tenant_type") == TenantType.PRODUCTION.value:
                tenants.append(d)
        return tenants

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
        obj = AuditLog(
            id=str(uuid.uuid4()),
            action=action.value,
            performed_by=actor_id,
            actor_name="",
            actor_role="",
            target_type="tenant",
            target_id=target_id,
            target_name=target_name,
            school_id=tenant_id or target_id,
            details=details or {},
            previous_state=previous_state,
            new_state=new_state,
            timestamp=datetime.now(timezone.utc),
        )
        self.session.add(obj)
        await self.session.flush()


__all__ = ["TenantEngine"]
