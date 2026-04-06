"""
Principal Timetable Routes
مسارات صفحة الجدول المدرسي للمدير
Clean API wrapper for the School Timetable Page
"""

from fastapi import APIRouter, HTTPException, Header, Depends, Query
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from datetime import datetime, timezone
import uuid, os, logging

logger = logging.getLogger("nassaq.principal_timetable")

_JWT_SECRET = os.environ.get('JWT_SECRET_KEY', '')
_JWT_ALGORITHM = os.environ.get('JWT_ALGORITHM', 'HS256')

router = APIRouter(prefix="/principal/timetable", tags=["Principal Timetable"])

db = None
smart_engine = None

def set_db(database):
    global db
    db = database

def set_engine(engine):
    global smart_engine
    smart_engine = engine


def utcnow():
    return datetime.now(timezone.utc).isoformat()


def _resolve_working_days(raw) -> list:
    if isinstance(raw, dict):
        return [k for k, v in raw.items() if v]
    if isinstance(raw, list):
        return raw
    return ["sunday", "monday", "tuesday", "wednesday", "thursday"]


async def _count_real_conflicts(timetable_id: str) -> int:
    teacher_conflicts = await db.timetable_sessions.aggregate([
        {"$match": {"timetable_id": timetable_id, "teacher_id": {"$nin": [None, ""]}}},
        {"$group": {
            "_id": {"teacher_id": "$teacher_id", "day": "$day_of_week", "period": "$period_number"},
            "count": {"$sum": 1}
        }},
        {"$match": {"count": {"$gt": 1}}}
    ]).to_list(500)
    class_conflicts = await db.timetable_sessions.aggregate([
        {"$match": {"timetable_id": timetable_id, "class_id": {"$nin": [None, ""]}}},
        {"$group": {
            "_id": {"class_id": "$class_id", "day": "$day_of_week", "period": "$period_number"},
            "count": {"$sum": 1}
        }},
        {"$match": {"count": {"$gt": 1}}}
    ]).to_list(500)
    return len(teacher_conflicts) + len(class_conflicts)


async def _get_conflict_details(timetable_id: str, school_id: str) -> list:
    day_names_ar = {
        "sunday": "الأحد", "monday": "الاثنين", "tuesday": "الثلاثاء",
        "wednesday": "الأربعاء", "thursday": "الخميس", "saturday": "السبت"
    }

    teacher_conflicts = await db.timetable_sessions.aggregate([
        {"$match": {"timetable_id": timetable_id, "teacher_id": {"$nin": [None, ""]}}},
        {"$group": {
            "_id": {"teacher_id": "$teacher_id", "day": "$day_of_week", "period": "$period_number"},
            "count": {"$sum": 1},
            "sessions": {"$push": {"class_id": "$class_id", "subject_name": "$subject_name", "session_id": "$id"}}
        }},
        {"$match": {"count": {"$gt": 1}}}
    ]).to_list(500)

    class_conflicts = await db.timetable_sessions.aggregate([
        {"$match": {"timetable_id": timetable_id, "class_id": {"$nin": [None, ""]}}},
        {"$group": {
            "_id": {"class_id": "$class_id", "day": "$day_of_week", "period": "$period_number"},
            "count": {"$sum": 1},
            "sessions": {"$push": {"teacher_id": "$teacher_id", "subject_name": "$subject_name", "session_id": "$id"}}
        }},
        {"$match": {"count": {"$gt": 1}}}
    ]).to_list(500)

    details = []

    teacher_ids = set()
    class_ids = set()
    for c in teacher_conflicts:
        teacher_ids.add(c["_id"]["teacher_id"])
        for s in c.get("sessions", []):
            if s.get("class_id"):
                class_ids.add(s["class_id"])
    for c in class_conflicts:
        class_ids.add(c["_id"]["class_id"])
        for s in c.get("sessions", []):
            if s.get("teacher_id"):
                teacher_ids.add(s["teacher_id"])

    teachers_map = {}
    if teacher_ids:
        async for u in db.users.find({"id": {"$in": list(teacher_ids)}}, {"id": 1, "name": 1, "full_name": 1}):
            teachers_map[u["id"]] = u.get("full_name") or u.get("name", "معلم")

    classes_map = {}
    if class_ids:
        async for c in db.classes.find({"id": {"$in": list(class_ids)}}, {"id": 1, "name": 1}):
            classes_map[c["id"]] = c.get("name", "فصل")

    for c in teacher_conflicts:
        tid = c["_id"]["teacher_id"]
        day = c["_id"]["day"]
        period = c["_id"]["period"]
        teacher_name = teachers_map.get(tid, tid[:8] if tid else "غير معروف")
        involved_classes = [classes_map.get(s.get("class_id"), s.get("class_id", "")) for s in c.get("sessions", [])]
        involved_subjects = [s.get("subject_name", "") for s in c.get("sessions", []) if s.get("subject_name")]

        details.append({
            "type": "teacher",
            "conflict_type_ar": "تعارض معلم",
            "conflict_type_en": "Teacher Conflict",
            "teacher_name": teacher_name,
            "teacher_id": tid,
            "day": day,
            "day_ar": day_names_ar.get(day, day),
            "period": period,
            "classes": involved_classes,
            "subjects": involved_subjects,
            "reason_ar": f"المعلم {teacher_name} مُعيَّن في أكثر من حصة في نفس الوقت (يوم {day_names_ar.get(day, day)} — الحصة {period})",
            "reason_en": f"Teacher {teacher_name} is assigned to multiple sessions at the same time ({day} — period {period})",
            "fix_ar": "قم بتغيير المعلم في إحدى الحصتين المتعارضتين أو نقل إحداهما إلى وقت آخر",
            "fix_en": "Change the teacher in one of the conflicting sessions or move one to a different time slot",
        })

    for c in class_conflicts:
        cid = c["_id"]["class_id"]
        day = c["_id"]["day"]
        period = c["_id"]["period"]
        class_name = classes_map.get(cid, cid[:8] if cid else "غير معروف")
        involved_teachers = [teachers_map.get(s.get("teacher_id"), s.get("teacher_id", "")) for s in c.get("sessions", [])]
        involved_subjects = [s.get("subject_name", "") for s in c.get("sessions", []) if s.get("subject_name")]

        details.append({
            "type": "class",
            "conflict_type_ar": "تعارض فصل",
            "conflict_type_en": "Class Conflict",
            "class_name": class_name,
            "class_id": cid,
            "day": day,
            "day_ar": day_names_ar.get(day, day),
            "period": period,
            "teachers": involved_teachers,
            "subjects": involved_subjects,
            "reason_ar": f"الفصل {class_name} مُعيَّن لأكثر من حصة في نفس الوقت (يوم {day_names_ar.get(day, day)} — الحصة {period})",
            "reason_en": f"Class {class_name} has multiple sessions at the same time ({day} — period {period})",
            "fix_ar": "قم بإزالة إحدى الحصتين المتعارضتين أو نقل إحداهما إلى وقت آخر",
            "fix_en": "Remove one of the conflicting sessions or move one to a different time slot",
        })

    return details

async def get_school_id(x_school_context: str = Header(default=None, alias="X-School-Context"),
                        authorization: str = Header(default=None)) -> Optional[str]:
    if x_school_context and x_school_context != "null":
        return x_school_context
    if authorization:
        try:
            import jwt
            token = authorization.replace("Bearer ", "")
            payload = jwt.decode(token, _JWT_SECRET, algorithms=[_JWT_ALGORITHM])
            school_id = payload.get("school_id") or payload.get("tenant_id")
            if school_id:
                return school_id
            user_id = payload.get("sub")
            if user_id and db is not None:
                user = await db.users.find_one({"id": user_id}, {"_id": 0, "school_id": 1, "tenant_id": 1})
                if user:
                    return user.get("tenant_id") or user.get("school_id")
        except Exception as e:
            logger.warning(f"Failed to extract school_id from authorization token: {e}")
    return None

async def _get_school_data(school_id: str) -> Dict[str, Any]:
    school = await db.schools.find_one({"id": school_id}, {"_id": 0}) or {}
    settings = await db.school_settings.find_one({"school_id": school_id}, {"_id": 0}) or {}
    classes_count = await db.classes.count_documents({"school_id": school_id, "is_active": {"$ne": False}})
    teachers_count = await db.users.count_documents({"school_id": school_id, "role": "teacher", "is_active": {"$ne": False}})
    subjects_count = await db.subjects.count_documents({"school_id": school_id, "is_active": {"$ne": False}})
    ts_count = await db.time_slots.count_documents({"school_id": school_id})
    return {
        "school": school,
        "settings": settings,
        "classes_count": classes_count,
        "teachers_count": teachers_count,
        "subjects_count": subjects_count,
        "time_slots_count": ts_count,
    }

async def _get_active_timetable(school_id: str) -> Optional[Dict]:
    published = await db.timetables.find_one(
        {"school_id": school_id, "status": "published"},
        {"_id": 0}, sort=[("created_at", -1)]
    )
    if published:
        return published
    draft = await db.timetables.find_one(
        {"school_id": school_id, "status": "draft"},
        {"_id": 0}, sort=[("created_at", -1)]
    )
    return draft


# ─────────────────────────────────────────────
# API 1: Page Summary
# GET /api/principal/timetable/summary
# ─────────────────────────────────────────────
@router.get("/summary")
async def get_timetable_summary(
    x_school_context: str = Header(default=None, alias="X-School-Context"),
    authorization: str = Header(default=None)
):
    school_id = await get_school_id(x_school_context, authorization)
    if not school_id:
        raise HTTPException(status_code=400, detail="School context required")

    info = await _get_school_data(school_id)
    school = info["school"]
    settings = info["settings"]
    active_tt = await _get_active_timetable(school_id)

    tt_status = "none"
    version_info = None
    if active_tt:
        tt_status = active_tt.get("status", "draft")
        stats = active_tt.get("statistics", {})
        real_conflicts = await _count_real_conflicts(active_tt.get("id", ""))
        version_info = {
            "id": active_tt.get("id"),
            "version_name": active_tt.get("version_name") or active_tt.get("name", "مسودة"),
            "status": active_tt.get("status"),
            "quality_score": stats.get("optimization_score", 0),
            "conflicts_count": real_conflicts,
            "warnings_count": active_tt.get("warnings_count", 0),
            "sessions_count": stats.get("total_sessions", 0),
            "generated_at": active_tt.get("generated_at") or active_tt.get("created_at"),
            "generated_by": active_tt.get("generated_by") or active_tt.get("created_by", "النظام"),
            "published_at": active_tt.get("published_at"),
        }

    working_days_raw = settings.get("working_days", {})
    if isinstance(working_days_raw, dict):
        active_days = [k for k, v in working_days_raw.items() if v]
    elif isinstance(working_days_raw, list):
        active_days = working_days_raw
    else:
        active_days = []

    academic_year_label = settings.get("academic_year", "")
    current_semester = settings.get("current_semester", "")
    if not academic_year_label:
        ay = await db.academic_years.find_one(
            {"school_id": school_id, "status": {"$in": ["active", "published"]}},
            {"_id": 0, "name": 1, "name_ar": 1}
        )
        if ay:
            academic_year_label = ay.get("name_ar") or ay.get("name", "")

    return {
        "success": True,
        "data": {
            "school_name": school.get("name_ar") or school.get("school_name_ar", ""),
            "academic_year": academic_year_label,
            "current_semester": current_semester,
            "classes_count": info["classes_count"],
            "teachers_count": info["teachers_count"],
            "subjects_count": info["subjects_count"],
            "time_slots_count": info["time_slots_count"],
            "active_days_count": len(active_days),
            "timetable_status": tt_status,
            "active_version": version_info,
            "generation_status": "idle",
        }
    }


# ─────────────────────────────────────────────
# API 2: Readiness Check (delegates to shared engine)
# GET /api/principal/timetable/readiness
# ─────────────────────────────────────────────
@router.get("/readiness")
async def get_readiness(
    x_school_context: str = Header(default=None, alias="X-School-Context"),
    authorization: str = Header(default=None)
):
    school_id = await get_school_id(x_school_context, authorization)
    if not school_id:
        raise HTTPException(status_code=400, detail="School context required")

    from routes.timetable_readiness_routes import _run_readiness_checks
    report = await _run_readiness_checks(school_id)

    items = []
    for cat_key, cat_data in report["categories"].items():
        cat_issues = cat_data["issues"]
        has_critical = any(i["type"] == "critical" for i in cat_issues)
        has_warning = any(i["type"] == "warning" for i in cat_issues)

        if cat_data["score"] == cat_data["max_score"]:
            status = "complete"
        elif has_critical:
            status = "missing"
        elif has_warning:
            status = "warning"
        else:
            status = "complete"

        fix_route = None
        fix_label = None
        desc = cat_data["name_ar"]
        if cat_issues:
            first_issue = cat_issues[0]
            fix_route = first_issue.get("fix_link")
            fix_label = first_issue.get("fix_action")
            desc = first_issue.get("message_ar", desc)
        else:
            desc = f"{cat_data['name_ar']} ✓"

        items.append({
            "key": cat_key,
            "label": cat_data["name_ar"],
            "status": status,
            "description": desc,
            "fix_route": fix_route,
            "fix_action_label": fix_label
        })

    overall_status = report["status"]
    percentage = report["percentage"]
    can_generate = report["can_generate"]

    passed_checks = sum(1 for i in items if i["status"] == "complete")
    failed_checks = sum(1 for i in items if i["status"] == "missing")
    warning_checks = sum(1 for i in items if i["status"] == "warning")
    total_checks = len(items)

    return {
        "success": True,
        "data": {
            "overall_status": overall_status,
            "total_checks": total_checks,
            "passed_checks": passed_checks,
            "failed_checks": failed_checks,
            "warning_checks": warning_checks,
            "percentage": percentage,
            "can_generate": can_generate,
            "items": items,
            "generated_at": utcnow(),
            "summary": report["summary"],
            "phases": report.get("phases", {}),
            "current_phase": report.get("current_phase", 1),
            "total_phases": report.get("total_phases", 6),
            "capacity": report.get("capacity", {})
        }
    }


# ─────────────────────────────────────────────
# API 3: Fetch Versions List
# GET /api/principal/timetable/versions
# ─────────────────────────────────────────────
@router.get("/versions")
async def get_versions(
    x_school_context: str = Header(default=None, alias="X-School-Context"),
    authorization: str = Header(default=None)
):
    school_id = await get_school_id(x_school_context, authorization)
    if not school_id:
        raise HTTPException(status_code=400, detail="School context required")

    cursor = db.timetables.find(
        {"school_id": school_id, "status": {"$ne": "archived"}},
        {"_id": 0},
        sort=[("created_at", -1)]
    ).limit(20)
    timetables = []
    async for tt in cursor:
        tt_id = tt.get("id")
        stats = tt.get("statistics", {})
        sessions_count = (
            stats.get("total_sessions")
            or tt.get("sessions_count")
            or await db.timetable_sessions.count_documents({"timetable_id": tt_id})
        )
        quality = stats.get("optimization_score") or tt.get("quality_score", 0)
        real_conflicts = await _count_real_conflicts(tt_id)
        timetables.append({
            "id": tt_id,
            "version_name": tt.get("version_name") or tt.get("name") or f"جدول {str(tt_id)[:6]}",
            "status": tt.get("status", "draft"),
            "generation_mode": tt.get("generation_mode", "full"),
            "quality_score": round(quality, 1),
            "conflicts_count": real_conflicts,
            "warnings_count": tt.get("warnings_count", 0),
            "sessions_count": sessions_count,
            "generated_at": tt.get("generated_at") or tt.get("created_at"),
            "generated_by": tt.get("generated_by") or tt.get("created_by", "النظام"),
            "published_at": tt.get("published_at"),
            "published_by_name": tt.get("published_by_name"),
            "is_published": tt.get("is_published", False),
            "completion_rate": round(stats.get("completion_rate", 0), 1),
        })

    return {
        "success": True,
        "data": {
            "versions": timetables,
            "total": len(timetables)
        }
    }


# ─────────────────────────────────────────────
# API 4: Fetch Filter Options (classes, teachers, grades)
# GET /api/principal/timetable/filter-options
# ─────────────────────────────────────────────
@router.get("/filter-options")
async def get_filter_options(
    x_school_context: str = Header(default=None, alias="X-School-Context"),
    authorization: str = Header(default=None)
):
    school_id = await get_school_id(x_school_context, authorization)
    if not school_id:
        raise HTTPException(status_code=400, detail="School context required")

    classes = []
    async for c in db.classes.find({"school_id": school_id, "is_active": {"$ne": False}}, {"_id": 0}):
        classes.append({"id": c.get("id"), "name": c.get("name_ar") or c.get("name"), "grade_level": c.get("grade_level")})

    teachers = []
    async for t in db.users.find({"school_id": school_id, "role": "teacher", "is_active": {"$ne": False}}, {"_id": 0}):
        tid = t.get("teacher_id") or t.get("id")
        teachers.append({"id": tid, "name": t.get("full_name") or t.get("name", "")})

    grades = []
    async for g in db.grade_levels.find({"school_id": school_id, "is_active": {"$ne": False}}, {"_id": 0}):
        grades.append({"id": g.get("id"), "name": g.get("name_ar"), "grade_number": g.get("grade_number")})

    subjects = []
    async for s in db.subjects.find({"school_id": school_id, "is_active": {"$ne": False}}, {"_id": 0}):
        subjects.append({"id": s.get("id"), "name": s.get("name_ar") or s.get("name", "")})

    raw_time_slots = []
    async for ts in db.time_slots.find({"school_id": school_id}, {"_id": 0}):
        slot_num = ts.get("slot_number") or ts.get("period_number")
        is_break = ts.get("is_break", False)
        is_prayer = ts.get("is_prayer", False)
        raw_type = ts.get("type", "period")
        block_type = ts.get("block_type")
        if block_type and block_type in ("break", "prayer", "assembly", "custom"):
            slot_type = block_type
        elif is_prayer or raw_type == "prayer":
            slot_type = "prayer"
        elif is_break or raw_type == "break":
            slot_type = "break"
        elif raw_type and raw_type != "period":
            slot_type = raw_type
        else:
            slot_type = "period"
        raw_time_slots.append({
            "id": ts.get("id"),
            "slot_number": slot_num,
            "type": slot_type,
            "name_ar": ts.get("name_ar") or ts.get("name") or ts.get("label_ar") or ts.get("label") or ts.get("title_ar") or (
                "استراحة" if slot_type == "break" else "صلاة" if slot_type == "prayer" else None
            ),
            "start_time": ts.get("start_time"),
            "end_time": ts.get("end_time"),
            "is_break": is_break,
            "is_prayer": is_prayer,
        })
    raw_time_slots.sort(key=lambda x: x.get("start_time") or "99:99")

    teaching_counter = 0
    time_slots = []
    for slot in raw_time_slots:
        is_teaching = slot["type"] not in ("break", "prayer")
        if is_teaching:
            teaching_counter += 1
            slot["period_number"] = teaching_counter
        else:
            slot["period_number"] = None
        time_slots.append(slot)

    settings = await db.school_settings.find_one({"school_id": school_id}, {"_id": 0}) or {}
    working_days_config = settings.get("working_days", {})
    day_names = {"sunday": "الأحد", "monday": "الاثنين", "tuesday": "الثلاثاء",
                 "wednesday": "الأربعاء", "thursday": "الخميس", "friday": "الجمعة", "saturday": "السبت"}
    day_order = ["sunday", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday"]
    if isinstance(working_days_config, list):
        active_days = set(working_days_config)
        working_days = [
            {"key": d, "name_ar": day_names[d], "order": i}
            for i, d in enumerate(day_order)
            if d in active_days
        ]
    else:
        working_days = [
            {"key": d, "name_ar": day_names[d], "order": i}
            for i, d in enumerate(day_order)
            if working_days_config.get(d, False)
        ]

    timetable_settings = {
        "periods_per_day": settings.get("periods_per_day", 7),
        "period_duration": settings.get("period_duration", 45),
        "school_day_start": settings.get("school_day_start"),
        "school_day_end": settings.get("school_day_end"),
    }

    return {
        "success": True,
        "data": {
            "classes": sorted(classes, key=lambda x: x.get("grade_level", 0)),
            "teachers": teachers,
            "subjects": subjects,
            "grades": sorted(grades, key=lambda x: x.get("grade_number", 0)),
            "time_slots": time_slots,
            "working_days": working_days,
            "timetable_settings": timetable_settings
        }
    }


# ─────────────────────────────────────────────
# API 5: Fetch Timetable Grid
# GET /api/principal/timetable/grid
# ─────────────────────────────────────────────
@router.get("/grid")
async def get_timetable_grid(
    timetable_id: Optional[str] = Query(None),
    view_mode: str = Query("class"),
    filter_id: Optional[str] = Query(None),
    class_id: Optional[str] = Query(None),
    teacher_id: Optional[str] = Query(None),
    subject_id: Optional[str] = Query(None),
    day: Optional[str] = Query(None),
    x_school_context: str = Header(default=None, alias="X-School-Context"),
    authorization: str = Header(default=None)
):
    school_id = await get_school_id(x_school_context, authorization)
    if not school_id:
        raise HTTPException(status_code=400, detail="School context required")

    if timetable_id:
        tt = await db.timetables.find_one({"id": timetable_id, "school_id": school_id}, {"_id": 0})
    else:
        tt = await _get_active_timetable(school_id)

    if not tt:
        return {"success": True, "data": {"sessions": [], "timetable": None, "total": 0}}

    classes_map = {}
    async for c in db.classes.find({"school_id": school_id}, {"_id": 0, "id": 1, "name": 1, "name_ar": 1}):
        classes_map[c["id"]] = c.get("name_ar") or c.get("name", "")

    subjects_map = {}
    async for s in db.subjects.find({"school_id": school_id}, {"_id": 0, "id": 1, "name_ar": 1, "name": 1}):
        subjects_map[s["id"]] = s.get("name_ar") or s.get("name", "")

    teachers_map = {}
    async for t in db.users.find({"school_id": school_id, "role": "teacher"}, {"_id": 0, "id": 1, "full_name": 1, "name": 1, "teacher_id": 1}):
        name = t.get("full_name") or t.get("name", "")
        if name:
            teachers_map[t["id"]] = name
            if t.get("teacher_id"):
                teachers_map[t["teacher_id"]] = name
    async for t in db.teachers.find({"school_id": school_id}, {"_id": 0, "id": 1, "full_name": 1, "name": 1, "name_ar": 1}):
        name = t.get("full_name") or t.get("name_ar") or t.get("name", "")
        if name and (t["id"] not in teachers_map or not teachers_map[t["id"]]):
            teachers_map[t["id"]] = name

    query = {"timetable_id": tt.get("id")}

    has_multi_filter = class_id or teacher_id or subject_id or day
    if has_multi_filter:
        if class_id:
            query["class_id"] = class_id
        if teacher_id:
            query["teacher_id"] = teacher_id
        if subject_id:
            query["subject_id"] = subject_id
        if day:
            query["$or"] = [{"day_of_week": day}, {"day": day}]
    elif filter_id:
        if view_mode == "class":
            query["class_id"] = filter_id
        elif view_mode == "teacher":
            query["teacher_id"] = filter_id
        elif view_mode == "grade":
            query["grade_id"] = filter_id
        elif view_mode == "subject":
            query["subject_id"] = filter_id
        elif view_mode == "day":
            query["$or"] = [{"day_of_week": filter_id}, {"day": filter_id}]

    sessions = []
    async for s in db.timetable_sessions.find(query, {"_id": 0}):
        cid = s.get("class_id", "")
        sid = s.get("subject_id", "")
        tid = s.get("teacher_id", "")
        sessions.append({
            "id": s.get("id"),
            "timetable_id": s.get("timetable_id"),
            "class_id": cid,
            "class_name": s.get("class_name") or classes_map.get(cid, cid),
            "subject_id": sid,
            "subject_name": s.get("subject_name") or subjects_map.get(sid, sid),
            "teacher_id": tid,
            "teacher_name": s.get("teacher_name") or teachers_map.get(tid, tid),
            "day_of_week": s.get("day_of_week") or s.get("day"),
            "period_number": s.get("period_number") or s.get("period"),
            "time_slot_id": s.get("time_slot_id"),
            "start_time": s.get("start_time"),
            "end_time": s.get("end_time"),
            "is_ai_generated": s.get("is_ai_generated", True) or s.get("source_type") == "ai_generated",
            "is_locked": s.get("is_locked", False),
            "has_warning": s.get("has_warning", False),
            "status": s.get("status", "scheduled"),
            "grade_id": s.get("grade_id"),
        })

    return {
        "success": True,
        "data": {
            "timetable": {
                "id": tt.get("id"),
                "status": tt.get("status"),
                "version_name": tt.get("version_name") or tt.get("name"),
                "quality_score": tt.get("statistics", {}).get("optimization_score", 0),
            },
            "sessions": sessions,
            "total": len(sessions)
        }
    }


# ─────────────────────────────────────────────
# API 6: Fetch Insights
# GET /api/principal/timetable/insights
# ─────────────────────────────────────────────
@router.get("/insights")
async def get_insights(
    timetable_id: Optional[str] = Query(None),
    x_school_context: str = Header(default=None, alias="X-School-Context"),
    authorization: str = Header(default=None)
):
    school_id = await get_school_id(x_school_context, authorization)
    if not school_id:
        raise HTTPException(status_code=400, detail="School context required")

    if timetable_id:
        tt = await db.timetables.find_one({"id": timetable_id}, {"_id": 0})
    else:
        tt = await _get_active_timetable(school_id)

    if not tt:
        return {"success": True, "data": {"insights": None}}

    tt_id = tt.get("id")
    total_sessions = await db.timetable_sessions.count_documents({"timetable_id": tt_id})
    assigned = await db.timetable_sessions.count_documents({"timetable_id": tt_id, "teacher_id": {"$ne": None}})

    conflicts = await _count_real_conflicts(tt_id)

    day_dist = {}
    async for s in db.timetable_sessions.find({"timetable_id": tt_id}, {"_id": 0, "day_of_week": 1}):
        day = s.get("day_of_week") or s.get("day", "")
        day_dist[day] = day_dist.get(day, 0) + 1

    subject_dist = {}
    subjects_map = {}
    async for sub in db.subjects.find({"school_id": school_id}, {"_id": 0, "id": 1, "name_ar": 1, "name": 1}):
        subjects_map[sub["id"]] = sub.get("name_ar") or sub.get("name", "")

    async for s in db.timetable_sessions.find({"timetable_id": tt_id}, {"_id": 0, "subject_id": 1, "subject_name": 1}):
        subj = s.get("subject_name") or subjects_map.get(s.get("subject_id", ""), "")
        if subj:
            subject_dist[subj] = subject_dist.get(subj, 0) + 1

    stats = tt.get("statistics", {})
    return {
        "success": True,
        "data": {
            "insights": {
                "quality_score": stats.get("optimization_score", 0),
                "total_sessions": total_sessions,
                "assigned_sessions": assigned,
                "unassigned_sessions": total_sessions - assigned,
                "conflicts_count": conflicts,
                "warnings_count": tt.get("warnings_count", 0),
                "coverage_percentage": round((assigned / total_sessions * 100) if total_sessions > 0 else 0, 1),
                "day_distribution": day_dist,
                "subject_distribution": subject_dist,
                "unscheduled_demands": tt.get("unscheduled_count", 0),
            }
        }
    }


# ─────────────────────────────────────────────
# API 7: Fetch Issues
# GET /api/principal/timetable/issues
# ─────────────────────────────────────────────
@router.get("/issues")
async def get_issues(
    timetable_id: Optional[str] = Query(None),
    x_school_context: str = Header(default=None, alias="X-School-Context"),
    authorization: str = Header(default=None)
):
    school_id = await get_school_id(x_school_context, authorization)
    if not school_id:
        raise HTTPException(status_code=400, detail="School context required")

    if timetable_id:
        tt = await db.timetables.find_one({"id": timetable_id}, {"_id": 0})
    else:
        tt = await _get_active_timetable(school_id)

    issues = []
    if tt and tt.get("school_id") == school_id:
        tt_id = tt.get("id")
        try:
            async for c in db.timetable_conflicts.find({"timetable_id": tt_id}, {"_id": 0}).limit(50):
                issues.append({
                    "id": c.get("id", str(uuid.uuid4())),
                    "type": c.get("severity", "warning"),
                    "category": c.get("type") or c.get("conflict_type", "conflict"),
                    "message_ar": c.get("description_ar") or c.get("message_ar") or c.get("description", "تعارض في الجدول"),
                    "message_en": c.get("description_en") or c.get("message_en") or c.get("description", "Timetable conflict"),
                    "affected_items": c.get("affected_items"),
                })
        except Exception as e:
            logger.warning(f"Failed to load timetable conflicts for {tt_id}: {e}")

        try:
            unscheduled = []
            async for u in db.timetable_unscheduled_demands.find({"timetable_id": tt_id}, {"_id": 0}).limit(20):
                unscheduled.append(u)
            if unscheduled:
                issues.append({
                    "id": "unscheduled-summary",
                    "type": "warning",
                    "category": "unscheduled",
                    "message_ar": f"يوجد {len(unscheduled)} حصة لم يتم توزيعها",
                    "message_en": f"{len(unscheduled)} sessions could not be scheduled",
                    "affected_items": [u.get("subject_name", "") for u in unscheduled[:5]]
                })
        except Exception as e:
            logger.warning(f"Failed to load unscheduled demands for {tt_id}: {e}")

        try:
            underutilized = tt.get("underutilized_teachers", [])
            teachers_map = {}
            if underutilized:
                teacher_ids = [t.get("teacher_id") for t in underutilized if t.get("teacher_id")]
                async for t in db.teachers.find({"id": {"$in": teacher_ids}}, {"_id": 0, "id": 1, "name": 1, "name_ar": 1}):
                    teachers_map[t["id"]] = t.get("name_ar") or t.get("name", "")

            zero_session_teachers = [t for t in underutilized if t.get("assigned_sessions", 0) == 0]
            low_load_teachers = [t for t in underutilized if t.get("assigned_sessions", 0) > 0]

            subject_names_map = {}
            all_subject_ids = set()
            for t in underutilized:
                for sid in t.get("subject_ids", []):
                    all_subject_ids.add(sid)
            if all_subject_ids:
                async for s in db.subjects.find({"id": {"$in": list(all_subject_ids)}}, {"_id": 0, "id": 1, "name_ar": 1, "name": 1}):
                    subject_names_map[s["id"]] = s.get("name_ar") or s.get("name", "")

            if zero_session_teachers:
                teacher_details = []
                for t in zero_session_teachers[:10]:
                    tname = teachers_map.get(t["teacher_id"], t.get("teacher_name", ""))
                    subject_names = [subject_names_map.get(sid, sid) for sid in t.get("subject_ids", [])]
                    teacher_details.append({
                        "teacher_id": t["teacher_id"],
                        "teacher_name": tname,
                        "subject_names": subject_names,
                        "reasons_ar": t.get("reasons_ar", [t.get("reason_ar", "")]),
                        "reasons_en": t.get("reasons_en", [t.get("reason_en", "")]),
                        "has_availability": t.get("has_availability", True),
                        "has_demand_match": t.get("has_demand_match", False),
                        "matched_classes": t.get("matched_classes", 0),
                    })
                teacher_names = [d["teacher_name"] for d in teacher_details]
                issues.append({
                    "id": "zero-session-teachers",
                    "type": "critical",
                    "category": "teacher_distribution",
                    "message_ar": f"يوجد {len(zero_session_teachers)} معلم لم يتم توزيع أي حصص عليهم رغم وجود إسنادات",
                    "message_en": f"{len(zero_session_teachers)} teacher(s) have assignments but received zero sessions",
                    "affected_items": teacher_names,
                    "details": teacher_details
                })

            if low_load_teachers:
                teacher_details = []
                for t in low_load_teachers[:10]:
                    tname = teachers_map.get(t["teacher_id"], t.get("teacher_name", ""))
                    subject_names = [subject_names_map.get(sid, sid) for sid in t.get("subject_ids", [])]
                    teacher_details.append({
                        "teacher_id": t["teacher_id"],
                        "teacher_name": tname,
                        "subject_names": subject_names,
                        "assigned_sessions": t.get("assigned_sessions", 0),
                        "weekly_load": t.get("weekly_load", 24),
                    })
                teacher_names = [d["teacher_name"] for d in teacher_details]
                issues.append({
                    "id": "low-load-teachers",
                    "type": "warning",
                    "category": "teacher_distribution",
                    "message_ar": f"{len(low_load_teachers)} معلم حصلوا على حصص أقل بكثير من نصابهم",
                    "message_en": f"{len(low_load_teachers)} teacher(s) have significantly fewer sessions than their capacity",
                    "affected_items": teacher_names,
                    "details": teacher_details
                })
        except Exception as e:
            logger.warning(f"Failed to analyze teacher distribution for timetable: {e}")

    return {
        "success": True,
        "data": {
            "issues": issues,
            "total": len(issues),
            "critical_count": len([i for i in issues if i["type"] == "critical"]),
            "warning_count": len([i for i in issues if i["type"] == "warning"]),
        }
    }


# ─────────────────────────────────────────────
# API 8: Generate Timetable
# POST /api/principal/timetable/generate
# ─────────────────────────────────────────────
class GenerateRequest(BaseModel):
    use_baseline: bool = False
    generation_mode: str = "full"
    target_classes: Optional[List[str]] = None
    semester: str = "first"
    notes: Optional[str] = None

@router.post("/generate")
async def generate_timetable(
    body: GenerateRequest,
    x_school_context: str = Header(default=None, alias="X-School-Context"),
    authorization: str = Header(default=None)
):
    school_id = await get_school_id(x_school_context, authorization)
    if not school_id:
        raise HTTPException(status_code=400, detail="School context required")

    if smart_engine is None:
        raise HTTPException(status_code=503, detail="Scheduling engine not available")

    try:
        result = await smart_engine.generate_timetable(
            school_id=school_id,
            created_by="principal"
        )

        if hasattr(result, 'timetable_id'):
            timetable_id = result.timetable_id
            status = result.status
            quality_score = round(result.optimization_score or 0, 1)
            sessions_count = result.scheduled_sessions or 0
            conflicts_count = result.conflicts_count or 0
            unscheduled_count = result.unscheduled_count or 0
            success = result.success
            message_ar = result.message_ar or "تم توليد الجدول"
        elif isinstance(result, dict):
            timetable_id = result.get("timetable_id")
            status = result.get("status", "completed")
            quality_score = result.get("quality_score", 0)
            sessions_count = result.get("scheduled_sessions", 0)
            conflicts_count = result.get("conflicts_count", 0)
            unscheduled_count = result.get("unscheduled_count", 0)
            success = result.get("success", True)
            message_ar = result.get("message_ar", "تم توليد الجدول")
        else:
            timetable_id = str(result) if result else None
            status = "completed"
            quality_score = 0
            sessions_count = 0
            conflicts_count = 0
            unscheduled_count = 0
            success = True
            message_ar = "تم توليد الجدول"

        if not success:
            raise HTTPException(status_code=422, detail=message_ar)

        if timetable_id:
            school_settings = await db.school_settings.find_one({"school_id": school_id})
            active_days = _resolve_working_days(school_settings.get("working_days") if school_settings else None)
            deleted_off_days = await db.timetable_sessions.delete_many({
                "timetable_id": timetable_id,
                "day_of_week": {"$nin": active_days}
            })
            if deleted_off_days.deleted_count > 0:
                sessions_count = await db.timetable_sessions.count_documents({"timetable_id": timetable_id})

            real_conflicts = await _count_real_conflicts(timetable_id)
            await db.timetables.update_one(
                {"id": timetable_id},
                {"$set": {"statistics.conflicts_count": real_conflicts}}
            )
            conflicts_count = real_conflicts

        return {
            "success": True,
            "message": "تم توليد الجدول بنجاح",
            "data": {
                "timetable_id": timetable_id,
                "status": status,
                "quality_score": quality_score,
                "sessions_count": sessions_count,
                "conflicts_count": conflicts_count,
                "unscheduled_count": unscheduled_count,
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=422, detail="خطأ في معالجة البيانات")


# ─────────────────────────────────────────────
# API 9: Pre-Publish Validation
# GET /api/principal/timetable/version/{id}/validate-publish
# ─────────────────────────────────────────────
@router.get("/version/{version_id}/validate-publish")
async def validate_before_publish(
    version_id: str,
    x_school_context: str = Header(default=None, alias="X-School-Context"),
    authorization: str = Header(default=None)
):
    school_id = await get_school_id(x_school_context, authorization)
    if not school_id:
        raise HTTPException(status_code=400, detail="School context required")

    tt = await db.timetables.find_one({"id": version_id, "school_id": school_id})
    if not tt:
        raise HTTPException(status_code=404, detail="Timetable version not found")

    validation_errors = []
    validation_warnings = []

    hard_constraints = await db.timetable_hard_constraints.find(
        {"is_system": True, "is_active": True}, {"_id": 0, "code": 1, "name_ar": 1, "validation_key": 1}
    ).to_list(50)
    hc_keys = {hc["validation_key"] for hc in hard_constraints}

    school_settings = await db.school_settings.find_one({"school_id": school_id})
    periods_per_day = school_settings.get("periods_per_day", 7) if school_settings else 7

    time_slots = []
    async for slot in db.time_slots.find({"school_id": school_id}).sort("period_number", 1):
        time_slots.append(slot)
    teaching_slots = [s for s in time_slots if not s.get("is_break") and not s.get("is_prayer")]

    if len(teaching_slots) != periods_per_day:
        validation_warnings.append({
            "code": "PERIODS_MISMATCH",
            "message": f"عدد الحصص في الإعدادات ({periods_per_day}) لا يتطابق مع الفترات الزمنية ({len(teaching_slots)})"
        })

    break_slots = [s for s in time_slots if s.get("is_break")]
    prayer_slots = [s for s in time_slots if s.get("is_prayer")]
    if not break_slots:
        validation_warnings.append({"code": "NO_BREAK", "message": "لم يتم تحديد فترة استراحة في الجدول"})
    if not prayer_slots:
        validation_warnings.append({"code": "NO_PRAYER", "message": "لم يتم تحديد فترة صلاة في الجدول"})

    sessions = await db.timetable_sessions.count_documents({"timetable_id": version_id})
    if sessions == 0:
        validation_errors.append({"code": "NO_SESSIONS", "message": "الجدول لا يحتوي على أي حصص"})

    conflict_details = await _get_conflict_details(version_id, school_id)
    teacher_conflict_details = [c for c in conflict_details if c.get("type") == "teacher"]
    class_conflict_details = [c for c in conflict_details if c.get("type") == "class"]
    real_conflicts = len(conflict_details)
    if real_conflicts > 0:
        validation_errors.append({
            "code": "CONFLICT",
            "message": f"يوجد {real_conflicts} تعارض في الجدول (معلم أو فصل مزدوج الحجز)",
            "details": conflict_details
        })

    # HC-01: Teacher Overlap — teacher_id + day + period must be unique
    if "teacher_overlap" in hc_keys and teacher_conflict_details:
        validation_errors.append({
            "code": "HC-01",
            "constraint": "teacher_overlap",
            "message": f"القيد الإلزامي: لا يمكن إسناد أكثر من حصة لنفس المعلم في نفس الوقت — يوجد {len(teacher_conflict_details)} تعارض معلم",
            "details": teacher_conflict_details
        })

    # HC-02: Class Overlap — class_id + day + period must be unique
    if "class_overlap" in hc_keys and class_conflict_details:
        validation_errors.append({
            "code": "HC-02",
            "constraint": "class_overlap",
            "message": f"القيد الإلزامي: لا يمكن تعيين فصل لأكثر من حصة في نفس الوقت — يوجد {len(class_conflict_details)} تعارض فصل",
            "details": class_conflict_details
        })

    classes = await db.classes.find({"school_id": school_id}).to_list(500)
    working_days = _resolve_working_days(school_settings.get("working_days") if school_settings else None)
    teaching_period_numbers = [s.get("period_number") for s in teaching_slots]

    empty_slots_count = 0
    for cls in classes:
        for day in working_days:
            for pn in teaching_period_numbers:
                has = await db.timetable_sessions.find_one({
                    "timetable_id": version_id,
                    "class_id": cls.get("id"),
                    "day_of_week": day,
                    "period_number": pn
                })
                if not has:
                    empty_slots_count += 1

    if empty_slots_count > 0:
        validation_warnings.append({
            "code": "EMPTY_SLOTS",
            "message": f"يوجد {empty_slots_count} خانة فارغة في الجدول"
        })

    if "schedule_completeness" in hc_keys and empty_slots_count > 0:
        validation_errors.append({
            "code": "HC-14",
            "constraint": "schedule_completeness",
            "message": f"القيد الإلزامي: اكتمال جميع الحصص — يوجد {empty_slots_count} خانة فارغة في الجدول"
        })

    underutilized = tt.get("underutilized_teachers", [])
    zero_session = [t for t in underutilized if t.get("assigned_sessions", 0) == 0]
    if zero_session:
        names = []
        teacher_ids = [t.get("teacher_id") for t in zero_session]
        teachers_map = {}
        async for t in db.teachers.find({"id": {"$in": teacher_ids}}, {"_id": 0, "id": 1, "full_name": 1, "name_ar": 1}):
            teachers_map[t["id"]] = t.get("full_name") or t.get("name_ar", "")
        for t in zero_session:
            tname = teachers_map.get(t["teacher_id"], t.get("teacher_name", ""))
            names.append(tname)
        validation_warnings.append({
            "code": "TEACHERS_WITHOUT_SESSIONS",
            "message": f"يوجد {len(zero_session)} معلم لم يحصلوا على أي حصة: {', '.join(names[:5])}",
            "teacher_names": names
        })

    can_publish = len(validation_errors) == 0

    return {
        "success": True,
        "data": {
            "can_publish": can_publish,
            "errors": validation_errors,
            "warnings": validation_warnings,
            "sessions_count": sessions,
            "classes_count": len(classes),
            "total_slots": len(classes) * len(working_days) * len(teaching_period_numbers),
            "empty_slots": empty_slots_count,
            "hard_constraints_enforced": len(hard_constraints),
        }
    }


# ─────────────────────────────────────────────
# API 9b: Publish Version
# POST /api/principal/timetable/version/{id}/publish
# ─────────────────────────────────────────────
@router.post("/version/{version_id}/publish")
async def publish_version(
    version_id: str,
    x_school_context: str = Header(default=None, alias="X-School-Context"),
    authorization: str = Header(default=None)
):
    school_id = await get_school_id(x_school_context, authorization)
    if not school_id:
        raise HTTPException(status_code=400, detail="School context required")

    tt = await db.timetables.find_one({"id": version_id, "school_id": school_id})
    if not tt:
        raise HTTPException(status_code=404, detail="Timetable version not found")

    sessions_count = await db.timetable_sessions.count_documents({"timetable_id": version_id})
    if sessions_count == 0:
        raise HTTPException(status_code=422, detail="لا يمكن نشر جدول فارغ بدون حصص")

    teacher_conflicts = await db.timetable_sessions.aggregate([
        {"$match": {"timetable_id": version_id}},
        {"$group": {
            "_id": {"teacher_id": "$teacher_id", "day": "$day_of_week", "period": "$period_number"},
            "count": {"$sum": 1}
        }},
        {"$match": {"count": {"$gt": 1}}}
    ]).to_list(100)
    if teacher_conflicts:
        raise HTTPException(status_code=422, detail=f"يوجد {len(teacher_conflicts)} تعارض في جدول المعلمين، يجب حلها قبل النشر")

    class_conflicts = await db.timetable_sessions.aggregate([
        {"$match": {"timetable_id": version_id}},
        {"$group": {
            "_id": {"class_id": "$class_id", "day": "$day_of_week", "period": "$period_number"},
            "count": {"$sum": 1}
        }},
        {"$match": {"count": {"$gt": 1}}}
    ]).to_list(100)
    if class_conflicts:
        raise HTTPException(status_code=422, detail=f"يوجد {len(class_conflicts)} تعارض في جدول الفصول، يجب حلها قبل النشر")

    now = utcnow()

    previously_published = []
    async for prev in db.timetables.find({"school_id": school_id, "status": "published", "id": {"$ne": version_id}}, {"id": 1, "_id": 0}):
        previously_published.append(prev.get("id"))

    if previously_published:
        await db.timetables.update_many(
            {"school_id": school_id, "status": "published", "id": {"$ne": version_id}},
            {"$set": {"status": "archived", "archived_at": now, "archived_by": "system_auto_archive"}}
        )

    publisher_info = "principal"
    publisher_name = "المدير"
    if authorization:
        try:
            import jwt
            token = authorization.replace("Bearer ", "")
            payload = jwt.decode(token, _JWT_SECRET, algorithms=[_JWT_ALGORITHM])
            publisher_info = payload.get("sub") or "principal"
            user_doc = await db.users.find_one({"id": publisher_info})
            if user_doc:
                publisher_name = user_doc.get("full_name") or user_doc.get("name") or publisher_info
        except Exception as e:
            logger.warning(f"Failed to resolve publisher info from token: {e}")

    school_settings = await db.school_settings.find_one({"school_id": school_id})
    working_days = _resolve_working_days(school_settings.get("working_days") if school_settings else None)

    time_slots_list = []
    async for slot in db.time_slots.find({"school_id": school_id}, {"_id": 0}).sort("period_number", 1):
        time_slots_list.append(slot)
    teaching_periods = [s for s in time_slots_list if not s.get("is_break") and not s.get("is_prayer")]
    break_positions = [s.get("period_number") for s in time_slots_list if s.get("is_break")]
    prayer_positions = [s.get("period_number") for s in time_slots_list if s.get("is_prayer")]

    all_sessions = await db.timetable_sessions.find(
        {"timetable_id": version_id}, {"_id": 0}
    ).to_list(50000)  # full fetch required: snapshot captures complete timetable state

    classes_list = await db.classes.find({"school_id": school_id}, {"_id": 0, "id": 1, "name": 1, "name_ar": 1, "grade": 1, "section": 1}).to_list(500)

    teacher_ids_in_tt = list(set(s.get("teacher_id") for s in all_sessions if s.get("teacher_id")))
    teachers_list = await db.teachers.find(
        {"id": {"$in": teacher_ids_in_tt}},
        {"_id": 0, "id": 1, "full_name": 1, "name": 1, "email": 1}
    ).to_list(2000)

    subject_ids_in_tt = list(set(s.get("subject_id") for s in all_sessions if s.get("subject_id")))
    subjects_list = await db.subjects.find(
        {"id": {"$in": subject_ids_in_tt}},
        {"_id": 0, "id": 1, "name": 1, "name_ar": 1, "code": 1}
    ).to_list(500)

    academic_year_doc = await db.academic_years.find_one({"school_id": school_id, "is_current": True}, {"_id": 0})
    academic_term_doc = await db.academic_terms.find_one({"school_id": school_id, "is_current": True}, {"_id": 0})

    snapshot = {
        "id": str(uuid.uuid4()),
        "timetable_id": version_id,
        "school_id": school_id,
        "version_name": tt.get("version_name") or tt.get("name") or f"إصدار {version_id[:6]}",
        "published_at": now,
        "published_by": publisher_info,
        "published_by_name": publisher_name,
        "academic_year": academic_year_doc.get("name", "") if academic_year_doc else "",
        "academic_year_id": academic_year_doc.get("id", "") if academic_year_doc else "",
        "academic_term": academic_term_doc.get("name", "") if academic_term_doc else "",
        "academic_term_id": academic_term_doc.get("id", "") if academic_term_doc else "",
        "working_days": working_days,
        "time_slots": time_slots_list,
        "teaching_periods_count": len(teaching_periods),
        "break_positions": break_positions,
        "prayer_positions": prayer_positions,
        "classes": classes_list,
        "teachers": teachers_list,
        "subjects": subjects_list,
        "sessions": all_sessions,
        "sessions_count": len(all_sessions),
        "classes_count": len(classes_list),
        "teachers_count": len(teachers_list),
        "subjects_count": len(subjects_list),
        "total_slots": len(classes_list) * len(teaching_periods) * len(working_days),
        "coverage_percent": round((len(all_sessions) / max(len(classes_list) * len(teaching_periods) * len(working_days), 1)) * 100, 1),
        "quality_score": tt.get("quality_score", 0),
        "created_at": now,
    }

    snapshot_saved = False
    try:
        await db.published_timetables.insert_one(snapshot)
        snapshot_saved = True
    except Exception as e:
        import logging
        logging.getLogger("nassaq").error(f"Failed to save timetable snapshot: {e}")

    publish_update = {
        "status": "published",
        "is_published": True,
        "published_at": now,
        "published_by": publisher_info,
        "published_by_name": publisher_name,
        "updated_at": now
    }

    if smart_engine:
        try:
            engine_result = await smart_engine.publish_timetable(version_id, publisher_info)
            if not engine_result:
                await db.timetables.update_one(
                    {"id": version_id},
                    {"$set": publish_update}
                )
        except Exception as e:
            logger.warning(f"Smart engine publish_timetable failed for {version_id}, falling back to direct update: {e}")
            await db.timetables.update_one(
                {"id": version_id},
                {"$set": publish_update}
            )
    else:
        await db.timetables.update_one(
            {"id": version_id},
            {"$set": publish_update}
        )

    verified = await db.timetables.find_one({"id": version_id}, {"_id": 0, "status": 1})
    if not verified or verified.get("status") != "published":
        await db.timetables.update_one(
            {"id": version_id},
            {"$set": publish_update}
        )

    try:
        await db.audit_logs.insert_one({
            "id": str(uuid.uuid4()),
            "event_type": "timetable_published",
            "school_id": school_id,
            "timetable_id": version_id,
            "published_by": publisher_info,
            "published_by_name": publisher_name,
            "published_at": now,
            "sessions_count": len(all_sessions),
            "classes_count": len(classes_list),
            "previous_version_ids": previously_published,
            "created_at": now,
        })
    except Exception as e:
        logger.warning(f"Failed to insert publish history for version {version_id}: {e}")

    result_data = {
        "published_at": now,
        "published_by": publisher_info,
        "published_by_name": publisher_name,
        "sessions_count": len(all_sessions),
        "archived_previous": previously_published
    }
    if snapshot_saved:
        result_data["snapshot_id"] = snapshot["id"]

    return {
        "success": True,
        "message": "تم نشر الجدول بنجاح وأصبح هو الجدول الرسمي المعتمد",
        "message_en": "Timetable published successfully",
        "data": result_data
    }


# ─────────────────────────────────────────────
# API 9c: Previous/Archived Timetables
# GET /api/principal/timetable/previous
# ─────────────────────────────────────────────
@router.get("/previous")
async def get_previous_timetables(
    x_school_context: str = Header(default=None, alias="X-School-Context"),
    authorization: str = Header(default=None)
):
    school_id = await get_school_id(x_school_context, authorization)
    if not school_id:
        raise HTTPException(status_code=400, detail="School context required")

    snapshots_map = {}
    async for snap in db.published_timetables.find(
        {"school_id": school_id},
        {"_id": 0, "timetable_id": 1, "published_by_name": 1, "academic_year": 1,
         "academic_term": 1, "sessions_count": 1, "classes_count": 1, "teachers_count": 1,
         "subjects_count": 1, "coverage_percent": 1, "total_slots": 1}
    ):
        snapshots_map[snap.get("timetable_id")] = snap

    cursor = db.timetables.find(
        {"school_id": school_id, "status": "archived"},
        {"_id": 0},
        sort=[("published_at", -1)]
    ).limit(50)

    previous = []
    idx = 0
    async for tt in cursor:
        idx += 1
        tt_id = tt.get("id")
        stats = tt.get("statistics", {})
        snap = snapshots_map.get(tt_id, {})

        sessions_count = (
            snap.get("sessions_count")
            or stats.get("total_sessions")
            or tt.get("sessions_count")
            or 0
        )

        previous.append({
            "id": tt_id,
            "version_number": idx,
            "version_name": tt.get("version_name") or tt.get("name") or f"إصدار {idx}",
            "status": "archived",
            "published_at": tt.get("published_at"),
            "published_by": tt.get("published_by", "غير محدد"),
            "published_by_name": snap.get("published_by_name") or tt.get("published_by_name", "المدير"),
            "archived_at": tt.get("archived_at"),
            "sessions_count": sessions_count,
            "classes_count": snap.get("classes_count", 0),
            "teachers_count": snap.get("teachers_count", 0),
            "subjects_count": snap.get("subjects_count", 0),
            "coverage_percent": snap.get("coverage_percent", 0),
            "academic_year": snap.get("academic_year", ""),
            "academic_term": snap.get("academic_term", ""),
            "quality_score": round(stats.get("optimization_score", 0) or tt.get("quality_score", 0), 1),
            "created_at": tt.get("created_at") or tt.get("generated_at"),
            "has_snapshot": tt_id in snapshots_map,
        })

    return {
        "success": True,
        "data": {
            "previous_timetables": previous,
            "total": len(previous)
        }
    }


@router.get("/previous/{timetable_id}/view")
async def view_previous_timetable(
    timetable_id: str,
    x_school_context: str = Header(default=None, alias="X-School-Context"),
    authorization: str = Header(default=None)
):
    school_id = await get_school_id(x_school_context, authorization)
    if not school_id:
        raise HTTPException(status_code=400, detail="School context required")

    snapshot = await db.published_timetables.find_one(
        {"timetable_id": timetable_id, "school_id": school_id},
        {"_id": 0},
        sort=[("published_at", -1)]
    )

    if snapshot:
        return {
            "success": True,
            "source": "snapshot",
            "data": {
                "id": snapshot.get("id"),
                "timetable_id": timetable_id,
                "version_name": snapshot.get("version_name", ""),
                "published_at": snapshot.get("published_at"),
                "published_by_name": snapshot.get("published_by_name", "المدير"),
                "academic_year": snapshot.get("academic_year", ""),
                "academic_term": snapshot.get("academic_term", ""),
                "working_days": snapshot.get("working_days", []),
                "time_slots": snapshot.get("time_slots", []),
                "break_positions": snapshot.get("break_positions", []),
                "prayer_positions": snapshot.get("prayer_positions", []),
                "classes": snapshot.get("classes", []),
                "teachers": snapshot.get("teachers", []),
                "subjects": snapshot.get("subjects", []),
                "sessions": snapshot.get("sessions", []),
                "sessions_count": snapshot.get("sessions_count", 0),
                "classes_count": snapshot.get("classes_count", 0),
                "teachers_count": snapshot.get("teachers_count", 0),
                "subjects_count": snapshot.get("subjects_count", 0),
                "coverage_percent": snapshot.get("coverage_percent", 0),
            }
        }

    tt = await db.timetables.find_one({"id": timetable_id, "school_id": school_id})
    if not tt:
        raise HTTPException(status_code=404, detail="الجدول غير موجود")

    sessions = await db.timetable_sessions.find(
        {"timetable_id": timetable_id}, {"_id": 0}
    ).to_list(50000)

    school_settings_doc = await db.school_settings.find_one({"school_id": school_id})
    w_days = _resolve_working_days(school_settings_doc.get("working_days") if school_settings_doc else None)

    slots = []
    async for slot in db.time_slots.find({"school_id": school_id}, {"_id": 0}).sort("period_number", 1):
        slots.append(slot)

    teacher_ids = list(set(s.get("teacher_id") for s in sessions if s.get("teacher_id")))
    subject_ids = list(set(s.get("subject_id") for s in sessions if s.get("subject_id")))
    class_ids = list(set(s.get("class_id") for s in sessions if s.get("class_id")))

    teachers_data = await db.teachers.find({"id": {"$in": teacher_ids}}, {"_id": 0, "id": 1, "full_name": 1, "name": 1}).to_list(2000)
    subjects_data = await db.subjects.find({"id": {"$in": subject_ids}}, {"_id": 0, "id": 1, "name": 1, "name_ar": 1, "code": 1}).to_list(500)
    classes_data = await db.classes.find({"id": {"$in": class_ids}}, {"_id": 0, "id": 1, "name": 1, "name_ar": 1, "grade": 1}).to_list(500)

    return {
        "success": True,
        "source": "live",
        "data": {
            "timetable_id": timetable_id,
            "version_name": tt.get("version_name") or tt.get("name", ""),
            "published_at": tt.get("published_at"),
            "published_by_name": tt.get("published_by_name", "المدير"),
            "working_days": w_days,
            "time_slots": slots,
            "classes": classes_data,
            "teachers": teachers_data,
            "subjects": subjects_data,
            "sessions": sessions,
            "sessions_count": len(sessions),
            "classes_count": len(classes_data),
            "teachers_count": len(teachers_data),
            "subjects_count": len(subjects_data),
        }
    }


# ─────────────────────────────────────────────
# API 9d: Empty Slots Details
# GET /api/principal/timetable/version/{id}/empty-slots
# ─────────────────────────────────────────────
@router.get("/version/{version_id}/empty-slots")
async def get_empty_slots_details(
    version_id: str,
    x_school_context: str = Header(default=None, alias="X-School-Context"),
    authorization: str = Header(default=None)
):
    school_id = await get_school_id(x_school_context, authorization)
    if not school_id:
        raise HTTPException(status_code=400, detail="School context required")

    school_settings = await db.school_settings.find_one({"school_id": school_id})
    working_days = _resolve_working_days(school_settings.get("working_days") if school_settings else None)

    time_slots = []
    async for slot in db.time_slots.find({"school_id": school_id}).sort("period_number", 1):
        time_slots.append(slot)
    teaching_slots = [s for s in time_slots if not s.get("is_break") and not s.get("is_prayer")]
    teaching_period_numbers = [s.get("period_number") for s in teaching_slots]

    DAY_NAMES_AR = {"sunday": "الأحد", "monday": "الاثنين", "tuesday": "الثلاثاء", "wednesday": "الأربعاء", "thursday": "الخميس", "saturday": "السبت", "friday": "الجمعة"}

    classes = await db.classes.find({"school_id": school_id}).to_list(500)
    class_map = {c.get("id"): c.get("name") or c.get("name_ar") or c.get("id") for c in classes}

    empty_by_class = {}
    total_empty = 0

    for cls in classes:
        cls_id = cls.get("id")
        cls_name = class_map.get(cls_id, cls_id)
        empty_days = {}

        for day in working_days:
            for pn in teaching_period_numbers:
                has = await db.timetable_sessions.find_one({
                    "timetable_id": version_id,
                    "class_id": cls_id,
                    "day_of_week": day,
                    "period_number": pn
                })
                if not has:
                    if day not in empty_days:
                        empty_days[day] = []
                    empty_days[day].append(pn)
                    total_empty += 1

        if empty_days:
            empty_by_class[cls_id] = {
                "class_name": cls_name,
                "empty_count": sum(len(v) for v in empty_days.values()),
                "days": {DAY_NAMES_AR.get(d, d): periods for d, periods in empty_days.items()}
            }

    sorted_classes = sorted(empty_by_class.values(), key=lambda x: -x["empty_count"])

    return {
        "success": True,
        "data": {
            "total_empty": total_empty,
            "total_classes": len(classes),
            "affected_classes": len(empty_by_class),
            "classes": sorted_classes[:50],
        }
    }


# ─────────────────────────────────────────────
# API 9e: Fill Gaps - Attempt to fill empty slots
# POST /api/principal/timetable/version/{id}/fill-gaps
# ─────────────────────────────────────────────
@router.post("/version/{version_id}/fill-gaps")
async def fill_timetable_gaps(
    version_id: str,
    x_school_context: str = Header(default=None, alias="X-School-Context"),
    authorization: str = Header(default=None)
):
    school_id = await get_school_id(x_school_context, authorization)
    if not school_id:
        raise HTTPException(status_code=400, detail="School context required")

    tt = await db.timetables.find_one({"id": version_id, "school_id": school_id})
    if not tt:
        raise HTTPException(status_code=404, detail="Timetable version not found")

    school_settings = await db.school_settings.find_one({"school_id": school_id})
    working_days = _resolve_working_days(school_settings.get("working_days") if school_settings else None)

    time_slots_raw = []
    async for slot in db.time_slots.find({"school_id": school_id}).sort("period_number", 1):
        time_slots_raw.append(slot)
    teaching_slots = [s for s in time_slots_raw if not s.get("is_break") and not s.get("is_prayer")]
    teaching_period_numbers = [s.get("period_number") for s in teaching_slots]
    slot_lookup = {s.get("period_number"): {"start_time": s.get("start_time", ""), "end_time": s.get("end_time", "")} for s in time_slots_raw}

    classes = await db.classes.find({"school_id": school_id}).to_list(500)
    teachers = await db.teachers.find({"school_id": school_id, "is_active": {"$ne": False}}).to_list(500)
    teacher_map = {t.get("id"): t for t in teachers}
    assignments = await db.teacher_assignments.find({"school_id": school_id}).to_list(5000)

    class_subject_teachers = {}
    for a in assignments:
        cls_id_a = a.get("class_id")
        subj_id_a = a.get("subject_id")
        tid_a = a.get("teacher_id")
        if cls_id_a and subj_id_a and tid_a:
            key = (cls_id_a, subj_id_a)
            if key not in class_subject_teachers:
                class_subject_teachers[key] = set()
            class_subject_teachers[key].add(tid_a)
        elif subj_id_a and tid_a and not cls_id_a:
            for c in classes:
                key = (c.get("id"), subj_id_a)
                if key not in class_subject_teachers:
                    class_subject_teachers[key] = set()
                class_subject_teachers[key].add(tid_a)

    existing_sessions = []
    async for s in db.timetable_sessions.find({"timetable_id": version_id}):
        existing_sessions.append(s)

    for s in existing_sessions:
        s_cls = s.get("class_id")
        s_subj = s.get("subject_id")
        s_tid = s.get("teacher_id")
        if s_cls and s_subj and s_tid:
            key = (s_cls, s_subj)
            if key not in class_subject_teachers:
                class_subject_teachers[key] = set()
            class_subject_teachers[key].add(s_tid)

    teacher_grid = {}
    class_grid = {}
    teacher_weekly_load = {}
    for s in existing_sessions:
        day = s.get("day_of_week")
        period = s.get("period_number")
        tid = s.get("teacher_id")
        cid = s.get("class_id")

        tkey = (day, period)
        if tkey not in teacher_grid:
            teacher_grid[tkey] = set()
        teacher_grid[tkey].add(tid)

        ckey = (cid, day, period)
        class_grid[ckey] = True

        teacher_weekly_load[tid] = teacher_weekly_load.get(tid, 0) + 1

    max_possible_weekly = len(working_days) * len(teaching_period_numbers)
    teacher_max_load = {}
    for t in teachers:
        explicit = t.get("weekly_periods") or t.get("max_weekly_periods")
        teacher_max_load[t.get("id")] = explicit if explicit else max_possible_weekly

    subjects = await db.subjects.find({"school_id": school_id}).to_list(500)
    subject_map = {s.get("id"): s for s in subjects}

    filled_count = 0
    still_empty = 0
    new_sessions = []

    for cls in classes:
        cls_id = cls.get("id")
        grade_id = cls.get("grade_id") or cls.get("grade") or ""

        for day in working_days:
            for pn in teaching_period_numbers:
                if (cls_id, day, pn) in class_grid:
                    continue

                best_teacher = None
                best_subject = None
                best_score = -1

                class_day_subjects = set()
                for p in teaching_period_numbers:
                    if (cls_id, day, p) in class_grid:
                        sess = next((s for s in existing_sessions + new_sessions if s.get("class_id") == cls_id and s.get("day_of_week") == day and s.get("period_number") == p), None)
                        if sess:
                            class_day_subjects.add(sess.get("subject_id"))

                for subj in subjects:
                    subj_id = subj.get("id")
                    possible_teachers = class_subject_teachers.get((cls_id, subj_id), [])

                    for tid in possible_teachers:
                        if (day, pn) in teacher_grid and tid in teacher_grid[(day, pn)]:
                            continue
                        if teacher_weekly_load.get(tid, 0) >= teacher_max_load.get(tid, 30):
                            continue

                        score = 50
                        if subj_id not in class_day_subjects:
                            score += 20
                        load_ratio = teacher_weekly_load.get(tid, 0) / max(teacher_max_load.get(tid, 30), 1)
                        score -= load_ratio * 15

                        if score > best_score:
                            best_score = score
                            best_teacher = tid
                            best_subject = subj_id

                if best_teacher and best_subject:
                    slot_times = slot_lookup.get(pn, {"start_time": "", "end_time": ""})
                    new_session = {
                        "id": str(uuid.uuid4()),
                        "timetable_id": version_id,
                        "school_id": school_id,
                        "class_id": cls_id,
                        "grade_id": grade_id,
                        "subject_id": best_subject,
                        "teacher_id": best_teacher,
                        "day_of_week": day,
                        "period_number": pn,
                        "start_time": slot_times["start_time"],
                        "end_time": slot_times["end_time"],
                        "session_type": "class",
                        "source_type": "ai_gap_fill",
                        "status": "scheduled",
                        "created_at": utcnow(),
                    }
                    new_sessions.append(new_session)

                    tkey = (day, pn)
                    if tkey not in teacher_grid:
                        teacher_grid[tkey] = set()
                    teacher_grid[tkey].add(best_teacher)
                    class_grid[(cls_id, day, pn)] = True
                    teacher_weekly_load[best_teacher] = teacher_weekly_load.get(best_teacher, 0) + 1
                    filled_count += 1
                else:
                    still_empty += 1

    # HARD CONSTRAINT: final class_id + day + period uniqueness check before insert
    safe_sessions = []
    all_occupied = set()
    for s in existing_sessions:
        all_occupied.add((s.get("class_id"), s.get("day_of_week"), s.get("period_number")))
    for ns in new_sessions:
        key = (ns["class_id"], ns["day_of_week"], ns["period_number"])
        if key not in all_occupied:
            safe_sessions.append(ns)
            all_occupied.add(key)
    new_sessions = safe_sessions

    # HARD CONSTRAINT: final teacher_id + day + period uniqueness check before insert
    teacher_safe_sessions = []
    teacher_occupied = set()
    for s in existing_sessions:
        teacher_occupied.add((s.get("teacher_id"), s.get("day_of_week"), s.get("period_number")))
    for ns in new_sessions:
        key = (ns["teacher_id"], ns["day_of_week"], ns["period_number"])
        if key not in teacher_occupied:
            teacher_safe_sessions.append(ns)
            teacher_occupied.add(key)
    new_sessions = teacher_safe_sessions

    if new_sessions:
        await db.timetable_sessions.insert_many(new_sessions)

        total_sessions = await db.timetable_sessions.count_documents({"timetable_id": version_id})
        await db.timetables.update_one(
            {"id": version_id},
            {"$set": {
                "sessions_count": total_sessions,
                "statistics.total_sessions": total_sessions,
                "updated_at": utcnow()
            }}
        )

    return {
        "success": True,
        "message": f"تم ملء {filled_count} خانة فارغة" + (f"، ولا يزال {still_empty} خانة لا يمكن ملؤها بسبب عدم توفر معلمين" if still_empty > 0 else " بنجاح"),
        "data": {
            "filled": filled_count,
            "still_empty": still_empty,
            "total_new_sessions": len(new_sessions),
        }
    }


# ─────────────────────────────────────────────
# API 10: Session Details
# GET /api/principal/timetable/session/{id}
# ─────────────────────────────────────────────
class SwapSessionsRequest(BaseModel):
    session_id_1: str
    session_id_2: str

class MoveSessionRequest(BaseModel):
    session_id: str
    new_day: str
    new_period: int

@router.post("/sessions/swap")
async def swap_sessions(
    data: SwapSessionsRequest,
    x_school_context: str = Header(default=None, alias="X-School-Context"),
    authorization: str = Header(default=None)
):
    school_id = await get_school_id(x_school_context, authorization)
    if not school_id:
        raise HTTPException(status_code=400, detail="School context required")

    s1 = await db.timetable_sessions.find_one({"id": data.session_id_1, "school_id": school_id}, {"_id": 0})
    s2 = await db.timetable_sessions.find_one({"id": data.session_id_2, "school_id": school_id}, {"_id": 0})

    if not s1 or not s2:
        raise HTTPException(status_code=404, detail="One or both sessions not found")

    tt_id_1 = s1.get("timetable_id")
    tt_id_2 = s2.get("timetable_id")
    if tt_id_1 != tt_id_2:
        raise HTTPException(status_code=400, detail="Cannot swap sessions from different timetable versions")

    timetable_id = tt_id_1
    tt = await db.timetables.find_one({"id": timetable_id, "school_id": school_id}, {"_id": 0, "status": 1})
    if tt and tt.get("status") == "published":
        raise HTTPException(status_code=400, detail="Cannot modify a published timetable")

    s1_day = s1.get("day_of_week") or s1.get("day")
    s1_period = s1.get("period_number")
    s1_slot = s1.get("time_slot_id")
    s1_start = s1.get("start_time")
    s1_end = s1.get("end_time")

    s2_day = s2.get("day_of_week") or s2.get("day")
    s2_period = s2.get("period_number")
    s2_slot = s2.get("time_slot_id")
    s2_start = s2.get("start_time")
    s2_end = s2.get("end_time")

    exclude_ids = [data.session_id_1, data.session_id_2]

    s1_teacher_conflict = await db.timetable_sessions.find_one({
        "timetable_id": timetable_id, "school_id": school_id,
        "teacher_id": s1.get("teacher_id"),
        "day_of_week": s2_day, "period_number": s2_period,
        "id": {"$nin": exclude_ids}
    })
    if s1_teacher_conflict:
        raise HTTPException(status_code=409, detail=f"تعارض: المعلم {s1.get('teacher_name', '')} لديه حصة أخرى في الخانة المستهدفة")

    s1_class_conflict = await db.timetable_sessions.find_one({
        "timetable_id": timetable_id, "school_id": school_id,
        "class_id": s1.get("class_id"),
        "day_of_week": s2_day, "period_number": s2_period,
        "id": {"$nin": exclude_ids}
    })
    if s1_class_conflict:
        raise HTTPException(status_code=409, detail=f"تعارض: الفصل {s1.get('class_name', '')} لديه حصة أخرى في الخانة المستهدفة")

    s2_teacher_conflict = await db.timetable_sessions.find_one({
        "timetable_id": timetable_id, "school_id": school_id,
        "teacher_id": s2.get("teacher_id"),
        "day_of_week": s1_day, "period_number": s1_period,
        "id": {"$nin": exclude_ids}
    })
    if s2_teacher_conflict:
        raise HTTPException(status_code=409, detail=f"تعارض: المعلم {s2.get('teacher_name', '')} لديه حصة أخرى في الخانة المستهدفة")

    s2_class_conflict = await db.timetable_sessions.find_one({
        "timetable_id": timetable_id, "school_id": school_id,
        "class_id": s2.get("class_id"),
        "day_of_week": s1_day, "period_number": s1_period,
        "id": {"$nin": exclude_ids}
    })
    if s2_class_conflict:
        raise HTTPException(status_code=409, detail=f"تعارض: الفصل {s2.get('class_name', '')} لديه حصة أخرى في الخانة المستهدفة")

    now = utcnow()
    await db.timetable_sessions.update_one(
        {"id": data.session_id_1, "school_id": school_id, "timetable_id": timetable_id},
        {"$set": {
            "day_of_week": s2_day, "day": s2_day,
            "period_number": s2_period,
            "time_slot_id": s2_slot,
            "start_time": s2_start, "end_time": s2_end,
            "source_type": "manual_adjusted",
            "updated_at": now
        }}
    )
    await db.timetable_sessions.update_one(
        {"id": data.session_id_2, "school_id": school_id, "timetable_id": timetable_id},
        {"$set": {
            "day_of_week": s1_day, "day": s1_day,
            "period_number": s1_period,
            "time_slot_id": s1_slot,
            "start_time": s1_start, "end_time": s1_end,
            "source_type": "manual_adjusted",
            "updated_at": now
        }}
    )

    return {
        "success": True,
        "message": "تم تبديل الحصتين بنجاح",
        "data": {
            "session_1": {"id": data.session_id_1, "new_day": s2_day, "new_period": s2_period},
            "session_2": {"id": data.session_id_2, "new_day": s1_day, "new_period": s1_period}
        }
    }


@router.post("/sessions/move")
async def move_session(
    data: MoveSessionRequest,
    x_school_context: str = Header(default=None, alias="X-School-Context"),
    authorization: str = Header(default=None)
):
    school_id = await get_school_id(x_school_context, authorization)
    if not school_id:
        raise HTTPException(status_code=400, detail="School context required")

    session = await db.timetable_sessions.find_one({"id": data.session_id, "school_id": school_id}, {"_id": 0})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    tt = await db.timetables.find_one({"id": session.get("timetable_id"), "school_id": school_id}, {"_id": 0, "status": 1})
    if tt and tt.get("status") == "published":
        raise HTTPException(status_code=400, detail="Cannot modify a published timetable")

    teacher_id = session.get("teacher_id")
    class_id = session.get("class_id")
    timetable_id = session.get("timetable_id")

    teacher_conflict = await db.timetable_sessions.find_one({
        "timetable_id": timetable_id, "school_id": school_id,
        "teacher_id": teacher_id,
        "day_of_week": data.new_day,
        "period_number": data.new_period,
        "id": {"$ne": data.session_id}
    })

    class_conflict = await db.timetable_sessions.find_one({
        "timetable_id": timetable_id, "school_id": school_id,
        "class_id": class_id,
        "day_of_week": data.new_day,
        "period_number": data.new_period,
        "id": {"$ne": data.session_id}
    })

    if teacher_conflict:
        t_name = teacher_conflict.get("teacher_name", "")
        raise HTTPException(status_code=409, detail=f"تعارض: المعلم {t_name} لديه حصة في نفس الوقت")

    if class_conflict:
        c_name = class_conflict.get("class_name", "")
        raise HTTPException(status_code=409, detail=f"تعارض: الفصل {c_name} لديه حصة في نفس الوقت")

    slot = await db.time_slots.find_one({
        "school_id": school_id,
        "period_number": data.new_period,
        "type": {"$nin": ["break", "prayer"]}
    }, {"_id": 0})
    if not slot:
        all_slots = []
        async for ts in db.time_slots.find({"school_id": school_id}, {"_id": 0}):
            all_slots.append(ts)
        all_slots.sort(key=lambda x: x.get("start_time") or "99:99")
        teaching_counter = 0
        for ts in all_slots:
            ts_type = ts.get("type", "period")
            if ts_type not in ("break", "prayer") and not ts.get("is_break") and not ts.get("is_prayer"):
                teaching_counter += 1
                if teaching_counter == data.new_period:
                    slot = ts
                    break

    if not slot:
        raise HTTPException(status_code=400, detail="الخانة المستهدفة ليست حصة دراسية صالحة")

    update_fields = {
        "day_of_week": data.new_day,
        "day": data.new_day,
        "period_number": data.new_period,
        "time_slot_id": slot.get("id"),
        "start_time": slot.get("start_time"),
        "end_time": slot.get("end_time"),
        "source_type": "manual_adjusted",
        "updated_at": utcnow()
    }

    await db.timetable_sessions.update_one(
        {"id": data.session_id, "school_id": school_id, "timetable_id": timetable_id},
        {"$set": update_fields}
    )

    return {
        "success": True,
        "message": "تم نقل الحصة بنجاح",
        "data": {"session_id": data.session_id, "new_day": data.new_day, "new_period": data.new_period}
    }


@router.get("/session/{session_id}")
async def get_session_details(
    session_id: str,
    x_school_context: str = Header(default=None, alias="X-School-Context"),
    authorization: str = Header(default=None)
):
    school_id = await get_school_id(x_school_context, authorization)
    if not school_id:
        raise HTTPException(status_code=400, detail="School context required")

    session = await db.timetable_sessions.find_one({"id": session_id}, {"_id": 0})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return {"success": True, "data": {"session": session}}
