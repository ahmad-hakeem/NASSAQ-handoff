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
from bson_compat import ObjectId
import uuid, os, logging, json, random, re, io, base64

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
    skip: int = 0,
    limit: int = 50
):
    """Get audit logs with filters - Platform Admin or Security Officer only"""
    logs = await audit_engine.get_audit_logs(
        tenant_id=tenant_id,
        action=action,
        entity_type=entity_type,
        severity=severity,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
        skip=skip
    )
    
    total = await db.audit_logs.count_documents({})
    
    return {
        "logs": logs,
        "total": total,
        "skip": skip,
        "limit": limit
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
    """Get audit statistics - Platform Admin or Security Officer only"""
    stats = await audit_engine.get_audit_stats(tenant_id=tenant_id, days=days)
    return stats


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
    await db.users.delete_one({"email": "admin@nassaq.sa"})
    
    # Check if new admin exists
    existing = await db.users.find_one({"email": "info@nassaqapp.com"})
    if existing:
        return {"message": "Admin already exists", "email": "info@nassaqapp.com"}
    
    admin_id = str(uuid.uuid4())
    admin_doc = {
        "id": admin_id,
        "email": "info@nassaqapp.com",
        "password_hash": hash_password("NassaqAdmin2026!##$$HBJ"),
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
    
    await db.users.insert_one(admin_doc)
    return {"message": "Admin created", "email": "info@nassaqapp.com"}





# ============== SEED TEST ACCOUNTS ==============
@router.post("/seed/test-accounts")
async def seed_test_accounts(current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))):
    """
    إنشاء حسابات اختبار للنظام - Platform Admin only:
    - مدير المدرسة: principal@nassaq.com / NassaqPrincipal2026
    - معلم: teacher@nassaq.com / NassaqTeacher2026
    """
    results = {
        "principal": None,
        "teacher": None
    }
    
    # Get or create a test school
    test_school = await db.schools.find_one({"code": "TEST001"}, {"_id": 0})
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
        await db.schools.insert_one(test_school)
    
    school_id = test_school.get("id")
    
    # 1. Create Principal Account
    existing_principal = await db.users.find_one({"email": "principal@nassaq.com"})
    if existing_principal:
        # Update password to ensure it's correct
        await db.users.update_one(
            {"email": "principal@nassaq.com"},
            {"$set": {
                "password_hash": hash_password("NassaqPrincipal2026"),
                "is_active": True,
                "updated_at": datetime.now(timezone.utc).isoformat()
            }}
        )
        results["principal"] = {"status": "updated", "email": "principal@nassaq.com"}
    else:
        principal_id = str(uuid.uuid4())
        principal_doc = {
            "id": principal_id,
            "email": "principal@nassaq.com",
            "password_hash": hash_password("NassaqPrincipal2026"),
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
        await db.users.insert_one(principal_doc)
        results["principal"] = {"status": "created", "email": "principal@nassaq.com"}
    
    # 2. Create Teacher Account
    existing_teacher = await db.users.find_one({"email": "teacher@nassaq.com"})
    if existing_teacher:
        # Update password to ensure it's correct
        await db.users.update_one(
            {"email": "teacher@nassaq.com"},
            {"$set": {
                "password_hash": hash_password("NassaqTeacher2026"),
                "is_active": True,
                "updated_at": datetime.now(timezone.utc).isoformat()
            }}
        )
        results["teacher"] = {"status": "updated", "email": "teacher@nassaq.com"}
    else:
        teacher_user_id = str(uuid.uuid4())
        teacher_id = str(uuid.uuid4())
        
        # User account
        teacher_user_doc = {
            "id": teacher_user_id,
            "email": "teacher@nassaq.com",
            "password_hash": hash_password("NassaqTeacher2026"),
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
        
        await db.users.insert_one(teacher_user_doc)
        await db.teachers.insert_one(teacher_profile_doc)
        
        # Update school teacher count
        await db.schools.update_one(
            {"id": school_id},
            {"$inc": {"current_teachers": 1}}
        )
        
        results["teacher"] = {"status": "created", "email": "teacher@nassaq.com"}
    
    return {
        "message": "تم إنشاء/تحديث حسابات الاختبار",
        "accounts": {
            "principal": {
                "email": "principal@nassaq.com",
                "password": "NassaqPrincipal2026",
                "role": "School Principal"
            },
            "teacher": {
                "email": "teacher@nassaq.com",
                "password": "NassaqTeacher2026",
                "role": "Teacher"
            }
        },
        "results": results
    }





# ============== DEMO DATA & ACTIVITY APIs ==============
@router.get("/demo/schools")
async def get_demo_schools(current_user: dict = Depends(get_current_user)):
    """Get all demo schools with related stats"""
    schools = await db.demo_schools.find({}, {"_id": 0}).to_list(100)
    return schools

@router.get("/demo/teachers")
async def get_demo_teachers(
    current_user: dict = Depends(get_current_user),
    school_id: Optional[str] = None
):
    """Get demo teachers, optionally filtered by school"""
    query = {"school_id": school_id} if school_id else {}
    teachers = await db.demo_teachers.find(query, {"_id": 0}).to_list(500)
    return teachers

@router.get("/demo/students")
async def get_demo_students(
    current_user: dict = Depends(get_current_user),
    school_id: Optional[str] = None,
    class_id: Optional[str] = None
):
    """Get demo students, optionally filtered by school/class"""
    query = {}
    if school_id:
        query["school_id"] = school_id
    if class_id:
        query["class_id"] = class_id
    students = await db.demo_students.find(query, {"_id": 0}).to_list(1000)
    return students

@router.get("/demo/classes")
async def get_demo_classes(
    current_user: dict = Depends(get_current_user),
    school_id: Optional[str] = None
):
    """Get demo classes, optionally filtered by school"""
    query = {"school_id": school_id} if school_id else {}
    classes = await db.demo_classes.find(query, {"_id": 0}).to_list(200)
    return classes

@router.get("/demo/stats")
async def get_demo_stats(current_user: dict = Depends(get_current_user)):
    """Get aggregated demo data statistics"""
    schools_count = await db.demo_schools.count_documents({})
    teachers_count = await db.demo_teachers.count_documents({})
    students_count = await db.demo_students.count_documents({})
    classes_count = await db.demo_classes.count_documents({})
    
    return {
        "schools": schools_count,
        "teachers": teachers_count,
        "students": students_count,
        "classes": classes_count
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
    
    logs = await db.activity_logs.find(query, {"_id": 0}).to_list(10000)
    
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
            except Exception:
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
    today_lessons = await db.activity_logs.count_documents({**today_query, "type": "lesson"})
    today_attendance = await db.activity_logs.count_documents({**today_query, "type": "attendance"})
    today_grades = await db.activity_logs.count_documents({**today_query, "type": "grade"})
    today_users = await db.activity_logs.count_documents({**today_query, "type": "user_activity"})
    
    # If no activity_logs data, fall back to real collections for an honest summary
    if today_lessons + today_attendance + today_grades + today_users == 0:
        today_str = today.strftime("%Y-%m-%d")
        today_attendance = await db.attendance.count_documents({"date": today_str})
        today_users = await db.users.count_documents({"is_active": True})
        today_lessons = await db.timetable_sessions.count_documents({})
        today_grades = await db.grades.count_documents({})

        return {
            "lessons": {"count": today_lessons, "change": 0, "status": "normal"},
            "attendance": {"count": today_attendance, "change": 0, "status": "normal"},
            "grades": {"count": today_grades, "change": 0, "status": "normal"},
            "users": {"count": today_users, "change": 0, "status": "normal"},
        }

    yesterday_query = {"timestamp": {"$gte": yesterday.isoformat(), "$lt": today.isoformat()}}
    yesterday_lessons = await db.activity_logs.count_documents({**yesterday_query, "type": "lesson"}) or 1
    yesterday_attendance = await db.activity_logs.count_documents({**yesterday_query, "type": "attendance"}) or 1
    yesterday_grades = await db.activity_logs.count_documents({**yesterday_query, "type": "grade"}) or 1
    yesterday_users = await db.activity_logs.count_documents({**yesterday_query, "type": "user_activity"}) or 1
    
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
    
    today_attendance = await db.activity_logs.count_documents({
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
    
    schools = await db.demo_schools.find({}, {"id": 1, "name": 1, "_id": 0}).to_list(100)
    for school in schools:
        school_activity = await db.activity_logs.count_documents({
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
    
    today_total = await db.activity_logs.count_documents({
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



