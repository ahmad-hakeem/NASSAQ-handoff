"""
NASSAQ Academics Sub-module
"""
from fastapi import APIRouter, HTTPException, Depends, status, Header, Query, Body, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import Response
from starlette.responses import StreamingResponse
from pydantic import AliasChoices, BaseModel, Field, ConfigDict, EmailStr, model_validator
from typing import List, Optional, Any, Dict
from datetime import datetime, timezone, timedelta
import uuid, os, logging, json, random, re, io, base64
from sqlalchemy import select, or_, func
from sqlalchemy.exc import IntegrityError

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
from engines.sql_utils import gd_find, gd_find_one, gd_insert, gd_insert_many, gd_update_one, gd_update_many, gd_count, gd_delete_one, gd_delete_many, gd_distinct, _gd_pull
from engines.entity_counts import reconcile_school_counts
from src.core.guards.tenant_guard import require_request_school_id
from src.common.utils.date_only import resolve_optional_birth_dates
from pg_models import Teacher, User


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
    from src.common.utils.tenant_scope import resolve_school_id
    return resolve_school_id(current_user, x_school_context)

# ============== TEACHERS ROUTES ==============

# Teacher Wizard Options
@router.get("/teachers/options/subjects")
async def get_teacher_subjects_options(current_user: dict = Depends(get_current_user)):
    """Get available subjects for the current school's teacher wizard.

    Sources, in order of preference:
      1. School-scoped + global subjects from `subjects` table
      2. Reference subjects from `reference_subjects` (the standard catalog)

    Returns a (possibly empty) list under ``subjects``. When the school has
    no subjects of its own and the reference catalog is empty, an empty list
    is returned so the wizard can show a clear "add subjects first" empty
    state instead of fabricating display-only rows with non-UUID ids that
    would later fail validation on teacher creation.
    """
    tenant_id = current_user.get("tenant_id")

    try:
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
    except Exception as exc:
        logger.warning(
            "Failed to load teacher subject options for tenant %s: %s",
            tenant_id, exc,
        )
        raise HTTPException(
            status_code=500,
            detail="تعذر تحميل قائمة المواد الدراسية. يرجى المحاولة مرة أخرى.",
        )

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
    query = {"school_id": school_id, "is_active": {"$ne": False}}
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
    date_of_birth: Optional[str] = Field(
        None,
        validation_alias=AliasChoices("date_of_birth", "birthDateGregorian"),
    )
    birth_date_hijri: Optional[str] = Field(
        None,
        validation_alias=AliasChoices("birth_date_hijri", "birthDateHijri"),
    )
    subject_ids: Optional[List[str]] = []
    grade_ids: Optional[List[str]] = []
    primary_subject_id: Optional[str] = None
    academic_degree: Optional[str] = None
    specialization: Optional[str] = None
    teacher_rank: Optional[str] = None
    contract_type: Optional[str] = "permanent"
    # Kept permissive at the wire boundary so blank strings from HTML forms can
    # be normalized to NULL by the create handler.
    years_of_experience: Optional[Any] = None
    hire_date: Optional[str] = None
    max_periods_per_week: Optional[int] = 24
    available_days: Optional[List[str]] = []
    
    # Nested structure fields (from frontend wizard)
    basic_info: Optional[dict] = None
    qualifications: Optional[dict] = None
    subjects: Optional[dict] = None
    schedule: Optional[dict] = None


def _normalise_teacher_email(value: Optional[str]) -> Optional[str]:
    """Canonical form used by authentication for identity comparisons."""
    return value.strip().lower() if value and value.strip() else None


def _normalise_teacher_phone(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    digits = re.sub(r"\D", "", value)
    # Treat the common Saudi local/international spellings as one identity.
    if digits.startswith("00966"):
        digits = digits[2:]
    if digits.startswith("966") and len(digits) == 12:
        digits = "0" + digits[3:]
    return digits or None


def _normalise_teacher_national_id(value: Optional[str]) -> Optional[str]:
    return re.sub(r"\D", "", value) or None if value else None


def _teacher_identity_matches(teacher: dict, user: dict, *, email: str, phone: str,
                              national_id: Optional[str]) -> bool:
    """Check the authoritative profile and reject only real user-row conflicts.

    ``teachers`` owns national ID and mobile.  Older create paths did not
    always copy mobile to ``users.phone``; NULL therefore supplies no
    contradictory identity evidence.  A populated, different user phone still
    fails closed.
    """
    if _normalise_teacher_email(teacher.get("email")) != email:
        return False
    if _normalise_teacher_email(user.get("email")) != email:
        return False
    if _normalise_teacher_phone(teacher.get("phone")) != phone:
        return False
    user_phone = _normalise_teacher_phone(user.get("phone"))
    if user_phone is not None and user_phone != phone:
        return False
    if national_id is not None:
        return _normalise_teacher_national_id(teacher.get("national_id")) == national_id
    return True


def _teacher_identity_error(code: str, message: str) -> HTTPException:
    """Identity errors are safe for tenant callers and disclose no owner data."""
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={"code": code, "message": message},
    )


def _phone_search_values(phone: Optional[str]) -> set[str]:
    if not phone:
        return set()
    values = {phone}
    if phone.startswith("05") and len(phone) == 10:
        values.update({"966" + phone[1:], "00966" + phone[1:]})
    return values


async def _lock_teacher_identity(
    school_id: str, *, email: Optional[str], phone: Optional[str],
    national_id: Optional[str],
) -> None:
    """Serialize only requests which compete for one identity key."""
    identity_lock_keys = set()
    if email:
        identity_lock_keys.add(f"teacher-email:{email}")
    if phone:
        identity_lock_keys.add(f"teacher-phone:{phone}")
    if national_id:
        identity_lock_keys.add(f"teacher-nid:{school_id}:{national_id}")
    for lock_key in sorted(identity_lock_keys):
        await db.session.execute(
            select(func.pg_advisory_xact_lock(func.hashtext(lock_key)))
        )


async def _has_known_administrative_suspension(
    user: dict, teacher_id: str,
) -> bool:
    """Use canonical status and reliable audit history for legacy rows."""
    if user.get("status") not in (None, "active"):
        return True
    latest_delete = await gd_find(
        db.session,
        "audit_logs",
        {"entity_type": "teacher", "entity_id": teacher_id, "action": "delete"},
        order_by="timestamp",
        desc_order=True,
        limit=1,
    )
    if latest_delete:
        previous = latest_delete[0].get("previous_state") or {}
        if previous.get("user_was_active") is False:
            return True
    latest_status = await gd_find(
        db.session,
        "audit_logs",
        {
            "target_id": user["id"],
            "action": {"$in": ["user_suspended", "user_activated"]},
        },
        order_by="timestamp",
        desc_order=True,
        limit=1,
    )
    if latest_status:
        return latest_status[0].get("action") == "user_suspended"
    return False


async def _restorable_teacher_for_wizard(
    school_id: str, *, email: str, phone: Optional[str], national_id: Optional[str],
) -> Optional[str]:
    """Resolve one globally unambiguous, same-school retained identity.

    Candidate discovery starts from the authoritative teacher profile (not
    ``users.phone``), then verifies account ownership and global contact
    collisions.  Ambiguity is surfaced for manual review instead of falling
    through to a misleading generic duplicate.
    """
    digits = lambda column: func.regexp_replace(column, r"\D", "", "g")
    phone_values = _phone_search_values(phone)
    teacher_predicates = [
        func.lower(func.trim(Teacher.email)) == email,
        digits(Teacher.phone).in_(phone_values),
    ]
    if national_id:
        teacher_predicates.append(digits(Teacher.national_id) == national_id)
    teacher_objs = (await db.session.execute(
        select(Teacher).where(or_(*teacher_predicates))
    )).scalars().all()
    teachers = [
        {c.name: getattr(obj, c.name) for c in obj.__table__.columns}
        for obj in teacher_objs
    ]
    user_predicates = [
        func.lower(func.trim(User.email)) == email,
        digits(User.phone).in_(phone_values),
    ]
    contact_users = (await db.session.execute(
        select(User).where(or_(*user_predicates))
    )).scalars().all()

    exact = [
        row for row in teachers
        if row.get("school_id") == school_id
        and _normalise_teacher_email(row.get("email")) == email
        and _normalise_teacher_phone(row.get("phone")) == phone
        and (
            national_id is None
            or _normalise_teacher_national_id(row.get("national_id")) == national_id
        )
    ]
    if len(exact) > 1:
        raise _teacher_identity_error(
            "TEACHER_ACCOUNT_REVIEW_REQUIRED",
            "تعذر تحديد حساب معلم واحد بشكل آمن. يلزم مراجعة الإدارة.",
        )
    if not exact:
        if national_id and any(
            row.get("school_id") == school_id
            and _normalise_teacher_national_id(row.get("national_id")) == national_id
            for row in teachers
        ):
            raise _teacher_identity_error(
                "TEACHER_NATIONAL_ID_CONFLICT",
                "رقم الهوية مرتبط ببيانات معلم مختلفة ويلزم مراجعته.",
            )
        if phone and any(
            _normalise_teacher_phone(row.get("phone")) == phone for row in teachers
        ):
            raise _teacher_identity_error(
                "TEACHER_MOBILE_CONFLICT",
                "رقم الجوال مرتبط بحساب آخر ولا يمكن استخدامه.",
            )
        if teachers:
            raise _teacher_identity_error(
                "TEACHER_ACCOUNT_REVIEW_REQUIRED",
                "توجد هوية محتفظ بها تتطلب مراجعة الإدارة.",
            )
        if contact_users:
            if phone and any(
                _normalise_teacher_phone(row.phone) == phone
                for row in contact_users
            ):
                raise _teacher_identity_error(
                    "TEACHER_MOBILE_CONFLICT",
                    "رقم الجوال مرتبط بحساب آخر ولا يمكن استخدامه.",
                )
            raise _teacher_identity_error(
                "TEACHER_ACCOUNT_REVIEW_REQUIRED",
                "بيانات الدخول مرتبطة بحساب محتفظ به ويلزم مراجعة الإدارة.",
            )
        return None

    teacher = exact[0]
    # A matching contact/profile anywhere else makes ownership ambiguous.
    for row in teachers:
        if row["id"] == teacher["id"]:
            continue
        if phone and _normalise_teacher_phone(row.get("phone")) == phone:
            raise _teacher_identity_error(
                "TEACHER_MOBILE_CONFLICT",
                "رقم الجوال مرتبط بحساب آخر ولا يمكن استخدامه.",
            )
        raise _teacher_identity_error(
            "TEACHER_ACCOUNT_REVIEW_REQUIRED",
            "توجد هوية محتفظ بها تتطلب مراجعة الإدارة.",
        )

    linked_objs = (await db.session.execute(
        select(User).where(or_(
            User.id == teacher.get("user_id"),
            User.teacher_id == teacher["id"],
        ))
    )).scalars().all()
    if len(linked_objs) != 1:
        raise _teacher_identity_error(
            "TEACHER_ACCOUNT_REVIEW_REQUIRED",
            "تعذر إثبات ملكية الحساب بشكل منفرد. يلزم مراجعة الإدارة.",
        )
    user_obj = linked_objs[0]
    user = {c.name: getattr(user_obj, c.name) for c in user_obj.__table__.columns}
    reverse_teacher_ids = set((await db.session.execute(
        select(Teacher.id).where(or_(
            Teacher.user_id == user["id"],
            Teacher.id == user.get("teacher_id"),
        ))
    )).scalars().all())
    if reverse_teacher_ids != {teacher["id"]}:
        raise _teacher_identity_error(
            "TEACHER_ACCOUNT_REVIEW_REQUIRED",
            "الحساب مرتبط بأكثر من ملف معلم ويلزم مراجعة الإدارة.",
        )
    # At most one side of the reciprocal link may be absent; disagreement is
    # never repaired automatically.
    if (
        teacher.get("user_id") not in (None, user["id"])
        or user.get("teacher_id") not in (None, teacher["id"])
        or (teacher.get("user_id") is None and user.get("teacher_id") is None)
        or user.get("role") != UserRole.TEACHER.value
        or user.get("tenant_id") != school_id
    ):
        raise _teacher_identity_error(
            "TEACHER_ACCOUNT_REVIEW_REQUIRED",
            "تعذر إثبات ارتباط حساب المعلم بالمدرسة. يلزم مراجعة الإدارة.",
        )
    if not _teacher_identity_matches(
        teacher, user, email=email, phone=phone, national_id=national_id
    ):
        code = (
            "TEACHER_MOBILE_CONFLICT"
            if _normalise_teacher_phone(user.get("phone")) not in (None, phone)
            else "TEACHER_ACCOUNT_REVIEW_REQUIRED"
        )
        raise _teacher_identity_error(
            code, "بيانات الحساب المحتفظ به متعارضة ويلزم مراجعتها.",
        )

    if any(other.id != user["id"] for other in contact_users):
        if any(
            other.id != user["id"]
            and _normalise_teacher_phone(other.phone) == phone
            for other in contact_users
        ):
            raise _teacher_identity_error(
                "TEACHER_MOBILE_CONFLICT",
                "رقم الجوال مرتبط بحساب آخر ولا يمكن استخدامه.",
            )
        raise _teacher_identity_error(
            "TEACHER_ACCOUNT_REVIEW_REQUIRED",
            "بيانات الدخول مرتبطة بحساب آخر ويلزم مراجعة الإدارة.",
        )

    if teacher.get("is_active") is not False or teacher.get("deleted_at") is None:
        raise _teacher_identity_error(
            "TEACHER_ACTIVE_DUPLICATE",
            "المعلم مسجل ونشط مسبقاً.",
        )
    # Deletion leaves status as active. Explicit suspension/lock states are
    # administrative safeguards and must never be cleared by teacher restore.
    if (
        user.get("is_active") is not False
        or await _has_known_administrative_suspension(user, teacher["id"])
    ):
        raise _teacher_identity_error(
            "TEACHER_ACCOUNT_REVIEW_REQUIRED",
            "الحساب المحتفظ به غير قابل للاستعادة التلقائية ويلزم مراجعته.",
        )
    return teacher["id"]

async def _check_teacher_create_identity(school_id, *, email, phone, national_id=None):
    """Shared by both creation APIs; run before inserting either identity row."""
    await _lock_teacher_identity(
        school_id, email=email, phone=phone, national_id=national_id,
    )
    restore_teacher_id = await _restorable_teacher_for_wizard(
        school_id, email=email, phone=phone, national_id=national_id,
    )
    if restore_teacher_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "TEACHER_RESTORE_AVAILABLE",
                "message": "هذا المعلم محذوف سابقاً. أكّد استعادة حسابه الحالي بدلاً من إنشاء حساب جديد.",
                "teacher_id": restore_teacher_id,
            },
        )
    if await gd_find_one(db.session, "users", {"email": email}):
        raise HTTPException(status_code=400, detail="البريد الإلكتروني مسجل مسبقاً")
    if phone and await gd_find_one(db.session, "users", {"phone": phone}):
        raise HTTPException(status_code=400, detail="رقم الهاتف مسجل مسبقاً")
    if national_id and await gd_find_one(
        db.session, "teachers", {"national_id": national_id, "school_id": school_id},
    ):
        raise HTTPException(status_code=400, detail="رقم الهوية الوطنية مسجل مسبقاً")


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
        if "date_of_birth" in data.basic_info:
            date_of_birth = data.basic_info["date_of_birth"]
        elif "birthDateGregorian" in data.basic_info:
            date_of_birth = data.basic_info["birthDateGregorian"]
        else:
            date_of_birth = data.date_of_birth
        if "birth_date_hijri" in data.basic_info:
            birth_date_hijri = data.basic_info["birth_date_hijri"]
        elif "birthDateHijri" in data.basic_info:
            birth_date_hijri = data.basic_info["birthDateHijri"]
        else:
            birth_date_hijri = data.birth_date_hijri
    else:
        full_name = data.full_name
        full_name_en = data.full_name_en
        email = data.email
        phone = data.phone
        national_id = data.national_id
        gender = data.gender
        nationality = data.nationality
        date_of_birth = data.date_of_birth
        birth_date_hijri = data.birth_date_hijri

    try:
        date_of_birth, birth_date_hijri = resolve_optional_birth_dates(
            date_of_birth, birth_date_hijri
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"date_of_birth/birth_date_hijri: {exc}",
        ) from exc
    
    qualifications = data.qualifications or {}

    def _optional_text(value):
        if value is None:
            return None
        if not isinstance(value, str):
            raise HTTPException(status_code=422, detail="المؤهل والرتبة يجب أن يكونا نصاً")
        value = value.strip()
        return value or None

    def _optional_experience(value):
        if isinstance(value, str):
            value = value.strip()
        if value is None or value == "":
            return None
        if isinstance(value, bool):
            raise HTTPException(status_code=422, detail="years_of_experience: سنوات الخبرة يجب أن تكون عدداً صحيحاً")
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            raise HTTPException(status_code=422, detail="years_of_experience: سنوات الخبرة يجب أن تكون عدداً صحيحاً")
        if isinstance(value, float) and value != parsed:
            raise HTTPException(status_code=422, detail="years_of_experience: سنوات الخبرة يجب أن تكون عدداً صحيحاً")
        if parsed < 0:
            raise HTTPException(status_code=422, detail="years_of_experience: سنوات الخبرة يجب أن تكون صفراً أو أكثر")
        return parsed

    def _qualification_value(name):
        return qualifications[name] if name in qualifications else getattr(data, name)

    academic_degree = _optional_text(_qualification_value("academic_degree"))
    specialization = _optional_text(_qualification_value("specialization"))
    teacher_rank = _optional_text(_qualification_value("teacher_rank"))
    years_of_experience = _optional_experience(_qualification_value("years_of_experience"))

    # Keep these sets in lockstep with the option endpoints, including their
    # existing fallback catalogs.  Lookup values are intentionally loaded at
    # write time so newly activated options are accepted without deployment.
    degree_rows = await gd_find(
        db.session, "lookup_options",
        {"type": "academic_degree", "is_active": {"$ne": False}}, limit=20,
    )
    supported_degrees = {
        row.get("code", row.get("id")) for row in degree_rows
        if row.get("code", row.get("id"))
    } or {"diploma", "bachelor", "master", "doctorate"}

    rank_rows = await gd_find(
        db.session, "lookup_options",
        {"type": "teacher_rank", "is_active": {"$ne": False}},
        order_by="order", desc_order=False, limit=100,
    )
    if not rank_rows:
        rank_rows = await gd_find(
            db.session, "teacher_ranks", {"is_active": True},
            order_by="order", desc_order=False, limit=100,
        )
    supported_ranks = {
        row.get("id") or row.get("code") for row in rank_rows
        if row.get("id") or row.get("code")
    } or {"teacher", "senior_teacher", "expert", "department_head"}
    if academic_degree is not None and academic_degree not in supported_degrees:
        raise HTTPException(status_code=422, detail="academic_degree غير مدعوم")
    if teacher_rank is not None and teacher_rank not in supported_ranks:
        raise HTTPException(status_code=422, detail="teacher_rank غير مدعوم")
    
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

    canonical_email = _normalise_teacher_email(email)
    canonical_phone = _normalise_teacher_phone(phone)
    canonical_national_id = _normalise_teacher_national_id(national_id)
    if (
        not canonical_email
        or "@" not in canonical_email
        or not canonical_phone
        or len(canonical_phone) < 7
        or (national_id is not None and not canonical_national_id)
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "TEACHER_IDENTITY_INVALID",
                "message": "البريد الإلكتروني أو رقم الجوال أو الهوية غير صالح.",
            },
        )

    # Serialize narrow identity keys. This closes the check-then-insert race
    # without locking unrelated teacher creation requests.
    await _check_teacher_create_identity(
        school_id,
        email=canonical_email,
        phone=canonical_phone,
        national_id=canonical_national_id,
    )

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
        "email": canonical_email,
        "phone": canonical_phone,
        "national_id": canonical_national_id,
        "gender": gender,
        "nationality": nationality,
        "date_of_birth": date_of_birth,
        "specialization": specialization or primary_subject_id or (subject_ids[0] if subject_ids else None),
        "primary_subject_id": primary_subject_id,
        "subject_ids": subject_ids,
        "grade_ids": grade_ids,
        "qualification": academic_degree,
        "academic_degree": academic_degree,
        "rank": teacher_rank,
        "teacher_rank": teacher_rank,
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
        "email": canonical_email,
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
        "phone": canonical_phone,
        "permissions": [
            "view_students", "manage_attendance", "manage_grades",
            "view_schedule", "manage_behavior", "view_reports"
        ],
        "preferred_language": "ar",
        "preferred_theme": "light",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    
    try:
        # If a database uniqueness constraint wins a race, the savepoint rolls
        # back both rows rather than leaving an orphan teacher profile.
        async with db.session.begin_nested():
            await gd_insert(db.session, "teachers", teacher_doc)
            await gd_insert(db.session, "users", user_doc)
    except IntegrityError:
        raise _teacher_identity_error(
            "TEACHER_ACCOUNT_REVIEW_REQUIRED",
            "تزامن إنشاء حساب آخر بالهوية نفسها. يرجى المراجعة والمحاولة مجدداً.",
        )
    
    # Reconcile school counts from live rows (Task #826) instead of nudging ±1.
    await reconcile_school_counts(db.session, school_id)
    
    return {
        "success": True,
        "teacher": {
            "id": teacher_id,
            "full_name": full_name,
            "email": email,
            "temp_password": temp_password,
            "specialization": specialization,
            "rank": teacher_rank,
            "date_of_birth": date_of_birth,
            "birth_date_hijri": birth_date_hijri,
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
    from src.common.utils.tenant_scope import resolve_school_id
    school_id = resolve_school_id(current_user, getattr(teacher_data, 'school_id', None)) or current_user.get("tenant_id")
    if not school_id:
        raise HTTPException(status_code=400, detail="يجب تحديد المدرسة / School context is required")
    teacher_data.school_id = school_id

    teacher_data.email = _normalise_teacher_email(teacher_data.email)
    canonical_phone = _normalise_teacher_phone(teacher_data.phone)
    # This API historically permits no phone; a supplied phone must be valid.
    if teacher_data.phone is not None and (not canonical_phone or len(canonical_phone) < 7):
        raise HTTPException(status_code=400, detail={
            "code": "TEACHER_IDENTITY_INVALID",
            "message": "رقم الجوال غير صالح.",
        })
    teacher_data.phone = canonical_phone or None
    await _check_teacher_create_identity(
        school_id, email=teacher_data.email, phone=canonical_phone,
    )
    
    # Create user account for teacher
    user_id = str(uuid.uuid4())
    teacher_id = str(uuid.uuid4())
    
    temp_password = f"Tch{uuid.uuid4().hex[:8]}!"
    user_doc = {
        "id": user_id,
        "teacher_id": teacher_id,
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
        "tenant_id": teacher_data.school_id,
        "specialization": teacher_data.specialization,
        "years_of_experience": teacher_data.years_of_experience or 0,
        "qualification": teacher_data.qualification,
        "academic_degree": teacher_data.qualification,
        "gender": teacher_data.gender,
        "is_active": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    
    await gd_insert(db.session, "users", user_doc)
    await gd_insert(db.session, "teachers", teacher_doc)
    
    # Reconcile school counts from live rows (Task #826) instead of nudging ±1.
    await reconcile_school_counts(db.session, teacher_data.school_id)

    try:
        from src.modules.schools.controllers.school_settings_mod import _ensure_teacher_linked_to_all_classes
        await _ensure_teacher_linked_to_all_classes(teacher_data.school_id, teacher_id)
    except Exception as e:
        logger.warning(f"Auto-assign teacher {teacher_id} to classes failed: {e}")
    
    response = TeacherResponse(**teacher_doc)
    response_data = response.dict() if hasattr(response, 'dict') else response.model_dump()
    response_data["temp_password"] = temp_password
    return response_data

@router.get("/teachers", response_model=List[TeacherResponse])
async def get_teachers(
    include_deleted: bool = Query(default=False),
    x_school_context: Optional[str] = Header(default=None, alias="X-School-Context"),
    current_user: dict = Depends(get_current_user)
):
    """Get all teachers or filter by school.

    Task #508 / Task #511: Platform admins MUST resolve preview scope
    via the `X-School-Context` header through `resolve_school_id`,
    which only honors the override when the bearer token was minted
    by `/role-switch/switch`. When the resolver returns no school
    context (plain PA token without a header, or a token not minted
    via the hardened role-switch flow), the route now FAILS CLOSED
    and returns an empty list — never an unscoped cross-tenant
    teacher directory. Non-platform callers are pinned to their own
    tenant via `resolve_school_id` (mismatched override → 403).

    Task #645 — `include_deleted` exposes soft-deleted teachers
    (``is_active=False`` with ``deleted_at``/``deleted_by`` populated)
    so admins can audit recent deletions and surface candidates for
    restoration. Restricted to platform/school admin roles and IT
    callers (who own their workspace); other callers silently get the
    active-only view regardless of the param.
    """
    from src.common.utils.tenant_scope import resolve_school_id
    query = {"status": {"$ne": "closed"}}
    if current_user.get("role") == UserRole.PLATFORM_ADMIN.value:
        scoped = resolve_school_id(current_user, x_school_context)
        if not scoped:
            return []
        query["school_id"] = scoped
    else:
        query["school_id"] = resolve_school_id(current_user, x_school_context)

    _admin_roles = {
        UserRole.PLATFORM_ADMIN.value,
        UserRole.SCHOOL_PRINCIPAL.value,
        UserRole.SCHOOL_ADMIN.value,
        UserRole.SCHOOL_SUB_ADMIN.value,
        UserRole.INDEPENDENT_TEACHER.value,
    }
    show_deleted = bool(include_deleted) and current_user.get("role") in _admin_roles
    # Regular teachers get a name-only directory; only admin/IT roles see the
    # full record (contact PII + scheduling config).
    _privileged = current_user.get("role") in _admin_roles

    teachers = await gd_find(db.session, "teachers", query, limit=1000)
    if not show_deleted:
        teachers = [t for t in teachers if t.get("is_active") is not False or not t.get("deleted_at")]

    deleted_by_map: Dict[str, str] = {}
    if show_deleted:
        deleter_ids = list({t.get("deleted_by") for t in teachers if t.get("deleted_by")})
        if deleter_ids:
            try:
                deleter_rows = await gd_find(
                    db.session, "users", {"id": {"$in": deleter_ids}}, limit=200
                )
                deleted_by_map = {
                    u.get("id"): (u.get("full_name") or u.get("email") or "")
                    for u in deleter_rows
                    if u.get("id")
                }
            except Exception as _deleter_err:
                logger.warning(
                    f"Failed to resolve deleted_by names for teachers: {_deleter_err}"
                )
                deleted_by_map = {}

    # Normalize field names for consistency
    result = []
    for t in teachers:
        # Map full_name_ar to full_name if needed
        if not t.get("full_name") and t.get("full_name_ar"):
            t["full_name"] = t["full_name_ar"]
        # Map subject_name to specialization if needed
        if not t.get("specialization") and t.get("subject_name"):
            t["specialization"] = t["subject_name"]
        if show_deleted and t.get("deleted_by"):
            t["deleted_by_name"] = deleted_by_map.get(t.get("deleted_by"))
        if not _privileged:
            # A regular teacher only needs a name directory — withhold contact
            # PII and operational scheduling config they have no need to read.
            t["email"] = None
            t["phone"] = None
            t["preferences"] = None
            t["constraints"] = None
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
    if teacher_id.startswith("deleted-teacher:"):
        raise HTTPException(status_code=404, detail="المعلم غير موجود")
    from src.common.utils.tenant_scope import assert_school_access
    teacher = await gd_find_one(db.session, "teachers", {"id": teacher_id})
    if not teacher:
        raise HTTPException(status_code=404, detail="المعلم غير موجود")
    assert_school_access(current_user, teacher.get("school_id"))
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
    if teacher_id.startswith("deleted-teacher:"):
        raise HTTPException(status_code=404, detail="المعلم غير موجود")
    from src.common.utils.tenant_scope import assert_school_access
    existing_teacher = await gd_find_one(db.session, "teachers", {"id": teacher_id})
    if not existing_teacher:
        raise HTTPException(status_code=404, detail="المعلم غير موجود")
    assert_school_access(current_user, existing_teacher.get("school_id"))
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
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.INDEPENDENT_TEACHER]))
):
    """Permanently delete an exclusively school-teacher account.

    School leadership/platform admins use the fail-closed transactional
    retention service. Shared or unproven accounts require platform review.
    Independent-teacher callers retain Task #645's existing soft deletion,
    restore eligibility, and own-workspace restriction (foreign IDs are 404).
    """
    from src.common.utils.tenant_scope import assert_school_access
    from src.core.guards.tenant_guard import is_independent_teacher, independent_workspace_id
    if not is_independent_teacher(current_user):
        from services.teacher_permanent_deletion import permanently_delete_teacher
        return await permanently_delete_teacher(db.session, teacher_id, current_user)
    async with db.session.begin_nested():
        stmt = select(Teacher).where(Teacher.id == teacher_id).with_for_update()
        teacher_obj = (await db.session.execute(stmt)).scalars().first()
        teacher = (
            {c.name: getattr(teacher_obj, c.name) for c in teacher_obj.__table__.columns}
            if teacher_obj else None
        )
        if (
            not teacher or teacher.get("is_active") is False
            or (is_independent_teacher(current_user) and teacher.get("school_id") != independent_workspace_id(current_user))
        ):
            raise HTTPException(status_code=404, detail="المعلم غير موجود")
        if not is_independent_teacher(current_user):
            assert_school_access(current_user, teacher.get("school_id"))

        school_id = teacher.get("school_id")
        user_id = teacher.get("user_id")
        now = datetime.now(timezone.utc)
        now_iso = now.isoformat()
        cleanup: Dict[str, Any] = {}
        user_was_active: Optional[bool] = None
        await gd_update_one(db.session, "teachers", {"id": teacher_id}, {
            "is_active": False, "deleted_at": now_iso, "deleted_by": current_user["id"],
        })
        for collection in (
            "teacher_assignments", "teacher_class_assignments", "teacher_subjects",
            "timetable_sessions", "class_sessions",
        ):
            cleanup[collection] = await gd_update_many(
                db.session, collection,
                {"teacher_id": teacher_id, "is_active": {"$ne": False}},
                {"is_active": False},
            )

        if user_id:
            # Resolve only the mutually-linked, same-school teacher account.
            linked = (await db.session.execute(
                select(User).where(or_(User.id == user_id, User.teacher_id == teacher_id)).with_for_update()
            )).scalars().all()
            if (
                len(linked) != 1 or linked[0].id != user_id
                or linked[0].teacher_id != teacher_id
                or linked[0].tenant_id != school_id
                or linked[0].role != UserRole.TEACHER.value
            ):
                raise HTTPException(status_code=409, detail="تعذر التحقق من ارتباط حساب المعلم")
            user_was_active = linked[0].is_active
            await gd_update_one(db.session, "users", {"id": user_id}, {"is_active": False})
            cleanup["user_account"] = 1

            from src.modules.schools.services.system_settings_service import revoke_session_refresh_chain
            sessions = await gd_find(db.session, "user_sessions", {
                "user_id": user_id, "revoked_at": None,
            }, limit=500)
            for session_row in sessions:
                # Keep the access token dead after a later account restore;
                # deactivating the user alone only protects the deleted period.
                access_jti = session_row.get("jti")
                if access_jti:
                    access_exp = session_row.get("expires_at") or (
                        now + timedelta(minutes=ACCESS_TOKEN_EXPIRE)
                    )
                    await gd_insert(db.session, "revoked_tokens", {
                        "jti": access_jti,
                        "expires_at": (
                            access_exp.isoformat()
                            if hasattr(access_exp, "isoformat") else str(access_exp)
                        ),
                        "revoked_at": now_iso,
                    })
                await revoke_session_refresh_chain(db.session, session_row, now, user_id)
            cleanup["auth_sessions"] = await gd_update_many(
                db.session, "user_sessions",
                {"user_id": user_id, "revoked_at": None},
                {"revoked_at": now_iso},
            )

        await reconcile_school_counts(db.session, school_id)
        audit_log = {
        "id": str(uuid.uuid4()),
        "school_id": school_id,
        "action": "delete",
        "entity_type": "teacher",
        "entity_id": teacher_id,
        "previous_state": {
            "full_name": teacher.get("full_name"),
            "is_active": True,
            "user_was_active": user_was_active,
        },
        "new_state": {
            "is_active": False,
            "deleted_at": now_iso,
            "deleted_by": current_user["id"],
        },
        "performed_by": current_user["id"],
        "performed_by_name": current_user.get("full_name", ""),
        "timestamp": now_iso,
        "ip_address": None,
        }
        await gd_insert(db.session, "audit_logs", audit_log)

    return {
        "message": "تم حذف المعلم بنجاح",
        "success": True,
        "cleanup": cleanup,
    }


@router.post("/teachers/{teacher_id}/restore")
async def restore_teacher(
    teacher_id: str,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.INDEPENDENT_TEACHER]))
):
    """Restore a soft-deleted teacher (Task #645).

    Clears ``is_active=False`` and the ``deleted_at`` / ``deleted_by``
    markers so the row reappears in ``GET /teachers``. Re-activates the
    linked user account if present. Dependent rows
    (teacher_assignments, teacher_class_assignments, teacher_subjects,
    timetable_sessions, class_sessions) are NOT auto-reactivated — the
    response body lists the inactive counts so the UI can prompt the
    principal to re-link them. Only teachers where ``is_active=False``
    AND ``deleted_at IS NOT NULL`` are restorable. IT callers are
    pinned to their own workspace (cross-workspace ids return 404 per
    spec §8 inv. 3).
    """
    from src.core.guards.tenant_guard import is_independent_teacher, independent_workspace_id
    base_filter: Dict[str, Any] = {"id": teacher_id, "is_active": False, "deleted_at": {"$ne": None}}
    if current_user.get("role") != UserRole.PLATFORM_ADMIN.value:
        caller_tenant = (
            independent_workspace_id(current_user) if is_independent_teacher(current_user)
            else current_user.get("tenant_id")
        )
        if not caller_tenant:
            raise HTTPException(status_code=403, detail="غير مصرح")
        base_filter["school_id"] = caller_tenant
    async with db.session.begin_nested():
        stmt = select(Teacher).where(Teacher.id == teacher_id).with_for_update()
        teacher_obj = (await db.session.execute(stmt)).scalars().first()
        teacher = (
            {c.name: getattr(teacher_obj, c.name) for c in teacher_obj.__table__.columns}
            if teacher_obj else None
        )
        if not teacher or any(
            teacher.get(k) != v for k, v in base_filter.items()
            if k not in ("deleted_at",)
        ) or teacher.get("deleted_at") is None:
            raise HTTPException(status_code=404, detail="المعلم غير موجود")

        now_iso = datetime.now(timezone.utc).isoformat()
        user_id = teacher.get("user_id")
        canonical_email = _normalise_teacher_email(teacher.get("email"))
        canonical_phone = _normalise_teacher_phone(teacher.get("phone"))
        canonical_national_id = _normalise_teacher_national_id(teacher.get("national_id"))
        identity_complete = bool(canonical_email and canonical_phone)
        await _lock_teacher_identity(
            teacher["school_id"],
            email=canonical_email,
            phone=canonical_phone,
            national_id=canonical_national_id,
        )
        linked = (await db.session.execute(
            select(User).where(or_(
                User.id == user_id,
                User.teacher_id == teacher_id,
            )).with_for_update()
        )).scalars().all()
        # Profiles created by the wizard carry all identity fields. Re-run the
        # same global ownership proof while holding both identity and row locks;
        # a collision introduced after the create hint must block restoration.
        if identity_complete:
            if user_id is None and not linked:
                # Some pre-account-era teacher profiles legitimately have
                # complete contacts but no login account. Restore only after
                # proving that this profile is the sole global teacher match
                # and that no User claims either contact.
                digits = lambda column: func.regexp_replace(column, r"\D", "", "g")
                phone_values = _phone_search_values(canonical_phone)
                teacher_predicates = [
                    func.lower(func.trim(Teacher.email)) == canonical_email,
                    digits(Teacher.phone).in_(phone_values),
                ]
                if canonical_national_id:
                    teacher_predicates.append(
                        digits(Teacher.national_id) == canonical_national_id
                    )
                matching_teacher_ids = set((await db.session.execute(
                    select(Teacher.id).where(or_(*teacher_predicates))
                )).scalars().all())
                matching_user_id = (await db.session.execute(
                    select(User.id).where(or_(
                        func.lower(func.trim(User.email)) == canonical_email,
                        digits(User.phone).in_(phone_values),
                    )).limit(1)
                )).scalar()
                if matching_teacher_ids != {teacher_id} or matching_user_id:
                    raise _teacher_identity_error(
                        "TEACHER_ACCOUNT_REVIEW_REQUIRED",
                        "توجد مطالبة أخرى ببيانات هذا الملف ويلزم مراجعتها.",
                    )
            else:
                verified_teacher_id = await _restorable_teacher_for_wizard(
                    teacher["school_id"],
                    email=canonical_email,
                    phone=canonical_phone,
                    national_id=canonical_national_id,
                )
                if verified_teacher_id != teacher_id:
                    raise _teacher_identity_error(
                        "TEACHER_ACCOUNT_REVIEW_REQUIRED",
                        "تعذر إثبات ملكية حساب المعلم بشكل منفرد.",
                    )
        else:
            # An incomplete profile cannot safely prove a linked account's
            # contact ownership. Profile-only rows remain explicitly
            # restorable, but any link or matching account requires review.
            if user_id or linked:
                raise _teacher_identity_error(
                    "TEACHER_ACCOUNT_REVIEW_REQUIRED",
                    "بيانات هوية الحساب المرتبط غير مكتملة ويلزم مراجعتها.",
                )
            possible_owner_predicates = []
            if canonical_email:
                possible_owner_predicates.append(
                    func.lower(func.trim(User.email)) == canonical_email
                )
            if canonical_phone:
                possible_owner_predicates.append(
                    func.regexp_replace(User.phone, r"\D", "", "g").in_(
                        _phone_search_values(canonical_phone)
                    )
                )
            if possible_owner_predicates:
                possible_owner = (await db.session.execute(
                    select(User.id).where(or_(*possible_owner_predicates)).limit(1)
                )).scalar()
                if possible_owner:
                    raise _teacher_identity_error(
                        "TEACHER_ACCOUNT_REVIEW_REQUIRED",
                        "يوجد حساب محتمل لهذا الملف ويلزم إثبات الارتباط يدوياً.",
                    )

        account_restored = False
        if user_id or linked:
            if (
                len(linked) != 1
                or user_id not in (None, linked[0].id)
                or linked[0].teacher_id not in (None, teacher_id)
                or linked[0].tenant_id != teacher.get("school_id")
                or linked[0].role != UserRole.TEACHER.value
            ):
                raise _teacher_identity_error(
                    "TEACHER_ACCOUNT_REVIEW_REQUIRED",
                    "تعذر التحقق من ارتباط حساب المعلم. يلزم مراجعة الإدارة.",
                )
            linked_user = {
                c.name: getattr(linked[0], c.name)
                for c in linked[0].__table__.columns
            }
            if await _has_known_administrative_suspension(linked_user, teacher_id):
                raise _teacher_identity_error(
                    "TEACHER_ACCOUNT_REVIEW_REQUIRED",
                    "الحساب موقوف إدارياً ولا يمكن استعادته من شاشة المعلمين.",
                )
            user_updates = {
                "is_active": True,
                "teacher_id": teacher_id,
            }
            if linked[0].phone is None and teacher.get("phone"):
                user_updates["phone"] = teacher["phone"]
            await gd_update_one(db.session, "users", {"id": linked[0].id}, user_updates)
            if user_id is None:
                await gd_update_one(
                    db.session, "teachers", {"id": teacher_id},
                    {"user_id": linked[0].id},
                )
            account_restored = True
        await gd_update_one(db.session, "teachers", {"id": teacher_id}, {
            "is_active": True, "deleted_at": None, "deleted_by": None,
        })

        school_id = teacher.get("school_id")
        await reconcile_school_counts(db.session, school_id)
        inactive_dependents = {
        "teacher_assignments": await gd_count(db.session, "teacher_assignments", {"teacher_id": teacher_id, "is_active": False}),
        "teacher_class_assignments": await gd_count(db.session, "teacher_class_assignments", {"teacher_id": teacher_id, "is_active": False}),
        "teacher_subjects": await gd_count(db.session, "teacher_subjects", {"teacher_id": teacher_id, "is_active": False}),
        "timetable_sessions": await gd_count(db.session, "timetable_sessions", {"teacher_id": teacher_id, "is_active": False}),
        "class_sessions": await gd_count(db.session, "class_sessions", {"teacher_id": teacher_id, "is_active": False}),
        }
        audit_log = {
        "id": str(uuid.uuid4()),
        "school_id": school_id,
        "action": "restore",
        "entity_type": "teacher",
        "entity_id": teacher_id,
        "old_data": {
            "full_name": teacher.get("full_name"),
            "is_active": False,
            "deleted_at": teacher.get("deleted_at"),
            "deleted_by": teacher.get("deleted_by"),
        },
        "new_data": {"is_active": True, "deleted_at": None, "deleted_by": None},
        "performed_by": current_user["id"],
        "performed_by_name": current_user.get("full_name", ""),
        "timestamp": now_iso,
        "ip_address": None,
        }
        await gd_insert(db.session, "audit_logs", audit_log)

    return {
        "message": "تمت استعادة المعلم بنجاح",
        "success": True,
        "restored_existing": True,
        "account_restored": account_restored,
        "profile_only": not account_restored,
        "inactive_dependents": inactive_dependents,
    }


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
    from src.core.guards.tenant_guard import independent_workspace_id as _itw_id
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
