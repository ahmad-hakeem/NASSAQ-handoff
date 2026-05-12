"""
NASSAQ Academics Sub-module
"""
from fastapi import APIRouter, HTTPException, Depends, status, Header, Query, Body, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import Response
from starlette.responses import StreamingResponse
from pydantic import BaseModel, Field, ConfigDict, EmailStr, model_validator
from typing import List, Optional, Any, Dict
from datetime import datetime, timezone, timedelta
import uuid, os, logging, json, random, re, io, base64

logger = logging.getLogger("nassaq.academics")

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


from shared_models import (
    TeacherCreate, TeacherUpdate, TeacherResponse, StudentCreate, StudentUpdate, StudentResponse, ClassCreate, ClassUpdate, ClassResponse, SubjectCreate, SubjectResponse
)

router = APIRouter()


async def get_school_id_from_context(current_user: dict, x_school_context: str = None) -> str:
    """Resolve school_id from header, with strict tenant isolation.

    Delegates to `utils.tenant_scope.resolve_school_id` so that non-platform
    callers can never address another school's data via the X-School-Context
    header (mismatched override → 403). Platform admins retain free override.
    """
    from utils.tenant_scope import resolve_school_id
    return resolve_school_id(current_user, x_school_context)

# ============== ACADEMIC YEARS APIs ==============
class AcademicYearBase(BaseModel):
    name: str
    name_en: Optional[str] = None
    start_date: str
    end_date: str
    is_current: bool = False
    school_id: Optional[str] = None

class AcademicYearResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    name: str = ""
    name_en: Optional[str] = None
    start_date: str
    end_date: str
    is_current: bool
    school_id: str
    status: str = "active"
    created_at: str


def _normalize_date_str(val) -> str:
    """Return YYYY-MM-DD regardless of whether val is a datetime, date, or ISO string."""
    if val is None:
        return ""
    return str(val)[:10]


def normalize_academic_year(doc: dict) -> dict:
    d = dict(doc)
    if "name" not in d and "name_ar" in d:
        d["name"] = d["name_ar"]
    if "name_en" not in d and "year" in d:
        d["name_en"] = d["year"]
    if "status" not in d:
        d["status"] = "active" if d.get("is_current") else "draft"
    if "created_at" not in d:
        d["created_at"] = d.get("updated_at", "")
    for field in ("start_date", "end_date"):
        if d.get(field):
            d[field] = _normalize_date_str(d[field])
    return d

@router.post("/academic-years", response_model=AcademicYearResponse)
async def create_academic_year(
    data: AcademicYearBase,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.INDEPENDENT_TEACHER]))
):
    """Create a new academic year"""
    academic_year_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    from auth_scope import independent_workspace_id
    from quotas.independent_teacher import enforce_academic_year_quota
    school_id = current_user.get("tenant_id") or independent_workspace_id(current_user) or data.school_id
    if not school_id:
        raise HTTPException(status_code=400, detail="لم يتم تحديد المدرسة")
    # Phase 0 §4.B-5 — IT v1 academic-year quota (single year).
    await enforce_academic_year_quota(db.session, current_user)
    
    if data.is_current:
        await gd_update_many(db.session, "academic_years", {"school_id": school_id, "is_current": True}, {"is_current": False})
    
    academic_year_doc = {
        "id": academic_year_id,
        "name": data.name,
        "name_ar": data.name,
        "name_en": data.name_en,
        "start_date": data.start_date,
        "end_date": data.end_date,
        "is_current": data.is_current,
        "school_id": school_id,
        "status": "active",
        "created_at": now,
        "updated_at": now,
        "created_by": current_user.get("id")
    }
    
    await gd_insert(db.session, "academic_years", academic_year_doc)
    
    return AcademicYearResponse(**academic_year_doc)

@router.get("/academic-years", response_model=List[AcademicYearResponse])
async def get_academic_years(
    school_id: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """Get all academic years for a school"""
    query = {}
    if school_id:
        query["school_id"] = school_id
    elif current_user.get("tenant_id"):
        query["school_id"] = current_user["tenant_id"]
    
    academic_years = await gd_find(db.session, "academic_years", query, order_by="start_date", desc_order=True, limit=100)
    return [AcademicYearResponse(**normalize_academic_year(ay)) for ay in academic_years]

@router.get("/academic-years/{academic_year_id}", response_model=AcademicYearResponse)
async def get_academic_year(
    academic_year_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get a single academic year — tenant-scoped (audit C-3)."""
    from utils.tenant_scope import tenant_scoped_find_one
    academic_year = await tenant_scoped_find_one(db.session, "academic_years", academic_year_id, current_user)
    if not academic_year:
        raise HTTPException(status_code=404, detail="العام الدراسي غير موجود")
    return AcademicYearResponse(**normalize_academic_year(academic_year))

@router.put("/academic-years/{academic_year_id}", response_model=AcademicYearResponse)
async def update_academic_year(
    academic_year_id: str,
    data: AcademicYearBase,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN]))
):
    """Update an academic year — tenant-scoped (audit C-3)."""
    from utils.tenant_scope import tenant_scoped_assert_one
    academic_year = await tenant_scoped_assert_one(
        db.session, "academic_years", academic_year_id, current_user,
        not_found_detail="العام الدراسي غير موجود",
    )

    school_id = current_user.get("tenant_id") or data.school_id or academic_year.get("school_id")
    
    if data.is_current:
        await gd_update_many(db.session, "academic_years", {"school_id": school_id, "is_current": True, "id": {"$ne": academic_year_id}}, {"is_current": False})
    
    update_data = {
        "name": data.name,
        "name_ar": data.name,
        "name_en": data.name_en,
        "start_date": data.start_date,
        "end_date": data.end_date,
        "is_current": data.is_current,
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    
    await gd_update_one(db.session, "academic_years", {"id": academic_year_id}, update_data)
    
    updated = await gd_find_one(db.session, "academic_years", {"id": academic_year_id})
    return AcademicYearResponse(**normalize_academic_year(updated))

@router.delete("/academic-years/{academic_year_id}")
async def delete_academic_year(
    academic_year_id: str,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN]))
):
    """Delete an academic year — tenant-scoped (audit C-3)."""
    from utils.tenant_scope import tenant_scoped_assert_one
    await tenant_scoped_assert_one(
        db.session, "academic_years", academic_year_id, current_user,
        not_found_detail="العام الدراسي غير موجود",
    )
    result = await gd_delete_one(db.session, "academic_years", {"id": academic_year_id})
    if result == 0:
        raise HTTPException(status_code=404, detail="العام الدراسي غير موجود")
    return {"message": "تم حذف العام الدراسي بنجاح"}





# ============== TERMS/SEMESTERS APIs ==============
class TermBase(BaseModel):
    name: str
    name_en: Optional[str] = None
    academic_year_id: str
    start_date: str
    end_date: str
    is_current: bool = False
    school_id: Optional[str] = None

class TermResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    name: str
    name_en: Optional[str] = None
    academic_year_id: str
    start_date: str
    end_date: str
    is_current: bool
    school_id: str
    created_at: str

@router.post("/terms", response_model=TermResponse)
async def create_term(
    data: TermBase,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.INDEPENDENT_TEACHER]))
):
    """Create a new term/semester"""
    term_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    from auth_scope import independent_workspace_id
    from quotas.independent_teacher import enforce_term_quota
    effective_school_id = current_user.get("tenant_id") or current_user.get("school_id") or independent_workspace_id(current_user) or data.school_id
    if not effective_school_id:
        raise HTTPException(status_code=400, detail="لم يتم تحديد المدرسة")
    # Phase 0 §4.B-5 — IT v1 term quota (max 2).
    await enforce_term_quota(db.session, current_user)

    # If setting as current, unset other current terms for this school
    if data.is_current:
        await gd_update_many(db.session, "terms", {"school_id": effective_school_id, "is_current": True}, {"is_current": False})
    
    term_doc = {
        "id": term_id,
        "name": data.name,
        "name_en": data.name_en,
        "academic_year_id": data.academic_year_id,
        "start_date": data.start_date,
        "end_date": data.end_date,
        "is_current": data.is_current,
        "school_id": effective_school_id,
        "created_at": now,
        "updated_at": now,
        "created_by": current_user.get("id")
    }
    
    await gd_insert(db.session, "terms", term_doc)
    
    return TermResponse(**term_doc)

@router.get("/terms", response_model=List[TermResponse])
async def get_terms(
    school_id: Optional[str] = None,
    academic_year_id: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """Get all terms for a school"""
    query = {}
    if school_id:
        query["school_id"] = school_id
    elif current_user.get("tenant_id"):
        query["school_id"] = current_user["tenant_id"]
    
    if academic_year_id:
        query["academic_year_id"] = academic_year_id
    
    terms = await gd_find(db.session, "terms", query, order_by="start_date", desc_order=True, limit=100)
    normalized = []
    for t in terms:
        t["start_date"] = _normalize_date_str(t.get("start_date"))
        t["end_date"] = _normalize_date_str(t.get("end_date"))
        normalized.append(t)
    return [TermResponse(**t) for t in normalized]

@router.get("/terms/{term_id}", response_model=TermResponse)
async def get_term(
    term_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get a single term — tenant-scoped (audit C-3)."""
    from utils.tenant_scope import tenant_scoped_find_one
    term = await tenant_scoped_find_one(db.session, "terms", term_id, current_user)
    if not term:
        raise HTTPException(status_code=404, detail="الفصل الدراسي غير موجود")
    return TermResponse(**term)

@router.put("/terms/{term_id}", response_model=TermResponse)
async def update_term(
    term_id: str,
    data: TermBase,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN]))
):
    """Update a term — tenant-scoped (audit C-3)."""
    from utils.tenant_scope import tenant_scoped_assert_one
    term = await tenant_scoped_assert_one(
        db.session, "terms", term_id, current_user,
        not_found_detail="الفصل الدراسي غير موجود",
    )
    
    # If setting as current, unset other current terms
    if data.is_current:
        await gd_update_many(db.session, "terms", {"school_id": data.school_id, "is_current": True, "id": {"$ne": term_id}}, {"is_current": False})
    
    update_data = {
        "name": data.name,
        "name_en": data.name_en,
        "academic_year_id": data.academic_year_id,
        "start_date": data.start_date,
        "end_date": data.end_date,
        "is_current": data.is_current,
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    
    await gd_update_one(db.session, "terms", {"id": term_id}, update_data)
    
    updated = await gd_find_one(db.session, "terms", {"id": term_id})
    return TermResponse(**updated)

@router.delete("/terms/{term_id}")
async def delete_term(
    term_id: str,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN]))
):
    """Delete a term — tenant-scoped (audit C-3)."""
    from utils.tenant_scope import tenant_scoped_assert_one
    await tenant_scoped_assert_one(
        db.session, "terms", term_id, current_user,
        not_found_detail="الفصل الدراسي غير موجود",
    )
    result = await gd_delete_one(db.session, "terms", {"id": term_id})
    if result == 0:
        raise HTTPException(status_code=404, detail="الفصل الدراسي غير موجود")
    return {"message": "تم حذف الفصل الدراسي بنجاح"}





# ============== GRADE LEVELS APIs ==============
class GradeLevelBase(BaseModel):
    name: str
    name_en: Optional[str] = None
    order: int = 1
    is_active: bool = True
    school_id: str

class GradeLevelResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    name: str
    name_en: Optional[str] = None
    order: int
    is_active: bool
    school_id: str
    created_at: str

@router.post("/grade-levels", response_model=GradeLevelResponse)
async def create_grade_level(
    data: GradeLevelBase,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN]))
):
    """Create a new grade level"""
    grade_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    
    grade_doc = {
        "id": grade_id,
        "name": data.name,
        "name_en": data.name_en,
        "order": data.order,
        "is_active": data.is_active,
        "school_id": data.school_id,
        "created_at": now,
        "updated_at": now,
        "created_by": current_user.get("id")
    }
    
    await gd_insert(db.session, "grade_levels", grade_doc)
    
    return GradeLevelResponse(**grade_doc)

@router.get("/grade-levels", response_model=List[GradeLevelResponse])
async def get_grade_levels(
    school_id: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """Get all grade levels for a school"""
    query = {}
    if school_id:
        query["school_id"] = school_id
    elif current_user.get("tenant_id"):
        query["school_id"] = current_user["tenant_id"]
    
    grade_levels = await gd_find(db.session, "grade_levels", query, order_by="order", desc_order=False, limit=100)
    return [GradeLevelResponse(**gl) for gl in grade_levels]

@router.get("/grade-levels/{grade_id}", response_model=GradeLevelResponse)
async def get_grade_level(
    grade_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get a single grade level — tenant-scoped (audit C-3)."""
    from utils.tenant_scope import tenant_scoped_find_one
    grade = await tenant_scoped_find_one(db.session, "grade_levels", grade_id, current_user)
    if not grade:
        raise HTTPException(status_code=404, detail="المرحلة الدراسية غير موجودة")
    return GradeLevelResponse(**grade)

@router.put("/grade-levels/{grade_id}", response_model=GradeLevelResponse)
async def update_grade_level(
    grade_id: str,
    data: GradeLevelBase,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN]))
):
    """Update a grade level — tenant-scoped (audit C-3)."""
    from utils.tenant_scope import tenant_scoped_assert_one
    grade = await tenant_scoped_assert_one(
        db.session, "grade_levels", grade_id, current_user,
        not_found_detail="المرحلة الدراسية غير موجودة",
    )
    
    update_data = {
        "name": data.name,
        "name_en": data.name_en,
        "order": data.order,
        "is_active": data.is_active,
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    
    await gd_update_one(db.session, "grade_levels", {"id": grade_id}, update_data)
    
    updated = await gd_find_one(db.session, "grade_levels", {"id": grade_id})
    return GradeLevelResponse(**updated)

@router.delete("/grade-levels/{grade_id}")
async def delete_grade_level(
    grade_id: str,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN]))
):
    """Delete a grade level — tenant-scoped (audit C-3)."""
    from utils.tenant_scope import tenant_scoped_assert_one
    await tenant_scoped_assert_one(
        db.session, "grade_levels", grade_id, current_user,
        not_found_detail="المرحلة الدراسية غير موجودة",
    )
    result = await gd_delete_one(db.session, "grade_levels", {"id": grade_id})
    if result == 0:
        raise HTTPException(status_code=404, detail="المرحلة الدراسية غير موجودة")
    return {"message": "تم حذف المرحلة الدراسية بنجاح"}





