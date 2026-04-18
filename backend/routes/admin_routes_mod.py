"""
NASSAQ Route Module: Audit logs, seed data, demo data
Auto-consolidated during Phase 8 modularization.
"""
from fastapi import APIRouter, HTTPException, Depends, status, Header, Query, Body, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import Response
from starlette.responses import StreamingResponse
from pydantic import BaseModel, Field, ConfigDict, EmailStr, model_validator
from typing import List, Optional, Any, Dict
from datetime import datetime, timezone, timedelta
import uuid, os, logging, json, random, re, io, base64

from engines.sql_utils import gd_find, gd_find_one, gd_insert, gd_insert_many, gd_update_one, gd_update_many, gd_count, gd_delete_one, gd_delete_many, gd_distinct, gd_upsert, _gd_aggregate
from dependencies import (
    db, get_current_user, require_roles, UserRole, SchoolStatus,
    hash_password, verify_password, create_access_token,
    JWT_SECRET, JWT_ALGORITHM, ACCESS_TOKEN_EXPIRE, security, logger,
    audit_engine, AuditAction, AuditSeverity,
    smart_scheduling_engine, TimetableRunStatus, TimetableStatus,
    ConflictType, ConflictSeverity, PreValidationResult, GenerationResult,
    hakim_engine, reporting_engine, export_engine, session_engine,
    REPORT_TYPES, generate_student_qr_code
)

router = APIRouter()



# ============== AUDIT LOG ROUTES ==============

# Action translations (Arabic)
_ACTION_AR = {
    "auth.login": "تسجيل دخول",
    "auth.logout": "تسجيل خروج",
    "auth.login_failed": "فشل تسجيل الدخول",
    "auth.register": "تسجيل حساب جديد",
    "auth.password_changed": "تغيير كلمة المرور",
    "user.created": "إنشاء مستخدم",
    "user.updated": "تحديث مستخدم",
    "user.deleted": "حذف مستخدم",
    "user.suspended": "تعليق مستخدم",
    "user.activated": "تفعيل مستخدم",
    "tenant.created": "إنشاء مؤسسة",
    "tenant.updated": "تحديث مؤسسة",
    "tenant.suspended": "تعليق مؤسسة",
    "tenant.activated": "تفعيل مؤسسة",
    "school.created": "إنشاء مدرسة",
    "school.updated": "تحديث مدرسة",
    "student.created": "إضافة طالب",
    "student.updated": "تحديث طالب",
    "teacher.created": "إضافة معلم",
    "teacher.updated": "تحديث معلم",
    "attendance.created": "تسجيل حضور",
    "grade.created": "تسجيل درجة",
    "grade.updated": "تحديث درجة",
    "schedule.created": "إنشاء جدول",
    "schedule.published": "نشر جدول",
    "settings.updated": "تحديث الإعدادات",
    "data.exported": "تصدير البيانات",
    "data.imported": "استيراد البيانات",
}

@router.get("/audit/logs")
async def get_audit_logs(
    current_user: dict = Depends(require_roles([
        UserRole.PLATFORM_ADMIN,
        UserRole.PLATFORM_SECURITY_OFFICER,
        UserRole.PLATFORM_DATA_ANALYST
    ])),
    tenant_id: Optional[str] = None,
    action: Optional[str] = None,
    entity_type: Optional[str] = None,
    severity: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    search: Optional[str] = None,
    days: Optional[int] = None,
    page: int = 1,
    limit: int = 50,
    skip: int = 0,
):
    """Get audit logs with full device & user data"""
    query: dict = {}
    if tenant_id:
        query["tenant_id"] = tenant_id
    import re as _re
    if action and action != "all":
        query["action"] = {"$regex": _re.escape(action), "$options": "i"}
    if entity_type and entity_type != "all":
        query["entity_type"] = entity_type
    if severity and severity != "all":
        query["severity"] = severity
    if days:
        query["timestamp"] = {"$gte": (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()}
    else:
        ts_f = {}
        if start_date:
            ts_f["$gte"] = start_date
        if end_date:
            ts_f["$lte"] = end_date
        if ts_f:
            query["timestamp"] = ts_f
    if search:
        safe_search = _re.escape(search)
        query["$or"] = [
            {"actor_name":  {"$regex": safe_search, "$options": "i"}},
            {"actor_email": {"$regex": safe_search, "$options": "i"}},
            {"action":      {"$regex": safe_search, "$options": "i"}},
            {"ip_address":  {"$regex": safe_search, "$options": "i"}},
            {"details.path":{"$regex": safe_search, "$options": "i"}},
        ]

    effective_skip = (page - 1) * limit if page > 1 else skip
    total = await gd_count(db.session, "audit_logs", query)
    raw = await gd_find(db.session, "audit_logs", query, order_by="timestamp", desc_order=True, offset=effective_skip, limit=limit)

    # Batch-resolve user names/emails for logs that don't have actor_name persisted
    missing_user_ids = list({
        l.get("performed_by") for l in raw
        if l.get("performed_by") and not (l.get("actor_name") or l.get("performed_by_name"))
    })
    user_lookup: dict = {}
    if missing_user_ids:
        users = await gd_find(db.session, "users", {"id": {"$in": missing_user_ids}}, limit=len(missing_user_ids))
        user_lookup = {
            u.get("id"): {
                "name":  u.get("full_name") or u.get("full_name_en") or u.get("email"),
                "email": u.get("email"),
                "role":  u.get("role"),
            }
            for u in users
        }

    enriched = []
    for log in raw:
        action_key = log.get("action", "")
        di_raw = log.get("device_info") or {}
        pb = log.get("performed_by")
        looked_up = user_lookup.get(pb) if pb else None
        enriched.append({
            "id":           str(log.get("id", log.get("_id", ""))),
            "action":       action_key,
            "action_ar":    _ACTION_AR.get(action_key, action_key),
            "severity":     log.get("severity", "low"),
            "performed_by": pb,
            "actor_name":   log.get("actor_name") or log.get("performed_by_name") or (looked_up.get("name") if looked_up else None),
            "actor_role":   log.get("actor_role") or log.get("performed_by_role") or (looked_up.get("role") if looked_up else None),
            "actor_email":  log.get("actor_email") or (looked_up.get("email") if looked_up else None),
            "entity_type":  log.get("entity_type") or log.get("target_type"),
            "entity_id":    log.get("entity_id") or log.get("target_id"),
            "target_name":  log.get("target_name"),
            "ip_address":   log.get("ip_address"),
            "user_agent":   log.get("user_agent"),
            "device_info":  {
                "browser":     di_raw.get("browser", "غير معروف"),
                "os":          di_raw.get("os", "غير معروف"),
                "device_type": di_raw.get("device_type", "غير معروف"),
                "raw":         di_raw.get("raw", log.get("user_agent", ""))[:200],
            } if (di_raw or log.get("user_agent")) else None,
            "tenant_id":    log.get("tenant_id"),
            "timestamp":    log.get("timestamp", ""),
            "details":      log.get("details"),
            "status":       log.get("status", "success"),
        })

    total_pages = max(1, (total + limit - 1) // limit)
    return {
        "logs":        enriched,
        "total":       total,
        "page":        page,
        "limit":       limit,
        "total_pages": total_pages,
    }


@router.get("/audit/stats")
async def get_audit_stats(
    current_user: dict = Depends(require_roles([
        UserRole.PLATFORM_ADMIN,
        UserRole.PLATFORM_SECURITY_OFFICER,
        UserRole.PLATFORM_DATA_ANALYST
    ])),
    tenant_id: Optional[str] = None,
    days: int = 30
):
    """Get audit statistics — returns unified format for the frontend"""
    try:
        now = datetime.now(timezone.utc)
        cutoff = (now - timedelta(days=days)).isoformat()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()

        base_q: dict = {"timestamp": {"$gte": cutoff}}
        if tenant_id:
            base_q["tenant_id"] = tenant_id

        # Fetch all logs in period (max 20k) and compute stats in Python
        
        all_logs = await gd_find(db.session, "audit_logs", base_q, limit=20000)

        total_events   = len(all_logs)
        today_events   = sum(1 for l in all_logs if (l.get("timestamp") or "") >= today_start)
        critical_count = sum(1 for l in all_logs if l.get("severity") == "critical")
        high_count     = sum(1 for l in all_logs if l.get("severity") == "high")
        failed_logins  = sum(1 for l in all_logs if l.get("action") in ("auth.login_failed", "login_failed"))
        unique_users   = len(set(l.get("performed_by") for l in all_logs if l.get("performed_by")))

        return {
            "total_events":  total_events,
            "today_events":  today_events,
            "critical_count": critical_count,
            "high_count":    high_count,
            "failed_logins": failed_logins,
            "unique_users":  unique_users,
            "period_days":   days,
        }
    except Exception as e:
        logger.error(f"Audit stats error: {e}")
        return {"total_events": 0, "today_events": 0, "critical_count": 0, "high_count": 0, "failed_logins": 0, "unique_users": 0, "period_days": days}


@router.get("/audit/critical-events")
async def get_critical_events(
    current_user: dict = Depends(require_roles([
        UserRole.PLATFORM_ADMIN,
        UserRole.PLATFORM_SECURITY_OFFICER
    ])),
    tenant_id: Optional[str] = None,
    days: int = 7
):
    """Get critical and high severity events - Platform Admin or Security Officer only"""
    events = await audit_engine.get_critical_events(tenant_id=tenant_id, days=days)
    return {"events": events, "count": len(events)}


@router.get("/audit/login-analytics")
async def get_login_analytics(
    current_user: dict = Depends(require_roles([
        UserRole.PLATFORM_ADMIN,
        UserRole.PLATFORM_SECURITY_OFFICER
    ])),
    tenant_id: Optional[str] = None,
    days: int = 30
):
    """Get login analytics - Platform Admin or Security Officer only"""
    analytics = await audit_engine.get_login_analytics(tenant_id=tenant_id, days=days)
    return analytics


@router.get("/audit/user-activity/{user_id}")
async def get_audit_user_activity(
    user_id: str,
    current_user: dict = Depends(require_roles([
        UserRole.PLATFORM_ADMIN,
        UserRole.PLATFORM_SECURITY_OFFICER,
        UserRole.SCHOOL_PRINCIPAL
    ])),
    days: int = 30
):
    """Get activity log for a specific user"""
    activity = await audit_engine.get_user_activity(user_id=user_id, days=days)
    return {"user_id": user_id, "activity": activity}


@router.get("/audit/entity-history/{entity_type}/{entity_id}")
async def get_entity_history(
    entity_type: str,
    entity_id: str,
    current_user: dict = Depends(require_roles([
        UserRole.PLATFORM_ADMIN,
        UserRole.PLATFORM_SECURITY_OFFICER,
        UserRole.SCHOOL_PRINCIPAL
    ]))
):
    """Get audit history for a specific entity"""
    history = await audit_engine.get_entity_history(entity_type=entity_type, entity_id=entity_id)
    return {"entity_type": entity_type, "entity_id": entity_id, "history": history}


@router.post("/audit/export")
async def export_audit_report(
    current_user: dict = Depends(require_roles([
        UserRole.PLATFORM_ADMIN,
        UserRole.PLATFORM_SECURITY_OFFICER
    ])),
    tenant_id: str = None,
    start_date: str = None,
    end_date: str = None
):
    """Export audit report for compliance"""
    if not start_date:
        start_date = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    if not end_date:
        end_date = datetime.now(timezone.utc).isoformat()
    
    report = await audit_engine.export_audit_report(
        tenant_id=tenant_id or "all",
        start_date=start_date,
        end_date=end_date
    )
    
    # Log the export action
    await audit_engine.log(
        action=AuditAction.DATA_EXPORTED.value,
        performed_by=current_user["id"],
        entity_type="audit_report",
        details={
            "start_date": start_date,
            "end_date": end_date,
            "tenant_id": tenant_id
        }
    )
    
    return report





# ============== SEED DATA ==============
# NOTE: These endpoints should only be used in development/testing
# In production, they should be disabled or require special auth
@router.post("/seed/admin")
async def seed_admin(current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))):
    """Create initial platform admin if not exists - Platform Admin only"""
    # Check for old admin and delete
    await gd_delete_one(db.session, "users", {"email": "admin@nassaq.sa"})
    
    # Check if new admin exists
    existing = await gd_find_one(db.session, "users", {"email": "info@nassaqapp.com"})
    if existing:
        return {"message": "Admin already exists", "email": "info@nassaqapp.com"}
    
    admin_id = str(uuid.uuid4())
    seed_password = os.environ.get("NASSAQ_SEED_ADMIN_PASSWORD")
    if not seed_password:
        raise HTTPException(status_code=500, detail="NASSAQ_SEED_ADMIN_PASSWORD environment variable is not set")
    admin_doc = {
        "id": admin_id,
        "email": "info@nassaqapp.com",
        "password_hash": hash_password(seed_password),
        "full_name": "مدير المنصة",
        "full_name_en": "Platform Admin",
        "role": UserRole.PLATFORM_ADMIN.value,
        "tenant_id": None,
        "phone": None,
        "avatar_url": None,
        "is_active": True,
        "preferred_language": "ar",
        "preferred_theme": "light",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    
    await gd_insert(db.session, "users", admin_doc)
    return {"message": "Admin created", "email": "info@nassaqapp.com"}





# ============== SEED TEST ACCOUNTS ==============
@router.post("/seed/test-accounts")
async def seed_test_accounts(current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))):
    """
    إنشاء حسابات اختبار للنظام - Platform Admin only.
    Passwords are read from TEST_PRINCIPAL_PASSWORD and TEST_TEACHER_PASSWORD env vars.
    """
    test_principal_password = os.getenv("TEST_PRINCIPAL_PASSWORD", "NassaqPrincipal2026")
    test_teacher_password = os.getenv("TEST_TEACHER_PASSWORD", "NassaqTeacher2026")

    results = {
        "principal": None,
        "teacher": None
    }
    
    # Get or create a test school
    test_school = await gd_find_one(db.session, "schools", {"code": "TEST001"})
    if not test_school:
        school_id = str(uuid.uuid4())
        test_school = {
            "id": school_id,
            "name": "مدرسة نَسَّق التجريبية",
            "name_en": "NASSAQ Test School",
            "code": "TEST001",
            "email": "school@nassaq.com",
            "phone": "0500000000",
            "address": "الرياض، المملكة العربية السعودية",
            "city": "الرياض",
            "region": "الرياض",
            "country": "SA",
            "logo_url": None,
            "status": "active",
            "student_capacity": 500,
            "current_students": 0,
            "current_teachers": 0,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        await gd_insert(db.session, "schools", test_school)
    
    school_id = test_school.get("id")
    
    # 1. Create Principal Account
    existing_principal = await gd_find_one(db.session, "users", {"email": "principal@nassaq.com"})
    if existing_principal:
        # Update password to ensure it's correct
        await gd_update_one(db.session, "users", {"email": "principal@nassaq.com"}, {
                "password_hash": hash_password(test_principal_password),
                "is_active": True,
                "updated_at": datetime.now(timezone.utc).isoformat()
            })
        results["principal"] = {"status": "updated", "email": "principal@nassaq.com"}
    else:
        principal_id = str(uuid.uuid4())
        principal_doc = {
            "id": principal_id,
            "email": "principal@nassaq.com",
            "password_hash": hash_password(test_principal_password),
            "full_name": "مدير المدرسة",
            "full_name_en": "School Principal",
            "role": UserRole.SCHOOL_PRINCIPAL.value,
            "tenant_id": school_id,
            "phone": "0511111111",
            "avatar_url": None,
            "is_active": True,
            "preferred_language": "ar",
            "preferred_theme": "light",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        await gd_insert(db.session, "users", principal_doc)
        results["principal"] = {"status": "created", "email": "principal@nassaq.com"}
    
    # 2. Create Teacher Account
    existing_teacher = await gd_find_one(db.session, "users", {"email": "teacher@nassaq.com"})
    if existing_teacher:
        # Update password to ensure it's correct
        await gd_update_one(db.session, "users", {"email": "teacher@nassaq.com"}, {
                "password_hash": hash_password(test_teacher_password),
                "is_active": True,
                "updated_at": datetime.now(timezone.utc).isoformat()
            })
        results["teacher"] = {"status": "updated", "email": "teacher@nassaq.com"}
    else:
        teacher_user_id = str(uuid.uuid4())
        teacher_id = str(uuid.uuid4())
        
        # User account
        teacher_user_doc = {
            "id": teacher_user_id,
            "email": "teacher@nassaq.com",
            "password_hash": hash_password(test_teacher_password),
            "full_name": "معلم تجريبي",
            "full_name_en": "Test Teacher",
            "role": UserRole.TEACHER.value,
            "tenant_id": school_id,
            "phone": "0522222222",
            "avatar_url": None,
            "is_active": True,
            "preferred_language": "ar",
            "preferred_theme": "light",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        
        # Teacher profile
        teacher_profile_doc = {
            "id": teacher_id,
            "user_id": teacher_user_id,
            "full_name": "معلم تجريبي",
            "full_name_en": "Test Teacher",
            "email": "teacher@nassaq.com",
            "phone": "0522222222",
            "school_id": school_id,
            "specialization": "الرياضيات",
            "years_of_experience": 5,
            "qualification": "بكالوريوس",
            "gender": "male",
            "is_active": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        
        await gd_insert(db.session, "users", teacher_user_doc)
        await gd_insert(db.session, "teachers", teacher_profile_doc)
        
        # Update school teacher count
        school = await gd_find_one(db.session, "schools", {"id": school_id})
        if school:
            await gd_update_one(db.session, "schools", {"id": school_id}, {"current_teachers": (school.get("current_teachers") or 0) + 1})
        
        results["teacher"] = {"status": "created", "email": "teacher@nassaq.com"}
    
    return {
        "message": "تم إنشاء/تحديث حسابات الاختبار",
        "accounts": {
            "principal": {
                "email": "principal@nassaq.com",
                "password": test_principal_password,
                "role": "School Principal"
            },
            "teacher": {
                "email": "teacher@nassaq.com",
                "password": test_teacher_password,
                "role": "Teacher"
            }
        },
        "results": results
    }






@router.get("/activity/daily")
async def get_daily_activity(
    current_user: dict = Depends(get_current_user),
    period: str = "today",
    view_by: str = "hour",
    school_id: Optional[str] = None
):
    """Get daily platform activity data for charts"""
    now = datetime.now(timezone.utc)
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    
    if period == "today":
        start_date = today
    elif period == "24h":
        start_date = now - timedelta(hours=24)
    elif period == "week":
        start_date = today - timedelta(days=7)
    elif period == "month":
        start_date = today - timedelta(days=30)
    else:
        start_date = today
    
    query = {"timestamp": {"$gte": start_date.isoformat()}}
    if school_id:
        query["school_id"] = school_id
    
    logs = await gd_find(db.session, "activity_logs", query, limit=10000)
    
    if view_by == "hour":
        hourly_data = {}
        for hour in range(24):
            hourly_data[hour] = {"lessons": 0, "attendance": 0, "grades": 0, "user_activity": 0}
        
        for log in logs:
            try:
                log_time = datetime.fromisoformat(log["timestamp"].replace("Z", "+00:00"))
                hour = log_time.hour
                log_type = log.get("type", "")
                
                if log_type == "lesson":
                    hourly_data[hour]["lessons"] += 1
                elif log_type == "attendance":
                    hourly_data[hour]["attendance"] += 1
                elif log_type == "grade":
                    hourly_data[hour]["grades"] += 1
                elif log_type == "user_activity":
                    hourly_data[hour]["user_activity"] += 1
            except Exception as e:
                logger.debug(f"Skipping malformed audit log entry: {e}")
                continue
        
        chart_data = []
        for hour in range(7, 17):
            chart_data.append({
                "hour": f"{hour:02d}:00",
                "lessons": hourly_data[hour]["lessons"],
                "attendance": hourly_data[hour]["attendance"],
                "grades": hourly_data[hour]["grades"],
                "users": hourly_data[hour]["user_activity"]
            })
        
        return {"chart_data": chart_data, "period": period, "view_by": view_by}
    
    elif view_by == "school":
        school_data = {}
        for log in logs:
            school_name = log.get("school_name", "Unknown")
            if school_name not in school_data:
                school_data[school_name] = {"lessons": 0, "attendance": 0, "grades": 0, "users": 0}
            
            log_type = log.get("type", "")
            if log_type == "lesson":
                school_data[school_name]["lessons"] += 1
            elif log_type == "attendance":
                school_data[school_name]["attendance"] += 1
            elif log_type == "grade":
                school_data[school_name]["grades"] += 1
            elif log_type == "user_activity":
                school_data[school_name]["users"] += 1
        
        chart_data = [{"school": k, **v} for k, v in school_data.items()]
        return {"chart_data": chart_data, "period": period, "view_by": view_by}
    
    else:
        type_data = {"lessons": 0, "attendance": 0, "grades": 0, "users": 0}
        for log in logs:
            log_type = log.get("type", "")
            if log_type == "lesson":
                type_data["lessons"] += 1
            elif log_type == "attendance":
                type_data["attendance"] += 1
            elif log_type == "grade":
                type_data["grades"] += 1
            elif log_type == "user_activity":
                type_data["users"] += 1
        
        return {"chart_data": type_data, "period": period, "view_by": view_by}

@router.get("/activity/summary")
async def get_activity_summary(current_user: dict = Depends(get_current_user)):
    """Get quick summary of today's activity"""
    import random
    
    now = datetime.now(timezone.utc)
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday = today - timedelta(days=1)
    
    today_query = {"timestamp": {"$gte": today.isoformat()}}
    today_lessons = await gd_count(db.session, "activity_logs", {**today_query, "type": "lesson"})
    today_attendance = await gd_count(db.session, "activity_logs", {**today_query, "type": "attendance"})
    today_grades = await gd_count(db.session, "activity_logs", {**today_query, "type": "grade"})
    today_users = await gd_count(db.session, "activity_logs", {**today_query, "type": "user_activity"})
    
    # If no activity_logs data, fall back to real collections for an honest summary
    if today_lessons + today_attendance + today_grades + today_users == 0:
        today_str = today.strftime("%Y-%m-%d")
        today_attendance = await gd_count(db.session, "attendance", {"date": today_str})
        today_users = await gd_count(db.session, "users", {"is_active": True})
        today_lessons = await gd_count(db.session, "timetable_sessions", {})
        today_grades = await gd_count(db.session, "grades", {})

        return {
            "lessons": {"count": today_lessons, "change": 0, "status": "normal"},
            "attendance": {"count": today_attendance, "change": 0, "status": "normal"},
            "grades": {"count": today_grades, "change": 0, "status": "normal"},
            "users": {"count": today_users, "change": 0, "status": "normal"},
        }

    yesterday_query = {"timestamp": {"$gte": yesterday.isoformat(), "$lt": today.isoformat()}}
    yesterday_lessons = await gd_count(db.session, "activity_logs", {**yesterday_query, "type": "lesson"}) or 1
    yesterday_attendance = await gd_count(db.session, "activity_logs", {**yesterday_query, "type": "attendance"}) or 1
    yesterday_grades = await gd_count(db.session, "activity_logs", {**yesterday_query, "type": "grade"}) or 1
    yesterday_users = await gd_count(db.session, "activity_logs", {**yesterday_query, "type": "user_activity"}) or 1
    
    def calc_change(today_val, yesterday_val):
        if yesterday_val == 0:
            return 100 if today_val > 0 else 0
        return round(((today_val - yesterday_val) / yesterday_val) * 100, 1)
    
    return {
        "lessons": {
            "count": today_lessons,
            "change": calc_change(today_lessons, yesterday_lessons),
            "status": "high" if today_lessons > yesterday_lessons * 1.2 else "low" if today_lessons < yesterday_lessons * 0.8 else "normal"
        },
        "attendance": {
            "count": today_attendance,
            "change": calc_change(today_attendance, yesterday_attendance),
            "status": "high" if today_attendance > yesterday_attendance * 1.2 else "low" if today_attendance < yesterday_attendance * 0.8 else "normal"
        },
        "grades": {
            "count": today_grades,
            "change": calc_change(today_grades, yesterday_grades),
            "status": "high" if today_grades > yesterday_grades * 1.2 else "low" if today_grades < yesterday_grades * 0.8 else "normal"
        },
        "users": {
            "count": today_users,
            "change": calc_change(today_users, yesterday_users),
            "status": "high" if today_users > yesterday_users * 1.2 else "low" if today_users < yesterday_users * 0.8 else "normal"
        }
    }

@router.get("/activity/alerts")
async def get_activity_alerts(current_user: dict = Depends(get_current_user)):
    """Get smart activity alerts"""
    now = datetime.now(timezone.utc)
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    
    alerts = []
    
    today_attendance = await gd_count(db.session, "activity_logs", {
        "timestamp": {"$gte": today.isoformat()},
        "type": "attendance"
    })
    
    if today_attendance < 50 and now.hour > 9:
        alerts.append({
            "type": "warning",
            "title": "انخفاض تسجيل الحضور",
            "message": f"تم تسجيل {today_attendance} عملية حضور فقط اليوم",
            "action": "attendance_report"
        })
    
    schools = await gd_find(db.session, "demo_schools", {}, limit=100)
    for school in schools:
        school_activity = await gd_count(db.session, "activity_logs", {
            "timestamp": {"$gte": today.isoformat()},
            "school_id": school["id"]
        })
        if school_activity == 0 and now.hour > 8:
            alerts.append({
                "type": "critical",
                "title": f"لا يوجد نشاط من {school['name']}",
                "message": "المدرسة لم تسجل أي نشاط اليوم",
                "action": "school_details",
                "school_id": school["id"]
            })
    
    today_total = await gd_count(db.session, "activity_logs", {
        "timestamp": {"$gte": today.isoformat()}
    })
    
    if today_total > 500:
        alerts.append({
            "type": "info",
            "title": "نشاط مرتفع غير عادي",
            "message": f"تم تسجيل {today_total} عملية اليوم - أعلى من المعدل الطبيعي",
            "action": "activity_report"
        })
    
    return {"alerts": alerts[:5]}



