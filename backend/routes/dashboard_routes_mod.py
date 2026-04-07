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
from engines.sql_utils import gd_find, gd_find_one, gd_insert, gd_insert_many, gd_update_one, gd_update_many, gd_count, gd_delete_one, gd_delete_many, gd_distinct, gd_upsert, _gd_aggregate
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
        total_schools = await gd_count(db.session, "schools", school_filter)
        active_schools = await gd_count(db.session, "schools", {**base_school_filter, "status": "active"})
        pending_schools = await gd_count(db.session, "schools", {**base_school_filter, "status": "pending"})
        suspended_schools = await gd_count(db.session, "schools", {**base_school_filter, "status": "suspended"})
        setup_schools = await gd_count(db.session, "schools", {**base_school_filter, "status": "setup"})
        
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
            schools_list = await gd_find(db.session, "schools", school_filter)
            filtered_school_ids = [s.get("id") for s in schools_list]
            
            if filtered_school_ids:
                student_filter["school_id"] = {"$in": filtered_school_ids}
                teacher_filter["school_id"] = {"$in": filtered_school_ids}
        
        school_id_filter = {"school_id": {"$in": filtered_school_ids}} if filtered_school_ids else {}
        
        operations_filter = {**time_filter}
        if filtered_school_ids:
            operations_filter["tenant_id"] = {"$in": filtered_school_ids}
        
        (total_students, students_missing_data,
         total_teachers, teachers_without_classes, incomplete_schedules, teachers_without_rank,
         total_users, active_users,
         total_classes, total_subjects, pending_requests, total_operations) = await asyncio.gather(
            gd_count(db.session, "students", student_filter),
            gd_count(db.session, "students", {**student_filter, "$or": [{"parent_phone": None}, {"parent_phone": ""}]}),
            gd_count(db.session, "teachers", teacher_filter),
            gd_count(db.session, "teachers", {**teacher_filter, "assigned_classes": {"$size": 0}}),
            gd_count(db.session, "teachers", {**teacher_filter, "schedule_complete": False}),
            gd_count(db.session, "teachers", {**teacher_filter, "$or": [{"rank": None}, {"rank": ""}]}),
            gd_count(db.session, "users", {}),
            gd_count(db.session, "users", {"is_active": True}),
            gd_count(db.session, "classes", school_id_filter if school_id_filter else {}),
            gd_count(db.session, "subjects", school_id_filter if school_id_filter else {}),
            gd_count(db.session, "registration_requests", {"status": "pending"}),
            gd_count(db.session, "events", operations_filter),
        )
        schools_without_principal = 0
        
    else:
        tenant_id = current_user.get("tenant_id")
        total_schools = 1
        active_schools = 1
        pending_schools = 0
        suspended_schools = 0
        setup_schools = 0
        
        (total_users, active_users, total_students, total_teachers,
         total_classes, total_subjects, total_operations) = await asyncio.gather(
            gd_count(db.session, "users", {"tenant_id": tenant_id}),
            gd_count(db.session, "users", {"tenant_id": tenant_id, "is_active": True}),
            gd_count(db.session, "students", {"school_id": tenant_id}),
            gd_count(db.session, "teachers", {"school_id": tenant_id}),
            gd_count(db.session, "classes", {"school_id": tenant_id}),
            gd_count(db.session, "subjects", {"school_id": tenant_id}),
            gd_count(db.session, "events", {"tenant_id": tenant_id}),
        )
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
        
        (total_schools, active_schools, suspended_schools, pending_schools, schools_last_month,
         students_present_today, students_absent_today, teachers_present_today, teachers_absent_today,
         total_students, students_last_month, total_teachers, teachers_last_month,
         total_lessons_today_events, waiting_events,
         total_classes, active_users_today) = await asyncio.gather(
            gd_count(db.session, "schools", {}),
            gd_count(db.session, "schools", {"status": "active"}),
            gd_count(db.session, "schools", {"status": "suspended"}),
            gd_count(db.session, "schools", {"status": "pending"}),
            gd_count(db.session, "schools", {"created_at": {"$gte": last_month_str}}),
            gd_count(db.session, "attendance", {"user_type": "student", "status": "present", "date": {"$gte": today_str}}),
            gd_count(db.session, "attendance", {"user_type": "student", "status": "absent", "date": {"$gte": today_str}}),
            gd_count(db.session, "attendance", {"user_type": "teacher", "status": "present", "date": {"$gte": today_str}}),
            gd_count(db.session, "attendance", {"user_type": "teacher", "status": "absent", "date": {"$gte": today_str}}),
            gd_count(db.session, "students", {}),
            gd_count(db.session, "students", {"created_at": {"$gte": last_month_str}}),
            gd_count(db.session, "teachers", {}),
            gd_count(db.session, "teachers", {"created_at": {"$gte": last_month_str}}),
            gd_count(db.session, "events", {"event_type": {"$in": ["lesson_started", "lesson", "class_session"]}, "created_at": {"$gte": today_start.isoformat()}}),
            gd_count(db.session, "events", {"event_type": {"$in": ["waiting_session", "substitute_needed", "coverage_needed"]}, "status": "pending", "created_at": {"$gte": today_start.isoformat()}}),
            gd_count(db.session, "classes", {}),
            gd_count(db.session, "users", {"last_login": {"$gte": today_start.isoformat()}}),
        )
        
        student_total_tracked = students_present_today + students_absent_today
        student_attendance_percentage = (students_present_today / student_total_tracked * 100) if student_total_tracked > 0 else 0
        teacher_total_tracked = teachers_present_today + teachers_absent_today
        teacher_attendance_percentage = (teachers_present_today / teacher_total_tracked * 100) if teacher_total_tracked > 0 else 0
        
        total_lessons_today = total_lessons_today_events
        if total_lessons_today == 0:
            total_lessons_today = await gd_count(db.session, "schedules", {"date": {"$gte": today_str}})
        
        waiting_sessions = waiting_events
        if waiting_sessions == 0:
            waiting_sessions = await gd_count(db.session, "schedules", {"teacher_id": None, "date": {"$gte": today_str}})
        
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
            from middleware.cache_metrics import record_hit
            record_hit()
            return _cc_stats_cache["data"]
        from middleware.cache_metrics import record_miss
        record_miss()

        now = datetime.now(timezone.utc)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        last_month_start = (now - timedelta(days=30)).replace(hour=0, minute=0, second=0, microsecond=0)
        
        today_str = today_start.isoformat()[:10]
        last_month_str = last_month_start.isoformat()

        import asyncio
        
        (registered_schools, ai_enabled_schools, active_schools_cc, schools_delta,
         teachers_in_schools, independent_teachers, teachers_delta,
         total_users, school_bound_users, school_teachers_count,
         students_present_cc, students_total_cc,
         teacher_att_present, teacher_att_total,
         registered_students, students_delta, pending_requests) = await asyncio.gather(
            gd_count(db.session, "schools", {}),
            gd_count(db.session, "schools", {"ai_enabled": True}),
            gd_count(db.session, "schools", {"status": "active"}),
            gd_count(db.session, "schools", {"created_at": {"$gte": last_month_str}}),
            gd_count(db.session, "teachers", {}),
            gd_count(db.session, "teachers", {"school_id": None}),
            gd_count(db.session, "teachers", {"created_at": {"$gte": last_month_str}}),
            gd_count(db.session, "users", {}),
            gd_count(db.session, "users", {"role": {"$in": ["school_principal", "school_sub_admin", "school_manager"]}}),
            gd_count(db.session, "users", {"role": "teacher", "tenant_id": {"$ne": None}}),
            gd_count(db.session, "attendance", {"user_type": "student", "status": "present", "date": {"$gte": today_str}}),
            gd_count(db.session, "attendance", {"user_type": "student", "date": {"$gte": today_str}}),
            gd_count(db.session, "teacher_attendance", {"status": "present", "date": today_str}),
            gd_count(db.session, "teacher_attendance", {"date": today_str}),
            gd_count(db.session, "students", {}),
            gd_count(db.session, "students", {"created_at": {"$gte": last_month_str}}),
            gd_count(db.session, "registration_requests", {"status": "pending"}),
        )
        school_teachers = school_teachers_count
        students_present_today = students_present_cc
        students_total_today = students_total_cc
        teachers_present_today = teacher_att_present
        teachers_total_today = teacher_att_total

        platform_accounts = total_users - school_bound_users - school_teachers

        if ai_enabled_schools == 0:
            ai_enabled_schools = await gd_count(db.session, "schools", {"status": "active"})

        if teachers_total_today == 0:
            teachers_present_today = await gd_count(db.session, "attendance", {"user_type": "teacher", "status": "present", "date": {"$gte": today_str}})
            teachers_total_today = await gd_count(db.session, "attendance", {"user_type": "teacher", "date": {"$gte": today_str}})

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
        raise HTTPException(
            status_code=500,
            detail="حدث خطأ أثناء جلب إحصائيات مركز التحكم"
        )


