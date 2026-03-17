"""
NASSAQ - Auth Routes
Authentication and authorization endpoints
"""
from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime, timezone
import uuid

from models import (
    UserCreate, UserLogin, UserResponse, TokenResponse,
    PasswordChangeRequest, UserRole
)
import logging

logger = logging.getLogger("nassaq.auth_routes")
from services import (
    hash_password, verify_password, create_access_token,
    security
)
from services.audit_service import log_action


def create_auth_routes(db, get_current_user):
    """Create auth router with database dependency"""
    router = APIRouter(prefix="/auth", tags=["Authentication"])
    
    @router.post("/register", response_model=TokenResponse)
    async def register(user_data: UserCreate):
        """Register a new user"""
        # Check if email exists
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
    
    @router.post("/login", response_model=TokenResponse)
    async def login(credentials: UserLogin):
        """Login user"""
        user = await db.users.find_one({"email": credentials.email})
        if not user:
            raise HTTPException(status_code=401, detail="بيانات الدخول غير صحيحة")
        
        if not verify_password(credentials.password, user["password_hash"]):
            raise HTTPException(status_code=401, detail="بيانات الدخول غير صحيحة")
        
        if not user.get("is_active", True):
            raise HTTPException(status_code=401, detail="الحساب معطل")
        
        user_id = str(user["_id"])
        token = create_access_token({"sub": user_id, "role": user["role"]})
        
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
            preferred_language=user.get("preferred_language", "ar"),
            preferred_theme=user.get("preferred_theme", "light"),
            created_at=user.get("created_at", "")
        )
        
        return TokenResponse(access_token=token, user=user_response)
    
    @router.get("/me", response_model=UserResponse)
    async def get_me(current_user: dict = Depends(get_current_user)):
        """Get current user info"""
        return UserResponse(
            id=current_user["id"],
            email=current_user["email"],
            full_name=current_user["full_name"],
            full_name_en=current_user.get("full_name_en"),
            role=UserRole(current_user["role"]),
            tenant_id=current_user.get("tenant_id"),
            phone=current_user.get("phone"),
            avatar_url=current_user.get("avatar_url"),
            is_active=current_user.get("is_active", True),
            must_change_password=current_user.get("must_change_password", False),
            preferred_language=current_user.get("preferred_language", "ar"),
            preferred_theme=current_user.get("preferred_theme", "light"),
            created_at=current_user["created_at"]
        )
    
    @router.put("/preferences")
    async def update_preferences(
        preferred_language: str = None,
        preferred_theme: str = None,
        current_user: dict = Depends(get_current_user)
    ):
        """Update user preferences"""
        updates = {"updated_at": datetime.now(timezone.utc).isoformat()}
        if preferred_language:
            updates["preferred_language"] = preferred_language
        if preferred_theme:
            updates["preferred_theme"] = preferred_theme
        
        await db.users.update_one({"id": current_user["id"]}, {"$set": updates})
        return {"message": "تم تحديث الإعدادات"}
    
    @router.post("/change-password")
    async def change_password(
        request: PasswordChangeRequest,
        current_user: dict = Depends(get_current_user)
    ):
        """Change user password"""
        # Verify current password
        if not verify_password(request.current_password, current_user.get("password_hash", "")):
            raise HTTPException(status_code=400, detail="كلمة المرور الحالية غير صحيحة")
        
        # Validate new password
        if len(request.new_password) < 8:
            raise HTTPException(status_code=400, detail="كلمة المرور يجب أن تكون 8 أحرف على الأقل")
        
        if request.current_password == request.new_password:
            raise HTTPException(status_code=400, detail="كلمة المرور الجديدة يجب أن تكون مختلفة")
        
        # Update password
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
        await log_action(
            db=db,
            action="password_changed",
            action_by=current_user["id"],
            action_by_name=current_user.get("full_name", ""),
            target_type="user",
            target_id=current_user["id"]
        )
        
        return {"message": "تم تغيير كلمة المرور بنجاح"}
    
    return router
