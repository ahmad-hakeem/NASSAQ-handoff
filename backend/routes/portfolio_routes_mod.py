"""
NASSAQ Route Module: Teacher Portfolio & Evidence endpoints
"""
from fastapi import APIRouter, HTTPException, Depends, Query, Body
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
import logging

from dependencies import db, get_current_user, require_roles, UserRole
from engines.portfolio_evidence_engine import (
    PortfolioEvidenceEngine, ALL_EVIDENCE_TYPES, EVIDENCE_SECTIONS, SECTION_FOR_TYPE,
)

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


@router.post("/teacher/portfolio/evidence")
async def add_evidence(
    data: ManualEvidenceCreate,
    current_user: dict = Depends(get_current_user),
):
    if current_user["role"] != "teacher":
        raise HTTPException(status_code=403, detail="غير مصرح")
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
    field = (payload.field or "").strip().lower()
    if mode not in ("generate", "improve"):
        raise HTTPException(status_code=422, detail="invalid_mode")
    if field not in ("title", "description"):
        raise HTTPException(status_code=422, detail="invalid_field")

    text_in = (payload.text or "").strip()
    if mode == "improve" and len(text_in) < 5:
        raise HTTPException(status_code=422, detail="TEXT_TOO_SHORT")

    try:
        from openai import OpenAI
        import os
        api_key = os.environ.get("AI_INTEGRATIONS_OPENAI_API_KEY", "")
        base_url = os.environ.get("AI_INTEGRATIONS_OPENAI_BASE_URL", "")
        if not api_key:
            return {"success": False, "text": text_in, "reason": "AI_DISABLED"}

        client = OpenAI(api_key=api_key, base_url=base_url if base_url else None)

        evidence_label = (payload.evidence_type or "").replace("_", " ")
        ctx_lines = []
        if evidence_label:
            ctx_lines.append(f"نوع الشاهد: {evidence_label}")
        if payload.subject:
            ctx_lines.append(f"المادة: {payload.subject}")
        if payload.grade:
            ctx_lines.append(f"الصف: {payload.grade}")
        if field == "description" and payload.title:
            ctx_lines.append(f"عنوان الشاهد: {payload.title}")
        context_block = "\n".join(ctx_lines) if ctx_lines else "—"

        if field == "title":
            field_rule = (
                "عنوان موجز ودقيق لشاهد ملف إنجاز معلم، بحد أقصى جملة واحدة قصيرة (٤-١٢ كلمة)، "
                "بدون علامات اقتباس وبدون نقطة في النهاية."
            )
        else:
            field_rule = (
                "وصف مهني واضح لشاهد في ملف إنجاز معلم، من ٢ إلى ٤ جمل، يبيّن الهدف والمحتوى والأثر التعليمي، "
                "بأسلوب رسمي مهني خالٍ من المبالغة."
            )

        if mode == "generate":
            system_prompt = (
                "أنت 'حكيم'، المساعد الذكي في منصة نسّاق التعليمية. مهمتك إنشاء نص عربي رسمي للمعلمين "
                "يستخدم في ملف الإنجاز الوظيفي. اكتب بالعربية الفصحى فقط بدون أي لغة أخرى."
            )
            user_prompt = (
                f"السياق:\n{context_block}\n\n"
                f"المطلوب: {field_rule}\n\n"
                "أعد النص النهائي فقط دون أي مقدمات أو شروحات."
            )
        else:
            system_prompt = (
                "أنت 'حكيم'، المساعد الذكي في منصة نسّاق التعليمية. مهمتك تحسين نصوص ملف إنجاز المعلم "
                "لتصبح أوضح وأكثر مهنية مع الحفاظ على المعنى الأصلي وعدم اختراع معلومات جديدة. "
                "اكتب بالعربية الفصحى فقط."
            )
            user_prompt = (
                f"السياق:\n{context_block}\n\n"
                f"النص الأصلي:\n{text_in}\n\n"
                f"المطلوب: {field_rule}\n\n"
                "أعد النص المُحسَّن فقط دون أي مقدمات أو شروحات."
            )

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=400 if field == "description" else 80,
            temperature=0.6 if mode == "improve" else 0.75,
        )
        out = (response.choices[0].message.content or "").strip()
        out = out.strip('"').strip("'").strip()
        if not out:
            return {"success": False, "text": text_in, "reason": "EMPTY"}
        return {"success": True, "text": out}
    except Exception as e:
        logger.warning(f"[Hakim] portfolio evidence text {mode}/{field} failed: {e}")
        raise HTTPException(status_code=502, detail="HAKIM_FAILED")
