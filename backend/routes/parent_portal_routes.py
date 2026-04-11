"""
NASSAQ - Parent Portal Routes
مسارات بوابة ولي الأمر
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional, List
from datetime import datetime, timezone, timedelta
import uuid
from engines.sql_utils import gd_find, gd_find_one, gd_insert, gd_insert_many, gd_update_one, gd_update_many, gd_count, gd_delete_one, gd_delete_many, gd_distinct

import logging

logger = logging.getLogger("nassaq.parent_portal_routes")


def setup_parent_portal_routes(db, get_current_user, require_roles, UserRole):
    """Setup parent portal routes"""

    router = APIRouter(prefix="/parent-portal", tags=["Parent Portal"])

    def _parent_or_conditions(parent_id: str, parent_phone: Optional[str]) -> list:
        conditions = [
            {"parent_id": parent_id},
            {"parent_user_id": parent_id},
        ]
        if parent_phone:
            conditions.append({"parent_phone": parent_phone})
        return conditions

    async def _get_linked_student_ids(parent_id: str, school_id: Optional[str] = None) -> List[str]:
        query = {"parent_ref": parent_id, "is_active": True}
        if school_id:
            query["tenant_id"] = school_id
        links = await gd_find(db.session, "guardian_links", query, limit=20)
        return [l["student_id"] for l in links]

    async def _find_children(parent_id: str, parent_phone: Optional[str], school_id: Optional[str] = None):
        or_conditions = _parent_or_conditions(parent_id, parent_phone)
        student_query = {"$or": or_conditions}
        if school_id:
            student_query["school_id"] = school_id
        children = await gd_find(db.session, "students", student_query, limit=50)
        found_ids = {c.get("id") for c in children}
        linked_ids = await _get_linked_student_ids(parent_id, school_id)
        missing_ids = [sid for sid in linked_ids if sid not in found_ids]
        if missing_ids:
            extra_q = {"id": {"$in": missing_ids}}
            if school_id:
                extra_q["school_id"] = school_id
            extra = await gd_find(db.session, "students", extra_q, limit=50)
            children.extend(extra)
        return children

    # ============= DASHBOARD =============

    @router.get("/dashboard")
    async def get_parent_dashboard(
        current_user: dict = Depends(require_roles([UserRole.PARENT]))
    ):
        """لوحة تحكم ولي الأمر"""
        parent_id = current_user.get("id")
        parent_phone = current_user.get("phone")
        school_id = current_user.get("tenant_id")

        children = await _find_children(parent_id, parent_phone, school_id)

        school_name_cache = {}
        children_data = []
        for child in children:
            child_id = child.get("id")

            total_days = await gd_count(db.session, "attendance", {"student_id": child_id})
            present_days = await gd_count(db.session, "attendance", {"student_id": child_id, "status": "present"})
            attendance_rate = (present_days / total_days * 100) if total_days > 0 else 100

            recent_grades = await gd_find(db.session, "grades", {"student_id": child_id}, order_by="date", desc_order=True, limit=3)
            all_grades = await gd_find(db.session, "grades", {"student_id": child_id}, limit=500)
            avg_score = sum(g.get("percentage", 0) for g in all_grades) / len(all_grades) if all_grades else 0

            child_school_name = child.get("school_name")
            if not child_school_name:
                sid = child.get("school_id") or school_id
                if sid and sid not in school_name_cache:
                    s_doc = await gd_find_one(db.session, "schools", {"id": sid})
                    school_name_cache[sid] = s_doc.get("name") if s_doc else sid
                child_school_name = school_name_cache.get(sid, "")

            children_data.append({
                "id": child_id,
                "name": child.get("full_name"),
                "grade": child.get("grade_level") or child.get("grade"),
                "class_name": child.get("class_name"),
                "class_id": child.get("class_id"),
                "school_name": child_school_name,
                "profile_picture": child.get("profile_picture"),
                "attendance_rate": round(attendance_rate, 1),
                "average_score": round(avg_score, 1),
                "recent_grades": [
                    {
                        "subject": g.get("subject"),
                        "score": g.get("score"),
                        "max_score": g.get("max_score"),
                        "date": g.get("date")
                    }
                    for g in recent_grades
                ]
            })

        unread_notifications = await gd_count(db.session, "notifications", {
            "recipient_id": parent_id,
            "read_status": False
        })

        unread_messages = await gd_count(db.session, "messages", {
            "receiver_id": parent_id,
            "read_status": False
        })

        return {
            "parent": {
                "id": parent_id,
                "name": current_user.get("full_name"),
                "email": current_user.get("email"),
                "phone": parent_phone
            },
            "children": children_data,
            "children_count": len(children_data),
            "unread_notifications": unread_notifications,
            "unread_messages": unread_messages
        }

    # ============= CHILDREN LIST =============

    @router.get("/children")
    async def get_parent_children(
        current_user: dict = Depends(require_roles([UserRole.PARENT]))
    ):
        """قائمة أبناء ولي الأمر"""
        parent_id = current_user.get("id")
        parent_phone = current_user.get("phone")
        school_id = current_user.get("tenant_id")

        students = await _find_children(parent_id, parent_phone, school_id)

        school_name_cache = {}
        children = []
        for s in students:
            child_id = s.get("id")

            total_days = await gd_count(db.session, "attendance", {"student_id": child_id})
            present_days = await gd_count(db.session, "attendance", {"student_id": child_id, "status": "present"})
            att_rate = round((present_days / total_days * 100), 1) if total_days > 0 else 0

            all_grades = await gd_find(db.session, "grades", {"student_id": child_id}, limit=500)
            avg_score = 0
            if all_grades:
                avg_score = round(sum(g.get("percentage", 0) for g in all_grades) / len(all_grades), 1)

            child_school_name = s.get("school_name")
            if not child_school_name:
                sid = s.get("school_id") or school_id
                if sid and sid not in school_name_cache:
                    s_doc = await gd_find_one(db.session, "schools", {"id": sid})
                    school_name_cache[sid] = s_doc.get("name") if s_doc else sid
                child_school_name = school_name_cache.get(sid, "")

            children.append({
                "id": child_id,
                "name": s.get("full_name", s.get("name", "")),
                "name_ar": s.get("full_name", ""),
                "grade": s.get("grade_level", s.get("grade", "")),
                "class_name": s.get("class_name", ""),
                "grade_id": s.get("grade_id"),
                "class_id": s.get("class_id"),
                "school_name": child_school_name,
                "photo_url": s.get("photo_url", ""),
                "profile_picture": s.get("photo_url", s.get("profile_picture", "")),
                "attendance_rate": att_rate,
                "average_score": avg_score,
                "gender": s.get("gender", ""),
            })

        return {"children": children, "total": len(children)}

    # ============= CHILD DETAILS =============

    async def _verify_parent_access(parent_id: str, parent_phone: Optional[str], child_id: str, school_id: Optional[str] = None):
        student_query = {"id": child_id, "$or": _parent_or_conditions(parent_id, parent_phone)}
        if school_id:
            student_query["school_id"] = school_id
        child = await gd_find_one(db.session, "students", student_query)
        if child:
            return child
        link_query = {"parent_ref": parent_id, "student_id": child_id, "is_active": True}
        if school_id:
            link_query["tenant_id"] = school_id
        link = await gd_find_one(db.session, "guardian_links", link_query)
        if link:
            fallback_q = {"id": child_id}
            if school_id:
                fallback_q["school_id"] = school_id
            return await gd_find_one(db.session, "students", fallback_q)
        return None

    @router.get("/child/{child_id}")
    async def get_child_details(
        child_id: str,
        current_user: dict = Depends(require_roles([UserRole.PARENT]))
    ):
        """تفاصيل الابن"""
        parent_id = current_user.get("id")
        parent_phone = current_user.get("phone")

        child = await _verify_parent_access(parent_id, parent_phone, child_id, current_user.get("tenant_id"))

        if not child:
            raise HTTPException(status_code=403, detail="غير مصرح لك بالوصول لهذا الطالب")

        child_school_name = child.get("school_name")
        if not child_school_name:
            sid = child.get("school_id") or current_user.get("tenant_id")
            if sid:
                s_doc = await gd_find_one(db.session, "schools", {"id": sid})
                child_school_name = s_doc.get("name") if s_doc else None

        return {
            "id": child.get("id"),
            "name": child.get("full_name"),
            "national_id": child.get("national_id"),
            "birth_date": child.get("date_of_birth"),
            "gender": child.get("gender"),
            "grade": child.get("grade_level"),
            "class_name": child.get("class_name"),
            "class_id": child.get("class_id"),
            "school_name": child_school_name,
            "student_number": child.get("student_number"),
            "enrollment_date": child.get("enrollment_date"),
            "profile_picture": child.get("profile_picture"),
        }

    # ============= CHILD GRADES =============

    @router.get("/child/{child_id}/grades")
    async def get_child_grades(
        child_id: str,
        subject: Optional[str] = None,
        current_user: dict = Depends(require_roles([UserRole.PARENT]))
    ):
        """درجات الابن"""
        parent_id = current_user.get("id")
        parent_phone = current_user.get("phone")

        child = await _verify_parent_access(parent_id, parent_phone, child_id, current_user.get("tenant_id"))

        if not child:
            raise HTTPException(status_code=403, detail="غير مصرح لك بالوصول لهذا الطالب")

        query = {"student_id": child_id}
        if subject:
            query["subject"] = subject

        grades = await gd_find(db.session, "grades", query, order_by="date", desc_order=True, limit=500)

        subjects_data = {}
        for grade in grades:
            subj = grade.get("subject", "غير محدد")
            if subj not in subjects_data:
                subjects_data[subj] = {"subject": subj, "grades": [], "total_score": 0, "total_max": 0}

            subjects_data[subj]["grades"].append({
                "score": grade.get("score"),
                "max_score": grade.get("max_score"),
                "percentage": grade.get("percentage"),
                "assessment_type": grade.get("assessment_type"),
                "date": grade.get("date")
            })
            subjects_data[subj]["total_score"] += grade.get("score", 0)
            subjects_data[subj]["total_max"] += grade.get("max_score", 100)

        for subj in subjects_data:
            data = subjects_data[subj]
            data["average"] = round((data["total_score"] / data["total_max"]) * 100, 1) if data["total_max"] > 0 else 0

        total_grades = len(grades)
        overall_avg = sum(g.get("percentage", 0) for g in grades) / total_grades if total_grades > 0 else 0

        return {
            "child_name": child.get("full_name"),
            "subjects": list(subjects_data.values()),
            "total_grades": total_grades,
            "overall_average": round(overall_avg, 1)
        }

    # ============= CHILD ATTENDANCE =============

    @router.get("/child/{child_id}/attendance")
    async def get_child_attendance(
        child_id: str,
        month: Optional[int] = None,
        year: Optional[int] = None,
        current_user: dict = Depends(require_roles([UserRole.PARENT]))
    ):
        """سجل حضور الابن"""
        parent_id = current_user.get("id")
        parent_phone = current_user.get("phone")

        child = await _verify_parent_access(parent_id, parent_phone, child_id, current_user.get("tenant_id"))

        if not child:
            raise HTTPException(status_code=403, detail="غير مصرح لك بالوصول لهذا الطالب")

        query = {"student_id": child_id}

        if month and year:
            start_date = f"{year}-{month:02d}-01"
            if month == 12:
                end_date = f"{year + 1}-01-01"
            else:
                end_date = f"{year}-{month + 1:02d}-01"
            query["date"] = {"$gte": start_date, "$lt": end_date}

        records = await gd_find(db.session, "attendance", query, order_by="date", desc_order=True, limit=500)

        total = len(records)
        present = sum(1 for r in records if r.get("status") == "present")
        absent = sum(1 for r in records if r.get("status") == "absent")
        late = sum(1 for r in records if r.get("status") == "late")
        excused = sum(1 for r in records if r.get("status") == "excused")

        return {
            "child_name": child.get("full_name"),
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
                "attendance_rate": round((present / total * 100) if total > 0 else 100, 1)
            }
        }

    # ============= CHILD SCHEDULE =============

    @router.get("/child/{child_id}/schedule")
    async def get_child_schedule(
        child_id: str,
        current_user: dict = Depends(require_roles([UserRole.PARENT]))
    ):
        """الجدول الدراسي للابن"""
        parent_id = current_user.get("id")
        parent_phone = current_user.get("phone")

        child = await _verify_parent_access(parent_id, parent_phone, child_id, current_user.get("tenant_id"))

        if not child:
            raise HTTPException(status_code=403, detail="غير مصرح لك بالوصول لهذا الطالب")

        school_id = child.get("school_id")

        day_en_to_ar = {
            "sunday": "الأحد", "monday": "الاثنين", "tuesday": "الثلاثاء",
            "wednesday": "الأربعاء", "thursday": "الخميس"
        }
        days_order = ["الأحد", "الاثنين", "الثلاثاء", "الأربعاء", "الخميس"]
        schedule_by_day = {day: [] for day in days_order}

        if child.get("class_id"):
            timetable = await gd_find_one(db.session, "timetables", {"school_id": school_id, "status": "published"}) or await gd_find_one(db.session, "timetables", {"school_id": school_id},
                sort=[("created_at", -1)])
            if timetable:
                all_sessions = await gd_find(db.session, "timetable_sessions", {
                        "timetable_id": timetable.get("id"),
                        "class_id": child.get("class_id")
                    }, limit=500)

                sub_ids = list(set(s.get("subject_id") for s in all_sessions if s.get("subject_id")))
                tch_ids = list(set(s.get("teacher_id") for s in all_sessions if s.get("teacher_id")))
                subs = await gd_find(db.session, "subjects", {"id": {"$in": sub_ids}}, limit=100)
                tchs = await gd_find(db.session, "teachers", {"id": {"$in": tch_ids}}, limit=100)
                sub_map = {s["id"]: s.get("name_ar", "") for s in subs}
                tch_map = {t["id"]: t.get("full_name", "") for t in tchs}

                for session in all_sessions:
                    day_ar = day_en_to_ar.get(session.get("day_of_week", ""), "")
                    if day_ar in schedule_by_day:
                        schedule_by_day[day_ar].append({
                            "period": session.get("period_number"),
                            "subject": sub_map.get(session.get("subject_id"), "غير محدد"),
                            "teacher": tch_map.get(session.get("teacher_id"), "غير محدد"),
                            "start_time": session.get("start_time"),
                            "end_time": session.get("end_time")
                        })

        for day in schedule_by_day:
            schedule_by_day[day] = sorted(schedule_by_day[day], key=lambda x: x.get("period", 0))

        return {
            "child_name": child.get("full_name"),
            "class_name": child.get("class_name"),
            "schedule": schedule_by_day,
            "days": days_order
        }

    # ============= TODAY LIVE =============

    @router.get("/child/{child_id}/today-live")
    async def get_child_today_live(
        child_id: str,
        current_user: dict = Depends(require_roles([UserRole.PARENT]))
    ):
        parent_id = current_user.get("id")
        parent_phone = current_user.get("phone")
        school_id = current_user.get("tenant_id")

        child = await _verify_parent_access(parent_id, parent_phone, child_id, school_id)
        if not child:
            raise HTTPException(status_code=403, detail="غير مصرح لك بالوصول لهذا الطالب")

        now = datetime.now(timezone(timedelta(hours=3)))
        current_time = now.strftime("%H:%M")
        day_map = {6: "sunday", 0: "monday", 1: "tuesday", 2: "wednesday", 3: "thursday"}
        today_en = day_map.get(now.weekday(), "")

        today_sessions = []
        if child.get("class_id") and today_en:
            timetable = await gd_find_one(db.session, "timetables", {
                "school_id": child.get("school_id", school_id),
                "status": "published"
            }) or await gd_find_one(db.session, "timetables", {
                "school_id": child.get("school_id", school_id)
            }, sort=[("created_at", -1)])

            if timetable:
                sessions = await gd_find(db.session, "timetable_sessions", {
                    "timetable_id": timetable.get("id"),
                    "class_id": child.get("class_id"),
                    "day_of_week": today_en
                }, limit=20)

                sub_ids = list(set(s.get("subject_id") for s in sessions if s.get("subject_id")))
                tch_ids = list(set(s.get("teacher_id") for s in sessions if s.get("teacher_id")))
                subs = await gd_find(db.session, "subjects", {"id": {"$in": sub_ids}}, limit=50) if sub_ids else []
                tchs = await gd_find(db.session, "teachers", {"id": {"$in": tch_ids}}, limit=50) if tch_ids else []
                sub_map = {s["id"]: s.get("name_ar", s.get("name", "")) for s in subs}
                tch_map = {t["id"]: t.get("full_name", "") for t in tchs}

                for s in sorted(sessions, key=lambda x: x.get("period_number", 0)):
                    today_sessions.append({
                        "period": s.get("period_number"),
                        "subject": sub_map.get(s.get("subject_id"), "غير محدد"),
                        "subject_id": s.get("subject_id"),
                        "teacher": tch_map.get(s.get("teacher_id"), "غير محدد"),
                        "teacher_id": s.get("teacher_id"),
                        "start_time": s.get("start_time"),
                        "end_time": s.get("end_time"),
                    })

        current_class = None
        upcoming_classes = []
        completed_count = 0
        for session in today_sessions:
            start = session.get("start_time", "")
            end = session.get("end_time", "")
            if start and end:
                if current_time >= end:
                    completed_count += 1
                elif start <= current_time < end:
                    current_class = {**session, "is_current": True}
                else:
                    upcoming_classes.append(session)

        today_date = now.date()
        days_offset = today_date.weekday() + 1 if today_date.weekday() != 6 else 0
        week_start = today_date - timedelta(days=days_offset)
        last_week_start = week_start - timedelta(days=7)
        last_week_end = week_start - timedelta(days=1)

        this_week_grades = await gd_find(db.session, "grades", {
            "student_id": child_id,
            "date": {"$gte": week_start.isoformat(), "$lte": today_date.isoformat()}
        }, limit=200)
        last_week_grades = await gd_find(db.session, "grades", {
            "student_id": child_id,
            "date": {"$gte": last_week_start.isoformat(), "$lte": last_week_end.isoformat()}
        }, limit=200)

        all_grades = await gd_find(db.session, "grades", {"student_id": child_id}, limit=500)
        overall_avg = round(sum(g.get("percentage", 0) for g in all_grades) / len(all_grades), 1) if all_grades else 0

        this_avg = round(sum(g.get("percentage", 0) for g in this_week_grades) / len(this_week_grades), 1) if this_week_grades else overall_avg
        last_avg = round(sum(g.get("percentage", 0) for g in last_week_grades) / len(last_week_grades), 1) if last_week_grades else this_avg
        trend = round(this_avg - last_avg, 1)

        if overall_avg >= 90:
            level = "ممتاز"
        elif overall_avg >= 80:
            level = "جيد جداً"
        elif overall_avg >= 70:
            level = "جيد ومستقر"
        elif overall_avg >= 60:
            level = "مقبول"
        else:
            level = "يحتاج تحسين"

        if trend > 2:
            phrase = "استمروا على هذا التقدم الرائع!"
        elif trend < -2:
            phrase = "لا تقلقوا، بالمتابعة سيتحسن الأداء"
        else:
            phrase = "أداء مستقر، واصلوا الدعم"

        child_school_name = child.get("school_name", "")
        if not child_school_name:
            sid = child.get("school_id") or school_id
            if sid:
                s_doc = await gd_find_one(db.session, "schools", {"id": sid})
                child_school_name = s_doc.get("name") if s_doc else ""

        return {
            "student": {
                "name": child.get("full_name"),
                "school_name": child_school_name,
                "grade_level": child.get("grade_level", child.get("grade", "")),
                "class_name": child.get("class_name", ""),
            },
            "school_day": {
                "today": today_en,
                "total_periods": len(today_sessions),
                "completed_periods": completed_count,
                "remaining_periods": len(upcoming_classes) + (1 if current_class else 0),
                "all_sessions": today_sessions,
                "is_school_day": today_en in day_map.values(),
                "server_time": current_time,
            },
            "current_class": current_class,
            "upcoming_classes": upcoming_classes,
            "performance": {
                "level": level,
                "overall_average": overall_avg,
                "trend": trend,
                "trend_direction": "up" if trend > 2 else ("down" if trend < -2 else "stable"),
                "phrase": phrase,
            }
        }

    # ============= WEEKLY STORY =============

    @router.get("/child/{child_id}/weekly-story")
    async def get_child_weekly_story(
        child_id: str,
        current_user: dict = Depends(require_roles([UserRole.PARENT]))
    ):
        parent_id = current_user.get("id")
        parent_phone = current_user.get("phone")
        school_id = current_user.get("tenant_id")

        child = await _verify_parent_access(parent_id, parent_phone, child_id, school_id)
        if not child:
            raise HTTPException(status_code=403, detail="غير مصرح لك بالوصول لهذا الطالب")

        now = datetime.now(timezone(timedelta(hours=3)))
        today = now.date()
        days_since_saturday = (today.weekday() + 2) % 7
        week_start = today - timedelta(days=days_since_saturday)
        week_end = week_start + timedelta(days=5)

        participation = await gd_find(db.session, "participation_records", {
            "student_id": child_id,
            "created_at": {"$gte": week_start.isoformat(), "$lte": (week_end + timedelta(days=1)).isoformat()}
        }, limit=200)
        participation_count = len(participation)

        positive_behaviors = await gd_count(db.session, "behaviour_records", {
            "student_id": child_id,
            "type": "positive",
            "created_at": {"$gte": week_start.isoformat(), "$lte": (week_end + timedelta(days=1)).isoformat()}
        })

        skills = await gd_find(db.session, "session_interactions", {
            "student_id": child_id,
            "created_at": {"$gte": week_start.isoformat(), "$lte": (week_end + timedelta(days=1)).isoformat()}
        }, limit=200)
        acquired_skills = list(set(
            s.get("skill_tag") for s in skills if s.get("skill_tag")
        ))

        week_grades = await gd_find(db.session, "grades", {
            "student_id": child_id,
            "date": {"$gte": week_start.isoformat(), "$lte": week_end.isoformat()}
        }, limit=200)
        subject_scores = {}
        for g in week_grades:
            subj = g.get("subject_name") or g.get("subject_id", "عام")
            if subj not in subject_scores:
                subject_scores[subj] = []
            subject_scores[subj].append(g.get("percentage", 0))

        strong_subjects = []
        weak_subjects = []
        for subj, scores in subject_scores.items():
            avg = sum(scores) / len(scores) if scores else 0
            if avg >= 80:
                strong_subjects.append({"subject": subj, "average": round(avg, 1)})
            elif avg < 60:
                weak_subjects.append({"subject": subj, "average": round(avg, 1)})

        remedial_plans = await gd_find(db.session, "student_plans", {
            "student_id": child_id,
            "plan_type": "remedial",
            "created_at": {"$gte": week_start.isoformat(), "$lte": (week_end + timedelta(days=1)).isoformat()}
        }, limit=20)

        daily_data = []
        day_names_ar = ["السبت", "الأحد", "الاثنين", "الثلاثاء", "الأربعاء", "الخميس"]
        for i in range(6):
            day_date = week_start + timedelta(days=i)
            day_str = day_date.isoformat()
            day_participation = sum(1 for p in participation if str(p.get("created_at", "")).startswith(day_str))
            day_behavior = await gd_count(db.session, "behaviour_records", {
                "student_id": child_id,
                "type": "positive",
                "created_at": {"$gte": day_str, "$lt": (day_date + timedelta(days=1)).isoformat()}
            })
            daily_data.append({
                "day": day_names_ar[i],
                "date": day_str,
                "participation": day_participation,
                "positive_behavior": day_behavior,
            })

        import hashlib
        tips = [
            "شجعوا أبناءكم على القراءة اليومية لمدة 15 دقيقة على الأقل",
            "احرصوا على مراجعة الواجبات مع أبنائكم يومياً",
            "النوم الكافي يعزز التركيز والتحصيل الدراسي",
            "شاركوا أبناءكم في حل المسائل الرياضية بطريقة ممتعة",
            "كلمة تشجيع واحدة تصنع فرقاً كبيراً في أداء الطالب",
        ]
        tip_index = int(hashlib.md5(f"{child_id}-{week_start}".encode()).hexdigest(), 16) % len(tips)

        return {
            "week_start": week_start.isoformat(),
            "week_end": week_end.isoformat(),
            "participation_count": participation_count,
            "positive_behaviors": positive_behaviors,
            "acquired_skills": acquired_skills,
            "strong_subjects": strong_subjects,
            "weak_subjects": weak_subjects,
            "remedial_plans": [
                {
                    "id": p.get("id"),
                    "title": p.get("title", "خطة علاجية"),
                    "description": p.get("description", ""),
                    "subject": p.get("subject", ""),
                    "teacher_name": p.get("teacher_name", ""),
                    "created_at": p.get("created_at"),
                }
                for p in remedial_plans
            ],
            "daily_chart_data": daily_data,
            "weekly_tip": tips[tip_index],
        }

    # ============= STUDENT PROFILE =============

    @router.get("/child/{child_id}/profile")
    async def get_child_profile(
        child_id: str,
        current_user: dict = Depends(require_roles([UserRole.PARENT]))
    ):
        parent_id = current_user.get("id")
        parent_phone = current_user.get("phone")
        child = await _verify_parent_access(parent_id, parent_phone, child_id, current_user.get("tenant_id"))
        if not child:
            raise HTTPException(status_code=403, detail="غير مصرح")

        school_name = child.get("school_name", "")
        if not school_name:
            sid = child.get("school_id") or current_user.get("tenant_id")
            if sid:
                s_doc = await gd_find_one(db.session, "schools", {"id": sid})
                school_name = s_doc.get("name") if s_doc else ""

        return {
            "id": child.get("id"),
            "name": child.get("full_name"),
            "grade_level": child.get("grade_level", child.get("grade", "")),
            "class_name": child.get("class_name", ""),
            "school_name": school_name,
            "emoji": child.get("emoji", "👦"),
            "profile_picture": child.get("profile_picture", ""),
            "gender": child.get("gender", ""),
            "health_conditions": child.get("health_conditions", []),
            "behavioral_aspects": child.get("behavioral_aspects", []),
            "family_situation": child.get("family_situation", ""),
        }

    @router.put("/child/{child_id}/profile")
    async def update_child_profile(
        child_id: str,
        data: dict,
        current_user: dict = Depends(require_roles([UserRole.PARENT]))
    ):
        parent_id = current_user.get("id")
        parent_phone = current_user.get("phone")
        child = await _verify_parent_access(parent_id, parent_phone, child_id, current_user.get("tenant_id"))
        if not child:
            raise HTTPException(status_code=403, detail="غير مصرح")

        allowed_fields = {"emoji", "health_conditions", "behavioral_aspects", "family_situation"}
        update_data = {k: v for k, v in data.items() if k in allowed_fields}

        if not update_data:
            raise HTTPException(status_code=400, detail="لا توجد بيانات صالحة للتحديث")

        await gd_update_one(db.session, "students", {"id": child_id}, {"$set": update_data})
        return {"success": True, "message": "تم تحديث الملف بنجاح"}

    # ============= ACHIEVEMENTS =============

    @router.get("/child/{child_id}/achievements")
    async def get_child_achievements(
        child_id: str,
        current_user: dict = Depends(require_roles([UserRole.PARENT]))
    ):
        parent_id = current_user.get("id")
        parent_phone = current_user.get("phone")
        child = await _verify_parent_access(parent_id, parent_phone, child_id, current_user.get("tenant_id"))
        if not child:
            raise HTTPException(status_code=403, detail="غير مصرح")

        achievements = await gd_find(
            db.session, "student_achievements",
            {"student_id": child_id},
            order_by="created_at", desc_order=True, limit=100
        )
        return {"achievements": achievements, "total": len(achievements)}

    @router.post("/child/{child_id}/achievements")
    async def add_child_achievement(
        child_id: str,
        data: dict,
        current_user: dict = Depends(require_roles([UserRole.PARENT]))
    ):
        parent_id = current_user.get("id")
        parent_phone = current_user.get("phone")
        school_id = current_user.get("tenant_id")
        child = await _verify_parent_access(parent_id, parent_phone, child_id, school_id)
        if not child:
            raise HTTPException(status_code=403, detail="غير مصرح")

        achievement = {
            "id": str(uuid.uuid4()),
            "student_id": child_id,
            "school_id": child.get("school_id", school_id),
            "name": data.get("name", ""),
            "type": data.get("type", "other"),
            "source": "parent",
            "source_user_id": parent_id,
            "file_url": data.get("file_url", ""),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await gd_insert(db.session, "student_achievements", achievement)
        return {"success": True, "achievement": achievement}

    # ============= ANALYTICS =============

    @router.get("/child/{child_id}/analytics")
    async def get_child_analytics(
        child_id: str,
        current_user: dict = Depends(require_roles([UserRole.PARENT]))
    ):
        parent_id = current_user.get("id")
        parent_phone = current_user.get("phone")
        school_id = current_user.get("tenant_id")
        child = await _verify_parent_access(parent_id, parent_phone, child_id, school_id)
        if not child:
            raise HTTPException(status_code=403, detail="غير مصرح")

        all_grades = await gd_find(db.session, "grades", {"student_id": child_id}, limit=1000)
        overall_avg = round(sum(g.get("percentage", 0) for g in all_grades) / len(all_grades), 1) if all_grades else 0

        target_subjects = {"رياضيات": 0, "علوم": 0, "عربي": 0, "إنجليزي": 0, "مهارات رقمية": 0}
        subject_counts = {k: 0 for k in target_subjects}
        subject_all = {}
        for g in all_grades:
            subj = g.get("subject_name") or g.get("subject_id", "عام")
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

        class_id = child.get("class_id")
        class_avg = 0
        child_school_id = child.get("school_id") or school_id
        if class_id:
            classmates = await gd_find(db.session, "students", {"class_id": class_id, "school_id": child_school_id}, limit=100)
            classmate_ids = [c.get("id") for c in classmates if c.get("id") != child_id]
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

        total_participation = await gd_count(db.session, "participation_records", {"student_id": child_id})
        if total_participation > 20:
            strengths.append({"area": "مشاركة صفية", "detail": f"{total_participation} مشاركة مسجلة"})

        total_att = await gd_count(db.session, "attendance", {"student_id": child_id})
        present_att = await gd_count(db.session, "attendance", {"student_id": child_id, "status": "present"})
        att_rate = round((present_att / total_att * 100), 1) if total_att > 0 else 100

        assignments = await gd_find(db.session, "student_assignments", {
            "$or": [{"class_id": class_id}, {"grade_id": child.get("grade_id")}]
        }, limit=200) if class_id else []
        submissions = await gd_find(db.session, "assignment_submissions", {
            "student_id": child_id
        }, limit=200)
        homework_rate = round(len(submissions) / max(1, len(assignments)) * 100, 1)

        if homework_rate < 60:
            weaknesses.append({"area": "واجبات غير مكتملة", "detail": f"نسبة إنجاز {homework_rate}%"})

        follow_up_score = (att_rate * 0.3) + (homework_rate * 0.3) + (min(total_participation, 50) / 50 * 100 * 0.2) + (overall_avg * 0.2)
        if follow_up_score >= 75:
            follow_up_status = "مستقر"
        elif follow_up_score >= 50:
            follow_up_status = "يحتاج متابعة"
        else:
            follow_up_status = "بحاجة دعم"

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
            "student_name": child.get("full_name"),
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
            "follow_up": {
                "score": round(follow_up_score, 1),
                "status": follow_up_status,
                "breakdown": {
                    "attendance_rate": att_rate,
                    "homework_rate": homework_rate,
                    "participation_score": round(min(total_participation, 50) / 50 * 100, 1),
                    "academic_average": overall_avg,
                }
            }
        }

    # ============= OPEN REQUESTS COUNT =============

    @router.get("/open-requests-count")
    async def get_open_requests_count(
        current_user: dict = Depends(require_roles([UserRole.PARENT]))
    ):
        parent_id = current_user.get("id")
        open_messages = await gd_count(db.session, "messages", {
            "sender_id": parent_id,
            "status": {"$in": ["open", "pending", "sent"]}
        })
        open_excuses = await gd_count(db.session, "absence_excuses", {
            "parent_id": parent_id,
            "status": {"$in": ["pending", "submitted"]}
        })
        open_meetings = await gd_count(db.session, "meeting_requests", {
            "parent_id": parent_id,
            "status": {"$in": ["pending", "submitted"]}
        })
        total_open = open_messages + open_excuses + open_meetings
        return {
            "total_open": total_open,
            "limit": 3,
            "can_submit": total_open < 3,
            "breakdown": {
                "messages": open_messages,
                "excuses": open_excuses,
                "meetings": open_meetings,
            }
        }

    # ============= QUICK MESSAGE (Communication Center) =============

    @router.post("/quick-message")
    async def send_quick_message(
        data: dict,
        current_user: dict = Depends(require_roles([UserRole.PARENT]))
    ):
        parent_id = current_user.get("id")
        school_id = current_user.get("tenant_id")
        content = data.get("content", "").strip()
        message_type = data.get("message_type", "note")
        recipient_type = data.get("recipient_type", "admin")

        if not content:
            raise HTTPException(status_code=400, detail="محتوى الرسالة مطلوب")

        open_messages = await gd_count(db.session, "messages", {
            "sender_id": parent_id,
            "status": {"$in": ["open", "pending", "sent"]}
        })
        open_excuses = await gd_count(db.session, "absence_excuses", {
            "parent_id": parent_id,
            "status": {"$in": ["pending", "submitted"]}
        })
        open_meetings = await gd_count(db.session, "meeting_requests", {
            "parent_id": parent_id,
            "status": {"$in": ["pending", "submitted"]}
        })
        if (open_messages + open_excuses + open_meetings) >= 3:
            raise HTTPException(status_code=429, detail="لقد وصلت للحد الأقصى من الطلبات المفتوحة (3)")

        receiver = None
        if recipient_type == "admin":
            receiver = await gd_find_one(db.session, "users", {
                "tenant_id": school_id,
                "role": {"$in": ["school_admin", "school_principal"]}
            })
        elif recipient_type == "teacher":
            children = await _find_children(parent_id, current_user.get("phone"), school_id)
            if children:
                child = children[0]
                if child.get("class_id"):
                    session = await gd_find_one(db.session, "timetable_sessions", {
                        "class_id": child.get("class_id")
                    })
                    if session and session.get("teacher_id"):
                        receiver = await gd_find_one(db.session, "teachers", {"id": session.get("teacher_id")})
                        if not receiver:
                            receiver = await gd_find_one(db.session, "users", {"id": session.get("teacher_id")})

        receiver_id = receiver.get("id", "") if receiver else ""
        receiver_name = (receiver.get("full_name") or receiver.get("name", "")) if receiver else "الإدارة"

        type_labels = {"note": "ملاحظة", "suggestion": "اقتراح", "inquiry": "استفسار"}
        subject = type_labels.get(message_type, "رسالة") + f" من ولي الأمر {current_user.get('full_name', '')}"

        message = {
            "id": str(uuid.uuid4()),
            "subject": subject,
            "content": content,
            "sender_id": parent_id,
            "sender_name": current_user.get("full_name"),
            "sender_role": "parent",
            "receiver_id": receiver_id,
            "receiver_name": receiver_name,
            "message_type": message_type,
            "read_status": False,
            "status": "sent",
            "school_id": school_id,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        await gd_insert(db.session, "messages", message)

        if receiver_id:
            await gd_insert(db.session, "notifications", {
                "id": str(uuid.uuid4()),
                "recipient_id": receiver_id,
                "notification_type": "message",
                "title": f"رسالة جديدة من ولي أمر: {current_user.get('full_name')}",
                "message": subject,
                "read_status": False,
                "created_at": datetime.now(timezone.utc).isoformat()
            })

        return {"success": True, "message": "تم استلام رسالتكم، رضاكم محل اهتمامنا"}

    # ============= MESSAGES =============

    @router.get("/messages")
    async def get_parent_messages(
        current_user: dict = Depends(require_roles([UserRole.PARENT]))
    ):
        """رسائل ولي الأمر"""
        parent_id = current_user.get("id")

        messages = await gd_find(db.session, "messages", {
            "$or": [
                {"sender_id": parent_id},
                {"receiver_id": parent_id},
                {"recipient_ids": parent_id}
            ]
        }, order_by="created_at", desc_order=True, limit=50)

        return {
            "messages": [
                {
                    "id": m.get("id"),
                    "subject": m.get("subject"),
                    "content": m.get("content") or m.get("body", ""),
                    "sender_id": m.get("sender_id"),
                    "sender_name": m.get("sender_name"),
                    "sender_type": m.get("sender_type"),
                    "receiver_id": m.get("receiver_id"),
                    "receiver_name": m.get("receiver_name"),
                    "student_name": m.get("student_name"),
                    "type": m.get("type"),
                    "is_sent": m.get("sender_id") == parent_id,
                    "read_status": m.get("read_status", False),
                    "created_at": m.get("created_at")
                }
                for m in messages
            ]
        }

    @router.post("/messages")
    async def send_parent_message(
        receiver_id: str,
        subject: str,
        content: str,
        child_id: Optional[str] = None,
        current_user: dict = Depends(require_roles([UserRole.PARENT]))
    ):
        """إرسال رسالة من ولي الأمر"""
        receiver = await gd_find_one(db.session, "users", {"id": receiver_id})
        if not receiver:
            receiver = await gd_find_one(db.session, "teachers", {"id": receiver_id})

        if not receiver:
            raise HTTPException(status_code=404, detail="المستلم غير موجود")

        message = {
            "id": str(uuid.uuid4()),
            "subject": subject,
            "content": content,
            "sender_id": current_user.get("id"),
            "sender_name": current_user.get("full_name"),
            "sender_role": "parent",
            "receiver_id": receiver_id,
            "receiver_name": receiver.get("full_name") or receiver.get("name"),
            "child_id": child_id,
            "read_status": False,
            "status": "sent",
            "created_at": datetime.now(timezone.utc).isoformat()
        }

        await gd_insert(db.session, "messages", message)

        await gd_insert(db.session, "notifications", {
            "id": str(uuid.uuid4()),
            "recipient_id": receiver_id,
            "notification_type": "message",
            "title": f"رسالة جديدة من ولي أمر: {current_user.get('full_name')}",
            "message": subject,
            "read_status": False,
            "created_at": datetime.now(timezone.utc).isoformat()
        })

        return {"success": True, "message_id": message["id"]}

    # ============= CHILD TEACHERS =============

    @router.get("/child/{child_id}/teachers")
    async def get_child_teachers(
        child_id: str,
        current_user: dict = Depends(require_roles([UserRole.PARENT]))
    ):
        """معلمي الابن"""
        parent_id = current_user.get("id")
        parent_phone = current_user.get("phone")

        child = await _verify_parent_access(parent_id, parent_phone, child_id, current_user.get("tenant_id"))

        if not child:
            raise HTTPException(status_code=403, detail="غير مصرح لك بالوصول لهذا الطالب")

        school_id = child.get("school_id")
        teachers = []

        if child.get("class_id"):
            timetable = await gd_find_one(db.session, "timetables", {"school_id": school_id, "status": "published"}) or await gd_find_one(db.session, "timetables", {"school_id": school_id},
                sort=[("created_at", -1)])
            if timetable:
                sessions = await gd_find(db.session, "timetable_sessions", {
                        "timetable_id": timetable.get("id"),
                        "class_id": child.get("class_id")
                    }, limit=500)

                teacher_subject_map = {}
                for s in sessions:
                    tid = s.get("teacher_id")
                    sid = s.get("subject_id")
                    if tid:
                        if tid not in teacher_subject_map:
                            teacher_subject_map[tid] = set()
                        if sid:
                            teacher_subject_map[tid].add(sid)

                if teacher_subject_map:
                    sub_ids = list(set(sid for sids in teacher_subject_map.values() for sid in sids))
                    subs = await gd_find(db.session, "subjects", {"id": {"$in": sub_ids}}, limit=100)
                    sub_name_map = {s["id"]: s.get("name_ar", "") for s in subs}

                    teacher_docs = await gd_find(db.session, "teachers", {"id": {"$in": list(teacher_subject_map.keys())}, "school_id": school_id}, limit=100)

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

        return {
            "child_name": child.get("full_name"),
            "teachers": teachers
        }

    @router.get("/child/{child_id}/progress-report")
    async def get_child_progress_report(
        child_id: str,
        current_user: dict = Depends(require_roles([UserRole.PARENT]))
    ):
        """تقرير تقدم الطفل الشامل"""
        parent_id = current_user.get("id")
        parent_phone = current_user.get("phone")

        child = await _verify_parent_access(parent_id, parent_phone, child_id, current_user.get("tenant_id"))
        if not child:
            raise HTTPException(status_code=403, detail="غير مصرح لك بالوصول لهذا الطالب")

        total_attendance = await gd_count(db.session, "attendance", {"student_id": child_id})
        present = await gd_count(db.session, "attendance", {"student_id": child_id, "status": "present"})
        absent = await gd_count(db.session, "attendance", {"student_id": child_id, "status": "absent"})
        late = await gd_count(db.session, "attendance", {"student_id": child_id, "status": "late"})
        attendance_rate = round((present / total_attendance * 100), 1) if total_attendance > 0 else 100

        grades = await gd_find(db.session, "grades", {"student_id": child_id}, limit=500)
        subjects_grades = {}
        for g in grades:
            subj = g.get("subject_name") or g.get("subject_id", "عام")
            if subj not in subjects_grades:
                subjects_grades[subj] = []
            subjects_grades[subj].append(g.get("percentage", 0))

        subject_averages = {}
        for subj, scores in subjects_grades.items():
            subject_averages[subj] = round(sum(scores) / len(scores), 1) if scores else 0

        overall_avg = round(sum(subject_averages.values()) / len(subject_averages), 1) if subject_averages else 0

        behaviour_pos = await gd_count(db.session, "behaviour_records", {"student_id": child_id, "type": "positive"})
        behaviour_neg = await gd_count(db.session, "behaviour_records", {"student_id": child_id, "type": "negative"})
        behaviour_total = behaviour_pos + behaviour_neg

        participation = await gd_find(db.session, "participation_records", {"student_id": child_id}, limit=500)
        total_participation_points = sum(p.get("points", 0) for p in participation)

        return {
            "student": {
                "id": child_id,
                "name": child.get("full_name"),
                "class": child.get("class_name"),
                "grade_level": child.get("grade_level")
            },
            "attendance": {
                "total_days": total_attendance,
                "present": present,
                "absent": absent,
                "late": late,
                "rate": attendance_rate
            },
            "academics": {
                "overall_average": overall_avg,
                "subject_averages": subject_averages,
                "total_assessments": len(grades)
            },
            "behaviour": {
                "positive": behaviour_pos,
                "negative": behaviour_neg,
                "total": behaviour_total,
                "ratio": round(behaviour_pos / max(1, behaviour_total) * 100, 1)
            },
            "participation": {
                "total_records": len(participation),
                "total_points": total_participation_points
            }
        }

    @router.get("/child/{child_id}/behaviour")
    async def get_child_behaviour(
        child_id: str,
        limit: int = 20,
        current_user: dict = Depends(require_roles([UserRole.PARENT]))
    ):
        """سجل سلوك الطفل"""
        parent_id = current_user.get("id")
        parent_phone = current_user.get("phone")

        child = await _verify_parent_access(parent_id, parent_phone, child_id, current_user.get("tenant_id"))
        if not child:
            raise HTTPException(status_code=403, detail="غير مصرح")

        records = await gd_find(db.session, "behaviour_records", {"student_id": child_id}, order_by="created_at", desc_order=True, limit=limit)

        return {"records": records, "total": len(records)}

    # ============= CHILD HOMEWORK =============

    @router.get("/child/{child_id}/homework")
    async def get_child_homework(
        child_id: str,
        current_user: dict = Depends(require_roles([UserRole.PARENT]))
    ):
        parent_id = current_user.get("id")
        parent_phone = current_user.get("phone")

        child = await _verify_parent_access(parent_id, parent_phone, child_id, current_user.get("tenant_id"))
        if not child:
            raise HTTPException(status_code=403, detail="غير مصرح")

        school_id = child.get("school_id")
        class_id = child.get("class_id")
        grade_id = child.get("grade_id") or child.get("grade")

        query = {"school_id": school_id, "is_active": True}
        if class_id:
            query["$or"] = [
                {"class_ids": class_id},
                {"class_id": class_id},
                {"grade_id": grade_id}
            ]

        assignments = await gd_find(db.session, "student_assignments", query, order_by="due_date", desc_order=True, limit=100)

        submissions = await gd_find(db.session, "assignment_submissions", {"student_id": child_id}, limit=500)
        submission_map = {s.get("assignment_id"): s for s in submissions}

        now = datetime.now(timezone.utc)
        result = []
        for a in assignments:
            aid = a.get("id")
            sub = submission_map.get(aid)
            due_str = a.get("due_date")
            try:
                if isinstance(due_str, str):
                    due = datetime.fromisoformat(due_str.replace('Z', '+00:00'))
                else:
                    due = due_str or (now + timedelta(days=7))
            except Exception as e:
                logger.debug(f"Failed to parse due_date '{due_str}': {e}")
                due = now + timedelta(days=7)

            if sub:
                st = "graded" if sub.get("grade") is not None else "submitted"
            elif due < now:
                st = "late"
            else:
                st = "pending"

            result.append({
                "id": aid,
                "title": a.get("title", ""),
                "subject_id": a.get("subject_id"),
                "due_date": due_str,
                "status": st,
                "grade": sub.get("grade") if sub else None,
                "submission_date": sub.get("submitted_at") if sub else None,
            })

        return {
            "child_name": child.get("full_name"),
            "assignments": result,
            "statistics": {
                "pending": len([a for a in result if a["status"] == "pending"]),
                "submitted": len([a for a in result if a["status"] == "submitted"]),
                "graded": len([a for a in result if a["status"] == "graded"]),
                "late": len([a for a in result if a["status"] == "late"])
            }
        }

    @router.get("/settings")
    async def get_parent_settings(
        current_user: dict = Depends(require_roles([UserRole.PARENT]))
    ):
        """إعدادات ولي الأمر"""
        settings = await gd_find_one(db.session, "user_preferences", {"user_id": current_user["id"]}) or {}

        return {
            "notification_preferences": settings.get("notification_preferences", {
                "email": True,
                "sms": True,
                "push": True,
                "attendance_alerts": True,
                "grade_alerts": True,
                "behaviour_alerts": True
            }),
            "language": settings.get("language", "ar"),
            "timezone": settings.get("timezone", "Asia/Riyadh")
        }

    @router.put("/settings")
    async def update_parent_settings(
        data: dict,
        current_user: dict = Depends(require_roles([UserRole.PARENT]))
    ):
        """تحديث إعدادات ولي الأمر"""
        now = datetime.now(timezone.utc).isoformat()

        await gd_update_one(db.session, "user_preferences", {"user_id": current_user["id"]}, {**data, "updated_at": now})

        return {"message": "تم تحديث الإعدادات بنجاح"}

    @router.get("/notifications")
    async def get_parent_notifications(
        limit: int = 20,
        unread_only: bool = False,
        current_user: dict = Depends(require_roles([UserRole.PARENT]))
    ):
        """إشعارات ولي الأمر"""
        query = {"recipient_id": current_user["id"]}
        if unread_only:
            query["read_status"] = False

        notifications = await gd_find(db.session, "notifications", query, order_by="created_at", desc_order=True, limit=limit)

        unread_count = await gd_count(db.session, "notifications", {"recipient_id": current_user["id"], "read_status": False})

        return {"notifications": notifications, "unread_count": unread_count}

    # ============= REPORTS =============

    @router.get("/reports")
    async def get_parent_reports(
        current_user: dict = Depends(require_roles([UserRole.PARENT]))
    ):
        """تقارير ولي الأمر - ملخص لجميع الأبناء"""
        parent_id = current_user.get("id")
        parent_phone = current_user.get("phone")
        school_id = current_user.get("tenant_id")

        students = await _find_children(parent_id, parent_phone, school_id)

        reports = []
        for s in students:
            sid = s.get("id")

            total_att = await gd_count(db.session, "attendance", {"student_id": sid})
            present = await gd_count(db.session, "attendance", {"student_id": sid, "status": "present"})
            absent = await gd_count(db.session, "attendance", {"student_id": sid, "status": "absent"})
            late = await gd_count(db.session, "attendance", {"student_id": sid, "status": "late"})
            att_rate = round((present / total_att * 100), 1) if total_att > 0 else 0

            grades = await gd_find(db.session, "grades", {"student_id": sid}, limit=500)
            avg_grade = 0
            if grades:
                avg_grade = round(sum(g.get("percentage", 0) for g in grades) / len(grades), 1)

            behaviour_records = await gd_find(db.session, "behaviour_records", {"student_id": sid}, limit=200)
            positive = sum(1 for b in behaviour_records if b.get("category") in ["positive", "إيجابي"])
            negative = sum(1 for b in behaviour_records if b.get("category") in ["negative", "سلبي"])

            reports.append({
                "student_id": sid,
                "student_name": s.get("full_name", s.get("name", "")),
                "grade": s.get("grade_level", s.get("grade", "")),
                "class_name": s.get("class_name", ""),
                "attendance": {
                    "rate": att_rate,
                    "present": present,
                    "absent": absent,
                    "late": late,
                    "total": total_att
                },
                "academic": {
                    "average_grade": avg_grade,
                    "total_grades": len(grades)
                },
                "behaviour": {
                    "positive": positive,
                    "negative": negative,
                    "total": len(behaviour_records)
                }
            })

        return {"reports": reports, "total": len(reports)}

    # ============= ABSENCE EXCUSES =============

    @router.post("/absence-excuse")
    async def submit_absence_excuse(
        data: dict,
        current_user: dict = Depends(require_roles([UserRole.PARENT]))
    ):
        parent_id = current_user.get("id")
        school_id = current_user.get("tenant_id")

        child_id = data.get("child_id")
        absence_date = data.get("absence_date")
        reason = data.get("reason", "").strip()

        if not child_id or not absence_date or not reason:
            raise HTTPException(status_code=400, detail="child_id, absence_date, and reason are required")

        children = await _find_children(parent_id, current_user.get("phone"), school_id)
        child_ids = [c.get("id") for c in children]
        if child_id not in child_ids:
            raise HTTPException(status_code=403, detail="Child not linked to this parent")

        child = next((c for c in children if c.get("id") == child_id), {})

        excuse = {
            "id": str(uuid.uuid4()),
            "parent_id": parent_id,
            "parent_name": current_user.get("full_name", ""),
            "child_id": child_id,
            "child_name": child.get("full_name", child.get("name", "")),
            "school_id": school_id,
            "absence_date": absence_date,
            "reason": reason,
            "attachment_url": data.get("attachment_url"),
            "attachment_name": data.get("attachment_name"),
            "status": "pending",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        await gd_insert(db.session, "absence_excuses", excuse)
        excuse.pop("_id", None)
        return {"message": "تم إرسال العذر بنجاح", "excuse": excuse}

    @router.get("/absence-excuses")
    async def get_absence_excuses(
        current_user: dict = Depends(require_roles([UserRole.PARENT]))
    ):
        parent_id = current_user.get("id")
        excuses = await gd_find(db.session, "absence_excuses", {"parent_id": parent_id}, order_by="created_at", desc_order=True, limit=100)
        return {"excuses": excuses, "total": len(excuses)}

    # ============= MEETING REQUESTS =============

    @router.post("/meeting-request")
    async def submit_meeting_request(
        data: dict,
        current_user: dict = Depends(require_roles([UserRole.PARENT]))
    ):
        parent_id = current_user.get("id")
        school_id = current_user.get("tenant_id")

        preferred_date = data.get("preferred_date")
        preferred_time = data.get("preferred_time")
        topic = data.get("topic", "").strip()
        contact_preference = data.get("contact_preference", "in_person")

        if not preferred_date or not topic:
            raise HTTPException(status_code=400, detail="preferred_date and topic are required")

        meeting = {
            "id": str(uuid.uuid4()),
            "parent_id": parent_id,
            "parent_name": current_user.get("full_name", ""),
            "parent_phone": current_user.get("phone", ""),
            "parent_email": current_user.get("email", ""),
            "school_id": school_id,
            "preferred_date": preferred_date,
            "preferred_time": preferred_time or "",
            "topic": topic,
            "details": data.get("details", "").strip(),
            "contact_preference": contact_preference,
            "status": "pending",
            "admin_notes": "",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        await gd_insert(db.session, "meeting_requests", meeting)
        meeting.pop("_id", None)
        return {"message": "تم إرسال طلب الاجتماع بنجاح", "meeting": meeting}

    @router.get("/meeting-requests")
    async def get_meeting_requests(
        current_user: dict = Depends(require_roles([UserRole.PARENT]))
    ):
        parent_id = current_user.get("id")
        meetings = await gd_find(db.session, "meeting_requests", {"parent_id": parent_id}, order_by="created_at", desc_order=True, limit=100)
        return {"meetings": meetings, "total": len(meetings)}

    return router
