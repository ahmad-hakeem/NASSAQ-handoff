"""
NASSAQ - User Models
All user-related Pydantic models
"""
from pydantic import BaseModel, Field, ConfigDict, EmailStr
from typing import List, Optional
from .enums import UserRole


class UserBase(BaseModel):
    email: EmailStr
    full_name: str
    full_name_en: Optional[str] = None
    role: UserRole
    tenant_id: Optional[str] = None
    phone: Optional[str] = None
    avatar_url: Optional[str] = None
    is_active: bool = True
    preferred_language: str = "ar"
    preferred_theme: str = "light"


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    full_name_en: Optional[str] = None
    role: UserRole
    tenant_id: Optional[str] = None
    phone: Optional[str] = None


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    email: str
    full_name: str
    full_name_en: Optional[str] = None
    role: UserRole
    tenant_id: Optional[str] = None
    phone: Optional[str] = None
    avatar_url: Optional[str] = None
    is_active: bool
    must_change_password: bool = False
    preferred_language: str
    preferred_theme: str
    created_at: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class PlatformUserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    role: str
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


class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str


class UserProfileUpdate(BaseModel):
    full_name: Optional[str] = None
    full_name_en: Optional[str] = None
    phone: Optional[str] = None
    avatar_url: Optional[str] = None


class UserPreferencesUpdate(BaseModel):
    preferred_language: Optional[str] = None
    preferred_theme: Optional[str] = None


class UserNotificationSettings(BaseModel):
    email_notifications: bool = True
    sms_notifications: bool = True
    attendance_alerts: bool = True
    grade_alerts: bool = True
    behavior_alerts: bool = True
