"""
NASSAQ Route Module: User management, profiles, sessions, avatars
Auto-consolidated during Phase 8 modularization.
"""
from fastapi import APIRouter, HTTPException, Depends, status, Header, Query, Body, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import Response
from starlette.responses import StreamingResponse
from pydantic import BaseModel, Field, ConfigDict, EmailStr, model_validator
from typing import List, Optional, Any, Dict
from datetime import datetime, timezone, timedelta
import uuid, os, logging, json, random, re, io, base64

from dependencies import (
    db, get_current_user, require_roles, UserRole, SchoolStatus,
    hash_password, verify_password, create_access_token,
    JWT_SECRET, JWT_ALGORITHM, ACCESS_TOKEN_EXPIRE, security, logger,
    audit_engine, AuditAction, AuditSeverity,
    smart_scheduling_engine, TimetableRunStatus, TimetableStatus,
    ConflictType, ConflictSeverity, PreValidationResult, GenerationResult,
    hakim_engine, reporting_engine, export_engine, session_engine,
    REPORT_TYPES, generate_student_qr_code,
    require_recent_mfa_403_if_independent_teacher,
)

from shared_models import (
    UserResponse
)

router = APIRouter()

# Task #201 — IT §5.7 step-up backfill: a single shared dependency
# instance so FastAPI can dedupe it across replays.
_REQUIRE_RECENT_MFA_403_IT = require_recent_mfa_403_if_independent_teacher()



# ============== USER MANAGEMENT ROUTES ==============
class PlatformUserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    role: str  # Will be validated against allowed roles
    phone: Optional[str] = None
    region: Optional[str] = None
    city: Optional[str] = None
    educational_department: Optional[str] = None
    school_name_ar: Optional[str] = None
    school_name_en: Optional[str] = None
    tenant_id: Optional[str] = None
    permissions: List[str] = []

class PlatformUserResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    email: str
    full_name: str
    role: str
    phone: Optional[str] = None
    region: Optional[str] = None
    city: Optional[str] = None
    educational_department: Optional[str] = None
    school_name_ar: Optional[str] = None
    school_name_en: Optional[str] = None
    permissions: List[str] = []
    is_active: bool = True
    must_change_password: bool = True
    created_at: str
    created_by: str

@router.post("/users/create", response_model=PlatformUserResponse)
async def create_platform_user(
    user_data: PlatformUserCreate,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))
):
    """
    Create a new platform user (admin or teacher) - Platform Admin only
    """
    allowed_roles = [r.value for r in UserRole]
    if user_data.role not in allowed_roles:
        raise HTTPException(status_code=400, detail="نوع الحساب غير مسموح به")
    
    # Check if email exists
    existing_email = await gd_find_one(db.session, "users", {"email": user_data.email})
    if existing_email:
        raise HTTPException(status_code=400, detail="البريد الإلكتروني مستخدم مسبقاً")
    
    # Check if phone exists (if provided)
    if user_data.phone:
        existing_phone = await gd_find_one(db.session, "users", {"phone": user_data.phone})
        if existing_phone:
            raise HTTPException(status_code=400, detail="رقم الهاتف مستخدم مسبقاً")
    
    # Create user
    user_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    
    new_user = {
        "id": user_id,
        "email": user_data.email,
        "password_hash": hash_password(user_data.password),
        "full_name": user_data.full_name,
        "role": user_data.role,
        "phone": user_data.phone,
        "region": user_data.region,
        "city": user_data.city,
        "educational_department": user_data.educational_department,
        "school_name_ar": user_data.school_name_ar,
        "school_name_en": user_data.school_name_en,
        "tenant_id": user_data.tenant_id,
        "permissions": user_data.permissions,
        "is_active": True,
        "must_change_password": True,  # Force password change on first login
        "preferred_language": "ar",
        "preferred_theme": "light",
        "created_at": now,
        "updated_at": now,
        "created_by": current_user["id"],
    }
    
    await gd_insert(db.session, "users", new_user)
    
    # Log this action using the new Audit Engine
    await audit_engine.log_data_change(
        action=AuditAction.USER_CREATED.value,
        performed_by=current_user["id"],
        entity_type="user",
        entity_id=user_id,
        tenant_id=current_user.get("tenant_id"),
        new_values={
            "role": user_data.role,
            "email": user_data.email,
            "full_name": user_data.full_name,
            "permissions_count": len(user_data.permissions)
        }
    )
    
    return PlatformUserResponse(
        id=user_id,
        email=user_data.email,
        full_name=user_data.full_name,
        role=user_data.role,
        phone=user_data.phone,
        region=user_data.region,
        city=user_data.city,
        educational_department=user_data.educational_department,
        school_name_ar=user_data.school_name_ar,
        school_name_en=user_data.school_name_en,
        permissions=user_data.permissions,
        is_active=True,
        must_change_password=True,
        created_at=now,
        created_by=current_user["id"]
    )

@router.get("/users/management-stats")
async def get_users_management_stats(
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN])),
):
    """Real-time stats for the Users Management page analysis cards.
    All values are direct DB counts — no mock data, no hardcoded values."""
    total_users = await gd_count(db.session, "users", {})
    active_users = await gd_count(db.session, "users", {"is_active": {"$ne": False}})
    suspended_users = await gd_count(db.session, "users", {"is_active": False})

    platform_admins = await gd_count(db.session, "users", {"role": {"$in": ["platform_admin", "platform_operations_manager"]}})
    school_admins = await gd_count(db.session, "users", {"role": {"$in": ["school_principal", "school_sub_admin", "school_manager"]}})
    teachers = await gd_count(db.session, "users", {"role": "teacher"})
    students = await gd_count(db.session, "users", {"role": "student"})
    parents = await gd_count(db.session, "users", {"role": "parent"})

    pending_requests = await gd_count(db.session, "registration_requests", {"status": "pending"})

    return {
        "total_users": total_users,
        "active_users": active_users,
        "suspended_users": suspended_users,
        "platform_admins": platform_admins,
        "school_admins": school_admins,
        "teachers": teachers,
        "students": students,
        "parents": parents,
        "pending_requests": pending_requests,
    }


@router.get("/users/platform-users")
async def get_platform_users(
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN])),
    skip: int = 0,
    limit: int = 100,
    role: Optional[str] = None,
    search: Optional[str] = None,
    status: Optional[str] = None,
    ai_status: Optional[str] = None,
    account_type: Optional[str] = None,
):
    """
    Get list of all platform users for admin management.
    Supports server-side filtering by role, status, AI, account_type and search.
    """
    query = {}
    
    if status and status != 'all':
        if status == 'active':
            query["is_active"] = {"$ne": False}
        elif status == 'suspended':
            query["is_active"] = False

    if ai_status and ai_status != 'all':
        if ai_status == 'enabled':
            query["ai_enabled"] = True
        elif ai_status == 'disabled':
            query["ai_enabled"] = {"$ne": True}

    role_conditions = []
    if role and role != 'all':
        role_conditions.append({"role": role})

    if account_type and account_type != 'all':
        if account_type == 'platform':
            role_conditions.append({"role": {"$regex": "^platform_", "$options": "i"}})
        elif account_type == 'school':
            role_conditions.append({"role": {"$in": ["school_principal", "school_admin", "school_sub_admin", "teacher", "student", "parent", "driver", "gatekeeper"]}})
        elif account_type == 'independent':
            role_conditions.append({"role": "independent_teacher"})
        elif account_type == 'testing':
            role_conditions.append({"role": {"$regex": "test", "$options": "i"}})

    if not role_conditions:
        pass
    elif len(role_conditions) == 1:
        query.update(role_conditions[0])
    else:
        query.setdefault("$and", []).extend(role_conditions)
    
    if search:
        import re as _re
        safe_search = _re.escape(search)
        search_conditions = [
            {"full_name": {"$regex": safe_search, "$options": "i"}},
            {"email": {"$regex": safe_search, "$options": "i"}},
            {"phone": {"$regex": safe_search, "$options": "i"}},
        ]
        if "$or" in query:
            query["$and"] = [{"$or": query.pop("$or")}, {"$or": search_conditions}]
        else:
            query["$or"] = search_conditions

    users = await gd_find(db.session, "users", query, offset=skip, limit=limit)
    
    total = await gd_count(db.session, "users", query)

    return {
        "users": users,
        "total": total,
        "skip": skip,
        "limit": limit
    }

@router.delete("/users/{user_id}")
async def delete_platform_user(
    user_id: str,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))
):
    """
    Soft delete a platform user
    """
    user = await gd_find_one(db.session, "users", {"id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="المستخدم غير موجود")
    
    # Cannot delete platform_admin
    if user.get("role") == "platform_admin":
        raise HTTPException(status_code=400, detail="لا يمكن حذف مدير المنصة")
    
    # Soft delete - just mark as inactive
    await gd_update_one(db.session, "users", {"id": user_id}, {
            "is_active": False,
            "deleted_at": datetime.now(timezone.utc).isoformat(),
            "deleted_by": current_user["id"]
        })
    
    # Audit log
    audit_log = {
        "id": str(uuid.uuid4()),
        "action": "user_deleted",
        "action_by": current_user["id"],
        "action_by_name": current_user.get("full_name", ""),
        "target_type": "user",
        "target_id": user_id,
        "target_name": user.get("full_name", ""),
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    await gd_insert(db.session, "audit_logs", audit_log)
    
    return {"message": "تم حذف المستخدم بنجاح"}




# ============== USERS MANAGEMENT ROUTES ==============
@router.get("/users", response_model=List[UserResponse])
async def get_users(
    role: Optional[str] = None,
    tenant_id: Optional[str] = None,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.SCHOOL_SUB_ADMIN]))
):
    query = {}
    
    if current_user["role"] in [UserRole.SCHOOL_PRINCIPAL.value, UserRole.SCHOOL_ADMIN.value, UserRole.SCHOOL_SUB_ADMIN.value]:
        query["tenant_id"] = current_user.get("tenant_id")
    elif tenant_id:
        query["tenant_id"] = tenant_id
    
    if role:
        query["role"] = role
    
    users = await gd_find(db.session, "users", query, limit=1000)
    return [UserResponse(**u) for u in users]

class UserStatusRequest(BaseModel):
    is_active: bool

@router.put("/users/{user_id}/status")
@router.patch("/users/{user_id}/status")
async def update_user_status(
    user_id: str,
    status_data: UserStatusRequest,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN]))
):
    user = await gd_find_one(db.session, "users", {"id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="المستخدم غير موجود")

    if current_user.get("role") != UserRole.PLATFORM_ADMIN.value:
        if user.get("tenant_id") != current_user.get("tenant_id"):
            raise HTTPException(status_code=403, detail="غير مصرح لك بتعديل بيانات هذا المستخدم")

    old_status = user.get("is_active", True)
    await gd_update_one(db.session, "users", {"id": user_id}, {"is_active": status_data.is_active, "updated_at": datetime.now(timezone.utc).isoformat()})

    audit_log = {
        "id": str(uuid.uuid4()),
        "action": "user_activated" if status_data.is_active else "user_suspended",
        "action_by": current_user["id"],
        "action_by_name": current_user.get("full_name", ""),
        "target_type": "user",
        "target_id": user_id,
        "target_name": user.get("full_name", ""),
        "details": {
            "old_status": "active" if old_status else "suspended",
            "new_status": "active" if status_data.is_active else "suspended",
        },
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    await gd_insert(db.session, "audit_logs", audit_log)

    return {"message": "تم تحديث حالة المستخدم"}




# ============== USER DETAILS & MANAGEMENT ROUTES ==============

@router.get("/users/{user_id}")
async def get_user_by_id(
    user_id: str,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))
):
    """Get detailed user information by ID"""
    user = await gd_find_one(db.session, "users", {"id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="المستخدم غير موجود")
    
    # Get creator name if exists
    if user.get("created_by"):
        creator = await gd_find_one(db.session, "users", {"id": user["created_by"]})
        user["created_by_name"] = creator.get("full_name") if creator else None
    
    return user

class UserUpdateRequest(BaseModel):
    full_name_ar: Optional[str] = None
    full_name_en: Optional[str] = None
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    region: Optional[str] = None
    city: Optional[str] = None
    educational_department: Optional[str] = None
    avatar_url: Optional[str] = None
    role: Optional[str] = None
    tenant_id: Optional[str] = None
    school_name: Optional[str] = None

@router.put("/users/{user_id}")
@router.patch("/users/{user_id}")
async def update_user(
    user_id: str,
    user_data: UserUpdateRequest,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))
):
    """Update user information"""
    user = await gd_find_one(db.session, "users", {"id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="المستخدم غير موجود")
    
    updates = {"updated_at": datetime.now(timezone.utc).isoformat()}
    
    if user_data.full_name_ar:
        updates["full_name_ar"] = user_data.full_name_ar
        updates["full_name"] = user_data.full_name_ar
    if user_data.full_name_en:
        updates["full_name_en"] = user_data.full_name_en
    if user_data.full_name:
        updates["full_name"] = user_data.full_name
    if user_data.email:
        # Check email uniqueness
        existing = await gd_find_one(db.session, "users", {"email": user_data.email, "id": {"$ne": user_id}})
        if existing:
            raise HTTPException(status_code=400, detail="البريد الإلكتروني مستخدم مسبقاً")
        updates["email"] = user_data.email
    if user_data.phone:
        updates["phone"] = user_data.phone
    if user_data.region:
        updates["region"] = user_data.region
    if user_data.city:
        updates["city"] = user_data.city
    if user_data.educational_department:
        updates["educational_department"] = user_data.educational_department
    if user_data.avatar_url:
        updates["avatar_url"] = user_data.avatar_url
    if user_data.tenant_id is not None:
        updates["tenant_id"] = user_data.tenant_id if user_data.tenant_id else None
    if user_data.school_name is not None:
        updates["school_name"] = user_data.school_name if user_data.school_name else None
    if user_data.role:
        valid_roles = [r.value for r in UserRole]
        if user_data.role not in valid_roles:
            raise HTTPException(status_code=400, detail=f"الدور غير صالح. الأدوار المسموحة: {', '.join(valid_roles)}")
        old_role = user.get("role", "")
        updates["role"] = user_data.role

    # When role or tenant_id changes, bump last_password_change to invalidate
    # all outstanding tokens — including switched/impersonation ones.
    # Both get_current_user() and decode_token_for_ws() reject tokens whose
    # iat < last_password_change, so this ensures entitlement changes take
    # effect immediately even for already-issued switched tokens.
    _role_or_tenant_changed = (
        ("role" in updates and updates["role"] != user.get("role"))
        or ("tenant_id" in updates and updates["tenant_id"] != user.get("tenant_id"))
    )
    if _role_or_tenant_changed:
        updates["last_password_change"] = datetime.now(timezone.utc).isoformat()

    await gd_update_one(db.session, "users", {"id": user_id}, updates)
    
    field_changes = {}
    for field, new_val in updates.items():
        if field == "updated_at":
            continue
        old_val = user.get(field)
        if old_val != new_val:
            field_changes[field] = {"old": old_val, "new": new_val}

    audit_log = {
        "id": str(uuid.uuid4()),
        "action": "user_updated",
        "action_by": current_user["id"],
        "action_by_name": current_user.get("full_name", ""),
        "target_type": "user",
        "target_id": user_id,
        "target_name": user.get("full_name", ""),
        "changes": field_changes,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    if "role" in field_changes:
        audit_log["action"] = "user_role_changed"
        audit_log["old_role"] = field_changes["role"]["old"]
        audit_log["new_role"] = field_changes["role"]["new"]
    await gd_insert(db.session, "audit_logs", audit_log)
    
    return {"message": "تم تحديث البيانات بنجاح"}

class PermissionsUpdateRequest(BaseModel):
    permissions: List[str]

@router.put("/users/{user_id}/permissions")
async def update_user_permissions(
    user_id: str,
    data: PermissionsUpdateRequest,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))
):
    """Update user permissions"""
    user = await gd_find_one(db.session, "users", {"id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="المستخدم غير موجود")
    
    old_permissions = user.get("permissions", [])
    
    await gd_update_one(db.session, "users", {"id": user_id}, {
            "permissions": data.permissions,
            "updated_at": datetime.now(timezone.utc).isoformat()
        })
    
    # Audit log
    audit_log = {
        "id": str(uuid.uuid4()),
        "action": "permissions_updated",
        "action_by": current_user["id"],
        "action_by_name": current_user.get("full_name", ""),
        "target_type": "user",
        "target_id": user_id,
        "target_name": user.get("full_name", ""),
        "details": {
            "old_permissions": old_permissions,
            "new_permissions": data.permissions,
            "added": [p for p in data.permissions if p not in old_permissions],
            "removed": [p for p in old_permissions if p not in data.permissions]
        },
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    await gd_insert(db.session, "audit_logs", audit_log)
    
    return {"message": "تم تحديث الصلاحيات بنجاح"}

class PasswordResetRequest(BaseModel):
    new_password: str

@router.post("/users/{user_id}/reset-password")
async def reset_user_password(
    user_id: str,
    data: PasswordResetRequest,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN]))
):
    """Reset user password (admin only)"""
    user = await gd_find_one(db.session, "users", {"id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="المستخدم غير موجود")

    if current_user.get("role") != UserRole.PLATFORM_ADMIN.value:
        if user.get("tenant_id") != current_user.get("tenant_id"):
            raise HTTPException(status_code=403, detail="غير مصرح لك بتعديل بيانات هذا المستخدم")

    await gd_update_one(db.session, "users", {"id": user_id}, {
            "password_hash": hash_password(data.new_password),
            "must_change_password": True,
            "password_reset_at": datetime.now(timezone.utc).isoformat(),
            "password_reset_by": current_user["id"],
            "updated_at": datetime.now(timezone.utc).isoformat()
        })
    
    # Audit log
    audit_log = {
        "id": str(uuid.uuid4()),
        "action": "password_reset",
        "action_by": current_user["id"],
        "action_by_name": current_user.get("full_name", ""),
        "target_type": "user",
        "target_id": user_id,
        "target_name": user.get("full_name", ""),
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    await gd_insert(db.session, "audit_logs", audit_log)

    try:
        from engines.email_service import send_admin_password_reset_notification
        user_email = user.get("email", "")
        if user_email:
            send_admin_password_reset_notification(
                to_email=user_email,
                user_name=user.get("full_name", ""),
                admin_name=current_user.get("full_name", "المدير"),
            )
    except Exception as e:
        logger.warning(f"Failed to send admin reset notification email: {e}")
    
    return {"message": "تم إعادة تعيين كلمة المرور بنجاح"}

@router.post("/users/{user_id}/suspend")
async def suspend_user(
    user_id: str,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN]))
):
    """Toggle user suspension status"""
    user = await gd_find_one(db.session, "users", {"id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="المستخدم غير موجود")

    if current_user.get("role") != UserRole.PLATFORM_ADMIN.value:
        if user.get("tenant_id") != current_user.get("tenant_id"):
            raise HTTPException(status_code=403, detail="غير مصرح لك بتعديل بيانات هذا المستخدم")

    # Cannot suspend platform_admin
    if user.get("role") == "platform_admin":
        raise HTTPException(status_code=400, detail="لا يمكن تعليق حساب مدير المنصة")
    
    new_status = not user.get("is_active", True)
    
    await gd_update_one(db.session, "users", {"id": user_id}, {
            "is_active": new_status,
            "suspended_at": datetime.now(timezone.utc).isoformat() if not new_status else None,
            "suspended_by": current_user["id"] if not new_status else None,
            "updated_at": datetime.now(timezone.utc).isoformat()
        })
    
    # Audit log
    audit_log = {
        "id": str(uuid.uuid4()),
        "action": "user_suspended" if not new_status else "user_activated",
        "action_by": current_user["id"],
        "action_by_name": current_user.get("full_name", ""),
        "target_type": "user",
        "target_id": user_id,
        "target_name": user.get("full_name", ""),
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    await gd_insert(db.session, "audit_logs", audit_log)
    
    return {
        "message": "تم تعليق الحساب بنجاح" if not new_status else "تم تفعيل الحساب بنجاح",
        "is_active": new_status
    }

class NotificationRequest(BaseModel):
    title: str
    message: str
    type: str = "system"

@router.post("/users/{user_id}/notify")
async def send_user_notification(
    user_id: str,
    data: NotificationRequest,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))
):
    """Send notification to a user"""
    user = await gd_find_one(db.session, "users", {"id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="المستخدم غير موجود")
    
    notification = {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "title": data.title,
        "message": data.message,
        "type": data.type,
        "sent_by": current_user["id"],
        "sent_by_name": current_user.get("full_name", ""),
        "is_read": False,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await gd_insert(db.session, "notifications", notification)
    
    return {"message": "تم إرسال الإشعار بنجاح", "notification_id": notification["id"]}

import base64
from engines.sql_utils import gd_find, gd_find_one, gd_insert, gd_insert_many, gd_update_one, gd_update_many, gd_count, gd_delete_one, gd_delete_many, gd_distinct, gd_upsert, _gd_aggregate

class ImageUploadRequest(BaseModel):
    image_data: str  # Base64 encoded image

@router.post("/users/{user_id}/upload-image")
async def upload_user_image(
    user_id: str,
    data: ImageUploadRequest,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))
):
    """Upload user profile image (base64)"""
    MAX_B64_LENGTH = 2 * 1024 * 1024
    if len(data.image_data) > MAX_B64_LENGTH:
        raise HTTPException(status_code=413, detail="حجم الصورة كبير جداً (الحد الأقصى 2MB) | Image too large (max 2MB)")

    allowed_prefixes = ("data:image/jpeg;base64,", "data:image/png;base64,", "data:image/webp;base64,")
    if not data.image_data.startswith(allowed_prefixes):
        raise HTTPException(status_code=400, detail="صيغة الصورة غير مدعومة (فقط JPEG, PNG, WEBP) | Unsupported image format (only JPEG, PNG, WEBP)")

    try:
        b64_content = data.image_data.split(",", 1)[1]
        base64.b64decode(b64_content, validate=True)
    except Exception:
        raise HTTPException(status_code=400, detail="بيانات الصورة غير صالحة | Invalid image data")

    user = await gd_find_one(db.session, "users", {"id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="المستخدم غير موجود")
    
    await gd_update_one(db.session, "users", {"id": user_id}, {
            "avatar_url": data.image_data,
            "updated_at": datetime.now(timezone.utc).isoformat()
        })
    
    return {"message": "تم رفع الصورة بنجاح", "avatar_url": data.image_data}

@router.get("/users/{user_id}/activity")
async def get_user_activity(
    user_id: str,
    limit: int = 50,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))
):
    """Get user activity logs"""
    user = await gd_find_one(db.session, "users", {"id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="المستخدم غير موجود")
    
    # Get activity from audit logs
    activities = await gd_find(db.session, "audit_logs", {"$or": [
            {"action_by": user_id},
            {"target_id": user_id}
        ]}, order_by="timestamp", desc_order=True, limit=limit)
    
    return {"activities": activities, "total": len(activities)}





# ============== USER PROFILE APIs ==============
class UserProfileUpdate(BaseModel):
    full_name: Optional[str] = None
    full_name_en: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    avatar_url: Optional[str] = None

class UserPreferencesUpdate(BaseModel):
    language: Optional[str] = None
    theme: Optional[str] = None
    time_format: Optional[str] = None
    date_format: Optional[str] = None
    first_day_of_week: Optional[str] = None
    # Task #200 §5.8 — Independent-teacher communication preferences
    # (default channel + quiet hours). Persisted as a JSONB blob inside
    # the existing `users.notification_preferences` column under the key
    # `it_communication`. No new persistence layer is introduced.
    it_communication: Optional[Dict[str, Any]] = None

class UserNotificationSettings(BaseModel):
    email_notifications: Optional[bool] = None
    sms_notifications: Optional[bool] = None
    push_notifications: Optional[bool] = None
    attendance_alerts: Optional[bool] = None
    grade_alerts: Optional[bool] = None
    behavior_alerts: Optional[bool] = None
    announcement_alerts: Optional[bool] = None
    weekly_digest: Optional[bool] = None

@router.put("/users/me", response_model=UserResponse)
async def update_current_user_profile(
    data: UserProfileUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Update current user's profile"""
    update_data = {"updated_at": datetime.now(timezone.utc).isoformat()}
    
    if data.full_name is not None:
        from engines.name_validation import validate_personal_name
        valid, err_msg = validate_personal_name(data.full_name)
        if not valid:
            raise HTTPException(status_code=400, detail=err_msg)
        update_data["full_name"] = data.full_name
    if data.full_name_en is not None:
        update_data["full_name_en"] = data.full_name_en
    if data.email is not None:
        # Check if email is already used by another user
        existing = await gd_find_one(db.session, "users", {"email": data.email, "id": {"$ne": current_user["id"]}})
        if existing:
            raise HTTPException(status_code=400, detail="البريد الإلكتروني مستخدم مسبقاً")
        update_data["email"] = data.email
    if data.phone is not None:
        # Check if phone is already used by another user
        existing = await gd_find_one(db.session, "users", {"phone": data.phone, "id": {"$ne": current_user["id"]}})
        if existing:
            raise HTTPException(status_code=400, detail="رقم الهاتف مستخدم مسبقاً")
        update_data["phone"] = data.phone
    if data.avatar_url is not None:
        update_data["avatar_url"] = data.avatar_url
    
    await gd_update_one(db.session, "users", {"id": current_user["id"]}, update_data)
    
    updated_user = await gd_find_one(db.session, "users", {"id": current_user["id"]})
    return UserResponse(**updated_user)

@router.get("/users/me/preferences")
async def get_current_user_preferences(
    current_user: dict = Depends(get_current_user)
):
    """Get current user's preferences"""
    notif_prefs = current_user.get("notification_preferences") or {}
    if not isinstance(notif_prefs, dict):
        notif_prefs = {}
    it_comm = notif_prefs.get("it_communication") or {}
    if not isinstance(it_comm, dict):
        it_comm = {}
    return {
        "language": current_user.get("preferred_language", "ar"),
        "theme": current_user.get("preferred_theme", "light"),
        "time_format": current_user.get("time_format", "12h"),
        "date_format": current_user.get("date_format", "dd/mm/yyyy"),
        "first_day_of_week": current_user.get("first_day_of_week", "sunday"),
        "it_communication": {
            "default_channel": it_comm.get("default_channel", "email"),
            "quiet_hours_start": it_comm.get("quiet_hours_start", "21:00"),
            "quiet_hours_end": it_comm.get("quiet_hours_end", "07:00"),
        },
    }

@router.put("/users/me/preferences")
async def update_current_user_preferences(
    data: UserPreferencesUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Update current user's preferences"""
    update_data = {"updated_at": datetime.now(timezone.utc).isoformat()}
    
    if data.language is not None:
        update_data["preferred_language"] = data.language
    if data.theme is not None:
        update_data["preferred_theme"] = data.theme
    if data.time_format is not None:
        update_data["time_format"] = data.time_format
    if data.date_format is not None:
        update_data["date_format"] = data.date_format
    if data.first_day_of_week is not None:
        update_data["first_day_of_week"] = data.first_day_of_week
    # Task #200 §5.8 — merge IT communication prefs into existing
    # `users.notification_preferences` JSONB blob without touching other keys.
    if data.it_communication is not None:
        existing = current_user.get("notification_preferences") or {}
        if not isinstance(existing, dict):
            existing = {}
        prior_it = existing.get("it_communication") if isinstance(existing.get("it_communication"), dict) else {}
        merged_it = {**prior_it, **{k: v for k, v in data.it_communication.items() if v is not None}}
        update_data["notification_preferences"] = {**existing, "it_communication": merged_it}

    await gd_update_one(db.session, "users", {"id": current_user["id"]}, update_data)

    return {"message": "تم تحديث التفضيلات بنجاح", "success": True}

@router.get("/users/me/notifications")
async def get_current_user_notification_settings(
    current_user: dict = Depends(get_current_user)
):
    """Get current user's notification settings.

    Independent-Teacher (IT) accounts only support push (in-app) delivery
    in this release — the email and SMS channels are intentionally
    suppressed for that role so any downstream dispatcher reading these
    flags sees ``False`` regardless of whatever historical value sits on
    the user row. The PUT counterpart enforces the same invariant.
    """
    is_independent_teacher = (current_user.get("role") or "").lower() == "independent_teacher"
    return {
        "email_notifications": False if is_independent_teacher else current_user.get("email_notifications", True),
        "sms_notifications": False if is_independent_teacher else current_user.get("sms_notifications", False),
        "push_notifications": current_user.get("push_notifications", True),
        "attendance_alerts": current_user.get("attendance_alerts", True),
        "grade_alerts": current_user.get("grade_alerts", True),
        "behavior_alerts": current_user.get("behavior_alerts", True),
        "announcement_alerts": current_user.get("announcement_alerts", True),
        "weekly_digest": current_user.get("weekly_digest", True),
    }

@router.put("/users/me/notifications")
async def update_current_user_notification_settings(
    data: UserNotificationSettings,
    current_user: dict = Depends(get_current_user)
):
    """Update current user's notification settings.

    IT accounts cannot opt back into email/SMS from this endpoint — those
    two fields are silently ignored for that role to keep the GET/PUT
    invariant aligned with the frontend (push-only channel selector).
    """
    update_data = {"updated_at": datetime.now(timezone.utc).isoformat()}
    is_independent_teacher = (current_user.get("role") or "").lower() == "independent_teacher"

    if data.email_notifications is not None and not is_independent_teacher:
        update_data["email_notifications"] = data.email_notifications
    if data.sms_notifications is not None and not is_independent_teacher:
        update_data["sms_notifications"] = data.sms_notifications
    if data.push_notifications is not None:
        update_data["push_notifications"] = data.push_notifications
    if data.attendance_alerts is not None:
        update_data["attendance_alerts"] = data.attendance_alerts
    if data.grade_alerts is not None:
        update_data["grade_alerts"] = data.grade_alerts
    if data.behavior_alerts is not None:
        update_data["behavior_alerts"] = data.behavior_alerts
    if data.announcement_alerts is not None:
        update_data["announcement_alerts"] = data.announcement_alerts
    if data.weekly_digest is not None:
        update_data["weekly_digest"] = data.weekly_digest
    
    await gd_update_one(db.session, "users", {"id": current_user["id"]}, update_data)
    
    return {"message": "تم تحديث إعدادات الإشعارات بنجاح", "success": True}





# ============== USER AVATAR UPLOAD ==============
@router.post("/users/me/avatar")
async def upload_user_avatar(
    request: Request,
    current_user: dict = Depends(get_current_user)
):
    """Upload user avatar image (supports jpg, png, jpeg, webp)"""
    try:
        body = await request.json()
        image_data = body.get("image_data")
        
        if not image_data:
            raise HTTPException(status_code=400, detail="لم يتم إرسال صورة")

        MAX_B64_LENGTH = 2 * 1024 * 1024
        if len(image_data) > MAX_B64_LENGTH:
            raise HTTPException(status_code=413, detail="حجم الصورة كبير جداً (الحد الأقصى 2MB) | Image too large (max 2MB)")

        allowed_prefixes = ("data:image/jpeg;base64,", "data:image/png;base64,", "data:image/webp;base64,", "data:image/jpg;base64,")
        if not image_data.startswith(allowed_prefixes):
            raise HTTPException(status_code=400, detail="صيغة الصورة غير مدعومة. الصيغ المدعومة: jpg, jpeg, png, webp | Unsupported format. Allowed: jpg, jpeg, png, webp")
        
        try:
            b64_content = image_data.split(",", 1)[1]
            base64.b64decode(b64_content, validate=True)
        except Exception:
            raise HTTPException(status_code=400, detail="بيانات الصورة غير صالحة | Invalid image data")

        # Save avatar URL (base64 data URL)
        update_data = {
            "avatar_url": image_data,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        
        await gd_update_one(db.session, "users", {"id": current_user["id"]}, update_data)
        
        return {
            "success": True,
            "message": "تم رفع الصورة بنجاح",
            "avatar_url": image_data
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="فشل رفع الصورة")


class UserProfileUpdateExtended(BaseModel):
    """Extended profile update with title support"""
    title: Optional[str] = None
    full_name: Optional[str] = None
    full_name_en: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    avatar_url: Optional[str] = None
    preferred_language: Optional[str] = None
    bio: Optional[str] = None


@router.put("/users/me/profile")
async def update_user_profile_extended(
    data: UserProfileUpdateExtended,
    current_user: dict = Depends(get_current_user),
    # Task #201 — IT §5.7 step-up backfill. IT-conditional so non-IT
    # roles (principal, school admin, teacher, parent, platform admin)
    # keep their existing MFA posture and outcomes unchanged.
    _mfa: dict = Depends(_REQUIRE_RECENT_MFA_403_IT),
):
    """Update current user's profile including title and language"""
    update_data = {"updated_at": datetime.now(timezone.utc).isoformat()}
    
    if data.title is not None:
        update_data["title"] = data.title if data.title != "none" else ""
    if data.full_name is not None:
        from engines.name_validation import validate_personal_name
        valid, err_msg = validate_personal_name(data.full_name)
        if not valid:
            raise HTTPException(status_code=400, detail=err_msg)
        update_data["full_name"] = data.full_name
    if data.full_name_en is not None:
        update_data["full_name_en"] = data.full_name_en
    if data.email is not None and data.email:
        existing = await gd_find_one(db.session, "users", {"email": data.email, "id": {"$ne": current_user["id"]}})
        if existing:
            raise HTTPException(status_code=400, detail="البريد الإلكتروني مستخدم مسبقاً")
        update_data["email"] = data.email
    if data.phone is not None and data.phone:
        existing = await gd_find_one(db.session, "users", {"phone": data.phone, "id": {"$ne": current_user["id"]}})
        if existing:
            raise HTTPException(status_code=400, detail="رقم الهاتف مستخدم مسبقاً")
        update_data["phone"] = data.phone
    if data.avatar_url is not None:
        update_data["avatar_url"] = data.avatar_url
    if data.preferred_language is not None:
        update_data["preferred_language"] = data.preferred_language
    if data.bio is not None:
        update_data["bio"] = data.bio
    
    await gd_update_one(db.session, "users", {"id": current_user["id"]}, update_data)
    
    updated_user = await gd_find_one(db.session, "users", {"id": current_user["id"]})
    
    return {
        "success": True,
        "message": "تم حفظ الملف الشخصي بنجاح",
        "user": updated_user
    }





# NOTE: User session management endpoints (/settings/sessions, /settings/sessions/end-all,
# /settings/sessions/{id}) live in routes/settings_routes.py and are backed by the real
# user_sessions table populated on login. The stubs that were here used a deleted
# `is_current` boolean and didn't actually revoke tokens.





# ============== TEST ACCOUNTS CREATION ENDPOINT ==============
@router.post("/test-accounts/create")
async def create_test_accounts(
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))
):
    """
    Create test student and parent accounts for testing the portal
    إنشاء حسابات تجريبية للطالب وولي الأمر
    """
    from routes.student_portal_routes import create_test_student_account, create_test_parent_account
    
    try:
        student = await create_test_student_account(db)
        parent = await create_test_parent_account(db)
        
        return {
            "success": True,
            "message": "تم إنشاء الحسابات التجريبية بنجاح",
            "accounts": {
                "student": {
                    "email": "student@nassaq.com",
                    "password": "Student@123",
                    "name": student.get("full_name") if student else "طالب تجريبي"
                },
                "parent": {
                    "email": "parent@nassaq.com", 
                    "password": "Parent@123",
                    "name": parent.get("full_name") if parent else "ولي أمر تجريبي"
                }
            }
        }
    except Exception as e:
        logger.error(f"Test account creation error: {e}")
        return {
            "success": False,
            "message": "حدث خطأ أثناء إنشاء الحسابات التجريبية"
        }


# Configure logging



