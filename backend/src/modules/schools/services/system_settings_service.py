"""
System Settings Service
Handles platform general settings, maintenance mode, terms & conditions, privacy policy,
contact info, security settings, user sessions, and refresh token revocation chains.
"""
from fastapi import HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import ValidationError
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone, timedelta
import uuid
import logging
import jwt as _jwt

from dependencies import (
    JWT_SECRET, JWT_ALGORITHM as _JWT_ALGORITHM,
    REFRESH_TOKEN_EXPIRE_DAYS as _RTE_DAYS,
)
from engines.sql_utils import (
    gd_find, gd_find_one, gd_insert, gd_update_one, gd_update_many, gd_upsert,
)
from src.modules.schools.dto.settings_dto import (
    GeneralSettings, MaintenanceSettings, ContactInfo, SecuritySettings,
    TermsVersion, PrivacyVersion
)

logger = logging.getLogger("nassaq")


def jti_from_creds(creds: Optional[HTTPAuthorizationCredentials]) -> Optional[str]:
    if not creds:
        return None
    try:
        payload = _jwt.decode(creds.credentials, JWT_SECRET, algorithms=[_JWT_ALGORITHM])
        return payload.get("jti")
    except Exception:
        return None


async def revoke_session_refresh_chain(session, s: dict, now: datetime, user_id: str) -> None:
    """Block the refresh path for a session row and revoke family."""
    from sqlalchemy import text as _sa_text
    r_jti = s.get("refresh_jti")
    r_fid = s.get("refresh_family_id")
    if r_jti:
        try:
            exp = s.get("refresh_expires_at") or (now + timedelta(days=_RTE_DAYS))
            await gd_insert(session, "revoked_tokens", {
                "jti": r_jti,
                "expires_at": exp.isoformat() if hasattr(exp, "isoformat") else str(exp),
                "revoked_at": now.isoformat(),
            })
        except Exception as _e:
            logger.debug(f"_revoke_session_refresh_chain: refresh jti insert: {_e}")
    if r_fid:
        try:
            await session.execute(
                _sa_text(
                    "INSERT INTO revoked_token_families "
                    "(family_id, revoked_at, reason, user_id) "
                    "VALUES (:f, :r, :why, :uid) "
                    "ON CONFLICT (family_id) DO NOTHING"
                ),
                {"f": r_fid, "r": now, "why": "user_ended_session", "uid": user_id},
            )
        except Exception as _fe:
            logger.debug(f"_revoke_session_refresh_chain: family insert: {_fe}")


def format_session(s: dict, current_jti: Optional[str]) -> dict:
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


class SystemSettingsService:
    """Service handling Platform System Settings, Legal Docs, Contact, Security, and Sessions."""

    @staticmethod
    async def get_general_settings(session) -> GeneralSettings:
        try:
            settings = await gd_find_one(session, "system_settings", {"type": "general"})
            if settings:
                return GeneralSettings(**settings.get("data", {}))
            return GeneralSettings()
        except Exception as e:
            logger.error(f"Error fetching general settings: {e}")
            return GeneralSettings()

    @staticmethod
    async def update_general_settings(session, settings: GeneralSettings, current_user: dict) -> dict:
        now = datetime.now(timezone.utc).isoformat()
        new_data = settings.dict()

        existing = await gd_find_one(session, "system_settings", {"type": "general"})
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

        await gd_upsert(session, "system_settings", {"type": "general"}, {"type": "general", "data": new_data, "updated_at": now, "updated_by": current_user.get("id")})

        if changes:
            await gd_insert(session, "audit_logs", {
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

    @staticmethod
    async def get_maintenance_settings(session) -> MaintenanceSettings:
        try:
            settings = await gd_find_one(session, "system_settings", {"type": "maintenance"})
            if settings:
                return MaintenanceSettings(**settings.get("data", {}))
            return MaintenanceSettings()
        except Exception:
            return MaintenanceSettings()

    @staticmethod
    async def update_maintenance_settings(session, settings: MaintenanceSettings, current_user: dict) -> dict:
        try:
            await gd_upsert(session, "system_settings", {"type": "maintenance"}, {
                "type": "maintenance",
                "data": settings.dict(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "updated_by": current_user.get("id")
            })

            action = "maintenance_enabled" if settings.maintenance_mode else "maintenance_disabled"
            await gd_insert(session, "audit_logs", {
                "id": str(uuid.uuid4()),
                "action": action,
                "performed_by": current_user.get("id"),
                "performed_by_name": current_user.get("name"),
                "timestamp": datetime.now(timezone.utc).isoformat()
            })

            return {"success": True, "message": "تم حفظ الإعدادات بنجاح"}
        except Exception as e:
            logger.error(f"Maintenance settings error: {e}")
            raise HTTPException(status_code=500, detail="حدث خطأ أثناء حفظ الإعدادات")

    @staticmethod
    async def get_terms_versions(session) -> List[TermsVersion]:
        try:
            versions = await gd_find(session, "terms_versions", {}, order_by="version_number", desc_order=True, limit=100)
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
        except Exception:
            return []

    @staticmethod
    async def create_terms_version(session, content_ar: str, content_en: str, current_user: dict) -> dict:
        try:
            last_version = await gd_find_one(session, "terms_versions", sort=[("version_number", -1)])
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

            await gd_insert(session, "terms_versions", version)
            await gd_insert(session, "audit_logs", {
                "id": str(uuid.uuid4()),
                "action": "terms_updated",
                "performed_by": current_user.get("id"),
                "performed_by_name": current_user.get("name"),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "details": {"version_number": next_version}
            })

            return {"success": True, "version_number": next_version}
        except Exception as e:
            logger.error(f"Operation error: {e}")
            raise HTTPException(status_code=500, detail="حدث خطأ داخلي في الخادم")

    @staticmethod
    async def publish_terms_version(session, version_id: str) -> dict:
        try:
            await gd_update_many(session, "terms_versions", {}, {"is_published": False})
            await gd_update_one(session, "terms_versions", {"id": version_id}, {
                "is_published": True,
                "published_at": datetime.now(timezone.utc).isoformat()
            })
            return {"success": True, "message": "تم نشر الإصدار بنجاح"}
        except Exception as e:
            logger.error(f"Operation error: {e}")
            raise HTTPException(status_code=500, detail="حدث خطأ داخلي في الخادم")

    @staticmethod
    async def get_published_terms(session) -> dict:
        try:
            v = await gd_find_one(
                session, "terms_versions", {"is_published": True}, sort=[("version_number", -1)]
            )
            if not v:
                return {"version_number": 0, "content_ar": "", "content_en": "", "published_at": None}
            return {
                "version_number": v.get("version_number", 0),
                "content_ar": v.get("content_ar", ""),
                "content_en": v.get("content_en", ""),
                "published_at": v.get("published_at"),
            }
        except Exception as e:
            logger.error(f"get_published_terms error: {e}")
            return {"version_number": 0, "content_ar": "", "content_en": "", "published_at": None}

    @staticmethod
    async def get_privacy_versions(session) -> List[PrivacyVersion]:
        try:
            versions = await gd_find(session, "privacy_versions", {}, order_by="version_number", desc_order=True, limit=100)
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
        except Exception:
            return []

    @staticmethod
    async def create_privacy_version(session, content_ar: str, content_en: str, current_user: dict) -> dict:
        try:
            last_version = await gd_find_one(session, "privacy_versions", sort=[("version_number", -1)])
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

            await gd_insert(session, "privacy_versions", version)
            return {"success": True, "version_number": next_version}
        except Exception as e:
            logger.error(f"Operation error: {e}")
            raise HTTPException(status_code=500, detail="حدث خطأ داخلي في الخادم")

    @staticmethod
    async def publish_privacy_version(session, version_id: str) -> dict:
        try:
            await gd_update_many(session, "privacy_versions", {}, {"is_published": False})
            await gd_update_one(session, "privacy_versions", {"id": version_id}, {
                "is_published": True,
                "published_at": datetime.now(timezone.utc).isoformat()
            })
            return {"success": True, "message": "تم نشر الإصدار بنجاح"}
        except Exception as e:
            logger.error(f"Operation error: {e}")
            raise HTTPException(status_code=500, detail="حدث خطأ داخلي في الخادم")

    @staticmethod
    async def get_published_privacy(session) -> dict:
        try:
            v = await gd_find_one(
                session, "privacy_versions", {"is_published": True}, sort=[("version_number", -1)]
            )
            if not v:
                return {"version_number": 0, "content_ar": "", "content_en": "", "published_at": None}
            return {
                "version_number": v.get("version_number", 0),
                "content_ar": v.get("content_ar", ""),
                "content_en": v.get("content_en", ""),
                "published_at": v.get("published_at"),
            }
        except Exception as e:
            logger.error(f"get_published_privacy error: {e}")
            return {"version_number": 0, "content_ar": "", "content_en": "", "published_at": None}

    @staticmethod
    async def get_contact_info(session) -> ContactInfo:
        try:
            settings = await gd_find_one(session, "system_settings", {"type": "contact"})
            if settings:
                return ContactInfo(**settings.get("data", {}))
            return ContactInfo()
        except Exception:
            return ContactInfo()

    @staticmethod
    async def update_contact_info(session, info: ContactInfo, current_user: dict) -> dict:
        now = datetime.now(timezone.utc).isoformat()
        new_data = info.dict()

        existing = await gd_find_one(session, "system_settings", {"type": "contact"})
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

        await gd_upsert(session, "system_settings", {"type": "contact"}, {"type": "contact", "data": new_data, "updated_at": now})

        if changes:
            await gd_insert(session, "audit_logs", {
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

    @staticmethod
    async def get_security_settings(session) -> SecuritySettings:
        try:
            settings = await gd_find_one(session, "system_settings", {"type": "security"})
            if settings:
                return SecuritySettings(**settings.get("data", {}))
            return SecuritySettings()
        except Exception:
            return SecuritySettings()

    @staticmethod
    async def update_security_settings(session, request: Request, current_user: dict) -> dict:
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

        existing = await gd_find_one(session, "system_settings", {"type": "security"})
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

        await gd_upsert(session, "system_settings", {"type": "security"}, {"type": "security", "data": new_data, "updated_at": now})

        if changes:
            await gd_insert(session, "audit_logs", {
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

    @staticmethod
    async def list_my_sessions(session, current_user: dict, creds: Optional[HTTPAuthorizationCredentials]) -> dict:
        try:
            now = datetime.now(timezone.utc)
            rows = await gd_find(
                session, "user_sessions",
                {"user_id": current_user["id"], "revoked_at": None},
                order_by="last_seen_at", desc_order=True, limit=200,
            )
            current_jti = jti_from_creds(creds)
            sessions = []
            for s in rows:
                exp = s.get("expires_at")
                if exp and hasattr(exp, "tzinfo") and exp < now:
                    continue
                sessions.append(format_session(s, current_jti))
            return {"sessions": sessions, "count": len(sessions)}
        except Exception as e:
            logger.error(f"list_my_sessions error: {e}", exc_info=True)
            return {"sessions": [], "count": 0}

    @staticmethod
    async def end_my_session(session, session_id: str, current_user: dict, creds: Optional[HTTPAuthorizationCredentials]) -> dict:
        row = await gd_find_one(session, "user_sessions", {"id": session_id, "user_id": current_user["id"]})
        if not row:
            raise HTTPException(status_code=404, detail="الجلسة غير موجودة")
        now = datetime.now(timezone.utc)
        await gd_update_one(session, "user_sessions", {"id": session_id}, {"revoked_at": now})
        jti = row.get("jti")
        if jti:
            try:
                exp = row.get("expires_at") or now
                await gd_insert(session, "revoked_tokens", {
                    "jti": jti,
                    "expires_at": exp.isoformat() if hasattr(exp, "isoformat") else str(exp),
                    "revoked_at": now.isoformat(),
                })
            except Exception:
                pass
        await revoke_session_refresh_chain(session, row, now, current_user["id"])
        was_current = bool(jti and jti_from_creds(creds) == jti)
        return {"success": True, "was_current": was_current, "message": "تم إنهاء الجلسة"}

    @staticmethod
    async def end_all_other_sessions(session, current_user: dict, creds: Optional[HTTPAuthorizationCredentials]) -> dict:
        now = datetime.now(timezone.utc)
        current_jti = jti_from_creds(creds)
        if not current_jti:
            raise HTTPException(
                status_code=400,
                detail="تعذر تحديد الجلسة الحالية؛ يرجى تسجيل الدخول مرة أخرى ثم إعادة المحاولة",
            )
        rows = await gd_find(
            session, "user_sessions",
            {"user_id": current_user["id"], "revoked_at": None},
            limit=500,
        )
        ended = 0
        for s in rows:
            if current_jti and s.get("jti") == current_jti:
                continue
            try:
                await gd_update_one(session, "user_sessions", {"id": s.get("id")}, {"revoked_at": now})
                jti = s.get("jti")
                if jti:
                    exp = s.get("expires_at") or now
                    await gd_insert(session, "revoked_tokens", {
                        "jti": jti,
                        "expires_at": exp.isoformat() if hasattr(exp, "isoformat") else str(exp),
                        "revoked_at": now.isoformat(),
                    })
                await revoke_session_refresh_chain(session, s, now, current_user["id"])
                ended += 1
            except Exception:
                pass
        return {"success": True, "ended": ended, "message": f"تم إنهاء {ended} جلسة أخرى"}
