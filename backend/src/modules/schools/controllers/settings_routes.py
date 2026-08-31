"""
System Settings Routes - مسارات إعدادات النظام
APIs for system settings, maintenance mode, terms & conditions, privacy, contact, security, and sessions.
Controller delegating logic to SystemSettingsService.
"""

from fastapi import APIRouter, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional, List

from dependencies import (
    db, get_current_user, require_roles, UserRole,
    require_recent_mfa,
)
from src.modules.schools.dto.settings_dto import (
    GeneralSettings, MaintenanceSettings, TermsVersion,
    PrivacyVersion, ContactInfo, SecuritySettings,
)
from src.modules.schools.services.system_settings_service import (
    SystemSettingsService,
    jti_from_creds as _jti_from_creds,
    revoke_session_refresh_chain as _revoke_session_refresh_chain,
)

_session_security = HTTPBearer(auto_error=False)


def setup_settings_routes(db_instance, get_current_user_dep, require_roles_dep, UserRole_dep, require_recent_mfa_dep=None):
    """Setup settings routes with database and auth dependencies for legacy app/routes.py integration."""
    if require_recent_mfa_dep is None:
        def require_recent_mfa_dep(max_age_seconds: int = 300):  # noqa: ARG001
            return get_current_user_dep

    r = APIRouter(prefix="/settings", tags=["System Settings"])

    # ============= GENERAL SETTINGS =============

    @r.get("/general", response_model=GeneralSettings)
    async def get_general_settings(
        current_user: dict = Depends(require_roles_dep([UserRole_dep.PLATFORM_ADMIN]))
    ):
        return await SystemSettingsService.get_general_settings(db_instance.session)

    @r.put("/general")
    async def update_general_settings(
        settings: GeneralSettings,
        current_user: dict = Depends(require_roles_dep([UserRole_dep.PLATFORM_ADMIN]))
    ):
        return await SystemSettingsService.update_general_settings(db_instance.session, settings, current_user)

    # ============= MAINTENANCE SETTINGS =============

    @r.get("/maintenance", response_model=MaintenanceSettings)
    async def get_maintenance_settings(
        current_user: dict = Depends(require_roles_dep([UserRole_dep.PLATFORM_ADMIN]))
    ):
        return await SystemSettingsService.get_maintenance_settings(db_instance.session)

    @r.put("/maintenance")
    async def update_maintenance_settings(
        settings: MaintenanceSettings,
        current_user: dict = Depends(require_roles_dep([UserRole_dep.PLATFORM_ADMIN])),
        _stepup: dict = Depends(require_recent_mfa_dep()),
    ):
        return await SystemSettingsService.update_maintenance_settings(db_instance.session, settings, current_user)

    # ============= TERMS & CONDITIONS =============

    @r.get("/terms/versions")
    async def get_terms_versions(
        current_user: dict = Depends(require_roles_dep([UserRole_dep.PLATFORM_ADMIN]))
    ):
        return await SystemSettingsService.get_terms_versions(db_instance.session)

    @r.post("/terms")
    async def create_terms_version(
        content_ar: str,
        content_en: str = "",
        current_user: dict = Depends(require_roles_dep([UserRole_dep.PLATFORM_ADMIN]))
    ):
        return await SystemSettingsService.create_terms_version(db_instance.session, content_ar, content_en, current_user)

    @r.post("/terms/{version_id}/publish")
    async def publish_terms_version(
        version_id: str,
        current_user: dict = Depends(require_roles_dep([UserRole_dep.PLATFORM_ADMIN]))
    ):
        return await SystemSettingsService.publish_terms_version(db_instance.session, version_id)

    # ============= PRIVACY POLICY =============

    @r.get("/privacy/versions")
    async def get_privacy_versions(
        current_user: dict = Depends(require_roles_dep([UserRole_dep.PLATFORM_ADMIN]))
    ):
        return await SystemSettingsService.get_privacy_versions(db_instance.session)

    @r.post("/privacy")
    async def create_privacy_version(
        content_ar: str,
        content_en: str = "",
        current_user: dict = Depends(require_roles_dep([UserRole_dep.PLATFORM_ADMIN]))
    ):
        return await SystemSettingsService.create_privacy_version(db_instance.session, content_ar, content_en, current_user)

    @r.post("/privacy/{version_id}/publish")
    async def publish_privacy_version(
        version_id: str,
        current_user: dict = Depends(require_roles_dep([UserRole_dep.PLATFORM_ADMIN]))
    ):
        return await SystemSettingsService.publish_privacy_version(db_instance.session, version_id)

    # ============= PUBLISHED LEGAL CONTENT =============

    @r.get("/terms/published")
    async def get_published_terms(
        current_user: dict = Depends(get_current_user_dep)
    ):
        return await SystemSettingsService.get_published_terms(db_instance.session)

    @r.get("/privacy/published")
    async def get_published_privacy(
        current_user: dict = Depends(get_current_user_dep)
    ):
        return await SystemSettingsService.get_published_privacy(db_instance.session)

    # ============= CONTACT INFO =============

    @r.get("/contact", response_model=ContactInfo)
    async def get_contact_info(
        current_user: dict = Depends(require_roles_dep([UserRole_dep.PLATFORM_ADMIN]))
    ):
        return await SystemSettingsService.get_contact_info(db_instance.session)

    @r.put("/contact")
    async def update_contact_info(
        info: ContactInfo,
        current_user: dict = Depends(require_roles_dep([UserRole_dep.PLATFORM_ADMIN]))
    ):
        return await SystemSettingsService.update_contact_info(db_instance.session, info, current_user)

    # ============= SECURITY SETTINGS =============

    @r.get("/security", response_model=SecuritySettings)
    async def get_security_settings(
        current_user: dict = Depends(require_roles_dep([UserRole_dep.PLATFORM_ADMIN]))
    ):
        return await SystemSettingsService.get_security_settings(db_instance.session)

    @r.put("/security")
    async def update_security_settings(
        request: Request,
        current_user: dict = Depends(require_roles_dep([UserRole_dep.PLATFORM_ADMIN])),
        _stepup: dict = Depends(require_recent_mfa_dep()),
    ):
        return await SystemSettingsService.update_security_settings(db_instance.session, request, current_user)

    # ============= ACTIVE SESSIONS =============

    @r.get("/sessions")
    async def list_my_sessions(
        current_user: dict = Depends(get_current_user_dep),
        creds: Optional[HTTPAuthorizationCredentials] = Depends(_session_security),
    ):
        return await SystemSettingsService.list_my_sessions(db_instance.session, current_user, creds)

    @r.delete("/sessions/{session_id}")
    async def end_my_session(
        session_id: str,
        current_user: dict = Depends(get_current_user_dep),
        creds: Optional[HTTPAuthorizationCredentials] = Depends(_session_security),
        _stepup: dict = Depends(require_recent_mfa_dep()),
    ):
        return await SystemSettingsService.end_my_session(db_instance.session, session_id, current_user, creds)

    @r.post("/sessions/end-all")
    async def end_all_other_sessions(
        current_user: dict = Depends(get_current_user_dep),
        creds: Optional[HTTPAuthorizationCredentials] = Depends(_session_security),
        _stepup: dict = Depends(require_recent_mfa_dep()),
    ):
        return await SystemSettingsService.end_all_other_sessions(db_instance.session, current_user, creds)

    return r


# Module-level router instance
router = setup_settings_routes(db, get_current_user, require_roles, UserRole, require_recent_mfa)
