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

from sqlalchemy import select, func, or_

from pg_models import User, AuditLog
from engines.sql_utils import (
    model_to_dict, models_to_dicts, dict_to_model, apply_updates,
    gd_find, gd_find_one, gd_insert, gd_update_one,
)

from src.common.dto.foundation import (
    UserIdentity, UserRelationship, LinkedRole,
    UserRole, AccountStatus, RelationshipType, PermissionScope,
    AuditLog as AuditLogModel, AuditAction
)


class IdentityEngine:
    """
    Core Identity Engine for NASSAQ
    Manages user identities, roles, and relationships
    """

    def __init__(self, db):
        self.db = db

    @property
    def session(self):
        return self.db.session

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
        # Bound any inline avatar before it reaches the User row: this engine
        # bypasses the gd_* helpers, so it must normalise for itself (the ORM
        # validator on User.avatar_url would otherwise reject an oversized
        # value with a programming-error exception).
        avatar_url = kwargs.get("avatar_url")
        if isinstance(avatar_url, str) and avatar_url.startswith("data:image/"):
            from src.common.utils.avatar_image import (
                MAX_IMAGE_FIELD_CHARS,
                AvatarImageError,
                normalize_avatar_data_url_async,
            )
            if len(avatar_url) > MAX_IMAGE_FIELD_CHARS:
                raise ValueError("حجم الصورة كبير جداً (الحد الأقصى 2MB)")
            try:
                avatar_url = await normalize_avatar_data_url_async(avatar_url)
            except AvatarImageError:
                raise ValueError("بيانات الصورة غير صالحة")

        user_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        stmt = select(User).where(User.email == email).limit(1)
        result = await self.session.execute(stmt)
        if result.scalars().first():
            raise ValueError("البريد الإلكتروني مستخدم مسبقاً")

        phone = kwargs.get("phone")
        if phone:
            stmt = select(User).where(User.phone == phone).limit(1)
            result = await self.session.execute(stmt)
            if result.scalars().first():
                raise ValueError("رقم الهاتف مستخدم مسبقاً")

        national_id = kwargs.get("national_id")
        if national_id:
            stmt = select(User).where(User.national_id == national_id).limit(1)
            result = await self.session.execute(stmt)
            if result.scalars().first():
                raise ValueError("رقم الهوية مستخدم مسبقاً")

        role_val = primary_role.value if isinstance(primary_role, UserRole) else primary_role
        linked_roles = []
        if tenant_id:
            linked_roles.append({
                "role": role_val,
                "tenant_id": tenant_id,
                "scope_id": None,
                "is_active": True,
                "assigned_at": now,
                "assigned_by": created_by,
            })

        obj = User(
            id=user_id,
            email=email,
            password_hash=password_hash,
            full_name=full_name,
            full_name_en=kwargs.get("full_name_en"),
            phone=phone,
            national_id=national_id,
            role=role_val,
            status=AccountStatus.ACTIVE.value,
            is_active=True,
            must_change_password=kwargs.get("must_change_password", True),
            primary_tenant_id=tenant_id,
            tenant_id=tenant_id,
            linked_roles=linked_roles,
            preferred_language=kwargs.get("preferred_language", "ar"),
            preferred_theme=kwargs.get("preferred_theme", "light"),
            avatar_url=avatar_url,
            email_verified=False,
            failed_login_attempts=0,
        )
        self.session.add(obj)
        await self.session.flush()

        await self._log_action(
            AuditAction.USER_CREATED,
            actor_id=created_by or "system",
            actor_name="System" if not created_by else "",
            target_type="user",
            target_id=user_id,
            target_name=full_name,
            tenant_id=tenant_id,
            details={"role": role_val}
        )

        user_doc = model_to_dict(obj)
        user_doc.pop("password_hash", None)
        user_doc["primary_role"] = role_val
        user_doc["created_by"] = created_by
        return user_doc

    async def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        stmt = select(User).where(User.id == user_id).limit(1)
        result = await self.session.execute(stmt)
        user = result.scalars().first()
        if not user:
            return None
        d = model_to_dict(user)
        d.pop("password_hash", None)
        d["primary_role"] = d.get("role")
        return d

    async def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        stmt = select(User).where(User.email == email).limit(1)
        result = await self.session.execute(stmt)
        user = result.scalars().first()
        if not user:
            return None
        d = model_to_dict(user)
        d["primary_role"] = d.get("role")
        return d

    async def update_user(
        self,
        user_id: str,
        updates: Dict[str, Any],
        updated_by: str
    ) -> Dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()

        current_user = await self.get_user_by_id(user_id)
        if not current_user:
            raise ValueError("المستخدم غير موجود")

        updates["updated_at"] = now

        protected_fields = ["id", "email", "password_hash", "created_at", "created_by"]
        for field in protected_fields:
            updates.pop(field, None)

        stmt = select(User).where(User.id == user_id).limit(1)
        result = await self.session.execute(stmt)
        user_obj = result.scalars().first()
        apply_updates(user_obj, updates)
        await self.session.flush()

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
        now = datetime.now(timezone.utc)

        current_user = await self.get_user_by_id(user_id)
        if not current_user:
            raise ValueError("المستخدم غير موجود")

        is_active = status in [AccountStatus.ACTIVE]

        stmt = select(User).where(User.id == user_id).limit(1)
        result = await self.session.execute(stmt)
        user_obj = result.scalars().first()
        user_obj.status = status.value
        user_obj.is_active = is_active
        user_obj.updated_at = now
        await self.session.flush()

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
        now = datetime.now(timezone.utc).isoformat()

        user = await self.get_user_by_id(user_id)
        if not user:
            raise ValueError("المستخدم غير موجود")

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

        stmt = select(User).where(User.id == user_id).limit(1)
        result = await self.session.execute(stmt)
        user_obj = result.scalars().first()
        roles = list(user_obj.linked_roles or [])
        roles.append(new_role)
        user_obj.linked_roles = roles
        user_obj.updated_at = datetime.now(timezone.utc)
        await self.session.flush()

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
        now = datetime.now(timezone.utc)

        user = await self.get_user_by_id(user_id)
        if not user:
            raise ValueError("المستخدم غير موجود")

        if user.get("primary_role") == role.value and not tenant_id:
            raise ValueError("لا يمكن إزالة الدور الأساسي")

        stmt = select(User).where(User.id == user_id).limit(1)
        result = await self.session.execute(stmt)
        user_obj = result.scalars().first()
        roles = list(user_obj.linked_roles or [])
        for r in roles:
            if r.get("role") == role.value and r.get("tenant_id") == tenant_id:
                r["is_active"] = False
        user_obj.linked_roles = roles
        user_obj.updated_at = now
        await self.session.flush()

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
        user = await self.get_user_by_id(user_id)
        if not user:
            return []

        roles = []
        roles.append({
            "role": user.get("primary_role"),
            "tenant_id": user.get("primary_tenant_id"),
            "is_primary": True,
            "is_active": True
        })

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
        user = await self.get_user_by_id(user_id)
        if not user:
            raise ValueError("المستخدم غير موجود")

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
        now = datetime.now(timezone.utc).isoformat()

        user1 = await self.get_user_by_id(user_id_1)
        user2 = await self.get_user_by_id(user_id_2)

        if not user1 or not user2:
            raise ValueError("أحد المستخدمين غير موجود")

        existing = await gd_find_one(self.session, "user_relationships", {
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

        await gd_insert(self.session, "user_relationships", relationship_doc)

        return relationship_doc

    async def get_user_relationships(
        self,
        user_id: str,
        relationship_type: Optional[RelationshipType] = None
    ) -> List[Dict[str, Any]]:
        filters1 = {"user_id_1": user_id, "is_active": True}
        filters2 = {"user_id_2": user_id, "is_active": True}

        if relationship_type:
            filters1["relationship_type"] = relationship_type.value
            filters2["relationship_type"] = relationship_type.value

        results1 = await gd_find(self.session, "user_relationships", filters1, limit=1000)
        results2 = await gd_find(self.session, "user_relationships", filters2, limit=1000)

        seen = set()
        relationships = []
        for r in results1 + results2:
            rid = r.get("id")
            if rid not in seen:
                seen.add(rid)
                relationships.append(r)

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
        user = await self.get_user_by_id(user_id)
        if not user:
            return []

        potential_relationships = []

        phone = user.get("phone")
        if phone:
            stmt = select(User).where(
                User.phone == phone,
                User.id != user_id
            ).limit(10)
            result = await self.session.execute(stmt)
            for u in result.scalars().all():
                d = model_to_dict(u)
                d.pop("password_hash", None)
                potential_relationships.append({
                    "user": d,
                    "detection_method": "phone",
                    "confidence": 0.9
                })

        national_id = user.get("national_id")
        if national_id and len(national_id) >= 10:
            prefix = national_id[:4]
            stmt = select(User).where(
                User.national_id.ilike(f"{prefix}%"),
                User.id != user_id
            ).limit(20)
            result = await self.session.execute(stmt)
            for u in result.scalars().all():
                d = model_to_dict(u)
                d.pop("password_hash", None)
                if not any(p["user"].get("id") == d.get("id") for p in potential_relationships):
                    potential_relationships.append({
                        "user": d,
                        "detection_method": "national_id_pattern",
                        "confidence": 0.6
                    })

        return potential_relationships

    async def verify_relationship(
        self,
        relationship_id: str,
        verified_by: str
    ) -> Dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        await gd_update_one(self.session, "user_relationships", {"id": relationship_id}, {
            "is_verified": True,
            "verified_by": verified_by,
            "verified_at": now
        })
        return await gd_find_one(self.session, "user_relationships", {"id": relationship_id})

    # ============== PASSWORD MANAGEMENT ==============

    async def record_failed_login(self, user_id: str) -> int:
        stmt = select(User).where(User.id == user_id).limit(1)
        result = await self.session.execute(stmt)
        user_obj = result.scalars().first()
        if not user_obj:
            return 0

        user_obj.failed_login_attempts = (user_obj.failed_login_attempts or 0) + 1
        await self.session.flush()

        attempts = user_obj.failed_login_attempts

        if attempts >= 5:
            user_obj.status = AccountStatus.LOCKED.value
            user_obj.locked_until = datetime.now(timezone.utc)
            await self.session.flush()

        return attempts

    async def reset_failed_login(self, user_id: str):
        stmt = select(User).where(User.id == user_id).limit(1)
        result = await self.session.execute(stmt)
        user_obj = result.scalars().first()
        if user_obj:
            user_obj.failed_login_attempts = 0
            user_obj.locked_until = None
            await self.session.flush()

    async def change_password(
        self,
        user_id: str,
        new_password_hash: str,
        changed_by: Optional[str] = None
    ):
        now = datetime.now(timezone.utc)

        stmt = select(User).where(User.id == user_id).limit(1)
        result = await self.session.execute(stmt)
        user_obj = result.scalars().first()
        if user_obj:
            user_obj.password_hash = new_password_hash
            user_obj.must_change_password = False
            user_obj.last_password_change = now
            user_obj.updated_at = now
            await self.session.flush()

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
        try:
            action_val = action.value if hasattr(action, "value") else str(action)
            log_data = {
                "actor_name": actor_name,
                "target_name": target_name,
                "previous_state": previous_state,
                "new_state": new_state,
            }
            if details:
                log_data.update(details)

            obj = AuditLog(
                id=str(uuid.uuid4()),
                school_id=tenant_id,
                action=action_val,
                performed_by=actor_id,
                entity_type=target_type,
                entity_id=target_id,
                details=details or {},
                data=log_data,
            )
            self.session.add(obj)
            await self.session.flush()
        except Exception as e:
            import logging
            logging.getLogger("nassaq.identity").warning(f"Failed to write audit log: {e}")


__all__ = ["IdentityEngine"]
