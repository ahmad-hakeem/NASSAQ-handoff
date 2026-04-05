"""
Audit Logs Routes - مسارات سجلات التدقيق
APIs for audit logs management
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone, timedelta
import logging

logger = logging.getLogger("nassaq.audit")


class DeviceInfo(BaseModel):
    browser: str = "غير معروف"
    os: str = "غير معروف"
    device_type: str = "غير معروف"
    raw: str = ""


class AuditLog(BaseModel):
    id: str
    action: str
    action_ar: str = ""
    severity: str = "low"
    # Actor info
    performed_by: Optional[str] = None
    actor_name: Optional[str] = None
    actor_role: Optional[str] = None
    actor_email: Optional[str] = None
    # Target
    entity_type: Optional[str] = None
    entity_id: Optional[str] = None
    target_type: Optional[str] = None
    target_id: Optional[str] = None
    target_name: Optional[str] = None
    # Network / device
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    device_info: Optional[DeviceInfo] = None
    # Metadata
    tenant_id: Optional[str] = None
    timestamp: str
    details: Optional[dict] = None
    status: str = "success"


class AuditLogsResponse(BaseModel):
    logs: List[AuditLog]
    total: int
    page: int
    limit: int
    total_pages: int


# Full action translations (Arabic)
ACTION_TRANSLATIONS: Dict[str, str] = {
    # Auth
    "auth.login": "تسجيل دخول",
    "auth.logout": "تسجيل خروج",
    "auth.login_failed": "فشل تسجيل الدخول",
    "auth.register": "تسجيل حساب جديد",
    "auth.password_changed": "تغيير كلمة المرور",
    "auth.password_reset": "إعادة تعيين كلمة المرور",
    # User
    "user.created": "إنشاء مستخدم",
    "user.updated": "تحديث مستخدم",
    "user.deleted": "حذف مستخدم",
    "user.suspended": "تعليق مستخدم",
    "user.activated": "تفعيل مستخدم",
    "user.role_assigned": "تعيين دور",
    "user.role_removed": "إزالة دور",
    # Tenant / School
    "tenant.created": "إنشاء مؤسسة",
    "tenant.updated": "تحديث مؤسسة",
    "tenant.suspended": "تعليق مؤسسة",
    "tenant.activated": "تفعيل مؤسسة",
    "tenant.deleted": "حذف مؤسسة",
    "school.created": "إنشاء مدرسة",
    "school.updated": "تحديث مدرسة",
    "school.suspended": "تعليق مدرسة",
    "school.activated": "تفعيل مدرسة",
    # Students / Teachers
    "student.created": "إضافة طالب",
    "student.updated": "تحديث طالب",
    "student.deleted": "حذف طالب",
    "teacher.created": "إضافة معلم",
    "teacher.updated": "تحديث معلم",
    "teacher.deleted": "حذف معلم",
    "class.created": "إنشاء فصل",
    "class.updated": "تحديث فصل",
    # Academic
    "academic.grade_recorded": "تسجيل درجة",
    "academic.grade_updated": "تحديث درجة",
    "academic.assessment_created": "إنشاء تقييم",
    "academic.assessment_published": "نشر تقييم",
    "academic.report_card_generated": "إنشاء كشف درجات",
    "grade.created": "تسجيل درجة",
    "grade.updated": "تحديث درجة",
    "assessment.created": "إنشاء تقييم",
    # Attendance
    "attendance.recorded": "تسجيل حضور",
    "attendance.bulk_recorded": "تسجيل حضور جماعي",
    "attendance.excuse_submitted": "تقديم عذر",
    "attendance.excuse_approved": "قبول عذر",
    "attendance.created": "تسجيل حضور",
    "attendance.updated": "تحديث حضور",
    # Behaviour
    "behaviour.note_created": "تسجيل ملاحظة سلوكية",
    "behaviour.action_created": "إجراء تأديبي",
    "behaviour.action_updated": "تحديث إجراء تأديبي",
    "behaviour.recorded": "تسجيل سلوك",
    "behaviour.created": "تسجيل سلوك",
    # Schedule
    "schedule.created": "إنشاء جدول",
    "schedule.generated": "توليد جدول",
    "schedule.published": "نشر جدول",
    "schedule.updated": "تحديث جدول",
    # Settings / System
    "settings.updated": "تحديث الإعدادات",
    "settings.created": "إنشاء إعدادات",
    "system.configuration": "إعداد النظام",
    "system.config": "إعداد النظام",
    "platform.updated": "تحديث المنصة",
    "admin.created": "إضافة مسؤول",
    # Data
    "data.exported": "تصدير البيانات",
    "data.imported": "استيراد البيانات",
    "data.bulk_imported": "استيراد جماعي للبيانات",
    "export.accessed": "الوصول للتصدير",
    "import.created": "استيراد ملف",
    "report.generated": "إنشاء تقرير",
    # Registration
    "registration.created": "طلب تسجيل",
    "registration.updated": "تحديث طلب تسجيل",
    # Notifications / Messages
    "notification.created": "إرسال إشعار",
    "message.created": "إرسال رسالة",
    # Security
    "security.updated": "تحديث أمني",
    "security.created": "إجراء أمني",
    # Role / Permission
    "role.created": "إنشاء دور",
    "role.updated": "تحديث دور",
    "permission.created": "منح صلاحية",
    # Sessions
    "session.skill_recorded": "تسجيل مهارة",
    "session.updated": "تحديث جلسة",
    # Invitation
    "invitation.created": "إرسال دعوة",
    # Issues / Product
    "issue.created": "إنشاء بلاغ",
    "issue.updated": "تحديث بلاغ",
    "product.created": "إنشاء منتج",
    "product.updated": "تحديث منتج",
    # Legacy flat keys
    "login": "تسجيل دخول",
    "logout": "تسجيل خروج",
    "login_failed": "فشل تسجيل الدخول",
    "user_created": "إنشاء مستخدم",
    "user_updated": "تحديث مستخدم",
    "user_deleted": "حذف مستخدم",
    "school_created": "إنشاء مدرسة",
    "school_updated": "تحديث مدرسة",
    "school_suspended": "تعليق مدرسة",
    "school_activated": "تفعيل مدرسة",
    "settings_updated": "تحديث الإعدادات",
    "data_exported": "تصدير البيانات",
    "data_imported": "استيراد البيانات",
    "attendance_recorded": "تسجيل حضور",
    "grade_recorded": "تسجيل درجة",
    "schedule_generated": "إنشاء جدول",
    "api_call": "طلب API",
}

ROLE_TRANSLATIONS: Dict[str, str] = {
    "platform_admin": "مدير المنصة",
    "admin": "مدير المدرسة",
    "principal": "مدير",
    "vice_principal": "وكيل",
    "teacher": "معلم",
    "student": "طالب",
    "parent": "ولي أمر",
    "supervisor": "مشرف",
    "coordinator": "منسق",
    "counselor": "مرشد",
    "data_entry": "إدخال بيانات",
}


def _translate(action: str) -> str:
    return ACTION_TRANSLATIONS.get(action, action)


def setup_audit_routes(db, get_current_user, require_roles, UserRole):
    """Setup audit routes with database and auth dependencies"""

    router = APIRouter(prefix="/audit", tags=["Audit Logs"])

    @router.get("/logs", response_model=AuditLogsResponse)
    async def get_audit_logs(
        page: int = Query(1, ge=1),
        limit: int = Query(50, ge=1, le=200),
        action: Optional[str] = None,
        severity: Optional[str] = None,
        user_id: Optional[str] = None,
        entity_type: Optional[str] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        search: Optional[str] = None,
        days: Optional[int] = None,
        current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))
    ):
        """جلب سجلات التدقيق مع الفلترة الكاملة"""
        try:
            query: dict = {}

            if action and action != "all":
                query["action"] = {"$regex": action, "$options": "i"}

            if severity and severity != "all":
                query["severity"] = severity

            if user_id:
                query["performed_by"] = user_id

            if entity_type and entity_type != "all":
                query["entity_type"] = entity_type

            # Date range
            if days:
                cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
                query["timestamp"] = {"$gte": cutoff}
            else:
                ts_filter = {}
                if from_date:
                    ts_filter["$gte"] = from_date
                if to_date:
                    ts_filter["$lte"] = to_date
                if ts_filter:
                    query["timestamp"] = ts_filter

            if search:
                query["$or"] = [
                    {"actor_name": {"$regex": search, "$options": "i"}},
                    {"actor_email": {"$regex": search, "$options": "i"}},
                    {"action": {"$regex": search, "$options": "i"}},
                    {"ip_address": {"$regex": search, "$options": "i"}},
                    {"details.path": {"$regex": search, "$options": "i"}},
                ]

            total = await db.audit_logs.count_documents(query)
            skip = (page - 1) * limit
            logs_cursor = db.audit_logs.find(query).sort("timestamp", -1).skip(skip).limit(limit)
            logs_list = await logs_cursor.to_list(limit)

            logs = []
            for log in logs_list:
                action_key = log.get("action", "")

                # Build DeviceInfo
                di_raw = log.get("device_info") or {}
                di = DeviceInfo(
                    browser=di_raw.get("browser", "غير معروف"),
                    os=di_raw.get("os", "غير معروف"),
                    device_type=di_raw.get("device_type", "غير معروف"),
                    raw=di_raw.get("raw", log.get("user_agent", ""))[:300],
                ) if di_raw or log.get("user_agent") else None

                logs.append(AuditLog(
                    id=str(log.get("id", log.get("_id", ""))),
                    action=action_key,
                    action_ar=_translate(action_key),
                    severity=log.get("severity", "low"),
                    performed_by=log.get("performed_by"),
                    actor_name=log.get("actor_name") or log.get("performed_by_name"),
                    actor_role=log.get("actor_role") or log.get("performed_by_role"),
                    actor_email=log.get("actor_email"),
                    entity_type=log.get("entity_type") or log.get("target_type"),
                    entity_id=log.get("entity_id") or log.get("target_id"),
                    target_type=log.get("target_type"),
                    target_id=log.get("target_id"),
                    target_name=log.get("target_name"),
                    ip_address=log.get("ip_address"),
                    user_agent=log.get("user_agent"),
                    device_info=di,
                    tenant_id=log.get("tenant_id"),
                    timestamp=log.get("timestamp", ""),
                    details=log.get("details"),
                    status=log.get("status", "success"),
                ))

            total_pages = max(1, (total + limit - 1) // limit)
            return AuditLogsResponse(logs=logs, total=total, page=page, limit=limit, total_pages=total_pages)

        except Exception as e:
            logger.error(f"Error getting audit logs: {e}")
            return AuditLogsResponse(logs=[], total=0, page=1, limit=limit, total_pages=0)

    @router.get("/stats")
    async def get_audit_stats(
        days: int = Query(30, ge=1),
        current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))
    ):
        """إحصائيات سجلات التدقيق"""
        try:
            now = datetime.now(timezone.utc)
            cutoff = (now - timedelta(days=days)).isoformat()
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()

            total_events = await db.audit_logs.count_documents({"timestamp": {"$gte": cutoff}})
            today_events = await db.audit_logs.count_documents({"timestamp": {"$gte": today_start}})
            critical_count = await db.audit_logs.count_documents({"timestamp": {"$gte": cutoff}, "severity": "critical"})
            high_count = await db.audit_logs.count_documents({"timestamp": {"$gte": cutoff}, "severity": "high"})
            failed_logins = await db.audit_logs.count_documents({
                "timestamp": {"$gte": cutoff},
                "action": {"$in": ["auth.login_failed", "login_failed"]}
            })
            unique_users_cursor = db.audit_logs.find(
                {"timestamp": {"$gte": cutoff}, "performed_by": {"$ne": None}},
                {"performed_by": 1}
            )
            unique_users_list = await unique_users_cursor.to_list(5000)
            unique_users = len(set(d.get("performed_by") for d in unique_users_list if d.get("performed_by")))

            return {
                "total_events": total_events,
                "today_events": today_events,
                "critical_count": critical_count,
                "high_count": high_count,
                "failed_logins": failed_logins,
                "unique_users": unique_users,
                "period_days": days,
            }

        except Exception as e:
            logger.error(f"Error getting audit stats: {e}")
            return {
                "total_events": 0,
                "today_events": 0,
                "critical_count": 0,
                "high_count": 0,
                "failed_logins": 0,
                "unique_users": 0,
                "period_days": days,
            }

    @router.get("/actions")
    async def get_available_actions(
        current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))
    ):
        """قائمة الإجراءات المتاحة للفلترة"""
        return [
            {"id": k, "name_ar": v}
            for k, v in ACTION_TRANSLATIONS.items()
            if "." in k  # prefer dot-notation keys
        ]

    @router.get("/entity-types")
    async def get_entity_types(
        current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))
    ):
        """أنواع الكيانات المتاحة للفلترة"""
        types = [
            {"id": "auth", "name_ar": "المصادقة"},
            {"id": "user", "name_ar": "المستخدمون"},
            {"id": "tenant", "name_ar": "المؤسسات"},
            {"id": "school", "name_ar": "المدارس"},
            {"id": "student", "name_ar": "الطلاب"},
            {"id": "teacher", "name_ar": "المعلمون"},
            {"id": "attendance", "name_ar": "الحضور"},
            {"id": "grade", "name_ar": "الدرجات"},
            {"id": "schedule", "name_ar": "الجداول"},
            {"id": "settings", "name_ar": "الإعدادات"},
            {"id": "data", "name_ar": "البيانات"},
            {"id": "security", "name_ar": "الأمان"},
            {"id": "system", "name_ar": "النظام"},
        ]
        return types

    @router.post("/log")
    async def create_audit_log(
        action: str,
        target_type: Optional[str] = None,
        target_id: Optional[str] = None,
        target_name: Optional[str] = None,
        details: Optional[dict] = None,
        current_user: dict = Depends(get_current_user)
    ):
        """إنشاء سجل تدقيق يدوي"""
        try:
            import uuid as _uuid
            log_entry = {
                "id": str(_uuid.uuid4()),
                "action": action,
                "target_type": target_type,
                "target_id": target_id,
                "target_name": target_name,
                "performed_by": current_user.get("id"),
                "actor_name": current_user.get("full_name") or current_user.get("name", "غير معروف"),
                "actor_role": current_user.get("role", ""),
                "actor_email": current_user.get("email"),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "details": details,
                "status": "success",
            }
            await db.audit_logs.insert_one(log_entry)
            return {"success": True, "log_id": log_entry["id"]}
        except Exception as e:
            logger.error(f"Error creating audit log: {e}")
            return {"success": False, "error": "حدث خطأ أثناء إنشاء سجل التدقيق"}

    @router.get("/export")
    async def export_audit_logs(
        format: str = Query("json", enum=["json", "csv"]),
        action: Optional[str] = None,
        severity: Optional[str] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        days: Optional[int] = None,
        limit: int = 1000,
        current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))
    ):
        """تصدير سجلات التدقيق"""
        try:
            query: dict = {}
            if action:
                query["action"] = action
            if severity:
                query["severity"] = severity
            if days:
                query["timestamp"] = {"$gte": (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()}
            else:
                if from_date:
                    query.setdefault("timestamp", {})["$gte"] = from_date
                if to_date:
                    query.setdefault("timestamp", {})["$lte"] = to_date

            logs = await db.audit_logs.find(query, {"_id": 0}).sort("timestamp", -1).limit(limit).to_list(limit)

            if format == "csv":
                if not logs:
                    return {"data": "", "format": "csv", "total": 0}
                import csv, io as csv_io
                flat_keys = ["id", "action", "severity", "performed_by", "actor_name",
                             "actor_role", "actor_email", "ip_address", "device_info",
                             "tenant_id", "timestamp", "details"]
                output = csv_io.StringIO()
                writer = csv.DictWriter(output, fieldnames=flat_keys, extrasaction="ignore")
                writer.writeheader()
                for log in logs:
                    row = {}
                    for k in flat_keys:
                        v = log.get(k)
                        row[k] = str(v) if isinstance(v, (dict, list)) else (v or "")
                    writer.writerow(row)
                return {"data": output.getvalue(), "format": "csv", "total": len(logs)}

            return {"data": logs, "format": "json", "total": len(logs)}
        except Exception as e:
            logger.error(f"Audit export error: {e}")
            return {"data": [], "format": format, "total": 0, "error": str(e)}

    @router.get("/user/{user_id}")
    async def get_user_audit_trail(
        user_id: str,
        limit: int = 50,
        current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))
    ):
        """سجل تدقيق مستخدم معين"""
        logs = await db.audit_logs.find(
            {"$or": [{"performed_by": user_id}, {"entity_id": user_id}, {"target_id": user_id}]},
            {"_id": 0}
        ).sort("timestamp", -1).limit(limit).to_list(limit)

        for log in logs:
            log["action_ar"] = _translate(log.get("action", ""))

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


def create_audit_router(db, get_current_user, require_roles, UserRole):
    return setup_audit_routes(db, get_current_user, require_roles, UserRole)
