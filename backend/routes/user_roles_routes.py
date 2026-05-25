"""
User Roles Routes - مسارات أدوار المستخدمين
APIs for user role switching and multi-role management
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPBearer as _HTTPBearer, HTTPAuthorizationCredentials as _HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timezone
import uuid
import logging
from engines.sql_utils import gd_find, gd_find_one, gd_insert, gd_insert_many, gd_update_one, gd_update_many, gd_count, gd_delete_one, gd_delete_many, gd_distinct, gd_upsert, _gd_aggregate
logger = logging.getLogger("nassaq")
_bearer_scheme = _HTTPBearer()


PLATFORM_ROLES = frozenset({
    "platform_admin", "platform_operations_manager",
    "platform_technical_admin", "platform_support_specialist",
    "platform_data_analyst", "platform_security_officer",
})

SCHOOL_SCOPED_ROLES = frozenset({
    "school_principal", "school_admin", "school_sub_admin",
    "teacher", "independent_teacher", "student", "parent",
})


class RoleSwitchRequest(BaseModel):
    target_role: str
    target_tenant_id: Optional[str] = None

class UserRolesResponse(BaseModel):
    current_role: str
    available_roles: List[dict]
    can_switch: bool


def _is_role_active(role_info: dict) -> bool:
    if role_info.get("is_active") is False:
        return False
    expires_at = role_info.get("expires_at")
    if expires_at:
        try:
            exp_dt = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
            if exp_dt < datetime.now(timezone.utc):
                return False
        except (ValueError, TypeError):
            pass
    return True


def setup_user_roles_routes(db, get_current_user, require_roles, UserRole, create_access_token, require_recent_mfa=None):
    router = APIRouter(prefix="/user-roles", tags=["User Roles"])

    async def _get_school_name(tenant_id: str) -> Optional[str]:
        if not tenant_id:
            return None
        school = await gd_find_one(db.session, "schools", {"id": tenant_id})
        if school:
            return school.get("name") or school.get("name_en")
        return None

    def _build_descriptive_label_ar(role: str, school_name: Optional[str]) -> str:
        role_ar = get_role_name_ar(role)
        if school_name and role not in PLATFORM_ROLES:
            return f"{role_ar} في {school_name}"
        return role_ar

    def _build_descriptive_label_en(role: str, school_name: Optional[str]) -> str:
        role_en = get_role_name_en(role)
        if school_name and role not in PLATFORM_ROLES:
            return f"{role_en} at {school_name}"
        return role_en

    @router.get("/my-roles")
    async def get_my_roles(
        current_user: dict = Depends(get_current_user)
    ):
        try:
            user_id = current_user.get("id")
            user = await gd_find_one(db.session, "users", {"id": user_id})
            if not user:
                raise HTTPException(status_code=404, detail="المستخدم غير موجود")

            current_role = current_user.get("role")
            current_tenant = current_user.get("tenant_id")

            primary_tenant_id = user.get("tenant_id")
            primary_school_name = user.get("school_name") or user.get("tenant_name") or await _get_school_name(primary_tenant_id)

            available_roles = [{
                "role": user.get("role"),
                "role_name_ar": get_role_name_ar(user.get("role")),
                "role_name_en": get_role_name_en(user.get("role")),
                "descriptive_ar": _build_descriptive_label_ar(user.get("role"), primary_school_name),
                "descriptive_en": _build_descriptive_label_en(user.get("role"), primary_school_name),
                "tenant_id": primary_tenant_id,
                "tenant_name": primary_school_name,
                "is_current": user.get("role") == current_role and (primary_tenant_id == current_tenant or not current_tenant),
                "is_primary": True
            }]

            additional_roles = user.get("additional_roles", [])
            for role_info in additional_roles:
                if not _is_role_active(role_info):
                    continue
                r_tenant = role_info.get("tenant_id")
                r_name = role_info.get("tenant_name") or await _get_school_name(r_tenant)
                available_roles.append({
                    "role": role_info.get("role"),
                    "role_name_ar": get_role_name_ar(role_info.get("role")),
                    "role_name_en": get_role_name_en(role_info.get("role")),
                    "descriptive_ar": _build_descriptive_label_ar(role_info.get("role"), r_name),
                    "descriptive_en": _build_descriptive_label_en(role_info.get("role"), r_name),
                    "tenant_id": r_tenant,
                    "tenant_name": r_name,
                    "is_current": role_info.get("role") == current_role and r_tenant == current_tenant,
                    "is_primary": False
                })

            if user.get("role") == "platform_admin":
                schools = await gd_find(db.session, "schools", {}, limit=100)
                _it_excluded_statuses = {"archived", "pending_hard_delete"}
                for school in schools:
                    s_id = school.get("id") or ""
                    s_status = school.get("status") or ""
                    if s_id.startswith("itw_") or s_status in _it_excluded_statuses:
                        continue
                    s_name = school.get("name") or school.get("name_en")
                    active_principal_count = await gd_count(
                        db.session, "users",
                        {"role": "school_principal", "tenant_id": s_id, "is_active": True},
                    )
                    available_roles.append({
                        "role": "school_principal",
                        "role_name_ar": "معاينة كمدير مدرسة",
                        "role_name_en": "Preview as School Principal",
                        "descriptive_ar": f"معاينة كمدير — {s_name}",
                        "descriptive_en": f"Preview as Principal — {s_name}",
                        "tenant_id": school.get("id"),
                        "tenant_name": s_name,
                        "is_current": False,
                        "is_primary": False,
                        "is_preview": True,
                        "no_principal": active_principal_count == 0,
                    })

            return {
                "user_id": user_id,
                "current_role": current_role,
                "current_tenant_id": current_tenant,
                "is_switched": current_user.get("is_switched", False),
                "original_role": current_user.get("original_role"),
                "available_roles": available_roles,
                "can_switch": len(available_roles) > 1
            }
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting user roles: {e}")
            raise HTTPException(status_code=500, detail="حدث خطأ داخلي في الخادم")

    @router.get("/available")
    async def get_available_roles(
        current_user: dict = Depends(get_current_user)
    ):
        try:
            user_id = current_user.get("id")
            user = await gd_find_one(db.session, "users", {"id": user_id})
            if not user:
                raise HTTPException(status_code=404, detail="المستخدم غير موجود")

            current_role = current_user.get("role")
            current_tenant = current_user.get("tenant_id")

            primary_tenant_id = user.get("tenant_id")
            primary_school_name = user.get("school_name") or user.get("tenant_name") or await _get_school_name(primary_tenant_id)

            roles = [{
                "role": user.get("role"),
                "role_name_ar": get_role_name_ar(user.get("role")),
                "role_name_en": get_role_name_en(user.get("role")),
                "descriptive_ar": _build_descriptive_label_ar(user.get("role"), primary_school_name),
                "descriptive_en": _build_descriptive_label_en(user.get("role"), primary_school_name),
                "tenant_id": primary_tenant_id,
                "tenant_name": primary_school_name,
                "is_current": user.get("role") == current_role and (primary_tenant_id == current_tenant or not current_tenant),
                "is_primary": True
            }]

            additional_roles = user.get("additional_roles", [])
            for role_info in additional_roles:
                if not _is_role_active(role_info):
                    continue
                r_tenant = role_info.get("tenant_id")
                r_name = role_info.get("tenant_name") or await _get_school_name(r_tenant)
                roles.append({
                    "role": role_info.get("role"),
                    "role_name_ar": get_role_name_ar(role_info.get("role")),
                    "role_name_en": get_role_name_en(role_info.get("role")),
                    "descriptive_ar": _build_descriptive_label_ar(role_info.get("role"), r_name),
                    "descriptive_en": _build_descriptive_label_en(role_info.get("role"), r_name),
                    "tenant_id": r_tenant,
                    "tenant_name": r_name,
                    "is_current": role_info.get("role") == current_role and r_tenant == current_tenant,
                    "is_primary": False
                })

            if user.get("role") == "platform_admin":
                schools = await gd_find(db.session, "schools", {}, limit=100)
                _it_excluded_statuses = {"archived", "pending_hard_delete"}
                for school in schools:
                    s_id = school.get("id") or ""
                    s_status = school.get("status") or ""
                    if s_id.startswith("itw_") or s_status in _it_excluded_statuses:
                        continue
                    s_name = school.get("name") or school.get("name_en")
                    active_principal_count = await gd_count(
                        db.session, "users",
                        {"role": "school_principal", "tenant_id": s_id, "is_active": True},
                    )
                    roles.append({
                        "role": "school_principal",
                        "role_name_ar": "معاينة كمدير مدرسة",
                        "role_name_en": "Preview as School Principal",
                        "descriptive_ar": f"معاينة كمدير — {s_name}",
                        "descriptive_en": f"Preview as Principal — {s_name}",
                        "tenant_id": school.get("id"),
                        "tenant_name": s_name,
                        "is_current": False,
                        "is_primary": False,
                        "is_preview": True,
                        "no_principal": active_principal_count == 0,
                    })

            return {"roles": roles}
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting available roles: {e}")
            raise HTTPException(status_code=500, detail="حدث خطأ داخلي في الخادم")

    # Build the MFA dependency once so it can be referenced in the handler
    # signature. Falls back to plain get_current_user if require_recent_mfa
    # was not supplied (backwards-compat shim for tests / old callers).
    _switch_mfa_dep = require_recent_mfa() if require_recent_mfa is not None else get_current_user

    @router.post("/switch")
    async def switch_role(
        request_body: RoleSwitchRequest,
        request: Request,
        current_user: dict = Depends(_switch_mfa_dep)
    ):
        try:
            user_id = current_user.get("id")
            user = await gd_find_one(db.session, "users", {"id": user_id})
            if not user:
                raise HTTPException(status_code=404, detail="المستخدم غير موجود")

            target_role = request_body.target_role
            target_tenant_id = request_body.target_tenant_id

            if target_role in SCHOOL_SCOPED_ROLES and not target_tenant_id:
                if user.get("role") == target_role and user.get("tenant_id"):
                    target_tenant_id = user.get("tenant_id")
                else:
                    matched = None
                    for ri in user.get("additional_roles", []):
                        if ri.get("role") == target_role and ri.get("tenant_id"):
                            matched = ri
                            break
                    if matched:
                        target_tenant_id = matched.get("tenant_id")
                    else:
                        raise HTTPException(
                            status_code=400,
                            detail="يجب تحديد المدرسة للأدوار المدرسية"
                        )

            is_valid_role = False
            tenant_name = None

            if user.get("role") == target_role:
                if target_tenant_id is None or target_tenant_id == user.get("tenant_id"):
                    is_valid_role = True
                    target_tenant_id = target_tenant_id or user.get("tenant_id")
                    tenant_name = user.get("school_name") or user.get("tenant_name")

            additional_roles = user.get("additional_roles", [])
            for role_info in additional_roles:
                if role_info.get("role") == target_role:
                    if not _is_role_active(role_info):
                        continue
                    if target_tenant_id is None or target_tenant_id == role_info.get("tenant_id"):
                        is_valid_role = True
                        target_tenant_id = target_tenant_id or role_info.get("tenant_id")
                        tenant_name = role_info.get("tenant_name")
                        break

            # SECURITY (task #355 vuln-2): block cross-tenant platform_admin impersonation
            # on this legacy endpoint. Platform admins must use the hardened
            # /role-switch/switch route which enforces reason, fresh MFA, and a
            # server-side impersonation_sessions row with its own restore path.
            # Allowing it here (even with MFA) bypasses the reason requirement and
            # the nested-impersonation guard of the hardened flow.
            if user.get("role") == "platform_admin" and target_role in SCHOOL_SCOPED_ROLES:
                raise HTTPException(
                    status_code=403,
                    detail="استخدم نقطة النهاية /role-switch/switch للتبديل إلى دور مدرسي"
                )

            if not is_valid_role:
                raise HTTPException(status_code=403, detail="ليس لديك صلاحية لهذا الدور")

            if target_tenant_id and target_role in SCHOOL_SCOPED_ROLES:
                school_doc = await gd_find_one(db.session, "schools", {"id": target_tenant_id})
                if not school_doc:
                    raise HTTPException(status_code=404, detail="المدرسة غير موجودة")

            if not tenant_name and target_tenant_id:
                tenant_name = await _get_school_name(target_tenant_id)

            from_role = current_user.get("role")
            original_role = current_user.get("original_role") or user.get("role")

            # SECURITY (audit H-2 / M-6 — Phase 2): for cross-tenant
            # platform-admin switches (the impersonation-style path on
            # this legacy endpoint), apply the same 15-minute TTL cap
            # and server-side `impersonation_sessions` persistence as
            # the hardened `/role-switch/switch` route. Same-user
            # multi-role swaps (e.g. principal ↔ teacher on the same
            # tenant) are NOT impersonation and keep the default TTL.
            is_cross_tenant_impersonation = (
                from_role == "platform_admin"
                and target_role in SCHOOL_SCOPED_ROLES
                and target_tenant_id
                and target_tenant_id != user.get("tenant_id")
            )

            token_data = {
                "sub": user_id,
                "role": target_role,
                "tenant_id": target_tenant_id,
                "school_id": target_tenant_id if target_role in SCHOOL_SCOPED_ROLES else None,
                "original_role": original_role,
                "is_switched": True
            }

            if is_cross_tenant_impersonation:
                from datetime import timedelta as _td
                new_token = create_access_token(token_data, expires_delta=_td(minutes=15))
            else:
                new_token = create_access_token(token_data)

            from utils.trusted_proxy import extract_client_ip as _ip
            client_ip = _ip(request)

            if is_cross_tenant_impersonation:
                import jwt as _jwt
                from dependencies import JWT_SECRET as _JS, JWT_ALGORITHM as _JA
                from sqlalchemy import text as _sa_text
                from datetime import timedelta as _td
                _payload = _jwt.decode(new_token, _JS, algorithms=[_JA])
                _now = datetime.now(timezone.utc)
                try:
                    await db.session.execute(
                        _sa_text(
                            """
                            INSERT INTO impersonation_sessions
                              (id, jti, original_user_id, original_role, target_user_id,
                               target_role, target_tenant_id, reason, started_at,
                               expires_at, ip_address)
                            VALUES
                              (:id, :jti, :ouid, :orole, :tuid, :trole, :ttid,
                               :reason, :started_at, :expires_at, :ip)
                            """
                        ),
                        {
                            "id": str(uuid.uuid4()),
                            "jti": _payload.get("jti"),
                            "ouid": user_id,
                            "orole": from_role,
                            "tuid": user_id,
                            "trole": target_role,
                            "ttid": target_tenant_id,
                            "reason": "legacy /user-roles/switch (cross-tenant impersonation)",
                            "started_at": _now,
                            "expires_at": _now + _td(minutes=15),
                            "ip": client_ip,
                        },
                    )
                except Exception as _e:
                    logger.warning(
                        f"Failed to persist legacy impersonation session: {_e}"
                    )

            await gd_insert(db.session, "audit_logs", {
                "id": str(uuid.uuid4()),
                "action": "role_switched",
                # Audit M2 (2026-05-25): match the hardened
                # /role-switch/switch schema so SIEM filtering by severity
                # / actor_role works uniformly across both surfaces.
                "severity": "high",
                "actor_role": from_role,
                "user_id": user_id,
                "performed_by": user_id,
                "performed_by_name": user.get("full_name"),
                "tenant_id": target_tenant_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "ip_address": client_ip,
                "details": {
                    "from_role": from_role,
                    "to_role": target_role,
                    "original_role": original_role,
                    "tenant_id": target_tenant_id,
                    "tenant_name": tenant_name
                }
            })

            await gd_insert(db.session, "role_switch_history", {
                "id": str(uuid.uuid4()),
                "user_id": user_id,
                "from_role": from_role,
                "to_role": target_role,
                "tenant_id": target_tenant_id,
                "tenant_name": tenant_name,
                "switched_at": datetime.now(timezone.utc).isoformat()
            })

            role_dashboard_map = {
                "platform_admin": "/admin",
                "platform_operations_manager": "/admin",
                "school_principal": "/principal",
                "school_admin": "/principal",
                "school_sub_admin": "/school",
                "teacher": "/teacher",
                "independent_teacher": "/teacher",
                "student": "/student",
                "parent": "/parent",
            }

            return {
                "success": True,
                "access_token": new_token,
                "token_type": "bearer",
                "role": target_role,
                "tenant_id": target_tenant_id,
                "school_id": target_tenant_id if target_role in SCHOOL_SCOPED_ROLES else None,
                "tenant_name": tenant_name,
                "redirect_to": role_dashboard_map.get(target_role, "/"),
                "message": f"تم التبديل إلى دور {get_role_name_ar(target_role)}"
            }
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error switching role: {e}")
            raise HTTPException(status_code=500, detail="حدث خطأ داخلي في الخادم")

    @router.post("/return-to-original")
    async def return_to_original_role(
        request: Request,
        credentials: _HTTPAuthorizationCredentials = Depends(_bearer_scheme),
        current_user: dict = Depends(_switch_mfa_dep)
    ):
        try:
            user_id = current_user.get("id")
            user = await gd_find_one(db.session, "users", {"id": user_id})
            if not user:
                raise HTTPException(status_code=404, detail="المستخدم غير موجود")

            if not current_user.get("is_switched"):
                raise HTTPException(status_code=400, detail="لم يتم تبديل الدور")

            original_role = user.get("role")
            original_tenant_id = user.get("tenant_id")
            from_role = current_user.get("role")

            # Decode the current switched token to extract its JTI for revocation.
            # The signature was already verified by get_current_user upstream.
            import jwt as _jwt
            from dependencies import JWT_SECRET as _JS, JWT_ALGORITHM as _JA
            from datetime import datetime as _dt, timezone as _tz, timedelta as _td
            _old_payload = _jwt.decode(
                credentials.credentials, _JS, algorithms=[_JA],
                options={"verify_exp": False}
            )
            _old_jti = _old_payload.get("jti")
            _old_exp = _old_payload.get("exp")

            token_data = {
                "sub": user_id,
                "role": original_role,
                "tenant_id": original_tenant_id,
                "school_id": original_tenant_id if original_role in SCHOOL_SCOPED_ROLES else None,
                "is_switched": False
            }
            new_token = create_access_token(token_data)

            # Revoke the old switched token so it cannot be replayed after restore.
            # Fail-closed: if the old token carries no JTI we cannot guarantee
            # revocation, so we abort rather than silently handing back a new
            # token while the old switched one remains valid.
            if not _old_jti:
                logger.error("return-to-original: switched token has no JTI — refusing restore to prevent token replay")
                raise HTTPException(status_code=500, detail="تعذّر إنهاء الجلسة بأمان. يرجى المحاولة مجدداً")
            if _old_jti:
                if _old_exp:
                    _rev_exp_dt = _dt.fromtimestamp(_old_exp, tz=_tz.utc)
                else:
                    _rev_exp_dt = _dt.now(_tz.utc) + _td(minutes=30)
                try:
                    from sqlalchemy import text as _sa_text_r
                    await db.session.execute(
                        _sa_text_r(
                            "INSERT INTO revoked_tokens (jti, expires_at, revoked_at) "
                            "VALUES (:jti, :exp, :rev) "
                            "ON CONFLICT (jti) DO NOTHING"
                        ),
                        {"jti": _old_jti, "exp": _rev_exp_dt, "rev": _dt.now(_tz.utc)},
                    )
                except Exception as _rev_err:
                    logger.error(f"return-to-original: failed to revoke switched token JTI={_old_jti}: {_rev_err}")
                    raise HTTPException(status_code=500, detail="تعذّر إنهاء الجلسة بأمان. يرجى المحاولة مجدداً")

            from utils.trusted_proxy import extract_client_ip as _ip_fn
            client_ip = _ip_fn(request)

            await gd_insert(db.session, "audit_logs", {
                "id": str(uuid.uuid4()),
                "action": "role_returned_to_original",
                "user_id": user_id,
                "performed_by": user_id,
                "performed_by_name": user.get("full_name"),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "ip_address": client_ip,
                "details": {
                    "from_role": from_role,
                    "to_role": original_role
                }
            })

            role_dashboard_map = {
                "platform_admin": "/admin",
                "platform_operations_manager": "/admin",
                "school_principal": "/principal",
                "school_admin": "/principal",
                "school_sub_admin": "/school",
                "teacher": "/teacher",
                "independent_teacher": "/teacher",
                "student": "/student",
                "parent": "/parent",
            }

            return {
                "success": True,
                "access_token": new_token,
                "token_type": "bearer",
                "role": original_role,
                "tenant_id": original_tenant_id,
                "redirect_to": role_dashboard_map.get(original_role, "/"),
                "message": "تمت العودة للدور الأصلي"
            }
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error returning to original role: {e}")
            raise HTTPException(status_code=500, detail="حدث خطأ داخلي في الخادم")

    @router.get("/switch-history")
    async def get_switch_history(
        current_user: dict = Depends(get_current_user)
    ):
        try:
            user_id = current_user.get("id")
            history = await gd_find(db.session, "role_switch_history", {"user_id": user_id}, order_by="switched_at", desc_order=True, limit=20)

            return {
                "history": [
                    {
                        "id": h.get("id"),
                        "from_role": h.get("from_role"),
                        "from_role_name": get_role_name_ar(h.get("from_role")),
                        "to_role": h.get("to_role"),
                        "to_role_name": get_role_name_ar(h.get("to_role")),
                        "tenant_name": h.get("tenant_name"),
                        "switched_at": h.get("switched_at")
                    }
                    for h in history
                ]
            }
        except Exception as e:
            return {"history": []}

    return router


def get_role_name_ar(role: str) -> str:
    role_names = {
        "platform_admin": "مدير المنصة",
        "platform_operations_manager": "مدير العمليات",
        "platform_technical_admin": "مسؤول تقني",
        "platform_support_specialist": "دعم فني",
        "platform_data_analyst": "محلل بيانات",
        "platform_security_officer": "مسؤول أمن",
        "school_principal": "مدير المدرسة",
        "school_sub_admin": "نائب مدير المدرسة",
        "school_admin": "مسؤول المدرسة",
        "teacher": "معلم",
        "independent_teacher": "معلم مستقل",
        "student": "طالب",
        "parent": "ولي أمر",
    }
    return role_names.get(role, role)


def get_role_name_en(role: str) -> str:
    role_names = {
        "platform_admin": "Platform Admin",
        "platform_operations_manager": "Operations Manager",
        "platform_technical_admin": "Technical Admin",
        "platform_support_specialist": "Support Specialist",
        "platform_data_analyst": "Data Analyst",
        "platform_security_officer": "Security Officer",
        "school_principal": "School Principal",
        "school_sub_admin": "Deputy Principal",
        "school_admin": "School Admin",
        "teacher": "Teacher",
        "independent_teacher": "Independent Teacher",
        "student": "Student",
        "parent": "Parent",
    }
    return role_names.get(role, role)
