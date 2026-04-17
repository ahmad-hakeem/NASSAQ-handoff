from typing import Optional

from fastapi import HTTPException, status

from models.enums import UserRole  # backend/ is on sys.path; matches existing convention


def _is_platform_admin(current_user: dict) -> bool:
    return current_user.get("role") == UserRole.PLATFORM_ADMIN.value


def assert_school_access(current_user: dict, school_id: str) -> None:
    """Raise 403 unless the caller belongs to school_id (or is platform admin).

    The single authoritative tenant guard for every timetable route.
    """
    if not school_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="school_id is required",
        )
    if _is_platform_admin(current_user):
        return
    user_tenant = current_user.get("tenant_id") or current_user.get("school_id")
    if not user_tenant or str(user_tenant) != str(school_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: school does not match caller's tenant",
        )


def resolve_school_id(current_user: dict, override: Optional[str]) -> Optional[str]:
    """Decide which school_id a request should operate on.

    Non-admins always operate on their own tenant; an override that
    matches their tenant is OK, an override that doesn't match is 403.
    Platform admins may override freely; with no override they get None
    (caller decides whether to require one).
    """
    if _is_platform_admin(current_user):
        return override  # may be None — caller decides
    user_tenant = current_user.get("tenant_id") or current_user.get("school_id")
    if override is not None and str(override) != str(user_tenant):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: school does not match caller's tenant",
        )
    if not user_tenant:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: caller has no tenant",
        )
    return str(user_tenant)
