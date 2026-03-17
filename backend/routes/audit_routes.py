"""
Audit Logs Routes - مسارات سجلات التدقيق
APIs for audit logs management
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timezone, timedelta
import logging

logger = logging.getLogger("nassaq.audit")


class AuditLog(BaseModel):
    """سجل تدقيق"""
    id: str
    action: str
    action_ar: str = ""
    target_type: Optional[str] = None
    target_id: Optional[str] = None
    target_name: Optional[str] = None
    performed_by: str
    performed_by_name: str
    performed_by_role: str = ""
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    timestamp: str
    details: Optional[dict] = None
    status: str = "success"  # success, failed, pending


class AuditLogsResponse(BaseModel):
    """استجابة سجلات التدقيق"""
    logs: List[AuditLog]
    total: int
    page: int
    limit: int
    total_pages: int


def setup_audit_routes(db, get_current_user, require_roles, UserRole):
    """Setup audit routes with database and auth dependencies"""
    
    router = APIRouter(prefix="/audit", tags=["Audit Logs"])
    
    # Action translations
    ACTION_TRANSLATIONS = {
        "login": "تسجيل دخول",
        "logout": "تسجيل خروج",
        "login_failed": "فشل تسجيل الدخول",
        "account_locked": "قفل حساب",
        "account_unlocked": "فتح حساب",
        "password_changed": "تغيير كلمة المرور",
        "force_password_change": "فرض تغيير كلمة المرور",
        "all_sessions_terminated": "إنهاء جميع الجلسات",
        "user_created": "إنشاء مستخدم",
        "user_updated": "تحديث مستخدم",
        "user_deleted": "حذف مستخدم",
        "school_created": "إنشاء مدرسة",
        "school_updated": "تحديث مدرسة",
        "school_suspended": "تعليق مدرسة",
        "school_activated": "تفعيل مدرسة",
        "ai_enabled": "تفعيل الذكاء الاصطناعي",
        "ai_disabled": "إيقاف الذكاء الاصطناعي",
        "settings_updated": "تحديث الإعدادات",
        "terms_updated": "تحديث الشروط والأحكام",
        "privacy_updated": "تحديث سياسة الخصوصية",
        "maintenance_enabled": "تفعيل وضع الصيانة",
        "maintenance_disabled": "إيقاف وضع الصيانة",
        "registration_opened": "فتح التسجيل",
        "registration_closed": "إغلاق التسجيل",
        "schedule_generated": "إنشاء جدول",
        "attendance_recorded": "تسجيل حضور",
        "grade_recorded": "تسجيل درجة",
        "message_sent": "إرسال رسالة",
        "notification_sent": "إرسال إشعار",
        "data_exported": "تصدير بيانات",
        "data_imported": "استيراد بيانات",
        "security_scan": "فحص أمني",
        "api_call": "طلب API",
    }
    
    @router.get("/logs", response_model=AuditLogsResponse)
    async def get_audit_logs(
        page: int = Query(1, ge=1),
        limit: int = Query(50, ge=1, le=200),
        action: Optional[str] = None,
        user_id: Optional[str] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        search: Optional[str] = None,
        current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))
    ):
        """
        جلب سجلات التدقيق
        Get audit logs with pagination and filtering
        """
        try:
            # Build query
            query = {}
            
            if action:
                query["action"] = action
            
            if user_id:
                query["performed_by"] = user_id
            
            if from_date:
                query["timestamp"] = {"$gte": from_date}
            
            if to_date:
                if "timestamp" in query:
                    query["timestamp"]["$lte"] = to_date
                else:
                    query["timestamp"] = {"$lte": to_date}
            
            if search:
                query["$or"] = [
                    {"performed_by_name": {"$regex": search, "$options": "i"}},
                    {"action": {"$regex": search, "$options": "i"}},
                    {"target_name": {"$regex": search, "$options": "i"}},
                ]
            
            # Get total count
            total = await db.audit_logs.count_documents(query)
            
            # Get paginated results
            skip = (page - 1) * limit
            logs_cursor = db.audit_logs.find(query).sort("timestamp", -1).skip(skip).limit(limit)
            logs_list = await logs_cursor.to_list(limit)
            
            # Transform logs
            logs = []
            for log in logs_list:
                action_key = log.get("action", "")
                logs.append(AuditLog(
                    id=str(log.get("id", log.get("_id", ""))),
                    action=action_key,
                    action_ar=ACTION_TRANSLATIONS.get(action_key, action_key),
                    target_type=log.get("target_type"),
                    target_id=log.get("target_id", log.get("target_user_id")),
                    target_name=log.get("target_name"),
                    performed_by=log.get("performed_by", ""),
                    performed_by_name=log.get("performed_by_name", "غير معروف"),
                    performed_by_role=log.get("performed_by_role", ""),
                    ip_address=log.get("ip_address"),
                    user_agent=log.get("user_agent"),
                    timestamp=log.get("timestamp", ""),
                    details=log.get("details"),
                    status=log.get("status", "success"),
                ))
            
            total_pages = (total + limit - 1) // limit
            
            return AuditLogsResponse(
                logs=logs,
                total=total,
                page=page,
                limit=limit,
                total_pages=total_pages
            )
            
        except Exception as e:
            logger.error(f"Error getting audit logs: {e}")
            return AuditLogsResponse(logs=[], total=0, page=1, limit=limit, total_pages=0)
    
    @router.get("/actions")
    async def get_available_actions(
        current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))
    ):
        """
        جلب قائمة الإجراءات المتاحة للفلترة
        Get list of available actions for filtering
        """
        return [
            {"id": key, "name_ar": value, "name_en": key.replace("_", " ").title()}
            for key, value in ACTION_TRANSLATIONS.items()
        ]
    
    @router.post("/log")
    async def create_audit_log(
        action: str,
        target_type: Optional[str] = None,
        target_id: Optional[str] = None,
        target_name: Optional[str] = None,
        details: Optional[dict] = None,
        current_user: dict = Depends(get_current_user)
    ):
        """
        إنشاء سجل تدقيق جديد (داخلي)
        Create a new audit log entry (internal use)
        """
        try:
            import uuid
            log_entry = {
                "id": str(uuid.uuid4()),
                "action": action,
                "target_type": target_type,
                "target_id": target_id,
                "target_name": target_name,
                "performed_by": current_user.get("id"),
                "performed_by_name": current_user.get("name", current_user.get("full_name", "غير معروف")),
                "performed_by_role": current_user.get("role", ""),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "details": details,
                "status": "success"
            }
            
            await db.audit_logs.insert_one(log_entry)
            return {"success": True, "log_id": log_entry["id"]}
            
        except Exception as e:
            logger.error(f"Error creating audit log: {e}")
            return {"success": False, "error": "حدث خطأ أثناء إنشاء سجل التدقيق"}
    
    @router.get("/stats")
    async def get_audit_stats(
        current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))
    ):
        """
        إحصائيات سجلات التدقيق
        Get audit log statistics
        """
        try:
            now = datetime.now(timezone.utc)
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
            week_start = (now - timedelta(days=7)).isoformat()
            
            total_logs = await db.audit_logs.count_documents({})
            logs_today = await db.audit_logs.count_documents({"timestamp": {"$gte": today_start}})
            logs_this_week = await db.audit_logs.count_documents({"timestamp": {"$gte": week_start}})
            
            # Count by action type
            login_attempts = await db.audit_logs.count_documents({"action": {"$in": ["login", "login_failed"]}})
            security_actions = await db.audit_logs.count_documents({
                "action": {"$in": ["account_locked", "account_unlocked", "force_password_change", "all_sessions_terminated"]}
            })
            
            return {
                "total_logs": total_logs,
                "logs_today": logs_today,
                "logs_this_week": logs_this_week,
                "login_attempts": login_attempts,
                "security_actions": security_actions,
            }
            
        except Exception as e:
            logger.error(f"Error getting audit stats: {e}")
            return {
                "total_logs": 0,
                "logs_today": 0,
                "logs_this_week": 0,
                "login_attempts": 0,
                "security_actions": 0,
            }

    @router.get("/export")
    async def export_audit_logs(
        format: str = Query("json", enum=["json", "csv"]),
        action: Optional[str] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        limit: int = 1000,
        current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))
    ):
        """تصدير سجلات التدقيق"""
        try:
            query = {}
            if action:
                query["action"] = action
            if from_date:
                query.setdefault("timestamp", {})["$gte"] = from_date
            if to_date:
                query.setdefault("timestamp", {})["$lte"] = to_date

            logs = await db.audit_logs.find(query, {"_id": 0}).sort("timestamp", -1).limit(limit).to_list(limit)

            if format == "csv":
                if not logs:
                    return {"data": "", "format": "csv", "total": 0}
                import csv
                import io as csv_io
                output = csv_io.StringIO()
                writer = csv.DictWriter(output, fieldnames=logs[0].keys())
                writer.writeheader()
                for log in logs:
                    row = {}
                    for k, v in log.items():
                        row[k] = str(v) if isinstance(v, dict) else v
                    writer.writerow(row)
                return {"data": output.getvalue(), "format": "csv", "total": len(logs)}

            return {"data": logs, "format": "json", "total": len(logs)}
        except Exception as e:
            logger.error(f"Audit export error: {e}")
            return {"data": [], "format": format, "total": 0, "error": "حدث خطأ أثناء تصدير السجلات"}

    @router.get("/user/{user_id}")
    async def get_user_audit_trail(
        user_id: str,
        limit: int = 50,
        current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))
    ):
        """سجل تدقيق مستخدم معين"""
        logs = await db.audit_logs.find(
            {"$or": [{"performed_by": user_id}, {"target_id": user_id}, {"actor_id": user_id}]},
            {"_id": 0}
        ).sort("timestamp", -1).limit(limit).to_list(limit)

        for log in logs:
            action_key = log.get("action", "")
            log["action_ar"] = ACTION_TRANSLATIONS.get(action_key, action_key)

        return {"logs": logs, "total": len(logs), "user_id": user_id}

    @router.delete("/cleanup")
    async def cleanup_old_audit_logs(
        days: int = Query(365, ge=30),
        current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))
    ):
        """حذف سجلات التدقيق القديمة"""
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        result = await db.audit_logs.delete_many({"timestamp": {"$lt": cutoff}})
        return {
            "message": f"تم حذف {result.deleted_count} سجل أقدم من {days} يوم",
            "deleted_count": result.deleted_count
        }

    return router


# Alias for backwards compatibility
def create_audit_router(db, get_current_user, require_roles, UserRole):
    """Backwards compatible alias"""
    return setup_audit_routes(db, get_current_user, require_roles, UserRole)
