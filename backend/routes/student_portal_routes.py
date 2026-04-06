"""
NASSAQ - Student Portal Routes
مسارات بوابة الطالب
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional, List
from datetime import datetime, timezone, timedelta
import uuid
import logging

logger = logging.getLogger("nassaq.student_portal_routes")


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
        student = await db.students.find_one({"id": student_id})
        if not student:
            student = await db.students.find_one({"user_id": current_user.get("id")})
        
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
            timetable = await db.timetables.find_one(
                {"school_id": school_id, "status": "published"}
            ) or await db.timetables.find_one(
                {"school_id": school_id},
                sort=[("created_at", -1)]
            )
            if timetable:
                sessions = await db.timetable_sessions.find(
                    {
                        "timetable_id": timetable.get("id"),
                        "class_id": student.get("class_id"),
                        "day_of_week": today_en
                    },
                    {"_id": 0}
                ).to_list(20)
                sub_ids = list(set(s.get("subject_id") for s in sessions if s.get("subject_id")))
                tch_ids = list(set(s.get("teacher_id") for s in sessions if s.get("teacher_id")))
                subs = await db.subjects.find({"id": {"$in": sub_ids}}, {"_id": 0, "id": 1, "name_ar": 1}).to_list(100)
                tchs = await db.teachers.find({"id": {"$in": tch_ids}}, {"_id": 0, "id": 1, "full_name": 1}).to_list(100)
                sub_map = {s["id"]: s.get("name_ar", "غير محدد") for s in subs}
                tch_map = {t["id"]: t.get("full_name", "غير محدد") for t in tchs}
                for session in sorted(sessions, key=lambda x: x.get("period_number", 0)):
                    schedule_entries.append({
                        "period": session.get("period_number"),
                        "subject": sub_map.get(session.get("subject_id"), "غير محدد"),
                        "teacher": tch_map.get(session.get("teacher_id"), "غير محدد"),
                        "start_time": session.get("start_time"),
                        "end_time": session.get("end_time")
                    })
        
        # Get recent grades
        recent_grades = []
        grades_cursor = db.grades.find({
            "student_id": student_id
        }).sort("date", -1).limit(5)
        async for grade in grades_cursor:
            recent_grades.append({
                "subject": grade.get("subject"),
                "score": grade.get("score"),
                "max_score": grade.get("max_score"),
                "percentage": grade.get("percentage"),
                "assessment_type": grade.get("assessment_type"),
                "date": grade.get("date")
            })
        
        # Calculate attendance stats
        total_days = await db.attendance.count_documents({"student_id": student_id})
        present_days = await db.attendance.count_documents({"student_id": student_id, "status": "present"})
        absent_days = await db.attendance.count_documents({"student_id": student_id, "status": "absent"})
        late_days = await db.attendance.count_documents({"student_id": student_id, "status": "late"})
        
        attendance_rate = (present_days / total_days * 100) if total_days > 0 else 100
        
        unread_notifications = await db.notifications.count_documents({
            "recipient_id": current_user.get("id"),
            "read_status": False
        })
        
        # Calculate GPA/average
        all_grades = await db.grades.find({"student_id": student_id}).to_list(1000)
        total_score = sum(g.get("percentage", 0) for g in all_grades)
        avg_score = total_score / len(all_grades) if all_grades else 0
        
        school_name = current_user.get("school_name")
        if not school_name and school_id:
            school_doc = await db.schools.find_one({"id": school_id}, {"_id": 0, "name": 1})
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
        
        query = {"student_id": student_id}
        if subject:
            query["subject"] = subject
        if assessment_type:
            query["assessment_type"] = assessment_type
        
        grades = await db.grades.find(query).sort("date", -1).to_list(500)
        
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
        
        query = {"student_id": student_id}
        
        # Filter by month/year if provided
        if month and year:
            start_date = f"{year}-{month:02d}-01"
            if month == 12:
                end_date = f"{year + 1}-01-01"
            else:
                end_date = f"{year}-{month + 1:02d}-01"
            query["date"] = {"$gte": start_date, "$lt": end_date}
        
        records = await db.attendance.find(query).sort("date", -1).to_list(500)
        
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
        student = await db.students.find_one({"id": student_id})
        if not student:
            student = await db.students.find_one({"user_id": current_user.get("id")})
        
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
            timetable = await db.timetables.find_one(
                {"school_id": school_id, "status": "published"}
            ) or await db.timetables.find_one(
                {"school_id": school_id},
                sort=[("created_at", -1)]
            )
            if timetable:
                all_sessions = await db.timetable_sessions.find(
                    {
                        "timetable_id": timetable.get("id"),
                        "class_id": student.get("class_id")
                    },
                    {"_id": 0}
                ).to_list(500)
                sub_ids = list(set(s.get("subject_id") for s in all_sessions if s.get("subject_id")))
                tch_ids = list(set(s.get("teacher_id") for s in all_sessions if s.get("teacher_id")))
                subs = await db.subjects.find({"id": {"$in": sub_ids}}, {"_id": 0, "id": 1, "name_ar": 1}).to_list(100)
                tchs = await db.teachers.find({"id": {"$in": tch_ids}}, {"_id": 0, "id": 1, "full_name": 1}).to_list(100)
                sub_map = {s["id"]: s.get("name_ar", "غير محدد") for s in subs}
                tch_map = {t["id"]: t.get("full_name", "غير محدد") for t in tchs}
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
        
        # Get messages where student is sender or receiver
        messages = await db.messages.find({
            "$or": [
                {"sender_id": user_id},
                {"receiver_id": user_id}
            ]
        }).sort("created_at", -1).limit(50).to_list(50)
        
        return {
            "messages": [
                {
                    "id": m.get("id"),
                    "subject": m.get("subject"),
                    "content": m.get("content"),
                    "sender_id": m.get("sender_id"),
                    "sender_name": m.get("sender_name"),
                    "receiver_id": m.get("receiver_id"),
                    "receiver_name": m.get("receiver_name"),
                    "is_sent": m.get("sender_id") == user_id,
                    "read_status": m.get("read_status", False),
                    "created_at": m.get("created_at")
                }
                for m in messages
            ]
        }
    
    @router.post("/messages")
    async def send_student_message(
        receiver_id: str,
        subject: str,
        content: str,
        current_user: dict = Depends(require_roles([UserRole.STUDENT]))
    ):
        """إرسال رسالة من الطالب"""
        tenant_id = current_user.get("tenant_id")
        receiver = await db.users.find_one({"id": receiver_id})
        if not receiver:
            receiver = await db.teachers.find_one({"id": receiver_id})
        
        if not receiver:
            raise HTTPException(status_code=404, detail="المستلم غير موجود")
        if not tenant_id or (receiver.get("tenant_id") != tenant_id and receiver.get("school_id") != tenant_id):
            raise HTTPException(status_code=403, detail="لا يمكنك مراسلة مستخدم من مدرسة أخرى")
        
        message = {
            "id": str(uuid.uuid4()),
            "subject": subject,
            "content": content,
            "sender_id": current_user.get("id"),
            "sender_name": current_user.get("full_name"),
            "sender_role": "student",
            "receiver_id": receiver_id,
            "receiver_name": receiver.get("full_name") or receiver.get("name"),
            "read_status": False,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        
        await db.messages.insert_one(message)
        
        # Create notification for receiver
        await db.notifications.insert_one({
            "id": str(uuid.uuid4()),
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
        student = await db.students.find_one({"id": student_id})
        if not student:
            student = await db.students.find_one({"user_id": current_user.get("id")})
        
        # Get teachers via timetable_sessions for this student's class
        teachers = []
        if student and student.get("class_id"):
            timetable = await db.timetables.find_one(
                {"school_id": school_id, "status": "published"}
            ) or await db.timetables.find_one(
                {"school_id": school_id},
                sort=[("created_at", -1)]
            )
            teacher_ids_set = set()
            teacher_subject_map = {}
            if timetable:
                sessions = await db.timetable_sessions.find(
                    {
                        "timetable_id": timetable.get("id"),
                        "class_id": student.get("class_id")
                    },
                    {"_id": 0, "teacher_id": 1, "subject_id": 1}
                ).to_list(500)
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
                subs = await db.subjects.find({"id": {"$in": sub_ids}}, {"_id": 0, "id": 1, "name_ar": 1}).to_list(100)
                sub_name_map = {s["id"]: s.get("name_ar", "") for s in subs}
                
                teacher_docs = await db.teachers.find(
                    {"id": {"$in": teacher_ids_list}, "school_id": school_id},
                    {"_id": 0}
                ).to_list(100)
                
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
        
        student = await db.students.find_one({"id": student_id})
        if not student:
            student = await db.students.find_one({"user_id": current_user.get("id")})
        
        total_days = await db.attendance.count_documents({"student_id": student_id})
        present_days = await db.attendance.count_documents({"student_id": student_id, "status": "present"})
        attendance_rate = round((present_days / total_days * 100), 1) if total_days > 0 else 100
        
        all_grades = await db.grades.find({"student_id": student_id}).to_list(1000)
        avg_score = round(sum(g.get("percentage", 0) for g in all_grades) / len(all_grades), 1) if all_grades else 0
        
        behaviour_pos = await db.behaviour_records.count_documents({"student_id": student_id, "type": "positive"})
        behaviour_neg = await db.behaviour_records.count_documents({"student_id": student_id, "type": "negative"})
        
        participation = await db.participation_records.find(
            {"student_id": student_id}, {"_id": 0, "points": 1}
        ).to_list(500)
        total_points = sum(p.get("points", 0) for p in participation)
        
        points_from_grades = len([g for g in all_grades if g.get("percentage", 0) >= 80]) * 5
        points_from_attendance = present_days * 2
        points_from_behaviour = behaviour_pos * 10
        total_score = total_points + points_from_grades + points_from_attendance + points_from_behaviour
        
        class_students = []
        if student and student.get("class_id"):
            class_students = await db.students.find(
                {"class_id": student.get("class_id"), "school_id": school_id},
                {"_id": 0, "id": 1}
            ).to_list(100)
        
        profile_school_name = current_user.get("school_name")
        if not profile_school_name and school_id:
            school_doc = await db.schools.find_one({"id": school_id}, {"_id": 0, "name": 1})
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
                "class_size": len(class_students)
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

        raw = await db.student_activities.find(
            query, {"_id": 0}
        ).sort("date", -1).to_list(100)

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
        
        student = await db.students.find_one({"id": student_id})
        if not student:
            student = await db.students.find_one({"user_id": current_user.get("id")})
        if not student:
            raise HTTPException(status_code=404, detail="سجل الطالب غير موجود")
        
        participation = await db.participation_records.find(
            {"student_id": student_id}, {"_id": 0}
        ).to_list(500)
        participation_points = sum(p.get("points", 0) for p in participation)
        
        all_grades = await db.grades.find({"student_id": student_id}).to_list(1000)
        grade_points = len([g for g in all_grades if g.get("percentage", 0) >= 80]) * 5
        
        total_days = await db.attendance.count_documents({"student_id": student_id})
        present_days = await db.attendance.count_documents({"student_id": student_id, "status": "present"})
        attendance_points = present_days * 2
        
        behaviour_pos = await db.behaviour_records.count_documents({"student_id": student_id, "type": "positive"})
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
            classmates = await db.students.find(
                {"class_id": student.get("class_id"), "school_id": school_id},
                {"_id": 0, "id": 1}
            ).to_list(100)
            class_size = len(classmates)
            cm_ids = [cm.get("id") for cm in classmates]

            from collections import defaultdict
            part_map = defaultdict(int)
            async for doc in db.participation_records.aggregate([
                {"$match": {"student_id": {"$in": cm_ids}}},
                {"$group": {"_id": "$student_id", "total": {"$sum": "$points"}}}
            ]):
                part_map[doc["_id"]] = doc["total"]

            grade_map = defaultdict(int)
            async for doc in db.grades.aggregate([
                {"$match": {"student_id": {"$in": cm_ids}, "percentage": {"$gte": 80}}},
                {"$group": {"_id": "$student_id", "count": {"$sum": 1}}}
            ]):
                grade_map[doc["_id"]] = doc["count"] * 5

            attend_map = defaultdict(int)
            async for doc in db.attendance.aggregate([
                {"$match": {"student_id": {"$in": cm_ids}, "status": "present"}},
                {"$group": {"_id": "$student_id", "count": {"$sum": 1}}}
            ]):
                attend_map[doc["_id"]] = doc["count"]

            beh_map = defaultdict(int)
            async for doc in db.behaviour_records.aggregate([
                {"$match": {"student_id": {"$in": cm_ids}, "type": "positive"}},
                {"$group": {"_id": "$student_id", "count": {"$sum": 1}}}
            ]):
                beh_map[doc["_id"]] = doc["count"]

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
        
        total_days = await db.attendance.count_documents({"student_id": student_id})
        present_days = await db.attendance.count_documents({"student_id": student_id, "status": "present"})
        absent_days = await db.attendance.count_documents({"student_id": student_id, "status": "absent"})
        late_days = await db.attendance.count_documents({"student_id": student_id, "status": "late"})
        attendance_rate = round((present_days / total_days * 100), 1) if total_days > 0 else 100
        
        all_grades = await db.grades.find({"student_id": student_id}).to_list(1000)
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
        total_assignments = await db.student_assignments.count_documents(assignment_filter)
        submissions = await db.assignment_submissions.find(
            {"student_id": student_id}, {"_id": 0}
        ).to_list(500)
        homework_rate = round((len(submissions) / max(1, total_assignments)) * 100, 1)
        
        participation = await db.participation_records.find(
            {"student_id": student_id}, {"_id": 0}
        ).to_list(500)
        participation_count = len(participation)
        participation_rate = min(100, participation_count * 10)
        
        behaviour_pos = await db.behaviour_records.count_documents({"student_id": student_id, "type": "positive"})
        behaviour_neg = await db.behaviour_records.count_documents({"student_id": student_id, "type": "negative"})
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
        
        total_days = await db.attendance.count_documents({"student_id": student_id})
        present_days = await db.attendance.count_documents({"student_id": student_id, "status": "present"})
        attendance_rate = round((present_days / total_days * 100), 1) if total_days > 0 else 100
        
        all_grades = await db.grades.find({"student_id": student_id}).to_list(1000)
        avg_score = round(sum(g.get("percentage", 0) for g in all_grades) / len(all_grades), 1) if all_grades else 0
        
        submissions = await db.assignment_submissions.find(
            {"student_id": student_id}, {"_id": 0}
        ).to_list(500)
        
        participation = await db.participation_records.find(
            {"student_id": student_id}, {"_id": 0}
        ).to_list(500)
        
        behaviour_pos = await db.behaviour_records.count_documents({"student_id": student_id, "type": "positive"})
        
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
        
        student = await db.students.find_one({"id": student_id}, {"_id": 0})
        if not student:
            student = await db.students.find_one({"user_id": current_user.get("id")}, {"_id": 0})
        
        class_id = student.get("class_id") if student else None
        grade_id = student.get("grade_id") or student.get("grade") if student else None
        
        query = {"school_id": school_id}
        if class_id:
            query["$or"] = [
                {"class_ids": class_id},
                {"class_id": class_id},
                {"grade_id": grade_id}
            ]
        
        assignments = await db.student_assignments.find(query, {"_id": 0}).sort("due_date", -1).to_list(100)
        
        submissions = await db.assignment_submissions.find(
            {"student_id": student_id}, {"_id": 0}
        ).to_list(200)
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
    existing = await db.users.find_one({"email": "student@nassaq.com"})
    if existing:
        return existing
    
    # Get first school
    school = await db.schools.find_one({"status": "active"})
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
        "role": "student",
        "tenant_id": school.get("id"),
        "phone": "0512345678",
        "is_active": True,
        "must_change_password": False,
        "student_id": student_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    await db.users.insert_one(user_doc)
    
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
    await db.students.insert_one(student_doc)
    
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
            await db.grades.insert_one(grade_doc)
    
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
        await db.attendance.insert_one(attendance_doc)
    
    return user_doc


async def create_test_parent_account(db):
    """Create test parent account for testing"""
    import bcrypt
    from datetime import datetime, timezone
    import uuid
    
    # Check if test parent already exists
    existing = await db.users.find_one({"email": "parent@nassaq.com"})
    if existing:
        return existing
    
    # Get test student
    test_student = await db.students.find_one({"email": "student@nassaq.com"})
    school = await db.schools.find_one({"status": "active"})
    
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
    await db.users.insert_one(user_doc)
    
    # Link parent to student
    if test_student:
        await db.students.update_one(
            {"id": test_student.get("id")},
            {"$set": {
                "parent_id": parent_id,
                "parent_user_id": parent_user_id,
                "parent_phone": "0509876543",
                "parent_name": "ولي أمر تجريبي"
            }}
        )
    
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
        student = await db.students.find_one({"id": student_id}, {"_id": 0})
        if not student:
            student = await db.students.find_one({"user_id": current_user.get("id")}, {"_id": 0})
        
        class_id = student.get("class_id") if student else None
        grade_id = student.get("grade_id") or student.get("grade") if student else None
        
        # Build query for assignments
        query = {"school_id": school_id, "is_active": True}
        
        if class_id:
            query["$or"] = [
                {"class_ids": class_id},
                {"class_id": class_id},
                {"grade_id": grade_id}
            ]
        
        # Get assignments
        assignments = await db.student_assignments.find(query, {"_id": 0}).sort("due_date", -1).to_list(100)
        
        # Get student submissions
        submissions = await db.assignment_submissions.find(
            {"student_id": student_id},
            {"_id": 0}
        ).to_list(500)
        
        submission_map = {s.get("assignment_id"): s for s in submissions}
        
        # Enrich assignments
        result = []
        now = datetime.now(timezone.utc)
        
        for a in assignments:
            assignment_id = a.get("id")
            submission = submission_map.get(assignment_id)
            
            # Determine status
            due_date_str = a.get("due_date")
            try:
                if isinstance(due_date_str, str):
                    due_date = datetime.fromisoformat(due_date_str.replace('Z', '+00:00'))
                else:
                    due_date = due_date_str
            except Exception as e:
                logger.debug(f"Failed to parse due_date '{due_date_str}': {e}")
                due_date = now + timedelta(days=7)
            
            if submission:
                if submission.get("grade") is not None:
                    a_status = "graded"
                else:
                    a_status = "submitted"
            elif due_date < now:
                a_status = "late"
            else:
                a_status = "pending"
            
            if status and a_status != status:
                continue
            
            # Get subject name
            subject = await db.subjects.find_one({"id": a.get("subject_id")}, {"_id": 0, "name_ar": 1})
            if not subject:
                subject = await db.reference_subjects.find_one({"id": a.get("subject_id")}, {"_id": 0, "name_ar": 1})
            
            # Get teacher name
            teacher = await db.teachers.find_one({"id": a.get("teacher_id")}, {"_id": 0, "full_name": 1, "full_name_ar": 1})
            
            result.append({
                "id": assignment_id,
                "title": a.get("title", ""),
                "description": a.get("description", ""),
                "subject_id": a.get("subject_id"),
                "subject_name": subject.get("name_ar") if subject else "",
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
        assignment = await db.student_assignments.find_one({"id": assignment_id}, {"_id": 0})
        if not assignment:
            raise HTTPException(status_code=404, detail="الواجب غير موجود")
        
        # Check not already submitted
        existing = await db.assignment_submissions.find_one({
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
        
        await db.assignment_submissions.insert_one(submission_doc)
        
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
        
        assignment = await db.student_assignments.find_one({"id": assignment_id}, {"_id": 0})
        if not assignment:
            raise HTTPException(status_code=404, detail="الواجب غير موجود")
        
        # Get submission
        submission = await db.assignment_submissions.find_one({
            "assignment_id": assignment_id,
            "student_id": student_id
        }, {"_id": 0})
        
        return {
            **assignment,
            "submission": submission
        }
    
    return router
