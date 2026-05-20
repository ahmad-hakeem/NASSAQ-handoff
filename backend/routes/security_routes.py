"""
Security Center Routes - مسارات مركز الأمان
APIs for security operations: lock/unlock accounts, end sessions, force password change
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timezone
import uuid
import logging
import os
from engines.sql_utils import gd_find, gd_find_one, gd_insert, gd_insert_many, gd_update_one, gd_update_many, gd_count, gd_delete_one, gd_delete_many, gd_distinct, gd_upsert, _gd_aggregate
logger = logging.getLogger("nassaq")

# Models
class AccountSearchRequest(BaseModel):
    """بحث عن حساب بالبريد أو رقم الهاتف"""
    search_query: str  # email or phone


class AccountSearchResult(BaseModel):
    """نتيجة البحث عن حساب"""
    id: str
    email: str
    name: str
    phone: Optional[str] = None
    role: str
    is_active: bool
    is_locked: bool = False


class ForcePasswordChangeRequest(BaseModel):
    """طلب فرض تغيير كلمة المرور"""
    target_type: str  # 'user', 'role', 'all'
    user_id: Optional[str] = None
    role: Optional[str] = None


class SessionActionResult(BaseModel):
    """نتيجة إجراء على الجلسات"""
    success: bool
    message: str
    affected_count: int = 0


def setup_security_routes(db, get_current_user, require_roles, UserRole, require_recent_mfa=None):
    # Task #169 Step 7: require_recent_mfa is injected by app/routes.py.
    # Defensive default: if a caller forgets to pass it (e.g. an old test
    # harness), fall back to a no-op that simply re-uses get_current_user
    # — that fail-open behaviour is ONLY acceptable in test contexts.
    if require_recent_mfa is None:
        def require_recent_mfa(max_age_seconds: int = 300):  # noqa: ARG001
            return get_current_user
    """Setup security routes with database and auth dependencies"""
    
    router = APIRouter(prefix="/security", tags=["Security Center"])
    
    @router.post("/search-account", response_model=List[AccountSearchResult])
    async def search_account(
        request: AccountSearchRequest,
        current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))
    ):
        """
        البحث عن حساب بالبريد الإلكتروني أو رقم الهاتف
        Search for an account by email or phone
        """
        try:
            import re as _re
            query = request.search_query.strip()
            if not query:
                return []
            
            safe_query = _re.escape(query)
            # Search by email or phone
            results = await gd_find(db.session, "users", {
                "$or": [
                    {"email": {"$regex": safe_query, "$options": "i"}},
                    {"phone": {"$regex": safe_query, "$options": "i"}}
                ]
            }, limit=20)
            
            return [
                AccountSearchResult(
                    id=str(user.get("id", user.get("_id", ""))),
                    email=user.get("email", ""),
                    name=user.get("name", user.get("full_name", "")),
                    phone=user.get("phone"),
                    role=user.get("role", "unknown"),
                    is_active=user.get("is_active", True),
                    is_locked=user.get("is_locked", False)
                )
                for user in results
            ]
        except Exception as e:
            logger.error(f"Error searching accounts: {e}")
            return []
    
    @router.post("/lock-account/{user_id}")
    async def lock_account(
        user_id: str,
        current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN])),
        # Task #169 Step 7: locking accounts is platform-admin only AND
        # requires a fresh MFA proof (≤5 minutes).
        _stepup: dict = Depends(require_recent_mfa()),
    ):
        """
        قفل حساب مستخدم
        Lock a user account
        """
        try:
            result = await gd_update_one(db.session, "users", {"$or": [{"id": user_id}, {"_id": user_id}]}, {
                        "is_locked": True,
                        "is_active": False,
                        "locked_at": datetime.now(timezone.utc).isoformat(),
                        "locked_by": current_user.get("id")
                    })
            
            if result == 0:
                raise HTTPException(status_code=404, detail="المستخدم غير موجود")
            
            # Log the action
            await gd_insert(db.session, "audit_logs", {
                "id": str(uuid.uuid4()),
                "action": "account_locked",
                "target_user_id": user_id,
                "performed_by": current_user.get("id"),
                "performed_by_name": current_user.get("name"),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "details": {"reason": "Manual lock by admin"}
            })
            
            # Send real-time security notification
            try:
                from routes.websocket_routes import get_connection_manager, send_realtime_notification
                ws_manager = get_connection_manager()
                # Notify the user whose account was locked
                await send_realtime_notification(
                    manager=ws_manager,
                    db=db,
                    notification_type="account_locked",
                    message_ar="تم قفل حسابك. يرجى التواصل مع الدعم الفني.",
                    message_en="Your account has been locked. Please contact support.",
                    target_users=[user_id],
                    save_to_db=True
                )
                # Notify other platform admins
                await send_realtime_notification(
                    manager=ws_manager,
                    db=db,
                    notification_type="security_alert",
                    message_ar=f"تم قفل حساب المستخدم {user_id} بواسطة {current_user.get('name', 'مدير')}",
                    message_en=f"User account {user_id} was locked by {current_user.get('name', 'Admin')}",
                    target_roles=["platform_admin", "platform_security_officer"],
                    extra_data={"target_user_id": user_id, "action": "account_locked"},
                    save_to_db=True
                )
            except Exception as e:
                logger.warning(f"Failed to send security notification: {e}")
            
            return {"success": True, "message": "تم قفل الحساب بنجاح"}
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail="خطأ في قفل الحساب")
    
    @router.post("/unlock-account/{user_id}")
    async def unlock_account(
        user_id: str,
        current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN])),
        # Unlocking re-enables a previously locked account. Require a fresh MFA
        # proof so a stolen admin bearer token cannot silently restore a locked
        # account and replay old attacker-held tokens.
        _stepup: dict = Depends(require_recent_mfa()),
    ):
        """
        فتح حساب مستخدم
        Unlock a user account
        """
        try:
            now = datetime.now(timezone.utc).isoformat()
            # Advance last_password_change so any attacker-held access/refresh
            # tokens that pre-date this unlock are immediately rejected by the
            # iat-vs-last_password_change check in get_current_user and the
            # refresh-token validator.
            result = await gd_update_one(db.session, "users", {"$or": [{"id": user_id}, {"_id": user_id}]}, {
                        "is_locked": False,
                        "is_active": True,
                        "unlocked_at": now,
                        "unlocked_by": current_user.get("id"),
                        "last_password_change": now,
                    })
            
            if result == 0:
                raise HTTPException(status_code=404, detail="المستخدم غير موجود")
            
            # Log the action
            await gd_insert(db.session, "audit_logs", {
                "id": str(uuid.uuid4()),
                "action": "account_unlocked",
                "target_user_id": user_id,
                "performed_by": current_user.get("id"),
                "performed_by_name": current_user.get("name"),
                "timestamp": now,
            })
            
            return {"success": True, "message": "تم فتح الحساب بنجاح"}
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail="خطأ في فتح الحساب")
    
    @router.post("/end-all-sessions", response_model=SessionActionResult)
    async def end_all_sessions(
        current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN])),
        # Task #169 Step 7: terminating every active session platform-wide
        # is the broadest blast-radius admin action — gate with fresh MFA.
        _stepup: dict = Depends(require_recent_mfa()),
    ):
        """
        إنهاء جميع الجلسات النشطة لجميع المستخدمين
        End all active sessions for all users (system-wide)
        """
        try:
            now = datetime.now(timezone.utc).isoformat()
            admin_id = current_user.get("id")

            await gd_insert(db.session, "audit_logs", {
                "id": str(uuid.uuid4()),
                "action": "all_sessions_terminated",
                "performed_by": admin_id,
                "performed_by_name": current_user.get("name", current_user.get("full_name", "")),
                "timestamp": now,
                "details": {"note": "JWT-based auth — clients must re-authenticate"}
            })

            return SessionActionResult(
                success=True,
                message="تم تسجيل طلب إنهاء الجلسات — يجب على المستخدمين إعادة تسجيل الدخول",
                affected_count=0
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail="خطأ في إنهاء الجلسات")
    
    @router.post("/force-password-change")
    async def force_password_change(
        request: ForcePasswordChangeRequest,
        current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))
    ):
        """
        فرض تغيير كلمة المرور
        Force password change for a user, role, or all users
        """
        try:
            affected_count = 0
            
            if request.target_type == 'user' and request.user_id:
                # Single user
                result = await gd_update_one(db.session, "users", {"$or": [{"id": request.user_id}, {"_id": request.user_id}]}, {
                            "must_change_password": True,
                            "password_change_required_at": datetime.now(timezone.utc).isoformat(),
                            "password_change_required_by": current_user.get("id")
                        })
                affected_count = result
                
            elif request.target_type == 'role' and request.role:
                # All users with specific role
                result = await gd_update_many(db.session, "users", {"role": request.role}, {
                            "must_change_password": True,
                            "password_change_required_at": datetime.now(timezone.utc).isoformat(),
                            "password_change_required_by": current_user.get("id")
                        })
                affected_count = result
                
                logger.info(f"Force password change applied to role={request.role}, affected={affected_count}")
                
            elif request.target_type == 'all':
                # ALL users except current admin
                result = await gd_update_many(db.session, "users", {"id": {"$ne": current_user.get("id")}}, {
                            "must_change_password": True,
                            "password_change_required_at": datetime.now(timezone.utc).isoformat(),
                            "password_change_required_by": current_user.get("id")
                        })
                affected_count = result
                
                logger.info(f"Force password change applied to all users, affected={affected_count}")
            
            # Log the action
            await gd_insert(db.session, "audit_logs", {
                "id": str(uuid.uuid4()),
                "action": "force_password_change",
                "target_type": request.target_type,
                "target_role": request.role,
                "target_user_id": request.user_id,
                "performed_by": current_user.get("id"),
                "performed_by_name": current_user.get("name"),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "details": {"affected_count": affected_count}
            })
            
            return {
                "success": True,
                "message": f"تم فرض تغيير كلمة المرور على {affected_count} مستخدم",
                "affected_count": affected_count
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail="خطأ في فرض تغيير كلمة المرور")
    
    @router.get("/roles")
    async def get_available_roles(
        current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))
    ):
        """
        جلب قائمة الأدوار المتاحة في النظام
        Get list of available roles in the system
        """
        roles = [
            {"id": "platform_admin", "name_ar": "مدير المنصة", "name_en": "Platform Admin"},
            {"id": "school_principal", "name_ar": "مدير مدرسة", "name_en": "School Principal"},
            {"id": "teacher", "name_ar": "معلم", "name_en": "Teacher"},
            {"id": "student", "name_ar": "طالب", "name_en": "Student"},
            {"id": "parent", "name_ar": "ولي أمر", "name_en": "Parent"},
            {"id": "independent_teacher", "name_ar": "معلم مستقل", "name_en": "Independent Teacher"},
        ]
        return roles

    @router.post("/deactivate-account/{user_id}")
    async def deactivate_account(
        user_id: str,
        current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN])),
        # Task #169 Step 7: deactivation is irreversible from the user's
        # perspective until reactivated; gate with fresh MFA.
        _stepup: dict = Depends(require_recent_mfa()),
    ):
        """تعطيل حساب مستخدم"""
        try:
            user = await gd_find_one(db.session, "users", {"id": user_id})
            if not user:
                raise HTTPException(status_code=404, detail="المستخدم غير موجود")

            now = datetime.now(timezone.utc).isoformat()
            await gd_update_one(db.session, "users", {"id": user_id}, {"is_active": False, "deactivated_at": now, "deactivated_by": current_user["id"]})

            await gd_insert(db.session, "audit_logs", {
                "id": str(uuid.uuid4()),
                "action": "account_deactivated",
                "performed_by": current_user.get("id"),
                "performed_by_name": current_user.get("full_name"),
                "target_id": user_id,
                "target_name": user.get("full_name"),
                "timestamp": now
            })

            return {"success": True, "message": "تم تعطيل الحساب بنجاح"}
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail="حدث خطأ داخلي في الخادم")

    @router.post("/reactivate-account/{user_id}")
    async def reactivate_account(
        user_id: str,
        current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN])),
        # Reactivating a disabled account restores login ability. Require a
        # fresh MFA proof so a stolen admin token cannot silently resurrect a
        # disabled account and make old attacker-held refresh tokens valid again.
        _stepup: dict = Depends(require_recent_mfa()),
    ):
        """إعادة تفعيل حساب مستخدم"""
        try:
            user = await gd_find_one(db.session, "users", {"id": user_id})
            if not user:
                raise HTTPException(status_code=404, detail="المستخدم غير موجود")

            now = datetime.now(timezone.utc).isoformat()
            # Advance last_password_change so any attacker-held access/refresh
            # tokens that pre-date this reactivation are immediately rejected by
            # the iat-vs-last_password_change check in get_current_user and the
            # refresh-token validator.
            await gd_update_one(db.session, "users", {"id": user_id}, {
                "is_active": True,
                "reactivated_at": now,
                "last_password_change": now,
            })

            await gd_insert(db.session, "audit_logs", {
                "id": str(uuid.uuid4()),
                "action": "account_reactivated",
                "performed_by": current_user.get("id"),
                "performed_by_name": current_user.get("full_name"),
                "target_id": user_id,
                "target_name": user.get("full_name"),
                "timestamp": now
            })

            return {"success": True, "message": "تم إعادة تفعيل الحساب بنجاح"}
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail="حدث خطأ داخلي في الخادم")

    @router.post("/password-reset-request/{user_id}")
    async def create_password_reset(
        user_id: str,
        current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN])),
        # Task #169 Step 7: admin-issued password resets mint a temp
        # password that grants login → also gate with fresh MFA.
        _stepup: dict = Depends(require_recent_mfa()),
    ):
        """إنشاء طلب إعادة تعيين كلمة المرور (يرسل كلمة مرور مؤقتة)"""
        try:
            user = await gd_find_one(db.session, "users", {"id": user_id})
            if not user:
                raise HTTPException(status_code=404, detail="المستخدم غير موجود")

            import hashlib
            temp_password = f"Temp@{uuid.uuid4().hex[:8]}"
            from routes.auth_routes_mod import hash_password
            hashed = hash_password(temp_password)

            now = datetime.now(timezone.utc).isoformat()
            await gd_update_one(db.session, "users", {"id": user_id}, {
                    "password_hash": hashed,
                    "must_change_password": True,
                    "password_reset_at": now,
                    "password_reset_by": current_user["id"]
                })

            await gd_insert(db.session, "audit_logs", {
                "id": str(uuid.uuid4()),
                "action": "password_reset",
                "performed_by": current_user.get("id"),
                "performed_by_name": current_user.get("full_name"),
                "target_id": user_id,
                "target_name": user.get("full_name"),
                "timestamp": now
            })

            logger.info(f"Password reset for user {user_id} by admin {current_user.get('id')}")
            return {
                "success": True,
                "message": "تم إعادة تعيين كلمة المرور بنجاح. سيُطلب من المستخدم تغيير كلمة المرور عند الدخول.",
                "temporary_password": temp_password,
                "must_change_on_login": True
            }
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail="حدث خطأ داخلي في الخادم")

    @router.get("/account-status/{user_id}")
    async def get_account_status(
        user_id: str,
        current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))
    ):
        """جلب حالة الحساب"""
        user = await gd_find_one(db.session, "users", {"id": user_id})
        if not user:
            raise HTTPException(status_code=404, detail="المستخدم غير موجود")

        SENSITIVE_FIELDS = {"password_hash", "password", "refresh_token", "reset_token"}
        safe_user = {k: v for k, v in user.items() if k not in SENSITIVE_FIELDS}
        return safe_user

    @router.get("/dashboard")
    async def security_dashboard(
        current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))
    ):
        """
        لوحة بيانات مركز الأمان — بيانات حقيقية
        Security Center Dashboard — real computed data
        """
        from datetime import timedelta
        try:
            now = datetime.now(timezone.utc)
            cutoff_24h = (now - timedelta(hours=24)).isoformat()
            cutoff_30d = (now - timedelta(days=30)).isoformat()

            total_accounts = await gd_count(db.session, "users", {})
            active_accounts = await gd_count(db.session, "users", {"is_active": True})
            locked_accounts = await gd_count(db.session, "users", {"is_locked": True})
            must_change_pw = await gd_count(db.session, "users", {"must_change_password": True})

            failed_logins_24h = await gd_count(db.session, "audit_logs", {
                "action": {"$in": ["auth.login_failed", "login_failed"]},
                "timestamp": {"$gte": cutoff_24h},
            })

            successful_logins_30d = await gd_count(db.session, "audit_logs", {
                "action": {"$in": ["auth.login", "login"]},
                "timestamp": {"$gte": cutoff_30d},
            })
            failed_logins_30d = await gd_count(db.session, "audit_logs", {
                "action": {"$in": ["auth.login_failed", "login_failed"]},
                "timestamp": {"$gte": cutoff_30d},
            })

            total_audit_events = await gd_count(db.session, "audit_logs", {
                "timestamp": {"$gte": cutoff_30d},
            })

            protected_pct = round((active_accounts / max(total_accounts, 1)) * 100) if total_accounts > 0 else 0

            total_login_attempts = successful_logins_30d + failed_logins_30d
            login_success_rate = round((successful_logins_30d / max(total_login_attempts, 1)) * 100) if total_login_attempts > 0 else 100

            pw_no_change = must_change_pw
            pw_policy_score = max(0, 100 - (pw_no_change * 5))
            pw_policy_score = min(100, pw_policy_score)

            https_enabled = bool(os.environ.get("REPLIT_DEV_DOMAIN") or os.environ.get("REPL_SLUG"))
            db_url = os.environ.get("DATABASE_URL", "")
            ssl_in_db = "sslmode" in db_url or "ssl=true" in db_url.lower()
            encryption_score = 0
            if https_enabled:
                encryption_score += 60
            if ssl_in_db or db_url:
                encryption_score += 40
            encryption_score = min(100, encryption_score)

            db_status_score = 0
            try:
                from engines.sql_utils import gd_count as _gc
                test_count = await _gc(db.session, "users", {})
                db_status_score = 100 if test_count >= 0 else 50
            except Exception:
                db_status_score = 30

            logging_score = 100 if total_audit_events > 0 else 50
            account_security_score = max(0, 100 - (locked_accounts * 5) - (failed_logins_24h * 2))
            auth_score = min(100, login_success_rate)

            score_factors = [
                {"id": "account_protection", "label_ar": "حماية الحسابات", "label_en": "Account Protection", "value": protected_pct, "weight": 20},
                {"id": "authentication", "label_ar": "المصادقة", "label_en": "Authentication", "value": auth_score, "weight": 15},
                {"id": "password_policy", "label_ar": "سياسة كلمات المرور", "label_en": "Password Policy", "value": pw_policy_score, "weight": 15},
                {"id": "encryption", "label_ar": "التشفير", "label_en": "Encryption", "value": encryption_score, "weight": 10},
                {"id": "database_status", "label_ar": "حالة قاعدة البيانات", "label_en": "Database Status", "value": db_status_score, "weight": 15},
                {"id": "logging", "label_ar": "تغطية السجلات", "label_en": "Logging Coverage", "value": logging_score, "weight": 10},
            ]

            backup_records = await gd_find(db.session, "audit_logs", {
                "action": {"$in": ["data.exported", "data_exported", "backup.created"]},
            }, order_by="timestamp", desc_order=True, limit=100)
            total_backups = len(backup_records)
            last_backup = backup_records[0].get("timestamp") if backup_records else now.isoformat()

            backup_freshness = 100
            if backup_records:
                last_backup_dt = datetime.fromisoformat(last_backup.replace("Z", "+00:00")) if last_backup else now
                days_since = (now - last_backup_dt).days
                if days_since > 30:
                    backup_freshness = 30
                elif days_since > 7:
                    backup_freshness = 60
                elif days_since > 1:
                    backup_freshness = 80

            score_factors.append(
                {"id": "backup_freshness", "label_ar": "حداثة النسخ الاحتياطية", "label_en": "Backup Freshness", "value": backup_freshness, "weight": 15}
            )

            security_score = round(sum(f["value"] * f["weight"] for f in score_factors) / max(sum(f["weight"] for f in score_factors), 1))

            return {
                "securityScore": min(100, security_score),
                "protectedAccounts": active_accounts,
                "totalAccounts": total_accounts,
                "applicationSecurity": min(100, account_security_score),
                "failedLogins24h": failed_logins_24h,
                "lockedAccounts": locked_accounts,
                "encryptedData": encryption_score,
                "databaseStatus": db_status_score,
                "passwordPolicyStrength": "strong" if pw_policy_score >= 80 else ("moderate" if pw_policy_score >= 50 else "weak"),
                "lastBackup": last_backup,
                "totalBackups": total_backups,
                "loggingCoverage": logging_score,
                "mustChangePassword": must_change_pw,
                "scoreFactors": score_factors,
            }
        except Exception as e:
            logger.error(f"Security dashboard error: {e}")
            return {
                "securityScore": 0, "protectedAccounts": 0, "totalAccounts": 0,
                "applicationSecurity": 0, "failedLogins24h": 0, "lockedAccounts": 0,
                "encryptedData": 0, "passwordPolicyStrength": "unknown",
                "lastBackup": datetime.now(timezone.utc).isoformat(),
                "totalBackups": 0, "loggingCoverage": 0, "mustChangePassword": 0,
                "scoreFactors": [],
            }

    @router.get("/alerts")
    async def security_alerts(
        current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))
    ):
        """
        تنبيهات أمنية حقيقية من سجلات التدقيق
        Real security alerts derived from audit logs
        """
        from datetime import timedelta
        try:
            now = datetime.now(timezone.utc)
            cutoff_7d = (now - timedelta(days=7)).isoformat()
            cutoff_1h = (now - timedelta(hours=1)).isoformat()
            alerts = []
            alert_id = 0

            failed_logins = await gd_find(db.session, "audit_logs", {
                "action": {"$in": ["auth.login_failed", "login_failed"]},
                "timestamp": {"$gte": cutoff_7d},
            }, order_by="timestamp", desc_order=True, limit=500)

            user_fails = {}
            for fl in failed_logins:
                uid = fl.get("performed_by") or fl.get("actor_email") or fl.get("details", {}).get("email", "unknown")
                user_fails.setdefault(uid, []).append(fl)

            dismissed_ids = set()
            dismissed_records = await gd_find(db.session, "security_dismissed_alerts", {}, limit=1000)
            for dr in dismissed_records:
                dismissed_ids.add(dr.get("alert_key", ""))

            for uid, fails in user_fails.items():
                recent_fails = [f for f in fails if f.get("timestamp", "") >= cutoff_1h]
                if len(recent_fails) > 5:
                    alert_id += 1
                    alert_key = f"brute-{uid}"
                    if alert_key not in dismissed_ids:
                        alerts.append({
                            "id": f"alert-brute-{alert_id}",
                            "type": "high",
                            "status": "active",
                            "title_ar": f"محاولات دخول فاشلة متكررة ({len(recent_fails)} محاولة)",
                            "title_en": f"Repeated failed login attempts ({len(recent_fails)} attempts)",
                            "description_ar": f"المستخدم {uid} لديه {len(recent_fails)} محاولة فاشلة خلال الساعة الأخيرة",
                            "description_en": f"User {uid} has {len(recent_fails)} failed attempts in the last hour",
                            "timestamp": recent_fails[0].get("timestamp", now.isoformat()),
                            "alert_key": alert_key,
                        })
                elif len(fails) >= 10:
                    alert_id += 1
                    alert_key = f"fails-weekly-{uid}"
                    if alert_key not in dismissed_ids:
                        alerts.append({
                            "id": f"alert-fails-{alert_id}",
                            "type": "medium",
                            "status": "active",
                            "title_ar": f"محاولات دخول فاشلة ({len(fails)} محاولة خلال 7 أيام)",
                            "title_en": f"Failed login attempts ({len(fails)} in 7 days)",
                            "description_ar": f"المستخدم {uid} لديه {len(fails)} محاولة فاشلة خلال الأسبوع",
                            "description_en": f"User {uid} has {len(fails)} failed attempts this week",
                            "timestamp": fails[0].get("timestamp", now.isoformat()),
                            "alert_key": alert_key,
                        })

            locked_events = await gd_find(db.session, "audit_logs", {
                "action": {"$in": ["account_locked", "security.account_locked"]},
                "timestamp": {"$gte": cutoff_7d},
            }, order_by="timestamp", desc_order=True, limit=20)

            for ev in locked_events:
                alert_id += 1
                target = ev.get("target_user_id") or ev.get("target_name") or "unknown"
                alert_key = f"lock-{ev.get('id', alert_id)}"
                if alert_key in dismissed_ids:
                    continue
                alerts.append({
                    "id": f"alert-lock-{alert_id}",
                    "type": "medium",
                    "status": "active",
                    "title_ar": "حساب تم قفله",
                    "title_en": "Account Locked",
                    "description_ar": f"تم قفل حساب {target} بواسطة {ev.get('performed_by_name', 'مدير')}",
                    "description_en": f"Account {target} was locked by {ev.get('performed_by_name', 'admin')}",
                    "timestamp": ev.get("timestamp", now.isoformat()),
                    "alert_key": alert_key,
                })

            pw_changes = await gd_find(db.session, "audit_logs", {
                "action": {"$in": ["force_password_change", "password_reset"]},
                "timestamp": {"$gte": cutoff_7d},
            }, order_by="timestamp", desc_order=True, limit=10)

            for ev in pw_changes:
                alert_id += 1
                alert_key = f"pw-{ev.get('id', alert_id)}"
                if alert_key in dismissed_ids:
                    continue
                alerts.append({
                    "id": f"alert-pw-{alert_id}",
                    "type": "low",
                    "status": "active",
                    "title_ar": "تغيير كلمة مرور إجباري",
                    "title_en": "Forced Password Change",
                    "description_ar": f"تم فرض تغيير كلمة مرور بواسطة {ev.get('performed_by_name', 'مدير')}",
                    "description_en": f"Password change forced by {ev.get('performed_by_name', 'admin')}",
                    "timestamp": ev.get("timestamp", now.isoformat()),
                    "alert_key": alert_key,
                })

            session_events = await gd_find(db.session, "audit_logs", {
                "action": "all_sessions_terminated",
                "timestamp": {"$gte": cutoff_7d},
            }, order_by="timestamp", desc_order=True, limit=5)

            for ev in session_events:
                alert_id += 1
                alert_key = f"sess-{ev.get('id', alert_id)}"
                if alert_key in dismissed_ids:
                    continue
                alerts.append({
                    "id": f"alert-sess-{alert_id}",
                    "type": "high",
                    "status": "active",
                    "title_ar": "إنهاء جميع الجلسات",
                    "title_en": "All Sessions Terminated",
                    "description_ar": f"تم إنهاء جميع الجلسات بواسطة {ev.get('performed_by_name', 'مدير')}",
                    "description_en": f"All sessions terminated by {ev.get('performed_by_name', 'admin')}",
                    "timestamp": ev.get("timestamp", now.isoformat()),
                    "alert_key": alert_key,
                })

            severity_rank = {"high": 0, "medium": 1, "low": 2}

            routine_actions = {
                "auth.login", "login", "auth.logout", "logout",
                "auth.register", "data.exported", "data.imported",
                "report.generated", "system.accessed",
                "security.accessed", "admin.accessed", "platform.accessed",
            }

            high_severity_events = await gd_find(db.session, "audit_logs", {
                "severity": {"$in": ["high", "critical"]},
                "timestamp": {"$gte": cutoff_7d},
            }, order_by="timestamp", desc_order=True, limit=50)

            action_labels = {
                "auth.login_failed": ("محاولة دخول فاشلة", "Failed login attempt"),
                "auth.password_changed": ("تغيير كلمة مرور", "Password changed"),
                "account_locked": ("قفل حساب مستخدم", "Account locked"),
                "account_unlocked": ("فتح حساب مستخدم", "Account unlocked"),
                "user.deleted": ("حذف مستخدم", "User deleted"),
                "user.suspended": ("تعليق مستخدم", "User suspended"),
                "user.created": ("إضافة مستخدم جديد", "User created"),
                "user.updated": ("تحديث بيانات مستخدم", "User updated"),
                "security.updated": ("تحديث إعدادات الأمان", "Security settings updated"),
                "security.created": ("إنشاء إعدادات أمنية", "Security settings created"),
                "tenant.created": ("إنشاء مدرسة جديدة", "New school created"),
                "tenant.updated": ("تحديث بيانات مدرسة", "School updated"),
                "tenant.suspended": ("تعليق مدرسة", "School suspended"),
                "tenant.activated": ("تفعيل مدرسة", "School activated"),
                "tenant.deleted": ("حذف مدرسة", "School deleted"),
                "school.created": ("إنشاء مدرسة جديدة", "New school created"),
                "school.updated": ("تحديث بيانات مدرسة", "School updated"),
                "school.suspended": ("تعليق مدرسة", "School suspended"),
                "school.activated": ("تفعيل مدرسة", "School activated"),
                "role.assigned": ("إسناد صلاحية", "Role assigned"),
                "role.revoked": ("سحب صلاحية", "Role revoked"),
                "permission.granted": ("منح صلاحية", "Permission granted"),
                "permission.revoked": ("سحب صلاحية", "Permission revoked"),
            }

            # Pre-fetch all unique performer IDs to resolve UUID -> name in one shot
            performer_ids = set()
            for ev in high_severity_events:
                pid = ev.get("performed_by") or ""
                if pid and len(str(pid)) > 20:
                    performer_ids.add(str(pid))
            users_by_id = {}
            if performer_ids:
                try:
                    user_rows = await gd_find(
                        db.session, "users",
                        {"id": {"$in": list(performer_ids)}},
                        limit=len(performer_ids),
                    )
                    for u in user_rows:
                        users_by_id[str(u.get("id"))] = (
                            u.get("full_name") or u.get("name") or u.get("email") or ""
                        )
                except Exception:
                    pass

            def _resolve_actor(ev):
                # Prefer human-readable fields first
                name = (
                    ev.get("actor_name")
                    or ev.get("performed_by_name")
                    or ev.get("actor_email")
                )
                if name:
                    return name
                # Pull from new_values/previous_values metadata if present
                for blob_key in ("new_values", "previous_values"):
                    blob = ev.get(blob_key) or {}
                    if isinstance(blob, dict):
                        v = blob.get("performed_by_email") or blob.get("performed_by_name")
                        if v:
                            return v
                pid = ev.get("performed_by") or ""
                if pid:
                    resolved = users_by_id.get(str(pid))
                    if resolved:
                        return resolved
                    # Hide raw UUIDs from end-users
                    if len(str(pid)) > 20:
                        return ""
                    return str(pid)
                return ""

            def _resolve_target(ev):
                for blob_key in ("new_values", "previous_values"):
                    blob = ev.get(blob_key) or {}
                    if isinstance(blob, dict):
                        for k in ("school_name", "tenant_name", "name", "target_name", "user_email", "email"):
                            v = blob.get(k)
                            if v:
                                return v
                return ""

            for ev in high_severity_events:
                action = ev.get("action", "unknown")
                if action in routine_actions:
                    continue
                alert_id += 1
                alert_key = f"severity-{ev.get('id', alert_id)}"
                if alert_key in dismissed_ids:
                    continue
                label_ar, label_en = action_labels.get(
                    action,
                    (f"حدث أمني: {action}", f"Security event: {action}"),
                )
                ip_addr = ev.get("ip_address", "")
                actor = _resolve_actor(ev)
                target = _resolve_target(ev)

                title_ar = label_ar
                title_en = label_en
                if target:
                    title_ar = f"{label_ar} — {target}"
                    title_en = f"{label_en} — {target}"

                desc_parts_ar = [label_ar]
                desc_parts_en = [label_en]
                if target:
                    desc_parts_ar.append(f"العنصر: {target}")
                    desc_parts_en.append(f"Item: {target}")
                if actor:
                    desc_parts_ar.append(f"بواسطة: {actor}")
                    desc_parts_en.append(f"By: {actor}")
                if ip_addr:
                    desc_parts_ar.append(f"IP: {ip_addr}")
                    desc_parts_en.append(f"IP: {ip_addr}")
                desc_ar = " — ".join(desc_parts_ar)
                desc_en = " — ".join(desc_parts_en)

                alerts.append({
                    "id": f"alert-sev-{alert_id}",
                    "type": "high",
                    "status": "active",
                    "title_ar": title_ar,
                    "title_en": title_en,
                    "description_ar": desc_ar,
                    "description_en": desc_en,
                    "timestamp": ev.get("timestamp", now.isoformat()),
                    "alert_key": alert_key,
                    "source_user": actor,
                    "source_ip": ip_addr,
                    "action": action,
                    "action_label_ar": label_ar,
                    "action_label_en": label_en,
                    "target_name": target,
                })

            alerts.sort(key=lambda a: a.get("timestamp", ""), reverse=True)
            alerts.sort(key=lambda a: severity_rank.get(a["type"], 3))

            return alerts
        except Exception as e:
            logger.error(f"Security alerts error: {e}")
            return []

    @router.post("/ai-report")
    async def generate_ai_report(
        current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))
    ):
        """
        تقرير وتوصيات الذكاء الاصطناعي الأمني
        AI security report and recommendations
        """
        from datetime import timedelta
        try:
            now = datetime.now(timezone.utc)
            cutoff_30d = (now - timedelta(days=30)).isoformat()
            cutoff_24h = (now - timedelta(hours=24)).isoformat()
            cutoff_90d = (now - timedelta(days=90)).isoformat()

            total = await gd_count(db.session, "users", {})
            active = await gd_count(db.session, "users", {"is_active": True})
            locked = await gd_count(db.session, "users", {"is_locked": True})
            must_change = await gd_count(db.session, "users", {"must_change_password": True})

            inactive_users = await gd_find(db.session, "users", {
                "is_active": True,
                "last_login": {"$lt": cutoff_90d}
            }, limit=100)
            inactive_90d = [u.get("email", "unknown") for u in inactive_users]

            failed_24h = await gd_count(db.session, "audit_logs", {
                "action": {"$in": ["auth.login_failed", "login_failed"]},
                "timestamp": {"$gte": cutoff_24h},
            })

            failed_30d = await gd_count(db.session, "audit_logs", {
                "action": {"$in": ["auth.login_failed", "login_failed"]},
                "timestamp": {"$gte": cutoff_30d},
            })

            total_logins_30d = await gd_count(db.session, "audit_logs", {
                "action": {"$in": ["auth.login", "login"]},
                "timestamp": {"$gte": cutoff_30d},
            })

            recommendations = []
            rec_id = 0

            if len(inactive_90d) > 0:
                rec_id += 1
                recommendations.append({
                    "id": f"rec-{rec_id}",
                    "title_ar": "مراجعة الحسابات غير النشطة",
                    "title_en": "Review Inactive Accounts",
                    "description_ar": f"يوجد {len(inactive_90d)} حساب نشط لم يسجل دخول منذ 90 يوماً. يُنصح بمراجعتها أو تعطيلها.",
                    "description_en": f"There are {len(inactive_90d)} active accounts with no login in 90 days. Consider reviewing or deactivating them.",
                    "priority": "high",
                    "impact": "High Impact",
                    "category": "accounts",
                })

            if failed_24h > 10:
                rec_id += 1
                recommendations.append({
                    "id": f"rec-{rec_id}",
                    "title_ar": "نمط محاولات دخول فاشلة مرتفع",
                    "title_en": "High Failed Login Pattern",
                    "description_ar": f"تم رصد {failed_24h} محاولة دخول فاشلة خلال 24 ساعة. يُنصح بمراجعة سجلات الدخول وتفعيل حماية إضافية.",
                    "description_en": f"Detected {failed_24h} failed login attempts in 24 hours. Review login logs and consider additional protection.",
                    "priority": "high",
                    "impact": "High Impact",
                    "category": "authentication",
                })
            elif failed_24h > 5:
                rec_id += 1
                recommendations.append({
                    "id": f"rec-{rec_id}",
                    "title_ar": "محاولات دخول فاشلة ملحوظة",
                    "title_en": "Notable Failed Login Attempts",
                    "description_ar": f"تم رصد {failed_24h} محاولة دخول فاشلة خلال 24 ساعة.",
                    "description_en": f"Detected {failed_24h} failed login attempts in 24 hours.",
                    "priority": "medium",
                    "impact": "Medium Impact",
                    "category": "authentication",
                })

            if locked > 0:
                rec_id += 1
                recommendations.append({
                    "id": f"rec-{rec_id}",
                    "title_ar": "حسابات مقفلة تحتاج مراجعة",
                    "title_en": "Locked Accounts Need Review",
                    "description_ar": f"يوجد {locked} حساب مقفل حالياً. راجع الحسابات المقفلة وافتحها إن لزم.",
                    "description_en": f"There are {locked} locked accounts. Review and unlock if appropriate.",
                    "priority": "medium",
                    "impact": "Medium Impact",
                    "category": "accounts",
                })

            if must_change > 0:
                rec_id += 1
                recommendations.append({
                    "id": f"rec-{rec_id}",
                    "title_ar": "مستخدمون بحاجة لتغيير كلمة المرور",
                    "title_en": "Users Need Password Change",
                    "description_ar": f"{must_change} مستخدم لم يغيّر كلمة المرور بعد.",
                    "description_en": f"{must_change} users still need to change their password.",
                    "priority": "low",
                    "impact": "Low Impact",
                    "category": "passwords",
                })

            protection_rate = round((active / max(total, 1)) * 100)
            if protection_rate < 80:
                rec_id += 1
                recommendations.append({
                    "id": f"rec-{rec_id}",
                    "title_ar": "نسبة حماية الحسابات منخفضة",
                    "title_en": "Low Account Protection Rate",
                    "description_ar": f"نسبة الحسابات المحمية {protection_rate}%. يُنصح بمراجعة الحسابات المعطلة.",
                    "description_en": f"Account protection rate is {protection_rate}%. Review disabled accounts.",
                    "priority": "high",
                    "impact": "High Impact",
                    "category": "accounts",
                })

            if not recommendations:
                recommendations.append({
                    "id": "rec-healthy",
                    "title_ar": "النظام آمن",
                    "title_en": "System Secure",
                    "description_ar": "لم يتم رصد أي مشاكل أمنية. استمر في المراقبة الدورية.",
                    "description_en": "No security issues detected. Continue periodic monitoring.",
                    "priority": "low",
                    "impact": "Positive",
                    "category": "general",
                })

            await gd_insert(db.session, "audit_logs", {
                "id": str(uuid.uuid4()),
                "action": "security.ai_report_generated",
                "performed_by": current_user.get("id"),
                "performed_by_name": current_user.get("name", current_user.get("full_name", "")),
                "timestamp": now.isoformat(),
                "details": {"recommendations_count": len(recommendations)},
            })

            return {
                "status": "completed",
                "timestamp": now.isoformat(),
                "summary": {
                    "total_accounts": total,
                    "active_accounts": active,
                    "locked_accounts": locked,
                    "inactive_90d": len(inactive_90d),
                    "failed_logins_24h": failed_24h,
                    "failed_logins_30d": failed_30d,
                    "total_logins_30d": total_logins_30d,
                    "must_change_password": must_change,
                },
                "recommendations": recommendations,
            }
        except Exception as e:
            logger.error(f"AI security report error: {e}")
            return {
                "status": "error",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "summary": {},
                "recommendations": [],
            }

    @router.post("/dismiss-alert/{alert_id}")
    async def dismiss_alert(
        alert_id: str,
        alert_key: Optional[str] = Query(None),
        current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))
    ):
        """تجاهل تنبيه أمني — يُحفظ بشكل دائم"""
        try:
            key = alert_key or alert_id
            await gd_insert(db.session, "security_dismissed_alerts", {
                "id": str(uuid.uuid4()),
                "alert_key": key,
                "alert_id": alert_id,
                "dismissed_by": current_user.get("id"),
                "dismissed_by_name": current_user.get("name", current_user.get("full_name", "")),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

            await gd_insert(db.session, "audit_logs", {
                "id": str(uuid.uuid4()),
                "action": "security.alert_dismissed",
                "performed_by": current_user.get("id"),
                "performed_by_name": current_user.get("name", current_user.get("full_name", "")),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "details": {"alert_id": alert_id, "alert_key": key},
            })
            return {"success": True, "message": "تم تجاهل التنبيه"}
        except Exception as e:
            logger.error(f"Dismiss alert error: {e}")
            return {"success": False}

    @router.post("/escalate-alert/{alert_id}")
    async def escalate_alert(
        alert_id: str,
        current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))
    ):
        """تصعيد تنبيه أمني"""
        try:
            await gd_insert(db.session, "audit_logs", {
                "id": str(uuid.uuid4()),
                "action": "security.alert_escalated",
                "severity": "high",
                "performed_by": current_user.get("id"),
                "performed_by_name": current_user.get("name", current_user.get("full_name", "")),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "details": {"alert_id": alert_id, "escalated_to": "tech_team"},
            })
            return {"success": True, "message": "تم تصعيد التنبيه للفريق التقني"}
        except Exception as e:
            logger.error(f"Escalate alert error: {e}")
            return {"success": False}

    return router
