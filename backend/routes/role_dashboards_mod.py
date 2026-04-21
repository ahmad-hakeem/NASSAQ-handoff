"""
NASSAQ Route Module: Teacher, student, parent dashboards, contact teacher
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
from engines.sql_utils import gd_find, gd_find_one, gd_insert, gd_insert_many, gd_update_one, gd_update_many, gd_count, gd_delete_one, gd_delete_many, gd_distinct, _gd_aggregate


from shared_models import (
    SessionStatusEnum, ScheduleStatusEnum
)

router = APIRouter()



# ============== TEACHER DASHBOARD APIs ==============
TEACHER_ADMIN_ROLES = {"admin", "super_admin", "platform_admin", "school_admin"}

def _verify_teacher_access(teacher_id: str, current_user: dict):
    caller_teacher = current_user.get("teacher_id") or current_user.get("id")
    if caller_teacher != teacher_id and current_user.get("role") not in TEACHER_ADMIN_ROLES:
        raise HTTPException(status_code=403, detail="ليس لديك صلاحية للوصول لبيانات هذا المعلم")


async def _resolve_teacher_record(teacher_id: str):
    """
    Resolve the actual teachers-collection record from any of:
      - teachers.id (direct hit)
      - teachers.user_id (when caller passed the user id)
      - users.id -> teachers (matched strictly by school_id + unique email)

    Returns the teacher dict or None. This is needed because the frontend
    falls back to ``user.id`` when ``users.teacher_id`` is not populated,
    but admin-side links (teacher_class_assignments, teacher_assignments,
    schedule_sessions, ...) are stored against teachers.id, so a direct
    query by user.id returns nothing.

    SECURITY: name-based matching is intentionally NOT used because two
    teachers in the same school can share a full_name, which would let
    one teacher's "My Classes" page surface another teacher's data.
    Email is required for the user→teacher fallback, and the match must
    be unique (exactly one candidate). When ambiguous, we refuse to
    resolve and return None so the page shows "no classes" rather than
    leaking the wrong data; an admin must then explicitly link the
    user to the correct teachers row.
    """
    if not teacher_id:
        return None

    # 1) Direct match on teachers.id
    teacher = await gd_find_one(db.session, "teachers", {"id": teacher_id})
    if teacher:
        return teacher

    # 2) teachers row already linked via user_id
    teacher = await gd_find_one(db.session, "teachers", {"user_id": teacher_id})
    if teacher:
        return teacher

    # 3) Strict email-based fallback from users -> teachers
    user = await gd_find_one(db.session, "users", {"id": teacher_id})
    if not user or user.get("role") != "teacher":
        return None

    tenant_id = user.get("tenant_id") or user.get("school_id")
    email = (user.get("email") or "").strip().lower()
    if not tenant_id or not email:
        return None

    candidates = await gd_find(db.session, "teachers", {
        "school_id": tenant_id,
        "email": email,
    }, limit=2)

    if len(candidates) != 1:
        if len(candidates) > 1:
            logger.warning(
                "_resolve_teacher_record: ambiguous match for user %s "
                "in school %s (%d teachers share email)",
                teacher_id, tenant_id, len(candidates),
            )
        return None

    teacher = candidates[0]

    # Safe to backfill: the match is unique within the school AND keyed
    # on the verified login email of this very user.
    try:
        await gd_update_one(
            db.session, "users",
            {"id": teacher_id},
            {"$set": {"teacher_id": teacher.get("id")}}
        )
    except Exception as _e:
        logger.debug(f"_resolve_teacher_record: backfill users.teacher_id failed: {_e}")

    return teacher


@router.get("/teacher/dashboard/{teacher_id}")
async def get_teacher_dashboard(
    teacher_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    الحصول على بيانات لوحة تحكم المعلم
    - الفصول المسندة
    - عدد الطلاب
    - الحصص اليومية
    - الإحصائيات
    """
    _verify_teacher_access(teacher_id, current_user)
    # First try to find in teachers collection by id
    teacher = await gd_find_one(db.session, "teachers", {"id": teacher_id})
    
    # If not found, try to find by user_id
    if not teacher:
        teacher = await gd_find_one(db.session, "teachers", {"user_id": teacher_id})
    
    # If still not found, try to find in users and then match to teachers
    if not teacher:
        user = await gd_find_one(db.session, "users", {"id": teacher_id, "role": "teacher"})
        if user:
            tenant_id = user.get("tenant_id")
            if not tenant_id:
                raise HTTPException(status_code=403, detail="المعلم غير مرتبط بمدرسة / Teacher has no school assignment")
            lookup_filter = {
                "school_id": tenant_id,
                "$or": [
                    {"email": user.get("email")},
                    {"full_name": user.get("full_name")}
                ]
            }
            teacher = await gd_find_one(db.session, "teachers", lookup_filter)
    
    if not teacher:
        # Return default data if teacher not found in teachers collection
        # This allows the dashboard to work even if data is only in users collection
        user = await gd_find_one(db.session, "users", {"id": teacher_id})
        if user and user.get("role") == "teacher":
            fb_school_id = user.get("tenant_id") or ""
            fb_school = await gd_find_one(db.session, "schools", {"id": fb_school_id}) if fb_school_id else None
            fb_school = fb_school or {}
            return {
                "teacher": {
                    "id": teacher_id,
                    "name": user.get("full_name") or "",
                    "full_name": user.get("full_name") or "",
                    "rank": "",
                    "qualification": "",
                    "specialization": "",
                    "email": user.get("email") or "",
                    "phone": "",
                    "hire_date": "",
                    "school_id": fb_school_id
                },
                "school_name": fb_school.get("name_ar") or fb_school.get("name") or "",
                "school_city": fb_school.get("city") or "",
                "school_type": fb_school.get("type") or "",
                "school_stage": fb_school.get("educational_stage") or fb_school.get("stage") or "",
                "stats": {
                    "my_classes": 0,
                    "my_students": 0,
                    "today_lessons": 0,
                    "pending_attendance": 0,
                    "weekly_sessions": 0,
                    "subjects_count": 0
                },
                "classes": [],
                "subjects": [],
                "subject_names": [],
                "today_schedule": [],
                "recent_activities": []
            }
        raise HTTPException(status_code=404, detail="المعلم غير موجود")
    
    # Use teacher's id from teachers collection for lookups
    actual_teacher_id = teacher.get("id")
    school_id = teacher.get("school_id")
    
    # Get teacher assignments using actual_teacher_id
    assignments = await gd_find(db.session, "teacher_assignments", {
        "teacher_id": actual_teacher_id,
        "is_active": True
    }, limit=100)
    
    class_ids = list(set(a.get("class_id") for a in assignments if a.get("class_id")))
    subject_ids = list(set(a.get("subject_id") for a in assignments if a.get("subject_id")))
    
    classes = await gd_find(db.session, "classes", {"id": {"$in": class_ids}}, limit=50)
    total_students = 0
    for cls_item in classes:
        count = await gd_count(db.session, "students", {"class_id": cls_item.get("id"), "is_active": True})
        cls_item["student_count"] = count
        total_students += count
    
    # Get subjects
    subjects = await gd_find(db.session, "subjects", {"id": {"$in": subject_ids}}, limit=50)
    
    # Get today's schedule
    today_day = ["sunday", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday"][datetime.now().weekday()]
    # Map Python weekday to our system
    day_map = {0: "monday", 1: "tuesday", 2: "wednesday", 3: "thursday", 4: "friday", 5: "saturday", 6: "sunday"}
    today_day = day_map.get(datetime.now().weekday(), "sunday")
    
    # Get current schedule
    schedule = await gd_find_one(db.session, "schedules", {
        "school_id": school_id,
        "status": {"$in": [ScheduleStatusEnum.DRAFT.value, ScheduleStatusEnum.PUBLISHED.value]}
    })
    
    today_lessons = []

    # Try schedule_sessions first (manual scheduling system)
    schedule_sessions_today = []
    if schedule:
        schedule_sessions_today = await gd_find(db.session, "schedule_sessions", {
            "schedule_id": schedule.get("id"),
            "teacher_id": actual_teacher_id,
            "day_of_week": today_day
        }, limit=20)

    if schedule_sessions_today:
        # Get time slots
        slot_ids = [s.get("time_slot_id") for s in schedule_sessions_today if s.get("time_slot_id")]
        slots = await gd_find(db.session, "time_slots", {"id": {"$in": slot_ids}}, limit=20) if slot_ids else []
        slot_map = {s.get("id"): s for s in slots}

        for session in schedule_sessions_today:
            slot = slot_map.get(session.get("time_slot_id"), {})
            assignment = next((a for a in assignments if a.get("id") == session.get("assignment_id")), {})
            class_info = next((c for c in classes if c.get("id") == (assignment.get("class_id") or session.get("class_id"))), {})
            subject_info = next((s for s in subjects if s.get("id") == (assignment.get("subject_id") or session.get("subject_id"))), {})
            lesson_time = slot.get("start_time") or session.get("start_time", "")
            lesson_period = slot.get("slot_number") or session.get("slot_number", 0)
            today_lessons.append({
                "id": session.get("id"),
                "schedule_session_id": session.get("id"),
                "time": lesson_time,
                "start_time": lesson_time,
                "end_time": slot.get("end_time") or session.get("end_time", ""),
                "period": lesson_period,
                "slot_number": lesson_period,
                "subject": subject_info.get("name_ar") or session.get("subject_name") or "غير محدد",
                "subject_name": subject_info.get("name_ar") or session.get("subject_name") or "غير محدد",
                "class_name": class_info.get("name") or session.get("class_name") or "غير محدد",
                "class_id": class_info.get("id") or session.get("class_id"),
                "subject_id": subject_info.get("id") or session.get("subject_id"),
            })
    else:
        timetable = await gd_find_one(db.session, "timetables", {"school_id": school_id, "status": "published"},
            sort=[("updated_at", -1), ("created_at", -1)]) or await gd_find_one(db.session, "timetables", {"school_id": school_id},
            sort=[("created_at", -1)])
        tt_query = {
            "teacher_id": actual_teacher_id,
            "day_of_week": today_day
        }
        if timetable:
            tt_query["timetable_id"] = timetable.get("id")
        timetable_sessions_today = await gd_find(db.session, "timetable_sessions", tt_query, limit=20)

        seen_periods = set()
        for session in timetable_sessions_today:
            period_key = session.get("period_number", 0)
            if period_key in seen_periods:
                continue
            seen_periods.add(period_key)
            class_info = await gd_find_one(db.session, "classes", {"id": session.get("class_id")}) or {}
            subject_info = await gd_find_one(db.session, "subjects", {"id": session.get("subject_id")}) or {}
            today_lessons.append({
                "id": session.get("id"),
                "schedule_session_id": session.get("id"),
                "time": session.get("start_time", ""),
                "start_time": session.get("start_time", ""),
                "end_time": session.get("end_time", ""),
                "period": session.get("period_number", 0),
                "slot_number": session.get("period_number", 0),
                "subject": subject_info.get("name_ar") or subject_info.get("name_en") or "مادة",
                "subject_name": subject_info.get("name_ar") or subject_info.get("name_en") or "مادة",
                "class_name": class_info.get("name") or "فصل",
                "class_id": session.get("class_id"),
                "subject_id": session.get("subject_id"),
            })

    today_lessons.sort(key=lambda x: x.get("period", 0) or 0)
    
    # Get pending attendance (classes where attendance not recorded today)
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    recorded_attendance = await gd_find(db.session, "attendance", {
        "teacher_id": actual_teacher_id,
        "date": today_str
    }, limit=50)
    recorded_class_ids = [a.get("class_id") for a in recorded_attendance]
    pending_attendance = len([c for c in class_ids if c not in recorded_class_ids])
    
    # Recent activities
    recent_activities = await gd_find(db.session, "audit_log", {
        "user_id": current_user.get("id"),
        "school_id": school_id
    }, order_by="timestamp", desc_order=True, limit=5)
    
    school = await gd_find_one(db.session, "schools", {"id": school_id}) or {}
    school_name = school.get("name_ar") or school.get("name") or school.get("name_en") or ""
    school_city = school.get("city") or ""
    school_type = school.get("type") or school.get("school_type") or ""
    school_stage = school.get("educational_stage") or school.get("stage") or ""
    primary_subject = None
    primary_sub_id = teacher.get("primary_subject_id") or teacher.get("specialization")
    if primary_sub_id:
        sub_doc = await gd_find_one(db.session, "subjects", {"id": primary_sub_id})
        if sub_doc:
            primary_subject = sub_doc.get("name_ar") or sub_doc.get("name_en")
        elif not primary_sub_id.startswith("sub-"):
            primary_subject = primary_sub_id
    subject_names = [s.get("name_ar") or s.get("name_en") or "" for s in subjects]

    return {
        "teacher": {
            "id": teacher.get("id"),
            "name": teacher.get("full_name") or teacher.get("name"),
            "full_name": teacher.get("full_name") or teacher.get("name"),
            "rank": teacher.get("rank") or "",
            "qualification": teacher.get("qualification") or "",
            "specialization": primary_subject or "",
            "email": teacher.get("email") or "",
            "phone": teacher.get("phone") or "",
            "hire_date": str(teacher.get("hire_date") or ""),
            "school_id": school_id
        },
        "school_name": school_name,
        "school_city": school_city,
        "school_type": school_type,
        "school_stage": school_stage,
        "stats": {
            "my_classes": len(class_ids),
            "my_students": total_students,
            "today_lessons": len(today_lessons),
            "pending_attendance": pending_attendance,
            "subjects_count": len(subject_ids),
            "weekly_sessions": sum(a.get("weekly_sessions", 0) for a in assignments)
        },
        "today_schedule": today_lessons,
        "classes": [{"id": c.get("id"), "name": c.get("name"), "students": c.get("student_count", 0)} for c in classes],
        "subjects": [{"id": s.get("id"), "name": s.get("name_ar") or s.get("name_en")} for s in subjects],
        "subject_names": subject_names,
        "recent_activities": [
            {"type": a.get("action"), "message": a.get("details", {}).get("description", a.get("action")), "time": a.get("timestamp")}
            for a in recent_activities
        ]
    }





# ============== STUDENT DASHBOARD APIs ==============
@router.get("/student/dashboard/{student_id}")
async def get_student_dashboard(
    student_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    الحصول على بيانات لوحة تحكم الطالب
    - الجدول اليومي
    - الدرجات
    - نسبة الحضور
    - الإشعارات
    """
    student = await gd_find_one(db.session, "students", {"id": student_id})
    if not student:
        raise HTTPException(status_code=404, detail="الطالب غير موجود")

    user_tenant = current_user.get("tenant_id")
    student_school = student.get("school_id")
    if user_tenant:
        if not student_school or user_tenant != student_school:
            raise HTTPException(status_code=403, detail="لا يمكنك الوصول إلى بيانات طالب من مدرسة أخرى")
    
    school_id = student_school
    class_id = student.get("class_id")
    
    # Get class info
    class_info = await gd_find_one(db.session, "classes", {"id": class_id})
    
    # Get today's schedule for the class
    day_map = {0: "monday", 1: "tuesday", 2: "wednesday", 3: "thursday", 4: "friday", 5: "saturday", 6: "sunday"}
    today_day = day_map.get(datetime.now().weekday(), "sunday")
    
    schedule = await gd_find_one(db.session, "schedules", {
        "school_id": school_id,
        "status": {"$in": [ScheduleStatusEnum.DRAFT.value, ScheduleStatusEnum.PUBLISHED.value]}
    })
    
    today_lessons = []
    if schedule:
        sessions = await gd_find(db.session, "schedule_sessions", {
            "schedule_id": schedule.get("id"),
            "class_id": class_id,
            "day_of_week": today_day,
            "status": SessionStatusEnum.SCHEDULED.value
        }, limit=20)
        
        # Get details
        slot_ids = list(set(s.get("time_slot_id") for s in sessions))
        teacher_ids = list(set(s.get("teacher_id") for s in sessions if s.get("teacher_id")))
        subject_ids = list(set(s.get("subject_id") for s in sessions if s.get("subject_id")))
        
        slots = await gd_find(db.session, "time_slots", {"id": {"$in": slot_ids}}, limit=20)
        teachers = await gd_find(db.session, "teachers", {"id": {"$in": teacher_ids}}, limit=20)
        subjects = await gd_find(db.session, "subjects", {"id": {"$in": subject_ids}}, limit=20)
        
        slot_map = {s.get("id"): s for s in slots}
        teacher_map = {t.get("id"): t for t in teachers}
        subject_map = {s.get("id"): s for s in subjects}
        
        for session in sessions:
            slot = slot_map.get(session.get("time_slot_id"), {})
            teacher = teacher_map.get(session.get("teacher_id"), {})
            subject = subject_map.get(session.get("subject_id"), {})
            
            today_lessons.append({
                "time": slot.get("start_time", ""),
                "period": slot.get("slot_number", 0),
                "subject": subject.get("name_ar") or subject.get("name_en") or "غير محدد",
                "teacher": teacher.get("full_name", "غير محدد"),
                "room": session.get("room_name", "")
            })
        
        today_lessons.sort(key=lambda x: x.get("period", 0))
    
    # Get attendance summary
    attendance_records = await gd_find(db.session, "attendance", {
        "student_id": student_id,
        "school_id": school_id
    }, limit=200)
    
    total_days = len(attendance_records)
    present_days = len([a for a in attendance_records if a.get("status") == "present"])
    attendance_rate = round((present_days / total_days * 100) if total_days > 0 else 100, 1)
    
    recent_grades = []
    submissions = await gd_find(db.session, "assessment_submissions", {
        "student_id": student_id
    }, order_by="submitted_at", desc_order=True, limit=10)
    for sub in submissions:
        assessment = await gd_find_one(db.session, "assessments", {"id": sub.get("assessment_id")})
        subject_name = ""
        if assessment and assessment.get("subject_id"):
            subj = await gd_find_one(db.session, "subjects", {"id": assessment["subject_id"]})
            subject_name = subj.get("name_ar", subj.get("name", "")) if subj else assessment.get("title", "")
        elif assessment:
            subject_name = assessment.get("title", "")
        grade_val = sub.get("grade", sub.get("score", 0))
        recent_grades.append({
            "subject": subject_name or "غير محدد",
            "grade": grade_val,
            "date": sub.get("submitted_at", sub.get("graded_at", datetime.now().strftime("%Y-%m-%d")))
        })
    
    average_grade = sum(g.get("grade", 0) for g in recent_grades) / len(recent_grades) if recent_grades else 0
    
    # Get notifications
    notifications = await gd_find(db.session, "notifications", {
        "$or": [
            {"target_id": student_id},
            {"target_type": "all", "school_id": school_id}
        ]
    }, order_by="created_at", desc_order=True, limit=5)
    
    return {
        "student": {
            "id": student.get("id"),
            "name": student.get("full_name"),
            "class_name": class_info.get("name") if class_info else "غير محدد",
            "school_id": school_id
        },
        "stats": {
            "attendance_rate": attendance_rate,
            "average_grade": round(average_grade, 1),
            "present_days": present_days,
            "absent_days": total_days - present_days,
            "total_lessons_today": len(today_lessons)
        },
        "today_schedule": today_lessons,
        "recent_grades": recent_grades,
        "notifications": [
            {"title": n.get("title"), "message": n.get("message"), "time": n.get("created_at"), "type": n.get("type", "info")}
            for n in notifications
        ]
    }





# ============== PARENT DASHBOARD APIs ==============
@router.get("/parent/dashboard/{parent_id}")
async def get_parent_dashboard(
    parent_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    الحصول على بيانات لوحة تحكم ولي الأمر
    - قائمة الأبناء
    - ملخص كل ابن (حضور، درجات، سلوك)
    """
    parent = await gd_find_one(db.session, "parents", {"id": parent_id})
    if not parent:
        raise HTTPException(status_code=404, detail="ولي الأمر غير موجود")
    
    school_id = parent.get("school_id")
    
    # Get children
    student_ids = parent.get("student_ids", [])
    children_data = []
    
    for student_id in student_ids:
        student = await gd_find_one(db.session, "students", {"id": student_id})
        if not student:
            continue
        
        class_info = await gd_find_one(db.session, "classes", {"id": student.get("class_id")})
        
        # Get attendance summary
        attendance_records = await gd_find(db.session, "attendance", {
            "student_id": student_id
        }, limit=200)
        
        total_days = len(attendance_records)
        present_days = len([a for a in attendance_records if a.get("status") == "present"])
        absent_days = len([a for a in attendance_records if a.get("status") == "absent"])
        late_days = len([a for a in attendance_records if a.get("status") == "late"])
        attendance_rate = round((present_days / total_days * 100) if total_days > 0 else 100, 1)
        
        grade_records = await gd_find(db.session, "grades", {
            "student_id": student_id
        }, order_by="recorded_at", desc_order=True, limit=10)
        recent_grades = [
            {
                "subject": g.get("subject_name", "غير محدد"),
                "grade": g.get("score", 0),
                "date": g.get("recorded_at", ""),
            }
            for g in grade_records
        ]
        average_grade = (
            sum(g.get("grade", 0) for g in recent_grades) / len(recent_grades)
            if recent_grades
            else 0
        )

        behaviour_records = await gd_find(db.session, "behaviour_records", {
            "student_id": student_id
        }, order_by="created_at", desc_order=True, limit=5)
        behaviour_notes = [
            {
                "type": b.get("type", "info"),
                "note": b.get("note", ""),
                "date": b.get("created_at", ""),
            }
            for b in behaviour_records
        ]
        
        # Get today's schedule
        day_map = {0: "monday", 1: "tuesday", 2: "wednesday", 3: "thursday", 4: "friday", 5: "saturday", 6: "sunday"}
        today_day = day_map.get(datetime.now().weekday(), "sunday")
        
        schedule = await gd_find_one(db.session, "schedules", {
            "school_id": school_id,
            "status": {"$in": [ScheduleStatusEnum.DRAFT.value, ScheduleStatusEnum.PUBLISHED.value]}
        })
        
        today_schedule = []
        if schedule:
            sessions = await gd_find(db.session, "schedule_sessions", {
                "schedule_id": schedule.get("id"),
                "class_id": student.get("class_id"),
                "day_of_week": today_day
            }, limit=10)
            
            for session in sessions:
                slot = await gd_find_one(db.session, "time_slots", {"id": session.get("time_slot_id")})
                teacher = await gd_find_one(db.session, "teachers", {"id": session.get("teacher_id")})
                subject = await gd_find_one(db.session, "subjects", {"id": session.get("subject_id")})
                
                today_schedule.append({
                    "time": slot.get("start_time", "") if slot else "",
                    "subject": subject.get("name_ar") if subject else "غير محدد",
                    "teacher": teacher.get("full_name") if teacher else "غير محدد"
                })
        
        children_data.append({
            "id": student.get("id"),
            "name": student.get("full_name"),
            "class_name": class_info.get("name") if class_info else "غير محدد",
            "avatar": student.get("avatar_url"),
            "stats": {
                "attendance_rate": attendance_rate,
                "average_grade": round(average_grade, 1),
                "absences": absent_days,
                "lates": late_days
            },
            "recent_grades": recent_grades,
            "behaviour_notes": behaviour_notes,
            "today_schedule": today_schedule[:5]
        })
    
    # Get notifications for parent
    notifications = await gd_find(db.session, "notifications", {
        "$or": [
            {"target_id": parent_id},
            {"target_id": {"$in": student_ids}},
            {"target_type": "all", "school_id": school_id}
        ]
    }, order_by="created_at", desc_order=True, limit=10)
    
    return {
        "parent": {
            "id": parent.get("id"),
            "name": parent.get("full_name"),
            "phone": parent.get("phone"),
            "email": parent.get("email")
        },
        "children_count": len(children_data),
        "children": children_data,
        "notifications": [
            {"title": n.get("title"), "message": n.get("message"), "time": n.get("created_at"), "type": n.get("type", "info")}
            for n in notifications
        ]
    }





# ============== CONTACT TEACHER API ==============
@router.post("/parent/contact-teacher")
async def parent_contact_teacher(
    teacher_id: str,
    student_id: str,
    subject: str,
    message: str,
    current_user: dict = Depends(require_roles([UserRole.PARENT]))
):
    """
    إرسال رسالة من ولي الأمر للمعلم
    """
    parent_id = current_user.get("id")
    
    # Verify parent has this student
    parent = await gd_find_one(db.session, "parents", {"id": parent_id})
    if not parent or student_id not in parent.get("student_ids", []):
        raise HTTPException(status_code=403, detail="غير مصرح لك بالتواصل بشأن هذا الطالب")
    
    # Get teacher
    teacher = await gd_find_one(db.session, "teachers", {"id": teacher_id})
    if not teacher:
        raise HTTPException(status_code=404, detail="المعلم غير موجود")
    
    # Create message
    msg_id = str(uuid.uuid4())
    msg_doc = {
        "id": msg_id,
        "type": "parent_teacher_message",
        "from_id": parent_id,
        "from_type": "parent",
        "from_name": parent.get("full_name"),
        "to_id": teacher_id,
        "to_type": "teacher",
        "to_name": teacher.get("full_name"),
        "student_id": student_id,
        "subject": subject,
        "message": message,
        "status": "sent",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "read": False
    }
    
    await gd_insert(db.session, "messages", msg_doc)
    
    # Create notification for teacher
    await gd_insert(db.session, "notifications", {
        "id": str(uuid.uuid4()),
        "type": "parent_message",
        "title": f"رسالة من ولي أمر: {parent.get('full_name')}",
        "message": subject[:100],
        "target_id": teacher.get("user_id"),
        "target_type": "user",
        "school_id": parent.get("school_id"),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "read": False
    })
    
    return {
        "success": True,
        "message_id": msg_id,
        "message_ar": "تم إرسال الرسالة بنجاح",
        "message_en": "Message sent successfully"
    }





# ============== TEACHER MODULE APIs ==============

@router.get("/teacher/sessions/{teacher_id}")
async def get_teacher_sessions_list(
    teacher_id: str,
    current_user: dict = Depends(get_current_user)
):
    _verify_teacher_access(teacher_id, current_user)
    teacher = await _resolve_teacher_record(teacher_id)
    resolved_teacher_id = teacher.get("id") if teacher else teacher_id
    sessions_list = await gd_find(db.session, "teacher_sessions", {"teacher_id": resolved_teacher_id}, order_by="created_at", desc_order=True, limit=200)

    for s in sessions_list:
        if not s.get("class_name") and s.get("class_id"):
            cls = await gd_find_one(db.session, "classes", {"id": s["class_id"]})
            s["class_name"] = cls.get("name", "") if cls else ""
        if not s.get("subject_name") and s.get("subject_id"):
            subj = await gd_find_one(db.session, "subjects", {"id": s["subject_id"]})
            s["subject_name"] = subj.get("name", "") if subj else ""

    return {"sessions": sessions_list}


@router.get("/teacher/classes/{teacher_id}")
async def get_teacher_classes(
    teacher_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Get all classes assigned to a teacher with enriched data
    جلب جميع الفصول المسندة للمعلم مع بيانات مُثرَاة
    """
    _verify_teacher_access(teacher_id, current_user)

    teacher = await _resolve_teacher_record(teacher_id)
    school_id = teacher.get("school_id") if teacher else None
    # Use the actual teachers.id for queries — admin-side assignments are
    # stored against teachers.id, not users.id.
    resolved_teacher_id = teacher.get("id") if teacher else teacher_id

    assignments = await gd_find(db.session, "teacher_assignments", {
        "teacher_id": resolved_teacher_id,
        "is_active": True
    }, limit=200)

    class_ids_from_assignments = set(a.get("class_id") for a in assignments if a.get("class_id"))

    tca_docs = await gd_find(db.session, "teacher_class_assignments", {
        "teacher_id": resolved_teacher_id
    }, limit=200)
    class_ids_from_tca = set(d.get("class_id") for d in tca_docs if d.get("class_id"))

    all_class_ids = list(class_ids_from_assignments | class_ids_from_tca)
    if not all_class_ids:
        return []

    classes = await gd_find(db.session, "classes", {"id": {"$in": all_class_ids}}, limit=100)

    schedule = await gd_find_one(db.session, "schedules", {"school_id": school_id, "status": {"$in": ["draft", "published"]}}) if school_id else None
    schedule_sessions = []
    time_slots_map = {}
    if schedule:
        schedule_sessions = await gd_find(db.session, "schedule_sessions", {"schedule_id": schedule["id"], "teacher_id": resolved_teacher_id, "status": "scheduled"}, limit=500)
        ts_docs = await gd_find(db.session, "time_slots", {"school_id": school_id, "is_break": {"$ne": True}}, limit=50)
        for ts in ts_docs:
            ts_id = ts.get("id") or ts.get("slot_number")
            if ts_id is not None:
                time_slots_map[str(ts_id)] = ts

    now = datetime.now()
    js_day_map = {6: "sunday", 0: "monday", 1: "tuesday", 2: "wednesday", 3: "thursday"}
    today_key = js_day_map.get(now.weekday())
    day_order = ["sunday", "monday", "tuesday", "wednesday", "thursday"]

    enriched_classes = []
    for cls in classes:
        cls_id = cls.get("id")
        class_assignments = [a for a in assignments if a.get("class_id") == cls_id]

        student_count = await gd_count(db.session, "students", {"class_id": cls_id, "is_active": True})

        subject_ids = list(set(a.get("subject_id") for a in class_assignments if a.get("subject_id")))
        if not subject_ids and schedule_sessions:
            subject_ids = list(set(
                s.get("subject_id") for s in schedule_sessions
                if s.get("class_id") == cls_id and s.get("subject_id")
            ))
        if not subject_ids:
            ta_for_class = await gd_find(db.session, "teacher_assignments", {"class_id": cls_id, "is_active": True}, limit=20)
            subject_ids = list(set(a.get("subject_id") for a in ta_for_class if a.get("subject_id")))
        if not subject_ids:
            subject_ids = list(set(a.get("subject_id") for a in assignments if a.get("subject_id")))

        subjects = []
        if subject_ids:
            subjects = await gd_find(db.session, "subjects", {"id": {"$in": subject_ids}}, limit=20)
        subject_names = [s.get("name_ar") or s.get("name_en") or "مادة" for s in subjects]

        class_schedule = [s for s in schedule_sessions if s.get("class_id") == cls_id]
        weekly_periods = len(class_schedule) or sum(a.get("weekly_sessions", 0) for a in class_assignments)

        next_session_info = None
        if class_schedule and today_key:
            today_idx = day_order.index(today_key) if today_key in day_order else -1
            now_minutes = now.hour * 60 + now.minute
            best = None
            for s in class_schedule:
                s_day = s.get("day_of_week", "").lower()
                if s_day not in day_order:
                    continue
                s_idx = day_order.index(s_day)
                ts_id = s.get("time_slot_id") or s.get("slot_number")
                ts = time_slots_map.get(str(ts_id), {})
                start_str = ts.get("start_time", s.get("start_time", ""))
                try:
                    parts = start_str.replace(":", " ").split()
                    s_min = int(parts[0]) * 60 + int(parts[1])
                except (ValueError, IndexError, TypeError):
                    s_min = 0
                if s_idx > today_idx or (s_idx == today_idx and s_min > now_minutes):
                    dist = (s_idx - today_idx) * 1440 + (s_min - now_minutes)
                else:
                    dist = (s_idx - today_idx + 5) * 1440 + (s_min - now_minutes)
                if best is None or dist < best[0]:
                    subj = next((sb for sb in subjects if sb.get("id") == s.get("subject_id")), {})
                    best = (dist, {
                        "day": s_day,
                        "start_time": ts.get("start_time", s.get("start_time", "")),
                        "end_time": ts.get("end_time", s.get("end_time", "")),
                        "subject_name": subj.get("name_ar") or subj.get("name_en") or "",
                        "slot_number": ts.get("slot_number", s.get("slot_number")),
                        "room_name": s.get("room_name", ""),
                    })
            if best:
                next_session_info = best[1]

        grade_name = cls.get("grade_name", "")
        if not grade_name:
            gl = cls.get("grade_level") or cls.get("grade_id", "")
            grade_map = {"1": "الأول", "2": "الثاني", "3": "الثالث", "4": "الرابع", "5": "الخامس", "6": "السادس"}
            grade_name = f"الصف {grade_map.get(str(gl), gl)}" if gl else ""

        status = "active"
        if not class_schedule:
            status = "no_upcoming"

        enriched_classes.append({
            **cls,
            "student_count": student_count,
            "subjects": subject_names,
            "weekly_periods": weekly_periods,
            "grade_name": grade_name,
            "next_session": next_session_info,
            "status": status,
            "schedule_count": len(class_schedule),
        })

    enriched_classes.sort(key=lambda c: (c.get("grade_level", "0"), c.get("name", "")))
    return enriched_classes


@router.get("/teacher/schedule/{teacher_id}")
async def get_teacher_schedule(
    teacher_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Get teacher's schedule
    جلب جدول المعلم
    """
    _verify_teacher_access(teacher_id, current_user)
    teacher = await _resolve_teacher_record(teacher_id)
    if not teacher:
        return []

    school_id = teacher.get("school_id")
    resolved_teacher_id = teacher.get("id") or teacher_id

    schedule_sessions_list = []

    schedule = await gd_find_one(db.session, "schedules", {
        "school_id": school_id,
        "status": {"$in": ["draft", "published"]}
    })

    if schedule:
        schedule_sessions_list = await gd_find(db.session, "schedule_sessions", {
            "schedule_id": schedule.get("id"),
            "teacher_id": resolved_teacher_id,
            "status": "scheduled"
        }, limit=100)

    if schedule_sessions_list:
        for session in schedule_sessions_list:
            assignment = await gd_find_one(db.session, "teacher_assignments", {"id": session.get("assignment_id")})
            if assignment:
                cls = await gd_find_one(db.session, "classes", {"id": assignment.get("class_id")})
                subject = await gd_find_one(db.session, "subjects", {"id": assignment.get("subject_id")})
                session["class_name"] = cls.get("name") if cls else "غير محدد"
                session["class_id"] = assignment.get("class_id")
                session["subject_name"] = (subject.get("name_ar") or subject.get("name_en")) if subject else "غير محدد"
            slot = await gd_find_one(db.session, "time_slots", {"id": session.get("time_slot_id")})
            if slot:
                session["slot_number"] = slot.get("slot_number")
                session["start_time"] = slot.get("start_time")
                session["end_time"] = slot.get("end_time")
            if not session.get("room_name"):
                session["room_name"] = session.get("room_number", "")
            if assignment and not session.get("subject_id"):
                session["subject_id"] = assignment.get("subject_id")
        return schedule_sessions_list

    timetable = await gd_find_one(db.session, "timetables", {"school_id": school_id, "status": "published"},
        sort=[("updated_at", -1), ("created_at", -1)]) or await gd_find_one(db.session, "timetables", {"school_id": school_id},
        sort=[("created_at", -1)])
    timetable_query = {"teacher_id": resolved_teacher_id, "school_id": school_id}
    if timetable:
        timetable_query["timetable_id"] = timetable.get("id")
    timetable_sessions = await gd_find(db.session, "timetable_sessions", timetable_query, order_by="day_of_week", desc_order=False, limit=200)

    seen_slots = set()
    unique_sessions = []
    for ts in timetable_sessions:
        key = (ts.get("day_of_week"), ts.get("period_number"))
        if key not in seen_slots:
            seen_slots.add(key)
            unique_sessions.append(ts)
    timetable_sessions = unique_sessions

    day_order = {"sunday": 0, "monday": 1, "tuesday": 2, "wednesday": 3, "thursday": 4}
    enriched = []
    for ts in timetable_sessions:
        cls = await gd_find_one(db.session, "classes", {"id": ts.get("class_id")}) or {}
        subject = await gd_find_one(db.session, "subjects", {"id": ts.get("subject_id")}) or {}
        enriched.append({
            "id": ts.get("id"),
            "schedule_session_id": ts.get("id"),
            "day_of_week": ts.get("day_of_week"),
            "period_number": ts.get("period_number"),
            "slot_number": ts.get("period_number"),
            "start_time": ts.get("start_time"),
            "end_time": ts.get("end_time"),
            "class_id": ts.get("class_id"),
            "class_name": cls.get("name", "فصل"),
            "subject_id": ts.get("subject_id"),
            "subject_name": subject.get("name_ar") or subject.get("name_en") or "مادة",
            "session_type": ts.get("session_type", "class"),
            "room_name": ts.get("room_name", ts.get("room_number", "")),
        })
    enriched.sort(key=lambda x: (day_order.get(x.get("day_of_week", ""), 9), x.get("period_number", 0)))
    return enriched


@router.get("/teacher/assessments/{teacher_id}")
async def get_teacher_assessments(
    teacher_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Get assessments created by teacher
    جلب تقييمات المعلم
    """
    _verify_teacher_access(teacher_id, current_user)
    teacher = await _resolve_teacher_record(teacher_id)
    resolved_teacher_id = teacher.get("id") if teacher else teacher_id
    assessments = await gd_find(db.session, "assessments", {
        "teacher_id": resolved_teacher_id
    }, order_by="created_at", desc_order=True, limit=100)
    
    # Enrich with class names
    for assessment in assessments:
        if assessment.get("class_id"):
            cls = await gd_find_one(db.session, "classes", {"id": assessment.get("class_id")})
            assessment["class_name"] = cls.get("name") if cls else ""
    
    return assessments


@router.get("/assessments/{assessment_id}/grades")
async def get_assessment_grades(
    assessment_id: str,
    current_user: dict = Depends(require_roles([UserRole.TEACHER, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.SCHOOL_SUB_ADMIN, UserRole.PLATFORM_ADMIN]))
):
    """Get grades for an assessment"""
    if current_user.get("role") != UserRole.PLATFORM_ADMIN:
        assessment = await gd_find_one(db.session, "assessments", {"id": assessment_id})
        if not assessment:
            raise HTTPException(status_code=404, detail="Assessment not found")
        user_tenant = current_user.get("tenant_id")
        if user_tenant and assessment.get("school_id") and assessment["school_id"] != user_tenant:
            raise HTTPException(status_code=403, detail="Access denied")
    grades = await gd_find(db.session, "grades", {"assessment_id": assessment_id}, limit=200)
    return grades


@router.post("/assessments/{assessment_id}/grades")
async def save_assessment_grades(
    assessment_id: str,
    data: dict = Body(...),
    current_user: dict = Depends(require_roles([UserRole.TEACHER, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.SCHOOL_SUB_ADMIN, UserRole.PLATFORM_ADMIN]))
):
    """Save grades for assessment - حفظ درجات التقييم"""
    if current_user.get("role") != UserRole.PLATFORM_ADMIN:
        assessment = await gd_find_one(db.session, "assessments", {"id": assessment_id})
        if not assessment:
            raise HTTPException(status_code=404, detail="Assessment not found")
        user_tenant = current_user.get("tenant_id")
        if user_tenant and assessment.get("school_id") and assessment["school_id"] != user_tenant:
            raise HTTPException(status_code=403, detail="Access denied")
    grades = data.get("grades", [])
    
    for grade in grades:
        grade_record = {
            "id": str(uuid.uuid4()),
            "assessment_id": assessment_id,
            "student_id": grade.get("student_id"),
            "score": grade.get("score"),
            "notes": grade.get("notes"),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "graded_by": current_user["id"]
        }
        
        # Upsert grade
        await gd_update_one(db.session, "grades", {"assessment_id": assessment_id, "student_id": grade.get("student_id")}, grade_record)
    
    # Update assessment status
    await gd_update_one(db.session, "assessments", {"id": assessment_id}, {"status": "graded", "graded_at": datetime.now(timezone.utc).isoformat()})
    
    return {"message": "تم حفظ الدرجات"}


@router.get("/students/{student_id}/grades")
async def get_student_grades(
    student_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get all grades for a student"""
    grades = await gd_find(db.session, "grades", {"student_id": student_id}, limit=100)
    
    # Enrich with assessment info
    for grade in grades:
        assessment = await gd_find_one(db.session, "assessments", {"id": grade.get("assessment_id")})
        if assessment:
            grade["assessment_name"] = assessment.get("name")
            grade["type"] = assessment.get("type")
            grade["max_score"] = assessment.get("max_score", 100)
    
    return grades


@router.get("/students/{student_id}/attendance-stats")
async def get_student_attendance_stats(
    student_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get attendance statistics for a student"""
    total = await gd_count(db.session, "attendance", {"student_id": student_id})
    present = await gd_count(db.session, "attendance", {"student_id": student_id, "status": "present"})
    absent = await gd_count(db.session, "attendance", {"student_id": student_id, "status": "absent"})
    late = await gd_count(db.session, "attendance", {"student_id": student_id, "status": "late"})
    
    rate = (present / total * 100) if total > 0 else 0
    
    return {
        "total": total,
        "present": present,
        "absent": absent,
        "late": late,
        "rate": round(rate, 1)
    }


@router.get("/behavior")
async def get_behavior_records(
    class_id: str = Query(None),
    student_id: str = Query(None),
    current_user: dict = Depends(get_current_user)
):
    """Get behavior records"""
    query = {}
    if class_id:
        query["class_id"] = class_id
    if student_id:
        query["student_id"] = student_id
    
    records = await gd_find(db.session, "behavior", query, order_by="date", desc_order=True, limit=200)
    return records


@router.post("/behavior")
async def create_behavior_record(
    data: dict = Body(...),
    current_user: dict = Depends(get_current_user)
):
    """Create behavior record - تسجيل ملاحظة سلوكية"""
    record = {
        "id": str(uuid.uuid4()),
        **data,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by": current_user["id"]
    }
    
    await gd_insert(db.session, "behavior", record)
    record.pop("_id", None)
    
    return {"message": "تم تسجيل الملاحظة السلوكية", "record": record}


@router.get("/classes/{class_id}/student-stats")
async def get_class_student_stats(
    class_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get aggregated stats (attendance, grades, behavior) for all students in a class"""
    if current_user.get("role") not in ADMIN_ROLES:
        teacher_id = current_user.get("teacher_id") or current_user.get("id")
        assignment = await gd_find_one(db.session, "teacher_assignments", {"teacher_id": teacher_id, "class_id": class_id})
        if not assignment:
            class_session = await gd_find_one(db.session, "class_sessions", {"teacher_id": teacher_id, "class_id": class_id})
            if not class_session:
                raise HTTPException(status_code=403, detail="ليس لديك صلاحية لعرض هذا الفصل")

    students = await gd_find(db.session, "students", {"class_id": class_id}, limit=100)

    student_ids = [s["id"] for s in students]
    if not student_ids:
        return {}

    att_totals = {}
    att_present = {}

    attendance_pipeline = [
        {"$match": {"student_id": {"$in": student_ids}}},
        {"$group": {
            "_id": "$student_id",
            "total": {"$sum": 1},
            "present": {"$sum": {"$cond": [{"$eq": ["$status", "present"]}, 1, 0]}},
        }}
    ]
    __doc_list = await _gd_aggregate(db.session, "attendance", attendance_pipeline)
    for doc in __doc_list:
        sid = doc["_id"]
        att_totals[sid] = doc["total"]
        att_present[sid] = doc["present"]

    session_att_pipeline = [
        {"$match": {"student_id": {"$in": student_ids}, "is_draft": {"$ne": True}}},
        {"$group": {
            "_id": "$student_id",
            "total": {"$sum": 1},
            "present": {"$sum": {"$cond": [{"$eq": ["$status", "present"]}, 1, 0]}},
        }}
    ]
    __doc_list = await _gd_aggregate(db.session, "session_attendance", session_att_pipeline)
    for doc in __doc_list:
        sid = doc["_id"]
        att_totals[sid] = att_totals.get(sid, 0) + doc["total"]
        att_present[sid] = att_present.get(sid, 0) + doc["present"]

    attendance_results = {}
    for sid in student_ids:
        total = att_totals.get(sid, 0)
        present = att_present.get(sid, 0)
        attendance_results[sid] = round((present / total * 100) if total > 0 else 0, 1)

    grades_pipeline = [
        {"$match": {"student_id": {"$in": student_ids}}},
        {"$group": {
            "_id": "$student_id",
            "avg_score": {"$avg": "$score"},
            "count": {"$sum": 1}
        }}
    ]
    grades_results = {}
    __doc_list = await _gd_aggregate(db.session, "grades", grades_pipeline)
    for doc in __doc_list:
        grades_results[doc["_id"]] = round(doc["avg_score"] or 0, 1)

    behavior_pipeline = [
        {"$match": {"student_id": {"$in": student_ids}}},
        {"$group": {
            "_id": "$student_id",
            "total_points": {"$sum": "$points"},
        }}
    ]
    behavior_results = {}
    __doc_list = await _gd_aggregate(db.session, "behavior", behavior_pipeline)
    for doc in __doc_list:
        behavior_results[doc["_id"]] = doc.get("total_points", 0)

    session_behavior_pipeline = [
        {"$match": {"student_id": {"$in": student_ids}, "interaction_type": "behaviour"}},
        {"$group": {
            "_id": "$student_id",
            "count": {"$sum": 1},
        }}
    ]
    __doc_list = await _gd_aggregate(db.session, "session_interactions", session_behavior_pipeline)
    for doc in __doc_list:
        sid = doc["_id"]
        behavior_results[sid] = behavior_results.get(sid, 0) + doc.get("count", 0)

    result = {}
    for sid in student_ids:
        result[sid] = {
            "attendance_rate": attendance_results.get(sid, 0),
            "average_grade": grades_results.get(sid, 0),
            "behavior_points": behavior_results.get(sid, 0)
        }

    return result


@router.get("/students/{student_id}/analytics")
async def get_student_analytics(
    student_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get comprehensive analytics for a single student"""
    if current_user.get("role") not in ADMIN_ROLES:
        teacher_id = current_user.get("teacher_id") or current_user.get("id")
        student = await gd_find_one(db.session, "students", {"id": student_id})
        if student:
            class_id = student.get("class_id")
            assignment = await gd_find_one(db.session, "teacher_assignments", {"teacher_id": teacher_id, "class_id": class_id})
            if not assignment:
                session_check = await gd_find_one(db.session, "class_sessions", {"teacher_id": teacher_id, "class_id": class_id})
                if not session_check:
                    raise HTTPException(status_code=403, detail="ليس لديك صلاحية لعرض بيانات هذا الطالب")

    attendance_records = await gd_find(db.session, "attendance", {"student_id": student_id}, order_by="date", desc_order=True, limit=100)

    session_att_raw = await gd_find(db.session, "session_attendance", {"student_id": student_id, "is_draft": {"$ne": True}}, order_by="recorded_at", desc_order=True, limit=100)

    session_att = []
    for r in session_att_raw:
        date_val = r.get("recorded_at", "")
        if isinstance(date_val, str) and len(date_val) >= 10:
            date_val = date_val[:10]
        session_att.append({"date": date_val, "status": r.get("status")})

    all_attendance = attendance_records + session_att
    total_att = len(all_attendance)
    present_count = sum(1 for r in all_attendance if r.get("status") == "present")
    absent_count = sum(1 for r in all_attendance if r.get("status") == "absent")
    late_count = sum(1 for r in all_attendance if r.get("status") == "late")
    attendance_rate = round((present_count / total_att * 100) if total_att > 0 else 0, 1)

    monthly_attendance = {}
    for r in all_attendance:
        d = r.get("date", "")
        month_key = d[:7] if isinstance(d, str) and len(d) >= 7 else "unknown"
        if month_key == "unknown":
            continue
        if month_key not in monthly_attendance:
            monthly_attendance[month_key] = {"total": 0, "present": 0}
        monthly_attendance[month_key]["total"] += 1
        if r.get("status") == "present":
            monthly_attendance[month_key]["present"] += 1
    attendance_trend = [
        {"month": k, "rate": round(v["present"] / v["total"] * 100, 1) if v["total"] > 0 else 0}
        for k, v in sorted(monthly_attendance.items())
    ]

    grades = await gd_find(db.session, "grades", {"student_id": student_id}, order_by="created_at", desc_order=True, limit=50)
    avg_grade = round(sum(g.get("score", 0) for g in grades) / len(grades), 1) if grades else 0

    interactions = await gd_find(db.session, "session_interactions", {"student_id": student_id}, order_by="recorded_at", desc_order=True, limit=50)

    participation_count = sum(1 for i in interactions if i.get("interaction_type") == "participation")
    behavior_interactions = [i for i in interactions if i.get("interaction_type") == "behaviour"]

    interaction_records = []
    for i in interactions:
        itype = i.get("interaction_type", "")
        note = ""
        if itype == "participation":
            note = i.get("participation_type", "مشاركة")
        elif itype == "behaviour":
            note = i.get("behaviour_details") or i.get("behaviour_type") or "سلوك"
        elif itype == "question":
            note = i.get("answer_result", "سؤال")
        interaction_records.append({
            "type": itype,
            "note": note,
            "created_at": i.get("recorded_at", "")
        })

    skills = await gd_find(db.session, "student_skills", {"student_id": student_id}, order_by="recorded_at", desc_order=True, limit=50)

    behavior_records = await gd_find(db.session, "behavior", {"student_id": student_id}, order_by="date", desc_order=True, limit=20)

    total_behavior = sum(r.get("points", 0) for r in behavior_records) + len(behavior_interactions)

    session_beh_records = []
    for b in behavior_interactions:
        session_beh_records.append({
            "note": b.get("behaviour_details") or b.get("behaviour_type") or "سلوك",
            "points": 1 if b.get("behaviour_category") == "positive" else -1,
            "created_at": b.get("recorded_at", "")
        })

    return {
        "attendance": {
            "rate": attendance_rate,
            "total": total_att,
            "present": present_count,
            "absent": absent_count,
            "late": late_count,
            "trend": attendance_trend,
            "recent": all_attendance[:10]
        },
        "grades": {
            "average": avg_grade,
            "count": len(grades),
            "records": grades[:10]
        },
        "participation": {
            "total_interactions": len(interactions),
            "participation_count": participation_count,
            "recent": interaction_records[:10]
        },
        "behavior": {
            "total_points": total_behavior,
            "records": behavior_records[:10],
            "session_records": session_beh_records[:10]
        },
        "skills": skills[:20]
    }


@router.get("/resources")
async def get_resources(
    teacher_id: str = Query(None),
    current_user: dict = Depends(get_current_user)
):
    """Get educational resources"""
    query = {}
    if teacher_id:
        query["teacher_id"] = teacher_id
    
    resources = await gd_find(db.session, "resources", query, order_by="created_at", desc_order=True, limit=100)
    return resources


@router.post("/resources")
async def create_resource(
    data: dict = Body(...),
    current_user: dict = Depends(get_current_user)
):
    """Create educational resource - إضافة مصدر تعليمي"""
    resource = {
        "id": str(uuid.uuid4()),
        **data,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by": current_user["id"]
    }
    
    await gd_insert(db.session, "resources", resource)
    resource.pop("_id", None)
    
    return {"message": "تمت إضافة المصدر", "resource": resource}


@router.delete("/resources/{resource_id}")
async def delete_resource(
    resource_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Delete resource"""
    await gd_delete_one(db.session, "resources", {"id": resource_id})
    return {"message": "تم حذف المصدر"}


@router.get("/messages")
async def get_messages(
    sender_id: str = Query(None),
    recipient_id: str = Query(None),
    current_user: dict = Depends(get_current_user)
):
    """Get messages filtered by sender or recipient"""
    query = {}
    caller_id = current_user.get("teacher_id") or current_user.get("id")
    if sender_id:
        if sender_id != caller_id and current_user.get("role") not in ("platform_admin", "school_principal", "school_admin"):
            raise HTTPException(status_code=403, detail="غير مصرح")
        query["sender_id"] = sender_id
    elif recipient_id:
        if recipient_id != caller_id and current_user.get("role") not in ("platform_admin", "school_principal", "school_admin"):
            raise HTTPException(status_code=403, detail="غير مصرح")
        query["$or"] = [{"recipient_ids": recipient_id}, {"recipient_id": recipient_id}]
    else:
        query["$or"] = [{"sender_id": caller_id}, {"recipient_ids": caller_id}, {"recipient_id": caller_id}]

    messages = await gd_find(db.session, "messages", query, order_by="created_at", desc_order=True, limit=100)
    return messages


@router.post("/messages")
async def send_message(
    data: dict = Body(...),
    current_user: dict = Depends(get_current_user)
):
    """Send message to parents - إرسال رسالة لأولياء الأمور"""
    sender_user_id = current_user.get("id")

    raw_recipients = data.get("recipient_ids") or []
    if isinstance(raw_recipients, str):
        raw_recipients = [raw_recipients]
    single = data.get("recipient_id")
    if single and single not in raw_recipients:
        raw_recipients.append(single)

    resolved_recipient_id = None
    for rid in raw_recipients:
        if not rid:
            continue
        user = await gd_find_one(db.session, "users", {"id": rid})
        if user:
            resolved_recipient_id = user["id"]
            break
        student = await gd_find_one(db.session, "students", {"id": rid})
        if not student:
            student = await gd_find_one(db.session, "students", {"parent_id": rid})
        if student:
            parent_user = None
            if student.get("parent_email"):
                parent_user = await gd_find_one(db.session, "users", {"email": student["parent_email"], "role": "parent"})
            if not parent_user and student.get("parent_phone"):
                parent_user = await gd_find_one(db.session, "users", {"phone": student["parent_phone"], "role": "parent"})
            if not parent_user and student.get("parent_name"):
                parent_user = await gd_find_one(db.session, "users", {"full_name": student["parent_name"], "role": "parent"})
            if parent_user:
                resolved_recipient_id = parent_user["id"]
                break

    message_doc = {
        "id": str(uuid.uuid4()),
        "sender_id": sender_user_id,
        "recipient_id": resolved_recipient_id,
        "school_id": current_user.get("tenant_id"),
        "subject": data.get("subject"),
        "body": data.get("body"),
        "is_read": False,
        "read_at": None,
        "created_at": datetime.now(timezone.utc),
    }

    await gd_insert(db.session, "messages", message_doc)

    return {"message": "تم إرسال الرسالة", "data": {"id": message_doc["id"]}}


@router.get("/grades")
async def get_grades(
    class_id: str = Query(None),
    student_id: str = Query(None),
    current_user: dict = Depends(get_current_user)
):
    """Get grades with filters"""
    query = {}
    if class_id:
        # Get assessments for this class first
        assessments = await gd_find(db.session, "assessments", {"class_id": class_id}, limit=100)
        assessment_ids = [a.get("id") for a in assessments]
        query["assessment_id"] = {"$in": assessment_ids}
    if student_id:
        query["student_id"] = student_id
    
    grades = await gd_find(db.session, "grades", query, limit=500)
    return grades


@router.get("/users/{user_id}/notifications/settings")
async def get_notification_settings(
    user_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get user notification settings (self or admin only)"""
    caller_id = current_user.get("id")
    if user_id != caller_id and current_user.get("role") not in ("platform_admin", "school_principal", "school_admin"):
        raise HTTPException(status_code=403, detail="غير مصرح بالوصول لإعدادات مستخدم آخر")
    settings = await gd_find_one(db.session, "notification_settings", {"user_id": user_id})
    return settings or {}


@router.put("/users/{user_id}/notifications/settings")
async def update_notification_settings(
    user_id: str,
    data: dict = Body(...),
    current_user: dict = Depends(get_current_user)
):
    """Update user notification settings (self or admin only)"""
    caller_id = current_user.get("id")
    if user_id != caller_id and current_user.get("role") not in ("platform_admin", "school_principal", "school_admin"):
        raise HTTPException(status_code=403, detail="غير مصرح بتعديل إعدادات مستخدم آخر")
    await gd_update_one(db.session, "notification_settings", {"user_id": user_id}, {**data, "updated_at": datetime.now(timezone.utc).isoformat()})
    return {"message": "تم حفظ الإعدادات"}


@router.put("/users/{user_id}/password")
async def change_user_password(
    user_id: str,
    data: dict = Body(...),
    current_user: dict = Depends(get_current_user)
):
    """Change user password"""
    if current_user["id"] != user_id and current_user.get("role") != "platform_admin":
        raise HTTPException(status_code=403, detail="Not authorized")
    
    # Verify current password
    user = await gd_find_one(db.session, "users", {"id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if not pwd_context.verify(data.get("current_password"), user.get("password_hash")):
        raise HTTPException(status_code=400, detail="كلمة المرور الحالية غير صحيحة")
    
    # Update password
    new_hash = pwd_context.hash(data.get("new_password"))
    await gd_update_one(db.session, "users", {"id": user_id}, {"password_hash": new_hash, "updated_at": datetime.now(timezone.utc).isoformat()})
    
    return {"message": "تم تغيير كلمة المرور"}


@router.get("/teacher/profile/{teacher_id}/activity")
async def get_teacher_activity_log(
    teacher_id: str,
    limit: int = Query(50, ge=1, le=200),
    current_user: dict = Depends(get_current_user)
):
    """Get teacher's own activity log for Profile & Settings page"""
    caller_id = current_user.get("teacher_id") or current_user.get("id")
    caller_role = current_user.get("role", "")
    if teacher_id != caller_id and caller_role not in ("platform_admin", "school_principal", "school_admin"):
        raise HTTPException(status_code=403, detail="غير مصرح")

    user = await gd_find_one(db.session, "users", {"$or": [{"id": teacher_id}, {"teacher_id": teacher_id}]})

    if teacher_id != caller_id and caller_role in ("school_principal", "school_admin"):
        caller_tenant = current_user.get("tenant_id")
        target_tenant = user.get("tenant_id") if user else None
        if caller_tenant and target_tenant and caller_tenant != target_tenant:
            raise HTTPException(status_code=403, detail="غير مصرح بالوصول لبيانات مدرسة أخرى")
    user_id = user.get("id") if user else teacher_id

    activities = await gd_find(db.session, "audit_logs", {"$or": [
            {"performed_by": user_id},
            {"action_by": user_id},
            {"performed_by": teacher_id},
            {"action_by": teacher_id},
        ]}, order_by="timestamp", desc_order=True, limit=limit)

    action_labels = {
        "auth.login": {"ar": "تسجيل دخول", "en": "Login", "icon": "login"},
        "auth.logout": {"ar": "تسجيل خروج", "en": "Logout", "icon": "logout"},
        "session.start": {"ar": "بدء حصة", "en": "Start Session", "icon": "session"},
        "session.end": {"ar": "إنهاء حصة", "en": "End Session", "icon": "session"},
        "attendance.record": {"ar": "تسجيل حضور", "en": "Record Attendance", "icon": "attendance"},
        "attendance.create": {"ar": "تسجيل حضور", "en": "Record Attendance", "icon": "attendance"},
        "behavior.create": {"ar": "تسجيل سلوك", "en": "Record Behavior", "icon": "behavior"},
        "grade.create": {"ar": "تسجيل درجات", "en": "Record Grades", "icon": "grade"},
        "message.send": {"ar": "إرسال رسالة", "en": "Send Message", "icon": "message"},
        "user.update": {"ar": "تحديث بيانات", "en": "Update Profile", "icon": "profile"},
        "user_updated": {"ar": "تحديث بيانات", "en": "Update Profile", "icon": "profile"},
        "password.change": {"ar": "تغيير كلمة المرور", "en": "Password Change", "icon": "security"},
    }

    formatted = []
    for act in activities:
        action = act.get("action", "")
        label_info = action_labels.get(action, {"ar": action, "en": action, "icon": "other"})
        formatted.append({
            "id": act.get("id", ""),
            "action": action,
            "label_ar": label_info["ar"],
            "label_en": label_info["en"],
            "icon": label_info["icon"],
            "description": act.get("description", act.get("details", "")),
            "timestamp": act.get("timestamp", act.get("created_at", "")),
            "entity_type": act.get("entity_type", ""),
            "page": act.get("page", act.get("path", "")),
        })

    return {"activities": formatted, "total": len(formatted)}



# ============== TEACHER SESSION ENGINE APIs ==============

ADMIN_ROLES = {"admin", "super_admin", "platform_admin", "school_admin"}

async def _verify_session_owner(session_id: str, current_user: dict):
    session = await gd_find_one(db.session, "class_sessions", {"id": session_id})
    if not session:
        raise HTTPException(status_code=404, detail="الجلسة غير موجودة")
    caller_teacher = current_user.get("teacher_id") or current_user.get("id")
    if session.get("teacher_id") and session["teacher_id"] != caller_teacher:
        if current_user.get("role") not in ADMIN_ROLES:
            raise HTTPException(status_code=403, detail="ليس لديك صلاحية على هذه الجلسة")


@router.post("/session/start")
async def start_class_session(
    data: dict = Body(...),
    current_user: dict = Depends(get_current_user)
):
    """
    بدء حصة جديدة
    Start a new class session
    
    Required fields:
    - schedule_session_id: ID from schedule_sessions
    - teacher_id: Teacher ID
    - class_id: Class ID
    - subject_id: Subject ID
    """
    caller_teacher = current_user.get("teacher_id") or current_user.get("id")
    requested_teacher = data.get("teacher_id") or caller_teacher
    if requested_teacher != caller_teacher and current_user.get("role") not in ADMIN_ROLES:
        raise HTTPException(status_code=403, detail="لا يمكنك بدء حصة لمعلم آخر")
    result = await session_engine.start_session(
        teacher_id=requested_teacher,
        schedule_session_id=data.get("schedule_session_id"),
        class_id=data.get("class_id"),
        subject_id=data.get("subject_id"),
        force_new=data.get("force_new") is True
    )
    return result


@router.get("/session/current")
async def get_current_session(
    schedule_session_id: str = None,
    current_user: dict = Depends(get_current_user)
):
    """Get current in-progress session by schedule session ID or any active session for teacher"""
    teacher_id = current_user.get("teacher_id") or current_user.get("id")
    active_statuses = ["in_progress", "session_opened", "attendance_in_progress",
                       "attendance_approved", "teaching_in_progress", "interaction_running",
                       "session_review"]
    
    if schedule_session_id:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        query = {
            "schedule_session_id": schedule_session_id,
            "date": today,
            "status": {"$in": active_statuses}
        }
        if teacher_id:
            query["teacher_id"] = teacher_id
        session = await gd_find_one(db.session, "class_sessions", query)
    else:
        session = await gd_find_one(db.session, "class_sessions", {
            "teacher_id": teacher_id,
            "status": {"$in": active_statuses}
        })
    
    if not session:
        raise HTTPException(status_code=404, detail="لا توجد جلسة جارية")
    
    class_info = await gd_find_one(db.session, "classes", {"id": session.get("class_id")})
    subject = await gd_find_one(db.session, "subjects", {"id": session.get("subject_id")})
    teacher = await gd_find_one(db.session, "teachers", {"id": session.get("teacher_id")})
    
    student_count = await gd_count(db.session, "session_attendance", {"session_id": session.get("id")})
    
    return {
        "session_record_id": session.get("id"),
        "session_status": session.get("status"),
        "start_time": session.get("start_time"),
        "class_name": class_info.get("name") if class_info else "فصل",
        "subject_name": (subject.get("name_ar") or subject.get("name")) if subject else "مادة",
        "teacher_name": teacher.get("full_name") if teacher else "معلم",
        "student_count": student_count,
        "session_id": session.get("id"),
        "class_id": session.get("class_id"),
        "subject_id": session.get("subject_id"),
        "schedule_session_id": session.get("schedule_session_id")
    }


@router.get("/session/{session_id}")
async def get_session_info(
    session_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get session information"""
    await _verify_session_owner(session_id, current_user)
    session = await gd_find_one(db.session, "class_sessions", {"id": session_id})
    if not session:
        raise HTTPException(status_code=404, detail="الجلسة غير موجودة")
    return session


@router.get("/session/by-schedule/{schedule_session_id}")
async def get_session_by_schedule_id(
    schedule_session_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get session information by schedule session ID"""
    session = await gd_find_one(db.session, "class_sessions", {"schedule_session_id": schedule_session_id})
    if not session:
        raise HTTPException(status_code=404, detail="الجلسة غير موجودة")
    await _verify_session_owner(session["id"], current_user)
    return session


@router.get("/session/{session_id}/students")
async def get_session_students(
    session_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    جلب قائمة الطلاب للحصة مع حالة الحضور
    Get students list with attendance status for session
    """
    await _verify_session_owner(session_id, current_user)
    students = await session_engine.get_session_students(session_id)
    return {
        "session_id": session_id,
        "total": len(students),
        "students": students
    }


@router.put("/session/{session_id}/attendance/{student_id}")
async def update_student_attendance(
    session_id: str,
    student_id: str,
    data: dict = Body(...),
    current_user: dict = Depends(get_current_user)
):
    """
    تحديث حالة حضور طالب
    Update student attendance status
    """
    await _verify_session_owner(session_id, current_user)
    from engines.session_engine import AttendanceStatus
    status = AttendanceStatus(data.get("status", "present"))
    result = await session_engine.update_attendance(
        session_id=session_id,
        student_id=student_id,
        status=status,
        teacher_id=current_user["id"]
    )
    return result


@router.post("/session/{session_id}/attendance/approve")
async def approve_session_attendance(
    session_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    اعتماد الحضور
    Approve and finalize attendance
    """
    await _verify_session_owner(session_id, current_user)
    result = await session_engine.approve_attendance(
        session_id=session_id,
        teacher_id=current_user["id"]
    )
    return result


@router.post("/session/{session_id}/mode")
async def set_session_mode(
    session_id: str,
    data: dict = Body(...),
    current_user: dict = Depends(get_current_user)
):
    """
    تحديد نمط التفاعل (متابعة واجب / مراجعة / امتحان مفاجئ)
    Set interaction mode (homework / review / quiz)
    """
    await _verify_session_owner(session_id, current_user)
    mode = data.get("mode", "review")
    teacher_id = current_user.get("teacher_id") or current_user["id"]
    result = await session_engine.set_interaction_mode(session_id, mode, teacher_id=teacher_id)
    return result


@router.post("/session/{session_id}/random-student")
async def select_random_student(
    session_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    اختيار طالب عشوائي
    Select random student using fair algorithm
    """
    await _verify_session_owner(session_id, current_user)
    result = await session_engine.select_random_student(session_id)
    return result


@router.post("/session/{session_id}/answer")
async def record_student_answer(
    session_id: str,
    data: dict = Body(...),
    current_user: dict = Depends(get_current_user)
):
    """
    تسجيل إجابة الطالب
    Record student answer (correct/wrong/no_answer)
    """
    await _verify_session_owner(session_id, current_user)
    from engines.session_engine import AnswerResult
    result = await session_engine.record_answer(
        session_id=session_id,
        student_id=data.get("student_id"),
        result=AnswerResult(data.get("result", "correct")),
        teacher_id=current_user["id"]
    )
    return result


@router.get("/session/{session_id}/activity")
async def get_session_activity(
    session_id: str,
    current_user: dict = Depends(get_current_user)
):
    await _verify_session_owner(session_id, current_user)
    log = await session_engine.get_activity_log(session_id, limit=50)
    return {"activity": log}


@router.post("/session/{session_id}/participation")
async def record_student_participation(
    session_id: str,
    data: dict = Body(...),
    current_user: dict = Depends(get_current_user)
):
    """
    تسجيل مشاركة الطالب
    Record student participation
    """
    await _verify_session_owner(session_id, current_user)
    from engines.session_engine import ParticipationType
    result = await session_engine.record_participation(
        session_id=session_id,
        student_id=data.get("student_id"),
        participation_type=ParticipationType(data.get("type", "active")),
        teacher_id=current_user["id"]
    )
    return result


@router.post("/session/{session_id}/behaviour")
async def record_student_behaviour(
    session_id: str,
    data: dict = Body(...),
    current_user: dict = Depends(get_current_user)
):
    """
    تسجيل سلوك الطالب
    Record student behaviour (positive/negative/skill)
    """
    await _verify_session_owner(session_id, current_user)
    from engines.session_engine import BehaviourCategory
    result = await session_engine.record_behaviour(
        session_id=session_id,
        student_id=data.get("student_id"),
        category=BehaviourCategory(data.get("category", "positive")),
        behaviour_type=data.get("behaviour_type"),
        details=data.get("details"),
        teacher_id=current_user["id"]
    )
    return result


@router.post("/session/{session_id}/homework")
async def record_homework_status(
    session_id: str,
    data: dict = Body(...),
    current_user: dict = Depends(get_current_user)
):
    """
    تسجيل حالة الواجب (حل / ما حل)
    Record homework status (done / not_done) for a single student
    """
    await _verify_session_owner(session_id, current_user)
    teacher_id = current_user.get("teacher_id") or current_user["id"]
    result = await session_engine.record_homework(
        session_id=session_id,
        student_id=data.get("student_id"),
        status=data.get("status", "done"),
        teacher_id=teacher_id
    )
    return result


@router.get("/session/{session_id}/homework")
async def get_homework_statuses(
    session_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    جلب حالات الواجب لجميع الطلاب
    Get homework statuses for all students in session
    """
    await _verify_session_owner(session_id, current_user)
    statuses = await session_engine.get_homework_statuses(session_id)
    return {"statuses": statuses}


@router.post("/session/{session_id}/homework/bulk")
async def bulk_record_homework(
    session_id: str,
    data: dict = Body(...),
    current_user: dict = Depends(get_current_user)
):
    """
    حفظ حالات الواجب لجميع الطلاب دفعة واحدة
    Bulk save homework statuses
    """
    await _verify_session_owner(session_id, current_user)
    teacher_id = current_user.get("teacher_id") or current_user["id"]
    result = await session_engine.bulk_record_homework(
        session_id=session_id,
        records=data.get("records", []),
        teacher_id=teacher_id
    )
    return result


@router.post("/session/{session_id}/seating")
async def update_seating_order(
    session_id: str,
    data: dict = Body(...),
    current_user: dict = Depends(get_current_user)
):
    """
    حفظ ترتيب جلوس الطلاب
    Save student seating order
    """
    await _verify_session_owner(session_id, current_user)
    teacher_id = current_user.get("teacher_id") or current_user["id"]
    result = await session_engine.update_seating_order(
        session_id=session_id,
        student_order=data.get("student_order", []),
        teacher_id=teacher_id
    )
    return result


@router.get("/session/{session_id}/review-preview")
async def get_session_review_preview(
    session_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    مراجعة ملخص الحصة قبل الإنهاء
    Get session review preview before ending (Section 7.5)
    """
    await _verify_session_owner(session_id, current_user)
    result = await session_engine.get_review_preview(
        session_id=session_id,
        teacher_id=current_user["id"]
    )
    return result


@router.post("/session/{session_id}/end")
async def end_class_session(
    session_id: str,
    request: Request = None,
    current_user: dict = Depends(get_current_user)
):
    """
    إنهاء الحصة
    End class session and get summary
    """
    await _verify_session_owner(session_id, current_user)
    closing_note = None
    try:
        body = await request.json()
        closing_note = body.get("closing_note") if body else None
    except Exception as e:
        logger.debug(f"No JSON body provided for end_session (optional): {e}")
    result = await session_engine.end_session(
        session_id=session_id,
        teacher_id=current_user["id"],
        closing_note=closing_note
    )
    return result


@router.get("/session/{session_id}/export-report")
async def export_session_report(
    session_id: str,
    format: str = "csv",
    current_user: dict = Depends(get_current_user)
):
    await _verify_session_owner(session_id, current_user)
    teacher_id = current_user.get("teacher_id") or current_user["id"]
    result = await session_engine.export_session_report(session_id, teacher_id, format)
    return result


@router.get("/student/{student_id}/score")
async def get_student_score(
    student_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    جلب نقاط الطالب
    Get student score information
    """
    result = await session_engine.get_student_score(student_id)
    return result


@router.get("/session/behaviour-types/all")
async def get_behaviour_types(
    current_user: dict = Depends(get_current_user)
):
    """
    جلب أنواع السلوكيات المتاحة
    Get available behaviour types
    """
    from engines.session_engine import DEFAULT_BEHAVIOUR_TYPES
    return DEFAULT_BEHAVIOUR_TYPES


@router.get("/teacher/{teacher_id}/class-metrics")
async def get_teacher_class_metrics(
    teacher_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    جلب مقاييس الفصول الحقيقية للمعلم
    Get real class metrics for a teacher (attendance, participation, performance)
    """
    _verify_teacher_access(teacher_id, current_user)
    teacher = await _resolve_teacher_record(teacher_id)
    resolved_teacher_id = teacher.get("id") if teacher else teacher_id
    assignments = await gd_find(db.session, "teacher_assignments", {"teacher_id": resolved_teacher_id, "is_active": True}, limit=200)
    class_ids_from_ta = set(a.get("class_id") for a in assignments if a.get("class_id"))

    tca_docs = await gd_find(db.session, "teacher_class_assignments", {"teacher_id": resolved_teacher_id}, limit=200)
    class_ids_from_tca = set(d.get("class_id") for d in tca_docs if d.get("class_id"))

    all_class_ids = list(class_ids_from_ta | class_ids_from_tca)
    metrics = {}
    for class_id in all_class_ids:
        metrics[class_id] = await session_engine.get_class_metrics(resolved_teacher_id, class_id)
    return metrics


@router.get("/skills-types")
async def get_skills_types(
    current_user: dict = Depends(get_current_user)
):
    """
    جلب أنواع المهارات المتاحة
    Get all available skill types
    """
    skills = await gd_find(db.session, "skills_types", {}, limit=100)
    if not skills:
        from engines.session_engine import DEFAULT_SKILLS_TYPES
        now = datetime.now(timezone.utc).isoformat()
        for s in DEFAULT_SKILLS_TYPES:
            s["created_at"] = now
        await gd_insert_many(db.session, "skills_types", [dict(s) for s in DEFAULT_SKILLS_TYPES])
        if audit_engine:
            try:
                await audit_engine.log(
                    action=AuditAction.SYSTEM_CONFIG,
                    performed_by=current_user.get("id", "system"),
                    details={"event": "skills_types_seeded", "count": len(DEFAULT_SKILLS_TYPES)}
                )
            except Exception:
                logger.debug("Skipped audit log for skills_types seed (FK constraint)")
        skills = await gd_find(db.session, "skills_types", {}, limit=100)
    return skills


@router.post("/skills-types")
async def create_skill_type(
    data: dict = Body(...),
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_ADMIN, UserRole.SCHOOL_PRINCIPAL]))
):
    """
    إنشاء نوع مهارة جديد
    Create a new skill type (admin only)
    """
    now = datetime.now(timezone.utc)
    skill = {
        "id": f"skill-{str(uuid.uuid4())[:8]}",
        "name": data.get("name", ""),
        "name_ar": data.get("name_ar", ""),
        "description": data.get("description", ""),
        "category": data.get("category", "general"),
        "created_at": now.isoformat()
    }
    await gd_insert(db.session, "skills_types", skill)
    if audit_engine:
        await audit_engine.log(
            action=AuditAction.SYSTEM_CONFIG,
            performed_by=current_user.get("id"),
            details={"event": "skill_type_created", "skill_id": skill["id"], "name": skill["name"]}
        )
    return {"message": "تم إنشاء نوع المهارة", "skill": {k: v for k, v in skill.items() if k != "_id"}}


@router.post("/session/{session_id}/skill")
async def record_session_skill(
    session_id: str,
    data: dict = Body(...),
    current_user: dict = Depends(get_current_user)
):
    """
    تسجيل مهارة لطالب خلال الحصة
    Record a skill for a student during a session
    """
    await _verify_session_owner(session_id, current_user)
    teacher_id = current_user["id"]
    result = await session_engine.record_skill(
        session_id=session_id,
        student_id=data.get("student_id"),
        skill_type_id=data.get("skill_type_id"),
        teacher_id=teacher_id,
        notes=data.get("notes")
    )
    if audit_engine:
        await audit_engine.log(
            action=AuditAction.DATA_MODIFY,
            performed_by=teacher_id,
            details={
                "event": "skill_recorded",
                "session_id": session_id,
                "student_id": data.get("student_id"),
                "skill_type_id": data.get("skill_type_id")
            }
        )
    return result


@router.post("/session/{session_id}/note")
async def add_session_note(
    session_id: str,
    data: dict = Body(...),
    current_user: dict = Depends(get_current_user)
):
    await _verify_session_owner(session_id, current_user)
    teacher_id = current_user.get("teacher_id") or current_user["id"]
    result = await session_engine.add_note(
        session_id=session_id,
        teacher_id=teacher_id,
        text=data.get("text", ""),
        note_type=data.get("note_type", "session"),
        student_id=data.get("student_id"),
        student_ids=data.get("student_ids")
    )
    return result


@router.get("/session/{session_id}/notes")
async def get_session_notes(
    session_id: str,
    current_user: dict = Depends(get_current_user)
):
    await _verify_session_owner(session_id, current_user)
    notes = await session_engine.get_session_notes(session_id)
    return {"session_id": session_id, "notes": notes}


@router.delete("/session/{session_id}/note/{note_id}")
async def delete_session_note(
    session_id: str,
    note_id: str,
    current_user: dict = Depends(get_current_user)
):
    await _verify_session_owner(session_id, current_user)
    teacher_id = current_user.get("teacher_id") or current_user["id"]
    result = await session_engine.delete_note(note_id, teacher_id)
    return result


@router.get("/session/{session_id}/live-metrics")
async def get_session_live_metrics(
    session_id: str,
    current_user: dict = Depends(get_current_user)
):
    await _verify_session_owner(session_id, current_user)
    metrics = await session_engine.get_live_metrics(session_id)
    return metrics


@router.get("/session/{session_id}/events")
async def get_session_events(
    session_id: str,
    current_user: dict = Depends(get_current_user)
):
    await _verify_session_owner(session_id, current_user)
    events = await session_engine.get_session_events(session_id)
    return {"session_id": session_id, "events": events}


@router.get("/session/{session_id}/report")
async def get_session_report(
    session_id: str,
    current_user: dict = Depends(get_current_user)
):
    await _verify_session_owner(session_id, current_user)
    report = await session_engine.get_session_report(session_id)
    return report


@router.get("/session/{session_id}/followup-record")
async def get_followup_record(
    session_id: str,
    current_user: dict = Depends(get_current_user)
):
    await _verify_session_owner(session_id, current_user)
    session = await gd_find_one(db.session, "class_sessions", {"id": session_id})
    if session:
        lookup = {"class_id": session.get("class_id"), "subject_id": session.get("subject_id")}
    else:
        lookup = {"session_id": session_id}
    record = await gd_find_one(db.session, "followup_records", lookup)
    if not record:
        return {
            "session_id": session_id,
            "columns": [
                {"id": "participation", "name": "المشاركة", "maxGrade": 10, "type": "grade", "group": "coursework"},
                {"id": "homework", "name": "الواجبات", "maxGrade": 10, "type": "grade", "group": "coursework"},
                {"id": "performance_task", "name": "المهام الأدائية", "maxGrade": 20, "type": "grade", "group": "coursework"},
                {"id": "short_test", "name": "الاختبار القصير", "maxGrade": 20, "type": "grade", "group": "exams"},
                {"id": "final_test", "name": "اختبار نهاية الفترة", "maxGrade": 40, "type": "grade", "group": "exams"},
            ],
            "data": {},
            "absences": {},
        }
    return {
        "session_id": session_id,
        "columns": record.get("columns", []),
        "data": record.get("data", {}),
        "absences": record.get("absences", {}),
    }


@router.post("/session/{session_id}/followup-record")
async def save_followup_record(
    session_id: str,
    payload: dict = Body(...),
    current_user: dict = Depends(get_current_user)
):
    await _verify_session_owner(session_id, current_user)
    session = await gd_find_one(db.session, "class_sessions", {"id": session_id})
    c_id = session.get("class_id") if session else None
    s_id = session.get("subject_id") if session else None
    lookup = {"class_id": c_id, "subject_id": s_id} if c_id and s_id else {"session_id": session_id}
    existing = await gd_find_one(db.session, "followup_records", lookup)
    record_data = {
        "class_id": c_id,
        "subject_id": s_id,
        "session_id": session_id,
        "columns": payload.get("columns", []),
        "data": payload.get("data", {}),
        "absences": payload.get("absences", {}),
        "updated_at": datetime.utcnow().isoformat(),
    }
    if existing:
        await gd_update_one(db.session, "followup_records", lookup, {"$set": record_data})
    else:
        record_data["created_at"] = datetime.utcnow().isoformat()
        await gd_insert(db.session, "followup_records", record_data)
    return {"success": True, "session_id": session_id}


@router.post("/session/{session_id}/followup-record/column")
async def add_followup_column(
    session_id: str,
    payload: dict = Body(...),
    current_user: dict = Depends(get_current_user)
):
    await _verify_session_owner(session_id, current_user)
    column = {
        "id": payload.get("id", f"col_{int(datetime.utcnow().timestamp() * 1000)}"),
        "name": payload.get("name", "عمود جديد"),
        "maxGrade": payload.get("maxGrade", 10),
        "type": payload.get("type", "grade"),
    }
    session = await gd_find_one(db.session, "class_sessions", {"id": session_id})
    c_id = session.get("class_id") if session else None
    s_id = session.get("subject_id") if session else None
    lookup = {"class_id": c_id, "subject_id": s_id} if c_id and s_id else {"session_id": session_id}
    existing = await gd_find_one(db.session, "followup_records", lookup)
    if existing:
        columns = existing.get("columns", [])
        columns.append(column)
        await gd_update_one(db.session, "followup_records", lookup, {"$set": {"columns": columns}})
    else:
        await gd_insert(db.session, "followup_records", {
            **lookup,
            "session_id": session_id,
            "columns": [column],
            "data": {},
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
        })
    return {"success": True, "column": column}


@router.get("/session/{session_id}/settings")
async def get_session_settings(
    session_id: str,
    current_user: dict = Depends(get_current_user)
):
    await _verify_session_owner(session_id, current_user)
    session = await gd_find_one(db.session, "class_sessions", {"id": session_id})
    if session:
        lookup = {"class_id": session.get("class_id"), "subject_id": session.get("subject_id")}
    else:
        lookup = {"session_id": session_id}
    record = await gd_find_one(db.session, "session_settings", lookup)
    default = {
        "subject_id": session.get("subject_id") if session else None,
        "participation_enabled": True,
        "homework_enabled": True,
        "homework_view_mode": "not_submitted",
        "recitation_enabled": False,
        "recitation_max_attempts": 1,
        "skill_enabled": False,
        "extra_columns": [],
    }
    if not record:
        return {"session_id": session_id, **default}
    return {
        "session_id": session_id,
        "subject_id": record.get("subject_id") or default["subject_id"],
        "participation_enabled": record.get("participation_enabled", True),
        "homework_enabled": record.get("homework_enabled", True),
        "homework_view_mode": record.get("homework_view_mode", "not_submitted"),
        "recitation_enabled": record.get("recitation_enabled", False),
        "recitation_max_attempts": record.get("recitation_max_attempts", 1),
        "skill_enabled": record.get("skill_enabled", False),
        "extra_columns": record.get("extra_columns", []),
    }


@router.post("/session/{session_id}/settings")
async def save_session_settings(
    session_id: str,
    payload: dict = Body(...),
    current_user: dict = Depends(get_current_user)
):
    await _verify_session_owner(session_id, current_user)
    session = await gd_find_one(db.session, "class_sessions", {"id": session_id})
    c_id = session.get("class_id") if session else None
    s_id = payload.get("subject_id") or (session.get("subject_id") if session else None)
    lookup = {"class_id": c_id, "subject_id": s_id} if c_id and s_id else {"session_id": session_id}
    existing = await gd_find_one(db.session, "session_settings", lookup)
    # Validate enum / numeric ranges
    hv_mode = payload.get("homework_view_mode", "not_submitted")
    if hv_mode not in ("not_submitted", "submitted"):
        hv_mode = "not_submitted"
    try:
        attempts = int(payload.get("recitation_max_attempts", 1) or 1)
    except (TypeError, ValueError):
        attempts = 1
    attempts = max(1, min(3, attempts))
    raw_cols = payload.get("extra_columns", []) or []
    extra_columns = []
    if isinstance(raw_cols, list):
        for c in raw_cols:
            if not isinstance(c, dict):
                continue
            extra_columns.append({
                "id": str(c.get("id") or f"col_{int(datetime.utcnow().timestamp() * 1000)}"),
                "name": str(c.get("name") or "")[:100],
                "type": c.get("type") if c.get("type") in ("grade", "check", "text") else "grade",
                "maxGrade": int(c.get("maxGrade") or 0),
            })
    record_data = {
        "class_id": c_id,
        "subject_id": s_id,
        "session_id": session_id,
        "participation_enabled": bool(payload.get("participation_enabled", True)),
        "homework_enabled": bool(payload.get("homework_enabled", True)),
        "homework_view_mode": hv_mode,
        "recitation_enabled": bool(payload.get("recitation_enabled", False)),
        "recitation_max_attempts": attempts,
        "skill_enabled": bool(payload.get("skill_enabled", False)),
        "extra_columns": extra_columns,
        "updated_at": datetime.utcnow().isoformat(),
    }
    if existing:
        await gd_update_one(db.session, "session_settings", lookup, {"$set": record_data})
    else:
        record_data["created_at"] = datetime.utcnow().isoformat()
        await gd_insert(db.session, "session_settings", record_data)
    return {"success": True, "session_id": session_id, **record_data}


@router.get("/teacher/{teacher_id}/sessions-history")
async def get_teacher_sessions_history(
    teacher_id: str,
    page: int = 1,
    limit: int = 20,
    status: str = None,
    current_user: dict = Depends(get_current_user)
):
    _verify_teacher_access(teacher_id, current_user)
    teacher = await _resolve_teacher_record(teacher_id)
    resolved_teacher_id = teacher.get("id") if teacher else teacher_id
    result = await session_engine.get_teacher_sessions(
        teacher_id=resolved_teacher_id,
        page=page,
        limit=limit,
        status_filter=status
    )
    return result


@router.post("/sessions/auto-close")
async def auto_close_stale_sessions(
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_ADMIN]))
):
    result = await session_engine.auto_close_stale_sessions()
    return result


@router.get("/teacher/achievements/{teacher_id}")
async def get_teacher_achievements(
    teacher_id: str,
    current_user: dict = Depends(get_current_user)
):
    _verify_teacher_access(teacher_id, current_user)
    teacher = await _resolve_teacher_record(teacher_id)
    school_id = teacher.get("school_id") if teacher else current_user.get("tenant_id")
    resolved_teacher_id = teacher.get("id") if teacher else teacher_id

    assignments = await gd_find(db.session, "teacher_assignments", {"teacher_id": resolved_teacher_id, "is_active": True}, limit=200)
    tca_docs = await gd_find(db.session, "teacher_class_assignments", {"teacher_id": resolved_teacher_id}, limit=200)
    class_ids = list(set(a.get("class_id") for a in assignments if a.get("class_id")) | set(d.get("class_id") for d in tca_docs if d.get("class_id")))

    total_classes = len(class_ids)
    total_students = 0
    if class_ids:
        for cid in class_ids:
            count = await gd_count(db.session, "students", {"class_id": cid})
            total_students += count

    sessions = await gd_find(db.session, "teacher_sessions", {"teacher_id": resolved_teacher_id}, limit=500)
    completed_sessions = [s for s in sessions if s.get("status") in ("completed", "ended")]
    total_sessions = len(completed_sessions)

    att_total = 0
    att_present = 0
    if class_ids:
        att_total = await gd_count(db.session, "attendance", {"class_id": {"$in": class_ids}})
        att_present = await gd_count(db.session, "attendance", {"class_id": {"$in": class_ids}, "status": "present"})
    attendance_rate = round((att_present / att_total) * 100) if att_total > 0 else 0

    behavior_records = await gd_find(db.session, "behaviour_records", {"teacher_id": teacher_id}, limit=1000)
    if not behavior_records:
        behavior_records = await gd_find(db.session, "behaviour_records", {"recorded_by": teacher_id}, limit=1000)
    positive_behavior = len([b for b in behavior_records if b.get("type") == "positive" or (b.get("points") or 0) > 0])
    negative_behavior = len([b for b in behavior_records if b.get("type") == "negative" or (b.get("points") or 0) < 0])

    teacher_assessments = await gd_find(db.session, "assessments", {"teacher_id": teacher_id}, limit=500)
    if not teacher_assessments and class_ids:
        teacher_assessments = await gd_find(db.session, "assessments", {"class_id": {"$in": class_ids}}, limit=500)
    total_assessments = len(teacher_assessments)

    avg_performance = 0
    assessment_ids = [a["id"] for a in teacher_assessments if a.get("id")]
    if assessment_ids:
        submissions = await gd_find(db.session, "assessment_submissions", {"assessment_id": {"$in": assessment_ids}}, limit=2000)
        if submissions:
            scores = [s.get("percentage") or s.get("score") or 0 for s in submissions]
            avg_performance = round(sum(scores) / len(scores)) if scores else 0

    participation_total = 0
    participation_active = 0
    if class_ids:
        participation_total = await gd_count(db.session, "participation", {"class_id": {"$in": class_ids}})
        participation_active = await gd_count(db.session, "participation", {"class_id": {"$in": class_ids}, "status": {"$in": ["active", "participated"]}})
    if participation_total == 0:
        participation_total = await gd_count(db.session, "session_interactions", {"teacher_id": teacher_id, "type": "participation"})
        participation_active = await gd_count(db.session, "session_interactions", {"teacher_id": teacher_id, "type": "participation", "response": {"$ne": "no_answer"}})
    participation_rate = round((participation_active / participation_total) * 100) if participation_total > 0 else 0

    regularity_rate = 0
    if total_sessions > 0:
        proper_sessions = len([s for s in completed_sessions if s.get("ended_at")])
        regularity_rate = round((proper_sessions / total_sessions) * 100)

    metrics = {
        "total_sessions": total_sessions,
        "total_students": total_students,
        "total_classes": total_classes,
        "attendance_rate": attendance_rate,
        "participation_rate": participation_rate,
        "avg_performance": avg_performance,
        "total_assessments": total_assessments,
        "positive_behavior": positive_behavior,
        "negative_behavior": negative_behavior,
        "regularity_rate": regularity_rate,
        "total_behavior_records": len(behavior_records),
    }

    badge_defs = [
        {"id": "sessions_10", "threshold": 10, "metric": "total_sessions", "category": "teaching"},
        {"id": "sessions_50", "threshold": 50, "metric": "total_sessions", "category": "teaching"},
        {"id": "sessions_100", "threshold": 100, "metric": "total_sessions", "category": "teaching"},
        {"id": "attendance_90", "threshold": 90, "metric": "attendance_rate", "category": "attendance"},
        {"id": "students_50", "threshold": 50, "metric": "total_students", "category": "impact"},
        {"id": "participation_80", "threshold": 80, "metric": "participation_rate", "category": "engagement"},
        {"id": "performance_85", "threshold": 85, "metric": "avg_performance", "category": "academic"},
        {"id": "classes_5", "threshold": 5, "metric": "total_classes", "category": "diversity"},
        {"id": "assessments_20", "threshold": 20, "metric": "total_assessments", "category": "assessment"},
        {"id": "behavior_positive_50", "threshold": 50, "metric": "positive_behavior", "category": "behavior"},
        {"id": "regularity_95", "threshold": 95, "metric": "regularity_rate", "category": "discipline"},
    ]

    earned_badges = []
    in_progress_badges = []
    for bd in badge_defs:
        current_val = metrics.get(bd["metric"], 0)
        progress = min(100, round((current_val / bd["threshold"]) * 100)) if bd["threshold"] > 0 else 0
        badge_info = {**bd, "current": current_val, "progress": progress, "earned": current_val >= bd["threshold"]}
        if badge_info["earned"]:
            earned_badges.append(badge_info)
        else:
            in_progress_badges.append(badge_info)

    monthly_sessions = {}
    for s in completed_sessions:
        ca = s.get("created_at")
        if ca:
            month_key = ca[:7] if isinstance(ca, str) else ca.strftime("%Y-%m") if hasattr(ca, "strftime") else str(ca)[:7]
            monthly_sessions[month_key] = monthly_sessions.get(month_key, 0) + 1

    school_avg = {}
    if school_id:
        all_teachers = await gd_find(db.session, "teachers", {"school_id": school_id}, limit=200)
        if len(all_teachers) > 1:
            all_t_ids = [t["id"] for t in all_teachers]
            all_sessions = await gd_count(db.session, "teacher_sessions", {"teacher_id": {"$in": all_t_ids}, "status": {"$in": ["completed", "ended"]}})
            school_avg["avg_sessions"] = round(all_sessions / len(all_teachers))
            school_avg["teacher_count"] = len(all_teachers)

    return {
        "metrics": metrics,
        "earned_badges": earned_badges,
        "in_progress_badges": in_progress_badges,
        "monthly_sessions": monthly_sessions,
        "school_comparison": school_avg,
        "total_earned": len(earned_badges),
        "total_badges": len(badge_defs),
    }
