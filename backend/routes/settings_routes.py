"""
System Settings Routes - مسارات إعدادات النظام
APIs for system settings, maintenance mode, terms & conditions, etc.
"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, ConfigDict, ValidationError
from typing import Optional, List
from datetime import datetime, timezone
import uuid
import jwt as _jwt
from dependencies import JWT_SECRET, JWT_ALGORITHM as _JWT_ALGORITHM

_session_security = HTTPBearer(auto_error=False)


def _jti_from_creds(creds: Optional[HTTPAuthorizationCredentials]) -> Optional[str]:
    if not creds:
        return None
    try:
        payload = _jwt.decode(creds.credentials, JWT_SECRET, algorithms=[_JWT_ALGORITHM])
        return payload.get("jti")
    except Exception:
        return None

import os
import base64
from engines.sql_utils import gd_find, gd_find_one, gd_insert, gd_insert_many, gd_update_one, gd_update_many, gd_count, gd_delete_one, gd_delete_many, gd_distinct, gd_upsert, _gd_aggregate


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
    """إعدادات الأمان

    Task #172 P0: ``extra='forbid'`` rejects any client-supplied field that
    isn't actually persisted on this endpoint (notably the legacy
    ``twoFactorEnabled`` toggle on the Platform Settings page that used to be
    silently dropped). The wrapper route below converts the resulting
    ValidationError into a safe Arabic HTTP 422 the frontend can show via
    NassaqAlertDialog.
    """
    model_config = ConfigDict(extra="forbid")

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


def setup_settings_routes(db, get_current_user, require_roles, UserRole, require_recent_mfa=None):
    # Task #169 Step 7: see security_routes.setup_security_routes for the
    # rationale behind the fallback.
    if require_recent_mfa is None:
        def require_recent_mfa(max_age_seconds: int = 300):  # noqa: ARG001
            return get_current_user
    """Setup settings routes with database and auth dependencies"""
    
    router = APIRouter(prefix="/settings", tags=["System Settings"])
    
    # ============= GENERAL SETTINGS =============
    
    @router.get("/general", response_model=GeneralSettings)
    async def get_general_settings(
        current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))
    ):
        """جلب الإعدادات العامة"""
        try:
            settings = await gd_find_one(db.session, "system_settings", {"type": "general"})
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

        existing = await gd_find_one(db.session, "system_settings", {"type": "general"})
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

        await gd_upsert(db.session, "system_settings", {"type": "general"}, {"type": "general", "data": new_data, "updated_at": now, "updated_by": current_user.get("id")})

        if changes:
            await gd_insert(db.session, "audit_logs", {
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
            settings = await gd_find_one(db.session, "system_settings", {"type": "maintenance"})
            if settings:
                return MaintenanceSettings(**settings.get("data", {}))
            return MaintenanceSettings()
        except Exception as e:
            return MaintenanceSettings()
    
    @router.put("/maintenance")
    async def update_maintenance_settings(
        settings: MaintenanceSettings,
        current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN])),
        # Task #169 Step 7: maintenance toggle can lock all users out → fresh MFA.
        _stepup: dict = Depends(require_recent_mfa()),
    ):
        """تحديث إعدادات الصيانة"""
        try:
            await gd_upsert(db.session, "system_settings", {"type": "maintenance"},
                {
                    "type": "maintenance",
                    "data": settings.dict(),
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                    "updated_by": current_user.get("id")
                }
            )
            
            # Log the action
            action = "maintenance_enabled" if settings.maintenance_mode else "maintenance_disabled"
            await gd_insert(db.session, "audit_logs", {
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
            versions = await gd_find(db.session, "terms_versions", {}, order_by="version_number", desc_order=True, limit=100)
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
            last_version = await gd_find_one(db.session, "terms_versions", sort=[("version_number", -1)])
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
            
            await gd_insert(db.session, "terms_versions", version)
            
            await gd_insert(db.session, "audit_logs", {
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
            await gd_update_many(db.session, "terms_versions", {}, {"is_published": False})
            
            # Publish this version
            await gd_update_one(db.session, "terms_versions", {"id": version_id}, {
                        "is_published": True,
                        "published_at": datetime.now(timezone.utc).isoformat()
                    })
            
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
            versions = await gd_find(db.session, "privacy_versions", {}, order_by="version_number", desc_order=True, limit=100)
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
            last_version = await gd_find_one(db.session, "privacy_versions", sort=[("version_number", -1)])
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
            
            await gd_insert(db.session, "privacy_versions", version)
            
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
            await gd_update_many(db.session, "privacy_versions", {}, {"is_published": False})
            await gd_update_one(db.session, "privacy_versions", {"id": version_id}, {"is_published": True, "published_at": datetime.now(timezone.utc).isoformat()})
            return {"success": True, "message": "تم نشر الإصدار بنجاح"}
        except Exception as e:
            import logging as _log
            _log.getLogger("nassaq").error(f"Operation error: {e}")
            raise HTTPException(status_code=500, detail="حدث خطأ داخلي في الخادم")
    
    # ============= PUBLISHED LEGAL CONTENT (any authenticated user) =============

    @router.get("/terms/published")
    async def get_published_terms(
        current_user: dict = Depends(get_current_user)
    ):
        """الإصدار المنشور من الشروط والأحكام — متاح لأي مستخدم مسجّل."""
        try:
            v = await gd_find_one(
                db.session,
                "terms_versions",
                {"is_published": True},
                sort=[("version_number", -1)],
            )
            if not v:
                return {
                    "version_number": 0,
                    "content_ar": "",
                    "content_en": "",
                    "published_at": None,
                }
            return {
                "version_number": v.get("version_number", 0),
                "content_ar": v.get("content_ar", ""),
                "content_en": v.get("content_en", ""),
                "published_at": v.get("published_at"),
            }
        except Exception as e:
            import logging as _log
            _log.getLogger("nassaq").error(f"get_published_terms error: {e}")
            return {"version_number": 0, "content_ar": "", "content_en": "", "published_at": None}

    @router.get("/privacy/published")
    async def get_published_privacy(
        current_user: dict = Depends(get_current_user)
    ):
        """الإصدار المنشور من سياسة الخصوصية — متاح لأي مستخدم مسجّل."""
        try:
            v = await gd_find_one(
                db.session,
                "privacy_versions",
                {"is_published": True},
                sort=[("version_number", -1)],
            )
            if not v:
                return {
                    "version_number": 0,
                    "content_ar": "",
                    "content_en": "",
                    "published_at": None,
                }
            return {
                "version_number": v.get("version_number", 0),
                "content_ar": v.get("content_ar", ""),
                "content_en": v.get("content_en", ""),
                "published_at": v.get("published_at"),
            }
        except Exception as e:
            import logging as _log
            _log.getLogger("nassaq").error(f"get_published_privacy error: {e}")
            return {"version_number": 0, "content_ar": "", "content_en": "", "published_at": None}

    # ============= CONTACT INFO =============
    
    @router.get("/contact", response_model=ContactInfo)
    async def get_contact_info(
        current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))
    ):
        """جلب بيانات التواصل"""
        try:
            settings = await gd_find_one(db.session, "system_settings", {"type": "contact"})
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

        existing = await gd_find_one(db.session, "system_settings", {"type": "contact"})
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

        await gd_upsert(db.session, "system_settings", {"type": "contact"}, {"type": "contact", "data": new_data, "updated_at": now})

        if changes:
            await gd_insert(db.session, "audit_logs", {
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
            settings = await gd_find_one(db.session, "system_settings", {"type": "security"})
            if settings:
                return SecuritySettings(**settings.get("data", {}))
            return SecuritySettings()
        except Exception as e:
            return SecuritySettings()
    
    @router.put("/security")
    async def update_security_settings(
        request: Request,
        current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN])),
        # Task #169 Step 7: editing platform-wide security policy → fresh MFA.
        _stepup: dict = Depends(require_recent_mfa()),
    ):
        """تحديث إعدادات الأمان مع تتبع التغييرات

        Task #172 P0: validate manually so a payload with unexpected fields
        (e.g. the now-removed ``twoFactorEnabled`` toggle) returns a safe
        Arabic 422 instead of FastAPI's default verbose error array.
        """
        try:
            raw = await request.json()
        except Exception:
            raise HTTPException(status_code=400, detail="نص الطلب غير صالح")
        if not isinstance(raw, dict):
            raise HTTPException(status_code=422, detail="تنسيق إعدادات الأمان غير صحيح")
        try:
            settings = SecuritySettings(**raw)
        except ValidationError as ve:
            extras = sorted({
                str(err.get("loc", [""])[-1])
                for err in ve.errors()
                if err.get("type") == "extra_forbidden"
            })
            if extras:
                joined = "، ".join(extras)
                raise HTTPException(
                    status_code=422,
                    detail=f"حقول غير مدعومة في إعدادات الأمان: {joined}",
                )
            raise HTTPException(
                status_code=422,
                detail="إعدادات الأمان المُرسلة غير صحيحة",
            )

        now = datetime.now(timezone.utc).isoformat()
        new_data = settings.dict()

        existing = await gd_find_one(db.session, "system_settings", {"type": "security"})
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

        await gd_upsert(db.session, "system_settings", {"type": "security"}, {"type": "security", "data": new_data, "updated_at": now})

        if changes:
            await gd_insert(db.session, "audit_logs", {
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
            user = await gd_find_one(db.session, "users", {"id": current_user.get("id")})
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

        existing = await gd_find_one(db.session, "users", {"id": user_id})
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

        await gd_update_one(db.session, "users", {"id": user_id}, update_fields)

        await gd_insert(db.session, "audit_logs", {
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
            MAX_SIZE = 5 * 1024 * 1024  # 5 MB
            ALLOWED_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}

            if file.content_type not in ALLOWED_TYPES:
                raise HTTPException(status_code=400, detail="صيغة الملف غير مدعومة. يرجى رفع صورة (JPEG, PNG, GIF, WebP)")

            content = await file.read()

            if len(content) > MAX_SIZE:
                raise HTTPException(status_code=400, detail="حجم الصورة يتجاوز الحد المسموح (5 ميغابايت)")

            encoded = base64.b64encode(content).decode('utf-8')
            data_url = f"data:{file.content_type};base64,{encoded}"
            
            await gd_update_one(db.session, "users", {"id": current_user.get("id")}, {"profile_picture": data_url, "avatar_url": data_url})
            
            return {"success": True, "profile_picture": data_url}
        except HTTPException:
            raise
        except Exception as e:
            import logging as _log
            _log.getLogger("nassaq").error(f"upload_profile_picture error: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="حدث خطأ داخلي في الخادم")
    
    @router.delete("/account/profile-picture")
    async def delete_profile_picture(
        current_user: dict = Depends(get_current_user)
    ):
        await gd_update_one(db.session, "users", {"id": current_user.get("id")}, {"profile_picture": None, "avatar_url": None})
        return {"success": True}

    # ============= ACTIVE SESSIONS =============

    def _fmt_session(s: dict, current_jti: Optional[str]) -> dict:
        device = s.get("device") or "Unknown"
        browser = s.get("browser") or ""
        os_name = s.get("os") or ""
        location = s.get("location") or s.get("ip_address") or "—"
        last_seen = s.get("last_seen_at") or s.get("created_at")
        created = s.get("created_at")
        is_current = bool(current_jti and s.get("jti") == current_jti)
        return {
            "id": str(s.get("id")),
            "device": f"{device} • {browser}".strip(" •"),
            "device_name": device,
            "browser": browser,
            "os": os_name,
            "ip": s.get("ip_address") or "",
            "ip_address": s.get("ip_address") or "",
            "location": location,
            "started_at": created.isoformat() if hasattr(created, "isoformat") else (created or ""),
            "lastActive": last_seen.isoformat() if hasattr(last_seen, "isoformat") else (last_seen or ""),
            "last_active": last_seen.isoformat() if hasattr(last_seen, "isoformat") else (last_seen or ""),
            "current": is_current,
            "is_current": is_current,
        }

    @router.get("/sessions")
    async def list_my_sessions(
        current_user: dict = Depends(get_current_user),
        creds: Optional[HTTPAuthorizationCredentials] = Depends(_session_security),
    ):
        """List the current user's active (non-revoked, non-expired) sessions."""
        from datetime import datetime as _dt, timezone as _tz
        try:
            now = _dt.now(_tz.utc)
            rows = await gd_find(
                db.session, "user_sessions",
                {"user_id": current_user["id"], "revoked_at": None},
                order_by="last_seen_at", desc_order=True, limit=200,
            )
            current_jti = _jti_from_creds(creds)
            sessions = []
            for s in rows:
                exp = s.get("expires_at")
                if exp and hasattr(exp, "tzinfo") and exp < now:
                    continue
                sessions.append(_fmt_session(s, current_jti))
            return {"sessions": sessions, "count": len(sessions)}
        except Exception as e:
            import logging as _log
            _log.getLogger("nassaq").error(f"list_my_sessions error: {e}", exc_info=True)
            return {"sessions": [], "count": 0}

    @router.delete("/sessions/{session_id}")
    async def end_my_session(
        session_id: str,
        current_user: dict = Depends(get_current_user),
        creds: Optional[HTTPAuthorizationCredentials] = Depends(_session_security),
        # Task #172 P0: revoking a session is sensitive — require fresh MFA
        # for users on a tier with MFA policy (no-op for student/driver/etc).
        _stepup: dict = Depends(require_recent_mfa()),
    ):
        """Revoke a single session belonging to the current user."""
        from datetime import datetime as _dt, timezone as _tz
        row = await gd_find_one(db.session, "user_sessions", {"id": session_id, "user_id": current_user["id"]})
        if not row:
            raise HTTPException(status_code=404, detail="الجلسة غير موجودة")
        now = _dt.now(_tz.utc)
        await gd_update_one(db.session, "user_sessions", {"id": session_id}, {"revoked_at": now})
        jti = row.get("jti")
        if jti:
            try:
                exp = row.get("expires_at") or now
                await gd_insert(db.session, "revoked_tokens", {
                    "jti": jti,
                    "expires_at": exp.isoformat() if hasattr(exp, "isoformat") else str(exp),
                    "revoked_at": now.isoformat(),
                })
            except Exception:
                pass
        was_current = bool(jti and _jti_from_creds(creds) == jti)
        return {"success": True, "was_current": was_current, "message": "تم إنهاء الجلسة"}

    @router.post("/sessions/end-all")
    async def end_all_other_sessions(
        current_user: dict = Depends(get_current_user),
        creds: Optional[HTTPAuthorizationCredentials] = Depends(_session_security),
        # Task #172 P0: bulk-revoke is even more sensitive than single-session
        # revoke — same step-up gate.
        _stepup: dict = Depends(require_recent_mfa()),
    ):
        """Revoke all of the current user's sessions except the current one."""
        from datetime import datetime as _dt, timezone as _tz
        now = _dt.now(_tz.utc)
        current_jti = _jti_from_creds(creds)
        # Task #172 P0: refuse to "end all OTHERS" when we cannot identify the
        # current session — otherwise we'd silently revoke EVERY session
        # including the caller's. Safer to fail closed with a clear message.
        if not current_jti:
            raise HTTPException(
                status_code=400,
                detail="تعذر تحديد الجلسة الحالية؛ يرجى تسجيل الدخول مرة أخرى ثم إعادة المحاولة",
            )
        rows = await gd_find(
            db.session, "user_sessions",
            {"user_id": current_user["id"], "revoked_at": None},
            limit=500,
        )
        ended = 0
        for s in rows:
            if current_jti and s.get("jti") == current_jti:
                continue
            try:
                await gd_update_one(db.session, "user_sessions", {"id": s.get("id")}, {"revoked_at": now})
                jti = s.get("jti")
                if jti:
                    exp = s.get("expires_at") or now
                    await gd_insert(db.session, "revoked_tokens", {
                        "jti": jti,
                        "expires_at": exp.isoformat() if hasattr(exp, "isoformat") else str(exp),
                        "revoked_at": now.isoformat(),
                    })
                ended += 1
            except Exception:
                pass
        return {"success": True, "ended": ended, "message": f"تم إنهاء {ended} جلسة أخرى"}
    
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
