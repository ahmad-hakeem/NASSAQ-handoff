"""
Audit Logs Routes - مسارات سجلات التدقيق
APIs for audit logs management
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone, timedelta
import hashlib
import json as _json
import logging
from sqlalchemy import text as _sql_text
from engines.sql_utils import gd_find, gd_find_one, gd_insert, gd_insert_many, gd_update_one, gd_update_many, gd_count, gd_delete_one, gd_delete_many, gd_distinct, gd_upsert, _gd_aggregate

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


def setup_audit_routes(db, get_current_user, require_roles, UserRole, require_recent_mfa=None):
    """Setup audit routes with database and auth dependencies.

    ``require_recent_mfa`` is the step-up dependency from
    ``backend.dependencies``; the MFA NDJSON export and the chain
    verification endpoint require a fresh second-factor proof on top of
    the standard platform-admin role gate. When None (e.g. wired by an
    older caller) we fall back to a no-op dep so the routes stay
    operable but log a startup warning.
    """

    # ``require_recent_mfa`` from ``backend.dependencies`` is a *factory*:
    # calling it returns the actual FastAPI dependency callable. Other
    # MFA-protected routers (security_routes, settings_routes) follow the
    # same convention with ``Depends(require_recent_mfa())``. We mirror
    # that here so the step-up check is genuinely enforced rather than
    # silently treated as "depend on the factory itself" (which FastAPI
    # would resolve to the inner function object without ever calling it).
    if require_recent_mfa is None:
        def require_recent_mfa(max_age_seconds: int = 300):  # noqa: ARG001
            async def _noop():
                return None
            return _noop
        logger.warning(
            "setup_audit_routes: require_recent_mfa not supplied — "
            "MFA export endpoint will NOT enforce step-up. Wire it via app.routes."
        )

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

            import re as _re

            if action and action != "all":
                query["action"] = {"$regex": _re.escape(action), "$options": "i"}

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
                safe_search = _re.escape(search)
                query["$or"] = [
                    {"actor_name": {"$regex": safe_search, "$options": "i"}},
                    {"actor_email": {"$regex": safe_search, "$options": "i"}},
                    {"action": {"$regex": safe_search, "$options": "i"}},
                    {"ip_address": {"$regex": safe_search, "$options": "i"}},
                    {"details.path": {"$regex": safe_search, "$options": "i"}},
                ]

            total = await gd_count(db.session, "audit_logs", query)
            skip = (page - 1) * limit
            logs_list = await gd_find(db.session, "audit_logs", query, order_by="timestamp", desc_order=True, offset=skip, limit=limit)

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

            total_events = await gd_count(db.session, "audit_logs", {"timestamp": {"$gte": cutoff}})
            today_events = await gd_count(db.session, "audit_logs", {"timestamp": {"$gte": today_start}})
            critical_count = await gd_count(db.session, "audit_logs", {"timestamp": {"$gte": cutoff}, "severity": "critical"})
            high_count = await gd_count(db.session, "audit_logs", {"timestamp": {"$gte": cutoff}, "severity": "high"})
            failed_logins = await gd_count(db.session, "audit_logs", {
                "timestamp": {"$gte": cutoff},
                "action": {"$in": ["auth.login_failed", "login_failed"]}
            })
            unique_users_list = await gd_find(db.session, "audit_logs", {"timestamp": {"$gte": cutoff}, "performed_by": {"$ne": None}})
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
        current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))
    ):
        """إنشاء سجل تدقيق يدوي — منصة المدير فقط"""
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
            await gd_insert(db.session, "audit_logs", log_entry)
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

            logs = await gd_find(db.session, "audit_logs", query, order_by="timestamp", desc_order=True, limit=limit)

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
            return {"data": [], "format": format, "total": 0, "error": "حدث خطأ أثناء التصدير"}

    @router.get("/user/{user_id}")
    async def get_user_audit_trail(
        user_id: str,
        limit: int = 50,
        current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))
    ):
        """سجل تدقيق مستخدم معين"""
        logs = await gd_find(db.session, "audit_logs", {"$or": [{"performed_by": user_id}, {"entity_id": user_id}, {"target_id": user_id}]}, order_by="timestamp", desc_order=True, limit=limit)

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
        result = await gd_delete_many(db.session, "audit_logs", {"timestamp": {"$lt": cutoff}})
        return {
            "message": f"تم حذف {result} سجل أقدم من {days} يوم",
            "deleted_count": result
        }

    # ------------------------------------------------------------------
    # Task #169 Step 8 — MFA NDJSON export + hash-chain verification.
    #
    # The ``audit_logs`` rows whose ``action`` starts with ``mfa.`` form a
    # per-tenant tamper-evident chain (see migration ``y1z2a3b4c5d6``):
    # the BEFORE INSERT trigger fills ``prev_hash`` and ``row_hash`` for
    # every new row, and the BEFORE UPDATE/DELETE trigger from
    # ``x1y2z3a4b5c6`` rejects mutation of any ``mfa.*`` row.
    #
    # Together these mean an offline auditor (or our own SOC tooling) can
    # take the NDJSON export, re-derive the chain, and detect any
    # back-dated insert / silent rewrite at the database layer — even one
    # made by a privileged operator who has DB credentials.
    # ------------------------------------------------------------------

    def _mfa_chain_payload(row: Dict[str, Any]) -> str:
        """Mirror of audit_logs_mfa_hash_chain_fn() in pure Python.

        Field order and the empty-default for NULLs MUST match the SQL
        ``concat_ws('|', ...)`` exactly, AND the ``details`` / ``timestamp``
        slots must use the raw Postgres ``::text`` representation rather
        than any Python re-formatting (asyncpg's datetime → ISO string is
        not byte-equal to ``timestamp::text``, and ``json.dumps`` is not
        byte-equal to JSONB ``::text``). Callers must therefore SELECT
        ``details::text AS details_text`` and ``timestamp::text AS
        timestamp_text`` and supply those keys here.
        """
        details_text = row.get("details_text")
        if details_text is None:
            details_text = "{}"

        ts_text = row.get("timestamp_text")
        if ts_text is None:
            ts = row.get("timestamp")
            ts_text = ts.isoformat(sep=" ") if isinstance(ts, datetime) else (str(ts) if ts is not None else "")

        parts = [
            row.get("id") or "",
            row.get("action") or "",
            row.get("performed_by") or "",
            row.get("school_id") or "",
            row.get("entity_type") or "",
            row.get("entity_id") or "",
            row.get("ip_address") or "",
            row.get("user_agent") or "",
            details_text,
            ts_text,
            row.get("prev_hash") or ("0" * 64),
        ]
        return "|".join(parts)

    @router.get("/mfa-export")
    async def mfa_audit_export(
        request: Request,
        from_date: Optional[str] = Query(None, description="ISO timestamp lower bound"),
        to_date: Optional[str] = Query(None, description="ISO timestamp upper bound"),
        school_id: Optional[str] = Query(None, description="Restrict to one tenant"),
        current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN])),
        _stepup: dict = Depends(require_recent_mfa()),
    ):
        """تصدير سجل التدقيق الخاص بالمصادقة متعددة العوامل (NDJSON).

        - يتطلب صلاحية مدير المنصة + إثبات تحقق ثاني حديث (step-up).
        - الناتج NDJSON: سطر JSON واحد لكل صف، مع ``prev_hash`` و
          ``row_hash`` و حقل ``details_text`` (تمثيل JSONB كما خُزّن) كي
          يستطيع المُدقّق إعادة احتساب السلسلة بشكل مستقل.
        """
        conditions = ["action LIKE 'mfa.%'"]
        params: Dict[str, Any] = {}
        if from_date:
            conditions.append("timestamp >= :from_date")
            params["from_date"] = from_date
        if to_date:
            conditions.append("timestamp <= :to_date")
            params["to_date"] = to_date
        if school_id:
            conditions.append("school_id = :school_id")
            params["school_id"] = school_id
        where_sql = " AND ".join(conditions)

        # Pull details as text so the auditor sees the *exact* JSONB
        # representation Postgres hashed, plus the parsed JSON for
        # readability. We stream row-by-row to bound memory.
        sql = _sql_text(
            f"""
            SELECT id, action, severity, performed_by, actor_name, actor_role,
                   actor_email, school_id, entity_type, entity_id, ip_address,
                   user_agent, timestamp, timestamp::text AS timestamp_text,
                   details, details::text AS details_text,
                   prev_hash, row_hash
              FROM audit_logs
             WHERE {where_sql}
             ORDER BY school_id NULLS FIRST, timestamp ASC, id ASC
            """
        )

        # Audit the export itself. We log BEFORE streaming so a torn
        # connection still leaves a trail of "an export was attempted".
        try:
            from engines.audit_engine import AuditLogEngine
            class _Repos:
                def __init__(self, s): self.session = s
            audit_engine = AuditLogEngine(_Repos(db.session))
            await audit_engine.log(
                action="mfa.audit.export",
                performed_by=current_user.get("id"),
                actor_name=current_user.get("full_name"),
                actor_role=current_user.get("role"),
                actor_email=current_user.get("email"),
                tenant_id=current_user.get("tenant_id"),
                ip_address=request.client.host if request.client else None,
                user_agent=request.headers.get("user-agent"),
                details={
                    "from_date": from_date,
                    "to_date": to_date,
                    "school_id_filter": school_id,
                },
            )
        except Exception as exc:
            logger.warning(f"mfa_audit_export: audit log failed: {exc}")

        # Materialise every row INSIDE the request scope. Previously the
        # query executed lazily from within the StreamingResponse generator,
        # which runs AFTER the route returns — by then pg_session_middleware
        # has already issued ``session.rollback()`` on the same request-scoped
        # asyncpg connection, so the lazy ``execute`` raised
        # "cannot perform operation: another operation is in progress" and the
        # whole export 500'd. Fetching here binds the DB work to the live
        # session; we then stream the already-encoded lines from memory. The
        # result set is bounded (only ``action LIKE 'mfa.%'`` rows), so this is
        # safe to hold in memory.
        result = await db.session.execute(sql, params)
        rows = result.mappings().all()

        def _encode_row(row) -> bytes:
            rec = dict(row)
            # Make the row JSON-serialisable (datetime, JSONB).
            ts = rec.get("timestamp")
            if isinstance(ts, datetime):
                rec["timestamp"] = ts.isoformat()
            return (_json.dumps(rec, ensure_ascii=False, default=str) + "\n").encode("utf-8")

        async def _generator():
            for row in rows:
                yield _encode_row(row)

        return StreamingResponse(
            _generator(),
            media_type="application/x-ndjson",
            headers={
                "Content-Disposition": "attachment; filename=\"nassaq_mfa_audit.ndjson\"",
                "Cache-Control": "no-store",
            },
        )

    @router.get("/mfa-verify-chain")
    async def mfa_audit_verify_chain(
        request: Request,
        school_id: Optional[str] = Query(None, description="Restrict to one tenant; default = verify every chain"),
        current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN])),
        _stepup: dict = Depends(require_recent_mfa()),
    ):
        """التحقق من سلامة سلسلة التجزئة لسجلات MFA.

        تمشي السلسلة لكل مدرسة (``school_id``) بترتيب الزمن وتعيد احتساب
        ``row_hash`` ومقارنته بالقيمة المخزّنة. أيّ عدم تطابق يعني تعديلاً
        غير مشروع على قاعدة البيانات.
        """
        conditions = ["action LIKE 'mfa.%'", "row_hash IS NOT NULL"]
        params: Dict[str, Any] = {}
        if school_id:
            conditions.append("school_id = :school_id")
            params["school_id"] = school_id
        where_sql = " AND ".join(conditions)

        sql = _sql_text(
            f"""
            SELECT id, action, performed_by, school_id, entity_type, entity_id,
                   ip_address, user_agent, timestamp,
                   timestamp::text AS timestamp_text,
                   details::text AS details_text,
                   prev_hash, row_hash
              FROM audit_logs
             WHERE {where_sql}
             ORDER BY school_id NULLS FIRST, timestamp ASC, id ASC
            """
        )
        result = await db.session.execute(sql, params)
        rows = list(result.mappings())

        # Per-tenant walk: each chain starts with prev_hash = '0'*64 and
        # every subsequent row's prev_hash must equal the previous row's
        # row_hash.
        chains: Dict[str, Dict[str, Any]] = {}
        per_tenant_prev: Dict[Any, Optional[str]] = {}
        breaks: List[Dict[str, Any]] = []
        verified = 0

        for row in rows:
            r = dict(row)
            tenant_key = r.get("school_id") or "__platform__"
            chain_state = chains.setdefault(tenant_key, {"count": 0, "intact": True})

            recomputed = hashlib.sha256(_mfa_chain_payload(r).encode("utf-8")).hexdigest()
            stored = r.get("row_hash")

            expected_prev = per_tenant_prev.get(tenant_key, "0" * 64)
            if expected_prev is None:
                expected_prev = "0" * 64

            row_ok = (recomputed == stored)
            link_ok = (r.get("prev_hash") == expected_prev)

            if not row_ok or not link_ok:
                chain_state["intact"] = False
                breaks.append({
                    "id": r.get("id"),
                    "school_id": r.get("school_id"),
                    "action": r.get("action"),
                    "timestamp": r.get("timestamp").isoformat() if isinstance(r.get("timestamp"), datetime) else r.get("timestamp"),
                    "row_hash_match": row_ok,
                    "prev_hash_match": link_ok,
                    "expected_prev_hash": expected_prev,
                    "stored_prev_hash": r.get("prev_hash"),
                })
            else:
                verified += 1

            chain_state["count"] += 1
            per_tenant_prev[tenant_key] = stored

        return {
            "intact": all(c["intact"] for c in chains.values()),
            "tenants_checked": len(chains),
            "rows_checked": len(rows),
            "rows_verified": verified,
            "rows_failed": len(breaks),
            "per_tenant": [
                {"school_id": (None if k == "__platform__" else k), "count": v["count"], "intact": v["intact"]}
                for k, v in chains.items()
            ],
            "breaks": breaks[:50],  # cap response size
        }

    return router


def create_audit_router(db, get_current_user, require_roles, UserRole, require_recent_mfa=None):
    return setup_audit_routes(db, get_current_user, require_roles, UserRole, require_recent_mfa)
