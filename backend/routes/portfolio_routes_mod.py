"""
NASSAQ Route Module: Teacher Portfolio & Evidence endpoints
"""
from fastapi import APIRouter, HTTPException, Depends, Query, Body, UploadFile, File
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
import logging

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
    metadata: Optional[Dict[str, Any]] = None


@router.get("/teacher/portfolio")
async def get_teacher_portfolio(current_user: dict = Depends(get_current_user)):
    if current_user["role"] not in ("teacher", "platform_admin", "school_principal", "school_admin"):
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
    if current_user["role"] not in ("teacher", "platform_admin", "school_principal", "school_admin"):
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
    if current_user["role"] != "teacher":
        raise HTTPException(status_code=403, detail="غير مصرح")

    import base64
    MAX_SIZE = 10 * 1024 * 1024  # 10 MB
    ALLOWED_TYPES = {
        "application/pdf",
        "image/jpeg", "image/png", "image/gif", "image/webp",
        "video/mp4", "video/webm", "video/quicktime",
    }
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail="صيغة الملف غير مدعومة")

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
        "file_url": f"data:{file.content_type};base64,{encoded}",
        "file_name": file.filename,
        "content_type": file.content_type,
        "size": len(content),
    }


@router.post("/teacher/portfolio/evidence")
async def add_evidence(
    data: ManualEvidenceCreate,
    current_user: dict = Depends(get_current_user),
):
    if current_user["role"] != "teacher":
        raise HTTPException(status_code=403, detail="غير مصرح")
    if data.file_url:
        MAX_DATA_URL = 14 * 1024 * 1024  # base64 of 10 MB ≈ 13.3 MB
        if len(data.file_url) > MAX_DATA_URL:
            raise HTTPException(status_code=400, detail="حجم المرفق يتجاوز الحد المسموح")
        if not (data.file_url.startswith("data:application/pdf;base64,")
                or data.file_url.startswith("data:image/")
                or data.file_url.startswith("data:video/")
                or data.file_url.startswith("https://")
                or data.file_url.startswith("http://")):
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
    if current_user["role"] != "teacher":
        raise HTTPException(status_code=403, detail="غير مصرح")
    updates = {k: v for k, v in data.model_dump().items() if v is not None}
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
    if current_user["role"] != "teacher":
        raise HTTPException(status_code=403, detail="غير مصرح")
    result = await _engine.delete_evidence(evidence_id, current_user["id"])
    if not result.get("success"):
        raise HTTPException(status_code=404, detail=result.get("error", "not_found"))
    return result


@router.get("/teacher/portfolio/progress")
async def get_portfolio_progress(current_user: dict = Depends(get_current_user)):
    if current_user["role"] not in ("teacher", "platform_admin", "school_principal", "school_admin"):
        raise HTTPException(status_code=403, detail="غير مصرح")
    teacher_id = current_user["id"]
    school_id = current_user.get("tenant_id")
    progress = await _engine.get_portfolio_progress(teacher_id, school_id)
    return progress


@router.get("/teacher/portfolio/evidence-types")
async def get_evidence_types(current_user: dict = Depends(get_current_user)):
    if current_user["role"] not in ("teacher", "platform_admin", "school_principal", "school_admin"):
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
    if current_user["role"] not in ("teacher", "platform_admin", "school_principal", "school_admin"):
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
    if reason == "AI_DISABLED":
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
    payload = {
        "teacher_id": teacher_id,
        "school_id": school_id or "",
        "updated_at": now,
        **updates,
    }
    await gd_upsert(db.session, "teacher_portfolio_meta", {"teacher_id": teacher_id}, payload)
    return await _load_meta(teacher_id)


async def _load_teacher_profile(teacher_id: str) -> Dict[str, Any]:
    """Load lightweight teacher info used as context for AI generation and CV personal-data grid."""
    try:
        from pg_models import Teacher, User
        result = await db.session.execute(select(Teacher).where(Teacher.id == teacher_id))
        teacher = result.scalar_one_or_none()
        if not teacher:
            return {}
        user_res = await db.session.execute(select(User).where(User.id == teacher_id))
        user = user_res.scalar_one_or_none()
        return {
            "full_name": (getattr(user, "full_name", None) or getattr(teacher, "full_name", None) or ""),
            "email": getattr(user, "email", None) or "",
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
    if current_user["role"] != "teacher":
        raise HTTPException(status_code=403, detail="غير مصرح")

    teacher_id = current_user["id"]
    school_id = current_user.get("tenant_id")

    meta = await _load_meta(teacher_id)
    profile = await _load_teacher_profile(teacher_id)

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


# ---- Intro ----

class IntroSave(BaseModel):
    text: str = Field("", max_length=2000)


@router.put("/teacher/portfolio/intro")
async def save_intro(payload: IntroSave, current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "teacher":
        raise HTTPException(status_code=403, detail="غير مصرح")
    meta = await _save_meta(current_user["id"], current_user.get("tenant_id"),
                            {"intro": (payload.text or "").strip()})
    return {"success": True, "intro": meta.get("intro", "")}


# ---- Vision / Mission / Values ----

class VMVSave(BaseModel):
    vision: str = Field("", max_length=1000)
    mission: str = Field("", max_length=1000)
    values: str = Field("", max_length=1000)


@router.put("/teacher/portfolio/vmv")
async def save_vmv(payload: VMVSave, current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "teacher":
        raise HTTPException(status_code=403, detail="غير مصرح")
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


@router.post("/teacher/portfolio/cv-item")
async def add_cv_item(payload: CVItemCreate, current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "teacher":
        raise HTTPException(status_code=403, detail="غير مصرح")
    if payload.kind not in CV_KINDS:
        raise HTTPException(status_code=422, detail="invalid_kind")

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
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    items.append(new_item)
    await _save_meta(current_user["id"], current_user.get("tenant_id"), {"cv_items": items})
    return {"success": True, "item": new_item}


@router.delete("/teacher/portfolio/cv-item/{item_id}")
async def delete_cv_item(item_id: str, current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "teacher":
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

async def _hakim_call(field: str, mode: str, text: str, context: Dict[str, Any]) -> str:
    try:
        from services.hakim_llm_service import hakim_generate
        result = await hakim_generate(mode=mode, field=field, text=text, context=context, language="ar")
    except Exception as e:
        logger.warning(f"[Hakim] portfolio {field}/{mode} failed: {e}")
        raise HTTPException(status_code=502, detail="HAKIM_FAILED")

    if result.get("success"):
        return result["text"]

    reason = result.get("reason") or "HAKIM_FAILED"
    if reason == "AI_DISABLED":
        raise HTTPException(status_code=503, detail="AI_DISABLED")
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
    if current_user["role"] != "teacher":
        raise HTTPException(status_code=403, detail="غير مصرح")
    mode = (payload.mode or "generate").strip().lower()
    if mode not in ("generate", "improve"):
        raise HTTPException(status_code=422, detail="invalid_mode")
    profile = await _load_teacher_profile(current_user["id"])
    context = {
        "teacher_name": profile.get("full_name"),
        "subject": profile.get("specialization") or profile.get("subject"),
        "evidence_title": (payload.title or "").strip(),
        "evidence_type": (payload.evidence_type or "").strip(),
        "section": (payload.section_key or "").strip(),
    }
    text_in = (payload.text or "").strip()
    out = await _hakim_call("evidence_description", mode, text_in, context)
    return {"success": True, "text": out}


@router.post("/teacher/portfolio/generate-intro")
async def generate_intro(payload: AIGenerateRequest, current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "teacher":
        raise HTTPException(status_code=403, detail="غير مصرح")
    mode = (payload.mode or "generate").strip().lower()
    if mode not in ("generate", "improve"):
        raise HTTPException(status_code=422, detail="invalid_mode")

    profile = await _load_teacher_profile(current_user["id"])
    context = {
        "teacher_name": profile.get("full_name"),
        "subject": profile.get("specialization") or profile.get("subject"),
        "years_of_experience": profile.get("years_of_experience"),
        "qualification": profile.get("qualification"),
    }
    text_in = (payload.text or "").strip()
    out = await _hakim_call("portfolio_intro", mode, text_in, context)

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
    if current_user["role"] != "teacher":
        raise HTTPException(status_code=403, detail="غير مصرح")
    mode = (payload.mode or "generate").strip().lower()
    if mode not in ("generate", "improve"):
        raise HTTPException(status_code=422, detail="invalid_mode")

    profile = await _load_teacher_profile(current_user["id"])
    context = {
        "teacher_name": profile.get("full_name"),
        "subject": profile.get("specialization") or profile.get("subject"),
        "years_of_experience": profile.get("years_of_experience"),
    }

    vision = await _hakim_call("portfolio_vision", mode, (payload.vision or "").strip(), context)
    mission = await _hakim_call("portfolio_mission", mode, (payload.mission or "").strip(), context)
    values = await _hakim_call("portfolio_values", mode, (payload.values or "").strip(), context)

    now = datetime.now(timezone.utc).isoformat()
    await _save_meta(current_user["id"], current_user.get("tenant_id"), {
        "vision": vision, "mission": mission, "values": values,
        "vmv_generated_at": now,
    })
    return {"success": True, "vision": vision, "mission": mission, "values": values}
