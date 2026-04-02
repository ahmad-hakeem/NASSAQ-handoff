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
        """تحديث الإعدادات العامة مع تتبع التغييرات"""
        now = datetime.now(timezone.utc).isoformat()
        new_data = settings.dict()

        existing = await db.system_settings.find_one({"type": "general"})
        old_data = existing.get("data", {}) if existing else {}

        field_labels = {
            "platform_name": "اسم المنصة (عربي)",
            "platform_name_en": "اسم المنصة (إنجليزي)",
            "browser_title": "عنوان المتصفح",
            "default_language": "اللغة الافتراضية",
            "date_system": "نظام التاريخ",
            "timezone": "المنطقة الزمنية",
        }

        changes = []
        for key, new_val in new_data.items():
            old_val = old_data.get(key, "")
            if str(old_val) != str(new_val):
                changes.append({
                    "field": key,
                    "field_label": field_labels.get(key, key),
                    "old_value": str(old_val),
                    "new_value": str(new_val),
                })

        await db.system_settings.update_one(
            {"type": "general"},
            {"$set": {"type": "general", "data": new_data, "updated_at": now, "updated_by": current_user.get("id")}},
            upsert=True
        )

        if changes:
            await db.audit_logs.insert_one({
                "id": str(uuid.uuid4()),
                "action": "settings_updated",
                "target_type": "general_settings",
                "performed_by": current_user.get("id"),
                "performed_by_name": current_user.get("full_name", current_user.get("name", "")),
                "performed_by_email": current_user.get("email", ""),
                "timestamp": now,
                "changes": changes,
            })

        return {"success": True, "message": "تم حفظ الإعدادات بنجاح", "changes": changes}
    
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
        """تحديث بيانات التواصل مع تتبع التغييرات"""
        now = datetime.now(timezone.utc).isoformat()
        new_data = info.dict()

        existing = await db.system_settings.find_one({"type": "contact"})
        old_data = existing.get("data", {}) if existing else {}

        field_labels = {
            "email": "البريد الإلكتروني",
            "phone": "رقم الهاتف",
            "working_hours_ar": "ساعات العمل",
            "address_ar": "العنوان",
            "social_twitter": "تويتر",
            "social_linkedin": "لينكدإن",
            "social_instagram": "إنستجرام",
            "social_facebook": "فيسبوك",
            "social_youtube": "يوتيوب",
        }

        changes = []
        for key, new_val in new_data.items():
            old_val = old_data.get(key, "")
            if str(old_val) != str(new_val):
                changes.append({
                    "field": key,
                    "field_label": field_labels.get(key, key),
                    "old_value": str(old_val),
                    "new_value": str(new_val),
                })

        await db.system_settings.update_one(
            {"type": "contact"},
            {"$set": {"type": "contact", "data": new_data, "updated_at": now}},
            upsert=True
        )

        if changes:
            await db.audit_logs.insert_one({
                "id": str(uuid.uuid4()),
                "action": "settings_updated",
                "target_type": "contact_settings",
                "performed_by": current_user.get("id"),
                "performed_by_name": current_user.get("full_name", current_user.get("name", "")),
                "performed_by_email": current_user.get("email", ""),
                "timestamp": now,
                "changes": changes,
            })

        return {"success": True, "message": "تم حفظ بيانات التواصل", "changes": changes}
    
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
        """تحديث إعدادات الأمان مع تتبع التغييرات"""
        now = datetime.now(timezone.utc).isoformat()
        new_data = settings.dict()

        existing = await db.system_settings.find_one({"type": "security"})
        old_data = existing.get("data", {}) if existing else {}

        field_labels = {
            "session_duration_minutes": "مدة الجلسة (بالدقائق)",
            "max_concurrent_sessions": "الحد الأقصى للجلسات",
            "min_password_length": "الحد الأدنى لطول كلمة المرور",
            "require_uppercase": "حرف كبير مطلوب",
            "require_lowercase": "حرف صغير مطلوب",
            "require_numbers": "رقم مطلوب",
            "require_special_chars": "رمز خاص مطلوب",
        }

        changes = []
        for key, new_val in new_data.items():
            old_val = old_data.get(key, "")
            if str(old_val) != str(new_val):
                changes.append({
                    "field": key,
                    "field_label": field_labels.get(key, key),
                    "old_value": str(old_val),
                    "new_value": str(new_val),
                })

        await db.system_settings.update_one(
            {"type": "security"},
            {"$set": {"type": "security", "data": new_data, "updated_at": now}},
            upsert=True
        )

        if changes:
            await db.audit_logs.insert_one({
                "id": str(uuid.uuid4()),
                "action": "settings_updated",
                "target_type": "security_settings",
                "performed_by": current_user.get("id"),
                "performed_by_name": current_user.get("full_name", current_user.get("name", "")),
                "performed_by_email": current_user.get("email", ""),
                "timestamp": now,
                "changes": changes,
            })

        return {"success": True, "message": "تم حفظ إعدادات الأمان", "changes": changes}
    
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
                    "name": user.get("full_name", user.get("name", "")),
                    "title": user.get("title", ""),
                    "phone": user.get("phone", ""),
                    "language": user.get("preferred_language", user.get("language", "ar")),
                    "profile_picture": user.get("profile_picture", user.get("avatar_url")),
                }
            return {}
        except Exception as e:
            return {}
    
    @router.put("/account")
    async def update_account_settings(
        settings: UserAccountSettings,
        current_user: dict = Depends(get_current_user)
    ):
        """تحديث إعدادات حساب المستخدم مع تسجيل التغييرات"""
        user_id = current_user.get("id")
        now = datetime.now(timezone.utc).isoformat()

        existing = await db.users.find_one({"id": user_id})
        if not existing:
            raise HTTPException(status_code=404, detail="المستخدم غير موجود")

        if settings.name:
            from engines.name_validation import validate_personal_name
            valid, err_msg = validate_personal_name(settings.name)
            if not valid:
                raise HTTPException(status_code=400, detail=err_msg)

        field_map = {
            "name": {"old_key": "full_name", "new_val": settings.name, "label": "الاسم"},
            "title": {"old_key": "title", "new_val": settings.title, "label": "اللقب"},
            "phone": {"old_key": "phone", "new_val": settings.phone, "label": "رقم الهاتف"},
            "language": {"old_key": "preferred_language", "new_val": settings.language, "label": "اللغة"},
        }

        changes = []
        update_fields = {"updated_at": now}
        for field_key, info in field_map.items():
            old_val = existing.get(info["old_key"], "")
            new_val = info["new_val"] or ""
            if str(old_val) != str(new_val):
                changes.append({
                    "field": field_key,
                    "field_label": info["label"],
                    "old_value": str(old_val),
                    "new_value": str(new_val),
                })
                update_fields[info["old_key"]] = new_val

        if not changes:
            return {"success": True, "message": "لا توجد تغييرات لحفظها", "changes": []}

        await db.users.update_one(
            {"id": user_id},
            {"$set": update_fields}
        )

        await db.audit_logs.insert_one({
            "id": str(uuid.uuid4()),
            "action": "account_settings_updated",
            "target_type": "user_account",
            "target_id": user_id,
            "performed_by": user_id,
            "performed_by_name": current_user.get("full_name", current_user.get("name", "")),
            "performed_by_email": current_user.get("email", ""),
            "timestamp": now,
            "changes": changes,
        })

        return {"success": True, "message": "تم حفظ إعدادات الحساب بنجاح", "changes": changes}
    
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
            
            await db.users.update_one(
                {"id": current_user.get("id")},
                {"$set": {"profile_picture": data_url, "avatar_url": data_url}}
            )
            
            return {"success": True, "profile_picture": data_url}
        except Exception as e:
            import logging as _log
            _log.getLogger("nassaq").error(f"Operation error: {e}")
            raise HTTPException(status_code=500, detail="حدث خطأ داخلي في الخادم")
    
    @router.delete("/account/profile-picture")
    async def delete_profile_picture(
        current_user: dict = Depends(get_current_user)
    ):
        await db.users.update_one(
            {"id": current_user.get("id")},
            {"$unset": {"profile_picture": "", "avatar_url": ""}}
        )
        return {"success": True}

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
