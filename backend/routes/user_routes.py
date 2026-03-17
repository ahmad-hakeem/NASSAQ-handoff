"""
NASSAQ - User Management Routes
User CRUD and management endpoints
"""
from fastapi import APIRouter, HTTPException, Depends
from typing import Optional, List
from datetime import datetime, timezone
import uuid

from models import (
    UserResponse, UserRole,
    PlatformUserCreate, PlatformUserResponse
)
import logging

logger = logging.getLogger("nassaq.user_routes")
from services import hash_password
from services.audit_service import log_action


def create_user_routes(db, get_current_user, require_roles):
    """Create user management router"""
    router = APIRouter(prefix="/users", tags=["Users"])
    
    @router.post("/create", response_model=PlatformUserResponse)
    async def create_platform_user(
        user_data: PlatformUserCreate,
        current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))
    ):
        """Create a new platform user - Platform Admin only"""
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
        
        # Check if phone exists
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
            "must_change_password": True,
            "preferred_language": "ar",
            "preferred_theme": "light",
            "created_at": now,
            "updated_at": now,
            "created_by": current_user["id"],
        }
        
        await db.users.insert_one(new_user)
        
        # Log action
        await log_action(
            db=db,
            action="user_created",
            action_by=current_user["id"],
            action_by_name=current_user.get("full_name", ""),
            target_type="user",
            target_id=user_id,
            target_name=user_data.full_name,
            details={
                "role": user_data.role,
                "email": user_data.email,
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
    
    @router.get("/platform-users")
    async def get_platform_users(
        current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN])),
        skip: int = 0,
        limit: int = 50,
        role: Optional[str] = None,
        search: Optional[str] = None
    ):
        """Get list of platform users"""
        query = {
            "role": {"$in": [
                'platform_operations_manager',
                'platform_technical_admin',
                'platform_support_specialist',
                'platform_data_analyst',
                'platform_security_officer',
                'testing_account',
                'teacher'
            ]}
        }
        
        if role:
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
    
    @router.get("", response_model=List[UserResponse])
    async def get_users(
        role: Optional[str] = None,
        tenant_id: Optional[str] = None,
        current_user: dict = Depends(require_roles([
            UserRole.PLATFORM_ADMIN, 
            UserRole.SCHOOL_PRINCIPAL, 
            UserRole.SCHOOL_SUB_ADMIN
        ]))
    ):
        """Get users list"""
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
    
    @router.put("/{user_id}/status")
    async def update_user_status(
        user_id: str,
        is_active: bool,
        current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL]))
    ):
        """Update user status"""
        result = await db.users.update_one(
            {"id": user_id},
            {"$set": {"is_active": is_active, "updated_at": datetime.now(timezone.utc).isoformat()}}
        )
        if result.modified_count == 0:
            raise HTTPException(status_code=404, detail="المستخدم غير موجود")
        return {"message": "تم تحديث حالة المستخدم"}
    
    @router.delete("/{user_id}")
    async def delete_platform_user(
        user_id: str,
        current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))
    ):
        """Soft delete a platform user"""
        user = await db.users.find_one({"id": user_id})
        if not user:
            raise HTTPException(status_code=404, detail="المستخدم غير موجود")
        
        # Cannot delete platform_admin
        if user.get("role") == "platform_admin":
            raise HTTPException(status_code=400, detail="لا يمكن حذف مدير المنصة")
        
        # Soft delete
        await db.users.update_one(
            {"id": user_id},
            {"$set": {
                "is_active": False,
                "deleted_at": datetime.now(timezone.utc).isoformat(),
                "deleted_by": current_user["id"]
            }}
        )
        
        # Audit log
        await log_action(
            db=db,
            action="user_deleted",
            action_by=current_user["id"],
            action_by_name=current_user.get("full_name", ""),
            target_type="user",
            target_id=user_id,
            target_name=user.get("full_name", "")
        )
        
        return {"message": "تم حذف المستخدم بنجاح"}
    
    return router
