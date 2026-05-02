"""
NASSAQ Scheduling Sub-module
"""
from fastapi import APIRouter, HTTPException, Depends, status, Header, Query, Body, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import Response
from starlette.responses import StreamingResponse
from pydantic import BaseModel, Field, ConfigDict, EmailStr, model_validator
from typing import List, Optional, Any, Dict
from datetime import datetime, timezone, timedelta
import uuid, os, logging, json, random, re, io, base64

logger = logging.getLogger("nassaq.scheduling")

from dependencies import (
    db, get_current_user, require_roles, UserRole, SchoolStatus,
    hash_password, verify_password, create_access_token,
    JWT_SECRET, JWT_ALGORITHM, ACCESS_TOKEN_EXPIRE, security,
    audit_engine, AuditAction, AuditSeverity,
    smart_scheduling_engine, TimetableRunStatus, TimetableStatus,
    ConflictType, ConflictSeverity, PreValidationResult, GenerationResult,
    hakim_engine, reporting_engine, export_engine, session_engine,
    REPORT_TYPES, generate_student_qr_code
)
from engines.sql_utils import gd_find, gd_find_one, gd_insert, gd_insert_many, gd_update_one, gd_update_many, gd_count, gd_delete_one, gd_delete_many, gd_distinct
from utils.tenant_scope import assert_school_access, resolve_school_id
from routes._publish_gate import assert_publishable


from shared_models import (
    StatusCheck, StatusCheckCreate, TeacherRankEnum, SessionStatusEnum, ScheduleStatusEnum, TimeSlotCreate, TimeSlotResponse, TeacherAssignmentCreate, TeacherAssignmentResponse, SchoolScheduleCreate, SchoolScheduleResponse, ScheduleSessionCreate, ScheduleSessionResponse
)

router = APIRouter()

# ============== SMART SCHEDULING ENGINE APIs ==============

# --- Models for Smart Scheduling ---
class SmartTimetableGenerateRequest(BaseModel):
    """طلب توليد الجدول الذكي"""
    academic_year_id: Optional[str] = None
    term_id: Optional[str] = None


class SmartValidationResponse(BaseModel):
    """استجابة التحقق من جاهزية البيانات"""
    is_valid: bool
    can_proceed: bool
    issues: List[dict] = []
    summary: dict = {}


class SmartTimetableResponse(BaseModel):
    """استجابة الجدول"""
    model_config = ConfigDict(extra="ignore")
    id: str
    school_id: str
    name: str
    status: str
    is_published: bool
    version_number: int = 1
    created_at: str
    statistics: dict = {}


class SmartTimetableSessionResponse(BaseModel):
    """استجابة حصة في الجدول"""
    model_config = ConfigDict(extra="ignore")
    id: str
    timetable_id: str
    class_id: str
    grade_id: Optional[str] = None
    subject_id: str
    teacher_id: str
    day_of_week: str
    period_number: int
    start_time: str
    end_time: str
    session_type: str = "class"
    source_type: str = "ai_generated"
    status: str = "scheduled"


# --- Pre-Validation API ---
@router.get("/smart-scheduling/validate/{school_id}")
async def smart_validate_data_readiness(
    school_id: str,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN]))
):
    """
    التحقق من جاهزية البيانات قبل توليد الجدول
    Phase 1: Validate data readiness before timetable generation
    
    يتحقق من:
    - المدرسة والعام الدراسي
    - المراحل والصفوف والفصول
    - المواد الدراسية والإسنادات
    - المعلمين والتوافر
    - إعدادات اليوم الدراسي
    - القيود الإدارية
    """
    assert_school_access(current_user, str(school_id))
    result = await smart_scheduling_engine.validate_data_readiness(school_id)
    
    return {
        "school_id": school_id,
        "is_valid": result.is_valid,
        "can_proceed": result.can_proceed,
        "issues": [i.model_dump() for i in result.issues],
        "summary": result.summary,
        "message_ar": "البيانات جاهزة للجدولة" if result.is_valid else f"يوجد {len(result.issues)} مشكلة تحتاج للمعالجة",
        "message_en": "Data is ready for scheduling" if result.is_valid else f"There are {len(result.issues)} issues that need attention"
    }


# --- Generate Timetable API ---
@router.post("/smart-scheduling/generate/{school_id}")
async def smart_generate_timetable(
    school_id: str,
    request: SmartTimetableGenerateRequest = None,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN]))
):
    """
    توليد الجدول الدراسي بالذكاء الاصطناعي
    Smart AI-Powered Timetable Generation
    
    المراحل:
    1. التحقق من جاهزية البيانات
    2. تحميل إعدادات المدرسة
    3. بناء مصفوفة الطلب الأكاديمي
    4. بناء مصفوفة الموارد المتاحة
    5. التحقق المسبق من التعارضات
    6. توليد مسودة الجدول
    7. اكتشاف التعارضات
    8. تحسين الجدول
    """
    assert_school_access(current_user, str(school_id))
    request = request or SmartTimetableGenerateRequest()

    # حمولة سياق حكيم — نُجمِّع البيانات الفعليّة من تبويبات إعدادات الجدول
    # الخمسة (التوقيت/الفصول/الإسناد/عدم التوفر/قيود الجدول) ونمرّرها صراحةً
    # للمحرك بدلاً من ترك المحرّك يقرأ القاعدة من جديد لكل مرحلة.
    context_payload = await _assemble_hakim_context_payload(school_id)

    report = await smart_scheduling_engine.build_infeasibility_report(school_id)
    if report.blocks_generation:
        raise HTTPException(
            status_code=422,
            detail={"code": "GENERATION_BLOCKED", "report": report.model_dump(mode="json")},
        )

    result = await smart_scheduling_engine.generate_timetable(
        school_id=school_id,
        academic_year_id=request.academic_year_id,
        term_id=request.term_id,
        created_by=current_user.get("id", "system"),
        calling_user=current_user,
        context_payload=context_payload,
    )
    
    return result.model_dump()


async def _assemble_hakim_context_payload(school_id: str) -> Dict[str, Any]:
    """Assemble the strict context payload for Hakeem.

    The payload is a single, validated dict that mirrors the five
    Schedule Settings tabs the user fills in:

      - ``school_settings``     — التوقيت + إعدادات اليوم الدراسي
      - ``time_slots``          — حصص اليوم وأنواعها
      - ``classes``             — الفصول الفعّالة
      - ``teacher_assignments`` — الإسنادات الفعّالة
      - ``teacher_unavailability``
      - ``class_unavailability``
      - ``school_constraints``  + ``administrative_constraints``

    We surface a basic structural validation (timing must exist) and
    log per-category counts; the engine then consumes the payload as
    its primary source instead of re-querying the DB per phase.
    """
    school_settings = await gd_find_one(db.session, "school_settings", {"school_id": school_id})
    time_slots = await gd_find(db.session, "time_slots", {"school_id": school_id}, limit=500)
    classes = await gd_find(db.session, "classes", {"school_id": school_id, "is_active": True}, limit=2000)
    assignments = await gd_find(db.session, "teacher_assignments", {"school_id": school_id, "is_active": True}, limit=5000)

    # Schedule Settings UI writes both teacher- and class-level rows into a
    # single `unavailability` collection with an `entity_type` discriminator
    # (teacher / class). We split here so each engine phase consumes only
    # the rows it cares about.
    unavailability_rows = await gd_find(db.session, "unavailability", {"school_id": school_id}, limit=10000)
    teacher_unavail = [u for u in unavailability_rows if u.get("entity_type") == "teacher"]
    class_unavail = [u for u in unavailability_rows if u.get("entity_type") == "class"]

    school_constraints = await gd_find(db.session, "school_constraints", {"school_id": school_id, "is_active": True}, limit=500)
    admin_constraints = await gd_find(db.session, "administrative_constraints", {"school_id": school_id, "is_active": True}, limit=500)

    # Strict contract — sections mirror the five Schedule Settings tabs
    # the user fills in (timing / classes / assignments / unavailability /
    # constraints). The engine reads from these named sections only.
    payload: Dict[str, Any] = {
        "school_id": school_id,
        "timing": {
            "school_settings": school_settings or None,
            "time_slots": time_slots or [],
        },
        "classes": classes or [],
        "assignments": assignments or [],
        "unavailability": {
            "teacher": teacher_unavail or [],
            "class": class_unavail or [],
        },
        "constraints": {
            "school": school_constraints or [],
            "administrative": admin_constraints or [],
        },
    }

    has_timing = bool(payload["timing"]["time_slots"]) or bool(
        (payload["timing"]["school_settings"] or {}).get("periods_per_day")
    )
    if not has_timing:
        # The infeasibility report (INF-05) will block generation, but
        # we surface the structural contract explicitly here so any
        # caller knows the payload is incomplete.
        logger.warning("hakim_context_payload school_id=%s missing timing — generation will be blocked by INF-05", school_id)

    logger.info(
        "hakim_context_payload school_id=%s timing.time_slots=%d classes=%d assignments=%d "
        "unavailability.teacher=%d unavailability.class=%d constraints.school=%d "
        "constraints.administrative=%d validated=%s",
        school_id,
        len(payload["timing"]["time_slots"]),
        len(payload["classes"]),
        len(payload["assignments"]),
        len(payload["unavailability"]["teacher"]),
        len(payload["unavailability"]["class"]),
        len(payload["constraints"]["school"]),
        len(payload["constraints"]["administrative"]),
        has_timing,
    )
    return payload


# --- Generate Timetable Smart API (Alternative endpoint for frontend) ---
@router.post("/timetable/generate-smart")
async def generate_timetable_smart(
    request: Request,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN]))
):
    """
    توليد الجدول الدراسي بالذكاء الاصطناعي - نقطة نهاية بديلة
    Smart AI-Powered Timetable Generation - Alternative endpoint
    """
    try:
        body = await request.json()
        use_baseline = bool(body.get("use_baseline", False))

        override = body.get("school_id") or request.headers.get("X-School-Context")
        if override is not None and not isinstance(override, str):
            raise HTTPException(status_code=400, detail="school_id يجب أن يكون نصاً")
        if isinstance(override, str):
            override = override.strip() or None

        school_id = resolve_school_id(current_user, override)
        if not school_id:
            raise HTTPException(status_code=400, detail="school_id مطلوب")
        
        # Get school settings
        settings = await gd_find_one(db.session, "school_settings", {"school_id": school_id})
        if not settings:
            raise HTTPException(status_code=404, detail="لم يتم العثور على إعدادات المدرسة")
        
        nested_settings = settings.get("settings", {})
        academic_year = nested_settings.get("academic_year") or settings.get("academicYear") or settings.get("academic_year")

        context_payload = await _assemble_hakim_context_payload(school_id)

        report = await smart_scheduling_engine.build_infeasibility_report(school_id)
        if report.blocks_generation:
            raise HTTPException(
                status_code=422,
                detail={"code": "GENERATION_BLOCKED", "report": report.model_dump(mode="json")},
            )

        # Generate timetable
        result = await smart_scheduling_engine.generate_timetable(
            school_id=school_id,
            academic_year_id=academic_year,
            term_id=None,
            created_by=current_user.get("id", "system"),
            calling_user=current_user,
            context_payload=context_payload,
        )
        
        return result.model_dump()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="فشل في توليد الجدول")


# --- Get School Timetables API ---
@router.get("/smart-scheduling/timetables/{school_id}")
async def smart_get_school_timetables(
    school_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    الحصول على جميع الجداول للمدرسة
    Get all timetables for a school
    """
    assert_school_access(current_user, str(school_id))
    timetables = await smart_scheduling_engine.get_school_timetables(school_id)
    return {
        "school_id": school_id,
        "total": len(timetables),
        "timetables": timetables
    }


# --- Timetable Versions List API (New - Must be before dynamic route) ---
@router.get("/smart-scheduling/timetable/versions")
async def get_timetable_versions(
    current_user: dict = Depends(get_current_user),
    x_school_context: Optional[str] = Header(None)
):
    """
    الحصول على جميع نسخ الجدول للمدرسة
    Get all timetable versions for the school
    """
    school_id = resolve_school_id(current_user, x_school_context)
    if not school_id:
        raise HTTPException(status_code=400, detail="معرف المدرسة مطلوب")
    
    # Fetch all timetables
    timetables = await gd_find(db.session, "timetables", {"school_id": school_id}, order_by="created_at", desc_order=True, limit=100)
    
    versions = []
    for tt in timetables:
        versions.append({
            "id": tt.get("id"),
            "versionName": tt.get("version_name") or tt.get("name") or f"نسخة {tt.get('id', '')[:6]}",
            "status": tt.get("status", "draft"),
            "generation_mode": tt.get("generation_mode", "full"),
            "quality_score": tt.get("quality_score", 0),
            "conflicts_count": tt.get("conflicts_count", 0),
            "warnings_count": tt.get("warnings_count", 0),
            "created_at": tt.get("created_at"),
            "published_at": tt.get("published_at"),
            "created_by": tt.get("created_by", "النظام"),
        })
    
    return {
        "school_id": school_id,
        "total": len(versions),
        "versions": versions
    }


# --- Active Timetable Sessions API (New - Must be before dynamic route) ---
@router.get("/smart-scheduling/timetable/active/sessions")
async def get_active_timetable_sessions(
    class_id: Optional[str] = None,
    teacher_id: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
    x_school_context: Optional[str] = Header(None)
):
    """
    الحصول على حصص الجدول النشط (المنشور أو المسودة)
    Get sessions for the active timetable
    """
    school_id = resolve_school_id(current_user, x_school_context)
    if not school_id:
        raise HTTPException(status_code=400, detail="معرف المدرسة مطلوب")
    
    # Find active (published) timetable first, then draft
    timetable = await gd_find_one(db.session, "timetables", {"school_id": school_id, "status": "published"})
    
    if not timetable:
        timetable = await gd_find_one(db.session, "timetables", {"school_id": school_id, "status": "draft"})
    
    if not timetable:
        return {"sessions": [], "total": 0, "message": "لا يوجد جدول نشط"}
    
    # Build query
    query = {"timetable_id": timetable.get("id")}
    if class_id:
        query["class_id"] = class_id
    if teacher_id:
        query["teacher_id"] = teacher_id
    
    # Fetch sessions
    sessions = await gd_find(db.session, "timetable_sessions", query, limit=1000)
    
    # Enrich sessions
    enriched_sessions = []
    for session in sessions:
        # Get teacher name
        teacher = await gd_find_one(db.session, "teachers", {"id": session.get("teacher_id")})
        # Get class name
        cls = await gd_find_one(db.session, "classes", {"id": session.get("class_id")})
        # Get grade
        grade = await gd_find_one(db.session, "grades", {"id": cls.get("grade_id") if cls else None})
        
        session["teacher_name"] = teacher.get("full_name") if teacher else ""
        session["class_name"] = f"{grade.get('name_ar', '')} - {cls.get('section', '') if cls else ''}" if grade else (cls.get("name", "") if cls else "")
        enriched_sessions.append(session)
    
    return {
        "timetable_id": timetable.get("id"),
        "total": len(enriched_sessions),
        "sessions": enriched_sessions
    }


# --- Get Timetable Details API ---
@router.get("/smart-scheduling/timetable/{timetable_id}")
async def smart_get_timetable(
    timetable_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    الحصول على تفاصيل جدول محدد
    Get specific timetable details
    """
    timetable = await smart_scheduling_engine.get_timetable(timetable_id)
    if not timetable:
        raise HTTPException(status_code=404, detail="الجدول غير موجود")
    assert_school_access(current_user, str(timetable.get("school_id")))
    
    return timetable


# --- Get Timetable Sessions API ---
@router.get("/smart-scheduling/timetable/{timetable_id}/sessions")
async def smart_get_timetable_sessions(
    timetable_id: str,
    class_id: Optional[str] = None,
    teacher_id: Optional[str] = None,
    day_of_week: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """
    الحصول على حصص الجدول
    Get timetable sessions with optional filters
    """
    timetable = await gd_find_one(db.session, "timetables", {"id": timetable_id})
    if not timetable:
        raise HTTPException(status_code=404, detail="الجدول غير موجود")
    assert_school_access(current_user, str(timetable.get("school_id")))
    sessions = await smart_scheduling_engine.get_timetable_sessions(
        timetable_id=timetable_id,
        class_id=class_id,
        teacher_id=teacher_id,
        day_of_week=day_of_week
    )

    # Batch fetch related entities (massive perf win vs N+1 queries)
    teacher_ids = list({s.get("teacher_id") for s in sessions if s.get("teacher_id")})
    class_ids = list({s.get("class_id") for s in sessions if s.get("class_id")})
    subject_ids = list({s.get("subject_id") for s in sessions if s.get("subject_id")})

    teachers = await gd_find(db.session, "teachers", {"id": {"$in": teacher_ids}}, limit=len(teacher_ids) or 1) if teacher_ids else []
    classes = await gd_find(db.session, "classes", {"id": {"$in": class_ids}}, limit=len(class_ids) or 1) if class_ids else []
    subjects = await gd_find(db.session, "subjects", {"id": {"$in": subject_ids}}, limit=len(subject_ids) or 1) if subject_ids else []
    found_subj_ids = {s.get("id") for s in subjects}
    missing_subj_ids = [sid for sid in subject_ids if sid not in found_subj_ids]
    if missing_subj_ids:
        ref_subjects = await gd_find(db.session, "reference_subjects", {"id": {"$in": missing_subj_ids}}, limit=len(missing_subj_ids))
        subjects = list(subjects) + list(ref_subjects)

    teacher_map = {t.get("id"): (t.get("full_name") or t.get("full_name_ar") or "") for t in teachers}
    class_map = {c.get("id"): (c.get("name") or c.get("name_ar") or "") for c in classes}
    subject_map = {s.get("id"): (s.get("name_ar") or s.get("name") or "") for s in subjects}

    for session in sessions:
        session["teacher_name"] = teacher_map.get(session.get("teacher_id"), "")
        session["class_name"] = class_map.get(session.get("class_id"), "")
        session["subject_name"] = subject_map.get(session.get("subject_id"), "")

    return {
        "timetable_id": timetable_id,
        "total": len(sessions),
        "sessions": sessions
    }


# --- Get Timetable Conflicts API ---
@router.get("/smart-scheduling/timetable/{timetable_id}/conflicts")
async def smart_get_timetable_conflicts(
    timetable_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    الحصول على تعارضات الجدول
    Get timetable conflicts
    """
    timetable = await gd_find_one(db.session, "timetables", {"id": timetable_id})
    if not timetable:
        raise HTTPException(status_code=404, detail="الجدول غير موجود")
    assert_school_access(current_user, str(timetable.get("school_id")))
    conflicts = await smart_scheduling_engine.get_timetable_conflicts(timetable_id)
    
    return {
        "timetable_id": timetable_id,
        "total": len(conflicts),
        "critical_count": len([c for c in conflicts if c.get("severity") == "critical"]),
        "high_count": len([c for c in conflicts if c.get("severity") == "high"]),
        "conflicts": conflicts
    }


# --- Get Run Logs API ---
@router.get("/smart-scheduling/run/{run_id}/logs")
async def smart_get_run_logs(
    run_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    الحصول على سجلات تشغيل المحرك
    Get scheduling engine run logs
    """
    logs = await smart_scheduling_engine.get_run_logs(run_id)
    
    return {
        "run_id": run_id,
        "total": len(logs),
        "logs": logs
    }


# --- Publish Timetable API ---
@router.post("/smart-scheduling/timetable/{timetable_id}/publish")
async def smart_publish_timetable(
    timetable_id: str,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN]))
):
    """
    نشر الجدول
    Publish the timetable (makes it visible to teachers and students)
    """
    timetable = await gd_find_one(db.session, "timetables", {"id": timetable_id})
    if not timetable:
        raise HTTPException(status_code=404, detail="الجدول غير موجود")
    assert_school_access(current_user, str(timetable.get("school_id")))
    await assert_publishable(
        smart_scheduling_engine,
        school_id=str(timetable.get("school_id")),
        timetable_id=timetable_id,
    )
    success = await smart_scheduling_engine.publish_timetable(
        timetable_id=timetable_id,
        published_by=current_user.get("id", "system")
    )
    
    if not success:
        raise HTTPException(
            status_code=400,
            detail="لا يمكن نشر الجدول - يوجد تعارضات حرجة غير محلولة"
        )
    
    return {
        "success": True,
        "timetable_id": timetable_id,
        "message_ar": "تم نشر الجدول بنجاح",
        "message_en": "Timetable published successfully"
    }


# --- Archive Timetable API ---
@router.post("/smart-scheduling/timetable/{timetable_id}/archive")
async def smart_archive_timetable(
    timetable_id: str,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN]))
):
    """
    أرشفة الجدول
    Archive the timetable
    """
    timetable = await gd_find_one(db.session, "timetables", {"id": timetable_id})
    if not timetable:
        raise HTTPException(status_code=404, detail="الجدول غير موجود")
    assert_school_access(current_user, str(timetable.get("school_id")))
    success = await smart_scheduling_engine.archive_timetable(
        timetable_id=timetable_id,
        archived_by=current_user.get("id", "system")
    )
    
    if not success:
        raise HTTPException(status_code=404, detail="الجدول غير موجود")
    
    return {
        "success": True,
        "timetable_id": timetable_id,
        "message_ar": "تم أرشفة الجدول",
        "message_en": "Timetable archived"
    }


# --- Pre-Scheduling Check API ---
@router.get("/smart-scheduling/pre-check/{school_id}")
async def smart_pre_scheduling_check(
    school_id: str,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN]))
):
    """
    التحقق المسبق من إمكانية الجدولة
    Pre-scheduling feasibility check
    
    يحسب:
    - إجمالي الطلب الأكاديمي
    - إجمالي سعة المعلمين
    - المواد بدون معلمين
    - نسبة الاستخدام المتوقعة
    """
    assert_school_access(current_user, str(school_id))
    # Load settings
    settings = await smart_scheduling_engine.load_school_settings(school_id)
    
    # Build demand and resources
    demands = await smart_scheduling_engine.build_academic_demand(school_id)
    resources = await smart_scheduling_engine.build_resource_availability(school_id, settings)
    
    # Run pre-check
    result = await smart_scheduling_engine.pre_scheduling_check(school_id, demands, resources, settings)
    infeasibility_report = await smart_scheduling_engine.build_infeasibility_report(school_id)

    return {
        "school_id": school_id,
        "can_schedule": result["can_schedule"],
        "warnings": result["warnings"],
        "errors": result["errors"],
        "statistics": result["statistics"],
        "infeasibility_report": infeasibility_report.model_dump(mode="json"),
        "message_ar": "يمكن بدء الجدولة" if result["can_schedule"] else "يوجد مشاكل تمنع الجدولة",
        "message_en": "Ready to schedule" if result["can_schedule"] else "Issues preventing scheduling"
    }


# --- Get Academic Demand Matrix API ---
@router.get("/smart-scheduling/demand-matrix/{school_id}")
async def smart_get_academic_demand(
    school_id: str,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN]))
):
    """
    الحصول على مصفوفة الطلب الأكاديمي
    Get Academic Demand Matrix (classes with their subjects and periods)
    """
    assert_school_access(current_user, str(school_id))
    demands = await smart_scheduling_engine.build_academic_demand(school_id)
    
    # Enrich with names
    enriched = []
    for demand in demands:
        # Get subjects with names
        subjects_with_names = []
        for subj in demand.subjects:
            subject_doc = await gd_find_one(db.session, "subjects", {"id": subj.get("subject_id")})
            if not subject_doc:
                subject_doc = await gd_find_one(db.session, "reference_subjects", {"id": subj.get("subject_id")})
            
            subjects_with_names.append({
                **subj,
                "subject_name": subject_doc.get("name_ar", "") if subject_doc else ""
            })
        
        enriched.append({
            "class_id": demand.class_id,
            "class_name": demand.class_name,
            "grade_id": demand.grade_id,
            "subjects": subjects_with_names,
            "total_periods_required": demand.total_periods_required
        })
    
    return {
        "school_id": school_id,
        "total_classes": len(enriched),
        "total_demand_periods": sum(d["total_periods_required"] for d in enriched),
        "demands": enriched
    }


# --- Get Resource Availability Matrix API ---
@router.get("/smart-scheduling/resource-matrix/{school_id}")
async def smart_get_resource_availability(
    school_id: str,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN]))
):
    """
    الحصول على مصفوفة توافر الموارد
    Get Resource Availability Matrix (teachers with their availability)
    """
    assert_school_access(current_user, str(school_id))
    settings = await smart_scheduling_engine.load_school_settings(school_id)
    resources = await smart_scheduling_engine.build_resource_availability(school_id, settings)
    
    # Convert to serializable format
    resources_data = []
    for r in resources:
        resources_data.append({
            "teacher_id": r.teacher_id,
            "teacher_name": r.teacher_name,
            "subject_ids": r.subject_ids,
            "weekly_load": r.weekly_load,
            "current_load": r.current_load,
            "availability": r.availability
        })
    
    return {
        "school_id": school_id,
        "total_teachers": len(resources_data),
        "total_capacity": sum(r["weekly_load"] for r in resources_data),
        "resources": resources_data
    }


# --- Delete Timetable API ---
@router.delete("/smart-scheduling/timetable/{timetable_id}")
async def smart_delete_timetable(
    timetable_id: str,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN]))
):
    """
    حذف الجدول
    Delete timetable and all its sessions
    """
    # Get timetable first
    timetable = await gd_find_one(db.session, "timetables", {"id": timetable_id})
    if not timetable:
        raise HTTPException(status_code=404, detail="الجدول غير موجود")
    assert_school_access(current_user, str(timetable.get("school_id")))
    
    # Don't delete published timetables
    if timetable.get("status") == TimetableStatus.PUBLISHED.value:
        raise HTTPException(status_code=400, detail="لا يمكن حذف جدول منشور - قم بأرشفته أولاً")
    
    # Delete sessions
    await gd_delete_many(db.session, "timetable_sessions", {"timetable_id": timetable_id})
    
    # Delete conflicts
    await gd_delete_many(db.session, "timetable_conflicts", {"timetable_id": timetable_id})
    
    # Delete unscheduled demands
    await gd_delete_many(db.session, "timetable_unscheduled_demands", {"timetable_id": timetable_id})
    
    # Delete timetable
    await gd_delete_one(db.session, "timetables", {"id": timetable_id})
    
    return {
        "success": True,
        "message_ar": "تم حذف الجدول بنجاح",
        "message_en": "Timetable deleted successfully"
    }





