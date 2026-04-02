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
from bson import ObjectId
import uuid, os, logging, json, random, re, io, base64

from dependencies import (
    db, get_current_user, require_roles, UserRole, SchoolStatus,
    hash_password, verify_password, create_access_token,
    JWT_SECRET, JWT_ALGORITHM, ACCESS_TOKEN_EXPIRE, security, logger,
    audit_engine, AuditAction, AuditSeverity,
    smart_scheduling_engine, TimetableRunStatus, TimetableStatus,
    ConflictType, ConflictSeverity, PreValidationResult, GenerationResult,
    hakim_engine, reporting_engine, export_engine, session_engine,
    REPORT_TYPES, generate_student_qr_code
)

from shared_models import (
    UserResponse
)

router = APIRouter()



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
    # Validate allowed roles
    allowed_roles = [
        'platform_admin',
        'platform_operations_manager',
        'platform_technical_admin', 
        'platform_support_specialist',
        'platform_data_analyst',
        'platform_security_officer',
        'testing_account',
        'teacher'
    ]
    
    if user_data.role not in allowed_roles:
        raise HTTPException(status_code=400, detail="نوع الحساب غير مسموح به")
    
    # Check if email exists
    existing_email = await db.users.find_one({"email": user_data.email})
    if existing_email:
        raise HTTPException(status_code=400, detail="البريد الإلكتروني مستخدم مسبقاً")
    
    # Check if phone exists (if provided)
    if user_data.phone:
        existing_phone = await db.users.find_one({"phone": user_data.phone})
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
        "permissions": user_data.permissions,
        "is_active": True,
        "must_change_password": True,  # Force password change on first login
        "preferred_language": "ar",
        "preferred_theme": "light",
        "created_at": now,
        "updated_at": now,
        "created_by": current_user["id"],
    }
    
    await db.users.insert_one(new_user)
    
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

@router.get("/users/platform-users")
async def get_platform_users(
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN])),
    skip: int = 0,
    limit: int = 100,
    role: Optional[str] = None,
    search: Optional[str] = None
):
    """
    Get list of all platform users for admin management
    """
    query = {}
    
    if role and role != 'all':
        query["role"] = role
    
    if search:
        query["$or"] = [
            {"full_name": {"$regex": search, "$options": "i"}},
            {"email": {"$regex": search, "$options": "i"}},
            {"phone": {"$regex": search, "$options": "i"}},
        ]
    
    users = await db.users.find(
        query,
        {"_id": 0, "password_hash": 0}
    ).skip(skip).limit(limit).to_list(length=limit)
    
    total = await db.users.count_documents(query)
    
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
    user = await db.users.find_one({"id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="المستخدم غير موجود")
    
    # Cannot delete platform_admin
    if user.get("role") == "platform_admin":
        raise HTTPException(status_code=400, detail="لا يمكن حذف مدير المنصة")
    
    # Soft delete - just mark as inactive
    await db.users.update_one(
        {"id": user_id},
        {"$set": {
            "is_active": False,
            "deleted_at": datetime.now(timezone.utc).isoformat(),
            "deleted_by": current_user["id"]
        }}
    )
    
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
    await db.audit_logs.insert_one(audit_log)
    
    return {"message": "تم حذف المستخدم بنجاح"}




# ============== USERS MANAGEMENT ROUTES ==============
@router.get("/users", response_model=List[UserResponse])
async def get_users(
    role: Optional[str] = None,
    tenant_id: Optional[str] = None,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.SCHOOL_SUB_ADMIN]))
):
    query = {}
    
    # Filter by tenant for school admins
    if current_user["role"] in [UserRole.SCHOOL_PRINCIPAL.value, UserRole.SCHOOL_SUB_ADMIN.value]:
        query["tenant_id"] = current_user.get("tenant_id")
    elif tenant_id:
        query["tenant_id"] = tenant_id
    
    if role:
        query["role"] = role
    
    users = await db.users.find(query, {"_id": 0, "password_hash": 0}).to_list(1000)
    return [UserResponse(**u) for u in users]

@router.put("/users/{user_id}/status")
async def update_user_status(
    user_id: str,
    is_active: bool,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN]))
):
    user = await db.users.find_one({"id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="المستخدم غير موجود")

    if current_user.get("role") != UserRole.PLATFORM_ADMIN.value:
        if user.get("tenant_id") != current_user.get("tenant_id"):
            raise HTTPException(status_code=403, detail="غير مصرح لك بتعديل بيانات هذا المستخدم")

    await db.users.update_one(
        {"id": user_id},
        {"$set": {"is_active": is_active, "updated_at": datetime.now(timezone.utc).isoformat()}}
    )
    return {"message": "تم تحديث حالة المستخدم"}




# ============== USER DETAILS & MANAGEMENT ROUTES ==============

@router.get("/users/{user_id}")
async def get_user_by_id(
    user_id: str,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))
):
    """Get detailed user information by ID"""
    user = await db.users.find_one({"id": user_id}, {"_id": 0, "password_hash": 0})
    if not user:
        raise HTTPException(status_code=404, detail="المستخدم غير موجود")
    
    # Get creator name if exists
    if user.get("created_by"):
        creator = await db.users.find_one({"id": user["created_by"]}, {"_id": 0, "full_name": 1})
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

@router.put("/users/{user_id}")
async def update_user(
    user_id: str,
    user_data: UserUpdateRequest,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))
):
    """Update user information"""
    user = await db.users.find_one({"id": user_id})
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
        existing = await db.users.find_one({"email": user_data.email, "id": {"$ne": user_id}})
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
    
    await db.users.update_one({"id": user_id}, {"$set": updates})
    
    # Audit log
    audit_log = {
        "id": str(uuid.uuid4()),
        "action": "user_updated",
        "action_by": current_user["id"],
        "action_by_name": current_user.get("full_name", ""),
        "target_type": "user",
        "target_id": user_id,
        "target_name": user.get("full_name", ""),
        "changes": updates,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    await db.audit_logs.insert_one(audit_log)
    
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
    user = await db.users.find_one({"id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="المستخدم غير موجود")
    
    old_permissions = user.get("permissions", [])
    
    await db.users.update_one(
        {"id": user_id},
        {"$set": {
            "permissions": data.permissions,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }}
    )
    
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
    await db.audit_logs.insert_one(audit_log)
    
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
    user = await db.users.find_one({"id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="المستخدم غير موجود")

    if current_user.get("role") != UserRole.PLATFORM_ADMIN.value:
        if user.get("tenant_id") != current_user.get("tenant_id"):
            raise HTTPException(status_code=403, detail="غير مصرح لك بتعديل بيانات هذا المستخدم")

    await db.users.update_one(
        {"id": user_id},
        {"$set": {
            "password_hash": hash_password(data.new_password),
            "must_change_password": True,
            "password_reset_at": datetime.now(timezone.utc).isoformat(),
            "password_reset_by": current_user["id"],
            "updated_at": datetime.now(timezone.utc).isoformat()
        }}
    )
    
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
    await db.audit_logs.insert_one(audit_log)
    
    return {"message": "تم إعادة تعيين كلمة المرور بنجاح"}

@router.post("/users/{user_id}/suspend")
async def suspend_user(
    user_id: str,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN]))
):
    """Toggle user suspension status"""
    user = await db.users.find_one({"id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="المستخدم غير موجود")

    if current_user.get("role") != UserRole.PLATFORM_ADMIN.value:
        if user.get("tenant_id") != current_user.get("tenant_id"):
            raise HTTPException(status_code=403, detail="غير مصرح لك بتعديل بيانات هذا المستخدم")

    # Cannot suspend platform_admin
    if user.get("role") == "platform_admin":
        raise HTTPException(status_code=400, detail="لا يمكن تعليق حساب مدير المنصة")
    
    new_status = not user.get("is_active", True)
    
    await db.users.update_one(
        {"id": user_id},
        {"$set": {
            "is_active": new_status,
            "suspended_at": datetime.now(timezone.utc).isoformat() if not new_status else None,
            "suspended_by": current_user["id"] if not new_status else None,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }}
    )
    
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
    await db.audit_logs.insert_one(audit_log)
    
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
    user = await db.users.find_one({"id": user_id})
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
    
    await db.notifications.insert_one(notification)
    
    return {"message": "تم إرسال الإشعار بنجاح", "notification_id": notification["id"]}

import base64

class ImageUploadRequest(BaseModel):
    image_data: str  # Base64 encoded image

@router.post("/users/{user_id}/upload-image")
async def upload_user_image(
    user_id: str,
    data: ImageUploadRequest,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))
):
    """Upload user profile image (base64)"""
    MAX_B64_LENGTH = 3 * 1024 * 1024
    if len(data.image_data) > MAX_B64_LENGTH:
        raise HTTPException(status_code=413, detail="حجم الصورة كبير جداً (الحد الأقصى 2MB)")

    allowed_prefixes = ("data:image/jpeg;base64,", "data:image/png;base64,", "data:image/webp;base64,")
    if not data.image_data.startswith(allowed_prefixes):
        raise HTTPException(status_code=400, detail="صيغة الصورة غير مدعومة (فقط JPEG, PNG, WEBP)")

    user = await db.users.find_one({"id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="المستخدم غير موجود")
    
    await db.users.update_one(
        {"id": user_id},
        {"$set": {
            "avatar_url": data.image_data,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }}
    )
    
    return {"message": "تم رفع الصورة بنجاح", "avatar_url": data.image_data}

@router.get("/users/{user_id}/activity")
async def get_user_activity(
    user_id: str,
    limit: int = 50,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))
):
    """Get user activity logs"""
    user = await db.users.find_one({"id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="المستخدم غير موجود")
    
    # Get activity from audit logs
    activities = await db.audit_logs.find(
        {"$or": [
            {"action_by": user_id},
            {"target_id": user_id}
        ]},
        {"_id": 0}
    ).sort("timestamp", -1).limit(limit).to_list(limit)
    
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
        existing = await db.users.find_one({"email": data.email, "id": {"$ne": current_user["id"]}})
        if existing:
            raise HTTPException(status_code=400, detail="البريد الإلكتروني مستخدم مسبقاً")
        update_data["email"] = data.email
    if data.phone is not None:
        # Check if phone is already used by another user
        existing = await db.users.find_one({"phone": data.phone, "id": {"$ne": current_user["id"]}})
        if existing:
            raise HTTPException(status_code=400, detail="رقم الهاتف مستخدم مسبقاً")
        update_data["phone"] = data.phone
    if data.avatar_url is not None:
        update_data["avatar_url"] = data.avatar_url
    
    await db.users.update_one({"id": current_user["id"]}, {"$set": update_data})
    
    updated_user = await db.users.find_one({"id": current_user["id"]}, {"_id": 0, "password_hash": 0})
    return UserResponse(**updated_user)

@router.get("/users/me/preferences")
async def get_current_user_preferences(
    current_user: dict = Depends(get_current_user)
):
    """Get current user's preferences"""
    return {
        "language": current_user.get("preferred_language", "ar"),
        "theme": current_user.get("preferred_theme", "light"),
        "time_format": current_user.get("time_format", "12h"),
        "date_format": current_user.get("date_format", "dd/mm/yyyy"),
        "first_day_of_week": current_user.get("first_day_of_week", "sunday"),
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
    
    await db.users.update_one({"id": current_user["id"]}, {"$set": update_data})
    
    return {"message": "تم تحديث التفضيلات بنجاح", "success": True}

@router.get("/users/me/notifications")
async def get_current_user_notification_settings(
    current_user: dict = Depends(get_current_user)
):
    """Get current user's notification settings"""
    return {
        "email_notifications": current_user.get("email_notifications", True),
        "sms_notifications": current_user.get("sms_notifications", False),
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
    """Update current user's notification settings"""
    update_data = {"updated_at": datetime.now(timezone.utc).isoformat()}
    
    if data.email_notifications is not None:
        update_data["email_notifications"] = data.email_notifications
    if data.sms_notifications is not None:
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
    
    await db.users.update_one({"id": current_user["id"]}, {"$set": update_data})
    
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

        MAX_B64_LENGTH = 3 * 1024 * 1024
        if len(image_data) > MAX_B64_LENGTH:
            raise HTTPException(status_code=413, detail="حجم الصورة كبير جداً (الحد الأقصى 2MB)")

        allowed_prefixes = ("data:image/jpeg;base64,", "data:image/png;base64,", "data:image/webp;base64,", "data:image/jpg;base64,")
        if not image_data.startswith(allowed_prefixes):
            raise HTTPException(status_code=400, detail="صيغة الصورة غير مدعومة. الصيغ المدعومة: jpg, jpeg, png, webp")
        
        # Save avatar URL (base64 data URL)
        update_data = {
            "avatar_url": image_data,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        
        await db.users.update_one({"id": current_user["id"]}, {"$set": update_data})
        
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
    current_user: dict = Depends(get_current_user)
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
        existing = await db.users.find_one({"email": data.email, "id": {"$ne": current_user["id"]}})
        if existing:
            raise HTTPException(status_code=400, detail="البريد الإلكتروني مستخدم مسبقاً")
        update_data["email"] = data.email
    if data.phone is not None and data.phone:
        existing = await db.users.find_one({"phone": data.phone, "id": {"$ne": current_user["id"]}})
        if existing:
            raise HTTPException(status_code=400, detail="رقم الهاتف مستخدم مسبقاً")
        update_data["phone"] = data.phone
    if data.avatar_url is not None:
        update_data["avatar_url"] = data.avatar_url
    if data.preferred_language is not None:
        update_data["preferred_language"] = data.preferred_language
    if data.bio is not None:
        update_data["bio"] = data.bio
    
    await db.users.update_one({"id": current_user["id"]}, {"$set": update_data})
    
    updated_user = await db.users.find_one({"id": current_user["id"]}, {"_id": 0, "password_hash": 0})
    
    return {
        "success": True,
        "message": "تم حفظ الملف الشخصي بنجاح",
        "user": updated_user
    }





# ============== USER SESSIONS MANAGEMENT ==============
@router.get("/settings/sessions")
async def get_user_sessions(
    current_user: dict = Depends(get_current_user)
):
    """Get active sessions for the current user"""
    sessions = await db.user_sessions.find(
        {"user_id": current_user["id"]},
        {"_id": 0}
    ).sort("last_active", -1).to_list(20)
    
    return {"sessions": sessions}


@router.post("/settings/sessions/end-all")
async def end_all_sessions(
    current_user: dict = Depends(get_current_user)
):
    """End all other sessions except current"""
    # In a real implementation, you would invalidate all tokens except the current one
    # For now, we'll just clear the sessions collection
    await db.user_sessions.delete_many({
        "user_id": current_user["id"],
        "is_current": {"$ne": True}
    })
    
    return {"message": "تم إنهاء جميع الجلسات الأخرى"}


@router.delete("/settings/sessions/{session_id}")
async def end_session(
    session_id: str,
    current_user: dict = Depends(get_current_user)
):
    """End a specific session"""
    result = await db.user_sessions.delete_one({
        "id": session_id,
        "user_id": current_user["id"]
    })
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="الجلسة غير موجودة")
    
    return {"message": "تم إنهاء الجلسة"}





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
        return {
            "success": False,
            "message": f"حدث خطأ: {str(e)}"
        }


# Configure logging



