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

# ============== CLASSES ROUTES ==============

# Class Wizard Options

class ClassWizardCreate(BaseModel):
    """Class creation via wizard"""
    name: Optional[str] = None
    name_ar: Optional[str] = None  # Support Arabic name from frontend
    name_en: Optional[str] = None
    grade_id: str
    grade: Optional[int] = None  # Can be derived from grade_id
    section: Optional[str] = "أ"  # Default section
    class_type: Optional[str] = "regular"
    capacity: int = 30
    homeroom_teacher_id: Optional[str] = None
    student_ids: List[str] = []

@router.post("/classes/create")
async def create_class_wizard(
    data: ClassWizardCreate,
    current_user: dict = Depends(get_current_user)
):
    """Create a new class via wizard"""
    school_id = current_user.get("tenant_id")
    
    if not school_id:
        raise HTTPException(status_code=400, detail="المستخدم غير مرتبط بمدرسة")
    
    class_id = str(uuid.uuid4())
    
    # Get grade level info
    grade_level = await db.grade_levels.find_one({"id": data.grade_id}, {"_id": 0})
    
    # Derive grade number from grade_level if not provided
    grade_number = data.grade
    if not grade_number and grade_level:
        grade_number = grade_level.get("grade", 1)
    elif not grade_number:
        # Try to extract from grade_id
        try:
            grade_number = int(data.grade_id)
        except (ValueError, TypeError):
            grade_number = 1
    
    # Use name_ar if name is not provided
    class_name = data.name or data.name_ar
    if not class_name:
        grade_name = grade_level.get("name_ar") if grade_level else f"الصف {grade_number}"
        class_name = f"{grade_name} - {data.section or 'أ'}"
    
    grade_name = grade_level.get("name_ar") if grade_level else f"الصف {grade_number}"
    
    # Create class document
    class_doc = {
        "id": class_id,
        "school_id": school_id,
        "name": class_name,
        "name_ar": class_name,
        "name_en": data.name_en or f"Grade {grade_number} - {data.section or 'A'}",
        "grade_level_id": data.grade_id,
        "grade": grade_number,
        "section": data.section or "أ",
        "class_type": data.class_type,
        "capacity": data.capacity,
        "student_count": len(data.student_ids),
        "homeroom_teacher_id": data.homeroom_teacher_id,
        "is_active": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    
    await db.classes.insert_one(class_doc)
    
    # Assign students to class
    if data.student_ids:
        await db.students.update_many(
            {"id": {"$in": data.student_ids}},
            {"$set": {
                "class_id": class_id,
                "grade": data.grade,
                "section": data.section,
            }}
        )
    
    # Get homeroom teacher name
    teacher_name = None
    if data.homeroom_teacher_id:
        teacher = await db.teachers.find_one({"id": data.homeroom_teacher_id}, {"_id": 0, "full_name": 1})
        if teacher:
            teacher_name = teacher.get("full_name")
    
    return {
        "success": True,
        "class": {
            "id": class_id,
            "name": class_name,
            "grade": grade_number,
            "section": data.section or "أ",
            "capacity": data.capacity,
            "student_count": len(data.student_ids),
            "homeroom_teacher_name": teacher_name,
        },
        "class_id": class_id,
        "message": "تم إنشاء الفصل بنجاح"
    }

@router.post("/classes", response_model=ClassResponse)
async def create_class(
    class_data: ClassCreate,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.SCHOOL_SUB_ADMIN]))
):
    """Create a new class"""
    class_id = str(uuid.uuid4())
    
    class_doc = {
        "id": class_id,
        "name": class_data.name,
        "name_en": getattr(class_data, 'name_en', None),
        "school_id": getattr(class_data, 'school_id', None) or current_user.get("tenant_id"),
        "grade_level": getattr(class_data, 'grade_level', None) or getattr(class_data, 'grade', None),
        "section": class_data.section,
        "capacity": class_data.capacity,
        "current_students": 0,
        "homeroom_teacher_id": getattr(class_data, 'homeroom_teacher_id', None) or getattr(class_data, 'class_teacher_id', None),
        "is_active": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.classes.insert_one(class_doc)
    
    # Get homeroom teacher name
    teacher_name = None
    if class_doc["homeroom_teacher_id"]:
        teacher = await db.teachers.find_one({"id": class_doc["homeroom_teacher_id"]}, {"_id": 0})
        if teacher:
            teacher_name = teacher.get("full_name")
    
    return ClassResponse(**class_doc, homeroom_teacher_name=teacher_name)

@router.get("/classes", response_model=List[ClassResponse])
async def get_classes(
    school_id: Optional[str] = None,
    grade_level: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """Get all classes or filter by school/grade"""
    query = {}
    if school_id:
        query["school_id"] = school_id
    elif current_user.get("role") != UserRole.PLATFORM_ADMIN.value:
        query["school_id"] = current_user.get("tenant_id")
    
    if grade_level:
        query["grade_level"] = grade_level
    
    classes = await db.classes.find(query, {"_id": 0}).to_list(1000)
    
    # Get teacher names
    teacher_ids = list(set([c.get("homeroom_teacher_id") for c in classes if c.get("homeroom_teacher_id")]))
    teachers = await db.teachers.find({"id": {"$in": teacher_ids}}, {"_id": 0}).to_list(100)
    teacher_map = {t.get("id"): t.get("full_name") or t.get("full_name_ar") for t in teachers}
    
    result = []
    for c in classes:
        c["homeroom_teacher_name"] = teacher_map.get(c.get("homeroom_teacher_id"))
        # Normalize field names - map name_ar to name if needed
        if not c.get("name") and c.get("name_ar"):
            c["name"] = c["name_ar"]
        # Map grade_id to grade_level_id if needed
        if not c.get("grade_level_id") and c.get("grade_id"):
            c["grade_level_id"] = c["grade_id"]
        result.append(ClassResponse(**c))
    
    return result

@router.get("/classes/{class_id}", response_model=ClassResponse)
async def get_class(class_id: str, current_user: dict = Depends(get_current_user)):
    """Get class by ID"""
    class_doc = await db.classes.find_one({"id": class_id}, {"_id": 0})
    if not class_doc:
        raise HTTPException(status_code=404, detail="الفصل غير موجود")
    
    teacher_name = None
    if class_doc.get("homeroom_teacher_id"):
        teacher = await db.teachers.find_one({"id": class_doc.get("homeroom_teacher_id")}, {"_id": 0})
        if teacher:
            teacher_name = teacher.get("full_name")
    
    return ClassResponse(**class_doc, homeroom_teacher_name=teacher_name)

@router.put("/classes/{class_id}")
async def update_class(
    class_id: str,
    class_data: ClassUpdate,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.SCHOOL_SUB_ADMIN]))
):
    """Update class"""
    # Build update dict with only provided fields
    update_fields = {"updated_at": datetime.now(timezone.utc).isoformat()}
    
    if class_data.name is not None:
        update_fields["name"] = class_data.name
    if class_data.name_en is not None:
        update_fields["name_en"] = class_data.name_en
    if class_data.grade_level is not None:
        update_fields["grade_level"] = class_data.grade_level
    if class_data.section is not None:
        update_fields["section"] = class_data.section
    if class_data.capacity is not None:
        update_fields["capacity"] = class_data.capacity
    if class_data.homeroom_teacher_id is not None:
        update_fields["homeroom_teacher_id"] = class_data.homeroom_teacher_id
    if class_data.is_active is not None:
        update_fields["is_active"] = class_data.is_active
    
    result = await db.classes.update_one(
        {"id": class_id},
        {"$set": update_fields}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="الفصل غير موجود")

    if "name" in update_fields:
        new_name = update_fields["name"]
        await db.teacher_assignments.update_many(
            {"class_id": class_id},
            {"$set": {"class_name": new_name}}
        )
        await db.schedule_sessions.update_many(
            {"class_id": class_id},
            {"$set": {"class_name": new_name}}
        )

    return {"message": "تم تحديث بيانات الفصل", "success": True}

@router.delete("/classes/{class_id}")
async def delete_class(
    class_id: str,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN]))
):
    """Delete class — full removal from system"""
    class_doc = await db.classes.find_one({"id": class_id}, {"_id": 0})
    if not class_doc:
        raise HTTPException(status_code=404, detail="الفصل غير موجود")
    
    student_count = await db.students.count_documents({"class_id": class_id, "is_active": {"$ne": False}})
    if student_count > 0:
        raise HTTPException(
            status_code=409,
            detail=f"لا يمكن حذف الفصل لوجود {student_count} طالب مرتبط به. يرجى نقل الطلاب أولاً."
        )
    
    school_id = class_doc.get("school_id")
    cleanup = {}
    await db.classes.delete_one({"id": class_id})
    r = await db.teacher_assignments.delete_many({"class_id": class_id})
    cleanup["teacher_assignments"] = r.deleted_count
    r = await db.teacher_class_assignments.delete_many({"class_id": class_id})
    cleanup["teacher_class_assignments"] = r.deleted_count
    r = await db.class_subjects.delete_many({"class_id": class_id})
    cleanup["class_subjects"] = r.deleted_count
    r = await db.timetable_sessions.delete_many({"class_id": class_id})
    cleanup["timetable_sessions"] = r.deleted_count
    r = await db.class_sessions.delete_many({"class_id": class_id})
    cleanup["class_sessions"] = r.deleted_count
    r = await db.attendance.delete_many({"class_id": class_id})
    cleanup["attendance"] = r.deleted_count
    r = await db.session_attendance.delete_many({"class_id": class_id})
    cleanup["session_attendance"] = r.deleted_count
    r = await db.assessments.delete_many({"class_id": class_id})
    cleanup["assessments"] = r.deleted_count
    r = await db.grades.delete_many({"class_id": class_id})
    cleanup["grades"] = r.deleted_count
    r = await db.behaviour_records.delete_many({"class_id": class_id})
    cleanup["behaviour_records"] = r.deleted_count

    return {"message": "تم حذف الفصل وجميع البيانات المرتبطة به بنجاح", "success": True, "cleanup": cleanup}




