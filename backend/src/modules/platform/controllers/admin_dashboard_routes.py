"""
Admin Dashboard Routes - مسارات لوحة تحكم مدير المنصة
APIs for Command Center stats and operations
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone, timedelta
import uuid
import logging
from sqlalchemy.exc import SQLAlchemyError
from engines.sql_utils import gd_find, gd_find_one, gd_insert, gd_insert_many, gd_update_one, gd_update_many, gd_count, gd_delete_one, gd_delete_many, gd_distinct, gd_upsert, _gd_aggregate

logger = logging.getLogger("nassaq.admin_dashboard")


class CommandCenterStats(BaseModel):
    registered_schools: int = 0
    registered_students: int = 0
    teachers_in_schools: int = 0
    independent_teachers: int = 0
    student_attendance_rate: float = 0.0
    teacher_attendance_rate: float = 0.0
    platform_accounts: int = 0
    pending_requests: int = 0
    ai_enabled_schools: int = 0
    active_schools: int = 0
    suspended_schools: int = 0
    pending_schools: int = 0
    total_parents: int = 0
    total_classes: int = 0
    total_subjects: int = 0
    total_school_admins: int = 0
    published_timetables: int = 0
    sessions_today: int = 0
    active_sessions_now: int = 0
    notifications_sent_today: int = 0
    behaviour_records_today: int = 0
    students_present_today: int = 0
    students_absent_today: int = 0
    teachers_present_today: int = 0
    teachers_absent_today: int = 0
    total_users: int = 0
    active_users_today: int = 0
    hijri_date: str = ""
    gregorian_date: str = ""
    last_updated: str = ""


class NotificationStats(BaseModel):
    total_notifications: int = 0
    unread_notifications: int = 0
    sent_messages: int = 0
    received_messages: int = 0
    scheduled_messages: int = 0


def setup_admin_routes(db, get_current_user, require_roles, UserRole):
    router = APIRouter(prefix="/admin", tags=["Admin Dashboard"])

    # NOTE: /command-center/stats is intentionally NOT defined here. The canonical
    # handler lives in dashboard_routes_mod.py, whose router is registered first, so
    # any copy here would be shadowed (dead) by FastAPI's first-match-wins. Edit the
    # roles/logic there, not here.

    @router.get("/command-center/system-health")
    async def get_system_health(
        current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.PLATFORM_OPERATIONS_MANAGER, UserRole.PLATFORM_SUB_ADMIN]))
    ):
        try:
            now = datetime.now(timezone.utc)
            db_healthy = True
            total_tables = 0
            try:
                from sqlalchemy import text as sa_text
                session = db._get_session()
                if session:
                    result = await session.execute(sa_text("SELECT 1"))
                    result.scalar()
                    tbl_result = await session.execute(sa_text(
                        "SELECT count(*) FROM information_schema.tables WHERE table_schema='public'"
                    ))
                    total_tables = tbl_result.scalar() or 0
                else:
                    db_healthy = False
            except (SQLAlchemyError, ConnectionError, OSError) as e:
                logger.error(f"System health DB check failed: {e}")
                db_healthy = False
            except Exception as e:
                logger.error(f"System health unexpected error: {e}")
                db_healthy = False

            return {
                "database": {
                    "status": "healthy" if db_healthy else "error",
                    "collections": total_tables,
                    "last_check": now.isoformat()
                },
                "api": {
                    "status": "healthy",
                    "uptime": "99.9%",
                    "last_check": now.isoformat()
                },
                "engines": {
                    "session_engine": "active",
                    "timetable_engine": "active",
                    "notification_engine": "active",
                    "ai_engine": "active"
                },
                "last_sync": now.isoformat()
            }
        except Exception as e:
            logger.error(f"Error getting system health: {e}")
            return {
                "database": {"status": "unknown"},
                "api": {"status": "unknown"},
                "engines": {},
                "last_sync": now.isoformat()
            }

    @router.get("/notifications/stats", response_model=NotificationStats)
    async def get_notification_stats(
        current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.PLATFORM_OPERATIONS_MANAGER]))
    ):
        try:
            total_notifications = await gd_count(db.session, "notifications", {})
            unread_notifications = await gd_count(db.session, "notifications", {
                "read_status": False,
                "$or": [
                    {"recipient_id": current_user.get("id")},
                    {"recipient_role": "platform_admin"}
                ]
            })
            sent_messages = await gd_count(db.session, "messages", {"status": "sent"})
            received_messages = await gd_count(db.session, "messages", {
                "$or": [
                    {"recipient_id": current_user.get("id")},
                    {"recipient_role": "platform_admin"}
                ]
            })
            scheduled_messages = await gd_count(db.session, "messages", {"status": "scheduled"})

            return NotificationStats(
                total_notifications=total_notifications,
                unread_notifications=unread_notifications,
                sent_messages=sent_messages,
                received_messages=received_messages,
                scheduled_messages=scheduled_messages
            )
        except Exception as e:
            logger.error(f"Error getting notification stats: {e}")
            return NotificationStats()

    @router.post("/ai-operation/{operation_type}")
    async def run_ai_operation(
        operation_type: str,
        current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))
    ):
        valid_operations = ["diagnosis", "data_quality", "import_analysis", "alerts_review"]
        if operation_type not in valid_operations:
            raise HTTPException(status_code=400, detail="نوع العملية غير صالح")

        try:
            result = {"operation": operation_type, "status": "completed", "message": "", "details": {}}

            if operation_type == "diagnosis":
                total_schools = await gd_count(db.session, "schools", {})
                active_schools = await gd_count(db.session, "schools", {"status": "active"})
                health_score = (active_schools / max(total_schools, 1)) * 100
                result["message"] = "تم تشخيص النظام بنجاح"
                result["details"] = {
                    "health_score": round(health_score, 1),
                    "total_schools": total_schools,
                    "active_schools": active_schools,
                    "issues_found": max(0, total_schools - active_schools)
                }
            elif operation_type == "data_quality":
                students_missing = await gd_count(db.session, "students", {
                    "$or": [{"parent_phone": None}, {"parent_phone": ""}]
                })
                teachers_missing = await gd_count(db.session, "teachers", {
                    "$or": [{"rank": None}, {"rank": ""}]
                })
                total_records = await gd_count(db.session, "students", {}) + await gd_count(db.session, "teachers", {})
                quality_score = max(0, 100 - ((students_missing + teachers_missing) / max(total_records, 1) * 100))
                result["message"] = f"جودة البيانات: {round(quality_score, 1)}%"
                result["details"] = {
                    "quality_score": round(quality_score, 1),
                    "students_missing_data": students_missing,
                    "teachers_missing_data": teachers_missing
                }
            elif operation_type == "alerts_review":
                pending_alerts = await gd_count(db.session, "notifications", {"read_status": False})
                recent = await gd_find(
                    db.session, "notifications", {"read_status": False},
                    order_by="created_at", desc_order=True, limit=5
                )
                result["message"] = f"تم مراجعة {pending_alerts} تنبيه"
                result["details"] = {
                    "pending_alerts": pending_alerts,
                    "reviewed": pending_alerts,
                    "recent": [
                        {
                            "id": n.get("id"),
                            "title": n.get("title") or n.get("subject") or "",
                            "type": n.get("type") or "alert",
                            "created_at": n.get("created_at") or "",
                        } for n in recent
                    ],
                }
            else:
                today_iso = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
                today_imports = await gd_find(
                    db.session, "audit_logs",
                    {"action": {"$regex": "^bulk_import_"}, "timestamp": {"$gte": today_iso}},
                    order_by="timestamp", desc_order=True, limit=100
                )
                total_files = len(today_imports)
                total_rows = sum(int((l.get("details") or {}).get("total_rows") or 0) for l in today_imports)
                imported = sum(int((l.get("details") or {}).get("imported") or 0) for l in today_imports)
                failed_rows = sum(int((l.get("details") or {}).get("failed") or 0) for l in today_imports)
                files_with_failures = sum(1 for l in today_imports if int((l.get("details") or {}).get("failed") or 0) > 0)
                result["message"] = f"تم تحليل {total_files} ملف استيراد اليوم"
                result["details"] = {
                    "files_analyzed": total_files,
                    "total_rows": total_rows,
                    "imported": imported,
                    "failed": failed_rows,
                    "files_with_failures": files_with_failures,
                    "ready_for_import": max(0, total_files - files_with_failures),
                    "issues_found": files_with_failures,
                    "recent": [
                        {
                            "action": l.get("action"),
                            "filename": (l.get("details") or {}).get("filename"),
                            "imported": (l.get("details") or {}).get("imported"),
                            "failed": (l.get("details") or {}).get("failed"),
                            "timestamp": l.get("timestamp"),
                        } for l in today_imports[:5]
                    ],
                }

            await gd_insert(db.session, "ai_operations", {
                "id": str(uuid.uuid4()),
                "operation_type": operation_type,
                "performed_by": current_user.get("id"),
                "result": result,
                "created_at": datetime.now(timezone.utc).isoformat()
            })
            return result
        except Exception as e:
            logger.error(f"AI operation error: {e}")
            raise HTTPException(status_code=500, detail="حدث خطأ أثناء تنفيذ العملية")

    @router.get("/ai-operations/history")
    async def get_ai_operations_history(
        limit: int = 10,
        current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.PLATFORM_OPERATIONS_MANAGER]))
    ):
        try:
            today_iso = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
            ops_today = await gd_count(db.session, "ai_operations", {"created_at": {"$gte": today_iso}})
            ops = await gd_find(
                db.session, "ai_operations", {},
                order_by="created_at", desc_order=True, limit=limit
            )
            user_ids = list({o.get("performed_by") for o in ops if o.get("performed_by")})
            users_map: Dict[str, str] = {}
            if user_ids:
                users = await gd_find(db.session, "users", {"id": {"$in": user_ids}}, limit=len(user_ids))
                users_map = {u.get("id"): (u.get("full_name") or u.get("email") or "") for u in users}
            history = []
            for o in ops:
                res = o.get("result") or {}
                history.append({
                    "id": o.get("id"),
                    "operation_type": o.get("operation_type"),
                    "message": res.get("message", ""),
                    "details": res.get("details", {}),
                    "performed_by": o.get("performed_by"),
                    "performed_by_name": users_map.get(o.get("performed_by"), ""),
                    "created_at": o.get("created_at"),
                })
            return {"history": history, "total": len(history), "operations_today": ops_today}
        except Exception as e:
            logger.error(f"Error getting AI operations history: {e}")
            return {"history": [], "total": 0, "operations_today": 0}

    @router.get("/ai-suggested-actions")
    async def get_ai_suggested_actions(
        current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.PLATFORM_OPERATIONS_MANAGER]))
    ):
        try:
            actions: List[Dict[str, Any]] = []

            schools_no_admin = await gd_count(db.session, "schools", {
                "$or": [{"principal_id": None}, {"principal_id": ""}]
            })
            if schools_no_admin > 0:
                actions.append({
                    "id": "schools_no_admin",
                    "title": f"توجد {schools_no_admin} مدرسة لم يتم استكمال بيانات مديرها",
                    "title_en": f"{schools_no_admin} schools missing principal data",
                    "priority": "high",
                    "type": "data",
                    "link": "/admin/schools",
                    "linkText": "إدارة المدارس",
                    "linkText_en": "Schools",
                })

            teachers_no_rank = await gd_count(db.session, "teachers", {
                "$or": [{"rank": None}, {"rank": ""}]
            })
            if teachers_no_rank > 0:
                actions.append({
                    "id": "teachers_no_rank",
                    "title": f"{teachers_no_rank} معلماً بدون رتبة محددة",
                    "title_en": f"{teachers_no_rank} teachers without rank",
                    "priority": "medium",
                    "type": "data",
                    "link": "/admin/teachers",
                    "linkText": "إدارة المعلمين",
                    "linkText_en": "Teachers",
                })

            today_iso = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
            recent_imports = await gd_find(
                db.session, "audit_logs",
                {"action": {"$regex": "^bulk_import_"}, "timestamp": {"$gte": today_iso}},
                order_by="timestamp", desc_order=True, limit=200
            )
            failed_imports_today = sum(
                1 for l in recent_imports if int((l.get("details") or {}).get("failed") or 0) > 0
            )
            if failed_imports_today > 0:
                actions.append({
                    "id": "failed_imports",
                    "title": f"{failed_imports_today} ملفات استيراد تحتاج مراجعة",
                    "title_en": f"{failed_imports_today} import files need review",
                    "priority": "high",
                    "type": "import",
                    "link": "/admin/users",
                    "linkText": "ملفات الاستيراد",
                    "linkText_en": "Imports",
                })

            pending_requests = await gd_count(db.session, "registration_requests", {"status": "pending"})
            if pending_requests > 0:
                actions.append({
                    "id": "pending_requests",
                    "title": f"{pending_requests} طلب تسجيل معلق",
                    "title_en": f"{pending_requests} pending registration requests",
                    "priority": "medium",
                    "type": "review",
                    "link": "/admin/schools",
                    "linkText": "إدارة المدارس",
                    "linkText_en": "Schools",
                })

            schools_no_ai = await gd_count(db.session, "schools", {
                "ai_enabled": {"$ne": True},
                "ai_features_enabled": {"$ne": True},
                "hakim_enabled": {"$ne": True},
                "status": "active"
            })
            if schools_no_ai > 0:
                actions.append({
                    "id": "ai_not_enabled",
                    "title": f"يُفضل تفعيل AI Scheduling لـ{schools_no_ai} مدرسة",
                    "title_en": f"Recommended to enable AI Scheduling for {schools_no_ai} schools",
                    "priority": "low",
                    "type": "suggestion",
                    "link": "/admin/schools",
                    "linkText": "إدارة المدارس",
                    "linkText_en": "Schools",
                })

            return {"actions": actions, "total": len(actions)}
        except Exception as e:
            logger.error(f"Error getting AI suggested actions: {e}")
            return {"actions": [], "total": 0}

    return router


def get_hijri_date(date: datetime) -> str:
    try:
        from hijri_converter import Gregorian
        h = Gregorian(date.year, date.month, date.day).to_hijri()
        HIJRI_MONTHS = [
            '', 'محرم', 'صفر', 'ربيع الأول', 'ربيع الآخر',
            'جمادى الأولى', 'جمادى الآخرة', 'رجب', 'شعبان',
            'رمضان', 'شوال', 'ذو القعدة', 'ذو الحجة'
        ]
        return f"{h.day} {HIJRI_MONTHS[h.month]} {h.year} هـ"
    except Exception as e:
        logger.debug(f"Hijri date conversion failed: {e}")
        return ""
