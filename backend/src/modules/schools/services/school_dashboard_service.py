"""
School Dashboard Service
Handles School Principal dashboard metrics (live attendance, sessions, alerts, interventions)
and Landing Page public statistics / growth indicators with aggressive caching and security floors.
"""
from fastapi import HTTPException
from typing import Dict, Any, Optional
from datetime import datetime, timezone, timedelta
import logging
import time as _time

from engines.sql_utils import (
    gd_find, gd_find_one, gd_count, _gd_aggregate,
)

logger = logging.getLogger("nassaq")

_public_stats_cache = {"data": None, "expires": 0}
_PUBLIC_STATS_TTL = 60

_public_schools_count_cache = {"data": None, "expires": 0}
_PUBLIC_SCHOOLS_COUNT_TTL = 300

_public_growth_cache = {"data": None, "expires": 0}
_PUBLIC_GROWTH_TTL = 300


def bucket_display(n: int) -> str:
    """Bucket a raw count into a vetted display string."""
    try:
        n = int(n or 0)
    except (TypeError, ValueError):
        n = 0
    if n <= 0:
        return "10+"
    buckets = [
        (10, "10+"), (25, "25+"), (50, "50+"), (100, "100+"),
        (250, "250+"), (500, "500+"), (1000, "1K+"),
        (2500, "2.5K+"), (5000, "5K+"), (10000, "10K+"),
        (25000, "25K+"), (50000, "50K+"), (100000, "100K+"),
    ]
    chosen = "10+"
    for threshold, label in buckets:
        if n >= threshold:
            chosen = label
        else:
            break
    return chosen


class SchoolDashboardService:
    """Service handling School Dashboard metrics and public platform statistics."""

    @staticmethod
    async def get_school_dashboard_data(session, current_user: dict) -> dict:
        school_id = current_user.get("tenant_id")
        if not school_id:
            raise HTTPException(status_code=400, detail="المستخدم غير مرتبط بمدرسة")

        total_students = await gd_count(session, "students", {"school_id": school_id, "is_active": True})
        total_teachers = await gd_count(session, "teachers", {"school_id": school_id, "is_active": True})
        total_classes = await gd_count(session, "classes", {"school_id": school_id, "is_active": True})

        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        student_attendance = await gd_find(session, "attendance", {
            "school_id": school_id,
            "date": today,
            "type": "student"
        }, limit=10000)

        teacher_attendance_records = await gd_find(session, "teacher_attendance", {
            "school_id": school_id,
            "date": today
        }, limit=1000)

        if not teacher_attendance_records:
            teacher_attendance_records = await gd_find(session, "attendance", {
                "school_id": school_id,
                "date": today,
                "type": "teacher"
            }, limit=1000)

        student_present = len([a for a in student_attendance if a.get("status") == "present"])
        student_absent = len([a for a in student_attendance if a.get("status") == "absent"])
        student_late = len([a for a in student_attendance if a.get("status") == "late"])
        student_excused = len([a for a in student_attendance if a.get("status") == "excused"])

        teacher_present = len([a for a in teacher_attendance_records if a.get("status") == "present"])
        teacher_absent = len([a for a in teacher_attendance_records if a.get("status") == "absent"])
        teacher_late = len([a for a in teacher_attendance_records if a.get("status") == "late"])
        teacher_excused = len([a for a in teacher_attendance_records if a.get("status") == "excused"])

        today_day = datetime.now(timezone.utc).strftime("%A").lower()
        sessions_count = await gd_count(session, "schedule_sessions", {
            "school_id": school_id,
            "day_of_week": today_day
        })

        alerts = await gd_find(session, "notifications", {
            "school_id": school_id
        }, order_by="created_at", desc_order=True, limit=10)

        total_student_today = len(student_attendance)
        student_attendance_rate = round((student_present / total_student_today) * 100, 1) if total_student_today > 0 else 0

        total_teacher_today = len(teacher_attendance_records)
        teacher_attendance_rate = round((teacher_present / total_teacher_today) * 100, 1) if total_teacher_today > 0 else 0

        thirty_days_ago = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%d")

        frequent_absence_pipeline = [
            {"$match": {"school_id": school_id, "status": "absent", "date": {"$gte": thirty_days_ago}}},
            {"$group": {"_id": "$teacher_id", "count": {"$sum": 1}}},
            {"$match": {"count": {"$gt": 2}}}
        ]
        frequent_absences = await _gd_aggregate(session, "teacher_attendance", frequent_absence_pipeline)

        if not frequent_absences:
            frequent_absence_pipeline_old = [
                {"$match": {"school_id": school_id, "type": "teacher", "status": "absent", "date": {"$gte": thirty_days_ago}}},
                {"$group": {"_id": "$teacher_id", "count": {"$sum": 1}}},
                {"$match": {"count": {"$gt": 2}}}
            ]
            frequent_absences = await _gd_aggregate(session, "attendance", frequent_absence_pipeline_old)

        teachers_frequent_absence = len(frequent_absences)

        classes_low_attendance = 0
        all_classes = await gd_find(session, "classes", {"school_id": school_id, "is_active": True}, limit=100)
        for cls in all_classes:
            class_attendance = [a for a in student_attendance if a.get("class_id") == cls["id"]]
            if class_attendance:
                present_count = len([a for a in class_attendance if a.get("status") == "present"])
                rate = (present_count / len(class_attendance)) * 100 if class_attendance else 0
                if rate < 80:
                    classes_low_attendance += 1

        dynamic_alerts = []
        if teacher_absent > 0:
            dynamic_alerts.append({
                "id": "alert-1",
                "type": "warning",
                "title_ar": f"{teacher_absent} معلم غائب اليوم",
                "title_en": f"{teacher_absent} teacher(s) absent today",
                "time_ar": "اليوم",
                "time_en": "Today"
            })
        if student_absent > 0:
            dynamic_alerts.append({
                "id": "alert-2",
                "type": "info",
                "title_ar": f"{student_absent} طالب غائب من إجمالي {total_student_today}",
                "title_en": f"{student_absent} student(s) absent out of {total_student_today}",
                "time_ar": "اليوم",
                "time_en": "Today"
            })
        if classes_low_attendance > 0:
            dynamic_alerts.append({
                "id": "alert-3",
                "type": "error",
                "title_ar": f"{classes_low_attendance} فصل بنسبة حضور أقل من 80%",
                "title_en": f"{classes_low_attendance} class(es) with <80% attendance",
                "time_ar": "اليوم",
                "time_en": "Today"
            })
        if student_attendance_rate >= 90:
            dynamic_alerts.append({
                "id": "alert-4",
                "type": "success",
                "title_ar": f"نسبة حضور ممتازة: {student_attendance_rate}%",
                "title_en": f"Excellent attendance rate: {student_attendance_rate}%",
                "time_ar": "اليوم",
                "time_en": "Today"
            })

        final_alerts = alerts if alerts else dynamic_alerts

        return {
            "metrics": {
                "totalStudents": {
                    "value": total_students,
                    "change": f"+{total_students}" if total_students > 0 else "0",
                    "changeType": "up" if total_students > 0 else "same",
                    "status": "normal"
                },
                "totalTeachers": {
                    "value": total_teachers,
                    "change": f"+{total_teachers}" if total_teachers > 0 else "0",
                    "changeType": "up" if total_teachers > 0 else "same",
                    "status": "normal"
                },
                "totalClasses": {
                    "value": total_classes,
                    "change": str(total_classes),
                    "changeType": "same",
                    "status": "normal"
                },
                "todaySessions": {
                    "value": sessions_count,
                    "change": str(sessions_count),
                    "changeType": "same" if sessions_count > 0 else "down",
                    "status": "normal" if sessions_count > 0 else "warning"
                },
                "attendanceRate": {
                    "value": f"{student_attendance_rate}%",
                    "change": f"{student_attendance_rate}%",
                    "changeType": "up" if student_attendance_rate >= 80 else "down",
                    "status": "normal" if student_attendance_rate >= 80 else "warning"
                },
                "waitingSubstitute": {
                    "value": teacher_absent,
                    "change": str(teacher_absent),
                    "changeType": "up" if teacher_absent > 0 else "same",
                    "status": "warning" if teacher_absent > 0 else "normal"
                },
            },
            "attendance": {
                "students": {
                    "present": student_present,
                    "absent": student_absent,
                    "late": student_late,
                    "excused": student_excused,
                    "total": total_student_today if total_student_today > 0 else total_students
                },
                "teachers": {
                    "present": teacher_present,
                    "absent": teacher_absent,
                    "late": teacher_late,
                    "excused": teacher_excused,
                    "total": total_teacher_today if total_teacher_today > 0 else total_teachers
                },
            },
            "interventions": {
                "classesWithoutTeacher": teacher_absent,
                "teachersWithFrequentAbsence": teachers_frequent_absence,
                "classesLowAttendance": classes_low_attendance,
            },
            "alerts": final_alerts,
            "generated_at": datetime.now(timezone.utc).isoformat()
        }

    @staticmethod
    async def get_public_schools_count(session) -> dict:
        try:
            _now = _time.monotonic()
            if _public_schools_count_cache["data"] and _now < _public_schools_count_cache["expires"]:
                return _public_schools_count_cache["data"]

            try:
                active_count = await gd_count(session, "schools", {"status": "active"})
            except Exception:
                active_count = 0

            DISPLAY_FLOOR = 1
            displayed = max(int(active_count or 0), DISPLAY_FLOOR)
            result = {"count": displayed}
            _public_schools_count_cache["data"] = result
            _public_schools_count_cache["expires"] = _now + _PUBLIC_SCHOOLS_COUNT_TTL
            return result
        except Exception as e:
            logger.error(f"Error fetching public schools count: {e}")
            return {"count": 1}

    @staticmethod
    async def get_public_growth_indicators(session) -> dict:
        try:
            _now = _time.monotonic()
            if _public_growth_cache["data"] and _now < _public_growth_cache["expires"]:
                return _public_growth_cache["data"]

            try:
                schools_n = await gd_count(session, "schools", {"status": "active"})
            except Exception:
                schools_n = 0
            try:
                teachers_n = await gd_count(session, "teachers", {"is_active": True})
            except Exception:
                try:
                    teachers_n = await gd_count(session, "teachers", {})
                except Exception:
                    teachers_n = 0

            result = {
                "schools": bucket_display(schools_n),
                "teachers": bucket_display(teachers_n),
            }
            _public_growth_cache["data"] = result
            _public_growth_cache["expires"] = _now + _PUBLIC_GROWTH_TTL
            return result
        except Exception as e:
            logger.error(f"Error fetching public growth indicators: {e}")
            return {"schools": "10+", "teachers": "10+"}

    @staticmethod
    async def get_public_stats(session, current_user: dict) -> dict:
        from src.common.utils.tenant_scope import _PLATFORM_ROLES
        if current_user.get("role") not in _PLATFORM_ROLES:
            raise HTTPException(status_code=403, detail="غير مصرح بالوصول")

        try:
            _now = _time.monotonic()
            if _public_stats_cache["data"] and _now < _public_stats_cache["expires"]:
                from src.core.middleware.cache_metrics import record_hit
                record_hit()
                return _public_stats_cache["data"]
            from src.core.middleware.cache_metrics import record_miss
            record_miss()

            cached_stats = await gd_find_one(session, "platform_stats", {"id": "platform_stats"})
            if cached_stats:
                result = {
                    "schools": cached_stats.get("total_schools", 0),
                    "students": cached_stats.get("total_students", 0),
                    "teachers": cached_stats.get("total_teachers", 0),
                    "parents": cached_stats.get("total_parents", 0),
                    "active_schools": cached_stats.get("active_schools", 0),
                    "last_updated": cached_stats.get("last_updated", "")
                }
                _public_stats_cache["data"] = result
                _public_stats_cache["expires"] = _now + _PUBLIC_STATS_TTL
                return result

            total_schools = await gd_count(session, "schools", {})
            active_schools = await gd_count(session, "schools", {"status": "active"})

            students_from_users = await gd_count(session, "users", {"role": "student"})
            students_from_col = await gd_count(session, "students", {})
            total_students = max(students_from_users, students_from_col)

            teachers_from_users = await gd_count(session, "users", {"role": "teacher"})
            teachers_from_col = await gd_count(session, "teachers", {})
            total_teachers = max(teachers_from_users, teachers_from_col)

            parents_from_users = await gd_count(session, "users", {"role": "parent"})
            parents_from_col = await gd_count(session, "parents", {})
            total_parents = max(parents_from_users, parents_from_col)

            result = {
                "schools": total_schools,
                "students": total_students,
                "teachers": total_teachers,
                "parents": total_parents,
                "active_schools": active_schools,
                "last_updated": datetime.now(timezone.utc).isoformat()
            }
            _public_stats_cache["data"] = result
            _public_stats_cache["expires"] = _now + _PUBLIC_STATS_TTL
            return result
        except Exception as e:
            logger.error(f"Error fetching public stats: {e}")
            return {
                "schools": 0,
                "students": 0,
                "teachers": 0,
                "parents": 0,
                "active_schools": 0,
                "last_updated": datetime.now(timezone.utc).isoformat()
            }
