"""
NASSAQ Route Module: Teacher Portfolio & Evidence endpoints
"""
from fastapi import APIRouter, HTTPException, Depends, Query, Body, UploadFile, File
from fastapi.responses import StreamingResponse, Response
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
import logging
import io
import os

from dependencies import db, get_current_user, require_roles, UserRole
from engines.portfolio_evidence_engine import (
    PortfolioEvidenceEngine, ALL_EVIDENCE_TYPES, EVIDENCE_SECTIONS, SECTION_FOR_TYPE,
    EVIDENCE_SUBSECTIONS_V2,
)
from engines.sql_utils import gd_find_one, gd_upsert, gd_find
from sqlalchemy import select, text
import uuid as _uuid
import hashlib as _hashlib


async def _lock_teacher_meta(teacher_id: str) -> None:
    """Acquire a transaction-scoped Postgres advisory lock keyed on teacher_id.
    Serializes concurrent read-modify-write on teacher_portfolio_meta for the same teacher,
    preventing lost CV items and duplicate meta docs under parallel requests.
    Released automatically at transaction end.
    """
    h = _hashlib.sha1(f"teacher_portfolio_meta:{teacher_id}".encode("utf-8")).digest()
    key = int.from_bytes(h[:8], "big", signed=True)
    await db.session.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": key})

router = APIRouter()
_engine = PortfolioEvidenceEngine(db)
logger = logging.getLogger("nassaq.portfolio.routes")

_TEACHER_WRITE_ROLES = ("teacher", "independent_teacher")

_ALLOWED_DATA_URL_PREFIXES = (
    "data:application/pdf;",
    "data:image/",
    "data:video/",
    "data:application/msword;",
    "data:application/vnd.openxmlformats-officedocument.",
    "data:application/vnd.ms-",
    "data:text/",
)


class ManualEvidenceCreate(BaseModel):
    evidence_type: str
    title_ar: str
    title_en: str = ""
    description_ar: Optional[str] = None
    description_en: Optional[str] = None
    date: Optional[str] = None
    class_id: Optional[str] = None
    subject_id: Optional[str] = None
    file_url: Optional[str] = None
    file_name: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class EvidenceUpdate(BaseModel):
    title_ar: Optional[str] = None
    title_en: Optional[str] = None
    description_ar: Optional[str] = None
    description_en: Optional[str] = None
    date: Optional[str] = None
    evidence_type: Optional[str] = None
    file_url: Optional[str] = None
    file_name: Optional[str] = None
    class_id: Optional[str] = None
    subject_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


@router.get("/teacher/portfolio")
async def get_teacher_portfolio(current_user: dict = Depends(get_current_user)):
    if current_user["role"] not in ("teacher", "platform_admin", "school_principal", "school_admin", "independent_teacher"):
        raise HTTPException(status_code=403, detail="غير مصرح")
    teacher_id = current_user["id"]
    school_id = current_user.get("tenant_id")
    portfolio = await _engine.get_teacher_portfolio(teacher_id, school_id)
    return portfolio


@router.get("/teacher/portfolio/evidence")
async def list_evidence(
    evidence_type: Optional[str] = None,
    section: Optional[str] = None,
    source: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user: dict = Depends(get_current_user),
):
    if current_user["role"] not in ("teacher", "platform_admin", "school_principal", "school_admin", "independent_teacher"):
        raise HTTPException(status_code=403, detail="غير مصرح")
    teacher_id = current_user["id"]
    school_id = current_user.get("tenant_id")
    result = await _engine.get_evidence_list(
        teacher_id=teacher_id,
        school_id=school_id,
        evidence_type=evidence_type,
        section=section,
        source=source,
        start_date=start_date,
        end_date=end_date,
        skip=skip,
        limit=limit,
    )
    return result


@router.post("/teacher/portfolio/upload")
async def upload_evidence_file(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
):
    """Upload an evidence attachment (PDF / image / video). Returns a data URL the client
    can store on the evidence record's file_url field. Stays consistent with the existing
    parent /upload-attachment pattern (base64 data URL, no external storage required)."""
    if current_user["role"] not in _TEACHER_WRITE_ROLES:
        raise HTTPException(status_code=403, detail="غير مصرح")

    import base64
    MAX_SIZE = 10 * 1024 * 1024  # 10 MB
    ALLOWED_TYPES = {
        "application/pdf",
        "image/jpeg", "image/png", "image/gif", "image/webp",
        "video/mp4", "video/webm", "video/quicktime",
        # Office documents
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.ms-powerpoint",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        # Plain text / markdown
        "text/plain", "text/markdown", "text/x-markdown",
        # Some browsers send octet-stream for office files; accept and normalize via extension
        "application/octet-stream",
    }
    EXT_TO_TYPE = {
        ".pdf": "application/pdf",
        ".doc": "application/msword",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".ppt": "application/vnd.ms-powerpoint",
        ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        ".xls": "application/vnd.ms-excel",
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".txt": "text/plain",
        ".md": "text/markdown",
        ".markdown": "text/markdown",
    }
    fname = (file.filename or "").lower()
    ext = ""
    if "." in fname:
        ext = fname[fname.rfind("."):]
    inferred = EXT_TO_TYPE.get(ext)
    ctype = file.content_type or ""
    # If browser sent generic octet-stream but extension is recognized, use the inferred type.
    if ctype in ("", "application/octet-stream") and inferred:
        ctype = inferred
    if ctype not in ALLOWED_TYPES and inferred not in ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail="صيغة الملف غير مدعومة")
    # Prefer the inferred type when it matches a known extension (more reliable)
    final_ctype = inferred or ctype

    chunks: list[bytes] = []
    total = 0
    CHUNK = 64 * 1024
    while True:
        chunk = await file.read(CHUNK)
        if not chunk:
            break
        total += len(chunk)
        if total > MAX_SIZE:
            raise HTTPException(status_code=400, detail="حجم الملف يتجاوز 10 ميغابايت")
        chunks.append(chunk)
    content = b"".join(chunks)
    encoded = base64.b64encode(content).decode("utf-8")
    return {
        "success": True,
        "file_url": f"data:{final_ctype};base64,{encoded}",
        "file_name": file.filename,
        "content_type": final_ctype,
        "size": len(content),
    }


@router.post("/teacher/portfolio/evidence")
async def add_evidence(
    data: ManualEvidenceCreate,
    current_user: dict = Depends(get_current_user),
):
    if current_user["role"] not in _TEACHER_WRITE_ROLES:
        raise HTTPException(status_code=403, detail="غير مصرح")
    if data.file_url:
        MAX_DATA_URL = 14 * 1024 * 1024  # base64 of 10 MB ≈ 13.3 MB
        if len(data.file_url) > MAX_DATA_URL:
            raise HTTPException(status_code=400, detail="حجم المرفق يتجاوز الحد المسموح")
        if not (
            data.file_url.startswith(_ALLOWED_DATA_URL_PREFIXES)
            or data.file_url.startswith("https://")
            or data.file_url.startswith("http://")
        ):
            raise HTTPException(status_code=400, detail="صيغة المرفق غير مدعومة")
    teacher_id = current_user["id"]
    school_id = current_user.get("tenant_id", "")
    result = await _engine.add_manual_evidence(
        teacher_id=teacher_id,
        school_id=school_id,
        evidence_type=data.evidence_type,
        title_ar=data.title_ar,
        title_en=data.title_en,
        description_ar=data.description_ar,
        description_en=data.description_en,
        date=data.date,
        class_id=data.class_id,
        subject_id=data.subject_id,
        file_url=data.file_url,
        file_name=data.file_name,
        metadata=data.metadata,
    )
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "فشل في إضافة الشاهد"))
    return result


@router.put("/teacher/portfolio/evidence/{evidence_id}")
async def update_evidence(
    evidence_id: str,
    data: EvidenceUpdate,
    current_user: dict = Depends(get_current_user),
):
    if current_user["role"] not in _TEACHER_WRITE_ROLES:
        raise HTTPException(status_code=403, detail="غير مصرح")
    if data.file_url:
        MAX_DATA_URL = 14 * 1024 * 1024
        if len(data.file_url) > MAX_DATA_URL:
            raise HTTPException(status_code=400, detail="حجم المرفق يتجاوز الحد المسموح")
        if not (
            data.file_url.startswith(_ALLOWED_DATA_URL_PREFIXES)
            or data.file_url.startswith("https://")
            or data.file_url.startswith("http://")
        ):
            raise HTTPException(status_code=400, detail="صيغة المرفق غير مدعومة")
    # Honor explicit None for fields the client actually sent (PATCH semantics),
    # so that teachers can clear file_url, class_id, subject_id, etc.
    sent = data.model_fields_set
    full = data.model_dump()
    updates = {k: full[k] for k in sent}
    result = await _engine.update_evidence(evidence_id, current_user["id"], updates)
    if not result.get("success"):
        err = result.get("error", "not_found")
        if err == "invalid_evidence_type":
            raise HTTPException(status_code=400, detail=err)
        raise HTTPException(status_code=404, detail=err)
    return result


@router.delete("/teacher/portfolio/evidence/{evidence_id}")
async def delete_evidence(
    evidence_id: str,
    current_user: dict = Depends(get_current_user),
):
    if current_user["role"] not in _TEACHER_WRITE_ROLES:
        raise HTTPException(status_code=403, detail="غير مصرح")
    result = await _engine.delete_evidence(evidence_id, current_user["id"])
    if not result.get("success"):
        raise HTTPException(status_code=404, detail=result.get("error", "not_found"))
    return result


@router.get("/teacher/portfolio/progress")
async def get_portfolio_progress(current_user: dict = Depends(get_current_user)):
    if current_user["role"] not in ("teacher", "platform_admin", "school_principal", "school_admin", "independent_teacher"):
        raise HTTPException(status_code=403, detail="غير مصرح")
    teacher_id = current_user["id"]
    school_id = current_user.get("tenant_id")
    progress = await _engine.get_portfolio_progress(teacher_id, school_id)
    return progress


@router.get("/teacher/portfolio/evidence-types")
async def get_evidence_types(current_user: dict = Depends(get_current_user)):
    if current_user["role"] not in ("teacher", "platform_admin", "school_principal", "school_admin", "independent_teacher"):
        raise HTTPException(status_code=403, detail="غير مصرح")
    result = {}
    for section_key, type_keys in EVIDENCE_SECTIONS.items():
        result[section_key] = type_keys
    return {"sections": result, "all_types": ALL_EVIDENCE_TYPES}


class HakimEvidenceTextRequest(BaseModel):
    mode: str = Field(..., description="generate | improve")
    field: str = Field(..., description="title | description")
    text: Optional[str] = ""
    evidence_type: Optional[str] = None
    title: Optional[str] = None
    subject: Optional[str] = None
    grade: Optional[str] = None


@router.post("/teacher/portfolio/hakim-evidence-text")
async def hakim_evidence_text(
    payload: HakimEvidenceTextRequest,
    current_user: dict = Depends(get_current_user),
):
    if current_user["role"] not in ("teacher", "platform_admin", "school_principal", "school_admin", "independent_teacher"):
        raise HTTPException(status_code=403, detail="غير مصرح")

    mode = (payload.mode or "").strip().lower()
    field_in = (payload.field or "").strip().lower()
    if mode not in ("generate", "improve"):
        raise HTTPException(status_code=422, detail="invalid_mode")
    if field_in not in ("title", "description"):
        raise HTTPException(status_code=422, detail="invalid_field")

    field_key = "evidence_title" if field_in == "title" else "evidence_description"
    text_in = (payload.text or "").strip()
    if mode == "improve" and len(text_in) < 5:
        raise HTTPException(status_code=422, detail="TEXT_TOO_SHORT")

    context = {
        "evidence_type": (payload.evidence_type or "").replace("_", " ") or None,
        "subject": payload.subject,
        "grade": payload.grade,
    }
    if field_in == "description" and payload.title:
        context["title"] = payload.title

    try:
        from services.hakim_llm_service import hakim_generate
        result = await hakim_generate(
            mode=mode, field=field_key, text=text_in, context=context, language="ar",
            tenant_id=current_user.get("tenant_id"),
        )
    except Exception as e:
        logger.warning(f"[Hakim] portfolio evidence text {mode}/{field_in} failed: {e}")
        raise HTTPException(status_code=502, detail="HAKIM_FAILED")

    if result.get("success"):
        return {
            "success": True,
            "text": result["text"],
            "generation_id": result.get("generation_id"),
            "model": result.get("model"),
            "elapsed_ms": result.get("elapsed_ms"),
        }

    reason = result.get("reason") or "HAKIM_FAILED"
    if reason in ("AI_DISABLED", "AI_DISABLED_BY_TENANT", "AI_CONSENT_UNVERIFIED"):
        return {"success": False, "text": text_in, "reason": reason}
    if reason == "TEXT_TOO_SHORT":
        raise HTTPException(status_code=422, detail="TEXT_TOO_SHORT")
    if reason in ("LLM_ERROR",):
        raise HTTPException(status_code=502, detail="HAKIM_FAILED")
    # validation failures (EMPTY/TOO_SHORT/WRONG_LANGUAGE/UNCHANGED) — surface gracefully
    return {"success": False, "text": text_in, "reason": reason}


# =============================================================================
# Portfolio v2 — editable metadata (intro / vision / mission / values / CV)
# Storage collection: teacher_portfolio_meta (one document per teacher).
# Doc shape:
#   {
#     id, teacher_id, school_id,
#     intro: str, vision: str, mission: str, values: str,
#     cv_items: [ {id, kind, title, organization, date, hours, description} ],
#     intro_generated_at, vmv_generated_at, updated_at
#   }
# =============================================================================

CV_KINDS = ("training_attended", "training_delivered", "award", "thank_letter")


async def _load_meta(teacher_id: str) -> Dict[str, Any]:
    doc = await gd_find_one(db.session, "teacher_portfolio_meta", {"teacher_id": teacher_id})
    if not doc:
        return {
            "teacher_id": teacher_id,
            "intro": "",
            "vision": "",
            "mission": "",
            "values": "",
            "cv_items": [],
            "intro_generated_at": None,
            "vmv_generated_at": None,
            "updated_at": None,
        }
    doc.setdefault("cv_items", [])
    return doc


async def _save_meta(teacher_id: str, school_id: Optional[str], updates: Dict[str, Any]) -> Dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    existing = await _load_meta(teacher_id)
    payload = {
        **existing,
        "teacher_id": teacher_id,
        "school_id": school_id if school_id is not None else existing.get("school_id", ""),
        "updated_at": now,
        **updates,
    }
    payload.pop("_id", None)
    await gd_upsert(db.session, "teacher_portfolio_meta", {"teacher_id": teacher_id}, payload)
    await db.session.commit()
    return await _load_meta(teacher_id)


async def _load_teacher_profile(current_user: dict) -> Dict[str, Any]:
    """Load lightweight teacher info used as context for AI generation and CV personal-data grid.

    Identity fields (full_name, email, phone) come from the authenticated user's
    own `users` row and are always returned, even when no `teachers` row exists.
    Teacher-specific fields (specialization, subject, qualification, ...) are
    layered on top when the `teachers` row is found via the resolved teacher id
    (`current_user["teacher_id"]`) or, as a fallback, `teachers.user_id`.
    """
    user_id = current_user.get("id")
    resolved_teacher_id = current_user.get("teacher_id")
    try:
        from pg_models import Teacher, User

        user_res = await db.session.execute(select(User).where(User.id == user_id))
        user = user_res.scalar_one_or_none()

        teacher = None
        if resolved_teacher_id:
            result = await db.session.execute(
                select(Teacher).where(Teacher.id == resolved_teacher_id)
            )
            teacher = result.scalar_one_or_none()
        if not teacher and user_id:
            result = await db.session.execute(
                select(Teacher).where(Teacher.user_id == user_id)
            )
            teacher = result.scalar_one_or_none()

        return {
            "full_name": (getattr(user, "full_name", None) or getattr(teacher, "full_name", None) or ""),
            "email": getattr(user, "email", None) or getattr(teacher, "email", None) or "",
            "phone": getattr(user, "phone", None) or getattr(teacher, "phone", None) or "",
            "specialization": getattr(teacher, "specialization", None) or "",
            "subject": getattr(teacher, "subject", None) or "",
            "rank": getattr(teacher, "rank", None) or "",
            "qualification": getattr(teacher, "qualification", None) or "",
            "years_of_experience": getattr(teacher, "years_of_experience", 0) or 0,
        }
    except Exception as e:
        logger.warning(f"_load_teacher_profile failed: {e}")
        return {}


def _auto_cv_from_evidence(evidence_list: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """Derive CV items (training attended, workshops, etc.) from existing portfolio evidence."""
    attended_types = {"training_certificate", "workshop_attendance", "training_attendance_report"}
    delivered_types = {"workshop_delivery"}
    auto = {"training_attended": [], "training_delivered": [], "award": []}
    for e in evidence_list:
        et = e.get("evidence_type")
        item = {
            "id": f"auto:{e.get('id')}",
            "source": "auto",
            "title": e.get("title_ar") or e.get("title_en") or "",
            "organization": (e.get("metadata") or {}).get("organization") or "",
            "date": e.get("date") or "",
            "hours": (e.get("metadata") or {}).get("hours"),
            "description": e.get("description_ar") or e.get("description_en") or "",
            "evidence_id": e.get("id"),
        }
        if et in attended_types:
            auto["training_attended"].append(item)
        elif et in delivered_types:
            auto["training_delivered"].append(item)
    return auto


@router.get("/teacher/portfolio/sections")
async def get_portfolio_sections(current_user: dict = Depends(get_current_user)):
    """Return everything the new 6-section portfolio UI needs in a single call.
    Restricted to the teacher viewing their own portfolio. Admin/principal review of
    other teachers' portfolios should go through a dedicated endpoint with an explicit
    teacher_id parameter and proper tenant scoping.
    """
    if current_user["role"] not in ("teacher", "platform_admin", "school_principal", "school_admin", "independent_teacher"):
        raise HTTPException(status_code=403, detail="غير مصرح")

    teacher_id = current_user["id"]
    school_id = current_user.get("tenant_id")

    meta = await _load_meta(teacher_id)
    profile = await _load_teacher_profile(current_user)

    # Evidence list (for sub-section counts + auto-CV)
    query: Dict[str, Any] = {"teacher_id": teacher_id}
    if school_id:
        query["school_id"] = school_id
    evidence_list = await gd_find(db.session, "portfolio_evidence", query,
                                   order_by="created_at", desc_order=True, limit=5000)

    # Sub-section counts + items for section 6
    subsections: Dict[str, Any] = {}
    for sub_key, type_keys in EVIDENCE_SUBSECTIONS_V2.items():
        sub_items = [e for e in evidence_list if e.get("evidence_type") in type_keys]
        subsections[sub_key] = {
            "count": len(sub_items),
            "types": type_keys,
            "items": sub_items[:50],
        }

    # Auto-derived CV items + manual ones from meta
    auto_cv = _auto_cv_from_evidence(evidence_list)
    manual_cv = {"training_attended": [], "training_delivered": [], "award": [], "thank_letter": []}
    for it in meta.get("cv_items", []):
        kind = it.get("kind")
        if kind in manual_cv:
            manual_cv[kind].append({**it, "source": "manual"})

    return {
        "intro": {
            "text": meta.get("intro", ""),
            "generated_at": meta.get("intro_generated_at"),
        },
        "vmv": {
            "vision": meta.get("vision", ""),
            "mission": meta.get("mission", ""),
            "values": meta.get("values", ""),
            "generated_at": meta.get("vmv_generated_at"),
        },
        "cv": {
            "profile": profile,
            "training_attended": auto_cv["training_attended"] + manual_cv["training_attended"],
            "training_delivered": auto_cv["training_delivered"] + manual_cv["training_delivered"],
            "award": manual_cv["award"],
            "thank_letter": manual_cv["thank_letter"],
        },
        "evidence_subsections": subsections,
        "updated_at": meta.get("updated_at"),
    }


# ---- PDF Export ----

_FONT_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static", "fonts", "Amiri-Regular.ttf")
_FONT_REGISTERED = False


def _ensure_arabic_font():
    global _FONT_REGISTERED
    if _FONT_REGISTERED:
        return "Amiri"
    try:
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        if os.path.exists(_FONT_PATH):
            pdfmetrics.registerFont(TTFont("Amiri", _FONT_PATH))
            _FONT_REGISTERED = True
            return "Amiri"
    except Exception as e:
        logger.warning(f"Failed to register Arabic font: {e}")
    return "Helvetica"


def _ar(text: str) -> str:
    if not text:
        return ""
    try:
        import arabic_reshaper
        from bidi.algorithm import get_display
        return get_display(arabic_reshaper.reshape(str(text)))
    except Exception:
        return str(text)


_SUBSECTION_TITLES_AR = {
    "planning": "شواهد التخطيط",
    "execution": "شواهد التنفيذ",
    "assessment": "شواهد التقويم",
    "results": "شواهد النتائج",
    "community": "شواهد التواصل والمجتمع",
    "professional_development": "شواهد التطوير المهني",
}

_SUBSECTION_COLORS = {
    "planning": "#2563EB",
    "execution": "#10B981",
    "assessment": "#9333EA",
    "results": "#D97706",
    "community": "#DB2777",
    "professional_development": "#4F46E5",
}

_TYPE_LABEL_AR = {
    "curriculum_distribution_plan": "خطة توزيع المنهج",
    "weekly_plan": "الخطة الأسبوعية",
    "lesson_plan": "خطة الدرس",
    "preparation_record": "سجل التحضير",
    "unit_plan": "خطة وحدة دراسية",
    "classroom_activity_plan": "خطة النشاط الصفي",
    "struggling_student_plan": "خطة دعم المتعثرين",
    "gifted_student_plan": "خطة رعاية المتفوقين",
    "learning_loss_plan": "خطة معالجة الفاقد التعليمي",
    "classroom_activity_photos": "صور أنشطة صفية",
    "student_worksheets": "أوراق عمل الطلاب",
    "applied_lesson_report": "تقرير درس تطبيقي",
    "lesson_video_recording": "تسجيل فيديو لدرس",
    "collaborative_lesson": "أنشطة تعاونية",
    "teaching_strategies": "استراتيجيات تدريس",
    "exam_results": "الاختبارات",
    "quiz_results": "الاختبارات القصيرة",
    "assessment_worksheet": "أوراق العمل التقويمية",
    "performance_task": "المهام الأدائية",
    "student_portfolio_files": "ملفات إنجاز الطلاب",
    "student_project": "مشاريع الطلاب",
    "oral_assessment": "التقويم الشفهي",
    "classroom_observation": "الملاحظة الصفية",
    "exam_results_analysis": "تحليل نتائج الاختبارات",
    "class_results_analysis": "تحليل نتائج الفصل",
    "student_progress_report": "تقارير تقدم الطلاب",
    "grade_analysis_tables": "جداول تحليل الدرجات",
    "before_after_comparison": "مقارنة النتائج قبل وبعد",
    "results_improvement_plan": "خطة تحسين النتائج",
    "parent_communication_log": "سجل التواصل مع أولياء الأمور",
    "parent_meeting_minutes": "تقرير اجتماع مع أولياء الأمور",
    "school_activity_participation": "مشاركة في نشاط مدرسي",
    "school_event_participation": "مشاركة في الفعاليات المدرسية",
    "training_attendance_report": "تقرير حضور دورة",
    "professional_growth_plan": "خطة تطوير مهني",
    "plc_participation": "مجتمعات التعلم المهنية",
    "peer_observation": "تبادل الزيارات",
    "workshop_attendance": "حضور ورش عمل",
    "workshop_delivery": "تقديم ورش",
    "volunteer_activity_report": "تقرير نشاط تطوعي",
    "training_certificate": "شهادة تدريبية",
    "attendance_record": "سجل حضور",
}


def _type_label(key: str) -> str:
    return _TYPE_LABEL_AR.get(key, (key or "").replace("_", " "))


async def _lookup_class_subject_names(class_ids, subject_ids):
    """Best-effort lookup of class names and subject names by id."""
    cls_map: Dict[str, str] = {}
    sub_map: Dict[str, str] = {}
    try:
        if class_ids:
            from pg_models import Class
            res = await db.session.execute(select(Class).where(Class.id.in_(list(class_ids))))
            for c in res.scalars().all():
                cls_map[str(c.id)] = getattr(c, "name", "") or getattr(c, "title", "") or ""
    except Exception:
        pass
    try:
        if subject_ids:
            from pg_models import Subject
            res = await db.session.execute(select(Subject).where(Subject.id.in_(list(subject_ids))))
            for s in res.scalars().all():
                sub_map[str(s.id)] = getattr(s, "name", "") or getattr(s, "title", "") or ""
    except Exception:
        pass
    return cls_map, sub_map


def _safe_filename_part(name: str) -> str:
    s = (name or "teacher").strip().replace(" ", "_")
    return "".join(ch for ch in s if ch.isalnum() or ch in ("_", "-")) or "teacher"


def _attachment_headers(filename_pretty: str, filename_ascii: str) -> Dict[str, str]:
    from urllib.parse import quote as _urlquote
    encoded = _urlquote(filename_pretty)
    return {"Content-Disposition": f'attachment; filename="{filename_ascii}"; filename*=UTF-8\'\'{encoded}'}


def _export_portfolio_html(profile, meta, evidence_list, cls_map, sub_map, current_user):
    """Render the portfolio as a printable, RTL HTML document."""
    teacher_name = profile.get("full_name") or current_user.get("full_name") or ""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    intro_text = (meta.get("intro") or "").strip()
    vision = (meta.get("vision") or "").strip()
    mission = (meta.get("mission") or "").strip()
    values = (meta.get("values") or "").strip()
    cv_items = list(meta.get("cv_items") or [])

    def esc(s):
        if s is None:
            return ""
        return (str(s)
                .replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                .replace('"', "&quot;"))

    profile_rows = []
    for label, val in [
        ("الاسم", teacher_name),
        ("البريد الإلكتروني", profile.get("email")),
        ("الجوال", profile.get("phone")),
        ("التخصص", profile.get("specialization")),
        ("المادة", profile.get("subject")),
        ("الرتبة", profile.get("rank")),
        ("المؤهل", profile.get("qualification")),
        ("سنوات الخبرة", profile.get("years_of_experience")),
    ]:
        if val:
            profile_rows.append(f"<tr><th>{esc(label)}</th><td>{esc(val)}</td></tr>")

    sections_html = []
    for sub_key, type_keys in EVIDENCE_SUBSECTIONS_V2.items():
        items = [e for e in evidence_list if e.get("evidence_type") in type_keys]
        title = _SUBSECTION_TITLES_AR.get(sub_key, sub_key)
        color = _SUBSECTION_COLORS.get(sub_key, "#0E3A5F")
        sections_html.append(f'<h2 style="color:{color};border-bottom:3px solid {color};padding-bottom:6px;margin-top:32px;">{esc(title)} <span class="count">({len(items)})</span></h2>')
        if not items:
            sections_html.append('<p class="muted">لا توجد شواهد في هذا القسم.</p>')
            continue
        for ev in items:
            ev_title = ev.get("title_ar") or ev.get("title_en") or ""
            ev_desc = ev.get("description_ar") or ev.get("description_en") or ""
            type_label = _type_label(ev.get("evidence_type"))
            cls_name = cls_map.get(ev.get("class_id"), "") if ev.get("class_id") else ""
            sub_name = sub_map.get(ev.get("subject_id"), "") if ev.get("subject_id") else ""
            date = ev.get("date") or (ev.get("created_at") or "")[:10]
            source = "تلقائي" if ev.get("source") == "auto" else "إضافة يدوية"
            file_url = ev.get("file_url") or ""
            file_name = ev.get("file_name") or ""
            attach = ""
            if file_url:
                if file_url.startswith("http://") or file_url.startswith("https://"):
                    attach = f'<div class="attach">المرفق: <a href="{esc(file_url)}" target="_blank" rel="noopener">{esc(file_name or file_url)}</a></div>'
                else:
                    attach = f'<div class="attach">المرفق: {esc(file_name or "ملف مرفق")}</div>'
            meta_bits = []
            if type_label: meta_bits.append(f'<span class="chip">{esc(type_label)}</span>')
            if sub_name: meta_bits.append(f'<span class="chip">المادة: {esc(sub_name)}</span>')
            if cls_name: meta_bits.append(f'<span class="chip">الصف: {esc(cls_name)}</span>')
            if date: meta_bits.append(f'<span class="chip">التاريخ: {esc(date)}</span>')
            meta_bits.append(f'<span class="chip src">{esc(source)}</span>')
            sections_html.append(
                f'<div class="card">'
                f'<h3>{esc(ev_title)}</h3>'
                f'<div class="meta">{"".join(meta_bits)}</div>'
                + (f'<p class="desc">{esc(ev_desc)}</p>' if ev_desc else "")
                + attach
                + '</div>'
            )

    cv_html = ""
    if cv_items:
        rows = []
        for it in cv_items:
            rows.append(
                f'<li><strong>{esc(it.get("title") or "")}</strong>'
                + (f' — {esc(it.get("organization"))}' if it.get("organization") else "")
                + (f' <em>({esc(it.get("date"))})</em>' if it.get("date") else "")
                + (f'<br><span class="muted">{esc(it.get("description"))}</span>' if it.get("description") else "")
                + '</li>'
            )
        cv_html = '<h2>السيرة الذاتية</h2><ul class="cv">' + "".join(rows) + '</ul>'

    html = f"""<!doctype html>
<html lang="ar" dir="rtl">
<head>
<meta charset="utf-8">
<title>ملف الإنجاز المهني — {esc(teacher_name)}</title>
<style>
  body {{ font-family: 'Segoe UI', Tahoma, 'Cairo', sans-serif; max-width: 900px; margin: 24px auto; padding: 0 24px; color: #1f2937; line-height: 1.7; background: #fff; }}
  h1 {{ color: #0E3A5F; margin-bottom: 4px; }}
  h2 {{ font-size: 18px; margin-top: 28px; }}
  h3 {{ margin: 0 0 8px; color: #0E3A5F; font-size: 15px; }}
  .subtitle {{ color: #6B7280; margin-top: 0; font-size: 13px; }}
  .card {{ border: 1px solid #E5E7EB; border-radius: 10px; padding: 14px 16px; margin: 10px 0; background: #FAFAFB; page-break-inside: avoid; }}
  .meta {{ display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 8px; }}
  .chip {{ font-size: 11px; background: #fff; border: 1px solid #E5E7EB; color: #374151; padding: 2px 8px; border-radius: 999px; }}
  .chip.src {{ background: #FEF3C7; border-color: #FDE68A; color: #92400E; }}
  .desc {{ margin: 6px 0 0; color: #374151; font-size: 13px; white-space: pre-wrap; }}
  .attach {{ margin-top: 8px; font-size: 12px; color: #4B5563; }}
  .attach a {{ color: #1FB1A8; text-decoration: none; }}
  .count {{ color: #6B7280; font-size: 13px; font-weight: normal; }}
  table.profile {{ border-collapse: collapse; margin: 12px 0; width: 100%; }}
  table.profile th {{ text-align: right; background: #F0F9FA; color: #0E3A5F; padding: 8px 12px; width: 30%; font-weight: 600; border: 1px solid #E5E7EB; }}
  table.profile td {{ padding: 8px 12px; border: 1px solid #E5E7EB; }}
  ul.cv {{ padding-right: 18px; }}
  ul.cv li {{ margin-bottom: 8px; }}
  .muted {{ color: #6B7280; font-size: 12px; }}
  .header-bar {{ background: #0E3A5F; color: #fff; padding: 14px 18px; border-radius: 10px; display: flex; justify-content: space-between; align-items: center; }}
  .header-bar .right {{ font-size: 13px; opacity: 0.85; }}
  @media print {{ body {{ margin: 0; }} .card {{ break-inside: avoid; }} }}
</style>
</head>
<body>
  <div class="header-bar">
    <div><strong>NASSAQ</strong> — ملف الإنجاز المهني</div>
    <div class="right">{esc(today)}</div>
  </div>
  <h1>{esc(teacher_name)}</h1>
  <p class="subtitle">{esc(profile.get("specialization") or profile.get("subject") or "")}</p>

  {('<h2>البيانات الشخصية</h2><table class="profile">' + "".join(profile_rows) + '</table>') if profile_rows else ''}

  {('<h2>المقدمة</h2><p class="desc">' + esc(intro_text) + '</p>') if intro_text else ''}

  {('<h2>الرؤية</h2><p class="desc">' + esc(vision) + '</p>') if vision else ''}
  {('<h2>الرسالة</h2><p class="desc">' + esc(mission) + '</p>') if mission else ''}
  {('<h2>القيم</h2><p class="desc">' + esc(values) + '</p>') if values else ''}

  {cv_html}

  <h2>الشواهد</h2>
  {"".join(sections_html)}
</body>
</html>"""

    pretty = f"portfolio_{_safe_filename_part(teacher_name)}_{today}.html"
    ascii_n = f"portfolio_{today}.html"
    return Response(
        content=html.encode("utf-8"),
        media_type="text/html; charset=utf-8",
        headers=_attachment_headers(pretty, ascii_n),
    )


def _export_portfolio_docx(profile, meta, evidence_list, cls_map, sub_map, current_user):
    """Render the portfolio as a DOCX (Word) document with RTL support."""
    from docx import Document
    from docx.shared import Pt, RGBColor, Cm
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml.ns import qn
    from docx.oxml import OxmlElement

    teacher_name = profile.get("full_name") or current_user.get("full_name") or ""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    doc = Document()
    # Set default RTL & font
    style = doc.styles["Normal"]
    style.font.name = "Arial"
    style.font.size = Pt(11)
    rpr = style.element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.append(rfonts)
    rfonts.set(qn("w:cs"), "Arial")

    def _set_rtl(paragraph):
        pPr = paragraph._p.get_or_add_pPr()
        bidi = OxmlElement("w:bidi")
        bidi.set(qn("w:val"), "1")
        pPr.append(bidi)
        paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT

    def add_p(text, *, bold=False, size=11, color=None, align_right=True, after=4):
        p = doc.add_paragraph()
        if align_right:
            _set_rtl(p)
        run = p.add_run(text or "")
        run.bold = bold
        run.font.size = Pt(size)
        if color:
            run.font.color.rgb = RGBColor.from_string(color.lstrip("#"))
        p.paragraph_format.space_after = Pt(after)
        return p

    def add_heading(text, level=1, color="0E3A5F"):
        size = {1: 18, 2: 14, 3: 12}.get(level, 12)
        return add_p(text, bold=True, size=size, color=color, after=6)

    # Cover
    add_heading("ملف الإنجاز المهني", level=1, color="0E3A5F")
    add_p(teacher_name, bold=True, size=16, after=2)
    sub = profile.get("specialization") or profile.get("subject") or ""
    if sub:
        add_p(sub, color="6B7280", size=11)
    add_p(f"تاريخ الإصدار: {today}", color="6B7280", size=10, after=12)

    # Profile table
    profile_rows = [(label, val) for label, val in [
        ("الاسم", teacher_name),
        ("البريد الإلكتروني", profile.get("email")),
        ("الجوال", profile.get("phone")),
        ("التخصص", profile.get("specialization")),
        ("المادة", profile.get("subject")),
        ("الرتبة", profile.get("rank")),
        ("المؤهل", profile.get("qualification")),
        ("سنوات الخبرة", profile.get("years_of_experience")),
    ] if val]
    if profile_rows:
        add_heading("البيانات الشخصية", level=2)
        tbl = doc.add_table(rows=len(profile_rows), cols=2)
        tbl.style = "Light Grid Accent 1"
        for i, (label, val) in enumerate(profile_rows):
            c0 = tbl.rows[i].cells[0]
            c1 = tbl.rows[i].cells[1]
            c0.text = ""
            c1.text = ""
            for cell, txt, bold in ((c0, str(label), True), (c1, str(val), False)):
                p = cell.paragraphs[0]
                _set_rtl(p)
                r = p.add_run(txt)
                r.bold = bold
                r.font.size = Pt(11)

    # Intro
    intro_text = (meta.get("intro") or "").strip()
    if intro_text:
        add_heading("المقدمة", level=2)
        add_p(intro_text)

    # Vision / Mission / Values
    for label, key in (("الرؤية", "vision"), ("الرسالة", "mission"), ("القيم", "values")):
        v = (meta.get(key) or "").strip()
        if v:
            add_heading(label, level=2)
            add_p(v)

    # CV
    cv_items = list(meta.get("cv_items") or [])
    if cv_items:
        add_heading("السيرة الذاتية", level=2)
        for it in cv_items:
            line = it.get("title") or ""
            if it.get("organization"):
                line += f" — {it.get('organization')}"
            if it.get("date"):
                line += f"  ({it.get('date')})"
            add_p(line, bold=True, after=2)
            if it.get("description"):
                add_p(it["description"], color="6B7280", size=10, after=6)

    # Evidences per section
    add_heading("الشواهد", level=2)
    for sub_key, type_keys in EVIDENCE_SUBSECTIONS_V2.items():
        items = [e for e in evidence_list if e.get("evidence_type") in type_keys]
        title = _SUBSECTION_TITLES_AR.get(sub_key, sub_key)
        color = _SUBSECTION_COLORS.get(sub_key, "#0E3A5F").lstrip("#")
        add_heading(f"{title}  ({len(items)})", level=3, color=color)
        if not items:
            add_p("لا توجد شواهد في هذا القسم.", color="9CA3AF", size=10, after=8)
            continue
        for ev in items:
            ev_title = ev.get("title_ar") or ev.get("title_en") or ""
            add_p(ev_title, bold=True, size=12, after=2)
            chips = []
            chips.append(_type_label(ev.get("evidence_type")))
            sub_name = sub_map.get(ev.get("subject_id"), "") if ev.get("subject_id") else ""
            cls_name = cls_map.get(ev.get("class_id"), "") if ev.get("class_id") else ""
            if sub_name:
                chips.append(f"المادة: {sub_name}")
            if cls_name:
                chips.append(f"الصف: {cls_name}")
            d = ev.get("date") or (ev.get("created_at") or "")[:10]
            if d:
                chips.append(f"التاريخ: {d}")
            chips.append("تلقائي" if ev.get("source") == "auto" else "إضافة يدوية")
            add_p(" • ".join(chips), color="6B7280", size=10, after=2)
            ev_desc = ev.get("description_ar") or ev.get("description_en") or ""
            if ev_desc:
                add_p(ev_desc, size=11, after=2)
            file_url = ev.get("file_url") or ""
            if file_url:
                file_name = ev.get("file_name") or "ملف مرفق"
                if file_url.startswith("http://") or file_url.startswith("https://"):
                    add_p(f"المرفق: {file_name} — {file_url}", color="1FB1A8", size=10, after=8)
                else:
                    add_p(f"المرفق: {file_name}", color="1FB1A8", size=10, after=8)
            else:
                add_p("", after=4)

    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)
    pretty = f"portfolio_{_safe_filename_part(teacher_name)}_{today}.docx"
    ascii_n = f"portfolio_{today}.docx"
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers=_attachment_headers(pretty, ascii_n),
    )


@router.get("/teacher/portfolio/export")
async def export_portfolio_pdf(
    format: str = "pdf",
    current_user: dict = Depends(get_current_user),
):
    """Export the teacher's full portfolio (intro, vision/mission/values, CV,
    and every evidence with full details) as a downloadable file.

    Supported formats (via ?format=): pdf (default), docx, html.
    """
    fmt = (format or "pdf").lower().strip()
    if fmt not in ("pdf", "docx", "html"):
        raise HTTPException(status_code=400, detail="format must be one of: pdf, docx, html")

    if current_user["role"] not in ("teacher", "platform_admin", "school_principal", "school_admin", "independent_teacher"):
        raise HTTPException(status_code=403, detail="غير مصرح")

    teacher_id = current_user["id"]
    school_id = current_user.get("tenant_id")

    meta = await _load_meta(teacher_id)
    profile = await _load_teacher_profile(current_user)
    portfolio = await _engine.get_teacher_portfolio(teacher_id, school_id)
    progress = await _engine.get_portfolio_progress(teacher_id, school_id)

    query: Dict[str, Any] = {"teacher_id": teacher_id}
    if school_id:
        query["school_id"] = school_id
    evidence_list = await gd_find(db.session, "portfolio_evidence", query,
                                   order_by="created_at", desc_order=True, limit=5000)

    class_ids = {e.get("class_id") for e in evidence_list if e.get("class_id")}
    subject_ids = {e.get("subject_id") for e in evidence_list if e.get("subject_id")}
    cls_map, sub_map = await _lookup_class_subject_names(class_ids, subject_ids)

    if fmt == "docx":
        return _export_portfolio_docx(profile, meta, evidence_list, cls_map, sub_map, current_user)
    if fmt == "html":
        return _export_portfolio_html(profile, meta, evidence_list, cls_map, sub_map, current_user)

    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_RIGHT, TA_CENTER, TA_LEFT
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak,
        KeepTogether, HRFlowable,
    )

    font = _ensure_arabic_font()
    buf = io.BytesIO()

    BRAND_NAVY = colors.HexColor("#0E3A5F")
    BRAND_TURQ = colors.HexColor("#1FB1A8")
    BRAND_LIGHT = colors.HexColor("#F0F9FA")
    GREY_BG = colors.HexColor("#F7F7F8")
    GREY_BORDER = colors.HexColor("#E5E7EB")
    TEXT_MUTED = colors.HexColor("#6B7280")

    def _on_page(canvas, doc):
        canvas.saveState()
        # Header strip
        canvas.setFillColor(BRAND_NAVY)
        canvas.rect(0, A4[1] - 18, A4[0], 18, stroke=0, fill=1)
        canvas.setFillColor(colors.white)
        canvas.setFont(font, 9)
        teacher_label = _ar(f"ملف الإنجاز المهني — {profile.get('full_name') or current_user.get('full_name') or ''}")
        canvas.drawRightString(A4[0] - 24, A4[1] - 13, teacher_label)
        canvas.drawString(24, A4[1] - 13, "NASSAQ")
        # Footer page number
        canvas.setFillColor(TEXT_MUTED)
        canvas.setFont(font, 8)
        canvas.drawCentredString(A4[0] / 2, 14, _ar(f"صفحة {doc.page}"))
        canvas.restoreState()

    doc = SimpleDocTemplate(buf, pagesize=A4, rightMargin=32, leftMargin=32,
                            topMargin=44, bottomMargin=28)
    styles = getSampleStyleSheet()
    h1 = ParagraphStyle("H1", parent=styles["Heading1"], fontName=font,
                        alignment=TA_CENTER, fontSize=22, textColor=BRAND_NAVY, spaceAfter=4)
    h2 = ParagraphStyle("H2", parent=styles["Heading2"], fontName=font,
                        alignment=TA_RIGHT, fontSize=15, textColor=BRAND_NAVY,
                        spaceBefore=14, spaceAfter=6)
    h3 = ParagraphStyle("H3", parent=styles["Heading3"], fontName=font,
                        alignment=TA_RIGHT, fontSize=12, textColor=BRAND_NAVY,
                        spaceBefore=6, spaceAfter=4)
    body = ParagraphStyle("Body", parent=styles["Normal"], fontName=font,
                          alignment=TA_RIGHT, fontSize=11, leading=18, textColor=colors.HexColor("#1F2937"))
    body_l = ParagraphStyle("BodyL", parent=body, alignment=TA_LEFT)
    small = ParagraphStyle("Small", parent=styles["Normal"], fontName=font,
                           alignment=TA_RIGHT, fontSize=9, textColor=TEXT_MUTED, leading=14)
    label_style = ParagraphStyle("Label", parent=body, fontSize=9, textColor=TEXT_MUTED, leading=12)
    value_style = ParagraphStyle("Value", parent=body, fontSize=10, leading=14)
    chip_auto = ParagraphStyle("ChipAuto", parent=body, fontSize=9, textColor=colors.white, alignment=TA_CENTER)
    chip_manual = ParagraphStyle("ChipManual", parent=body, fontSize=9, textColor=colors.white, alignment=TA_CENTER)

    def _fmt_date(v):
        if not v:
            return ""
        if isinstance(v, datetime):
            return v.strftime("%Y-%m-%d")
        s = str(v)
        return s.split("T")[0][:10]

    def _kv_table(rows):
        """rows: list of (label_ar, value_ar). Returns a 2-col table."""
        data = [[Paragraph(_ar(v or "—"), value_style), Paragraph(_ar(k), label_style)] for k, v in rows]
        tbl = Table(data, colWidths=[None, 110])
        tbl.setStyle(TableStyle([
            ("BACKGROUND", (1, 0), (1, -1), GREY_BG),
            ("BOX", (0, 0), (-1, -1), 0.4, GREY_BORDER),
            ("INNERGRID", (0, 0), (-1, -1), 0.3, GREY_BORDER),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("FONTNAME", (0, 0), (-1, -1), font),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        return tbl

    story: List[Any] = []
    teacher_name = profile.get("full_name") or current_user.get("full_name") or ""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # ================= COVER =================
    story.append(Spacer(1, 30))
    story.append(Paragraph(_ar("ملف الإنجاز المهني"), h1))
    story.append(Paragraph(_ar("Professional Portfolio"),
        ParagraphStyle("sub", parent=h1, fontSize=12, textColor=BRAND_TURQ, spaceAfter=18)))

    if teacher_name:
        story.append(Paragraph(_ar(teacher_name),
            ParagraphStyle("name", parent=h1, fontSize=18, textColor=BRAND_NAVY, spaceAfter=6)))

    profile_rows = [
        ("الاسم الكامل", profile.get("full_name")),
        ("البريد الإلكتروني", profile.get("email")),
        ("رقم الهاتف", profile.get("phone")),
        ("التخصص", profile.get("specialization") or profile.get("subject")),
        ("المرتبة الوظيفية", profile.get("rank")),
        ("المؤهل العلمي", profile.get("qualification")),
        ("سنوات الخبرة", str(profile.get("years_of_experience") or "")),
    ]
    profile_rows = [(k, v) for k, v in profile_rows if v]
    if profile_rows:
        story.append(Spacer(1, 8))
        story.append(_kv_table(profile_rows))

    story.append(Spacer(1, 12))
    story.append(Paragraph(_ar(f"تاريخ التصدير: {today}"), small))
    story.append(PageBreak())

    # ================= OVERVIEW =================
    story.append(Paragraph(_ar("نظرة عامة"), h2))
    overall = progress.get("overall_percent", portfolio.get("coverage_percent", 0))
    total_ev = portfolio.get("total_evidence", len(evidence_list))
    auto_c = portfolio.get("auto_count", sum(1 for e in evidence_list if (e.get("source") or "auto") == "auto"))
    manual_c = portfolio.get("manual_count", sum(1 for e in evidence_list if e.get("source") == "manual"))

    summary_data = [[
        Paragraph(_ar(f"{overall}%"), ParagraphStyle("bignum", parent=body, fontSize=18, alignment=TA_CENTER, textColor=BRAND_TURQ)),
        Paragraph(_ar(f"{total_ev}"), ParagraphStyle("bignum2", parent=body, fontSize=18, alignment=TA_CENTER, textColor=BRAND_NAVY)),
        Paragraph(_ar(f"{auto_c}"), ParagraphStyle("bignum3", parent=body, fontSize=18, alignment=TA_CENTER, textColor=colors.HexColor("#D97706"))),
        Paragraph(_ar(f"{manual_c}"), ParagraphStyle("bignum4", parent=body, fontSize=18, alignment=TA_CENTER, textColor=colors.HexColor("#2563EB"))),
    ], [
        Paragraph(_ar("التقدم العام"), ParagraphStyle("lab", parent=small, alignment=TA_CENTER)),
        Paragraph(_ar("إجمالي الشواهد"), ParagraphStyle("lab", parent=small, alignment=TA_CENTER)),
        Paragraph(_ar("شواهد تلقائية"), ParagraphStyle("lab", parent=small, alignment=TA_CENTER)),
        Paragraph(_ar("شواهد يدوية"), ParagraphStyle("lab", parent=small, alignment=TA_CENTER)),
    ]]
    summary_tbl = Table(summary_data, colWidths=[125, 125, 125, 125])
    summary_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), BRAND_LIGHT),
        ("BOX", (0, 0), (-1, -1), 0.6, BRAND_TURQ),
        ("INNERGRID", (0, 0), (-1, -1), 0.3, BRAND_TURQ),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("FONTNAME", (0, 0), (-1, -1), font),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(summary_tbl)
    story.append(Spacer(1, 10))

    # Per-section breakdown table
    breakdown_rows = [[
        Paragraph(_ar("النسبة"), ParagraphStyle("th", parent=body, alignment=TA_CENTER, fontSize=10, textColor=colors.white)),
        Paragraph(_ar("عدد الشواهد"), ParagraphStyle("th", parent=body, alignment=TA_CENTER, fontSize=10, textColor=colors.white)),
        Paragraph(_ar("القسم"), ParagraphStyle("th", parent=body, alignment=TA_RIGHT, fontSize=10, textColor=colors.white)),
    ]]
    sub_counts = {}
    for sub_key, type_keys in EVIDENCE_SUBSECTIONS_V2.items():
        items = [e for e in evidence_list if e.get("evidence_type") in type_keys]
        sub_counts[sub_key] = (len(items), len(type_keys))
    for sub_key in EVIDENCE_SUBSECTIONS_V2.keys():
        count, total_types = sub_counts.get(sub_key, (0, 0))
        covered_types = len({e.get("evidence_type") for e in evidence_list if e.get("evidence_type") in EVIDENCE_SUBSECTIONS_V2.get(sub_key, [])})
        pct = round((covered_types / total_types) * 100) if total_types else 0
        breakdown_rows.append([
            Paragraph(_ar(f"{pct}%"), ParagraphStyle("td", parent=body, alignment=TA_CENTER, fontSize=10)),
            Paragraph(_ar(str(count)), ParagraphStyle("td", parent=body, alignment=TA_CENTER, fontSize=10)),
            Paragraph(_ar(_SUBSECTION_TITLES_AR.get(sub_key, sub_key)), ParagraphStyle("td", parent=body, alignment=TA_RIGHT, fontSize=10)),
        ])
    breakdown_tbl = Table(breakdown_rows, colWidths=[80, 90, None])
    breakdown_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), BRAND_NAVY),
        ("BOX", (0, 0), (-1, -1), 0.4, GREY_BORDER),
        ("INNERGRID", (0, 0), (-1, -1), 0.3, GREY_BORDER),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("FONTNAME", (0, 0), (-1, -1), font),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, GREY_BG]),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(Paragraph(_ar("توزيع الشواهد حسب الأقسام"), h3))
    story.append(breakdown_tbl)

    # ================= INTRO =================
    intro_text = (meta.get("intro") or "").strip()
    if intro_text:
        story.append(PageBreak())
        story.append(Paragraph(_ar("١. المقدمة التعريفية"), h2))
        story.append(HRFlowable(width="100%", thickness=1, color=BRAND_TURQ, spaceAfter=8))
        story.append(Paragraph(_ar(intro_text), body))

    # ================= VMV =================
    vision = (meta.get("vision") or "").strip()
    mission = (meta.get("mission") or "").strip()
    values = (meta.get("values") or "").strip()
    if vision or mission or values:
        story.append(PageBreak())
        story.append(Paragraph(_ar("٢. الرؤية والرسالة والقيم"), h2))
        story.append(HRFlowable(width="100%", thickness=1, color=BRAND_TURQ, spaceAfter=8))
        if vision:
            story.append(Paragraph(_ar("الرؤية"), h3))
            story.append(Paragraph(_ar(vision), body))
        if mission:
            story.append(Paragraph(_ar("الرسالة"), h3))
            story.append(Paragraph(_ar(mission), body))
        if values:
            story.append(Paragraph(_ar("القيم"), h3))
            story.append(Paragraph(_ar(values), body))

    # ================= CV =================
    auto_cv = _auto_cv_from_evidence(evidence_list)
    cv_buckets = [
        ("training_attended", "الدورات التدريبية الحاصل عليها"),
        ("training_delivered", "الدورات التدريبية المُقدَّمة"),
        ("award", "الجوائز والشهادات"),
        ("thank_letter", "خطابات الشكر"),
    ]
    manual_by_kind: Dict[str, List[Dict[str, Any]]] = {k: [] for k, _ in cv_buckets}
    for it in meta.get("cv_items", []):
        kind = it.get("kind")
        if kind in manual_by_kind:
            manual_by_kind[kind].append(it)

    has_cv = any(auto_cv.get(k) or manual_by_kind.get(k) for k, _ in cv_buckets)
    if has_cv:
        story.append(PageBreak())
        story.append(Paragraph(_ar("٣. السيرة الذاتية"), h2))
        story.append(HRFlowable(width="100%", thickness=1, color=BRAND_TURQ, spaceAfter=8))
        for key, label in cv_buckets:
            items = list(auto_cv.get(key, [])) + list(manual_by_kind.get(key, []))
            if not items:
                continue
            story.append(Paragraph(_ar(label), h3))
            cv_rows = [[
                Paragraph(_ar("التاريخ"), ParagraphStyle("th", parent=body, alignment=TA_CENTER, fontSize=9, textColor=colors.white)),
                Paragraph(_ar("الجهة / الساعات"), ParagraphStyle("th", parent=body, alignment=TA_CENTER, fontSize=9, textColor=colors.white)),
                Paragraph(_ar("العنوان"), ParagraphStyle("th", parent=body, alignment=TA_RIGHT, fontSize=9, textColor=colors.white)),
            ]]
            for it in items:
                title = it.get("title") or it.get("title_ar") or it.get("name") or ""
                org = it.get("organization") or ""
                hours = it.get("hours")
                org_part = org
                if hours:
                    org_part = (org + " — " if org else "") + f"{hours} ساعة"
                date = _fmt_date(it.get("date") or it.get("created_at"))
                cv_rows.append([
                    Paragraph(_ar(date or "—"), ParagraphStyle("td", parent=body, alignment=TA_CENTER, fontSize=10)),
                    Paragraph(_ar(org_part or "—"), ParagraphStyle("td", parent=body, alignment=TA_CENTER, fontSize=10)),
                    Paragraph(_ar(title or "—"), ParagraphStyle("td", parent=body, alignment=TA_RIGHT, fontSize=10)),
                ])
            cv_tbl = Table(cv_rows, colWidths=[80, 140, None])
            cv_tbl.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), BRAND_NAVY),
                ("BOX", (0, 0), (-1, -1), 0.4, GREY_BORDER),
                ("INNERGRID", (0, 0), (-1, -1), 0.3, GREY_BORDER),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, GREY_BG]),
                ("FONTNAME", (0, 0), (-1, -1), font),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]))
            story.append(cv_tbl)
            story.append(Spacer(1, 6))

    # ================= EVIDENCES =================
    if evidence_list:
        story.append(PageBreak())
        story.append(Paragraph(_ar("٤. شواهد الإنجاز"), h2))
        story.append(HRFlowable(width="100%", thickness=1, color=BRAND_TURQ, spaceAfter=8))
        story.append(Paragraph(_ar(f"إجمالي الشواهد المُسجَّلة خلال العام: {len(evidence_list)}"), small))
        story.append(Spacer(1, 6))

        for sub_key, type_keys in EVIDENCE_SUBSECTIONS_V2.items():
            items = [e for e in evidence_list if e.get("evidence_type") in type_keys]
            if not items:
                continue
            color_hex = _SUBSECTION_COLORS.get(sub_key, "#0E3A5F")
            section_color = colors.HexColor(color_hex)
            sub_title = _SUBSECTION_TITLES_AR.get(sub_key, sub_key)

            # Section header banner
            header_tbl = Table([[
                Paragraph(_ar(f"{len(items)}"),
                          ParagraphStyle("cnt", parent=body, alignment=TA_CENTER,
                                         fontSize=14, textColor=colors.white)),
                Paragraph(_ar(sub_title),
                          ParagraphStyle("hdr", parent=body, alignment=TA_RIGHT,
                                         fontSize=14, textColor=colors.white)),
            ]], colWidths=[55, None])
            header_tbl.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), section_color),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("FONTNAME", (0, 0), (-1, -1), font),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
            ]))
            story.append(header_tbl)
            story.append(Spacer(1, 6))

            for idx, ev in enumerate(items, start=1):
                title = ev.get("title_ar") or ev.get("title_en") or ev.get("title") or "بدون عنوان"
                desc_ar = ev.get("description_ar") or ""
                desc_en = ev.get("description_en") or ""
                date = _fmt_date(ev.get("date") or ev.get("created_at"))
                source = ev.get("source") or ("auto" if ev.get("auto_generated") else "manual")
                src_label = "تلقائي" if source == "auto" else "يدوي"
                ev_type = ev.get("evidence_type", "")
                type_label = _type_label(ev_type)
                file_name = ev.get("file_name") or ""
                file_url = ev.get("file_url") or ""
                file_kind = ev.get("file_kind") or ""
                cls_name = cls_map.get(str(ev.get("class_id") or ""), "")
                sub_name = sub_map.get(str(ev.get("subject_id") or ""), "")
                metadata = ev.get("metadata") or {}

                # Card header (number + title + source chip)
                src_color = colors.HexColor("#10B981" if source == "auto" else "#2563EB")
                card_header = Table([[
                    Paragraph(_ar(src_label),
                              ParagraphStyle("chip", parent=body, alignment=TA_CENTER,
                                             fontSize=9, textColor=colors.white)),
                    Paragraph(_ar(f"{idx}. {title}"),
                              ParagraphStyle("evt", parent=body, fontSize=12,
                                             textColor=BRAND_NAVY, alignment=TA_RIGHT)),
                ]], colWidths=[55, None])
                card_header.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (0, 0), src_color),
                    ("BACKGROUND", (1, 0), (1, 0), GREY_BG),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("BOX", (0, 0), (-1, -1), 0.4, GREY_BORDER),
                    ("FONTNAME", (0, 0), (-1, -1), font),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ]))

                # KV details
                rows = []
                if type_label:
                    rows.append(("نوع الشاهد", type_label))
                if date:
                    rows.append(("التاريخ", date))
                rows.append(("المصدر", src_label))
                if cls_name:
                    rows.append(("الفصل", cls_name))
                if sub_name:
                    rows.append(("المادة", sub_name))
                def _safe_url(u: str) -> str:
                    if not u:
                        return ""
                    if u.startswith("data:"):
                        return "(ملف مضمَّن داخل النظام)"
                    if len(u) > 120:
                        return u[:117] + "..."
                    return u
                safe_url = _safe_url(file_url)
                disp_name = (file_name or "")[:120]
                if disp_name or safe_url:
                    rows.append(("الملف المرفق", disp_name or safe_url))
                if file_kind:
                    rows.append(("نوع الملف", file_kind))
                if safe_url and safe_url != disp_name:
                    rows.append(("الرابط", safe_url))
                # Surface common metadata fields
                if isinstance(metadata, dict):
                    for mk, mlabel in [
                        ("organization", "الجهة"),
                        ("hours", "عدد الساعات"),
                        ("location", "المكان"),
                        ("participants", "عدد المشاركين"),
                        ("score", "الدرجة"),
                        ("grade", "الصف"),
                        ("notes", "ملاحظات"),
                    ]:
                        v = metadata.get(mk)
                        if v not in (None, "", []):
                            rows.append((mlabel, str(v)))

                card_body = _kv_table(rows)

                pieces = [card_header, card_body]
                if desc_ar:
                    pieces.append(Spacer(1, 4))
                    pieces.append(Paragraph(_ar("الوصف"), label_style))
                    pieces.append(Paragraph(_ar(desc_ar), body))
                if desc_en and desc_en.strip() and desc_en.strip() != desc_ar.strip():
                    pieces.append(Paragraph(_ar("Description (EN):"), label_style))
                    pieces.append(Paragraph(desc_en, body_l))
                pieces.append(Spacer(1, 10))

                story.append(KeepTogether(pieces))
            story.append(Spacer(1, 4))

    if not evidence_list and not intro_text and not (vision or mission or values) and not has_cv:
        story.append(Paragraph(_ar("لا توجد شواهد أو محتوى مضاف بعد."), body))

    doc.build(story, onFirstPage=_on_page, onLaterPages=_on_page)
    buf.seek(0)
    from urllib.parse import quote as _urlquote
    pretty_name = (teacher_name or "teacher").strip().replace(" ", "_")
    pretty_filename = f"portfolio_{pretty_name}_{today}.pdf"
    ascii_filename = f"portfolio_{today}.pdf"
    encoded = _urlquote(pretty_filename)
    cd = f"attachment; filename=\"{ascii_filename}\"; filename*=UTF-8''{encoded}"
    return StreamingResponse(
        buf,
        media_type="application/pdf",
        headers={"Content-Disposition": cd},
    )


# ---- Intro ----

class IntroSave(BaseModel):
    text: str = Field("", max_length=2000)


@router.put("/teacher/portfolio/intro")
async def save_intro(payload: IntroSave, current_user: dict = Depends(get_current_user)):
    if current_user["role"] not in ("teacher", "independent_teacher"):
        raise HTTPException(status_code=403, detail="غير مصرح")
    teacher_id = current_user["id"]
    intro_text = (payload.text or "").strip()
    try:
        await _lock_teacher_meta(teacher_id)
        meta = await _save_meta(teacher_id, current_user.get("tenant_id"),
                                {"intro": intro_text})
    except Exception as exc:
        logger.error("save_intro failed for teacher=%s: %s", teacher_id, exc)
        raise HTTPException(status_code=500, detail="فشل حفظ المقدمة، يرجى المحاولة مرة أخرى")
    saved = meta.get("intro", "")
    if saved != intro_text:
        logger.error("save_intro keying mismatch: sent=%r stored=%r teacher=%s",
                     intro_text[:40], saved[:40], teacher_id)
        raise HTTPException(status_code=500, detail="فشل حفظ المقدمة، يرجى المحاولة مرة أخرى")
    return {"success": True, "intro": saved}


# ---- Vision / Mission / Values ----

class VMVSave(BaseModel):
    vision: str = Field("", max_length=1000)
    mission: str = Field("", max_length=1000)
    values: str = Field("", max_length=1000)


@router.put("/teacher/portfolio/vmv")
async def save_vmv(payload: VMVSave, current_user: dict = Depends(get_current_user)):
    if current_user["role"] not in ("teacher", "independent_teacher"):
        raise HTTPException(status_code=403, detail="غير مصرح")
    await _lock_teacher_meta(current_user["id"])
    meta = await _save_meta(current_user["id"], current_user.get("tenant_id"), {
        "vision": (payload.vision or "").strip(),
        "mission": (payload.mission or "").strip(),
        "values": (payload.values or "").strip(),
    })
    return {
        "success": True,
        "vmv": {
            "vision": meta.get("vision", ""),
            "mission": meta.get("mission", ""),
            "values": meta.get("values", ""),
        }
    }


# ---- CV manual items ----

class CVItemCreate(BaseModel):
    kind: str = Field(..., description="training_attended | training_delivered | award | thank_letter")
    title: str = Field(..., min_length=2, max_length=300)
    organization: Optional[str] = Field(None, max_length=200)
    date: Optional[str] = None
    hours: Optional[int] = Field(None, ge=0, le=100000)
    description: Optional[str] = Field(None, max_length=1000)
    file_url: Optional[str] = None
    file_name: Optional[str] = Field(None, max_length=300)


@router.post("/teacher/portfolio/cv-item")
async def add_cv_item(payload: CVItemCreate, current_user: dict = Depends(get_current_user)):
    if current_user["role"] not in ("teacher", "independent_teacher"):
        raise HTTPException(status_code=403, detail="غير مصرح")
    if payload.kind not in CV_KINDS:
        raise HTTPException(status_code=422, detail="invalid_kind")

    # Validate optional file_url: same caps & schemes as manual evidence attachments
    if payload.file_url:
        MAX_DATA_URL = 14 * 1024 * 1024  # base64 of 10 MB ≈ 13.3 MB
        if len(payload.file_url) > MAX_DATA_URL:
            raise HTTPException(status_code=413, detail="file_too_large")
        if not (payload.file_url.startswith("data:application/pdf;base64,")
                or payload.file_url.startswith("data:application/msword;base64,")
                or payload.file_url.startswith("data:application/vnd.openxmlformats-officedocument.wordprocessingml.document;base64,")
                or payload.file_url.startswith("data:image/")
                or payload.file_url.startswith("https://")
                or payload.file_url.startswith("http://")):
            raise HTTPException(status_code=422, detail="unsupported_file_type")

    await _lock_teacher_meta(current_user["id"])
    meta = await _load_meta(current_user["id"])
    items = list(meta.get("cv_items") or [])
    new_item = {
        "id": str(_uuid.uuid4()),
        "kind": payload.kind,
        "title": payload.title.strip(),
        "organization": (payload.organization or "").strip() or None,
        "date": payload.date or None,
        "hours": payload.hours,
        "description": (payload.description or "").strip() or None,
        "file_url": (payload.file_url or "").strip() or None,
        "file_name": (payload.file_name or "").strip() or None,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    items.append(new_item)
    await _save_meta(current_user["id"], current_user.get("tenant_id"), {"cv_items": items})
    return {"success": True, "item": new_item}


@router.delete("/teacher/portfolio/cv-item/{item_id}")
async def delete_cv_item(item_id: str, current_user: dict = Depends(get_current_user)):
    if current_user["role"] not in ("teacher", "independent_teacher"):
        raise HTTPException(status_code=403, detail="غير مصرح")
    await _lock_teacher_meta(current_user["id"])
    meta = await _load_meta(current_user["id"])
    items = list(meta.get("cv_items") or [])
    new_items = [it for it in items if it.get("id") != item_id]
    if len(new_items) == len(items):
        raise HTTPException(status_code=404, detail="not_found")
    await _save_meta(current_user["id"], current_user.get("tenant_id"), {"cv_items": new_items})
    return {"success": True}


# ---- AI generators (Hakim) ----

async def _hakim_call(
    field: str,
    mode: str,
    text: str,
    context: Dict[str, Any],
    *,
    tenant_id: Optional[str] = None,
) -> str:
    try:
        from services.hakim_llm_service import hakim_generate
        result = await hakim_generate(
            mode=mode, field=field, text=text, context=context, language="ar",
            tenant_id=tenant_id,
        )
    except Exception as e:
        logger.warning(f"[Hakim] portfolio {field}/{mode} failed: {e}")
        raise HTTPException(status_code=502, detail="HAKIM_FAILED")

    if result.get("success"):
        return result["text"]

    reason = result.get("reason") or "HAKIM_FAILED"
    if reason in ("AI_DISABLED", "AI_DISABLED_BY_TENANT", "AI_CONSENT_UNVERIFIED"):
        raise HTTPException(status_code=503, detail=reason)
    if reason == "TEXT_TOO_SHORT":
        raise HTTPException(status_code=422, detail="TEXT_TOO_SHORT")
    raise HTTPException(status_code=502, detail="HAKIM_FAILED")


class AIGenerateRequest(BaseModel):
    mode: str = Field("generate", description="generate | improve")
    text: Optional[str] = ""


class EvidenceDescAIRequest(BaseModel):
    mode: str = Field("generate", description="generate | improve")
    text: Optional[str] = ""
    title: Optional[str] = ""
    evidence_type: Optional[str] = ""
    section_key: Optional[str] = ""


@router.post("/teacher/portfolio/generate-evidence-desc")
async def generate_evidence_description(
    payload: EvidenceDescAIRequest,
    current_user: dict = Depends(get_current_user),
):
    if current_user["role"] not in ("teacher", "independent_teacher"):
        raise HTTPException(status_code=403, detail="غير مصرح")
    mode = (payload.mode or "generate").strip().lower()
    if mode not in ("generate", "improve"):
        raise HTTPException(status_code=422, detail="invalid_mode")
    profile = await _load_teacher_profile(current_user)
    context = {
        "teacher_name": profile.get("full_name"),
        "subject": profile.get("specialization") or profile.get("subject"),
        "evidence_title": (payload.title or "").strip(),
        "evidence_type": (payload.evidence_type or "").strip(),
        "section": (payload.section_key or "").strip(),
    }
    text_in = (payload.text or "").strip()
    out = await _hakim_call(
        "evidence_description", mode, text_in, context,
        tenant_id=current_user.get("tenant_id"),
    )
    return {"success": True, "text": out}


@router.post("/teacher/portfolio/generate-intro")
async def generate_intro(payload: AIGenerateRequest, current_user: dict = Depends(get_current_user)):
    if current_user["role"] not in ("teacher", "independent_teacher"):
        raise HTTPException(status_code=403, detail="غير مصرح")
    mode = (payload.mode or "generate").strip().lower()
    if mode not in ("generate", "improve"):
        raise HTTPException(status_code=422, detail="invalid_mode")

    profile = await _load_teacher_profile(current_user)
    context = {
        "teacher_name": profile.get("full_name"),
        "subject": profile.get("specialization") or profile.get("subject"),
        "years_of_experience": profile.get("years_of_experience"),
        "qualification": profile.get("qualification"),
    }
    text_in = (payload.text or "").strip()
    out = await _hakim_call(
        "portfolio_intro", mode, text_in, context,
        tenant_id=current_user.get("tenant_id"),
    )

    now = datetime.now(timezone.utc).isoformat()
    await _save_meta(current_user["id"], current_user.get("tenant_id"),
                     {"intro": out, "intro_generated_at": now})
    return {"success": True, "text": out}


class VMVGenerateRequest(BaseModel):
    mode: str = Field("generate", description="generate | improve")
    vision: Optional[str] = ""
    mission: Optional[str] = ""
    values: Optional[str] = ""


@router.post("/teacher/portfolio/generate-vmv")
async def generate_vmv(payload: VMVGenerateRequest, current_user: dict = Depends(get_current_user)):
    if current_user["role"] not in ("teacher", "independent_teacher"):
        raise HTTPException(status_code=403, detail="غير مصرح")
    mode = (payload.mode or "generate").strip().lower()
    if mode not in ("generate", "improve"):
        raise HTTPException(status_code=422, detail="invalid_mode")

    profile = await _load_teacher_profile(current_user)
    context = {
        "teacher_name": profile.get("full_name"),
        "subject": profile.get("specialization") or profile.get("subject"),
        "years_of_experience": profile.get("years_of_experience"),
    }

    async def _gen_or_keep(field: str, current_text: str) -> str:
        """For 'generate' mode always (re)generate. For 'improve' mode, only call
        Hakim when current_text has enough content; otherwise keep the existing value
        so an empty sibling field doesn't fail the whole VMV request."""
        text_in = (current_text or "").strip()
        if mode == "improve" and len(text_in) < 5:
            return text_in
        return await _hakim_call(
            field, mode, text_in, context,
            tenant_id=current_user.get("tenant_id"),
        )

    vision = await _gen_or_keep("portfolio_vision", payload.vision or "")
    mission = await _gen_or_keep("portfolio_mission", payload.mission or "")
    values = await _gen_or_keep("portfolio_values", payload.values or "")

    await _lock_teacher_meta(current_user["id"])
    now = datetime.now(timezone.utc).isoformat()
    await _save_meta(current_user["id"], current_user.get("tenant_id"), {
        "vision": vision, "mission": mission, "values": values,
        "vmv_generated_at": now,
    })
    return {"success": True, "vision": vision, "mission": mission, "values": values}
