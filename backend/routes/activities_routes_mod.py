"""
NASSAQ Route Module: Student Activities & Certificates/Awards CRUD
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime, timezone
import uuid

from dependencies import db, get_current_user, logger

router = APIRouter(prefix="/activities", tags=["activities"])
from engines.sql_utils import gd_find, gd_find_one, gd_insert, gd_insert_many, gd_update_one, gd_update_many, gd_count, gd_delete_one, gd_delete_many, gd_distinct


ACTIVITY_TYPES = ["academic", "sports", "arts", "community", "scientific", "cultural", "other"]


class ActivityCreate(BaseModel):
    name: str
    name_en: Optional[str] = None
    activity_type: str = "other"
    date: Optional[str] = None
    role: Optional[str] = None
    description: Optional[str] = None


class ActivityUpdate(BaseModel):
    name: Optional[str] = None
    name_en: Optional[str] = None
    activity_type: Optional[str] = None
    date: Optional[str] = None
    role: Optional[str] = None
    description: Optional[str] = None


class CertificateCreate(BaseModel):
    title: str
    title_en: Optional[str] = None
    date: Optional[str] = None
    issuing_body: Optional[str] = None
    description: Optional[str] = None
    image_url: Optional[str] = None


class CertificateUpdate(BaseModel):
    title: Optional[str] = None
    title_en: Optional[str] = None
    date: Optional[str] = None
    issuing_body: Optional[str] = None
    description: Optional[str] = None
    image_url: Optional[str] = None


@router.get("/student/{student_id}")
async def list_student_activities(
    student_id: str,
    school_id: str = Query(...),
    current_user: dict = Depends(get_current_user),
):
    """List a student's extracurricular activities.

    SECURITY: Activities are non-public student records. The caller must
    be the student themselves, a guardian, an assigned teacher, or a
    school admin. Cross-tenant access is rejected first; then an
    object-level check via can_view_student enforces the relationship.
    """
    tenant = current_user.get("tenant_id")
    if tenant and tenant != school_id:
        raise HTTPException(403, "غير مصرح")
    from utils.tenant_scope import can_view_student, require_can_view_student_sync_check
    allowed = await can_view_student(db.session, current_user, student_id)
    require_can_view_student_sync_check(allowed)
    records = await gd_find(db.session, "student_activities", {"student_id": student_id, "school_id": school_id}, order_by="date", desc_order=True, limit=500)
    for r in records:
        r.pop("_id", None)
    return records


@router.post("/student/{student_id}")
async def create_student_activity(
    student_id: str,
    data: ActivityCreate,
    school_id: str = Query(...),
    current_user: dict = Depends(get_current_user),
):
    tenant = current_user.get("tenant_id")
    if tenant and tenant != school_id:
        raise HTTPException(403, "غير مصرح")
    role = current_user.get("role", "")
    if role not in ("school_admin", "admin", "teacher", "super_admin"):
        raise HTTPException(403, "ليس لديك صلاحية")
    doc = {
        "id": str(uuid.uuid4()),
        "student_id": student_id,
        "school_id": school_id,
        "name": data.name,
        "name_en": data.name_en,
        "activity_type": data.activity_type if data.activity_type in ACTIVITY_TYPES else "other",
        "date": data.date,
        "role": data.role,
        "description": data.description,
        "created_by": current_user.get("user_id"),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    await gd_insert(db.session, "student_activities", doc)
    doc.pop("_id", None)
    return doc


@router.put("/{activity_id}")
async def update_activity(
    activity_id: str,
    data: ActivityUpdate,
    current_user: dict = Depends(get_current_user),
):
    role = current_user.get("role", "")
    if role not in ("school_admin", "admin", "teacher", "super_admin"):
        raise HTTPException(403, "ليس لديك صلاحية")
    tenant = current_user.get("tenant_id")
    if not tenant:
        raise HTTPException(400, "لم يتم تحديد المدرسة")
    update_fields = {"updated_at": datetime.now(timezone.utc).isoformat()}
    for field in ["name", "name_en", "activity_type", "date", "role", "description"]:
        val = getattr(data, field, None)
        if val is not None:
            update_fields[field] = val
    result = await gd_update_one(db.session, "student_activities", {"id": activity_id, "school_id": tenant}, update_fields)
    if result == 0:
        raise HTTPException(404, "النشاط غير موجود")
    return {"success": True, "message": "تم تحديث النشاط"}


@router.delete("/{activity_id}")
async def delete_activity(
    activity_id: str,
    current_user: dict = Depends(get_current_user),
):
    role = current_user.get("role", "")
    if role not in ("school_admin", "admin", "super_admin"):
        raise HTTPException(403, "ليس لديك صلاحية")
    tenant = current_user.get("tenant_id")
    if not tenant:
        raise HTTPException(400, "لم يتم تحديد المدرسة")
    result = await gd_delete_one(db.session, "student_activities", {"id": activity_id, "school_id": tenant})
    if result == 0:
        raise HTTPException(404, "النشاط غير موجود")
    return {"success": True, "message": "تم حذف النشاط"}


@router.get("/certificates/student/{student_id}")
async def list_student_certificates(
    student_id: str,
    school_id: str = Query(...),
    current_user: dict = Depends(get_current_user),
):
    """List a student's certificates and awards.

    SECURITY: Certificate records are non-public student data. The caller
    must be the student themselves, a guardian, an assigned teacher, or a
    school admin. Cross-tenant access is rejected first; then an
    object-level check via can_view_student enforces the relationship.
    """
    tenant = current_user.get("tenant_id")
    if tenant and tenant != school_id:
        raise HTTPException(403, "غير مصرح")
    from utils.tenant_scope import can_view_student, require_can_view_student_sync_check
    allowed = await can_view_student(db.session, current_user, student_id)
    require_can_view_student_sync_check(allowed)
    records = await gd_find(db.session, "student_certificates", {"student_id": student_id, "school_id": school_id}, order_by="date", desc_order=True, limit=500)
    for r in records:
        r.pop("_id", None)
    return records


@router.post("/certificates/student/{student_id}")
async def create_student_certificate(
    student_id: str,
    data: CertificateCreate,
    school_id: str = Query(...),
    current_user: dict = Depends(get_current_user),
):
    tenant = current_user.get("tenant_id")
    if tenant and tenant != school_id:
        raise HTTPException(403, "غير مصرح")
    role = current_user.get("role", "")
    if role not in ("school_admin", "admin", "teacher", "super_admin"):
        raise HTTPException(403, "ليس لديك صلاحية")
    doc = {
        "id": str(uuid.uuid4()),
        "student_id": student_id,
        "school_id": school_id,
        "title": data.title,
        "title_en": data.title_en,
        "date": data.date,
        "issuing_body": data.issuing_body,
        "description": data.description,
        "image_url": data.image_url,
        "created_by": current_user.get("user_id"),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    await gd_insert(db.session, "student_certificates", doc)
    doc.pop("_id", None)
    return doc


@router.put("/certificates/{certificate_id}")
async def update_certificate(
    certificate_id: str,
    data: CertificateUpdate,
    current_user: dict = Depends(get_current_user),
):
    role = current_user.get("role", "")
    if role not in ("school_admin", "admin", "teacher", "super_admin"):
        raise HTTPException(403, "ليس لديك صلاحية")
    tenant = current_user.get("tenant_id")
    if not tenant:
        raise HTTPException(400, "لم يتم تحديد المدرسة")
    update_fields = {"updated_at": datetime.now(timezone.utc).isoformat()}
    for field in ["title", "title_en", "date", "issuing_body", "description", "image_url"]:
        val = getattr(data, field, None)
        if val is not None:
            update_fields[field] = val
    result = await gd_update_one(db.session, "student_certificates", {"id": certificate_id, "school_id": tenant}, update_fields)
    if result == 0:
        raise HTTPException(404, "الشهادة غير موجودة")
    return {"success": True, "message": "تم تحديث الشهادة"}


@router.delete("/certificates/{certificate_id}")
async def delete_certificate(
    certificate_id: str,
    current_user: dict = Depends(get_current_user),
):
    role = current_user.get("role", "")
    if role not in ("school_admin", "admin", "super_admin"):
        raise HTTPException(403, "ليس لديك صلاحية")
    tenant = current_user.get("tenant_id")
    if not tenant:
        raise HTTPException(400, "لم يتم تحديد المدرسة")
    result = await gd_delete_one(db.session, "student_certificates", {"id": certificate_id, "school_id": tenant})
    if result == 0:
        raise HTTPException(404, "الشهادة غير موجودة")
    return {"success": True, "message": "تم حذف الشهادة"}
