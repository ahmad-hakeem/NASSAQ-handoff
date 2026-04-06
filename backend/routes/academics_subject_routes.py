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

from shared_models import (
    TeacherCreate, TeacherUpdate, TeacherResponse, StudentCreate, StudentUpdate, StudentResponse, ClassCreate, ClassUpdate, ClassResponse, SubjectCreate, SubjectResponse
)

router = APIRouter()


async def get_school_id_from_context(current_user: dict, x_school_context: str = None) -> str:
    if x_school_context:
        return x_school_context
    return current_user.get("tenant_id")


class SubjectCreateForSchool(BaseModel):
    name: str
    name_en: Optional[str] = None
    grade_id: Optional[str] = None
    weekly_periods: int = 4

# ============== SUBJECTS CRUD - إدارة المواد الدراسية ==============

class SubjectCreate(BaseModel):
    name_ar: str
    name_en: Optional[str] = None
    code: Optional[str] = None
    category: Optional[str] = None
    weekly_periods: int = 4
    description: Optional[str] = None

class SubjectUpdate(BaseModel):
    name_ar: Optional[str] = None
    name_en: Optional[str] = None
    code: Optional[str] = None
    category: Optional[str] = None
    weekly_periods: Optional[int] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None

@router.post("/school/subjects")
async def create_school_subject(
    subject_data: SubjectCreate,
    current_user: dict = Depends(require_roles([UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN])),
    x_school_context: str = Header(default=None, alias="X-School-Context")
):
    """Create a new subject for the school - إضافة مادة جديدة للمدرسة"""
    school_id = await get_school_id_from_context(current_user, x_school_context)
    
    if not school_id:
        raise HTTPException(status_code=400, detail="School context required")
    
    subject_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    
    subject_doc = {
        "id": subject_id,
        "school_id": school_id,
        "name_ar": subject_data.name_ar,
        "name_en": subject_data.name_en or subject_data.name_ar,
        "code": subject_data.code or f"SUB-{subject_id[:8].upper()}",
        "category": subject_data.category or "general",
        "weekly_periods": subject_data.weekly_periods,
        "description": subject_data.description,
        "is_active": True,
        "created_at": now,
        "updated_at": now,
        "created_by": current_user.get("id")
    }
    
    await db.subjects.insert_one(subject_doc)
    
    # Remove _id from response
    if "_id" in subject_doc:
        del subject_doc["_id"]
    
    return {"id": subject_id, "message": "تم إضافة المادة بنجاح", "subject": subject_doc}

@router.put("/school/subjects/{subject_id}")
async def update_school_subject(
    subject_id: str,
    subject_data: SubjectUpdate,
    current_user: dict = Depends(require_roles([UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN])),
    x_school_context: str = Header(default=None, alias="X-School-Context")
):
    """Update a subject - تعديل مادة"""
    school_id = await get_school_id_from_context(current_user, x_school_context)
    
    if not school_id:
        raise HTTPException(status_code=400, detail="School context required")
    
    # Check if subject exists for this school
    subject = await db.subjects.find_one({"id": subject_id, "school_id": school_id}, {"_id": 0})
    
    if not subject:
        raise HTTPException(status_code=404, detail="المادة غير موجودة")
    
    update_data = {"updated_at": datetime.now(timezone.utc).isoformat()}
    
    if subject_data.name_ar is not None:
        update_data["name_ar"] = subject_data.name_ar
    if subject_data.name_en is not None:
        update_data["name_en"] = subject_data.name_en
    if subject_data.code is not None:
        update_data["code"] = subject_data.code
    if subject_data.category is not None:
        update_data["category"] = subject_data.category
    if subject_data.weekly_periods is not None:
        update_data["weekly_periods"] = subject_data.weekly_periods
    if subject_data.description is not None:
        update_data["description"] = subject_data.description
    if subject_data.is_active is not None:
        update_data["is_active"] = subject_data.is_active
    
    await db.subjects.update_one({"id": subject_id}, {"$set": update_data})
    
    return {"message": "تم تحديث المادة بنجاح"}

@router.delete("/school/subjects/{subject_id}")
async def delete_school_subject(
    subject_id: str,
    force: bool = False,
    current_user: dict = Depends(require_roles([UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN])),
    x_school_context: str = Header(default=None, alias="X-School-Context")
):
    """Delete (soft) a subject - حذف مادة"""
    school_id = await get_school_id_from_context(current_user, x_school_context)
    
    if not school_id:
        raise HTTPException(status_code=400, detail="School context required")
    
    # Check if subject exists for this school
    subject = await db.subjects.find_one({"id": subject_id, "school_id": school_id}, {"_id": 0})
    
    if not subject:
        raise HTTPException(status_code=404, detail="المادة غير موجودة")
    
    # Check for dependencies (teacher assignments)
    assignments_count = await db.teacher_assignments.count_documents({"subject_id": subject_id, "school_id": school_id})
    
    if assignments_count > 0 and not force:
        return {
            "warning": True,
            "message": f"هذه المادة مرتبطة بـ {assignments_count} إسناد للمعلمين. هل تريد الحذف؟",
            "dependencies": {
                "teacher_assignments": assignments_count
            },
            "requires_confirmation": True
        }
    
    # Soft delete
    await db.subjects.update_one(
        {"id": subject_id},
        {"$set": {"is_active": False, "deleted_at": datetime.now(timezone.utc).isoformat(), "deleted_by": current_user["id"]}}
    )
    
    # Audit log
    audit_log = {
        "id": str(uuid.uuid4()),
        "school_id": school_id,
        "action": "delete",
        "entity_type": "subject",
        "entity_id": subject_id,
        "old_data": {"name_ar": subject.get("name_ar"), "is_active": True},
        "new_data": {"is_active": False},
        "performed_by": current_user["id"],
        "performed_by_name": current_user.get("full_name", ""),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "ip_address": None
    }
    await db.audit_logs.insert_one(audit_log)
    
    return {"message": "تم حذف المادة بنجاح"}

@router.get("/school/subjects")
async def get_school_subjects(
    current_user: dict = Depends(get_current_user),
    x_school_context: str = Header(default=None, alias="X-School-Context")
):
    """Get all subjects for the school - جلب جميع المواد للمدرسة"""
    school_id = await get_school_id_from_context(current_user, x_school_context)
    
    if not school_id:
        raise HTTPException(status_code=400, detail="School context required")
    
    subjects = await db.subjects.find(
        {"school_id": school_id, "is_active": True},
        {"_id": 0}
    ).to_list(100)
    
    return subjects

@router.get("/school/subjects/unique")
async def get_unique_school_subjects(
    current_user: dict = Depends(get_current_user),
    x_school_context: str = Header(default=None, alias="X-School-Context")
):
    """Get unique subjects from all sources for teacher assignment - جلب المواد الفريدة للإسناد"""
    school_id = await get_school_id_from_context(current_user, x_school_context)
    
    if not school_id:
        raise HTTPException(status_code=400, detail="School context required")
    
    subjects_dict = {}
    
    # 1. Get subjects from school's subjects collection
    school_subjects = await db.subjects.find(
        {"school_id": school_id, "is_active": {"$ne": False}},
        {"_id": 0}
    ).to_list(500)
    
    for s in school_subjects:
        name = s.get("name") or s.get("name_ar") or "مادة بدون اسم"
        if name not in subjects_dict:
            subjects_dict[name] = {
                "id": s.get("id"),
                "name_ar": s.get("name_ar") or s.get("name"),
                "name_en": s.get("name_en"),
                "code": s.get("code"),
                "source": "school"
            }
    
    # 2. Get subjects from reference_subjects (if not enough)
    if len(subjects_dict) < 10:
        ref_subjects = await db.reference_subjects.find(
            {},
            {"_id": 0}
        ).to_list(500)
        
        for s in ref_subjects:
            name = s.get("name") or s.get("name_ar") or "مادة بدون اسم"
            if name not in subjects_dict:
                subjects_dict[name] = {
                    "id": s.get("id"),
                    "name_ar": s.get("name_ar") or s.get("name"),
                    "name_en": s.get("name_en"),
                    "code": s.get("code"),
                    "source": "reference"
                }
    
    # 3. If still not enough, get from official curriculum
    if len(subjects_dict) < 10:
        official_subjects = await db.official_curriculum_subjects.find(
            {},
            {"_id": 0}
        ).to_list(500)
        
        for s in official_subjects:
            name = s.get("name_ar") or s.get("name") or "مادة بدون اسم"
            if name not in subjects_dict:
                subjects_dict[name] = {
                    "id": s.get("id"),
                    "name_ar": s.get("name_ar") or s.get("name"),
                    "name_en": s.get("name_en"),
                    "code": s.get("code"),
                    "source": "official"
                }
    
    # Convert to list sorted by name
    result = sorted(subjects_dict.values(), key=lambda x: x.get("name_ar") or "")
    
    return result





# ============== SUBJECTS ROUTES ==============
@router.post("/subjects", response_model=SubjectResponse)
async def create_subject(
    subject_data: SubjectCreate,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.SCHOOL_SUB_ADMIN]))
):
    """Create a new subject"""
    subject_id = str(uuid.uuid4())
    
    subject_doc = {
        "id": subject_id,
        "name": getattr(subject_data, 'name', None) or getattr(subject_data, 'name_ar', None),
        "name_en": getattr(subject_data, 'name_en', None),
        "school_id": getattr(subject_data, 'school_id', None) or current_user.get("tenant_id"),
        "code": getattr(subject_data, 'code', None),
        "description": getattr(subject_data, 'description', None),
        "weekly_hours": getattr(subject_data, 'weekly_hours', None) or getattr(subject_data, 'weekly_periods', 4),
        "grade_levels": getattr(subject_data, 'grade_levels', None),
        "is_active": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.subjects.insert_one(subject_doc)
    return SubjectResponse(**subject_doc)

@router.get("/subjects", response_model=List[SubjectResponse])
async def get_subjects(
    school_id: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """Get all subjects or filter by school"""
    query = {}
    if school_id:
        query["school_id"] = school_id
    elif current_user.get("role") != UserRole.PLATFORM_ADMIN.value:
        query["school_id"] = current_user.get("tenant_id")
    
    subjects = await db.subjects.find(query, {"_id": 0}).to_list(1000)
    result = []
    for s in subjects:
        if "name" not in s and "name_ar" in s:
            s["name"] = s["name_ar"]
        if "weekly_periods" not in s and "weekly_hours" in s:
            s["weekly_periods"] = s["weekly_hours"]
        try:
            result.append(SubjectResponse(**s))
        except Exception as e:
            logger.warning(f"Failed to serialize subject {s.get('id', 'unknown')}: {e}")
    return result

@router.get("/subjects/{subject_id}", response_model=SubjectResponse)
async def get_subject(subject_id: str, current_user: dict = Depends(get_current_user)):
    """Get subject by ID"""
    subject = await db.subjects.find_one({"id": subject_id}, {"_id": 0})
    if not subject:
        raise HTTPException(status_code=404, detail="المادة غير موجودة")
    return SubjectResponse(**subject)

@router.put("/subjects/{subject_id}")
async def update_subject(
    subject_id: str,
    subject_data: SubjectCreate,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.SCHOOL_SUB_ADMIN]))
):
    """Update subject"""
    old_subject = await db.subjects.find_one({"id": subject_id}, {"_id": 0, "name": 1})
    result = await db.subjects.update_one(
        {"id": subject_id},
        {"$set": {
            "name": subject_data.name,
            "name_en": subject_data.name_en,
            "code": subject_data.code,
            "description": subject_data.description,
            "weekly_hours": subject_data.weekly_hours,
            "grade_levels": subject_data.grade_levels,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }}
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="المادة غير موجودة")

    if old_subject and subject_data.name != old_subject.get("name"):
        await db.teacher_assignments.update_many(
            {"subject_id": subject_id},
            {"$set": {"subject_name": subject_data.name}}
        )
        await db.schedule_sessions.update_many(
            {"subject_id": subject_id},
            {"$set": {"subject_name": subject_data.name}}
        )

    return {"message": "تم تحديث بيانات المادة"}

@router.delete("/subjects/{subject_id}")
async def delete_subject(
    subject_id: str,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN]))
):
    """Delete subject (soft delete)"""
    subject = await db.subjects.find_one({"id": subject_id}, {"_id": 0})
    if not subject:
        raise HTTPException(status_code=404, detail="المادة غير موجودة")
    
    await db.subjects.update_one({"id": subject_id}, {"$set": {"is_active": False}})
    return {"message": "تم حذف المادة"}




# ============== SUBJECTS (for scheduling) ==============

@router.get("/school/settings/subjects")
async def get_school_subjects(
    current_user: dict = Depends(get_current_user),
    x_school_context: str = Header(default=None, alias="X-School-Context")
):
    """Get school subjects - جلب المواد الدراسية"""
    school_id = await get_school_id_from_context(current_user, x_school_context)
    
    if not school_id:
        raise HTTPException(status_code=400, detail="School context required")
    
    subjects = await db.subjects.find({"tenant_id": school_id}, {"_id": 0}).to_list(100)
    return {"subjects": subjects}


@router.post("/school/settings/subjects")
async def create_school_subject(
    data: SubjectCreateForSchool,
    current_user: dict = Depends(require_roles([UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN])),
    x_school_context: str = Header(default=None, alias="X-School-Context")
):
    """Create subject - إنشاء مادة دراسية"""
    school_id = await get_school_id_from_context(current_user, x_school_context)
    
    if not school_id:
        raise HTTPException(status_code=400, detail="School context required")
    
    subject = {
        "id": str(uuid.uuid4()),
        "tenant_id": school_id,
        "name": data.name,
        "name_en": data.name_en,
        "grade_id": data.grade_id,
        "weekly_periods": data.weekly_periods,
        "is_active": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by": current_user["id"]
    }
    
    await db.subjects.insert_one(subject)
    subject.pop("_id", None)
    
    return {"message": "تم إضافة المادة الدراسية", "subject": subject}


@router.delete("/school/settings/subjects/{subject_id}")
async def delete_school_subject(
    subject_id: str,
    current_user: dict = Depends(require_roles([UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN])),
    x_school_context: str = Header(default=None, alias="X-School-Context")
):
    """Delete subject - حذف مادة دراسية"""
    school_id = await get_school_id_from_context(current_user, x_school_context)
    
    if not school_id:
        raise HTTPException(status_code=400, detail="School context required")
    
    await db.subjects.delete_one({"id": subject_id, "tenant_id": school_id})
    
    return {"message": "تم حذف المادة الدراسية"}





