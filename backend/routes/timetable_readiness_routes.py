"""
Timetable Readiness Engine Routes — 6-Phase Sequential Flow
نظام التحقق من جاهزية إعدادات المدرسة لإنشاء الجدول — 6 مراحل متسلسلة

Phase 1: Time Structure (working days, periods, time slots)
Phase 2: Academic Entities (classes, subjects, grade-subject links)
Phase 3: Teaching Staff (teachers registered, workload defined)
Phase 4: Teaching Relationships (teacher↔subject, class↔subject assignments)
Phase 5: Constraints & Validation (hard + soft constraints check)
Phase 6: Generation Ready (capacity check, load balance)
"""

from fastapi import APIRouter, HTTPException, Depends, Header
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from datetime import datetime, timezone
from enum import Enum
import asyncio
import time as _time
import logging, os
from engines.sql_utils import gd_find, gd_find_one, gd_insert, gd_insert_many, gd_update_one, gd_update_many, gd_count, gd_delete_one, gd_delete_many, gd_distinct, _gd_aggregate
from dependencies import get_current_user
from utils.tenant_scope import resolve_school_id


logger = logging.getLogger("nassaq.timetable_readiness_routes")

router = APIRouter(prefix="/timetable-readiness", tags=["Timetable Readiness"])


async def readiness_school_id(
    x_school_context: Optional[str] = Header(None, alias="X-School-Context"),
    current_user: dict = Depends(get_current_user),
) -> str:
    resolved = resolve_school_id(current_user, x_school_context)
    if resolved is None:
        raise HTTPException(status_code=400, detail="X-School-Context header is required for platform admin")
    return resolved

db = None

def set_database(database):
    global db
    db = database


class ReadinessStatus(str, Enum):
    NOT_READY = "NOT_READY"
    PARTIALLY_READY = "PARTIALLY_READY"
    FULLY_READY = "FULLY_READY"


class IssueType(str, Enum):
    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"


class ReadinessIssue(BaseModel):
    id: str
    type: IssueType
    category: str
    message_ar: str
    message_en: str
    fix_link: Optional[str] = None
    fix_action: Optional[str] = None
    affected_items: Optional[List[str]] = None


class CategoryReadiness(BaseModel):
    name_ar: str
    name_en: str
    score: int
    max_score: int
    status: str
    issues: List[ReadinessIssue]


def _parse_working_days_from_settings(settings):
    working_days = settings.get("working_days", {})
    if isinstance(working_days, dict) and working_days:
        result = [k for k, v in working_days.items() if v]
        if result:
            return result

    work_days = settings.get("work_days", {})
    if isinstance(work_days, dict) and work_days:
        result = [k for k, v in work_days.items() if v]
        if result:
            return result

    ar_to_en = {
        'الأحد': 'sunday', 'الإثنين': 'monday', 'الاثنين': 'monday',
        'الثلاثاء': 'tuesday', 'الأربعاء': 'wednesday',
        'الخميس': 'thursday', 'الجمعة': 'friday', 'السبت': 'saturday'
    }
    working_days_ar = settings.get("working_days_ar", [])
    if isinstance(working_days_ar, list) and working_days_ar:
        return [ar_to_en.get(d, d) for d in working_days_ar if ar_to_en.get(d, d)]

    nested = settings.get("settings", {})
    if isinstance(nested, dict):
        for key in ("working_days", "work_days"):
            nested_val = nested.get(key, {})
            if isinstance(nested_val, dict) and nested_val:
                result = [k for k, v in nested_val.items() if v]
                if result:
                    return result

    return []


# ── In-memory TTL cache + single-flight lock ────────────────────────────────
# The readiness function issues ~15 sequential DB queries on a shared session
# (~3s/call). It is called by both `/principal/timetable/readiness` and
# `/timetable-readiness/check`, often nearly simultaneously on page load.
# We cache its result per school for a short window to keep the page snappy.
_READINESS_TTL_SEC = 30.0
_readiness_cache: Dict[str, tuple] = {}            # school_id -> (expires_at, payload)
_readiness_locks: Dict[str, asyncio.Lock] = {}     # school_id -> single-flight lock


def invalidate_readiness_cache(school_id: Optional[str] = None) -> None:
    """Drop cached readiness result(s). Called by mutating endpoints if needed."""
    if school_id is None:
        _readiness_cache.clear()
    else:
        _readiness_cache.pop(school_id, None)


async def _run_readiness_checks(school_id: str):
    now = _time.monotonic()
    cached = _readiness_cache.get(school_id)
    if cached and cached[0] > now:
        return cached[1]

    lock = _readiness_locks.setdefault(school_id, asyncio.Lock())
    async with lock:
        # Re-check after acquiring the lock — another waiter may have populated it.
        cached = _readiness_cache.get(school_id)
        now = _time.monotonic()
        if cached and cached[0] > now:
            return cached[1]
        result = await _run_readiness_checks_impl(school_id)
        _readiness_cache[school_id] = (now + _READINESS_TTL_SEC, result)
        return result


async def _run_readiness_checks_impl(school_id: str):
    settings = await gd_find_one(db.session, "school_settings", {"school_id": school_id}) or {}

    active_days = _parse_working_days_from_settings(settings)
    periods_per_day = settings.get("periods_per_day") or settings.get("periodsPerDay") or 0
    period_duration = settings.get("period_duration") or settings.get("periodDuration") or 0
    day_start = (settings.get("school_day_start") or settings.get("day_start") or
                 settings.get("dayStart") or settings.get("start_time") or "")
    custom = settings.get("custom_settings") or {}
    if isinstance(custom, dict):
        academic_year = (settings.get("academic_year") or settings.get("academicYear") or
                         custom.get("academic_year") or custom.get("academicYear") or "")
        current_semester = (settings.get("current_semester") or settings.get("currentSemester") or
                            custom.get("current_semester") or custom.get("currentSemester") or "")
    else:
        academic_year = settings.get("academic_year") or settings.get("academicYear") or ""
        current_semester = settings.get("current_semester") or settings.get("currentSemester") or ""

    if not academic_year:
        cur_year_row = await gd_find_one(db.session, "academic_years", {"school_id": school_id, "is_current": True})
        if cur_year_row:
            academic_year = cur_year_row.get("name") or cur_year_row.get("id") or ""
    if not current_semester:
        cur_term_row = await gd_find_one(db.session, "terms", {"school_id": school_id, "is_current": True})
        if cur_term_row:
            current_semester = cur_term_row.get("name") or cur_term_row.get("id") or ""

    ts_count = await gd_count(db.session, "time_slots", {"school_id": school_id, "type": {"$ne": "break"}})
    classes_count = await gd_count(db.session, "classes", {"school_id": school_id, "is_active": {"$ne": False}})
    teachers_count = await gd_count(db.session, "users", {"school_id": school_id, "role": "teacher", "is_active": {"$ne": False}})
    subjects_count = await gd_count(db.session, "subjects", {"school_id": school_id})
    teacher_subject_count = await gd_count(db.session, "teacher_assignments", {"school_id": school_id})
    if teacher_subject_count == 0:
        teacher_subject_count = await gd_count(db.session, "teacher_subjects", {"school_id": school_id})
    class_subject_count = await gd_count(db.session, "teacher_assignments", {"school_id": school_id})
    if class_subject_count == 0:
        class_subject_count = await gd_count(db.session, "class_subjects", {"school_id": school_id})
    grade_subject_count = await gd_count(db.session, "grade_subjects", {"school_id": school_id})

    phases = {}
    all_issues = []

    def add_phase(key, phase_number, name_ar, name_en, score, max_score, issues, blocked_by=None):
        if score >= max_score:
            st = "complete"
        elif score == 0:
            st = "not_started"
        else:
            st = "partial"

        is_blocked = False
        if blocked_by:
            for dep_key in blocked_by:
                dep = phases.get(dep_key)
                if dep and dep["status"] == "not_started":
                    is_blocked = True
                    break

        if is_blocked:
            st = "blocked"

        phase = {
            "phase": phase_number,
            "key": key,
            "name_ar": name_ar,
            "name_en": name_en,
            "score": min(score, max_score),
            "max_score": max_score,
            "status": st,
            "issues": [i.dict() for i in issues],
            "blocked_by": blocked_by or []
        }
        phases[key] = phase
        all_issues.extend(issues)

    # ─── PHASE 1: Time Structure ───
    p1_score, p1_issues = 0, []
    if len(active_days) >= 1:
        p1_score += 5
        if len(active_days) >= 5:
            p1_score += 3
    else:
        p1_issues.append(ReadinessIssue(id="no-working-days", type=IssueType.CRITICAL, category="time_structure",
            message_ar="لم يتم تحديد أيام الدراسة", message_en="Working days not configured",
            fix_link="/school/settings?tab=timings", fix_action="تحديد أيام الدراسة"))

    if periods_per_day >= 1:
        p1_score += 5
    else:
        p1_issues.append(ReadinessIssue(id="no-periods", type=IssueType.CRITICAL, category="time_structure",
            message_ar="لم يتم تحديد عدد الحصص اليومية", message_en="Periods per day not set",
            fix_link="/school/settings?tab=time", fix_action="تحديد عدد الحصص"))

    if period_duration >= 30:
        p1_score += 4
    else:
        p1_issues.append(ReadinessIssue(id="no-duration", type=IssueType.CRITICAL, category="time_structure",
            message_ar="لم يتم تحديد مدة الحصة", message_en="Period duration not set",
            fix_link="/school/settings?tab=time", fix_action="تحديد مدة الحصة"))

    if day_start:
        p1_score += 3
    else:
        p1_issues.append(ReadinessIssue(id="no-day-start", type=IssueType.WARNING, category="time_structure",
            message_ar="لم يتم تحديد وقت بداية اليوم الدراسي", message_en="Day start time not set",
            fix_link="/school/settings?tab=time", fix_action="تحديد وقت البداية"))

    if academic_year:
        p1_score += 3
    else:
        p1_issues.append(ReadinessIssue(id="no-academic-year", type=IssueType.CRITICAL, category="time_structure",
            message_ar="لم يتم تحديد العام الدراسي الحالي — يرجى تعيين عام دراسي كعام حالي",
            message_en="No active academic year set",
            fix_link="/academic-structure", fix_action="تحديد العام الدراسي"))

    if current_semester:
        p1_score += 2
    else:
        p1_issues.append(ReadinessIssue(id="no-semester", type=IssueType.CRITICAL, category="time_structure",
            message_ar="لم يتم تحديد الفصل الدراسي الحالي — يرجى تعيين فصل دراسي كفصل حالي",
            message_en="No active semester/term set",
            fix_link="/academic-structure", fix_action="تحديد الفصل الدراسي"))

    add_phase("time_structure", 1, "الهيكل الزمني", "Time Structure", p1_score, 25, p1_issues)

    # ─── PHASE 2: Academic Entities ───
    p2_score, p2_issues = 0, []
    if classes_count >= 1:
        p2_score += 8
        if classes_count >= 5:
            p2_score += 2
    else:
        p2_issues.append(ReadinessIssue(id="no-classes", type=IssueType.CRITICAL, category="academic_entities",
            message_ar="لا يوجد فصول دراسية", message_en="No classes registered",
            fix_link="/school/classes", fix_action="إضافة الفصول"))

    if subjects_count >= 1:
        p2_score += 8
    else:
        p2_issues.append(ReadinessIssue(id="no-subjects", type=IssueType.CRITICAL, category="academic_entities",
            message_ar="لا يوجد مواد دراسية", message_en="No subjects registered",
            fix_link="/school/subjects", fix_action="إضافة المواد"))

    if grade_subject_count >= 1 or class_subject_count >= 1:
        p2_score += 7
    else:
        p2_issues.append(ReadinessIssue(id="no-grade-subject-links", type=IssueType.CRITICAL, category="academic_entities",
            message_ar="لم يتم ربط المواد بالصفوف أو الفصول", message_en="No grade/class subject links",
            fix_link="/school/settings?tab=curriculum", fix_action="ربط المواد بالصفوف"))

    add_phase("academic_entities", 2, "الكيانات الأكاديمية", "Academic Entities", p2_score, 25, p2_issues, blocked_by=["time_structure"])

    # ─── PHASE 3: Teaching Staff ───
    p3_score, p3_issues = 0, []
    if teachers_count >= 1:
        p3_score += 10
        if teachers_count >= 5:
            p3_score += 3
        if teachers_count >= 10:
            p3_score += 2
    else:
        p3_issues.append(ReadinessIssue(id="no-teachers", type=IssueType.CRITICAL, category="teaching_staff",
            message_ar="لا يوجد معلمين مسجلين", message_en="No teachers registered",
            fix_link="/school/teachers", fix_action="إضافة المعلمين"))

    add_phase("teaching_staff", 3, "الكادر التعليمي", "Teaching Staff", p3_score, 15, p3_issues, blocked_by=["academic_entities"])

    # ─── PHASE 4: Teaching Relationships ───
    p4_score, p4_issues = 0, []
    if teacher_subject_count >= 1:
        p4_score += 10
    else:
        p4_issues.append(ReadinessIssue(id="no-teacher-subjects", type=IssueType.CRITICAL, category="teaching_relationships",
            message_ar="لا يوجد إسنادات للمعلمين بالمواد", message_en="No teacher-subject assignments",
            fix_link="/school/teachers", fix_action="ربط المعلمين بالمواد"))

    if class_subject_count >= 1:
        p4_score += 5
    else:
        p4_issues.append(ReadinessIssue(id="no-class-subjects", type=IssueType.WARNING, category="teaching_relationships",
            message_ar="لم يتم ربط المواد بالفصول", message_en="No class-subject assignments",
            fix_link="/school/settings?tab=curriculum", fix_action="ربط المواد بالفصول"))

    if teacher_subject_count >= classes_count and classes_count > 0:
        p4_score += 5
    elif classes_count > 0:
        unlinked_ratio = max(0, classes_count - teacher_subject_count) / classes_count
        if unlinked_ratio > 0.5:
            p4_issues.append(ReadinessIssue(id="low-teacher-coverage", type=IssueType.WARNING, category="teaching_relationships",
                message_ar=f"تغطية المعلمين للفصول منخفضة ({teacher_subject_count}/{classes_count})",
                message_en=f"Low teacher-class coverage ({teacher_subject_count}/{classes_count})",
                fix_link="/school/teachers", fix_action="زيادة إسنادات المعلمين"))
        else:
            p4_score += 3

    add_phase("teaching_relationships", 4, "علاقات التدريس", "Teaching Relationships", p4_score, 20, p4_issues, blocked_by=["teaching_staff"])

    # ─── PHASE 5: Constraints & Validation ───
    p5_score, p5_issues = 0, []
    # Count constraints that apply to this school: those scoped explicitly to
    # the school, plus system/global rows (school_id missing or marked system).
    _scope_filter = {"$or": [
        {"school_id": school_id},
        {"is_system": True},
        {"school_id": None},
        {"school_id": {"$exists": False}},
    ]}
    hard_count = await gd_count(db.session, "timetable_hard_constraints", {"is_active": True, **_scope_filter})
    soft_count = await gd_count(db.session, "timetable_soft_constraints", {"is_active": True, **_scope_filter})

    if hard_count > 0:
        p5_score += 4
    else:
        p5_issues.append(ReadinessIssue(id="no-hard-constraints", type=IssueType.WARNING, category="constraints",
            message_ar="لا توجد قيود إلزامية مفعّلة", message_en="No active hard constraints",
            fix_link="/school/settings?tab=constraints", fix_action="مراجعة القيود الإلزامية"))

    if soft_count > 0:
        p5_score += 3
    else:
        p5_issues.append(ReadinessIssue(id="no-soft-constraints", type=IssueType.INFO, category="constraints",
            message_ar="لا توجد قيود تفضيلية مفعّلة", message_en="No active soft constraints",
            fix_link="/school/settings?tab=constraints", fix_action="مراجعة القيود التفضيلية"))

    if ts_count >= (periods_per_day or 1):
        p5_score += 3
    else:
        p5_issues.append(ReadinessIssue(id="incomplete-time-slots", type=IssueType.INFO, category="constraints",
            message_ar="سيتم توليد الفترات الزمنية تلقائياً عند الإنشاء", message_en="Time slots will be auto-generated",
            fix_link="/school/settings?tab=time", fix_action="تحديد الفترات الزمنية"))

    add_phase("constraints", 5, "القيود والتحقق", "Constraints & Validation", p5_score, 10, p5_issues, blocked_by=["teaching_relationships"])

    # ─── PHASE 6: Generation Ready ───
    p6_score, p6_issues = 0, []

    total_available_slots = len(active_days) * periods_per_day * classes_count if periods_per_day and classes_count else 0

    total_required = 0
    ta_list = await gd_find(db.session, "teacher_assignments", {"school_id": school_id}, limit=5000) if teacher_subject_count > 0 else []
    if ta_list:
        seen_class_subject = set()
        for ta in ta_list:
            cs_key = (str(ta.get("class_id", "")), str(ta.get("subject_id", "") or ta.get("subject_name", "")))
            if cs_key not in seen_class_subject:
                seen_class_subject.add(cs_key)
                total_required += ta.get("weekly_sessions") or ta.get("periods_per_week") or ta.get("weekly_periods") or 4
    elif class_subject_count > 0:
        cs_list = await gd_find(db.session, "class_subjects", {"school_id": school_id})
        for cs in cs_list:
            total_required += cs.get("weekly_periods") or cs.get("weekly_sessions") or 4
    elif grade_subject_count > 0:
        gs_list = await gd_find(db.session, "grade_subjects", {"school_id": school_id})
        for gs in gs_list:
            total_required += gs.get("weekly_periods") or gs.get("periods_per_week") or 4

    if total_available_slots > 0:
        if total_required <= total_available_slots:
            p6_score += 3
        else:
            deficit = total_required - total_available_slots
            suggestion = f"يرجى تقليل عدد الحصص المطلوبة بمقدار {deficit} حصة أو زيادة عدد الحصص اليومية أو أيام الدراسة"
            p6_issues.append(ReadinessIssue(
                id="capacity-overflow", type=IssueType.WARNING, category="generation_ready",
                message_ar=f"الحصص المطلوبة ({total_required}) أكثر من المتاحة ({total_available_slots})\n{suggestion}",
                message_en=f"Required periods ({total_required}) exceed available slots ({total_available_slots}). Reduce required periods by {deficit} or increase daily periods/working days.",
                fix_link="/school/settings?tab=curriculum", fix_action="مراجعة توزيع المواد"))

    ta_agg_results = await _gd_aggregate(db.session, "teacher_assignments", [
        {"$match": {"school_id": school_id}},
        {"$group": {"_id": "$teacher_id", "total": {"$sum": {"$ifNull": ["$weekly_sessions", 4]}}}}
    ])
    overloaded_teachers = []
    max_load = 24
    for ta in ta_agg_results:
        if not ta["_id"]:
            continue
        if ta["total"] > max_load:
            teacher_user = await gd_find_one(db.session, "users", {"id": ta["_id"], "school_id": school_id, "role": "teacher"})
            if not teacher_user:
                teacher_user = await gd_find_one(db.session, "teachers", {"id": ta["_id"], "school_id": school_id})
            t_name = (teacher_user.get("name_ar") or teacher_user.get("full_name") or teacher_user.get("name") or str(ta["_id"])[:8]) if teacher_user else str(ta["_id"])[:8]
            overloaded_teachers.append({"id": str(ta["_id"]), "name": t_name, "load": ta["total"], "max": max_load})

    if overloaded_teachers:
        for idx, t in enumerate(overloaded_teachers[:3]):
            excess = t["load"] - t["max"]
            p6_issues.append(ReadinessIssue(
                id=f"teacher-overload-{idx+1}", type=IssueType.WARNING, category="generation_ready",
                message_ar=f"المعلم ({t['name']}) حمله ({t['load']}) حصة يتجاوز الحد الأقصى ({t['max']})\nيرجى تقليل {excess} حصة من نصاب هذا المعلم أو توزيعها على معلمين آخرين",
                message_en=f"Teacher ({t['name']}) load ({t['load']}) exceeds max ({t['max']}). Reduce {excess} sessions or redistribute.",
                fix_link="/school/settings?section=dynamic&tab=assignments", fix_action="مراجعة نصاب المعلم"))

    if teachers_count > 0 and classes_count > 0:
        total_teacher_capacity = teachers_count * max_load
        if total_required > total_teacher_capacity:
            shortage = total_required - total_teacher_capacity
            needed_teachers = max(1, shortage // max_load + (1 if shortage % max_load > 0 else 0))
            p6_issues.append(ReadinessIssue(
                id="teacher-capacity-shortage", type=IssueType.WARNING, category="generation_ready",
                message_ar=f"سعة المعلمين ({total_teacher_capacity} حصة) لا تكفي للطلب ({total_required} حصة)\nيرجى إضافة {needed_teachers} معلم على الأقل لتغطية العجز",
                message_en=f"Teacher capacity ({total_teacher_capacity}) insufficient for demand ({total_required}). Add at least {needed_teachers} teacher(s).",
                fix_link="/school/teachers", fix_action="إضافة معلمين"))

    all_phases_ready = all(p["status"] in ("complete", "partial") for k, p in phases.items() if k != "generation_ready")
    if all_phases_ready:
        p6_score += 2

    add_phase("generation_ready", 6, "جاهز للإنشاء", "Generation Ready", p6_score, 5, p6_issues, blocked_by=["constraints"])

    total_score = sum(p["score"] for p in phases.values())
    max_score = sum(p["max_score"] for p in phases.values())
    percentage = round((total_score / max_score) * 100, 1) if max_score > 0 else 0

    critical_issues = [i for i in all_issues if i.type == IssueType.CRITICAL]
    warnings = [i for i in all_issues if i.type == IssueType.WARNING]
    info_items = [i for i in all_issues if i.type == IssueType.INFO]

    has_critical = len(critical_issues) > 0
    any_blocked = any(p["status"] == "blocked" for p in phases.values())

    if has_critical or any_blocked:
        status = ReadinessStatus.NOT_READY
        can_generate = False
    elif len(warnings) > 0:
        status = ReadinessStatus.PARTIALLY_READY
        can_generate = True
    else:
        status = ReadinessStatus.FULLY_READY
        can_generate = True

    current_phase = 1
    for i in range(1, 7):
        phase_obj = [p for p in phases.values() if p["phase"] == i]
        if phase_obj and phase_obj[0]["status"] in ("complete",):
            current_phase = i + 1
        else:
            break
    current_phase = min(current_phase, 6)

    return {
        "status": status.value,
        "overall_score": total_score,
        "max_score": max_score,
        "percentage": percentage,
        "current_phase": current_phase,
        "total_phases": 6,
        "phases": {key: phase for key, phase in phases.items()},
        "categories": {key: {
            "name_ar": phase["name_ar"],
            "name_en": phase["name_en"],
            "score": phase["score"],
            "max_score": phase["max_score"],
            "status": phase["status"],
            "issues": phase["issues"]
        } for key, phase in phases.items()},
        "critical_issues": [i.dict() for i in critical_issues],
        "warnings": [i.dict() for i in warnings],
        "info_items": [i.dict() for i in info_items],
        "can_generate": can_generate,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "total_issues": len(all_issues),
            "critical_count": len(critical_issues),
            "warning_count": len(warnings),
            "info_count": len(info_items)
        },
        "capacity": {
            "total_available_slots": total_available_slots,
            "total_required_periods": total_required,
            "utilization_pct": round((total_required / total_available_slots) * 100, 1) if total_available_slots > 0 else 0
        }
    }


@router.get("/check")
async def check_timetable_readiness(
    school_id: str = Depends(readiness_school_id),
):
    return await _run_readiness_checks(school_id)


@router.get("/summary")
async def get_readiness_summary(
    school_id: str = Depends(readiness_school_id),
):
    full_report = await _run_readiness_checks(school_id)

    status_messages = {
        "NOT_READY": {"ar": "النظام غير جاهز لإنشاء الجدول", "en": "System not ready for timetable generation", "color": "red", "icon": "x-circle"},
        "PARTIALLY_READY": {"ar": "النظام جاهز جزئياً - يمكن المتابعة مع تحذيرات", "en": "Partially ready - can proceed with warnings", "color": "yellow", "icon": "alert-triangle"},
        "FULLY_READY": {"ar": "النظام جاهز بالكامل لإنشاء الجدول", "en": "System fully ready for timetable generation", "color": "green", "icon": "check-circle"}
    }

    status_info = status_messages.get(full_report["status"], status_messages["NOT_READY"])

    return {
        "status": full_report["status"],
        "status_message_ar": status_info["ar"],
        "status_message_en": status_info["en"],
        "status_color": status_info["color"],
        "status_icon": status_info["icon"],
        "percentage": full_report["percentage"],
        "current_phase": full_report["current_phase"],
        "total_phases": 6,
        "can_generate": full_report["can_generate"],
        "critical_count": full_report["summary"]["critical_count"],
        "warning_count": full_report["summary"]["warning_count"],
        "capacity": full_report.get("capacity", {})
    }
