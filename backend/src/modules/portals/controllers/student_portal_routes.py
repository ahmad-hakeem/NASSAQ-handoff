"""
NASSAQ - Student Portal Routes
مسارات بوابة الطالب
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional, List
from datetime import datetime, timezone, timedelta
import uuid
from pydantic import BaseModel, Field, ConfigDict
from engines.sql_utils import (
    gd_find, gd_find_one, gd_insert, gd_insert_many, gd_update_one,
    gd_update_many, gd_count, gd_delete_one, gd_delete_many, gd_distinct,
    gd_iter_rows,
)
# FIX (D8): Use the canonical UserRole enum for the seed-account role string
# instead of a hardcoded "student" literal.
from dependencies import UserRole
from engines.timetable_session_lifecycle import find_live_timetable_sessions
from src.common.utils.subject_display import build_subject_name_map


# FIX (C2): Validate `send_student_message` payload via Pydantic so the backend
# rejects empty subjects, oversized blobs, and missing fields with a clear 422
# response instead of accepting any string the client sends.
class StudentMessageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    receiver_id: str = Field(..., min_length=1, max_length=64)
    subject: str = Field(..., min_length=1, max_length=200)
    content: str = Field(..., min_length=1, max_length=5000)


# FIX (C3): A timetable filtered exclusively by `status="published"` causes
# schools using other lifecycle states ("active", "current") to see an empty
# schedule. Centralize the accepted "live" states so all schedule lookups agree.
LIVE_TIMETABLE_STATUSES = ["published", "active", "current"]

# Keep aggregate IN clauses bounded without limiting the class itself.  The
# profile endpoint uses COUNT, while the points endpoint only materialises
# these IDs to calculate a rank.
CLASSMATE_ID_BATCH_SIZE = 500


def _class_student_filter(class_id, school_id):
    """Return the tenant- and active-scoped student filter for one class."""
    return {
        "class_id": class_id,
        "school_id": school_id,
        "is_active": {"$ne": False},
    }


def _batched_ids(ids, size=CLASSMATE_ID_BATCH_SIZE):
    """Yield bounded ID batches; this is not a limit on the class size."""
    for start in range(0, len(ids), size):
        yield ids[start:start + size]

import logging

logger = logging.getLogger("nassaq.student_portal_routes")


# FIX (D5): Centralize the repeated "look up student by id, then fall back
# to user_id" pattern that previously lived inline in every handler so that
# the resolution rules can be changed in one place. Defined at module scope
# so both setup_student_portal_routes and setup_homework_routes can call it.
async def _resolve_student(db, student_id: str, user_id: str):
    s = await gd_find_one(db.session, "students", {"id": student_id})
    if not s:
        s = await gd_find_one(db.session, "students", {"user_id": user_id})
    return s


def setup_student_portal_routes(db, get_current_user, require_roles, UserRole):
    """Setup student portal routes"""
    
    router = APIRouter(prefix="/student-portal", tags=["Student Portal"])

    # ============= DASHBOARD =============
    
    @router.get("/dashboard")
    async def get_student_dashboard(
        current_user: dict = Depends(require_roles([UserRole.STUDENT]))
    ):
        """لوحة تحكم الطالب"""
        student_id = current_user.get("student_id") or current_user.get("id")
        school_id = current_user.get("tenant_id")
        
        # Get student info
        student = await _resolve_student(db, student_id, current_user.get("id"))
        
        # Get today's schedule
        today = datetime.now().strftime("%A")
        day_map = {
            "Sunday": "الأحد", "Monday": "الاثنين", "Tuesday": "الثلاثاء",
            "Wednesday": "الأربعاء", "Thursday": "الخميس", "Friday": "الجمعة", "Saturday": "السبت"
        }
        today_ar = day_map.get(today, today)
        
        schedule_entries = []
        if student and student.get("class_id"):
            today_en = datetime.now().strftime("%A").lower()
            # FIX (C3): Accept any "live" lifecycle status, not just "published".
            timetable = await gd_find_one(db.session, "timetables", {"school_id": school_id, "status": {"$in": LIVE_TIMETABLE_STATUSES}}) or await gd_find_one(db.session, "timetables", {"school_id": school_id},
                sort=[("created_at", -1)])
            if timetable:
                sessions = await find_live_timetable_sessions(db.session, {
                        "school_id": school_id,
                        "timetable_id": timetable.get("id"),
                        "class_id": student.get("class_id"),
                        "day_of_week": today_en
                    }, limit=20)
                sub_ids = list(set(s.get("subject_id") for s in sessions if s.get("subject_id")))
                tch_ids = list(set(s.get("teacher_id") for s in sessions if s.get("teacher_id")))
                subs = await gd_find(db.session, "subjects", {"id": {"$in": sub_ids}}, limit=100)
                tchs = await gd_find(db.session, "teachers", {"id": {"$in": tch_ids}}, limit=100)
                sub_map = build_subject_name_map(subs)
                tch_map = {t["id"]: (t.get("full_name") or "") for t in tchs}
                for session in sorted(sessions, key=lambda x: x.get("period_number", 0)):
                    schedule_entries.append({
                        "period": session.get("period_number"),
                        "subject": (sub_map.get(session.get("subject_id"))
                                    or (session.get("subject_name") or "").strip()
                                    or "غير محدد"),
                        "teacher": (tch_map.get(session.get("teacher_id"))
                                    or (session.get("teacher_name") or "").strip()
                                    or "غير محدد"),
                        "start_time": session.get("start_time"),
                        "end_time": session.get("end_time")
                    })
        
        # Get recent grades
        recent_grades = []
        grades_list = await gd_find(db.session, "grades",
            {"student_id": student_id},
            order_by="date", desc_order=True, limit=5)
        for grade in grades_list:
            recent_grades.append({
                "subject": grade.get("subject"),
                "score": grade.get("score"),
                "max_score": grade.get("max_score"),
                "percentage": grade.get("percentage"),
                "assessment_type": grade.get("assessment_type"),
                "date": grade.get("date")
            })
        
        # FIX (C4): Combine four separate count queries into one fetch and tally
        # the statuses in Python. For a typical student record (~200 rows/year)
        # this trades a ~100-byte transfer for three saved round-trips.
        # Limit guards against runaway memory if a record is corrupted; a
        # student attending school for 50 years would still fit comfortably.
        attendance_rows = await gd_find(
            db.session,
            "attendance",
            {"student_id": student_id},
            limit=10000,
        )
        total_days = len(attendance_rows)
        present_days = sum(1 for r in attendance_rows if r.get("status") == "present")
        absent_days = sum(1 for r in attendance_rows if r.get("status") == "absent")
        late_days = sum(1 for r in attendance_rows if r.get("status") == "late")

        attendance_rate = (present_days / total_days * 100) if total_days > 0 else 100
        
        unread_notifications = await gd_count(db.session, "notifications", {
            "recipient_id": current_user.get("id"),
            "read_status": False
        })
        
        # Calculate GPA/average
        all_grades = await gd_find(db.session, "grades", {"student_id": student_id}, limit=1000)
        total_score = sum(g.get("percentage", 0) for g in all_grades)
        avg_score = total_score / len(all_grades) if all_grades else 0
        
        school_name = current_user.get("school_name")
        if not school_name and school_id:
            school_doc = await gd_find_one(db.session, "schools", {"id": school_id})
            school_name = school_doc.get("name") if school_doc else school_id

        return {
            "student": {
                "id": student.get("id") if student else student_id,
                "name": student.get("full_name") if student else current_user.get("full_name"),
                "grade": (student.get("grade_level") or student.get("grade")) if student else None,
                "class_name": student.get("class_name") if student else None,
                "school_name": school_name
            },
            "today_schedule": sorted(schedule_entries, key=lambda x: x.get("start_time", "")),
            "recent_grades": recent_grades,
            "attendance": {
                "total_days": total_days,
                "present": present_days,
                "absent": absent_days,
                "late": late_days,
                "rate": round(attendance_rate, 1)
            },
            "average_score": round(avg_score, 1),
            "unread_notifications": unread_notifications,
            "current_date": datetime.now().strftime("%Y-%m-%d"),
            "current_day": today_ar
        }
    
    # ============= GRADES =============
    
    @router.get("/grades")
    async def get_student_grades(
        subject: Optional[str] = None,
        assessment_type: Optional[str] = None,
        current_user: dict = Depends(require_roles([UserRole.STUDENT]))
    ):
        """درجات الطالب"""
        student_id = current_user.get("student_id") or current_user.get("id")
        school_id = current_user.get("tenant_id")

        # Tenant isolation: enforce school_id when available to prevent cross-school data leakage
        query = {"student_id": student_id}
        if school_id:
            query["school_id"] = school_id
        if subject:
            query["subject"] = subject
        if assessment_type:
            query["assessment_type"] = assessment_type
        
        grades = await gd_find(db.session, "grades", query, order_by="date", desc_order=True, limit=500)
        
        # Group by subject
        subjects_data = {}
        for grade in grades:
            subj = grade.get("subject", "غير محدد")
            if subj not in subjects_data:
                subjects_data[subj] = {
                    "subject": subj,
                    "grades": [],
                    "total_score": 0,
                    "total_max": 0,
                    "count": 0
                }
            
            subjects_data[subj]["grades"].append({
                "id": grade.get("id"),
                "score": grade.get("score"),
                "max_score": grade.get("max_score"),
                "percentage": grade.get("percentage"),
                "assessment_type": grade.get("assessment_type"),
                "date": grade.get("date"),
                "notes": grade.get("notes")
            })
            subjects_data[subj]["total_score"] += grade.get("score", 0)
            subjects_data[subj]["total_max"] += grade.get("max_score", 100)
            subjects_data[subj]["count"] += 1
        
        # Calculate averages
        for subj in subjects_data:
            data = subjects_data[subj]
            if data["total_max"] > 0:
                data["average"] = round((data["total_score"] / data["total_max"]) * 100, 1)
            else:
                data["average"] = 0
        
        # Overall stats
        total_grades = len(grades)
        overall_avg = sum(g.get("percentage", 0) for g in grades) / total_grades if total_grades > 0 else 0
        
        return {
            "subjects": list(subjects_data.values()),
            "total_grades": total_grades,
            "overall_average": round(overall_avg, 1),
            "assessment_types": list(set(g.get("assessment_type") for g in grades if g.get("assessment_type")))
        }
    
    # ============= ATTENDANCE =============
    
    @router.get("/attendance")
    async def get_student_attendance(
        month: Optional[int] = None,
        year: Optional[int] = None,
        current_user: dict = Depends(require_roles([UserRole.STUDENT]))
    ):
        """سجل حضور الطالب"""
        student_id = current_user.get("student_id") or current_user.get("id")
        school_id = current_user.get("tenant_id")

        # Tenant isolation: enforce school_id when available
        query = {"student_id": student_id}
        if school_id:
            query["school_id"] = school_id

        # Filter by month/year if provided
        if month and year:
            start_date = f"{year}-{month:02d}-01"
            if month == 12:
                end_date = f"{year + 1}-01-01"
            else:
                end_date = f"{year}-{month + 1:02d}-01"
            query["date"] = {"$gte": start_date, "$lt": end_date}
        
        records = await gd_find(db.session, "attendance", query, order_by="date", desc_order=True, limit=500)
        
        # Statistics
        total = len(records)
        present = sum(1 for r in records if r.get("status") == "present")
        absent = sum(1 for r in records if r.get("status") == "absent")
        late = sum(1 for r in records if r.get("status") == "late")
        excused = sum(1 for r in records if r.get("status") == "excused")
        
        attendance_rate = (present / total * 100) if total > 0 else 100
        
        return {
            "records": [
                {
                    "date": r.get("date"),
                    "status": r.get("status"),
                    "check_in_time": r.get("check_in_time"),
                    "check_out_time": r.get("check_out_time"),
                    "notes": r.get("notes")
                }
                for r in records
            ],
            "statistics": {
                "total_days": total,
                "present": present,
                "absent": absent,
                "late": late,
                "excused": excused,
                "attendance_rate": round(attendance_rate, 1)
            },
            "current_month": month or datetime.now().month,
            "current_year": year or datetime.now().year
        }
    
    # ============= SCHEDULE =============
    
    @router.get("/schedule")
    async def get_student_schedule(
        current_user: dict = Depends(require_roles([UserRole.STUDENT]))
    ):
        """الجدول الدراسي للطالب"""
        student_id = current_user.get("student_id") or current_user.get("id")
        school_id = current_user.get("tenant_id")
        
        # Get student info
        student = await _resolve_student(db, student_id, current_user.get("id"))
        
        if not student:
            return {"schedule": {}, "days": []}
        
        # Organize by day using timetable_sessions
        day_en_to_ar = {
            "sunday": "الأحد", "monday": "الاثنين", "tuesday": "الثلاثاء",
            "wednesday": "الأربعاء", "thursday": "الخميس", "friday": "الجمعة", "saturday": "السبت"
        }
        days_order = ["الأحد", "الاثنين", "الثلاثاء", "الأربعاء", "الخميس"]
        schedule_by_day = {day: [] for day in days_order}
        
        if student.get("class_id"):
            # FIX (C3): Accept any "live" lifecycle status, not just "published".
            timetable = await gd_find_one(db.session, "timetables", {"school_id": school_id, "status": {"$in": LIVE_TIMETABLE_STATUSES}}) or await gd_find_one(db.session, "timetables", {"school_id": school_id},
                sort=[("created_at", -1)])
            if timetable:
                all_sessions = await find_live_timetable_sessions(db.session, {
                        "school_id": school_id,
                        "timetable_id": timetable.get("id"),
                        "class_id": student.get("class_id")
                    }, limit=500)
                sub_ids = list(set(s.get("subject_id") for s in all_sessions if s.get("subject_id")))
                tch_ids = list(set(s.get("teacher_id") for s in all_sessions if s.get("teacher_id")))
                subs = await gd_find(db.session, "subjects", {"id": {"$in": sub_ids}}, limit=100)
                tchs = await gd_find(db.session, "teachers", {"id": {"$in": tch_ids}}, limit=100)
                sub_map = build_subject_name_map(subs)
                tch_map = {t["id"]: (t.get("full_name") or "") for t in tchs}
                for session in all_sessions:
                    day_ar = day_en_to_ar.get(session.get("day_of_week", ""), "")
                    if day_ar in schedule_by_day:
                        schedule_by_day[day_ar].append({
                            "period": session.get("period_number"),
                            "subject": (sub_map.get(session.get("subject_id"))
                                        or (session.get("subject_name") or "").strip()
                                        or "غير محدد"),
                            "teacher": (tch_map.get(session.get("teacher_id"))
                                        or (session.get("teacher_name") or "").strip()
                                        or "غير محدد"),
                            "start_time": session.get("start_time"),
                            "end_time": session.get("end_time")
                        })
        
        for day in schedule_by_day:
            schedule_by_day[day] = sorted(schedule_by_day[day], key=lambda x: x.get("period", 0))
        
        return {
            "schedule": schedule_by_day,
            "days": days_order,
            "student_info": {
                "class_id": student.get("class_id"),
                "class_name": student.get("class_name"),
                "grade_level": student.get("grade_level")
            }
        }
    
    # ============= MESSAGES =============
    
    @router.get("/messages")
    async def get_student_messages(
        current_user: dict = Depends(require_roles([UserRole.STUDENT]))
    ):
        """رسائل الطالب"""
        user_id = current_user.get("id")
        school_id = current_user.get("tenant_id")

        # Tenant isolation + schema fix: pg_models uses `recipient_id`; we also accept legacy
        # `receiver_id` for backward compat with older records stored in JSONB data column.
        query = {
            "$or": [
                {"sender_id": user_id},
                {"recipient_id": user_id},
                {"receiver_id": user_id},
            ]
        }
        if school_id:
            query["school_id"] = school_id

        messages = await gd_find(db.session, "messages", query, order_by="created_at", desc_order=True, limit=50)

        return {
            "messages": [
                {
                    "id": m.get("id"),
                    "subject": m.get("subject"),
                    "content": m.get("content") or m.get("body"),
                    "sender_id": m.get("sender_id"),
                    "sender_name": m.get("sender_name"),
                    # Expose canonical recipient_id; keep receiver_id alias for frontend backward compat
                    "recipient_id": m.get("recipient_id") or m.get("receiver_id"),
                    "receiver_id": m.get("recipient_id") or m.get("receiver_id"),
                    "receiver_name": m.get("receiver_name") or m.get("recipient_name"),
                    "is_sent": m.get("sender_id") == user_id,
                    "read_status": m.get("read_status", m.get("is_read", False)),
                    "created_at": m.get("created_at")
                }
                for m in messages
            ]
        }
    
    @router.post("/messages")
    async def send_student_message(
        payload: StudentMessageRequest,
        current_user: dict = Depends(require_roles([UserRole.STUDENT]))
    ):
        """إرسال رسالة من الطالب"""
        # FIX (C2): Pull validated values from the Pydantic body. The previous
        # signature used three loose query params with no length checks.
        receiver_id = payload.receiver_id
        subject = payload.subject
        content = payload.content
        tenant_id = current_user.get("tenant_id")
        receiver = await gd_find_one(db.session, "users", {"id": receiver_id})
        if not receiver:
            receiver = await gd_find_one(db.session, "teachers", {"id": receiver_id})

        if not receiver:
            raise HTTPException(status_code=404, detail="المستلم غير موجود")
        if not tenant_id or (receiver.get("tenant_id") != tenant_id and receiver.get("school_id") != tenant_id):
            raise HTTPException(status_code=403, detail="لا يمكنك مراسلة مستخدم من مدرسة أخرى")

        message = {
            "id": str(uuid.uuid4()),
            "school_id": tenant_id,
            "subject": subject,
            "content": content,
            "body": content,
            "sender_id": current_user.get("id"),
            "sender_name": current_user.get("full_name"),
            "sender_role": UserRole.STUDENT.value,
            "recipient_id": receiver_id,
            "receiver_id": receiver_id,
            "receiver_name": receiver.get("full_name") or receiver.get("name"),
            "read_status": False,
            "is_read": False,
            "created_at": datetime.now(timezone.utc).isoformat()
        }

        await gd_insert(db.session, "messages", message)

        # Create notification for receiver
        await gd_insert(db.session, "notifications", {
            "id": str(uuid.uuid4()),
            "school_id": tenant_id,
            "recipient_id": receiver_id,
            "notification_type": "message",
            "title": f"رسالة جديدة من {current_user.get('full_name')}",
            "message": subject,
            "read_status": False,
            "created_at": datetime.now(timezone.utc).isoformat()
        })

        return {"success": True, "message_id": message["id"]}
    
    # ============= TEACHERS LIST =============
    
    @router.get("/teachers")
    async def get_student_teachers(
        current_user: dict = Depends(require_roles([UserRole.STUDENT]))
    ):
        """قائمة معلمي الطالب"""
        student_id = current_user.get("student_id") or current_user.get("id")
        school_id = current_user.get("tenant_id")
        
        # Get student info
        student = await _resolve_student(db, student_id, current_user.get("id"))
        
        # Get teachers via timetable_sessions for this student's class
        teachers = []
        if student and student.get("class_id"):
            # FIX (C3): Accept any "live" lifecycle status, not just "published".
            timetable = await gd_find_one(db.session, "timetables", {"school_id": school_id, "status": {"$in": LIVE_TIMETABLE_STATUSES}}) or await gd_find_one(db.session, "timetables", {"school_id": school_id},
                sort=[("created_at", -1)])
            teacher_ids_set = set()
            teacher_subject_map = {}
            if timetable:
                sessions = await find_live_timetable_sessions(db.session, {
                        "school_id": school_id,
                        "timetable_id": timetable.get("id"),
                        "class_id": student.get("class_id")
                    }, limit=500)
                for s in sessions:
                    tid = s.get("teacher_id")
                    sid = s.get("subject_id")
                    if tid:
                        teacher_ids_set.add(tid)
                        if tid not in teacher_subject_map:
                            teacher_subject_map[tid] = set()
                        if sid:
                            teacher_subject_map[tid].add(sid)
            
            if teacher_ids_set:
                teacher_ids_list = list(teacher_ids_set)
                sub_ids = list(set(sid for sids in teacher_subject_map.values() for sid in sids))
                subs = await gd_find(db.session, "subjects", {"id": {"$in": sub_ids}}, limit=100)
                sub_name_map = build_subject_name_map(subs)
                
                teacher_docs = await gd_find(db.session, "teachers", {"id": {"$in": teacher_ids_list}, "school_id": school_id}, limit=100)
                
                for t in teacher_docs:
                    tid = t.get("id")
                    subject_names = [sub_name_map.get(sid, "") for sid in teacher_subject_map.get(tid, set()) if sub_name_map.get(sid)]
                    teachers.append({
                        "id": tid,
                        "name": t.get("full_name"),
                        "subjects": subject_names,
                        "email": t.get("email"),
                        "profile_picture": t.get("profile_picture")
                    })
        
        return {"teachers": teachers}
    
    # ============= PROFILE =============
    
    @router.get("/profile")
    async def get_student_profile(
        current_user: dict = Depends(require_roles([UserRole.STUDENT]))
    ):
        student_id = current_user.get("student_id") or current_user.get("id")
        school_id = current_user.get("tenant_id")
        
        student = await _resolve_student(db, student_id, current_user.get("id"))
        
        total_days = await gd_count(db.session, "attendance", {"student_id": student_id})
        present_days = await gd_count(db.session, "attendance", {"student_id": student_id, "status": "present"})
        attendance_rate = round((present_days / total_days * 100), 1) if total_days > 0 else 100
        
        all_grades = await gd_find(db.session, "grades", {"student_id": student_id}, limit=1000)
        avg_score = round(sum(g.get("percentage", 0) for g in all_grades) / len(all_grades), 1) if all_grades else 0
        
        behaviour_pos = await gd_count(db.session, "behaviour_records", {"student_id": student_id, "type": "positive"})
        behaviour_neg = await gd_count(db.session, "behaviour_records", {"student_id": student_id, "type": "negative"})
        
        participation = await gd_find(db.session, "participation_records", {"student_id": student_id}, limit=500)
        total_points = sum(p.get("points", 0) for p in participation)
        
        points_from_grades = len([g for g in all_grades if g.get("percentage", 0) >= 80]) * 5
        points_from_attendance = present_days * 2
        points_from_behaviour = behaviour_pos * 10
        total_score = total_points + points_from_grades + points_from_attendance + points_from_behaviour
        
        class_size = 0
        if student and student.get("class_id"):
            class_size = await gd_count(
                db.session,
                "students",
                _class_student_filter(student.get("class_id"), school_id),
            )
        
        profile_school_name = current_user.get("school_name")
        if not profile_school_name and school_id:
            school_doc = await gd_find_one(db.session, "schools", {"id": school_id})
            profile_school_name = school_doc.get("name") if school_doc else None

        return {
            "student": {
                "id": student.get("id") if student else student_id,
                "name": student.get("full_name") if student else current_user.get("full_name"),
                "name_en": student.get("full_name_en") if student else None,
                "email": student.get("email") if student else current_user.get("email"),
                "phone": student.get("phone") if student else None,
                "national_id": student.get("national_id") if student else None,
                "birth_date": (student.get("date_of_birth") or student.get("birth_date")) if student else None,
                "gender": student.get("gender") if student else None,
                "grade": (student.get("grade") or student.get("grade_level")) if student else None,
                "class_name": student.get("class_name") if student else None,
                "class_id": student.get("class_id") if student else None,
                "school_name": profile_school_name,
                "profile_picture": student.get("profile_picture") if student else None,
                "enrollment_date": student.get("enrollment_date") if student else None
            },
            "stats": {
                "total_points": total_score,
                "attendance_rate": attendance_rate,
                "average_score": avg_score,
                "total_grades": len(all_grades),
                "class_size": class_size
            }
        }
    
    # ============= ACTIVITIES =============

    @router.get("/activities")
    async def get_student_activities(
        current_user: dict = Depends(require_roles([UserRole.STUDENT]))
    ):
        student_id = current_user.get("student_id") or current_user.get("id")
        school_id = current_user.get("tenant_id")

        query = {"student_id": student_id}
        if school_id:
            query["school_id"] = school_id

        raw = await gd_find(db.session, "student_activities", query, order_by="date", desc_order=True, limit=100)

        activities = []
        for a in raw:
            activities.append({
                "id": a.get("id"),
                "name": a.get("name", ""),
                "type": a.get("type", "other"),
                "date": a.get("date", ""),
                "description": a.get("description", ""),
            })

        return {"activities": activities, "total": len(activities)}

    # ============= POINTS & GAMIFICATION =============
    
    @router.get("/points")
    async def get_student_points(
        current_user: dict = Depends(require_roles([UserRole.STUDENT]))
    ):
        student_id = current_user.get("student_id") or current_user.get("id")
        school_id = current_user.get("tenant_id")
        
        student = await _resolve_student(db, student_id, current_user.get("id"))
        if not student:
            raise HTTPException(status_code=404, detail="سجل الطالب غير موجود")
        
        participation = await gd_find(db.session, "participation_records", {"student_id": student_id}, limit=500)
        participation_points = sum(p.get("points", 0) for p in participation)
        
        all_grades = await gd_find(db.session, "grades", {"student_id": student_id}, limit=1000)
        grade_points = len([g for g in all_grades if g.get("percentage", 0) >= 80]) * 5
        
        total_days = await gd_count(db.session, "attendance", {"student_id": student_id})
        present_days = await gd_count(db.session, "attendance", {"student_id": student_id, "status": "present"})
        attendance_points = present_days * 2
        
        behaviour_pos = await gd_count(db.session, "behaviour_records", {"student_id": student_id, "type": "positive"})
        behaviour_points = behaviour_pos * 10
        
        total_score = participation_points + grade_points + attendance_points + behaviour_points
        
        if total_score >= 500:
            level = 5
            level_name = "متميز"
            level_name_en = "Outstanding"
        elif total_score >= 300:
            level = 4
            level_name = "متقدم"
            level_name_en = "Advanced"
        elif total_score >= 150:
            level = 3
            level_name = "جيد جداً"
            level_name_en = "Very Good"
        elif total_score >= 50:
            level = 2
            level_name = "جيد"
            level_name_en = "Good"
        else:
            level = 1
            level_name = "مبتدئ"
            level_name_en = "Beginner"
        
        rank = 1
        class_size = 1
        if student and student.get("class_id"):
            class_filter = _class_student_filter(student.get("class_id"), school_id)
            class_size = await gd_count(db.session, "students", class_filter)
            # Only IDs are needed for ranking.  DISTINCT avoids loading full
            # student rows, and batching below keeps every aggregate query's
            # IN list bounded without imposing a class-size ceiling.
            cm_ids = [
                cm_id for cm_id in await gd_distinct(
                    db.session, "students", "id", class_filter
                ) if cm_id
            ]

            from collections import defaultdict
            part_map = defaultdict(int)
            grade_map = defaultdict(int)
            attend_map = defaultdict(int)
            beh_map = defaultdict(int)
            for id_batch in _batched_ids(cm_ids):
                # _gd_aggregate materialises at most 50,000 matching rows
                # before grouping.  A high-activity class can exceed that
                # cap within one ID batch, so stream each collection through
                # keyset-paged reads and accumulate by student instead.
                async for record in gd_iter_rows(
                    db.session,
                    "participation_records",
                    {"student_id": {"$in": id_batch}},
                ):
                    sid = record.get("student_id")
                    part_map[sid] += record.get("points") or 0

                async for record in gd_iter_rows(
                    db.session,
                    "grades",
                    {
                        "student_id": {"$in": id_batch},
                        "percentage": {"$gte": 80},
                    },
                ):
                    grade_map[record.get("student_id")] += 5

                async for record in gd_iter_rows(
                    db.session,
                    "attendance",
                    {
                        "student_id": {"$in": id_batch},
                        "status": "present",
                    },
                ):
                    attend_map[record.get("student_id")] += 1

                async for record in gd_iter_rows(
                    db.session,
                    "behaviour_records",
                    {
                        "student_id": {"$in": id_batch},
                        "type": "positive",
                    },
                ):
                    beh_map[record.get("student_id")] += 1

            classmate_scores = []
            for cm_id in cm_ids:
                cm_total = part_map[cm_id] + grade_map[cm_id] + (attend_map[cm_id] * 2) + (beh_map[cm_id] * 10)
                classmate_scores.append({"id": cm_id, "score": cm_total})

            classmate_scores.sort(key=lambda x: x["score"], reverse=True)
            for i, cs in enumerate(classmate_scores):
                if cs["id"] == student_id:
                    rank = i + 1
                    break
        
        return {
            "total_score": total_score,
            "level": level,
            "level_name": level_name,
            "level_name_en": level_name_en,
            "rank": rank,
            "class_size": class_size,
            "breakdown": {
                "participation": participation_points,
                "grades": grade_points,
                "attendance": attendance_points,
                "behaviour": behaviour_points
            },
            "recent_points": [
                {"source": p.get("source", "مشاركة"), "points": p.get("points", 0), "date": p.get("created_at")}
                for p in sorted(participation, key=lambda x: x.get("created_at", ""), reverse=True)[:10]
            ]
        }
    
    # ============= PROGRESS =============
    
    @router.get("/progress")
    async def get_student_progress(
        current_user: dict = Depends(require_roles([UserRole.STUDENT]))
    ):
        student_id = current_user.get("student_id") or current_user.get("id")
        
        total_days = await gd_count(db.session, "attendance", {"student_id": student_id})
        present_days = await gd_count(db.session, "attendance", {"student_id": student_id, "status": "present"})
        absent_days = await gd_count(db.session, "attendance", {"student_id": student_id, "status": "absent"})
        late_days = await gd_count(db.session, "attendance", {"student_id": student_id, "status": "late"})
        attendance_rate = round((present_days / total_days * 100), 1) if total_days > 0 else 100
        
        all_grades = await gd_find(db.session, "grades", {"student_id": student_id}, limit=1000)
        avg_score = round(sum(g.get("percentage", 0) for g in all_grades) / len(all_grades), 1) if all_grades else 0
        
        subjects_data = {}
        for g in all_grades:
            subj = g.get("subject", "عام")
            if subj not in subjects_data:
                subjects_data[subj] = []
            subjects_data[subj].append(g.get("percentage", 0))
        subject_averages = [
            {"subject": k, "average": round(sum(v) / len(v), 1)} for k, v in subjects_data.items()
        ]
        
        tenant_id = current_user.get("tenant_id")
        assignment_filter = {"school_id": tenant_id} if tenant_id else {"school_id": "__none__"}
        total_assignments = await gd_count(db.session, "student_assignments", assignment_filter)
        submissions = await gd_find(db.session, "assignment_submissions", {"student_id": student_id}, limit=500)
        homework_rate = round((len(submissions) / max(1, total_assignments)) * 100, 1)
        
        participation = await gd_find(db.session, "participation_records", {"student_id": student_id}, limit=500)
        participation_count = len(participation)
        participation_rate = min(100, participation_count * 10)
        
        behaviour_pos = await gd_count(db.session, "behaviour_records", {"student_id": student_id, "type": "positive"})
        behaviour_neg = await gd_count(db.session, "behaviour_records", {"student_id": student_id, "type": "negative"})
        behaviour_total = behaviour_pos + behaviour_neg
        behaviour_quality = round(behaviour_pos / max(1, behaviour_total) * 100, 1)
        
        monthly_grades = {}
        for g in all_grades:
            date_str = g.get("date", "")
            if isinstance(date_str, str) and len(date_str) >= 7:
                month_key = date_str[:7]
                if month_key not in monthly_grades:
                    monthly_grades[month_key] = []
                monthly_grades[month_key].append(g.get("percentage", 0))
        
        monthly_trend = [
            {"month": k, "average": round(sum(v) / len(v), 1)}
            for k, v in sorted(monthly_grades.items())
        ]
        
        return {
            "attendance": {
                "rate": attendance_rate,
                "present": present_days,
                "absent": absent_days,
                "late": late_days,
                "total": total_days
            },
            "academics": {
                "average": avg_score,
                "total_grades": len(all_grades),
                "subject_averages": subject_averages,
                "monthly_trend": monthly_trend
            },
            "homework": {
                "rate": homework_rate,
                "submitted": len(submissions),
                "total": total_assignments
            },
            "participation": {
                "rate": participation_rate,
                "count": participation_count
            },
            "behaviour": {
                "quality": behaviour_quality,
                "positive": behaviour_pos,
                "negative": behaviour_neg,
                "total": behaviour_total
            }
        }
    
    # ============= ACHIEVEMENTS =============
    
    @router.get("/achievements")
    async def get_student_achievements(
        current_user: dict = Depends(require_roles([UserRole.STUDENT]))
    ):
        student_id = current_user.get("student_id") or current_user.get("id")
        
        total_days = await gd_count(db.session, "attendance", {"student_id": student_id})
        present_days = await gd_count(db.session, "attendance", {"student_id": student_id, "status": "present"})
        attendance_rate = round((present_days / total_days * 100), 1) if total_days > 0 else 100
        
        all_grades = await gd_find(db.session, "grades", {"student_id": student_id}, limit=1000)
        avg_score = round(sum(g.get("percentage", 0) for g in all_grades) / len(all_grades), 1) if all_grades else 0
        
        submissions = await gd_find(db.session, "assignment_submissions", {"student_id": student_id}, limit=500)
        
        participation = await gd_find(db.session, "participation_records", {"student_id": student_id}, limit=500)
        
        behaviour_pos = await gd_count(db.session, "behaviour_records", {"student_id": student_id, "type": "positive"})
        
        achievements = []
        
        if len(participation) >= 10:
            achievements.append({
                "id": "best_participant",
                "title_ar": "أفضل مشارك",
                "title_en": "Best Participant",
                "description_ar": "شارك أكثر من 10 مرات في الحصص",
                "description_en": "Participated more than 10 times in classes",
                "icon": "star",
                "color": "gold",
                "earned": True
            })
        
        if len(all_grades) >= 5:
            recent_5 = sorted(all_grades, key=lambda x: x.get("date", ""), reverse=True)[:5]
            old_5 = sorted(all_grades, key=lambda x: x.get("date", ""))[:5]
            recent_avg = sum(g.get("percentage", 0) for g in recent_5) / len(recent_5)
            old_avg = sum(g.get("percentage", 0) for g in old_5) / len(old_5)
            if recent_avg > old_avg + 5:
                achievements.append({
                    "id": "best_improvement",
                    "title_ar": "أفضل تحسن",
                    "title_en": "Best Improvement",
                    "description_ar": "تحسن أداؤك الدراسي بشكل ملحوظ",
                    "description_en": "Your academic performance improved significantly",
                    "icon": "trending-up",
                    "color": "green",
                    "earned": True
                })
        
        if attendance_rate >= 95:
            achievements.append({
                "id": "perfect_attendance",
                "title_ar": "الالتزام بالحضور",
                "title_en": "Perfect Attendance",
                "description_ar": "نسبة حضور 95% أو أعلى",
                "description_en": "95%+ attendance rate",
                "icon": "check-circle",
                "color": "blue",
                "earned": True
            })
        
        if len(submissions) >= 5:
            achievements.append({
                "id": "homework_hero",
                "title_ar": "بطل الواجبات",
                "title_en": "Homework Hero",
                "description_ar": "أكمل 5 واجبات أو أكثر",
                "description_en": "Completed 5+ assignments",
                "icon": "clipboard-check",
                "color": "purple",
                "earned": True
            })
        
        if avg_score >= 90:
            achievements.append({
                "id": "honor_student",
                "title_ar": "طالب متفوق",
                "title_en": "Honor Student",
                "description_ar": "معدل 90% أو أعلى",
                "description_en": "90%+ average score",
                "icon": "award",
                "color": "gold",
                "earned": True
            })
        
        if behaviour_pos >= 5:
            achievements.append({
                "id": "good_behavior",
                "title_ar": "سلوك مثالي",
                "title_en": "Good Behavior",
                "description_ar": "حصل على 5 نقاط سلوك إيجابية أو أكثر",
                "description_en": "Earned 5+ positive behavior points",
                "icon": "heart",
                "color": "red",
                "earned": True
            })
        
        all_possible = [
            {"id": "best_participant", "title_ar": "أفضل مشارك", "title_en": "Best Participant", "icon": "star", "color": "gold", "earned": False},
            {"id": "best_improvement", "title_ar": "أفضل تحسن", "title_en": "Best Improvement", "icon": "trending-up", "color": "green", "earned": False},
            {"id": "perfect_attendance", "title_ar": "الالتزام بالحضور", "title_en": "Perfect Attendance", "icon": "check-circle", "color": "blue", "earned": False},
            {"id": "homework_hero", "title_ar": "بطل الواجبات", "title_en": "Homework Hero", "icon": "clipboard-check", "color": "purple", "earned": False},
            {"id": "honor_student", "title_ar": "طالب متفوق", "title_en": "Honor Student", "icon": "award", "color": "gold", "earned": False},
            {"id": "good_behavior", "title_ar": "سلوك مثالي", "title_en": "Good Behavior", "icon": "heart", "color": "red", "earned": False},
        ]
        
        earned_ids = {a["id"] for a in achievements}
        locked = [a for a in all_possible if a["id"] not in earned_ids]
        
        return {
            "earned": achievements,
            "locked": locked,
            "total_earned": len(achievements),
            "total_possible": len(all_possible)
        }
    
    @router.get("/homework")
    async def get_student_homework(
        status: Optional[str] = None,
        current_user: dict = Depends(require_roles([UserRole.STUDENT]))
    ):
        student_id = current_user.get("student_id") or current_user.get("id")
        school_id = current_user.get("tenant_id")
        
        student = await _resolve_student(db, student_id, current_user.get("id"))
        
        class_id = student.get("class_id") if student else None
        grade_id = (student.get("grade_id") or student.get("grade")) if student else None
        
        query = {"school_id": school_id}
        if class_id:
            query["$or"] = [
                {"class_ids": class_id},
                {"class_id": class_id},
                {"grade_id": grade_id}
            ]
        
        assignments = await gd_find(db.session, "student_assignments", query, order_by="due_date", desc_order=True, limit=100)
        
        submissions = await gd_find(db.session, "assignment_submissions", {"student_id": student_id}, limit=200)
        sub_map = {s.get("assignment_id"): s for s in submissions}
        
        result = []
        for a in assignments:
            sub = sub_map.get(a.get("id"), {})
            hw_status = sub.get("status", "pending") if sub else "pending"
            if status and hw_status != status:
                continue
            result.append({
                "id": a.get("id"),
                "title": a.get("title"),
                "subject": a.get("subject_name", a.get("subject", "")),
                "due_date": a.get("due_date"),
                "type": a.get("type", "homework"),
                "status": hw_status,
                "grade": sub.get("grade"),
                "submitted_at": sub.get("submitted_at"),
                "description": a.get("description", ""),
            })
        
        return {"homework": result, "total": len(result)}

    setup_homework_routes(router, db, get_current_user, require_roles, UserRole)
    
    return router


# ============= TEST ACCOUNTS CREATION =============

async def create_test_student_account(db):
    """Create test student account for testing"""
    import bcrypt
    from datetime import datetime, timezone
    import uuid
    
    # Check if test student already exists
    existing = await gd_find_one(db.session, "users", {"email": "student@nassaq.com"})
    if existing:
        return existing
    
    # Get first school
    school = await gd_find_one(db.session, "schools", {"status": "active"})
    if not school:
        return None
    
    # Create student user
    student_user_id = str(uuid.uuid4())
    student_id = str(uuid.uuid4())
    
    password_hash = bcrypt.hashpw("Student@123".encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    
    # Create user record
    user_doc = {
        "id": student_user_id,
        "email": "student@nassaq.com",
        "password_hash": password_hash,
        "full_name": "طالب تجريبي",
        "full_name_en": "Test Student",
        "role": UserRole.STUDENT.value,
        "tenant_id": school.get("id"),
        "phone": "0512345678",
        "is_active": True,
        "must_change_password": False,
        "student_id": student_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    await gd_insert(db.session, "users", user_doc)
    
    # Create student record
    student_doc = {
        "id": student_id,
        "user_id": student_user_id,
        "full_name": "طالب تجريبي",
        "full_name_en": "Test Student",
        "email": "student@nassaq.com",
        "phone": "0512345678",
        "school_id": school.get("id"),
        "school_name": school.get("name"),
        "grade": "الصف الأول",
        "class_name": "الفصل أ",
        "national_id": "1234567890",
        "birth_date": "2010-01-15",
        "gender": "male",
        "parent_phone": "0509876543",
        "parent_name": "ولي أمر تجريبي",
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await gd_insert(db.session, "students", student_doc)

    # Recompute the school's stored counts from live rows (Task #826) so the
    # denormalized columns stay accurate instead of drifting.
    from engines.entity_counts import reconcile_school_counts
    await reconcile_school_counts(db.session, school.get("id"))

    # Add some test grades
    subjects = ["الرياضيات", "اللغة العربية", "العلوم", "اللغة الإنجليزية"]
    for subject in subjects:
        for i in range(3):
            grade_doc = {
                "id": str(uuid.uuid4()),
                "student_id": student_id,
                "subject": subject,
                "score": 75 + (i * 5),
                "max_score": 100,
                "percentage": 75 + (i * 5),
                "assessment_type": ["اختبار شهري", "اختبار نهائي", "واجب"][i],
                "date": f"2026-03-{10 - i}",
                "created_at": datetime.now(timezone.utc).isoformat()
            }
            await gd_insert(db.session, "grades", grade_doc)
    
    # Add some test attendance
    for i in range(20):
        status = "present" if i < 17 else ("late" if i < 19 else "absent")
        attendance_doc = {
            "id": str(uuid.uuid4()),
            "student_id": student_id,
            "date": f"2026-02-{(i % 28) + 1:02d}",
            "status": status,
            "check_in_time": "07:30" if status == "present" else "08:00",
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        await gd_insert(db.session, "attendance", attendance_doc)
    
    return user_doc


async def create_test_parent_account(db):
    """Create test parent account for testing"""
    import bcrypt
    from datetime import datetime, timezone
    import uuid
    
    # Check if test parent already exists
    existing = await gd_find_one(db.session, "users", {"email": "parent@nassaq.com"})
    if existing:
        return existing
    
    # Get test student
    test_student = await gd_find_one(db.session, "students", {"email": "student@nassaq.com"})
    school = await gd_find_one(db.session, "schools", {"status": "active"})
    
    if not school:
        return None
    
    # Create parent user
    parent_user_id = str(uuid.uuid4())
    parent_id = str(uuid.uuid4())
    
    password_hash = bcrypt.hashpw("Parent@123".encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    
    # Create user record
    user_doc = {
        "id": parent_user_id,
        "email": "parent@nassaq.com",
        "password_hash": password_hash,
        "full_name": "ولي أمر تجريبي",
        "full_name_en": "Test Parent",
        "role": "parent",
        "tenant_id": school.get("id"),
        "phone": "0509876543",
        "is_active": True,
        "must_change_password": False,
        "parent_id": parent_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    await gd_insert(db.session, "users", user_doc)
    
    # Link parent to student
    if test_student:
        await gd_update_one(db.session, "students", {"id": test_student.get("id")}, {
                "parent_id": parent_id,
                "parent_user_id": parent_user_id,
                "parent_phone": "0509876543",
                "parent_name": "ولي أمر تجريبي"
            })
    
    return user_doc


# ============= HOMEWORK/ASSIGNMENTS APIs =============

def setup_homework_routes(router, db, get_current_user, require_roles, UserRole):
    """Setup homework routes for students"""
    
    @router.get("/assignments")
    async def get_student_assignments(
        status: Optional[str] = None,  # pending, submitted, graded, late
        current_user: dict = Depends(require_roles([UserRole.STUDENT]))
    ):
        """
        الحصول على واجبات الطالب
        Get student assignments
        """
        student_id = current_user.get("student_id") or current_user.get("id")
        school_id = current_user.get("tenant_id")
        
        # Get student info for class
        student = await _resolve_student(db, student_id, current_user.get("id"))
        
        class_id = student.get("class_id") if student else None
        grade_id = (student.get("grade_id") or student.get("grade")) if student else None
        
        # Build query for assignments
        query = {"school_id": school_id, "is_active": True}
        
        if class_id:
            query["$or"] = [
                {"class_ids": class_id},
                {"class_id": class_id},
                {"grade_id": grade_id}
            ]
        
        # Get assignments
        assignments = await gd_find(db.session, "student_assignments", query, order_by="due_date", desc_order=True, limit=100)

        # Get student submissions
        submissions = await gd_find(db.session, "assignment_submissions", {"student_id": student_id}, limit=500)

        submission_map = {s.get("assignment_id"): s for s in submissions}

        # FIX (B4): Eliminate N+1 queries by batch-loading every subject and teacher
        # referenced by the assignment list with a single $in query per collection.
        subject_ids = list({a.get("subject_id") for a in assignments if a.get("subject_id")})
        teacher_ids = list({a.get("teacher_id") for a in assignments if a.get("teacher_id")})

        subject_map: dict = {}
        if subject_ids:
            subjects_rows = await gd_find(db.session, "subjects", {"id": {"$in": subject_ids}}, limit=len(subject_ids))
            subject_map = {s.get("id"): s for s in subjects_rows}
            missing_subject_ids = [sid for sid in subject_ids if sid not in subject_map]
            if missing_subject_ids:
                ref_rows = await gd_find(db.session, "reference_subjects", {"id": {"$in": missing_subject_ids}}, limit=len(missing_subject_ids))
                for s in ref_rows:
                    subject_map[s.get("id")] = s

        teacher_map: dict = {}
        if teacher_ids:
            teachers_rows = await gd_find(db.session, "teachers", {"id": {"$in": teacher_ids}}, limit=len(teacher_ids))
            teacher_map = {t.get("id"): t for t in teachers_rows}

        # Enrich assignments
        result = []
        now = datetime.now(timezone.utc)

        for a in assignments:
            assignment_id = a.get("id")
            submission = submission_map.get(assignment_id)

            # FIX (B7): If due_date is missing/unparseable, leave it as None instead
            # of silently inventing a fake one (now + 7 days). Such an assignment
            # can never be considered "late" until a real due_date is provided.
            due_date_str = a.get("due_date")
            due_date = None
            try:
                if isinstance(due_date_str, str) and due_date_str:
                    due_date = datetime.fromisoformat(due_date_str.replace('Z', '+00:00'))
                elif isinstance(due_date_str, datetime):
                    due_date = due_date_str
            except Exception as e:
                logger.warning(f"Assignment {assignment_id} has unparseable due_date '{due_date_str}': {e}")
                due_date = None

            if submission:
                if submission.get("grade") is not None:
                    a_status = "graded"
                else:
                    a_status = "submitted"
            elif due_date is not None and due_date < now:
                a_status = "late"
            else:
                a_status = "pending"

            if status and a_status != status:
                continue

            subject = subject_map.get(a.get("subject_id"))
            teacher = teacher_map.get(a.get("teacher_id"))

            result.append({
                "id": assignment_id,
                "title": a.get("title", ""),
                "description": a.get("description", ""),
                "subject_id": a.get("subject_id"),
                "subject_name": (subject.get("name_ar") or subject.get("name")) if subject else "",
                "teacher_id": a.get("teacher_id"),
                "teacher_name": (teacher.get("full_name") or teacher.get("full_name_ar")) if teacher else "",
                "due_date": due_date_str,
                "max_grade": a.get("max_grade", 100),
                "status": a_status,
                "grade": submission.get("grade") if submission else None,
                "feedback": submission.get("feedback") if submission else None,
                "submission_date": submission.get("submitted_at") if submission else None,
                "created_at": a.get("created_at")
            })
        
        return {
            "assignments": result,
            "total": len(result),
            "statistics": {
                "pending": len([a for a in result if a["status"] == "pending"]),
                "submitted": len([a for a in result if a["status"] == "submitted"]),
                "graded": len([a for a in result if a["status"] == "graded"]),
                "late": len([a for a in result if a["status"] == "late"])
            }
        }
    
    @router.post("/assignments/{assignment_id}/submit")
    async def submit_assignment(
        assignment_id: str,
        content: str = None,
        current_user: dict = Depends(require_roles([UserRole.STUDENT]))
    ):
        """
        تسليم واجب
        Submit an assignment
        """
        student_id = current_user.get("student_id") or current_user.get("id")
        
        # Check assignment exists
        assignment = await gd_find_one(db.session, "student_assignments", {"id": assignment_id})
        if not assignment:
            raise HTTPException(status_code=404, detail="الواجب غير موجود")
        
        # Check not already submitted
        existing = await gd_find_one(db.session, "assignment_submissions", {
            "assignment_id": assignment_id,
            "student_id": student_id
        })
        
        if existing:
            raise HTTPException(status_code=400, detail="تم تسليم هذا الواجب مسبقاً")
        
        # Create submission
        submission_doc = {
            "id": str(uuid.uuid4()),
            "assignment_id": assignment_id,
            "student_id": student_id,
            "content": content or "",
            "submitted_at": datetime.now(timezone.utc).isoformat(),
            "is_late": datetime.now(timezone.utc) > datetime.fromisoformat(assignment.get("due_date", "2099-12-31").replace('Z', '+00:00')),
            "grade": None,
            "feedback": None
        }
        
        await gd_insert(db.session, "assignment_submissions", submission_doc)
        
        return {
            "success": True,
            "submission_id": submission_doc["id"],
            "message_ar": "تم تسليم الواجب بنجاح",
            "message_en": "Assignment submitted successfully"
        }
    
    @router.get("/assignments/{assignment_id}")
    async def get_assignment_details(
        assignment_id: str,
        current_user: dict = Depends(require_roles([UserRole.STUDENT]))
    ):
        """تفاصيل الواجب"""
        student_id = current_user.get("student_id") or current_user.get("id")
        school_id = current_user.get("tenant_id")

        assignment = await gd_find_one(db.session, "student_assignments", {"id": assignment_id})
        if not assignment:
            raise HTTPException(status_code=404, detail="الواجب غير موجود")

        # SECURITY (A1): Verify the assignment actually belongs to the student's school
        # AND to one of their classes/grades. Without this check any student could read
        # any assignment by guessing the ID (IDOR).
        if school_id and assignment.get("school_id") and assignment.get("school_id") != school_id:
            raise HTTPException(status_code=404, detail="الواجب غير موجود")

        student = await _resolve_student(db, student_id, current_user.get("id"))
        if not student:
            raise HTTPException(status_code=404, detail="الطالب غير موجود")

        student_class_id = student.get("class_id")
        student_grade_id = student.get("grade_id") or student.get("grade")
        a_class_ids = assignment.get("class_ids") or []
        if not isinstance(a_class_ids, list):
            a_class_ids = [a_class_ids]

        belongs_to_student = (
            (student_class_id and assignment.get("class_id") == student_class_id)
            or (student_class_id and student_class_id in a_class_ids)
            or (student_grade_id and assignment.get("grade_id") == student_grade_id)
        )
        if not belongs_to_student:
            raise HTTPException(status_code=404, detail="الواجب غير موجود")

        # Get submission
        submission = await gd_find_one(db.session, "assignment_submissions", {
            "assignment_id": assignment_id,
            "student_id": student_id
        })

        return {
            **assignment,
            "submission": submission
        }

    @router.get("/my-analytics")
    async def get_student_my_analytics(
        current_user: dict = Depends(require_roles([UserRole.STUDENT]))
    ):
        student_id = current_user.get("student_id") or current_user.get("id")
        school_id = current_user.get("tenant_id")

        student = await _resolve_student(db, student_id, current_user.get("id"))
        if not student:
            raise HTTPException(status_code=404, detail="الطالب غير موجود")
        student_id = student.get("id", student_id)

        all_grades = await gd_find(db.session, "grades", {"student_id": student_id}, limit=1000)
        overall_avg = round(sum(g.get("percentage", 0) for g in all_grades) / len(all_grades), 1) if all_grades else 0

        # FIX (B5): Some grade rows store only `subject_id` (a UUID) and lack the
        # human-readable `subject_name`. Falling back to the UUID as a grouping
        # key produced empty radar charts and meaningless labels. Resolve every
        # subject_id to its Arabic/English name in a single batched query and
        # build a uuid→name map before iterating the grades.
        subject_ids_in_grades = list({g.get("subject_id") for g in all_grades if g.get("subject_id") and not g.get("subject_name")})
        subject_name_by_id: dict = {}
        if subject_ids_in_grades:
            subj_rows = await gd_find(db.session, "subjects", {"id": {"$in": subject_ids_in_grades}}, limit=len(subject_ids_in_grades))
            for s in subj_rows:
                subject_name_by_id[s.get("id")] = s.get("name_ar") or s.get("name") or ""
            missing = [sid for sid in subject_ids_in_grades if sid not in subject_name_by_id]
            if missing:
                ref_rows = await gd_find(db.session, "reference_subjects", {"id": {"$in": missing}}, limit=len(missing))
                for s in ref_rows:
                    subject_name_by_id[s.get("id")] = s.get("name_ar") or s.get("name") or ""

        target_subjects = {"رياضيات": 0, "علوم": 0, "عربي": 0, "إنجليزي": 0, "مهارات رقمية": 0}
        subject_counts = {k: 0 for k in target_subjects}
        subject_all = {}
        for g in all_grades:
            subj = g.get("subject_name") or subject_name_by_id.get(g.get("subject_id")) or "عام"
            if subj not in subject_all:
                subject_all[subj] = []
            subject_all[subj].append(g.get("percentage", 0))
            for key in target_subjects:
                if key in subj:
                    target_subjects[key] += g.get("percentage", 0)
                    subject_counts[key] += 1
                    break

        radar_data = []
        for subj, total in target_subjects.items():
            count = subject_counts[subj]
            radar_data.append({"subject": subj, "score": round(total / count, 1) if count > 0 else 0})

        monthly_data = {}
        for g in all_grades:
            date_str = str(g.get("date", ""))
            if date_str and len(date_str) >= 7:
                month_key = date_str[:7]
                if month_key not in monthly_data:
                    monthly_data[month_key] = []
                monthly_data[month_key].append(g.get("percentage", 0))

        line_chart_data = sorted([
            {"month": k, "average": round(sum(v) / len(v), 1)}
            for k, v in monthly_data.items()
        ], key=lambda x: x["month"])

        class_id = student.get("class_id")
        class_avg = 0
        if class_id:
            classmates = await gd_find(db.session, "students", {"class_id": class_id, "school_id": school_id}, limit=100)
            classmate_ids = [c.get("id") for c in classmates if c.get("id") != student_id]
            if classmate_ids:
                class_grades = await gd_find(db.session, "grades", {
                    "student_id": {"$in": classmate_ids}
                }, limit=5000)
                class_avg = round(sum(g.get("percentage", 0) for g in class_grades) / len(class_grades), 1) if class_grades else 0

        strengths = []
        weaknesses = []
        for subj, scores in subject_all.items():
            avg = round(sum(scores) / len(scores), 1) if scores else 0
            if avg >= 80:
                strengths.append({"area": subj, "detail": f"متوسط {avg}%"})
            elif avg < 60:
                weaknesses.append({"area": subj, "detail": f"متوسط {avg}%"})

        total_participation = await gd_count(db.session, "participation_records", {"student_id": student_id})
        if total_participation > 20:
            strengths.append({"area": "مشاركة صفية", "detail": f"{total_participation} مشاركة مسجلة"})

        if overall_avg >= 90:
            level = "ممتاز"
        elif overall_avg >= 80:
            level = "جيد جداً"
        elif overall_avg >= 70:
            level = "جيد"
        elif overall_avg >= 60:
            level = "مقبول"
        else:
            level = "ضعيف"

        return {
            "student_name": student.get("full_name"),
            "summary": {
                "overall_average": overall_avg,
                "level": level,
                "class_average": class_avg,
                "total_assessments": len(all_grades),
            },
            "gauge_data": {"value": overall_avg, "level": level},
            "line_chart_data": line_chart_data,
            "radar_data": radar_data,
            "strengths": strengths,
            "weaknesses": weaknesses,
        }

    return router
