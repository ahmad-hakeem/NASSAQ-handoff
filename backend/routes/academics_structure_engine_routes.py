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


class EducationalStageCreate(BaseModel):
    name: str
    name_en: Optional[str] = None
    order: int = 1

class AcademicTermCreate(BaseModel):
    name: str
    name_en: Optional[str] = None
    start_date: str
    end_date: str
    is_active: bool = True

# ============== ACADEMIC STRUCTURE ENGINE ROUTES ==============

class GradeCreate(BaseModel):
    stage_code: str
    grade_number: int
    name_ar: str
    name_en: Optional[str] = None
    display_order: Optional[int] = None

class SectionCreate(BaseModel):
    grade_id: str
    name: str  # أ، ب، ج
    capacity: int = 30
    homeroom_teacher_id: Optional[str] = None
    classroom_id: Optional[str] = None
    academic_year: str = "1446-1447"

class ClassroomCreate(BaseModel):
    name: str
    building: Optional[str] = None
    floor: Optional[int] = None
    room_type: str = "classroom"
    capacity: int = 30
    has_projector: bool = False
    has_smartboard: bool = False
    has_ac: bool = True
    notes: Optional[str] = None

class SubjectCreate(BaseModel):
    name_ar: str
    name_en: Optional[str] = None
    code: str
    category: str = "core"
    default_periods: int = 4
    stages: List[str] = []


@router.post("/academic/stages/seed-defaults")
async def seed_default_stages(
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))
):
    """Seed default educational stages"""
    default_stages = [
        {"code": "KG", "name_ar": "رياض الأطفال", "name_en": "Kindergarten", "order": 1, "min_age": 3, "max_age": 6, "grades_count": 3},
        {"code": "PRIMARY", "name_ar": "المرحلة الابتدائية", "name_en": "Primary", "order": 2, "min_age": 6, "max_age": 12, "grades_count": 6},
        {"code": "INTERMEDIATE", "name_ar": "المرحلة المتوسطة", "name_en": "Intermediate", "order": 3, "min_age": 12, "max_age": 15, "grades_count": 3},
        {"code": "SECONDARY", "name_ar": "المرحلة الثانوية", "name_en": "Secondary", "order": 4, "min_age": 15, "max_age": 18, "grades_count": 3}
    ]
    
    count = 0
    for stage in default_stages:
        existing = await gd_find_one(db.session, "educational_stages", {"code": stage["code"], "is_global": True})
        if not existing:
            stage["id"] = str(uuid.uuid4())
            stage["tenant_id"] = None
            stage["is_global"] = True
            stage["is_active"] = True
            stage["created_at"] = datetime.now(timezone.utc).isoformat()
            stage["created_by"] = current_user["id"]
            await gd_insert(db.session, "educational_stages", stage)
            count += 1
    
    return {"message": f"تم إضافة {count} مرحلة تعليمية", "added": count}


@router.get("/academic/stages")
async def get_educational_stages(
    school_id: Optional[str] = None,
    include_global: bool = True,
    current_user: dict = Depends(get_current_user)
):
    """Get educational stages"""
    from utils.tenant_scope import resolve_school_id
    effective_school_id = resolve_school_id(current_user, school_id) or current_user.get("tenant_id")
    query = {"is_active": True}
    
    if effective_school_id:
        if include_global:
            query["$or"] = [{"tenant_id": effective_school_id}, {"is_global": True}]
        else:
            query["tenant_id"] = effective_school_id
    else:
        query["is_global"] = True
    
    stages = await gd_find(db.session, "educational_stages", query, order_by="order", desc_order=False, limit=100)
    return {"stages": stages, "total": len(stages)}


@router.post("/academic/grades/seed-defaults")
async def seed_default_grades(
    school_id: str,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN]))
):
    """Seed default grades for a school"""
    from utils.tenant_scope import resolve_school_id
    effective_school_id = resolve_school_id(current_user, school_id)
    if not effective_school_id:
        raise HTTPException(status_code=400, detail="يجب تحديد المدرسة")
    school_id = effective_school_id
    stages = await gd_find(db.session, "educational_stages", {"$or": [{"tenant_id": school_id}, {"is_global": True}], "is_active": True}, limit=100)
    
    grade_names_ar = {1: "الأول", 2: "الثاني", 3: "الثالث", 4: "الرابع", 5: "الخامس", 6: "السادس"}
    
    count = 0
    for stage in stages:
        stage_code = stage.get("code")
        grades_count = stage.get("grades_count", 3)
        
        for i in range(1, grades_count + 1):
            existing = await gd_find_one(db.session, "grades", {
                "tenant_id": school_id,
                "stage_code": stage_code,
                "grade_number": i
            })
            
            if not existing:
                if stage_code == "KG":
                    name_ar = f"روضة {i}"
                    name_en = f"KG{i}"
                else:
                    name_ar = f"الصف {grade_names_ar.get(i, str(i))}"
                    name_en = f"Grade {i}"
                
                grade_doc = {
                    "id": str(uuid.uuid4()),
                    "tenant_id": school_id,
                    "stage_id": stage.get("id"),
                    "stage_code": stage_code,
                    "stage_name_ar": stage.get("name_ar"),
                    "grade_number": i,
                    "name_ar": name_ar,
                    "name_en": name_en,
                    "full_name_ar": f"{name_ar} - {stage.get('name_ar')}",
                    "display_order": stage.get("order", 1) * 10 + i,
                    "is_active": True,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "created_by": current_user["id"]
                }
                await gd_insert(db.session, "grades", grade_doc)
                count += 1
    
    return {"message": f"تم إضافة {count} صف دراسي", "added": count}


@router.get("/academic/grades")
async def get_grades(
    school_id: str,
    stage_code: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """Get grades for a school"""
    from utils.tenant_scope import resolve_school_id
    effective_school_id = resolve_school_id(current_user, school_id) or current_user.get("tenant_id")
    if not effective_school_id:
        raise HTTPException(status_code=400, detail="يجب تحديد المدرسة")
    school_id = effective_school_id
    query = {"tenant_id": school_id, "is_active": True}
    if stage_code:
        query["stage_code"] = stage_code
    
    grades = await gd_find(db.session, "grades", query, order_by="display_order", desc_order=False, limit=100)
    return {"grades": grades, "total": len(grades)}


@router.post("/academic/grades")
async def create_grade(
    data: GradeCreate,
    school_id: str,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN]))
):
    """Create a new grade"""
    from utils.tenant_scope import resolve_school_id
    effective_school_id = resolve_school_id(current_user, school_id)
    if not effective_school_id:
        raise HTTPException(status_code=400, detail="يجب تحديد المدرسة")
    school_id = effective_school_id
    # Get stage info
    stage = await gd_find_one(db.session, "educational_stages", {
        "$or": [{"code": data.stage_code, "tenant_id": school_id}, {"code": data.stage_code, "is_global": True}]
    })
    
    if not stage:
        raise HTTPException(status_code=404, detail="المرحلة غير موجودة")
    
    grade_doc = {
        "id": str(uuid.uuid4()),
        "tenant_id": school_id,
        "stage_id": stage.get("id"),
        "stage_code": data.stage_code,
        "stage_name_ar": stage.get("name_ar"),
        "grade_number": data.grade_number,
        "name_ar": data.name_ar,
        "name_en": data.name_en,
        "full_name_ar": f"{data.name_ar} - {stage.get('name_ar')}",
        "display_order": data.display_order or (stage.get("order", 1) * 10 + data.grade_number),
        "is_active": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by": current_user["id"]
    }
    
    await gd_insert(db.session, "grades", grade_doc)
    grade_doc.pop("_id", None)
    return grade_doc


@router.post("/academic/sections")
async def create_section(
    data: SectionCreate,
    school_id: str,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN]))
):
    """Create a new section/class"""
    from utils.tenant_scope import resolve_school_id
    effective_school_id = resolve_school_id(current_user, school_id)
    if not effective_school_id:
        raise HTTPException(status_code=400, detail="يجب تحديد المدرسة")
    school_id = effective_school_id
    # Get grade info
    grade = await gd_find_one(db.session, "grades", {"id": data.grade_id, "tenant_id": school_id})
    if not grade:
        raise HTTPException(status_code=404, detail="الصف غير موجود")
    
    section_doc = {
        "id": str(uuid.uuid4()),
        "tenant_id": school_id,
        "grade_id": data.grade_id,
        "grade_name_ar": grade.get("name_ar"),
        "stage_code": grade.get("stage_code"),
        "name": data.name,
        "full_name_ar": f"{grade.get('full_name_ar')} ({data.name})",
        "capacity": data.capacity,
        "current_students": 0,
        "homeroom_teacher_id": data.homeroom_teacher_id,
        "classroom_id": data.classroom_id,
        "is_active": True,
        "academic_year": data.academic_year,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by": current_user["id"]
    }
    
    await gd_insert(db.session, "sections", section_doc)
    section_doc.pop("_id", None)
    return section_doc


@router.get("/academic/sections")
async def get_sections(
    school_id: str,
    grade_id: Optional[str] = None,
    stage_code: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """Get sections for a school"""
    from utils.tenant_scope import resolve_school_id
    effective_school_id = resolve_school_id(current_user, school_id) or current_user.get("tenant_id")
    if not effective_school_id:
        raise HTTPException(status_code=400, detail="يجب تحديد المدرسة")
    school_id = effective_school_id
    query = {"tenant_id": school_id, "is_active": True}
    if grade_id:
        query["grade_id"] = grade_id
    if stage_code:
        query["stage_code"] = stage_code
    
    sections = await gd_find(db.session, "sections", query, order_by="full_name_ar", desc_order=False, limit=1000)
    return {"sections": sections, "total": len(sections)}


@router.put("/academic/sections/{section_id}")
async def update_section(
    section_id: str,
    updates: dict,
    current_user: dict = Depends(require_roles([UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN]))
):
    """Update a section"""
    from utils.tenant_scope import assert_school_access
    existing_section = await gd_find_one(db.session, "sections", {"id": section_id})
    if not existing_section:
        raise HTTPException(status_code=404, detail="القسم غير موجود")
    assert_school_access(current_user, existing_section.get("tenant_id"))
    protected = ["id", "tenant_id", "created_at", "created_by"]
    for field in protected:
        updates.pop(field, None)
    
    updates["updated_at"] = datetime.now(timezone.utc).isoformat()
    updates["updated_by"] = current_user["id"]
    
    await gd_update_one(db.session, "sections", {"id": section_id}, updates)
    return await gd_find_one(db.session, "sections", {"id": section_id})


@router.post("/academic/sections/{section_id}/assign-teacher")
async def assign_homeroom_teacher(
    section_id: str,
    teacher_id: str,
    current_user: dict = Depends(require_roles([UserRole.SCHOOL_PRINCIPAL]))
):
    """Assign homeroom teacher to section"""
    from utils.tenant_scope import assert_school_access
    existing_section = await gd_find_one(db.session, "sections", {"id": section_id})
    if not existing_section:
        raise HTTPException(status_code=404, detail="القسم غير موجود")
    assert_school_access(current_user, existing_section.get("tenant_id"))
    now = datetime.now(timezone.utc).isoformat()

    await gd_update_one(db.session, "sections", {"id": section_id}, {
            "homeroom_teacher_id": teacher_id,
            "homeroom_assigned_at": now,
            "homeroom_assigned_by": current_user["id"]
        })

    return await gd_find_one(db.session, "sections", {"id": section_id})


@router.post("/academic/classrooms")
async def create_classroom(
    data: ClassroomCreate,
    school_id: str,
    current_user: dict = Depends(require_roles([UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN]))
):
    """Create a physical classroom"""
    from utils.tenant_scope import resolve_school_id
    effective_school_id = resolve_school_id(current_user, school_id)
    if not effective_school_id:
        raise HTTPException(status_code=400, detail="يجب تحديد المدرسة")
    school_id = effective_school_id
    classroom_doc = {
        "id": str(uuid.uuid4()),
        "tenant_id": school_id,
        "name": data.name,
        "building": data.building,
        "floor": data.floor,
        "room_type": data.room_type,
        "capacity": data.capacity,
        "has_projector": data.has_projector,
        "has_smartboard": data.has_smartboard,
        "has_ac": data.has_ac,
        "is_available": True,
        "notes": data.notes,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by": current_user["id"]
    }
    
    await gd_insert(db.session, "physical_classrooms", classroom_doc)
    classroom_doc.pop("_id", None)
    return classroom_doc


@router.get("/academic/classrooms")
async def get_classrooms(
    school_id: Optional[str] = None,
    room_type: Optional[str] = None,
    available_only: bool = False,
    current_user: dict = Depends(get_current_user)
):
    """Get physical classrooms.

    `school_id` is optional — when omitted the endpoint resolves the tenant
    from the authenticated user's token (same pattern as other school-scoped
    routes).  Callers that already supply `school_id` continue to work as
    before provided it matches the caller's own tenant.
    """
    # Derive resolved_school_id from auth token; fall back to query param only
    # for platform admins who legitimately pass a target school.
    user_tenant = current_user.get("tenant_id")
    role = current_user.get("role") or ""
    if school_id is None:
        if not user_tenant:
            raise HTTPException(status_code=403, detail="يجب تحديد المدرسة")
        resolved_school_id = user_tenant
    else:
        # Non-platform roles may not query a foreign school, and must always
        # carry a tenant_id in their token (fail-closed: no token tenant → deny).
        if role not in ("platform_admin", "platform_support"):
            if not user_tenant or school_id != user_tenant:
                raise HTTPException(status_code=403, detail="يجب تحديد المدرسة")
        resolved_school_id = school_id

    query: Dict[str, Any] = {"tenant_id": resolved_school_id}
    if room_type:
        query["room_type"] = room_type
    if available_only:
        query["is_available"] = True

    classrooms = await gd_find(db.session, "physical_classrooms", query, order_by="name", desc_order=False, limit=1000)
    return {"classrooms": classrooms, "total": len(classrooms)}


@router.put("/academic/classrooms/{classroom_id}")
async def update_classroom(
    classroom_id: str,
    updates: dict,
    current_user: dict = Depends(require_roles([UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN]))
):
    """Update a classroom"""
    from utils.tenant_scope import assert_school_access
    existing_classroom = await gd_find_one(db.session, "physical_classrooms", {"id": classroom_id})
    if not existing_classroom:
        raise HTTPException(status_code=404, detail="الفصل غير موجود")
    assert_school_access(current_user, existing_classroom.get("tenant_id"))
    protected = ["id", "tenant_id", "created_at", "created_by"]
    for field in protected:
        updates.pop(field, None)

    updates["updated_at"] = datetime.now(timezone.utc).isoformat()
    updates["updated_by"] = current_user["id"]

    await gd_update_one(db.session, "physical_classrooms", {"id": classroom_id}, updates)
    return await gd_find_one(db.session, "physical_classrooms", {"id": classroom_id})


@router.post("/academic/subjects/seed-defaults")
async def seed_default_subjects(
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))
):
    """Seed default subjects"""
    default_subjects = [
        {"name_ar": "اللغة العربية", "name_en": "Arabic Language", "code": "ARB", "category": "core", "default_periods": 6},
        {"name_ar": "الرياضيات", "name_en": "Mathematics", "code": "MTH", "category": "core", "default_periods": 5},
        {"name_ar": "العلوم", "name_en": "Science", "code": "SCI", "category": "core", "default_periods": 4},
        {"name_ar": "اللغة الإنجليزية", "name_en": "English Language", "code": "ENG", "category": "core", "default_periods": 4},
        {"name_ar": "الدراسات الإسلامية", "name_en": "Islamic Studies", "code": "ISL", "category": "core", "default_periods": 4},
        {"name_ar": "الدراسات الاجتماعية", "name_en": "Social Studies", "code": "SOC", "category": "core", "default_periods": 3},
        {"name_ar": "الحاسب الآلي", "name_en": "Computer Science", "code": "CMP", "category": "elective", "default_periods": 2},
        {"name_ar": "التربية الفنية", "name_en": "Art Education", "code": "ART", "category": "elective", "default_periods": 2},
        {"name_ar": "التربية البدنية", "name_en": "Physical Education", "code": "PHY", "category": "activity", "default_periods": 2},
        {"name_ar": "المهارات الحياتية", "name_en": "Life Skills", "code": "LFS", "category": "elective", "default_periods": 1},
        {"name_ar": "الفيزياء", "name_en": "Physics", "code": "PHS", "category": "core", "default_periods": 4, "stages": ["SECONDARY"]},
        {"name_ar": "الكيمياء", "name_en": "Chemistry", "code": "CHM", "category": "core", "default_periods": 4, "stages": ["SECONDARY"]},
        {"name_ar": "الأحياء", "name_en": "Biology", "code": "BIO", "category": "core", "default_periods": 4, "stages": ["SECONDARY"]},
    ]
    
    count = 0
    for subject in default_subjects:
        existing = await gd_find_one(db.session, "subjects", {"code": subject["code"], "is_global": True})
        if not existing:
            subject["id"] = str(uuid.uuid4())
            subject["tenant_id"] = None
            subject["is_global"] = True
            subject["is_active"] = True
            subject["created_at"] = datetime.now(timezone.utc).isoformat()
            subject["created_by"] = current_user["id"]
            await gd_insert(db.session, "subjects", subject)
            count += 1
    
    return {"message": f"تم إضافة {count} مادة دراسية", "added": count}


@router.get("/academic/subjects")
async def get_subjects(
    school_id: Optional[str] = None,
    category: Optional[str] = None,
    stage_code: Optional[str] = None,
    include_global: bool = True,
    current_user: dict = Depends(get_current_user)
):
    """Get subjects"""
    from utils.tenant_scope import resolve_school_id
    effective_school_id = resolve_school_id(current_user, school_id) or current_user.get("tenant_id")
    query = {"is_active": True}
    
    if effective_school_id:
        if include_global:
            query["$or"] = [{"tenant_id": effective_school_id}, {"is_global": True}]
        else:
            query["tenant_id"] = effective_school_id
    else:
        query["is_global"] = True
    
    if category:
        query["category"] = category
    
    subjects = await gd_find(db.session, "subjects", query, order_by="name_ar", desc_order=False, limit=1000)
    
    # Filter by stage if specified
    if stage_code:
        subjects = [s for s in subjects if not s.get("stages") or stage_code in s.get("stages", [])]
    
    return {"subjects": subjects, "total": len(subjects)}


@router.post("/academic/subjects")
async def create_subject(
    data: SubjectCreate,
    school_id: Optional[str] = None,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN]))
):
    """Create a new subject"""
    from utils.tenant_scope import resolve_school_id
    effective_school_id = resolve_school_id(current_user, school_id) or current_user.get("tenant_id")
    school_id = effective_school_id
    subject_doc = {
        "id": str(uuid.uuid4()),
        "tenant_id": resolved_school_id,
        "name_ar": data.name_ar,
        "name_en": data.name_en,
        "code": data.code,
        "category": data.category,
        "default_periods": data.default_periods,
        "stages": data.stages,
        "is_global": resolved_school_id is None,
        "is_active": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by": current_user["id"]
    }
    
    await gd_insert(db.session, "subjects", subject_doc)
    subject_doc.pop("_id", None)
    return subject_doc


@router.get("/academic/structure/{school_id}")
async def get_academic_structure(
    school_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get complete academic structure for a school"""
    from utils.tenant_scope import assert_school_access
    assert_school_access(current_user, school_id)
    stages = await gd_find(db.session, "educational_stages", {"$or": [{"tenant_id": school_id}, {"is_global": True}], "is_active": True}, order_by="order", desc_order=False, limit=100)
    
    grades = await gd_find(db.session, "grades", {"tenant_id": school_id, "is_active": True}, limit=100)
    sections = await gd_find(db.session, "sections", {"tenant_id": school_id, "is_active": True}, limit=1000)
    classrooms = await gd_find(db.session, "physical_classrooms", {"tenant_id": school_id}, limit=1000)
    subjects = await gd_find(db.session, "subjects", {"$or": [{"tenant_id": school_id}, {"is_global": True}], "is_active": True}, limit=1000)
    
    structure = {
        "school_id": school_id,
        "stages": [],
        "total_grades": len(grades),
        "total_sections": len(sections),
        "total_classrooms": len(classrooms),
        "total_subjects": len(subjects),
    }
    
    for stage in stages:
        stage_grades = [g for g in grades if g.get("stage_code") == stage.get("code")]
        stage_sections = [s for s in sections if s.get("stage_code") == stage.get("code")]
        
        stage_data = {
            "id": stage.get("id"),
            "code": stage.get("code"),
            "name_ar": stage.get("name_ar"),
            "grades_count": len(stage_grades),
            "sections_count": len(stage_sections),
            "grades": []
        }
        
        for grade in sorted(stage_grades, key=lambda x: x.get("grade_number", 0)):
            grade_sections = [s for s in stage_sections if s.get("grade_id") == grade.get("id")]
            grade_data = {
                "id": grade.get("id"),
                "name_ar": grade.get("name_ar"),
                "grade_number": grade.get("grade_number"),
                "sections_count": len(grade_sections),
                "sections": grade_sections
            }
            stage_data["grades"].append(grade_data)
        
        structure["stages"].append(stage_data)
    
    return structure





# ============== EDUCATIONAL STAGES ==============

@router.get("/school/settings/stages")
async def get_school_stages(
    current_user: dict = Depends(get_current_user),
    x_school_context: str = Header(default=None, alias="X-School-Context")
):
    """Get school educational stages - جلب المراحل التعليمية"""
    school_id = await get_school_id_from_context(current_user, x_school_context)
    
    if not school_id:
        raise HTTPException(status_code=400, detail="School context required")
    
    stages = await gd_find(db.session, "school_stages", {"school_id": school_id}, order_by="order", desc_order=False, limit=50)
    return {"stages": stages}


@router.post("/school/settings/stages")
async def create_school_stage(
    data: EducationalStageCreate,
    current_user: dict = Depends(require_roles([UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN])),
    x_school_context: str = Header(default=None, alias="X-School-Context")
):
    """Create educational stage - إنشاء مرحلة تعليمية"""
    school_id = await get_school_id_from_context(current_user, x_school_context)
    
    if not school_id:
        raise HTTPException(status_code=400, detail="School context required")
    
    stage = {
        "id": str(uuid.uuid4()),
        "school_id": school_id,
        "name": data.name,
        "name_en": data.name_en,
        "order": data.order,
        "is_active": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by": current_user["id"]
    }
    
    await gd_insert(db.session, "school_stages", stage)
    stage.pop("_id", None)
    
    return {"message": "تم إضافة المرحلة التعليمية", "stage": stage}


@router.delete("/school/settings/stages/{stage_id}")
async def delete_school_stage(
    stage_id: str,
    current_user: dict = Depends(require_roles([UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN])),
    x_school_context: str = Header(default=None, alias="X-School-Context")
):
    """Delete educational stage - حذف مرحلة تعليمية"""
    school_id = await get_school_id_from_context(current_user, x_school_context)
    
    if not school_id:
        raise HTTPException(status_code=400, detail="School context required")
    
    # Check for dependencies (grades in this stage)
    grades_count = await gd_count(db.session, "school_grades", {"stage_id": stage_id, "school_id": school_id})
    if grades_count > 0:
        raise HTTPException(status_code=400, detail=f"لا يمكن حذف المرحلة لأنها تحتوي على {grades_count} صفوف")
    
    await gd_delete_one(db.session, "school_stages", {"id": stage_id, "school_id": school_id})
    
    # Audit log
    audit_log = {
        "id": str(uuid.uuid4()),
        "school_id": school_id,
        "action": "delete",
        "entity_type": "stage",
        "entity_id": stage_id,
        "performed_by": current_user["id"],
        "performed_by_name": current_user.get("full_name", ""),
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    await gd_insert(db.session, "audit_logs", audit_log)
    
    return {"message": "تم حذف المرحلة التعليمية"}


@router.put("/school/settings/stages/{stage_id}")
async def update_school_stage(
    stage_id: str,
    data: EducationalStageCreate,
    current_user: dict = Depends(require_roles([UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN])),
    x_school_context: str = Header(default=None, alias="X-School-Context")
):
    """Update educational stage - تحديث مرحلة تعليمية"""
    school_id = await get_school_id_from_context(current_user, x_school_context)
    
    if not school_id:
        raise HTTPException(status_code=400, detail="School context required")
    
    update_data = {
        "name": data.name,
        "name_en": data.name_en,
        "order": data.order,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "updated_by": current_user["id"]
    }
    
    result = await gd_update_one(db.session, "school_stages", {"id": stage_id, "school_id": school_id}, update_data)
    
    if result == 0:
        raise HTTPException(status_code=404, detail="المرحلة غير موجودة")
    
    # Audit log
    audit_log = {
        "id": str(uuid.uuid4()),
        "school_id": school_id,
        "action": "update",
        "entity_type": "stage",
        "entity_id": stage_id,
        "new_data": update_data,
        "performed_by": current_user["id"],
        "performed_by_name": current_user.get("full_name", ""),
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    await gd_insert(db.session, "audit_logs", audit_log)
    
    return {"message": "تم تحديث المرحلة التعليمية", "stage": update_data}





# ============== GRADES ==============

@router.get("/school/settings/grades")
async def get_school_grades(
    current_user: dict = Depends(get_current_user),
    x_school_context: str = Header(default=None, alias="X-School-Context")
):
    """Get school grades - جلب الصفوف الدراسية"""
    school_id = await get_school_id_from_context(current_user, x_school_context)
    
    if not school_id:
        raise HTTPException(status_code=400, detail="School context required")
    
    grades = await gd_find(db.session, "school_grades", {"school_id": school_id}, limit=100)
    return {"grades": grades}


@router.post("/school/settings/grades")
async def create_school_grade(
    data: GradeCreate,
    current_user: dict = Depends(require_roles([UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN])),
    x_school_context: str = Header(default=None, alias="X-School-Context")
):
    """Create grade - إنشاء صف دراسي"""
    school_id = await get_school_id_from_context(current_user, x_school_context)
    
    if not school_id:
        raise HTTPException(status_code=400, detail="School context required")
    
    grade = {
        "id": str(uuid.uuid4()),
        "school_id": school_id,
        "name": data.name,
        "name_en": data.name_en,
        "stage_id": data.stage_id,
        "is_active": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by": current_user["id"]
    }
    
    await gd_insert(db.session, "school_grades", grade)
    grade.pop("_id", None)
    
    return {"message": "تم إضافة الصف الدراسي", "grade": grade}


@router.delete("/school/settings/grades/{grade_id}")
async def delete_school_grade(
    grade_id: str,
    current_user: dict = Depends(require_roles([UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN])),
    x_school_context: str = Header(default=None, alias="X-School-Context")
):
    """Delete grade - حذف صف دراسي"""
    school_id = await get_school_id_from_context(current_user, x_school_context)
    
    if not school_id:
        raise HTTPException(status_code=400, detail="School context required")
    
    # Check for dependencies (classes in this grade)
    classes_count = await gd_count(db.session, "classes", {"grade_id": grade_id, "school_id": school_id})
    if classes_count > 0:
        raise HTTPException(status_code=400, detail=f"لا يمكن حذف الصف لأنه يحتوي على {classes_count} فصل")
    
    await gd_delete_one(db.session, "school_grades", {"id": grade_id, "school_id": school_id})
    
    # Audit log
    audit_log = {
        "id": str(uuid.uuid4()),
        "school_id": school_id,
        "action": "delete",
        "entity_type": "grade",
        "entity_id": grade_id,
        "performed_by": current_user["id"],
        "performed_by_name": current_user.get("full_name", ""),
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    await gd_insert(db.session, "audit_logs", audit_log)
    
    return {"message": "تم حذف الصف الدراسي"}


@router.put("/school/settings/grades/{grade_id}")
async def update_school_grade(
    grade_id: str,
    data: GradeCreate,
    current_user: dict = Depends(require_roles([UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN])),
    x_school_context: str = Header(default=None, alias="X-School-Context")
):
    """Update grade - تحديث صف دراسي"""
    school_id = await get_school_id_from_context(current_user, x_school_context)
    
    if not school_id:
        raise HTTPException(status_code=400, detail="School context required")
    
    update_data = {
        "name": data.name,
        "name_en": data.name_en,
        "stage_id": data.stage_id,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "updated_by": current_user["id"]
    }
    
    result = await gd_update_one(db.session, "school_grades", {"id": grade_id, "school_id": school_id}, update_data)
    
    if result == 0:
        raise HTTPException(status_code=404, detail="الصف غير موجود")
    
    # Audit log
    audit_log = {
        "id": str(uuid.uuid4()),
        "school_id": school_id,
        "action": "update",
        "entity_type": "grade",
        "entity_id": grade_id,
        "new_data": update_data,
        "performed_by": current_user["id"],
        "performed_by_name": current_user.get("full_name", ""),
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    await gd_insert(db.session, "audit_logs", audit_log)
    
    return {"message": "تم تحديث الصف الدراسي", "grade": update_data}





# ============== SECTIONS ==============

@router.get("/school/settings/sections")
async def get_school_sections(
    current_user: dict = Depends(get_current_user),
    x_school_context: str = Header(default=None, alias="X-School-Context")
):
    """Get school sections - جلب الشعب"""
    school_id = await get_school_id_from_context(current_user, x_school_context)
    
    if not school_id:
        raise HTTPException(status_code=400, detail="School context required")
    
    sections = await gd_find(db.session, "school_sections", {"school_id": school_id}, limit=200)
    return {"sections": sections}


@router.post("/school/settings/sections")
async def create_school_section(
    data: SectionCreate,
    current_user: dict = Depends(require_roles([UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN])),
    x_school_context: str = Header(default=None, alias="X-School-Context")
):
    """Create section - إنشاء شعبة"""
    school_id = await get_school_id_from_context(current_user, x_school_context)
    
    if not school_id:
        raise HTTPException(status_code=400, detail="School context required")
    
    section = {
        "id": str(uuid.uuid4()),
        "school_id": school_id,
        "name": data.name,
        "grade_id": data.grade_id,
        "class_id": data.class_id,
        "is_active": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by": current_user["id"]
    }
    
    await gd_insert(db.session, "school_sections", section)
    section.pop("_id", None)
    
    return {"message": "تم إضافة الشعبة", "section": section}


@router.delete("/school/settings/sections/{section_id}")
async def delete_school_section(
    section_id: str,
    current_user: dict = Depends(require_roles([UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN])),
    x_school_context: str = Header(default=None, alias="X-School-Context")
):
    """Delete section - حذف شعبة"""
    school_id = await get_school_id_from_context(current_user, x_school_context)
    
    if not school_id:
        raise HTTPException(status_code=400, detail="School context required")
    
    await gd_delete_one(db.session, "school_sections", {"id": section_id, "school_id": school_id})
    
    return {"message": "تم حذف الشعبة"}





# ============== ACADEMIC TERMS ==============

@router.get("/school/settings/academic-terms")
async def get_academic_terms(
    current_user: dict = Depends(get_current_user),
    x_school_context: str = Header(default=None, alias="X-School-Context")
):
    """Get academic terms - جلب الفصول الدراسية"""
    school_id = await get_school_id_from_context(current_user, x_school_context)
    
    if not school_id:
        raise HTTPException(status_code=400, detail="School context required")
    
    terms = await gd_find(db.session, "academic_terms", {"school_id": school_id}, order_by="start_date", desc_order=False, limit=10)
    return {"terms": terms}


@router.post("/school/settings/academic-terms")
async def create_academic_term(
    data: AcademicTermCreate,
    current_user: dict = Depends(require_roles([UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN])),
    x_school_context: str = Header(default=None, alias="X-School-Context")
):
    """Create academic term - إنشاء فصل دراسي"""
    school_id = await get_school_id_from_context(current_user, x_school_context)
    
    if not school_id:
        raise HTTPException(status_code=400, detail="School context required")
    
    term = {
        "id": str(uuid.uuid4()),
        "school_id": school_id,
        "name": data.name,
        "name_en": data.name_en,
        "start_date": data.start_date,
        "end_date": data.end_date,
        "is_active": data.is_active,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by": current_user["id"]
    }
    
    await gd_insert(db.session, "academic_terms", term)
    term.pop("_id", None)
    
    return {"message": "تم إضافة الفصل الدراسي", "term": term}


@router.put("/school/settings/academic-terms/{term_id}")
async def update_academic_term(
    term_id: str,
    data: AcademicTermCreate,
    current_user: dict = Depends(require_roles([UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN])),
    x_school_context: str = Header(default=None, alias="X-School-Context")
):
    """Update academic term - تحديث فصل دراسي"""
    school_id = await get_school_id_from_context(current_user, x_school_context)
    
    if not school_id:
        raise HTTPException(status_code=400, detail="School context required")
    
    await gd_update_one(db.session, "academic_terms", {"id": term_id, "school_id": school_id}, {
                "name": data.name,
                "name_en": data.name_en,
                "start_date": data.start_date,
                "end_date": data.end_date,
                "is_active": data.is_active,
                "updated_at": datetime.now(timezone.utc).isoformat()
            })
    
    return {"message": "تم تحديث الفصل الدراسي"}


@router.delete("/school/settings/academic-terms/{term_id}")
async def delete_academic_term(
    term_id: str,
    current_user: dict = Depends(require_roles([UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN])),
    x_school_context: str = Header(default=None, alias="X-School-Context")
):
    """Delete academic term - حذف فصل دراسي"""
    school_id = await get_school_id_from_context(current_user, x_school_context)
    
    if not school_id:
        raise HTTPException(status_code=400, detail="School context required")
    
    await gd_delete_one(db.session, "academic_terms", {"id": term_id, "school_id": school_id})
    
    return {"message": "تم حذف الفصل الدراسي"}





