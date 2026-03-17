"""
System Settings Routes - مسارات إعدادات النظام
APIs for system settings, maintenance mode, terms & conditions, etc.
"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timezone
import uuid
import os
import base64


# Models
class GeneralSettings(BaseModel):
    """الإعدادات العامة"""
    platform_name: str = "نَسَّق"
    platform_name_en: str = "NASSAQ"
    browser_title: str = "نَسَّق | NASSAQ"
    default_language: str = "ar"  # ar or en
    date_system: str = "both"  # hijri, gregorian, both
    timezone: str = "Asia/Riyadh"


class MaintenanceSettings(BaseModel):
    """إعدادات الصيانة"""
    maintenance_mode: bool = False
    registration_open: bool = True
    maintenance_message_ar: str = "نحيطكم علمًا أن النظام يخضع حاليًا لأعمال صيانة وتحسينات تقنية."
    maintenance_message_en: str = "The system is currently undergoing maintenance."
    registration_closed_message_ar: str = "نود إبلاغكم بأن التسجيل في المنصة مغلق حاليًا."
    registration_closed_message_en: str = "Registration is currently closed."


class TermsVersion(BaseModel):
    """إصدار الشروط والأحكام"""
    id: str
    version_number: int
    content_ar: str
    content_en: str = ""
    created_at: str
    created_by: str
    created_by_name: str
    is_published: bool = False
    published_at: Optional[str] = None


class PrivacyVersion(BaseModel):
    """إصدار سياسة الخصوصية"""
    id: str
    version_number: int
    content_ar: str
    content_en: str = ""
    created_at: str
    created_by: str
    created_by_name: str
    is_published: bool = False
    published_at: Optional[str] = None


class ContactInfo(BaseModel):
    """بيانات التواصل"""
    email: str = ""
    phone: str = ""
    working_hours_ar: str = ""
    working_hours_en: str = ""
    address_ar: str = ""
    address_en: str = ""
    social_twitter: str = ""
    social_linkedin: str = ""
    social_instagram: str = ""
    social_facebook: str = ""
    social_youtube: str = ""


class SecuritySettings(BaseModel):
    """إعدادات الأمان"""
    session_duration_minutes: int = 60
    max_concurrent_sessions: int = 3
    min_password_length: int = 8
    require_uppercase: int = 1
    require_lowercase: int = 1
    require_numbers: int = 1
    require_special_chars: int = 1


class UserAccountSettings(BaseModel):
    """إعدادات حساب المستخدم"""
    name: str
    title: str = ""  # السيد، الدكتور، إلخ
    phone: str = ""
    language: str = "ar"
    profile_picture: Optional[str] = None


def setup_settings_routes(db, get_current_user, require_roles, UserRole):
    """Setup settings routes with database and auth dependencies"""
    
    router = APIRouter(prefix="/settings", tags=["System Settings"])
    
    # ============= GENERAL SETTINGS =============
    
    @router.get("/general", response_model=GeneralSettings)
    async def get_general_settings(
        current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))
    ):
        """جلب الإعدادات العامة"""
        try:
            settings = await db.system_settings.find_one({"type": "general"})
            if settings:
                return GeneralSettings(**settings.get("data", {}))
            return GeneralSettings()
        except Exception as e:
            logger.error(f"Error fetching general settings: {e}")
            return GeneralSettings()
    
    @router.put("/general")
    async def update_general_settings(
        settings: GeneralSettings,
        current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))
    ):
        """تحديث الإعدادات العامة"""
        try:
            await db.system_settings.update_one(
                {"type": "general"},
                {
                    "$set": {
                        "type": "general",
                        "data": settings.dict(),
                        "updated_at": datetime.now(timezone.utc).isoformat(),
                        "updated_by": current_user.get("id")
                    }
                },
                upsert=True
            )
            
            # Log the action
            await db.audit_logs.insert_one({
                "id": str(uuid.uuid4()),
                "action": "settings_updated",
                "target_type": "general_settings",
                "performed_by": current_user.get("id"),
                "performed_by_name": current_user.get("name"),
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
            
            return {"success": True, "message": "تم حفظ الإعدادات بنجاح"}
        except Exception as e:
            import logging as _log
            _log.getLogger("nassaq").error(f"Settings update error: {e}")
            raise HTTPException(status_code=500, detail="حدث خطأ أثناء حفظ الإعدادات")
    
    # ============= MAINTENANCE SETTINGS =============
    
    @router.get("/maintenance", response_model=MaintenanceSettings)
    async def get_maintenance_settings(
        current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))
    ):
        """جلب إعدادات الصيانة"""
        try:
            settings = await db.system_settings.find_one({"type": "maintenance"})
            if settings:
                return MaintenanceSettings(**settings.get("data", {}))
            return MaintenanceSettings()
        except Exception as e:
            return MaintenanceSettings()
    
    @router.put("/maintenance")
    async def update_maintenance_settings(
        settings: MaintenanceSettings,
        current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))
    ):
        """تحديث إعدادات الصيانة"""
        try:
            await db.system_settings.update_one(
                {"type": "maintenance"},
                {
                    "$set": {
                        "type": "maintenance",
                        "data": settings.dict(),
                        "updated_at": datetime.now(timezone.utc).isoformat(),
                        "updated_by": current_user.get("id")
                    }
                },
                upsert=True
            )
            
            # Log the action
            action = "maintenance_enabled" if settings.maintenance_mode else "maintenance_disabled"
            await db.audit_logs.insert_one({
                "id": str(uuid.uuid4()),
                "action": action,
                "performed_by": current_user.get("id"),
                "performed_by_name": current_user.get("name"),
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
            
            return {"success": True, "message": "تم حفظ الإعدادات بنجاح"}
        except Exception as e:
            import logging as _log
            _log.getLogger("nassaq").error(f"Maintenance settings error: {e}")
            raise HTTPException(status_code=500, detail="حدث خطأ أثناء حفظ الإعدادات")
    
    # ============= TERMS & CONDITIONS =============
    
    @router.get("/terms/versions")
    async def get_terms_versions(
        current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))
    ):
        """جلب جميع إصدارات الشروط والأحكام"""
        try:
            versions = await db.terms_versions.find().sort("version_number", -1).to_list(100)
            return [
                TermsVersion(
                    id=str(v.get("id", v.get("_id"))),
                    version_number=v.get("version_number", 0),
                    content_ar=v.get("content_ar", ""),
                    content_en=v.get("content_en", ""),
                    created_at=v.get("created_at", ""),
                    created_by=v.get("created_by", ""),
                    created_by_name=v.get("created_by_name", ""),
                    is_published=v.get("is_published", False),
                    published_at=v.get("published_at")
                )
                for v in versions
            ]
        except Exception as e:
            return []
    
    @router.post("/terms")
    async def create_terms_version(
        content_ar: str,
        content_en: str = "",
        current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))
    ):
        """إنشاء إصدار جديد من الشروط والأحكام"""
        try:
            # Get next version number
            last_version = await db.terms_versions.find_one(sort=[("version_number", -1)])
            next_version = (last_version.get("version_number", 0) if last_version else 0) + 1
            
            version = {
                "id": str(uuid.uuid4()),
                "version_number": next_version,
                "content_ar": content_ar,
                "content_en": content_en,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "created_by": current_user.get("id"),
                "created_by_name": current_user.get("name"),
                "is_published": False
            }
            
            await db.terms_versions.insert_one(version)
            
            await db.audit_logs.insert_one({
                "id": str(uuid.uuid4()),
                "action": "terms_updated",
                "performed_by": current_user.get("id"),
                "performed_by_name": current_user.get("name"),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "details": {"version_number": next_version}
            })
            
            return {"success": True, "version_number": next_version}
        except Exception as e:
            import logging as _log
            _log.getLogger("nassaq").error(f"Operation error: {e}")
            raise HTTPException(status_code=500, detail="حدث خطأ داخلي في الخادم")
    
    @router.post("/terms/{version_id}/publish")
    async def publish_terms_version(
        version_id: str,
        current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))
    ):
        """نشر إصدار من الشروط والأحكام"""
        try:
            # Unpublish all other versions
            await db.terms_versions.update_many(
                {},
                {"$set": {"is_published": False}}
            )
            
            # Publish this version
            await db.terms_versions.update_one(
                {"id": version_id},
                {
                    "$set": {
                        "is_published": True,
                        "published_at": datetime.now(timezone.utc).isoformat()
                    }
                }
            )
            
            return {"success": True, "message": "تم نشر الإصدار بنجاح"}
        except Exception as e:
            import logging as _log
            _log.getLogger("nassaq").error(f"Operation error: {e}")
            raise HTTPException(status_code=500, detail="حدث خطأ داخلي في الخادم")
    
    # ============= PRIVACY POLICY =============
    
    @router.get("/privacy/versions")
    async def get_privacy_versions(
        current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))
    ):
        """جلب جميع إصدارات سياسة الخصوصية"""
        try:
            versions = await db.privacy_versions.find().sort("version_number", -1).to_list(100)
            return [
                PrivacyVersion(
                    id=str(v.get("id", v.get("_id"))),
                    version_number=v.get("version_number", 0),
                    content_ar=v.get("content_ar", ""),
                    content_en=v.get("content_en", ""),
                    created_at=v.get("created_at", ""),
                    created_by=v.get("created_by", ""),
                    created_by_name=v.get("created_by_name", ""),
                    is_published=v.get("is_published", False),
                    published_at=v.get("published_at")
                )
                for v in versions
            ]
        except Exception as e:
            return []
    
    @router.post("/privacy")
    async def create_privacy_version(
        content_ar: str,
        content_en: str = "",
        current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))
    ):
        """إنشاء إصدار جديد من سياسة الخصوصية"""
        try:
            last_version = await db.privacy_versions.find_one(sort=[("version_number", -1)])
            next_version = (last_version.get("version_number", 0) if last_version else 0) + 1
            
            version = {
                "id": str(uuid.uuid4()),
                "version_number": next_version,
                "content_ar": content_ar,
                "content_en": content_en,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "created_by": current_user.get("id"),
                "created_by_name": current_user.get("name"),
                "is_published": False
            }
            
            await db.privacy_versions.insert_one(version)
            
            return {"success": True, "version_number": next_version}
        except Exception as e:
            import logging as _log
            _log.getLogger("nassaq").error(f"Operation error: {e}")
            raise HTTPException(status_code=500, detail="حدث خطأ داخلي في الخادم")
    
    @router.post("/privacy/{version_id}/publish")
    async def publish_privacy_version(
        version_id: str,
        current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))
    ):
        """نشر إصدار من سياسة الخصوصية"""
        try:
            await db.privacy_versions.update_many({}, {"$set": {"is_published": False}})
            await db.privacy_versions.update_one(
                {"id": version_id},
                {"$set": {"is_published": True, "published_at": datetime.now(timezone.utc).isoformat()}}
            )
            return {"success": True, "message": "تم نشر الإصدار بنجاح"}
        except Exception as e:
            import logging as _log
            _log.getLogger("nassaq").error(f"Operation error: {e}")
            raise HTTPException(status_code=500, detail="حدث خطأ داخلي في الخادم")
    
    # ============= CONTACT INFO =============
    
    @router.get("/contact", response_model=ContactInfo)
    async def get_contact_info(
        current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))
    ):
        """جلب بيانات التواصل"""
        try:
            settings = await db.system_settings.find_one({"type": "contact"})
            if settings:
                return ContactInfo(**settings.get("data", {}))
            return ContactInfo()
        except Exception as e:
            return ContactInfo()
    
    @router.put("/contact")
    async def update_contact_info(
        info: ContactInfo,
        current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))
    ):
        """تحديث بيانات التواصل"""
        try:
            await db.system_settings.update_one(
                {"type": "contact"},
                {
                    "$set": {
                        "type": "contact",
                        "data": info.dict(),
                        "updated_at": datetime.now(timezone.utc).isoformat()
                    }
                },
                upsert=True
            )
            return {"success": True, "message": "تم حفظ بيانات التواصل"}
        except Exception as e:
            import logging as _log
            _log.getLogger("nassaq").error(f"Operation error: {e}")
            raise HTTPException(status_code=500, detail="حدث خطأ داخلي في الخادم")
    
    # ============= SECURITY SETTINGS =============
    
    @router.get("/security", response_model=SecuritySettings)
    async def get_security_settings(
        current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))
    ):
        """جلب إعدادات الأمان"""
        try:
            settings = await db.system_settings.find_one({"type": "security"})
            if settings:
                return SecuritySettings(**settings.get("data", {}))
            return SecuritySettings()
        except Exception as e:
            return SecuritySettings()
    
    @router.put("/security")
    async def update_security_settings(
        settings: SecuritySettings,
        current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))
    ):
        """تحديث إعدادات الأمان"""
        try:
            await db.system_settings.update_one(
                {"type": "security"},
                {
                    "$set": {
                        "type": "security",
                        "data": settings.dict(),
                        "updated_at": datetime.now(timezone.utc).isoformat()
                    }
                },
                upsert=True
            )
            return {"success": True, "message": "تم حفظ إعدادات الأمان"}
        except Exception as e:
            import logging as _log
            _log.getLogger("nassaq").error(f"Operation error: {e}")
            raise HTTPException(status_code=500, detail="حدث خطأ داخلي في الخادم")
    
    # ============= USER ACCOUNT SETTINGS =============
    
    @router.get("/account")
    async def get_account_settings(
        current_user: dict = Depends(get_current_user)
    ):
        """جلب إعدادات حساب المستخدم"""
        try:
            user = await db.users.find_one({"id": current_user.get("id")})
            if user:
                return {
                    "name": user.get("name", ""),
                    "title": user.get("title", ""),
                    "phone": user.get("phone", ""),
                    "language": user.get("language", "ar"),
                    "profile_picture": user.get("profile_picture"),
                }
            return {}
        except Exception as e:
            return {}
    
    @router.put("/account")
    async def update_account_settings(
        settings: UserAccountSettings,
        current_user: dict = Depends(get_current_user)
    ):
        """تحديث إعدادات حساب المستخدم"""
        try:
            await db.users.update_one(
                {"id": current_user.get("id")},
                {
                    "$set": {
                        "name": settings.name,
                        "title": settings.title,
                        "phone": settings.phone,
                        "language": settings.language,
                        "updated_at": datetime.now(timezone.utc).isoformat()
                    }
                }
            )
            return {"success": True, "message": "تم حفظ إعدادات الحساب"}
        except Exception as e:
            import logging as _log
            _log.getLogger("nassaq").error(f"Operation error: {e}")
            raise HTTPException(status_code=500, detail="حدث خطأ داخلي في الخادم")
    
    @router.post("/account/upload-picture")
    async def upload_profile_picture(
        file: UploadFile = File(...),
        current_user: dict = Depends(get_current_user)
    ):
        """رفع صورة شخصية"""
        try:
            # Read and encode file
            content = await file.read()
            encoded = base64.b64encode(content).decode('utf-8')
            data_url = f"data:{file.content_type};base64,{encoded}"
            
            # Update user profile
            await db.users.update_one(
                {"id": current_user.get("id")},
                {"$set": {"profile_picture": data_url}}
            )
            
            return {"success": True, "profile_picture": data_url}
        except Exception as e:
            import logging as _log
            _log.getLogger("nassaq").error(f"Operation error: {e}")
            raise HTTPException(status_code=500, detail="حدث خطأ داخلي في الخادم")
    
    # ============= ACTIVE SESSIONS =============
    
    @router.get("/sessions/active")
    async def get_active_sessions(
        current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))
    ):
        """جلب الجلسات النشطة"""
        try:
            sessions = await db.sessions.find().sort("created_at", -1).to_list(100)
            return [
                {
                    "id": str(s.get("id", s.get("_id"))),
                    "user_id": s.get("user_id"),
                    "user_name": s.get("user_name", "غير معروف"),
                    "role": s.get("role", ""),
                    "device": s.get("device", "غير معروف"),
                    "ip_address": s.get("ip_address", ""),
                    "started_at": s.get("created_at", ""),
                }
                for s in sessions
            ]
        except Exception as e:
            return []
    
    # ============= TITLES (الألقاب) =============
    
    @router.get("/titles")
    async def get_available_titles():
        """جلب قائمة الألقاب المتاحة"""
        return {
            "ar": [
                {"id": "mr", "label": "السيد"},
                {"id": "mrs", "label": "السيدة"},
                {"id": "miss", "label": "الآنسة"},
                {"id": "ms", "label": "الأستاذة / السيدة"},
                {"id": "dr", "label": "دكتور"},
                {"id": "prof", "label": "أستاذ"},
                {"id": "eng", "label": "مهندس"},
                {"id": "consultant", "label": "مستشار"},
                {"id": "excellency", "label": "معالي"},
                {"id": "honor", "label": "سعادة"},
                {"id": "sheikh", "label": "الشيخ"},
            ],
            "en": [
                {"id": "mr", "label": "Mr."},
                {"id": "mrs", "label": "Mrs."},
                {"id": "miss", "label": "Miss"},
                {"id": "ms", "label": "Ms."},
                {"id": "dr", "label": "Dr."},
                {"id": "prof", "label": "Prof."},
                {"id": "eng", "label": "Eng."},
                {"id": "consultant", "label": "Consultant"},
                {"id": "excellency", "label": "His/Her Excellency"},
                {"id": "honor", "label": "His/Her Excellency"},
                {"id": "sheikh", "label": "Sheikh"},
            ]
        }
    
    return router
