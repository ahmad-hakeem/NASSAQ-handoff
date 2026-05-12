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
    REPORT_TYPES, generate_student_qr_code,
    require_recent_mfa_403_if_independent_teacher,
)
from engines.sql_utils import gd_find, gd_find_one, gd_insert, gd_insert_many, gd_update_one, gd_update_many, gd_count, gd_delete_one, gd_delete_many, gd_distinct, _gd_inc, _gd_pull
from auth_scope import require_request_school_id


from shared_models import (
    TeacherCreate, TeacherUpdate, TeacherResponse, StudentCreate, StudentUpdate, StudentResponse, ClassCreate, ClassUpdate, ClassResponse, SubjectCreate, SubjectResponse
)

router = APIRouter()

# Task #201 — IT §5.7 step-up backfill on parent deletion. Conditional
# on caller role so principal/admin behaviour on DELETE /parents/{id}
# is preserved.
_REQUIRE_RECENT_MFA_403_IT = require_recent_mfa_403_if_independent_teacher()


async def get_school_id_from_context(current_user: dict, x_school_context: str = None) -> str:
    """Resolve school_id from header, with strict tenant isolation.

    Delegates to `utils.tenant_scope.resolve_school_id` so that non-platform
    callers can never address another school's data via the X-School-Context
    header (mismatched override → 403). Platform admins retain free override.
    """
    from utils.tenant_scope import resolve_school_id
    return resolve_school_id(current_user, x_school_context)

# ============== TEACHERS ROUTES ==============

# Teacher Wizard Options
@router.get("/teachers/options/subjects")
async def get_teacher_subjects_options(current_user: dict = Depends(get_current_user)):
    """Get available subjects for the current school's teacher wizard.

    Sources, in order of preference:
      1. School-scoped + global subjects from `subjects` table
      2. Reference subjects from `reference_subjects`
      3. A built-in fallback list of standard Saudi subjects so the UI is
         never empty (the previous behaviour returned [] and broke the
         add-teacher wizard for any tenant whose tables hadn't been seeded).
    """
    tenant_id = current_user.get("tenant_id")

    collected: list = []
    if tenant_id:
        # School-scoped + global subjects from the main subjects table
        collected = await gd_find(
            db.session,
            "subjects",
            {
                "$or": [
                    {"school_id": tenant_id},
                    {"is_global": True},
                ],
                "is_active": True,
            },
            limit=300,
        )

    if not collected:
        collected = await gd_find(db.session, "reference_subjects", {"is_active": True}, limit=300)

    # Deduplicate by Arabic name and normalise the shape
    seen_names = set()
    unique_subjects = []
    for s in collected:
        name = s.get("name_ar") or s.get("name") or ""
        if name and name not in seen_names:
            seen_names.add(name)
            unique_subjects.append({
                "id": s.get("id"),
                "name": name,
                "name_ar": name,
                "name_en": s.get("name_en", ""),
                "code": s.get("code", ""),
                "color": s.get("color", "#3B82F6"),
            })

    if not unique_subjects:
        # Built-in safety net so the wizard is never blank
        FALLBACK = [
            ("math", "الرياضيات", "Mathematics"),
            ("arabic", "اللغة العربية", "Arabic Language"),
            ("english", "اللغة الإنجليزية", "English Language"),
            ("science", "العلوم", "Science"),
            ("social", "الدراسات الاجتماعية", "Social Studies"),
            ("islamic", "التربية الإسلامية", "Islamic Studies"),
            ("quran", "القرآن الكريم", "Quran"),
            ("pe", "التربية البدنية", "Physical Education"),
            ("art", "التربية الفنية", "Art"),
            ("computer", "الحاسب الآلي", "Computer Science"),
        ]
        unique_subjects = [
            {"id": code, "name": ar, "name_ar": ar, "name_en": en,
             "code": code, "color": "#3B82F6"}
            for code, ar, en in FALLBACK
        ]

    return {"subjects": unique_subjects}


# ============== ADMIN CONSTRAINTS CRUD - إدارة القيود الإدارية ==============

class ConstraintCreate(BaseModel):
    name_ar: str
    name_en: Optional[str] = None
    description_ar: Optional[str] = None
    description_en: Optional[str] = None
    type: str = "hard"  # 'hard' or 'soft'
    priority: str = "medium"  # 'critical', 'high', 'medium', 'low'
    restricted_periods: Optional[List[int]] = None
    max_consecutive_periods: Optional[int] = None

class ConstraintUpdate(BaseModel):
    name_ar: Optional[str] = None
    name_en: Optional[str] = None
    description_ar: Optional[str] = None
    description_en: Optional[str] = None
    type: Optional[str] = None
    priority: Optional[str] = None
    restricted_periods: Optional[List[int]] = None
    max_consecutive_periods: Optional[int] = None
    is_active: Optional[bool] = None

@router.post("/school/constraints")
async def create_school_constraint(
    constraint_data: ConstraintCreate,
    current_user: dict = Depends(require_roles([UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN])),
    x_school_context: str = Header(default=None, alias="X-School-Context")
):
    """Create a new admin constraint for the school - إضافة قيد إداري جديد"""
    school_id = await get_school_id_from_context(current_user, x_school_context)
    
    if not school_id:
        raise HTTPException(status_code=400, detail="School context required")
    
    constraint_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    
    constraint_doc = {
        "id": constraint_id,
        "school_id": school_id,
        "name_ar": constraint_data.name_ar,
        "name_en": constraint_data.name_en or constraint_data.name_ar,
        "description_ar": constraint_data.description_ar,
        "description_en": constraint_data.description_en,
        "type": constraint_data.type,
        "priority": constraint_data.priority,
        "restricted_periods": constraint_data.restricted_periods or [],
        "max_consecutive_periods": constraint_data.max_consecutive_periods,
        "is_active": True,
        "created_at": now,
        "updated_at": now,
        "created_by": current_user.get("id")
    }
    
    # Insert into school_constraints collection (not admin_constraints)
    await gd_insert(db.session, "school_constraints", constraint_doc)
    
    # Remove _id from response
    if "_id" in constraint_doc:
        del constraint_doc["_id"]
    
    return {"id": constraint_id, "message": "تم إضافة القيد بنجاح", "constraint": constraint_doc}

@router.put("/school/constraints/{constraint_id}")
async def update_school_constraint(
    constraint_id: str,
    constraint_data: ConstraintUpdate,
    current_user: dict = Depends(require_roles([UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN])),
    x_school_context: str = Header(default=None, alias="X-School-Context")
):
    """Update an admin constraint - تعديل قيد إداري"""
    school_id = await get_school_id_from_context(current_user, x_school_context)
    
    if not school_id:
        raise HTTPException(status_code=400, detail="School context required")
    
    # Check constraint exists in school_constraints collection
    constraint = await gd_find_one(db.session, "school_constraints", {"id": constraint_id, "school_id": school_id})
    
    if not constraint:
        raise HTTPException(status_code=404, detail="القيد غير موجود")
    
    update_data = {"updated_at": datetime.now(timezone.utc).isoformat()}
    
    if constraint_data.name_ar is not None:
        update_data["name_ar"] = constraint_data.name_ar
    if constraint_data.name_en is not None:
        update_data["name_en"] = constraint_data.name_en
    if constraint_data.description_ar is not None:
        update_data["description_ar"] = constraint_data.description_ar
    if constraint_data.description_en is not None:
        update_data["description_en"] = constraint_data.description_en
    if constraint_data.type is not None:
        update_data["type"] = constraint_data.type
    if constraint_data.priority is not None:
        update_data["priority"] = constraint_data.priority
    if constraint_data.restricted_periods is not None:
        update_data["restricted_periods"] = constraint_data.restricted_periods
    if constraint_data.max_consecutive_periods is not None:
        update_data["max_consecutive_periods"] = constraint_data.max_consecutive_periods
    if constraint_data.is_active is not None:
        update_data["is_active"] = constraint_data.is_active
    
    await gd_update_one(db.session, "school_constraints", {"id": constraint_id, "school_id": school_id}, update_data)
    
    return {"message": "تم تحديث القيد بنجاح"}

@router.delete("/school/constraints/{constraint_id}")
async def delete_school_constraint(
    constraint_id: str,
    current_user: dict = Depends(require_roles([UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN])),
    x_school_context: str = Header(default=None, alias="X-School-Context")
):
    """Delete (soft) an admin constraint - حذف قيد إداري"""
    school_id = await get_school_id_from_context(current_user, x_school_context)
    
    if not school_id:
        raise HTTPException(status_code=400, detail="School context required")
    
    # Check constraint exists in school_constraints collection
    constraint = await gd_find_one(db.session, "school_constraints", {"id": constraint_id, "school_id": school_id})
    
    if not constraint:
        raise HTTPException(status_code=404, detail="القيد غير موجود")
    
    # Soft delete
    await gd_update_one(db.session, "school_constraints", {"id": constraint_id, "school_id": school_id}, {"is_active": False, "deleted_at": datetime.now(timezone.utc).isoformat()})
    
    return {"message": "تم حذف القيد بنجاح"}

@router.get("/school/constraints")
async def get_school_constraints(
    current_user: dict = Depends(get_current_user),
    x_school_context: str = Header(default=None, alias="X-School-Context")
):
    """Get all constraints for the school - جلب جميع القيود للمدرسة"""
    school_id = await get_school_id_from_context(current_user, x_school_context)
    
    # Get school-specific constraints first
    school_constraints = await gd_find(db.session, "school_constraints", {"school_id": school_id}, limit=100)
    
    # If no school-specific constraints, get reference constraints as starting point
    if not school_constraints:
        ref_constraints = await gd_find(db.session, "admin_constraints", {"is_active": True}, limit=100)
        
        # Copy reference constraints to school-specific collection
        for c in ref_constraints:
            school_constraint = {
                "id": str(uuid.uuid4()),
                "school_id": school_id,
                "ref_id": c.get("id"),
                "name_ar": c.get("name_ar", c.get("name", "")),
                "name_en": c.get("name_en", ""),
                "description_ar": c.get("description_ar", c.get("description", "")),
                "description_en": c.get("description_en", ""),
                "type": c.get("type", "hard"),
                "priority": c.get("priority", "medium"),
                "is_active": c.get("is_active", True),
                "is_system": True,  # Mark as system-generated
                "created_at": datetime.now(timezone.utc).isoformat()
            }
            await gd_insert(db.session, "school_constraints", school_constraint)
            school_constraint.pop("_id", None)
            school_constraints.append(school_constraint)
    
    return school_constraints


@router.get("/teachers/options/grades")
async def get_teacher_grades_options(current_user: dict = Depends(get_current_user)):
    """Get available grade levels from reference database or school classes"""
    
    grades = await gd_find(db.session, "academic_grades", {"is_active": True}, order_by="order", desc_order=False, limit=100)
    
    if grades:
        stages = await gd_find(db.session, "academic_stages", {"is_active": True}, order_by="order", desc_order=False, limit=10)
        stages_map = {s["id"]: s for s in stages}
        
        formatted_grades = []
        for g in grades:
            stage = stages_map.get(g.get("stage_id"), {})
            formatted_grades.append({
                "id": g.get("id"),
                "name": g.get("name_ar", ""),
                "name_ar": g.get("name_ar", ""),
                "name_en": g.get("name_en", ""),
                "grade": g.get("order", g.get("grade_level", 1)),
                "stage": stage.get("name_ar", ""),
                "stage_en": stage.get("name_en", ""),
                "stage_id": g.get("stage_id")
            })
        return {"grades": formatted_grades}
    
    # Task #155: fail-closed school-id resolution; see audit row #11.
    school_id = require_request_school_id(current_user)
    query = {"school_id": school_id}
    classes = await gd_find(db.session, "classes", query, limit=500)
    
    grade_map = {}
    # Order matters: longer/multi-word names must be checked first so
    # "الثاني عشر" doesn't get matched as "الثاني".
    GRADE_ORDER = [
        ('الثاني عشر', 12), ('الحادي عشر', 11),
        ('العاشر', 10), ('التاسع', 9), ('الثامن', 8), ('السابع', 7),
        ('السادس', 6), ('الخامس', 5), ('الرابع', 4), ('الثالث', 3),
        ('الثاني', 2), ('الأول', 1),
    ]
    for cls in classes:
        cls_name = cls.get("name") or cls.get("name_ar") or ""
        if "الصف" not in cls_name:
            continue
        order_num = 99
        matched_label = None
        for ar_name, num in GRADE_ORDER:
            if ar_name in cls_name:
                order_num = num
                matched_label = ar_name
                break
        grade_name = f"الصف {matched_label}" if matched_label else cls_name
        if grade_name not in grade_map:
            grade_id = f"grade-{order_num}"
            grade_map[grade_name] = {
                "id": grade_id,
                "name": grade_name,
                "name_ar": grade_name,
                "name_en": f"Grade {order_num}" if order_num != 99 else grade_name,
                "grade": order_num,
            }
    
    sorted_grades = sorted(grade_map.values(), key=lambda g: g["grade"])

    if not sorted_grades:
        # Built-in safety net so the teacher wizard's grade picker is never
        # empty (covers freshly-created schools that haven't seeded grades
        # or classes yet).
        FALLBACK_GRADES = [
            (1, "الصف الأول الابتدائي", "Grade 1"),
            (2, "الصف الثاني الابتدائي", "Grade 2"),
            (3, "الصف الثالث الابتدائي", "Grade 3"),
            (4, "الصف الرابع الابتدائي", "Grade 4"),
            (5, "الصف الخامس الابتدائي", "Grade 5"),
            (6, "الصف السادس الابتدائي", "Grade 6"),
            (7, "الصف الأول المتوسط", "Grade 7"),
            (8, "الصف الثاني المتوسط", "Grade 8"),
            (9, "الصف الثالث المتوسط", "Grade 9"),
            (10, "الصف الأول الثانوي", "Grade 10"),
            (11, "الصف الثاني الثانوي", "Grade 11"),
            (12, "الصف الثالث الثانوي", "Grade 12"),
        ]
        sorted_grades = [
            {"id": f"grade-{n}", "name": ar, "name_ar": ar, "name_en": en, "grade": n}
            for n, ar, en in FALLBACK_GRADES
        ]

    return {"grades": sorted_grades}

@router.get("/teachers/options/academic-degrees")
async def get_academic_degrees_options(current_user: dict = Depends(get_current_user)):
    """Get available academic degrees from DB or defaults"""
    db_degrees = await gd_find(db.session, "lookup_options", {"type": "academic_degree", "is_active": {"$ne": False}}, limit=20)
    if db_degrees:
        degrees = [{"id": r.get("code", r.get("id")), "name": r.get("name_ar"), "name_en": r.get("name_en")} for r in db_degrees]
    else:
        degrees = [
            {"id": "diploma", "name": "دبلوم", "name_en": "Diploma"},
            {"id": "bachelor", "name": "بكالوريوس", "name_en": "Bachelor's"},
            {"id": "master", "name": "ماجستير", "name_en": "Master's"},
            {"id": "doctorate", "name": "دكتوراه", "name_en": "Doctorate"},
        ]
    return {"degrees": degrees}

@router.get("/teachers/options/teacher-ranks")
async def get_teacher_ranks_options(current_user: dict = Depends(get_current_user)):
    """Get available teacher ranks from database or defaults"""
    ranks = await gd_find(db.session, "lookup_options", {"type": "teacher_rank", "is_active": {"$ne": False}}, order_by="order", desc_order=False, limit=100)
    
    if not ranks:
        ranks = await gd_find(db.session, "teacher_ranks", {"is_active": True}, order_by="order", desc_order=False, limit=100)
    
    if not ranks:
        ranks = [
            {"id": "teacher", "name_ar": "معلم", "name_en": "Teacher", "weekly_periods": 24},
            {"id": "senior_teacher", "name_ar": "معلم أول", "name_en": "Senior Teacher", "weekly_periods": 22},
            {"id": "expert", "name_ar": "معلم خبير", "name_en": "Expert Teacher", "weekly_periods": 18},
            {"id": "department_head", "name_ar": "رئيس قسم", "name_en": "Department Head", "weekly_periods": 16},
        ]
    
    formatted_ranks = []
    for r in ranks:
        formatted_ranks.append({
            "id": r.get("id") or r.get("code"),
            "name": r.get("name_ar", r.get("name", "")),
            "name_en": r.get("name_en", ""),
            "weekly_periods": r.get("weekly_periods", 24),
            "is_special_education": r.get("is_special_education", False)
        })
    
    return {"ranks": formatted_ranks}

@router.get("/teachers/options/contract-types")
async def get_contract_types_options(current_user: dict = Depends(get_current_user)):
    """Get available contract types from DB or defaults"""
    db_types = await gd_find(db.session, "lookup_options", {"type": "contract_type", "is_active": {"$ne": False}}, limit=20)
    if db_types:
        types = [{"id": r.get("code", r.get("id")), "name": r.get("name_ar"), "name_en": r.get("name_en")} for r in db_types]
    else:
        types = [
            {"id": "permanent", "name": "دائم", "name_en": "Permanent"},
            {"id": "contract", "name": "عقد", "name_en": "Contract"},
            {"id": "part_time", "name": "دوام جزئي", "name_en": "Part-time"},
        ]
    return {"types": types}

@router.get("/teachers/options/nationalities")
async def get_nationalities_options(current_user: dict = Depends(get_current_user)):
    """Get available nationalities from DB or defaults"""
    db_nations = await gd_find(db.session, "lookup_options", {"type": "nationality", "is_active": {"$ne": False}}, limit=100)
    if db_nations:
        nationalities = [{"id": r.get("code", r.get("id")), "name": r.get("name_ar"), "name_en": r.get("name_en")} for r in db_nations]
    else:
        nationalities = [
            {"id": "SA", "name": "سعودي", "name_en": "Saudi"},
            {"id": "EG", "name": "مصري", "name_en": "Egyptian"},
            {"id": "JO", "name": "أردني", "name_en": "Jordanian"},
            {"id": "SY", "name": "سوري", "name_en": "Syrian"},
            {"id": "PS", "name": "فلسطيني", "name_en": "Palestinian"},
            {"id": "SD", "name": "سوداني", "name_en": "Sudanese"},
            {"id": "YE", "name": "يمني", "name_en": "Yemeni"},
            {"id": "TN", "name": "تونسي", "name_en": "Tunisian"},
            {"id": "MA", "name": "مغربي", "name_en": "Moroccan"},
            {"id": "PK", "name": "باكستاني", "name_en": "Pakistani"},
            {"id": "IN", "name": "هندي", "name_en": "Indian"},
            {"id": "OTHER", "name": "أخرى", "name_en": "Other"},
        ]
    return {"nationalities": nationalities}

class TeacherWizardCreate(BaseModel):
    """Teacher creation via wizard - supports both flat and nested structures"""
    # Flat structure fields
    full_name: Optional[str] = None
    full_name_en: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    national_id: Optional[str] = None
    gender: Optional[str] = "male"
    nationality: Optional[str] = "sa"
    date_of_birth: Optional[str] = None
    subject_ids: Optional[List[str]] = []
    grade_ids: Optional[List[str]] = []
    primary_subject_id: Optional[str] = None
    academic_degree: Optional[str] = None
    specialization: Optional[str] = None
    teacher_rank: Optional[str] = None
    contract_type: Optional[str] = "permanent"
    years_of_experience: Optional[int] = 0
    hire_date: Optional[str] = None
    max_periods_per_week: Optional[int] = 24
    available_days: Optional[List[str]] = []
    
    # Nested structure fields (from frontend wizard)
    basic_info: Optional[dict] = None
    qualifications: Optional[dict] = None
    subjects: Optional[dict] = None
    schedule: Optional[dict] = None

@router.post("/teachers/create")
async def create_teacher_wizard(
    data: TeacherWizardCreate,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.SCHOOL_SUB_ADMIN]))
):
    """Create a new teacher via wizard"""
    school_id = current_user.get("tenant_id")
    
    if not school_id:
        raise HTTPException(status_code=400, detail="المستخدم غير مرتبط بمدرسة")
    
    # Handle nested structure from frontend wizard
    if data.basic_info:
        full_name = data.basic_info.get("full_name_ar") or data.basic_info.get("full_name") or data.full_name
        full_name_en = data.basic_info.get("full_name_en") or data.full_name_en
        email = data.basic_info.get("email") or data.email
        phone = data.basic_info.get("phone") or data.phone
        national_id = data.basic_info.get("national_id") or data.national_id
        gender = data.basic_info.get("gender") or data.gender
        nationality = data.basic_info.get("nationality") or data.nationality
        date_of_birth = data.basic_info.get("date_of_birth") or data.date_of_birth
    else:
        full_name = data.full_name
        full_name_en = data.full_name_en
        email = data.email
        phone = data.phone
        national_id = data.national_id
        gender = data.gender
        nationality = data.nationality
        date_of_birth = data.date_of_birth
    
    if data.qualifications:
        academic_degree = data.qualifications.get("academic_degree") or data.academic_degree
        specialization = data.qualifications.get("specialization") or data.specialization
        teacher_rank = data.qualifications.get("teacher_rank") or data.teacher_rank
        years_of_experience = data.qualifications.get("years_of_experience") or data.years_of_experience or 0
    else:
        academic_degree = data.academic_degree
        specialization = data.specialization
        teacher_rank = data.teacher_rank
        years_of_experience = data.years_of_experience or 0
    
    if data.subjects:
        subject_ids = data.subjects.get("subject_ids") or data.subject_ids or []
        grade_ids = data.subjects.get("grade_ids") or data.grade_ids or []
        primary_subject_id = data.subjects.get("primary_subject_id") or data.primary_subject_id
        max_periods_per_week = data.subjects.get("max_periods_per_week") or data.max_periods_per_week or 24
    else:
        subject_ids = data.subject_ids or []
        grade_ids = data.grade_ids or []
        primary_subject_id = data.primary_subject_id
        max_periods_per_week = data.max_periods_per_week or 24
    
    if data.schedule:
        contract_type = data.schedule.get("contract_type") or data.contract_type or "permanent"
        available_days = data.schedule.get("available_days") or data.available_days or []
        hire_date = data.schedule.get("hire_date") or data.hire_date
    else:
        contract_type = data.contract_type or "permanent"
        available_days = data.available_days or []
        hire_date = data.hire_date
    
    # Validate required fields
    if not full_name:
        raise HTTPException(status_code=400, detail="الاسم مطلوب")
    if not email:
        raise HTTPException(status_code=400, detail="البريد الإلكتروني مطلوب")
    if not phone:
        raise HTTPException(status_code=400, detail="رقم الهاتف مطلوب")
    
    # Check if email exists
    existing = await gd_find_one(db.session, "users", {"email": email})
    if existing:
        raise HTTPException(status_code=400, detail="البريد الإلكتروني مسجل مسبقاً")

    # Check if phone exists (uniqueness across users)
    if phone:
        existing_phone = await gd_find_one(db.session, "users", {"phone": phone})
        if existing_phone:
            raise HTTPException(status_code=400, detail="رقم الهاتف مسجل مسبقاً")

    # Check if national_id is unique among teachers in same school
    if national_id:
        existing_nid = await gd_find_one(
            db.session, "teachers",
            {"national_id": national_id, "school_id": school_id}
        )
        if existing_nid:
            raise HTTPException(status_code=400, detail="رقم الهوية الوطنية مسجل مسبقاً")

    # Get school info
    school = await gd_find_one(db.session, "schools", {"id": school_id})
    school_code = school.get("code", "NSS") if school else "NSS"
    
    # Generate IDs and password
    teacher_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    temp_password = f"Tch{uuid.uuid4().hex[:8]}!"
    
    # Create teacher document
    teacher_doc = {
        "id": teacher_id,
        "school_id": school_id,
        "user_id": user_id,
        "full_name": full_name,
        "full_name_en": full_name_en or full_name,
        "email": email,
        "phone": phone,
        "national_id": national_id,
        "gender": gender,
        "nationality": nationality,
        "date_of_birth": date_of_birth,
        "specialization": specialization or primary_subject_id or (subject_ids[0] if subject_ids else None),
        "primary_subject_id": primary_subject_id,
        "subject_ids": subject_ids,
        "grade_ids": grade_ids,
        "qualification": academic_degree,
        "rank": teacher_rank,
        "contract_type": contract_type,
        "years_of_experience": years_of_experience,
        "max_periods_per_week": max_periods_per_week,
        "available_days": available_days,
        "hire_date": hire_date or datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "is_active": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    
    # Create user document
    user_doc = {
        "id": user_id,
        "email": email,
        "password_hash": hash_password(temp_password),
        "full_name": full_name,
        "full_name_en": full_name_en or full_name,
        "role": "teacher",
        "is_active": True,
        "is_suspended": False,
        "must_change_password": True,
        "tenant_id": school_id,
        "school_id": school_id,
        "teacher_id": teacher_id,
        "phone": phone,
        "permissions": [
            "view_students", "manage_attendance", "manage_grades",
            "view_schedule", "manage_behavior", "view_reports"
        ],
        "preferred_language": "ar",
        "preferred_theme": "light",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    
    await gd_insert(db.session, "teachers", teacher_doc)
    await gd_insert(db.session, "users", user_doc)
    
    # Update school teacher count
    await _gd_inc(db.session, "schools", {"id": school_id}, {"current_teachers": 1})
    
    return {
        "success": True,
        "teacher": {
            "id": teacher_id,
            "full_name": full_name,
            "email": email,
            "temp_password": temp_password,
            "specialization": specialization,
            "rank": teacher_rank,
        },
        "teacher_id": teacher_id,
        "user_account": {
            "created": True,
            "email": email,
            "temp_password": temp_password,
        },
        "message": "تم إنشاء حساب المعلم بنجاح"
    }

@router.post("/teachers")
async def create_teacher(
    teacher_data: TeacherCreate,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.SCHOOL_SUB_ADMIN]))
):
    """Create a new teacher"""
    school_id = getattr(teacher_data, 'school_id', None) or current_user.get("tenant_id")
    if not school_id:
        raise HTTPException(status_code=400, detail="يجب تحديد المدرسة / School context is required")
    user_tenant = current_user.get("tenant_id")
    if user_tenant and school_id != user_tenant:
        raise HTTPException(status_code=403, detail="لا يمكنك إنشاء معلم في مدرسة أخرى / Cannot create teacher in another school")
    teacher_data.school_id = school_id

    # Check if email already exists
    existing = await gd_find_one(db.session, "users", {"email": teacher_data.email})
    if existing:
        raise HTTPException(status_code=400, detail="البريد الإلكتروني مسجل مسبقاً")
    
    # Create user account for teacher
    user_id = str(uuid.uuid4())
    teacher_id = str(uuid.uuid4())
    
    temp_password = f"Tch{uuid.uuid4().hex[:8]}!"
    user_doc = {
        "id": user_id,
        "email": teacher_data.email,
        "password_hash": hash_password(temp_password),
        "full_name": teacher_data.full_name,
        "full_name_en": teacher_data.full_name_en,
        "role": UserRole.TEACHER.value,
        "tenant_id": teacher_data.school_id,
        "phone": teacher_data.phone,
        "avatar_url": None,
        "is_active": True,
        "must_change_password": True,
        "preferred_language": "ar",
        "preferred_theme": "light",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    
    teacher_doc = {
        "id": teacher_id,
        "user_id": user_id,
        "full_name": teacher_data.full_name,
        "full_name_en": teacher_data.full_name_en,
        "email": teacher_data.email,
        "phone": teacher_data.phone,
        "school_id": teacher_data.school_id,
        "specialization": teacher_data.specialization,
        "years_of_experience": teacher_data.years_of_experience or 0,
        "qualification": teacher_data.qualification,
        "gender": teacher_data.gender,
        "is_active": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    
    await gd_insert(db.session, "users", user_doc)
    await gd_insert(db.session, "teachers", teacher_doc)
    
    # Update school teacher count
    await _gd_inc(db.session, "schools", {"id": teacher_data.school_id}, {"current_teachers": 1})

    try:
        from routes.school_settings_mod import _ensure_teacher_linked_to_all_classes
        await _ensure_teacher_linked_to_all_classes(teacher_data.school_id, teacher_id)
    except Exception as e:
        logger.warning(f"Auto-assign teacher {teacher_id} to classes failed: {e}")
    
    response = TeacherResponse(**teacher_doc)
    response_data = response.dict() if hasattr(response, 'dict') else response.model_dump()
    response_data["temp_password"] = temp_password
    return response_data

@router.get("/teachers", response_model=List[TeacherResponse])
async def get_teachers(
    school_id: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """Get all teachers or filter by school"""
    query = {"status": {"$ne": "closed"}}
    if school_id:
        query["school_id"] = school_id
    elif current_user.get("role") != UserRole.PLATFORM_ADMIN.value:
        query["school_id"] = current_user.get("tenant_id")
    
    teachers = await gd_find(db.session, "teachers", query, limit=1000)
    
    # Normalize field names for consistency
    result = []
    for t in teachers:
        # Map full_name_ar to full_name if needed
        if not t.get("full_name") and t.get("full_name_ar"):
            t["full_name"] = t["full_name_ar"]
        # Map subject_name to specialization if needed
        if not t.get("specialization") and t.get("subject_name"):
            t["specialization"] = t["subject_name"]
        result.append(TeacherResponse(**t))
    return result

@router.get("/teachers/me", response_model=TeacherResponse)
async def get_my_teacher_profile(current_user: dict = Depends(get_current_user)):
    """E-02: Return the teacher row associated with the logged-in user.
    Resolution order: enriched JWT teacher_id → teachers.user_id → email.
    Any role with a linked teacher row is allowed (teacher, principal-with-teaching-load, etc.)."""
    teacher = None
    tid = current_user.get("teacher_id")
    if tid:
        teacher = await gd_find_one(db.session, "teachers", {"id": tid})
    if not teacher:
        teacher = await gd_find_one(db.session, "teachers", {"user_id": current_user.get("id")})
    # Fallback by email is tenant-scoped to prevent cross-tenant resolution.
    if not teacher and current_user.get("email"):
        q = {"email": current_user.get("email")}
        if current_user.get("tenant_id"):
            q["school_id"] = current_user.get("tenant_id")
        teacher = await gd_find_one(db.session, "teachers", q)
    if not teacher:
        raise HTTPException(status_code=404, detail="لا يوجد ملف معلم مرتبط بالحساب")
    # Defensive cross-tenant guard: even if a row was returned, verify it belongs
    # to the caller's tenant when both sides have a tenant.
    if current_user.get("tenant_id") and teacher.get("school_id") and teacher.get("school_id") != current_user.get("tenant_id"):
        raise HTTPException(status_code=404, detail="لا يوجد ملف معلم مرتبط بالحساب")
    if not teacher.get("full_name") and teacher.get("full_name_ar"):
        teacher["full_name"] = teacher["full_name_ar"]
    if not teacher.get("specialization") and teacher.get("subject_name"):
        teacher["specialization"] = teacher["subject_name"]
    return TeacherResponse(**teacher)


@router.get("/teachers/{teacher_id}", response_model=TeacherResponse)
async def get_teacher(teacher_id: str, current_user: dict = Depends(get_current_user)):
    """Get teacher by ID"""
    teacher = await gd_find_one(db.session, "teachers", {"id": teacher_id})
    if not teacher:
        raise HTTPException(status_code=404, detail="المعلم غير موجود")
    # Normalize field names
    if not teacher.get("full_name") and teacher.get("full_name_ar"):
        teacher["full_name"] = teacher["full_name_ar"]
    if not teacher.get("specialization") and teacher.get("subject_name"):
        teacher["specialization"] = teacher["subject_name"]
    return TeacherResponse(**teacher)

@router.put("/teachers/{teacher_id}")
async def update_teacher(
    teacher_id: str,
    teacher_data: TeacherUpdate,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.SCHOOL_SUB_ADMIN]))
):
    """Update teacher"""
    # Build update dict with only provided fields
    update_fields = {"updated_at": datetime.now(timezone.utc).isoformat()}
    
    if teacher_data.full_name is not None:
        update_fields["full_name"] = teacher_data.full_name
    if teacher_data.full_name_en is not None:
        update_fields["full_name_en"] = teacher_data.full_name_en
    if teacher_data.email is not None:
        update_fields["email"] = teacher_data.email
    if teacher_data.phone is not None:
        update_fields["phone"] = teacher_data.phone
    if teacher_data.specialization is not None:
        update_fields["specialization"] = teacher_data.specialization
    if teacher_data.years_of_experience is not None:
        update_fields["years_of_experience"] = teacher_data.years_of_experience
    if teacher_data.qualification is not None:
        update_fields["qualification"] = teacher_data.qualification
    if teacher_data.gender is not None:
        update_fields["gender"] = teacher_data.gender
    if teacher_data.is_active is not None:
        update_fields["is_active"] = teacher_data.is_active
    if teacher_data.preferences is not None:
        update_fields["preferences"] = teacher_data.preferences
    if teacher_data.constraints is not None:
        update_fields["constraints"] = teacher_data.constraints

    result = await gd_update_one(db.session, "teachers", {"id": teacher_id}, update_fields)
    if result == 0:
        raise HTTPException(status_code=404, detail="المعلم غير موجود")

    if "full_name" in update_fields:
        new_name = update_fields["full_name"]
        await gd_update_many(db.session, "teacher_assignments", {"teacher_id": teacher_id}, {"teacher_name": new_name})
        await gd_update_many(db.session, "schedule_sessions", {"teacher_id": teacher_id}, {"teacher_name": new_name})

    return {"message": "تم تحديث بيانات المعلم", "success": True}

@router.delete("/teachers/{teacher_id}")
async def delete_teacher(
    teacher_id: str,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN]))
):
    """Delete teacher — full removal from system"""
    teacher = await gd_find_one(db.session, "teachers", {"id": teacher_id})
    if not teacher:
        raise HTTPException(status_code=404, detail="المعلم غير موجود")
    
    school_id = teacher.get("school_id")
    user_id = teacher.get("user_id")

    cleanup = {}
    await gd_delete_one(db.session, "teachers", {"id": teacher_id})

    await _gd_inc(db.session, "schools", {"id": school_id}, {"current_teachers": -1})

    r = await gd_delete_many(db.session, "teacher_assignments", {"teacher_id": teacher_id})
    cleanup["teacher_assignments"] = r
    r = await gd_delete_many(db.session, "teacher_class_assignments", {"teacher_id": teacher_id})
    cleanup["teacher_class_assignments"] = r
    r = await gd_delete_many(db.session, "teacher_subjects", {"teacher_id": teacher_id})
    cleanup["teacher_subjects"] = r
    r = await gd_delete_many(db.session, "teacher_attendance", {"teacher_id": teacher_id})
    cleanup["teacher_attendance"] = r
    r = await gd_delete_many(db.session, "timetable_sessions", {"teacher_id": teacher_id})
    cleanup["timetable_sessions"] = r
    r = await gd_delete_many(db.session, "class_sessions", {"teacher_id": teacher_id})
    cleanup["class_sessions"] = r
    r = await gd_delete_many(db.session, "session_event_log", {"teacher_id": teacher_id})
    cleanup["session_event_log"] = r
    r = await gd_delete_many(db.session, "user_relationships", {"$or": [{"source_id": teacher_id}, {"target_id": teacher_id}]})
    cleanup["user_relationships"] = r

    if user_id:
        await gd_delete_one(db.session, "users", {"id": user_id})
        await gd_delete_many(db.session, "user_roles", {"user_id": user_id})
        await gd_delete_many(db.session, "user_identities", {"user_id": user_id})
        cleanup["user_account"] = 1

    return {"message": "تم حذف المعلم وجميع بياناته من النظام بالكامل", "success": True, "cleanup": cleanup}


@router.delete("/parents/{parent_id}")
async def delete_parent(
    parent_id: str,
    # Task #201 — IT §5.7 widens this allow-list to include
    # INDEPENDENT_TEACHER so IT callers can manage parents in their own
    # workspace. Non-IT roles see exactly the same allow-list as before.
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.INDEPENDENT_TEACHER])),
    _mfa: dict = Depends(_REQUIRE_RECENT_MFA_403_IT),
):
    """Delete parent — full removal from system"""
    # Task #201 — fall back to the synthetic IT workspace id so the
    # tenant filter scopes correctly for IT callers (their tenant_id is
    # NULL on the users row). `gd_*` aliases tenant_id ↔ school_id, so
    # the existing query shape continues to work.
    from auth_scope import independent_workspace_id as _itw_id
    tenant_id = current_user.get("tenant_id") or _itw_id(current_user)
    parent = await gd_find_one(db.session, "parents", {"id": parent_id, "tenant_id": tenant_id})
    if not parent:
        raise HTTPException(status_code=404, detail="ولي الأمر غير موجود")

    user_id = parent.get("user_id")

    cleanup = {}
    await gd_delete_one(db.session, "parents", {"id": parent_id})

    r = await gd_delete_many(db.session, "guardian_links", {"parent_id": parent_id})
    cleanup["guardian_links"] = r
    r = await gd_delete_many(db.session, "user_relationships", {"$or": [{"source_id": parent_id}, {"target_id": parent_id}]})
    cleanup["user_relationships"] = r

    matching_students = await gd_find(db.session, "students", {"parent_ids": parent_id})
    for stu in matching_students:
        await _gd_pull(db.session, "students", {"id": stu["id"]}, {"parent_ids": parent_id})

    if user_id:
        await gd_delete_one(db.session, "users", {"id": user_id})
        await gd_delete_many(db.session, "user_roles", {"user_id": user_id})
        await gd_delete_many(db.session, "user_identities", {"user_id": user_id})
        cleanup["user_account"] = 1

    return {"message": "تم حذف ولي الأمر وجميع بياناته من النظام بالكامل", "success": True, "cleanup": cleanup}


# ============== GLOBAL TALENTS ==============

@router.get("/talents")
async def get_global_talents(
    current_user: dict = Depends(get_current_user)
):
    tenant_id = current_user.get("tenant_id")
    query = {"$or": [{"is_global": True}]}
    if tenant_id:
        query["$or"].append({"tenant_id": tenant_id})
    talents = await gd_find(db.session, "global_talents", query, order_by="name_ar", desc_order=False, limit=500)
    return {"talents": talents}


@router.post("/talents")
async def create_custom_talent(
    data: dict = Body(...),
    current_user: dict = Depends(require_roles([UserRole.SCHOOL_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.TEACHER]))
):
    name_ar = data.get("name_ar", "").strip()
    name_en = data.get("name_en", "").strip()
    if not name_ar:
        raise HTTPException(400, "اسم الموهبة بالعربية مطلوب")
    tenant_id = current_user.get("tenant_id")
    value_key = re.sub(r'\s+', '_', name_ar).lower()
    existing = await gd_find_one(db.session, "global_talents", {
        "$or": [
            {"name_ar": name_ar, "$or": [{"is_global": True}, {"tenant_id": tenant_id}]},
            {"value": value_key, "$or": [{"is_global": True}, {"tenant_id": tenant_id}]}
        ]
    })
    if existing:
        raise HTTPException(400, "هذه الموهبة موجودة بالفعل")
    talent_doc = {
        "id": str(uuid.uuid4()),
        "value": value_key,
        "name_ar": name_ar,
        "name_en": name_en or name_ar,
        "tenant_id": tenant_id,
        "is_global": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by": current_user["id"]
    }
    await gd_insert(db.session, "global_talents", talent_doc)
    talent_doc.pop("_id", None)
    return talent_doc
