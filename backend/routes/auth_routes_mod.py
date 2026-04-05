"""
NASSAQ Route Module: Authentication, login, role context, password, role switching
Auto-consolidated during Phase 8 modularization.
"""
from fastapi import APIRouter, HTTPException, Depends, status, Header, Query, Body, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import Response
from starlette.responses import StreamingResponse
from pydantic import BaseModel, Field, ConfigDict, EmailStr, model_validator
from typing import List, Optional, Any, Dict
from datetime import datetime, timezone, timedelta
from bson_compat import ObjectId
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
    UserCreate, UserLogin, UserResponse, TokenResponse
)

router = APIRouter()



# ============== AUTH ROUTES ==============
@router.post("/auth/register", response_model=TokenResponse)
async def register(user_data: UserCreate):
    user_data.role = UserRole.STUDENT
    user_data.tenant_id = None

    existing = await db.users.find_one({"email": user_data.email})
    if existing:
        raise HTTPException(status_code=400, detail="البريد الإلكتروني مسجل مسبقاً")
    
    # Create user
    user_id = str(uuid.uuid4())
    user_doc = {
        "id": user_id,
        "email": user_data.email,
        "password_hash": hash_password(user_data.password),
        "full_name": user_data.full_name,
        "full_name_en": user_data.full_name_en,
        "role": user_data.role.value,
        "tenant_id": user_data.tenant_id,
        "phone": user_data.phone,
        "avatar_url": None,
        "is_active": True,
        "preferred_language": "ar",
        "preferred_theme": "light",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.users.insert_one(user_doc)
    
    # Create token
    token = create_access_token({"sub": user_id, "role": user_data.role.value})
    
    user_response = UserResponse(
        id=user_id,
        email=user_data.email,
        full_name=user_data.full_name,
        full_name_en=user_data.full_name_en,
        role=user_data.role,
        tenant_id=user_data.tenant_id,
        phone=user_data.phone,
        avatar_url=None,
        is_active=True,
        preferred_language="ar",
        preferred_theme="light",
        created_at=user_doc["created_at"]
    )
    
    return TokenResponse(access_token=token, user=user_response)

@router.post("/auth/login", response_model=TokenResponse)
async def login(credentials: UserLogin):
    user = await db.users.find_one({"email": credentials.email})
    if not user:
        # Log failed login attempt
        await audit_engine.log_auth_event(
            action=AuditAction.LOGIN_FAILED.value,
            user_id=None,
            success=False,
            email=credentials.email,
            reason="user_not_found"
        )
        raise HTTPException(status_code=401, detail="بيانات الدخول غير صحيحة")
    
    if not verify_password(credentials.password, user["password_hash"]):
        # Log failed login attempt
        await audit_engine.log_auth_event(
            action=AuditAction.LOGIN_FAILED.value,
            user_id=str(user["_id"]),
            tenant_id=user.get("tenant_id"),
            success=False,
            email=credentials.email,
            reason="invalid_password"
        )
        raise HTTPException(status_code=401, detail="بيانات الدخول غير صحيحة")
    
    if not user.get("is_active", True):
        # Log failed login attempt
        await audit_engine.log_auth_event(
            action=AuditAction.LOGIN_FAILED.value,
            user_id=str(user["_id"]),
            tenant_id=user.get("tenant_id"),
            success=False,
            email=credentials.email,
            reason="account_disabled"
        )
        raise HTTPException(status_code=401, detail="الحساب معطل")
    
    user_id = user.get("id") or str(user["_id"])
    token_payload = {"sub": user_id, "role": user["role"]}
    if user.get("tenant_id"):
        token_payload["tenant_id"] = user["tenant_id"]
    if user.get("school_id"):
        token_payload["school_id"] = user["school_id"]
    token = create_access_token(token_payload)
    
    # Log successful login
    await audit_engine.log_auth_event(
        action=AuditAction.LOGIN.value,
        user_id=user_id,
        tenant_id=user.get("tenant_id"),
        success=True,
        email=credentials.email
    )
    
    from engines.name_validation import is_generic_name
    user_response = UserResponse(
        id=user_id,
        email=user["email"],
        full_name=user["full_name"],
        full_name_en=user.get("full_name_en"),
        role=UserRole(user["role"]),
        tenant_id=user.get("tenant_id"),
        phone=user.get("phone"),
        avatar_url=user.get("avatar_url"),
        is_active=user.get("is_active", True),
        has_generic_name=is_generic_name(user.get("full_name")),
        preferred_language=user.get("preferred_language", "ar"),
        preferred_theme=user.get("preferred_theme", "light"),
        created_at=user.get("created_at", ""),
        teacher_id=user.get("teacher_id"),
        student_id=user.get("student_id"),
        parent_id=user.get("parent_id")
    )
    
    return TokenResponse(access_token=token, user=user_response)

@router.post("/auth/logout")
async def logout(
    request: Request,
    current_user: dict = Depends(get_current_user)
):
    """
    Logout endpoint — records audit trail for session end.
    JWT is stateless so no server-side invalidation; client must discard the token.
    """
    user_id = current_user.get("id") or str(current_user.get("_id", ""))
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    await audit_engine.log_auth_event(
        action=AuditAction.LOGOUT.value,
        user_id=user_id,
        tenant_id=current_user.get("tenant_id"),
        success=True,
        email=current_user.get("email"),
        ip_address=ip_address,
        user_agent=user_agent,
    )

    return {"message": "تم تسجيل الخروج بنجاح"}

@router.get("/auth/me", response_model=UserResponse)
async def get_me(current_user: dict = Depends(get_current_user)):
    from engines.name_validation import is_generic_name
    return UserResponse(
        id=current_user["id"],
        email=current_user["email"],
        full_name=current_user["full_name"],
        full_name_en=current_user.get("full_name_en"),
        title=current_user.get("title"),
        role=UserRole(current_user["role"]),
        tenant_id=current_user.get("tenant_id"),
        phone=current_user.get("phone"),
        avatar_url=current_user.get("avatar_url"),
        is_active=current_user.get("is_active", True),
        must_change_password=current_user.get("must_change_password", False),
        has_generic_name=is_generic_name(current_user.get("full_name")),
        preferred_language=current_user.get("preferred_language", "ar"),
        preferred_theme=current_user.get("preferred_theme", "light"),
        created_at=current_user["created_at"],
        teacher_id=current_user.get("teacher_id"),
        student_id=current_user.get("student_id"),
        parent_id=current_user.get("parent_id"),
        is_switched=current_user.get("is_switched", False),
        original_role=current_user.get("original_role")
    )

@router.put("/auth/preferences")
async def update_preferences(
    preferred_language: Optional[str] = None,
    preferred_theme: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    updates = {"updated_at": datetime.now(timezone.utc).isoformat()}
    if preferred_language:
        updates["preferred_language"] = preferred_language
    if preferred_theme:
        updates["preferred_theme"] = preferred_theme
    
    await db.users.update_one({"id": current_user["id"]}, {"$set": updates})
    return {"message": "تم تحديث الإعدادات"}





# ============== ACTIVE ROLE CONTEXT ==============
class ActiveRoleContextRequest(BaseModel):
    role_id: str
    school_id: Optional[str] = None
    scope_id: Optional[str] = None

class ActiveRoleContextResponse(BaseModel):
    user_identity_id: str
    role_id: str
    role_name: str
    school_id: Optional[str] = None
    school_name: Optional[str] = None
    scope_id: Optional[str] = None
    is_active: bool = True
    set_at: str

@router.post("/auth/set-active-role", response_model=ActiveRoleContextResponse)
async def set_active_role_context(
    context: ActiveRoleContextRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Set the active role context for the current session.
    تعيين سياق الدور النشط للجلسة الحالية
    """
    user_id = current_user["id"]
    now = datetime.now(timezone.utc).isoformat()
    
    # Validate user has this role
    user_roles = current_user.get("linked_roles", [])
    valid_role = None
    
    # Check primary role first
    if current_user.get("role") == context.role_id:
        valid_role = {
            "role": current_user.get("role"),
            "tenant_id": current_user.get("tenant_id"),
            "is_active": True
        }
    else:
        # Check linked roles
        for role in user_roles:
            if role.get("role") == context.role_id and role.get("is_active", True):
                if context.school_id:
                    if role.get("tenant_id") == context.school_id:
                        valid_role = role
                        break
                else:
                    valid_role = role
                    break
    
    if not valid_role:
        raise HTTPException(status_code=400, detail="الدور غير متوفر للمستخدم")
    
    # Determine school_id
    school_id = context.school_id or valid_role.get("tenant_id") or current_user.get("tenant_id")
    
    # Get school name if school_id provided
    school_name = None
    if school_id:
        school = await db.schools.find_one({"id": school_id}, {"_id": 0, "name_ar": 1, "name_en": 1})
        if school:
            school_name = school.get("name_ar") or school.get("name_en")
    
    # Store active role context in user's session/document
    active_context = {
        "role_id": context.role_id,
        "school_id": school_id,
        "scope_id": context.scope_id,
        "set_at": now,
        "is_active": True
    }
    
    await db.users.update_one(
        {"id": user_id},
        {"$set": {
            "active_role_context": active_context,
            "updated_at": now
        }}
    )
    
    return ActiveRoleContextResponse(
        user_identity_id=user_id,
        role_id=context.role_id,
        role_name=get_role_display_name(context.role_id),
        school_id=school_id,
        school_name=school_name,
        scope_id=context.scope_id,
        is_active=True,
        set_at=now
    )

@router.get("/auth/active-role", response_model=ActiveRoleContextResponse)
async def get_active_role_context(current_user: dict = Depends(get_current_user)):
    """
    Get the current active role context.
    جلب سياق الدور النشط الحالي
    """
    user_id = current_user["id"]
    active_context = current_user.get("active_role_context")
    
    if not active_context:
        # Return default based on primary role
        school_id = current_user.get("tenant_id")
        school_name = None
        
        if school_id:
            school = await db.schools.find_one({"id": school_id}, {"_id": 0, "name_ar": 1})
            if school:
                school_name = school.get("name_ar")
        
        return ActiveRoleContextResponse(
            user_identity_id=user_id,
            role_id=current_user.get("role", ""),
            role_name=get_role_display_name(current_user.get("role", "")),
            school_id=school_id,
            school_name=school_name,
            is_active=True,
            set_at=current_user.get("created_at", "")
        )
    
    # Get school name
    school_name = None
    if active_context.get("school_id"):
        school = await db.schools.find_one({"id": active_context["school_id"]}, {"_id": 0, "name_ar": 1})
        if school:
            school_name = school.get("name_ar")
    
    return ActiveRoleContextResponse(
        user_identity_id=user_id,
        role_id=active_context.get("role_id", current_user.get("role", "")),
        role_name=get_role_display_name(active_context.get("role_id", current_user.get("role", ""))),
        school_id=active_context.get("school_id"),
        school_name=school_name,
        scope_id=active_context.get("scope_id"),
        is_active=active_context.get("is_active", True),
        set_at=active_context.get("set_at", "")
    )

def get_role_display_name(role: str) -> str:
    """Get Arabic display name for role"""
    role_names = {
        "platform_admin": "مدير المنصة",
        "school_principal": "مدير المدرسة",
        "school_sub_admin": "مشرف المدرسة",
        "teacher": "معلم",
        "student": "طالب",
        "parent": "ولي أمر"
    }
    return role_names.get(role, role)




# ============== PASSWORD CHANGE ROUTE ==============
class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str

@router.post("/auth/change-password")
async def change_password(
    request: PasswordChangeRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Change user password. Required for first-time login with temporary password.
    """
    # Verify current password
    if not verify_password(request.current_password, current_user.get("password_hash", "")):
        raise HTTPException(status_code=400, detail="كلمة المرور الحالية غير صحيحة")
    
    # Validate new password
    if len(request.new_password) < 8:
        raise HTTPException(status_code=400, detail="كلمة المرور يجب أن تكون 8 أحرف على الأقل")
    
    if request.current_password == request.new_password:
        raise HTTPException(status_code=400, detail="كلمة المرور الجديدة يجب أن تكون مختلفة")
    
    # Update password and clear must_change_password flag
    await db.users.update_one(
        {"id": current_user["id"]},
        {"$set": {
            "password_hash": hash_password(request.new_password),
            "must_change_password": False,
            "password_changed_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }}
    )
    
    # Log password change
    audit_log = {
        "id": str(uuid.uuid4()),
        "action": "password_changed",
        "action_by": current_user["id"],
        "action_by_name": current_user.get("full_name", ""),
        "target_type": "user",
        "target_id": current_user["id"],
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    await db.audit_logs.insert_one(audit_log)
    
    return {"message": "تم تغيير كلمة المرور بنجاح"}




# ============== USER ROLE SWITCHING ==============
@router.get("/users/{user_id}/roles")
async def get_user_roles(
    user_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get all roles for a user"""
    # Only allow self or platform admin
    if current_user["id"] != user_id and current_user["role"] != "platform_admin":
        raise HTTPException(status_code=403, detail="غير مصرح")
    
    user = await db.users.find_one({"id": user_id}, {"_id": 0, "password_hash": 0})
    if not user:
        raise HTTPException(status_code=404, detail="المستخدم غير موجود")
    
    roles = []
    
    # Primary role
    roles.append({
        "role": user.get("role") or user.get("primary_role"),
        "tenant_id": user.get("tenant_id") or user.get("primary_tenant_id"),
        "is_primary": True,
        "is_active": True
    })
    
    # Linked roles
    for linked in user.get("linked_roles", []):
        if linked.get("is_active"):
            roles.append({
                "role": linked.get("role"),
                "tenant_id": linked.get("tenant_id"),
                "scope_id": linked.get("scope_id"),
                "is_primary": False,
                "is_active": True
            })
    
    return {"roles": roles, "total": len(roles)}


@router.post("/users/{user_id}/switch-role")
async def switch_user_role(
    user_id: str,
    target_role: str,
    target_tenant_id: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """Switch active role for a user"""
    # Only allow self
    if current_user["id"] != user_id:
        raise HTTPException(status_code=403, detail="يمكنك فقط تبديل دورك الخاص")
    
    user = await db.users.find_one({"id": user_id}, {"_id": 0, "password_hash": 0})
    if not user:
        raise HTTPException(status_code=404, detail="المستخدم غير موجود")
    
    # Get available roles
    available_roles = []
    primary_role = user.get("role") or user.get("primary_role")
    primary_tenant = user.get("tenant_id") or user.get("primary_tenant_id")
    
    available_roles.append({"role": primary_role, "tenant_id": primary_tenant})
    
    for linked in user.get("linked_roles", []):
        if linked.get("is_active"):
            available_roles.append({
                "role": linked.get("role"),
                "tenant_id": linked.get("tenant_id")
            })
    
    # Check if target role is valid
    role_valid = any(
        r["role"] == target_role and r["tenant_id"] == target_tenant_id
        for r in available_roles
    )
    
    if not role_valid:
        raise HTTPException(status_code=400, detail="ليس لديك صلاحية الوصول لهذا الدور")
    
    # Audit log
    now = datetime.now(timezone.utc).isoformat()
    await db.audit_logs.insert_one({
        "id": str(uuid.uuid4()),
        "action": "role_switched",
        "action_category": "identity",
        "actor_id": user_id,
        "actor_name": user.get("full_name", ""),
        "target_type": "user",
        "target_id": user_id,
        "tenant_id": target_tenant_id,
        "details": {
            "from_role": primary_role,
            "to_role": target_role
        },
        "timestamp": now
    })
    
    # Return new token context (in real implementation, would generate new JWT)
    return {
        "message": "تم تبديل الدور بنجاح",
        "user_id": user_id,
        "active_role": target_role,
        "active_tenant_id": target_tenant_id,
        "full_name": user.get("full_name"),
        "email": user.get("email")
    }


@router.post("/users/{user_id}/add-role")
async def add_role_to_user(
    user_id: str,
    role: str,
    tenant_id: Optional[str] = None,
    scope_id: Optional[str] = None,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN]))
):
    """Add an additional role to a user"""
    now = datetime.now(timezone.utc).isoformat()
    
    user = await db.users.find_one({"id": user_id}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=404, detail="المستخدم غير موجود")
    
    # Check if role already exists
    existing_roles = user.get("linked_roles", [])
    for existing in existing_roles:
        if (existing.get("role") == role and 
            existing.get("tenant_id") == tenant_id and
            existing.get("is_active")):
            raise HTTPException(status_code=400, detail="هذا الدور موجود مسبقاً للمستخدم")
    
    new_role = {
        "role": role,
        "tenant_id": tenant_id,
        "scope_id": scope_id,
        "is_active": True,
        "assigned_at": now,
        "assigned_by": current_user["id"],
    }
    
    await db.users.update_one(
        {"id": user_id},
        {
            "$push": {"linked_roles": new_role},
            "$set": {"updated_at": now}
        }
    )
    
    # Audit log
    await db.audit_logs.insert_one({
        "id": str(uuid.uuid4()),
        "action": "role_assigned",
        "action_category": "identity",
        "actor_id": current_user["id"],
        "actor_name": current_user.get("full_name", ""),
        "target_type": "user",
        "target_id": user_id,
        "target_name": user.get("full_name"),
        "tenant_id": tenant_id,
        "details": {"role": role, "scope_id": scope_id},
        "timestamp": now
    })
    
    return {"message": "تم إضافة الدور بنجاح", "role": new_role}





# ============== PHASE 6: ROLE SWITCHING SYSTEM ==============

ROLE_SWITCH_ALLOWED = {
    UserRole.PLATFORM_ADMIN.value: [
        UserRole.SCHOOL_PRINCIPAL.value, UserRole.SCHOOL_ADMIN.value,
        UserRole.TEACHER.value, UserRole.STUDENT.value, UserRole.PARENT.value,
    ],
    UserRole.SCHOOL_PRINCIPAL.value: [
        UserRole.SCHOOL_ADMIN.value, UserRole.TEACHER.value,
    ],
    UserRole.SCHOOL_ADMIN.value: [
        UserRole.TEACHER.value,
    ],
}

@router.get("/role-switch/available-roles")
async def get_available_roles(
    current_user: dict = Depends(get_current_user),
):
    role = current_user.get("role", "")
    available = ROLE_SWITCH_ALLOWED.get(role, [])
    if not available:
        return {"current_role": role, "available_roles": [], "can_switch": False}

    schools = []
    if role == UserRole.PLATFORM_ADMIN.value:
        school_docs = await db.schools.find(
            {"status": "active"}, {"_id": 0, "id": 1, "name": 1, "name_ar": 1}
        ).to_list(100)
        schools = school_docs

    return {
        "current_role": role,
        "available_roles": available,
        "can_switch": True,
        "schools": schools,
    }

@router.post("/role-switch/switch")
async def switch_role(
    data: dict = Body(...),
    current_user: dict = Depends(get_current_user),
):
    target_role = data.get("target_role")
    target_school_id = data.get("school_id")

    current_role = current_user.get("role", "")
    allowed = ROLE_SWITCH_ALLOWED.get(current_role, [])

    if target_role not in allowed:
        raise HTTPException(403, "لا يمكنك التبديل إلى هذا الدور")

    if current_role == UserRole.PLATFORM_ADMIN.value:
        if target_school_id:
            school = await db.schools.find_one({"id": target_school_id})
            if not school:
                raise HTTPException(404, "المدرسة غير موجودة")
        else:
            raise HTTPException(400, "يجب تحديد المدرسة للتبديل")
    else:
        target_school_id = current_user.get("tenant_id")
        if not target_school_id:
            raise HTTPException(400, "لم يتم تحديد المدرسة")

    user_id = current_user.get("id")

    token_data = {
        "sub": user_id,
        "role": target_role,
        "original_role": current_role,
        "original_user_id": user_id,
        "tenant_id": target_school_id,
        "is_impersonating": True,
    }
    new_token = create_access_token(token_data)

    await db.audit_logs.insert_one({
        "id": str(uuid.uuid4()),
        "action": "role_switch",
        "action_by": user_id,
        "original_role": current_role,
        "target_role": target_role,
        "target_school_id": target_school_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

    return {
        "token": new_token,
        "role": target_role,
        "school_id": target_school_id,
        "is_impersonating": True,
        "original_role": current_role,
    }

@router.post("/role-switch/restore")
async def restore_role(
    current_user: dict = Depends(get_current_user),
):
    original_role = current_user.get("original_role")
    if not original_role:
        return {"message": "أنت بالفعل في دورك الأصلي", "restored": False}

    user_id = current_user.get("original_user_id") or current_user.get("id")

    user = await db.users.find_one({"id": user_id})
    if not user:
        from bson_compat import ObjectId
        try:
            user = await db.users.find_one({"_id": ObjectId(user_id)})
        except Exception as e:
            logger.debug(f"ObjectId lookup fallback failed for user_id={user_id}: {e}")
    if not user:
        raise HTTPException(404, "المستخدم الأصلي غير موجود")

    uid = user.get("id") or str(user.get("_id"))
    token_data = {
        "sub": uid,
        "role": user.get("role", original_role),
        "tenant_id": user.get("tenant_id"),
    }
    new_token = create_access_token(token_data)

    return {
        "token": new_token,
        "role": user.get("role", original_role),
        "school_id": user.get("tenant_id"),
        "is_impersonating": False,
        "restored": True,
    }


class ProfileCompletionUpdate(BaseModel):
    phone: Optional[str] = None
    address: Optional[str] = None
    emergency_contact: Optional[str] = None
    emergency_phone: Optional[str] = None
    date_of_birth: Optional[str] = None
    gender: Optional[str] = None
    nationality: Optional[str] = None
    bio: Optional[str] = None
    profile_picture: Optional[str] = None


@router.get("/auth/profile-completion")
async def get_profile_completion(
    current_user: dict = Depends(get_current_user)
):
    """Get profile completion percentage and missing fields"""
    profile_fields = {
        "full_name": "الاسم الكامل",
        "email": "البريد الإلكتروني",
        "phone": "رقم الهاتف",
        "gender": "الجنس",
        "date_of_birth": "تاريخ الميلاد",
        "address": "العنوان",
        "nationality": "الجنسية",
        "emergency_contact": "جهة اتصال الطوارئ",
        "emergency_phone": "هاتف الطوارئ"
    }

    completed = []
    missing = []
    for field, label in profile_fields.items():
        if current_user.get(field):
            completed.append({"field": field, "label": label})
        else:
            missing.append({"field": field, "label": label})

    percentage = round(len(completed) / len(profile_fields) * 100) if profile_fields else 0

    return {
        "percentage": percentage,
        "completed_fields": completed,
        "missing_fields": missing,
        "total_fields": len(profile_fields),
        "completed_count": len(completed)
    }


@router.put("/auth/complete-profile")
async def complete_profile(
    data: ProfileCompletionUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Update profile fields for completion"""
    updates = {"updated_at": datetime.now(timezone.utc).isoformat()}

    for field in ["phone", "address", "emergency_contact", "emergency_phone",
                  "date_of_birth", "gender", "nationality", "bio", "profile_picture"]:
        value = getattr(data, field, None)
        if value is not None:
            updates[field] = value

    await db.users.update_one(
        {"id": current_user["id"]},
        {"$set": updates}
    )

    return {"message": "تم تحديث الملف الشخصي بنجاح"}


@router.get("/auth/sessions")
async def get_user_sessions(
    current_user: dict = Depends(get_current_user)
):
    """Get active sessions for the current user"""
    sessions = await db.user_sessions.find(
        {"user_id": current_user["id"], "is_active": True},
        {"_id": 0}
    ).sort("last_activity", -1).to_list(10)

    return {"sessions": sessions, "total": len(sessions)}


@router.post("/auth/sessions/revoke-all")
async def revoke_all_sessions(
    current_user: dict = Depends(get_current_user)
):
    """Revoke all sessions except current"""
    await db.user_sessions.update_many(
        {"user_id": current_user["id"]},
        {"$set": {"is_active": False, "revoked_at": datetime.now(timezone.utc).isoformat()}}
    )
    return {"message": "تم إلغاء جميع الجلسات"}


@router.get("/auth/login-history")
async def get_login_history(
    limit: int = 20,
    current_user: dict = Depends(get_current_user)
):
    """Get login history for the current user"""
    logs = await db.audit_logs.find(
        {"actor_id": current_user["id"], "action": {"$in": ["login", "login_success", "password_changed"]}},
        {"_id": 0}
    ).sort("timestamp", -1).limit(limit).to_list(limit)

    return {"history": logs, "total": len(logs)}

