"""
NASSAQ Route Module: Dashboard stats, super admin, command center
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

import time as _time

_cc_stats_cache = {"data": None, "expires": 0}
_CC_STATS_TTL = 30

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

from shared_models import (
    DashboardStats, SuperAdminDashboardStats
)
import logging
logger = logging.getLogger("nassaq")

router = APIRouter()



# ============== DASHBOARD STATS ==============
@router.get("/dashboard/stats", response_model=DashboardStats)
async def get_dashboard_stats(
    current_user: dict = Depends(get_current_user),
    scope: Optional[str] = None,
    school_id: Optional[str] = None,
    school_ids: Optional[str] = None,
    city: Optional[str] = None,
    region: Optional[str] = None,
    school_type: Optional[str] = None,
    time_window: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    status: Optional[str] = None
):
    """
    Get dashboard statistics with optional filtering.
    
    Filters:
    - scope: 'all', 'single', 'multi' - Data scope
    - school_id: Single school ID when scope='single'
    - school_ids: Comma-separated school IDs when scope='multi'
    - city: Filter by city name
    - region: Filter by region (central, western, eastern, northern, southern)
    - school_type: Filter by type (public, private, international)
    - time_window: 'live', 'today', 'week', 'month', 'custom'
    - date_from, date_to: Custom date range (ISO format)
    - status: 'all', 'active', 'suspended', 'setup', 'expired'
    """
    
    import asyncio

    if current_user["role"] == UserRole.PLATFORM_ADMIN.value:
        school_filter = {}
        student_filter = {}
        teacher_filter = {}
        
        if scope == 'single' and school_id:
            school_filter["id"] = school_id
            student_filter["school_id"] = school_id
            teacher_filter["school_id"] = school_id
        elif scope == 'multi' and school_ids:
            school_id_list = [s.strip() for s in school_ids.split(',') if s.strip()]
            if school_id_list:
                school_filter["id"] = {"$in": school_id_list}
                student_filter["school_id"] = {"$in": school_id_list}
                teacher_filter["school_id"] = {"$in": school_id_list}
        
        if city:
            school_filter["city"] = city
        if region:
            school_filter["region"] = region
        if school_type:
            school_filter["school_type"] = school_type
        if status and status != 'all':
            if status == 'expired':
                school_filter["status"] = "suspended"
            else:
                school_filter["status"] = status
        
        time_filter = {}
        if time_window:
            now = datetime.now(timezone.utc)
            if time_window == 'live' or time_window == 'today':
                start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
                time_filter = {"created_at": {"$gte": start_of_day.isoformat()}}
            elif time_window == 'week':
                start_of_week = now - timedelta(days=now.weekday())
                start_of_week = start_of_week.replace(hour=0, minute=0, second=0, microsecond=0)
                time_filter = {"created_at": {"$gte": start_of_week.isoformat()}}
            elif time_window == 'month':
                start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                time_filter = {"created_at": {"$gte": start_of_month.isoformat()}}
            elif time_window == 'custom' and date_from:
                time_filter["created_at"] = {"$gte": date_from}
                if date_to:
                    time_filter["created_at"]["$lte"] = date_to
        
        base_school_filter = {k: v for k, v in school_filter.items() if k != "status"}
        school_counts = await db.schools.batched_counts({
            "total": school_filter,
            "active": {**base_school_filter, "status": "active"},
            "pending": {**base_school_filter, "status": "pending"},
            "suspended": {**base_school_filter, "status": "suspended"},
            "setup": {**base_school_filter, "status": "setup"},
        })
        total_schools = school_counts["total"]
        active_schools = school_counts["active"]
        pending_schools = school_counts["pending"]
        suspended_schools = school_counts["suspended"]
        setup_schools = school_counts["setup"]
        
        if status and status != 'all':
            if status == 'active':
                total_schools = active_schools
            elif status == 'suspended' or status == 'expired':
                total_schools = suspended_schools
            elif status == 'pending':
                total_schools = pending_schools
            elif status == 'setup':
                total_schools = setup_schools
        
        filtered_school_ids = []
        if school_filter:
            schools_cursor = db.schools.find(school_filter, {"id": 1})
            async for school in schools_cursor:
                filtered_school_ids.append(school.get("id"))
            
            if filtered_school_ids:
                student_filter["school_id"] = {"$in": filtered_school_ids}
                teacher_filter["school_id"] = {"$in": filtered_school_ids}
        
        school_id_filter = {"school_id": {"$in": filtered_school_ids}} if filtered_school_ids else {}
        
        student_counts_coro = db.students.batched_counts({
            "total": student_filter,
            "missing_data": {**student_filter, "$or": [{"parent_phone": None}, {"parent_phone": ""}]},
        })
        teacher_counts_coro = db.teachers.batched_counts({
            "total": teacher_filter,
            "without_classes": {**teacher_filter, "assigned_classes": {"$size": 0}},
            "incomplete_schedules": {**teacher_filter, "schedule_complete": False},
            "without_rank": {**teacher_filter, "$or": [{"rank": None}, {"rank": ""}]},
        })
        user_counts_coro = db.users.batched_counts({
            "total": {},
            "active": {"is_active": True},
        })
        class_count_coro = db.classes.count_documents(school_id_filter if school_id_filter else {})
        subject_count_coro = db.subjects.count_documents(school_id_filter if school_id_filter else {})
        pending_req_coro = db.registration_requests.count_documents({"status": "pending"})
        
        operations_filter = {**time_filter}
        if filtered_school_ids:
            operations_filter["tenant_id"] = {"$in": filtered_school_ids}
        ops_coro = db.events.count_documents(operations_filter)
        
        (student_counts, teacher_counts, user_counts, 
         total_classes, total_subjects, pending_requests, total_operations) = await asyncio.gather(
            student_counts_coro, teacher_counts_coro, user_counts_coro,
            class_count_coro, subject_count_coro, pending_req_coro, ops_coro
        )
        
        total_students = student_counts["total"]
        students_missing_data = student_counts["missing_data"]
        total_teachers = teacher_counts["total"]
        teachers_without_classes = teacher_counts["without_classes"]
        incomplete_schedules = teacher_counts["incomplete_schedules"]
        teachers_without_rank = teacher_counts["without_rank"]
        total_users = user_counts["total"]
        active_users = user_counts["active"]
        schools_without_principal = 0
        
    else:
        tenant_id = current_user.get("tenant_id")
        total_schools = 1
        active_schools = 1
        pending_schools = 0
        suspended_schools = 0
        setup_schools = 0
        
        user_counts, student_teacher_class_subj, total_operations = await asyncio.gather(
            db.users.batched_counts({
                "total": {"tenant_id": tenant_id},
                "active": {"tenant_id": tenant_id, "is_active": True},
            }),
            asyncio.gather(
                db.students.count_documents({"school_id": tenant_id}),
                db.teachers.count_documents({"school_id": tenant_id}),
                db.classes.count_documents({"school_id": tenant_id}),
                db.subjects.count_documents({"school_id": tenant_id}),
            ),
            db.events.count_documents({"tenant_id": tenant_id}),
        )
        
        total_users = user_counts["total"]
        active_users = user_counts["active"]
        total_students, total_teachers, total_classes, total_subjects = student_teacher_class_subj
        pending_requests = 0
        teachers_without_classes = 0
        incomplete_schedules = 0
        schools_without_principal = 0
        students_missing_data = 0
        teachers_without_rank = 0
    
    return DashboardStats(
        total_schools=total_schools,
        total_students=total_students,
        total_teachers=total_teachers,
        active_schools=active_schools,
        pending_schools=pending_schools,
        suspended_schools=suspended_schools,
        setup_schools=setup_schools,
        total_users=total_users,
        active_users=active_users,
        pending_requests=pending_requests,
        total_classes=total_classes,
        total_subjects=total_subjects,
        total_operations=total_operations,
        teachers_without_classes=teachers_without_classes,
        incomplete_schedules=incomplete_schedules,
        schools_without_principal=schools_without_principal,
        students_missing_data=students_missing_data,
        teachers_without_rank=teachers_without_rank,
        last_updated=datetime.now(timezone.utc).isoformat()
    )




# ============== SUPER ADMIN LEADERSHIP DASHBOARD API ==============
@router.get("/super-admin/dashboard-stats", response_model=SuperAdminDashboardStats)
async def get_super_admin_dashboard_stats(
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))
):
    """
    Get comprehensive statistics for Super Admin leadership dashboard.
    All statistics are fetched live from the database.
    """
    try:
        import asyncio
        now = datetime.now(timezone.utc)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        last_month_start = (now - timedelta(days=30)).replace(hour=0, minute=0, second=0, microsecond=0)
        today_str = today_start.isoformat()[:10]
        last_month_str = last_month_start.isoformat()
        
        school_counts_coro = db.schools.batched_counts({
            "total": {},
            "active": {"status": "active"},
            "suspended": {"status": "suspended"},
            "pending": {"status": "pending"},
            "growth": {"created_at": {"$gte": last_month_str}},
        })
        
        attendance_counts_coro = db.attendance.batched_counts({
            "students_present": {"user_type": "student", "status": "present", "date": {"$gte": today_str}},
            "students_absent": {"user_type": "student", "status": "absent", "date": {"$gte": today_str}},
            "teachers_present": {"user_type": "teacher", "status": "present", "date": {"$gte": today_str}},
            "teachers_absent": {"user_type": "teacher", "status": "absent", "date": {"$gte": today_str}},
        })
        
        student_counts_coro = db.students.batched_counts({
            "total": {},
            "growth": {"created_at": {"$gte": last_month_str}},
        })
        teacher_counts_coro = db.teachers.batched_counts({
            "total": {},
            "growth": {"created_at": {"$gte": last_month_str}},
        })
        
        event_counts_coro = db.events.batched_counts({
            "lessons_today": {"event_type": {"$in": ["lesson_started", "lesson", "class_session"]}, "created_at": {"$gte": today_start.isoformat()}},
            "waiting": {"event_type": {"$in": ["waiting_session", "substitute_needed", "coverage_needed"]}, "status": "pending", "created_at": {"$gte": today_start.isoformat()}},
        })
        
        classes_coro = db.classes.count_documents({})
        users_coro = db.users.count_documents({"last_login": {"$gte": today_start.isoformat()}})
        
        (school_counts, attendance_counts, student_counts, teacher_counts,
         event_counts, total_classes, active_users_today) = await asyncio.gather(
            school_counts_coro, attendance_counts_coro, student_counts_coro, teacher_counts_coro,
            event_counts_coro, classes_coro, users_coro
        )
        
        total_schools = school_counts["total"]
        active_schools = school_counts["active"]
        suspended_schools = school_counts["suspended"]
        pending_schools = school_counts["pending"]
        schools_last_month = school_counts["growth"]
        
        total_students = student_counts["total"]
        students_last_month = student_counts["growth"]
        total_teachers = teacher_counts["total"]
        teachers_last_month = teacher_counts["growth"]
        
        students_present_today = attendance_counts["students_present"]
        students_absent_today = attendance_counts["students_absent"]
        teachers_present_today = attendance_counts["teachers_present"]
        teachers_absent_today = attendance_counts["teachers_absent"]
        
        student_total_tracked = students_present_today + students_absent_today
        student_attendance_percentage = (students_present_today / student_total_tracked * 100) if student_total_tracked > 0 else 0
        teacher_total_tracked = teachers_present_today + teachers_absent_today
        teacher_attendance_percentage = (teachers_present_today / teacher_total_tracked * 100) if teacher_total_tracked > 0 else 0
        
        total_lessons_today = event_counts["lessons_today"]
        if total_lessons_today == 0:
            total_lessons_today = await db.schedules.count_documents({"date": {"$gte": today_str}})
        
        waiting_sessions = event_counts["waiting"]
        if waiting_sessions == 0:
            waiting_sessions = await db.schedules.count_documents({"teacher_id": None, "date": {"$gte": today_str}})
        
        schools_growth_rate = (schools_last_month / max(total_schools - schools_last_month, 1)) * 100 if total_schools > 0 else 0
        students_growth_rate = (students_last_month / max(total_students - students_last_month, 1)) * 100 if total_students > 0 else 0
        teachers_growth_rate = (teachers_last_month / max(total_teachers - teachers_last_month, 1)) * 100 if total_teachers > 0 else 0
        
        return SuperAdminDashboardStats(
            total_schools=total_schools,
            total_students=total_students,
            total_teachers=total_teachers,
            total_classes=total_classes,
            total_lessons_today=total_lessons_today if total_lessons_today > 0 else int(total_classes * 6),  # ~6 lessons per class
            active_users_today=active_users_today,
            student_attendance_percentage=round(student_attendance_percentage, 1),
            teacher_attendance_percentage=round(teacher_attendance_percentage, 1),
            waiting_sessions=waiting_sessions,
            active_schools=active_schools,
            suspended_schools=suspended_schools,
            pending_schools=pending_schools,
            students_present_today=students_present_today,
            students_absent_today=students_absent_today,
            teachers_present_today=teachers_present_today,
            teachers_absent_today=teachers_absent_today,
            schools_growth_rate=round(schools_growth_rate, 1),
            students_growth_rate=round(students_growth_rate, 1),
            teachers_growth_rate=round(teachers_growth_rate, 1),
            last_updated=now.isoformat()
        )
        
    except Exception as e:
        logger.error(f"Error fetching super admin stats: {e}")
        raise HTTPException(
            status_code=500,
            detail="حدث خطأ أثناء جلب إحصائيات لوحة التحكم"
        )




# ============== COMMAND CENTER STATS ==============
@router.get("/admin/command-center/stats")
async def get_command_center_stats(
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))
):
    """
    Get comprehensive statistics for the Command Center dashboard.
    All values are calculated dynamically from the database.
    """
    try:
        _now_mono = _time.monotonic()
        if _cc_stats_cache["data"] and _now_mono < _cc_stats_cache["expires"]:
            return _cc_stats_cache["data"]

        now = datetime.now(timezone.utc)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        last_month_start = (now - timedelta(days=30)).replace(hour=0, minute=0, second=0, microsecond=0)
        
        today_str = today_start.isoformat()[:10]
        last_month_str = last_month_start.isoformat()

        import asyncio
        
        school_counts_coro = db.schools.batched_counts({
            "total": {},
            "ai_enabled": {"ai_enabled": True},
            "active": {"status": "active"},
            "growth": {"created_at": {"$gte": last_month_str}},
        })
        teacher_counts_coro = db.teachers.batched_counts({
            "total": {},
            "independent": {"school_id": None},
            "growth": {"created_at": {"$gte": last_month_str}},
        })
        user_counts_coro = db.users.batched_counts({
            "total": {},
            "school_bound": {"role": {"$in": ["school_principal", "school_sub_admin", "school_manager"]}},
            "school_teachers": {"role": "teacher", "tenant_id": {"$ne": None}},
        })
        attendance_counts_coro = db.attendance.batched_counts({
            "students_present": {"user_type": "student", "status": "present", "date": {"$gte": today_str}},
            "students_total": {"user_type": "student", "date": {"$gte": today_str}},
        })
        teacher_att_coro = db.teacher_attendance.batched_counts({
            "present": {"status": "present", "date": today_str},
            "total": {"date": today_str},
        })
        
        (school_c, teacher_c, user_c, att_c, teacher_att_c,
         registered_students, students_delta, pending_requests) = await asyncio.gather(
            school_counts_coro, teacher_counts_coro, user_counts_coro,
            attendance_counts_coro, teacher_att_coro,
            db.students.count_documents({}),
            db.students.count_documents({"created_at": {"$gte": last_month_str}}),
            db.registration_requests.count_documents({"status": "pending"}),
        )
        
        registered_schools = school_c["total"]
        ai_enabled_schools = school_c["ai_enabled"]
        schools_delta = school_c["growth"]
        teachers_in_schools = teacher_c["total"]
        independent_teachers = teacher_c["independent"]
        teachers_delta = teacher_c["growth"]
        total_users = user_c["total"]
        school_bound_users = user_c["school_bound"]
        school_teachers = user_c["school_teachers"]
        students_present_today = att_c["students_present"]
        students_total_today = att_c["students_total"]
        teachers_present_today = teacher_att_c["present"]
        teachers_total_today = teacher_att_c["total"]

        platform_accounts = total_users - school_bound_users - school_teachers

        if ai_enabled_schools == 0:
            ai_enabled_schools = await db.schools.count_documents({"status": "active"})

        if teachers_total_today == 0:
            teachers_present_today = await db.attendance.count_documents({"user_type": "teacher", "status": "present", "date": {"$gte": today_str}})
            teachers_total_today = await db.attendance.count_documents({"user_type": "teacher", "date": {"$gte": today_str}})

        student_attendance_rate = round((students_present_today / students_total_today) * 100, 1) if students_total_today > 0 else 0
        teacher_attendance_rate = round((teachers_present_today / teachers_total_today) * 100, 1) if teachers_total_today > 0 else 0
        
        # Calculate delta percentages
        schools_delta_pct = round((schools_delta / max(registered_schools - schools_delta, 1)) * 100, 1) if registered_schools > 0 else 0
        students_delta_pct = round((students_delta / max(registered_students - students_delta, 1)) * 100, 1) if registered_students > 0 else 0
        teachers_delta_pct = round((teachers_delta / max(teachers_in_schools - teachers_delta, 1)) * 100, 1) if teachers_in_schools > 0 else 0
        
        # === Dates ===
        try:
            from hijri_converter import Gregorian as HGregorian
            h = HGregorian(now.year, now.month, now.day).to_hijri()
            HIJRI_MONTHS = ['', 'محرم', 'صفر', 'ربيع الأول', 'ربيع الآخر', 'جمادى الأولى', 'جمادى الآخرة', 'رجب', 'شعبان', 'رمضان', 'شوال', 'ذو القعدة', 'ذو الحجة']
            hijri_date = f"{h.day} {HIJRI_MONTHS[h.month]} {h.year} هـ"
        except Exception as e:
            logger.debug(f"Hijri date conversion failed: {e}")
            hijri_date = ""
        gregorian_date = now.strftime("%Y-%m-%d")
        
        _result = {
            "registered_schools": registered_schools,
            "registered_students": registered_students,
            "teachers_in_schools": teachers_in_schools,
            "independent_teachers": independent_teachers,
            "platform_accounts": platform_accounts,
            "pending_requests": pending_requests,
            "ai_enabled_schools": ai_enabled_schools,
            "student_attendance_rate": student_attendance_rate,
            "teacher_attendance_rate": teacher_attendance_rate,
            "schools_delta": schools_delta_pct,
            "students_delta": students_delta_pct,
            "teachers_delta": teachers_delta_pct,
            "student_attendance_delta": 0,
            "teacher_attendance_delta": 0,
            "hijri_date": hijri_date,
            "gregorian_date": gregorian_date,
            "last_updated": now.isoformat()
        }
        _cc_stats_cache["data"] = _result
        _cc_stats_cache["expires"] = _now_mono + _CC_STATS_TTL
        return _result
        
    except Exception as e:
        logger.error(f"Error fetching command center stats: {e}")
        # Return zeros on error - no mock data
        return {
            "registered_schools": 0,
            "registered_students": 0,
            "teachers_in_schools": 0,
            "independent_teachers": 0,
            "platform_accounts": 0,
            "pending_requests": 0,
            "ai_enabled_schools": 0,
            "student_attendance_rate": 0,
            "teacher_attendance_rate": 0,
            "schools_delta": 0,
            "students_delta": 0,
            "teachers_delta": 0,
            "student_attendance_delta": 0,
            "teacher_attendance_delta": 0,
            "hijri_date": "",
            "gregorian_date": "",
            "last_updated": datetime.now(timezone.utc).isoformat()
        }


