"""
NASSAQ Route Module: Teachers, students, classes, subjects CRUD, academic years/terms/grades/structure
Auto-consolidated during Phase 8 modularization.
"""
from fastapi import APIRouter, HTTPException, Depends, status, Header, Query, Body, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import Response
from starlette.responses import StreamingResponse
from pydantic import BaseModel, Field, ConfigDict, EmailStr, model_validator
from typing import List, Optional, Any, Dict
from datetime import datetime, timezone, timedelta
from bson import ObjectId
import uuid, os, logging, json, random, re, io, base64

async def get_school_id_from_context(current_user: dict, x_school_context: str = None) -> str:
    if x_school_context:
        return x_school_context
    return current_user.get("tenant_id")

from dependencies import (
    db, get_current_user, require_roles, UserRole, SchoolStatus,
    hash_password, verify_password, create_access_token,
    JWT_SECRET, JWT_ALGORITHM, ACCESS_TOKEN_EXPIRE, security, logger,
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

class SubjectCreateForSchool(BaseModel):
    name: str
    name_en: Optional[str] = None
    grade_id: Optional[str] = None
    weekly_periods: int = 4




# ============== TEACHERS ROUTES ==============

# Teacher Wizard Options
@router.get("/teachers/options/subjects")
async def get_teacher_subjects_options(current_user: dict = Depends(get_current_user)):
    """Get available subjects from reference database - unique subjects only"""
    
    # Get subjects from reference_subjects collection first, then fallback to subjects
    subjects = await db.reference_subjects.find(
        {"is_active": True},
        {"_id": 0, "id": 1, "name_ar": 1, "name_en": 1, "code": 1, "color": 1}
    ).to_list(300)
    
    if not subjects:
        subjects = await db.subjects.find(
            {"is_active": True},
            {"_id": 0, "id": 1, "name_ar": 1, "name_en": 1, "code": 1, "color": 1}
        ).to_list(300)
    
    # Remove duplicates by name_ar (keep first occurrence)
    seen_names = set()
    unique_subjects = []
    for s in subjects:
        name = s.get("name_ar", s.get("name", ""))
        if name and name not in seen_names:
            seen_names.add(name)
            unique_subjects.append({
                "id": s.get("id"),
                "name": name,
                "name_ar": name,
                "name_en": s.get("name_en", ""),
                "code": s.get("code", ""),
                "color": s.get("color", "#3B82F6")
            })
    
    return {"subjects": unique_subjects}

# Reference Data APIs
@router.get("/reference/academic-structure")
async def get_academic_structure(current_user: dict = Depends(get_current_user)):
    """Get complete academic structure (stages, grades, tracks)"""
    # Try reference_* collections first (new naming), fall back to old names
    stages = await db.reference_stages.find({}, {"_id": 0}).sort("order", 1).to_list(10)
    if not stages:
        stages = await db.academic_stages.find({"is_active": True}, {"_id": 0}).sort("order", 1).to_list(10)
    
    grades = await db.reference_grades.find({}, {"_id": 0}).sort("order", 1).to_list(50)
    if not grades:
        grades = await db.academic_grades.find({"is_active": True}, {"_id": 0}).sort("order", 1).to_list(50)
    
    tracks = await db.reference_tracks.find({}, {"_id": 0}).to_list(10)
    if not tracks:
        tracks = await db.education_tracks.find({"is_active": True}, {"_id": 0}).to_list(10)
    
    subject_mappings = await db.subject_mappings.find({}, {"_id": 0}).to_list(50)
    
    return {
        "stages": stages,
        "grades": grades,
        "tracks": tracks,
        "subject_mappings": subject_mappings
    }

@router.get("/reference/stages")
async def get_reference_stages(current_user: dict = Depends(get_current_user)):
    """Get all academic stages"""
    stages = await db.reference_stages.find({}, {"_id": 0}).sort("order", 1).to_list(10)
    if not stages:
        stages = await db.academic_stages.find({"is_active": True}, {"_id": 0}).sort("order", 1).to_list(10)
    return stages

@router.get("/reference/grades")
async def get_reference_grades(current_user: dict = Depends(get_current_user)):
    """Get all grades"""
    grades = await db.reference_grades.find({}, {"_id": 0}).sort("order", 1).to_list(50)
    if not grades:
        grades = await db.academic_grades.find({"is_active": True}, {"_id": 0}).sort("order", 1).to_list(50)
    return grades

@router.get("/reference/tracks")
async def get_reference_tracks(current_user: dict = Depends(get_current_user)):
    """Get all education tracks"""
    tracks = await db.reference_tracks.find({}, {"_id": 0}).to_list(10)
    if not tracks:
        tracks = await db.education_tracks.find({"is_active": True}, {"_id": 0}).to_list(10)
    return tracks

@router.get("/reference/subjects")
async def get_reference_subjects(current_user: dict = Depends(get_current_user)):
    """Get all reference subjects"""
    subjects = await db.reference_subjects.find({"is_active": True}, {"_id": 0}).to_list(500)
    if not subjects:
        subjects = await db.subjects.find({"is_active": True}, {"_id": 0}).to_list(100)
    return subjects

@router.get("/reference/teacher-ranks")
async def get_reference_teacher_ranks(current_user: dict = Depends(get_current_user)):
    """Get all teacher ranks with teaching loads"""
    ranks = await db.reference_teacher_ranks.find({}, {"_id": 0}).sort("order", 1).to_list(20)
    if not ranks:
        ranks = await db.teacher_ranks.find({"is_active": True}, {"_id": 0}).sort("order", 1).to_list(20)
    return ranks

@router.get("/reference/admin-constraints")
async def get_reference_admin_constraints(current_user: dict = Depends(get_current_user)):
    """Get all administrative scheduling constraints"""
    constraints = await db.reference_admin_constraints.find({"is_active": True}, {"_id": 0}).to_list(50)
    if not constraints:
        constraints = await db.admin_constraints.find({"is_active": True}, {"_id": 0}).to_list(50)
    return constraints

@router.get("/reference/default-settings")
async def get_reference_default_settings(current_user: dict = Depends(get_current_user)):
    """Get default school settings template"""
    settings = await db.default_school_settings.find_one({}, {"_id": 0})
    if not settings:
        settings = await db.default_settings.find_one({"id": "default-school-settings"}, {"_id": 0})
    return settings or {}





# ============== STUDENTS ROUTES ==============
@router.post("/students", response_model=StudentResponse)
async def create_student(
    student_data: StudentCreate,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.SCHOOL_SUB_ADMIN]))
):
    """Create a new student"""
    student_id = str(uuid.uuid4())
    
    student_doc = {
        "id": student_id,
        "user_id": None,  # Students may not have user accounts initially
        "full_name": student_data.full_name,
        "full_name_en": student_data.full_name_en,
        "email": student_data.email,
        "phone": student_data.phone,
        "school_id": student_data.school_id,
        "class_id": student_data.class_id,
        "student_number": student_data.student_number,
        "date_of_birth": student_data.date_of_birth,
        "gender": student_data.gender,
        "parent_phone": student_data.parent_phone,
        "parent_name": student_data.parent_name,
        "talents": getattr(student_data, 'talents', []) or [],
        "character_traits": getattr(student_data, 'character_traits', []) or [],
        "is_gifted": len(getattr(student_data, 'talents', []) or []) > 0 or bool(getattr(student_data, 'is_gifted', False)),
        "is_active": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.students.insert_one(student_doc)
    
    # Update school student count
    await db.schools.update_one(
        {"id": student_data.school_id},
        {"$inc": {"current_students": 1}}
    )
    
    # Update class student count if assigned
    if student_data.class_id:
        await db.classes.update_one(
            {"id": student_data.class_id},
            {"$inc": {"current_students": 1}}
        )
    
    # Get class name for response
    class_name = None
    if student_data.class_id:
        class_doc = await db.classes.find_one({"id": student_data.class_id}, {"_id": 0})
        if class_doc:
            class_name = class_doc.get("name")
    
    return StudentResponse(**student_doc, class_name=class_name)

@router.get("/students", response_model=List[StudentResponse])
async def get_students(
    school_id: Optional[str] = None,
    class_id: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """Get all students or filter by school/class"""
    query = {"is_active": {"$ne": False}}
    if school_id:
        query["school_id"] = school_id
    elif current_user.get("role") != UserRole.PLATFORM_ADMIN.value:
        query["school_id"] = current_user.get("tenant_id")
    
    if class_id:
        query["class_id"] = class_id
    
    students = await db.students.find(query, {"_id": 0}).to_list(1000)
    
    # Get class names
    class_ids = list(set([s.get("class_id") for s in students if s.get("class_id")]))
    classes = await db.classes.find({"id": {"$in": class_ids}}, {"_id": 0}).to_list(100)
    class_map = {c.get("id"): c.get("name") or c.get("name_ar") for c in classes}
    
    result = []
    for s in students:
        s["class_name"] = class_map.get(s.get("class_id"))
        # Normalize field names - map full_name_ar to full_name if needed
        if not s.get("full_name") and s.get("full_name_ar"):
            s["full_name"] = s["full_name_ar"]
        result.append(StudentResponse(**s))
    
    return result

@router.get("/classes/options/grades")
async def get_class_grades_options(current_user: dict = Depends(get_current_user)):
    """Get available grade levels for class creation"""
    school_id = current_user.get("tenant_id")
    
    grades = await db.grade_levels.find(
        {"school_id": school_id} if school_id else {},
        {"_id": 0}
    ).to_list(100)
    
    result_grades = []
    for g in grades:
        result_grades.append({
            "id": g.get("id", g.get("_id", "")),
            "name_ar": g.get("name_ar") or g.get("name", ""),
            "name_en": g.get("name_en", ""),
            "grade": g.get("grade"),
            "stage": g.get("stage"),
            "stage_id": g.get("stage_id")
        })
    
    if not result_grades:
        grade_levels = await db.students.distinct("grade_level", {"school_id": school_id, "is_active": {"$ne": False}})
        grade_levels = sorted([g for g in grade_levels if g], key=lambda x: int(x) if x.isdigit() else 999)
        grade_names = {
            "1": ("الصف الأول", "Grade 1"), "2": ("الصف الثاني", "Grade 2"),
            "3": ("الصف الثالث", "Grade 3"), "4": ("الصف الرابع", "Grade 4"),
            "5": ("الصف الخامس", "Grade 5"), "6": ("الصف السادس", "Grade 6"),
            "7": ("الصف السابع", "Grade 7"), "8": ("الصف الثامن", "Grade 8"),
            "9": ("الصف التاسع", "Grade 9"), "10": ("الصف العاشر", "Grade 10"),
            "11": ("الصف الحادي عشر", "Grade 11"), "12": ("الصف الثاني عشر", "Grade 12"),
        }
        for gl in grade_levels:
            names = grade_names.get(gl, (f"الصف {gl}", f"Grade {gl}"))
            result_grades.append({"id": gl, "name_ar": names[0], "name_en": names[1], "grade": int(gl) if gl.isdigit() else None, "stage": "ابتدائي" if gl.isdigit() and int(gl) <= 6 else "متوسط/ثانوي"})
    
    return {"grades": result_grades}

@router.get("/classes/options/teachers")
async def get_class_teachers_options(current_user: dict = Depends(get_current_user)):
    """Get available teachers for homeroom assignment"""
    school_id = current_user.get("tenant_id")
    
    teachers = await db.teachers.find(
        {"school_id": school_id, "is_active": {"$ne": False}} if school_id else {"is_active": {"$ne": False}},
        {"_id": 0}
    ).to_list(200)
    
    result_teachers = []
    for t in teachers:
        result_teachers.append({
            "teacher_id": t.get("teacher_id") or t.get("id", ""),
            "full_name_ar": t.get("full_name_ar") or t.get("name_ar") or t.get("full_name") or t.get("name", ""),
            "full_name_en": t.get("full_name_en", ""),
            "specialization": t.get("specialization", ""),
            "email": t.get("email", "")
        })
    
    return {"teachers": result_teachers}

@router.get("/classes/options/students")
async def get_class_students_options(current_user: dict = Depends(get_current_user)):
    """Get available students for class assignment"""
    school_id = current_user.get("tenant_id") or current_user.get("school_id")
    
    query = {"school_id": school_id, "is_active": {"$ne": False}} if school_id else {"is_active": {"$ne": False}}
    students = await db.students.find(query, {"_id": 0}).to_list(500)
    
    result_students = []
    for s in students:
        result_students.append({
            "student_id": s.get("student_id") or s.get("id", ""),
            "full_name_ar": s.get("full_name_ar") or s.get("full_name", ""),
            "full_name_en": s.get("full_name_en", ""),
            "student_number": s.get("student_number", ""),
            "grade_id": s.get("grade_id") or (f"grade_{s.get('grade_level')}" if s.get("grade_level") else ""),
            "grade_level": s.get("grade_level", ""),
            "class_id": s.get("class_id")
        })
    
    return {"students": result_students}

@router.get("/classes/options/class-types")
async def get_class_types_options(current_user: dict = Depends(get_current_user)):
    """Get available class types"""
    types = [
        {"code": "regular", "name_ar": "عادي", "name_en": "Regular"},
        {"code": "advanced", "name_ar": "متقدم", "name_en": "Advanced"},
        {"code": "special", "name_ar": "تربية خاصة", "name_en": "Special Education"},
        {"code": "gifted", "name_ar": "موهوبين", "name_en": "Gifted"},
    ]
    return {"types": types}

@router.get("/classes/{class_id}/students", response_model=List[StudentResponse])
async def get_class_students(
    class_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get all students in a specific class"""
    query = {"class_id": class_id, "is_active": True}
    if current_user.get("role") != UserRole.PLATFORM_ADMIN.value:
        tenant = current_user.get("tenant_id")
        if tenant:
            query["school_id"] = tenant

    students = await db.students.find(query, {"_id": 0}).to_list(1000)

    cls = await db.classes.find_one({"id": class_id}, {"_id": 0, "name": 1})
    class_name = cls.get("name") if cls else None

    students_missing_parent = [s["id"] for s in students if not s.get("parent_id") and s.get("parent_phone")]
    parent_lookup = {}
    if students_missing_parent:
        parent_links = await db.parent_student_links.find(
            {"student_id": {"$in": students_missing_parent}}, {"_id": 0, "student_id": 1, "parent_id": 1}
        ).to_list(500)
        for link in parent_links:
            parent_lookup[link["student_id"]] = link.get("parent_id")
        if not parent_lookup:
            parent_users = await db.users.find(
                {"role": "parent", "student_ids": {"$in": students_missing_parent}}, {"_id": 0, "id": 1, "student_ids": 1}
            ).to_list(500)
            for pu in parent_users:
                for sid in (pu.get("student_ids") or []):
                    if sid in students_missing_parent:
                        parent_lookup[sid] = pu["id"]

    result = []
    for s in students:
        s["class_name"] = class_name
        if not s.get("full_name") and s.get("full_name_ar"):
            s["full_name"] = s["full_name_ar"]
        if hasattr(s.get("created_at"), "isoformat"):
            s["created_at"] = s["created_at"].isoformat()
        if not s.get("parent_id") and s["id"] in parent_lookup:
            s["parent_id"] = parent_lookup[s["id"]]
        result.append(StudentResponse(**s))

    return result


@router.get("/students/{student_id}", response_model=StudentResponse)
async def get_student(student_id: str, current_user: dict = Depends(get_current_user)):
    """Get student by ID"""
    student = await db.students.find_one({"id": student_id}, {"_id": 0})
    if not student:
        raise HTTPException(status_code=404, detail="الطالب غير موجود")
    
    class_name = None
    if student.get("class_id"):
        class_doc = await db.classes.find_one({"id": student.get("class_id")}, {"_id": 0})
        if class_doc:
            class_name = class_doc.get("name") or class_doc.get("name_ar")
    
    # Normalize field names
    if not student.get("full_name") and student.get("full_name_ar"):
        student["full_name"] = student["full_name_ar"]
    
    student["class_name"] = class_name
    return StudentResponse(**student)

@router.put("/students/{student_id}")
async def update_student(
    student_id: str,
    student_data: StudentUpdate,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.SCHOOL_SUB_ADMIN]))
):
    """Update student"""
    school_id = current_user.get("tenant_id")
    query = {"id": student_id}
    if school_id:
        query["school_id"] = school_id

    existing = await db.students.find_one(query, {"_id": 0, "id": 1})
    if not existing:
        raise HTTPException(status_code=404, detail="الطالب غير موجود")

    update_fields = {"updated_at": datetime.now(timezone.utc).isoformat()}
    
    if student_data.full_name is not None:
        update_fields["full_name"] = student_data.full_name
    if student_data.full_name_en is not None:
        update_fields["full_name_en"] = student_data.full_name_en
    if student_data.email is not None:
        update_fields["email"] = student_data.email
    if student_data.phone is not None:
        update_fields["phone"] = student_data.phone
    if student_data.grade is not None:
        update_fields["grade"] = student_data.grade
    if student_data.class_id is not None:
        update_fields["class_id"] = student_data.class_id
    if student_data.date_of_birth is not None:
        update_fields["date_of_birth"] = student_data.date_of_birth
    if student_data.gender is not None:
        update_fields["gender"] = student_data.gender
    if student_data.parent_phone is not None:
        update_fields["parent_phone"] = student_data.parent_phone
    if student_data.parent_name is not None:
        update_fields["parent_name"] = student_data.parent_name
    if student_data.talents is not None:
        update_fields["talents"] = student_data.talents
        update_fields["is_gifted"] = len(student_data.talents) > 0
    elif student_data.is_gifted is not None:
        update_fields["is_gifted"] = student_data.is_gifted
    if student_data.character_traits is not None:
        update_fields["character_traits"] = student_data.character_traits
    if student_data.is_active is not None:
        update_fields["is_active"] = student_data.is_active
    
    result = await db.students.update_one(query, {"$set": update_fields})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="الطالب غير موجود")
    return {"message": "تم تحديث بيانات الطالب وحفظها في قاعدة البيانات بنجاح", "success": True}

@router.post("/students/transfer-class")
async def transfer_student_class(
    request: Request,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN]))
):
    body = await request.json()
    student_id = body.get("student_id")
    target_class_id = body.get("target_class_id")
    if not student_id or not target_class_id:
        raise HTTPException(status_code=400, detail="student_id و target_class_id مطلوبان")

    school_id = current_user.get("tenant_id") or current_user.get("school_id")
    if not school_id:
        raise HTTPException(status_code=400, detail="سياق المدرسة مطلوب")

    student = await db.students.find_one({"id": student_id, "school_id": school_id}, {"_id": 0})
    if not student:
        raise HTTPException(status_code=404, detail="الطالب غير موجود")

    target_class = await db.classes.find_one({"id": target_class_id, "school_id": school_id}, {"_id": 0})
    if not target_class:
        raise HTTPException(status_code=404, detail="الفصل المستهدف غير موجود")

    old_class_id = student.get("class_id")
    if old_class_id == target_class_id:
        return {"success": True, "message": "الطالب موجود بالفعل في هذا الفصل"}

    now = datetime.now(timezone.utc).isoformat()
    await db.students.update_one(
        {"id": student_id, "school_id": school_id},
        {"$set": {
            "class_id": target_class_id,
            "class_name": target_class.get("name_ar") or target_class.get("name", ""),
            "updated_at": now
        }}
    )

    if old_class_id:
        await db.classes.update_one(
            {"id": old_class_id, "school_id": school_id},
            {"$pull": {"student_ids": student_id}}
        )
        old_count = await db.students.count_documents({"class_id": old_class_id, "school_id": school_id})
        await db.classes.update_one(
            {"id": old_class_id, "school_id": school_id},
            {"$set": {"student_count": old_count}}
        )

    await db.classes.update_one(
        {"id": target_class_id, "school_id": school_id},
        {"$addToSet": {"student_ids": student_id}}
    )
    new_count = await db.students.count_documents({"class_id": target_class_id, "school_id": school_id})
    await db.classes.update_one(
        {"id": target_class_id, "school_id": school_id},
        {"$set": {"student_count": new_count}}
    )

    student_name = student.get("full_name", "")
    target_name = target_class.get("name_ar") or target_class.get("name", "")
    return {
        "success": True,
        "message": f"تم نقل الطالب {student_name} إلى الفصل {target_name} بنجاح"
    }

@router.delete("/students/{student_id}")
async def delete_student(
    student_id: str,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN]))
):
    """Delete student — full removal from system"""
    student = await db.students.find_one({"id": student_id}, {"_id": 0})
    if not student:
        raise HTTPException(status_code=404, detail="الطالب غير موجود")
    
    school_id = student.get("school_id")
    class_id = student.get("class_id")
    user_id = student.get("user_id")

    cleanup = {}
    await db.students.delete_one({"id": student_id})

    await db.schools.update_one(
        {"id": school_id},
        {"$inc": {"current_students": -1}}
    )
    if class_id:
        await db.classes.update_one(
            {"id": class_id},
            {"$inc": {"current_students": -1}}
        )

    r = await db.attendance.delete_many({"student_id": student_id})
    cleanup["attendance"] = r.deleted_count
    r = await db.session_attendance.delete_many({"student_id": student_id})
    cleanup["session_attendance"] = r.deleted_count
    r = await db.grades.delete_many({"student_id": student_id})
    cleanup["grades"] = r.deleted_count
    r = await db.student_daily_scores.delete_many({"student_id": student_id})
    cleanup["student_daily_scores"] = r.deleted_count
    r = await db.student_score_ledger.delete_many({"student_id": student_id})
    cleanup["student_score_ledger"] = r.deleted_count
    r = await db.student_skills.delete_many({"student_id": student_id})
    cleanup["student_skills"] = r.deleted_count
    r = await db.behaviour_records.delete_many({"student_id": student_id})
    cleanup["behaviour_records"] = r.deleted_count
    r = await db.session_interactions.delete_many({"student_id": student_id})
    cleanup["session_interactions"] = r.deleted_count
    r = await db.guardian_links.delete_many({"student_id": student_id})
    cleanup["guardian_links"] = r.deleted_count
    r = await db.user_relationships.delete_many({"$or": [{"source_id": student_id}, {"target_id": student_id}]})
    cleanup["user_relationships"] = r.deleted_count

    if user_id:
        await db.users.delete_one({"id": user_id})
        await db.user_roles.delete_many({"user_id": user_id})
        await db.user_identities.delete_many({"user_id": user_id})
        cleanup["user_account"] = 1

    return {"message": "تم حذف الطالب وجميع بياناته من النظام بالكامل", "success": True, "cleanup": cleanup}




# ============== STUDENT WIZARD ROUTES ==============
class StudentWizardCreate(BaseModel):
    """Student wizard creation model"""
    full_name: str
    email: Optional[str] = None
    national_id: Optional[str] = None
    gender: str = "male"
    date_of_birth: Optional[str] = None
    education_level: Optional[str] = None
    grade_id: Optional[str] = None
    class_id: Optional[str] = None
    parent: Optional[dict] = None
    health: Optional[dict] = None
    link_to_parent_id: Optional[str] = None

@router.post("/student-wizard/check-parent")
async def check_parent_exists(
    phone: Optional[str] = None,
    email: Optional[str] = None,
    national_id: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """Check if parent already exists and return their students (siblings)"""
    school_id = current_user.get("tenant_id")
    
    query = {"school_id": school_id}
    conditions = []
    
    if phone:
        conditions.append({"phone": phone})
    if email:
        conditions.append({"email": email})
    if national_id:
        conditions.append({"national_id": national_id})
    
    if not conditions:
        return {"found": False}
    
    query["$or"] = conditions
    
    parent = await db.parents.find_one(query, {"_id": 0})
    
    if parent:
        # Get parent's students (siblings)
        students = await db.students.find(
            {"school_id": school_id, "id": {"$in": parent.get("student_ids", [])}},
            {"_id": 0, "id": 1, "full_name": 1, "student_number": 1, "grade": 1, "section": 1}
        ).to_list(100)
        
        return {
            "found": True,
            "parent": parent,
            "students": students
        }
    
    return {"found": False}


@router.get("/parents")
async def get_parents(
    current_user: dict = Depends(get_current_user)
):
    school_id = current_user.get("tenant_id")
    query = {"status": {"$ne": "closed"}}
    if school_id:
        query["school_id"] = school_id
    parents = await db.parents.find(query, {"_id": 0}).to_list(1000)
    result = []
    for p in parents:
        student_ids = p.get("student_ids", [])
        children = []
        if student_ids:
            child_query = {"id": {"$in": student_ids}}
            if school_id:
                child_query["school_id"] = school_id
            students_docs = await db.students.find(
                child_query,
                {"_id": 0, "id": 1, "full_name": 1, "full_name_ar": 1, "class_name": 1}
            ).to_list(50)
            children = [{"id": s.get("id"), "name": s.get("full_name") or s.get("full_name_ar")} for s in students_docs]
        p["children"] = children
        p["children_count"] = len(children)
        if not p.get("full_name") and p.get("full_name_ar"):
            p["full_name"] = p["full_name_ar"]
        if not p.get("relationship"):
            p["relationship"] = p.get("relation")
        result.append(p)
    return result


@router.get("/student-wizard/search-parents")
async def search_parents(
    q: str = "",
    current_user: dict = Depends(get_current_user)
):
    """Search for existing parents by name or phone"""
    school_id = current_user.get("tenant_id")
    
    if not q or len(q) < 2:
        return {"parents": []}
    
    # Search by name or phone
    query = {
        "school_id": school_id,
        "$or": [
            {"full_name": {"$regex": q, "$options": "i"}},
            {"phone": {"$regex": q, "$options": "i"}},
        ]
    }
    
    parents = await db.parents.find(
        query,
        {"_id": 0, "id": 1, "full_name": 1, "phone": 1, "email": 1, "national_id": 1, "relationship": 1, "address": 1, "student_ids": 1}
    ).limit(10).to_list(10)
    
    # Add children count and names
    result = []
    for parent in parents:
        student_ids = parent.get("student_ids", [])
        children_count = len(student_ids)
        children = []
        
        if student_ids:
            students = await db.students.find(
                {"id": {"$in": student_ids}},
                {"_id": 0, "full_name": 1}
            ).to_list(10)
            children = [{"name": s.get("full_name")} for s in students]
        
        result.append({
            "id": parent.get("id"),
            "full_name": parent.get("full_name"),
            "phone": parent.get("phone"),
            "email": parent.get("email"),
            "national_id": parent.get("national_id"),
            "relationship": parent.get("relationship", "father"),
            "address": parent.get("address"),
            "children_count": children_count,
            "children": children
        })
    
    return {"parents": result}

@router.post("/student-wizard/create")
async def create_student_with_wizard(
    data: StudentWizardCreate,
    current_user: dict = Depends(get_current_user)
):
    """Create student with parent and health info via wizard"""
    school_id = current_user.get("tenant_id")
    
    if not school_id:
        raise HTTPException(status_code=400, detail="المستخدم غير مرتبط بمدرسة")
    
    # Get school info
    school = await db.schools.find_one({"id": school_id}, {"_id": 0, "code": 1, "name": 1})
    if not school:
        raise HTTPException(status_code=404, detail="المدرسة غير موجودة")
    
    # Generate student number: NSS-CODE-GRADE-XXXX
    school_code = school.get("code", "NSS")
    grade_num = data.grade_id[-1] if data.grade_id else "0"
    
    # Count existing students to generate sequential number
    student_count = await db.students.count_documents({"school_id": school_id})
    student_number = f"NSS-{school_code}-{grade_num}-{str(student_count + 1).zfill(4)}"
    
    student_id = str(uuid.uuid4())
    
    # Get class info
    class_doc = None
    if data.class_id:
        class_doc = await db.classes.find_one({"id": data.class_id}, {"_id": 0})
    
    # Create student
    student_doc = {
        "id": student_id,
        "school_id": school_id,
        "student_number": student_number,
        "full_name": data.full_name,
        "full_name_en": data.full_name,
        "email": data.email,
        "national_id": data.national_id,
        "gender": data.gender,
        "date_of_birth": data.date_of_birth,
        "grade": class_doc.get("grade") if class_doc else None,
        "section": class_doc.get("section") if class_doc else None,
        "class_id": data.class_id,
        "education_level": data.education_level,
        "is_active": True,
        "enrollment_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    
    # Add health info if provided
    if data.health:
        student_doc["health_status"] = data.health.get("health_status")
        student_doc["allergies"] = data.health.get("allergies", [])
        student_doc["medications"] = data.health.get("medications", [])
        student_doc["special_needs"] = data.health.get("special_needs")
        student_doc["health_notes"] = data.health.get("notes")
    
    await db.students.insert_one(student_doc)
    
    # Handle parent
    parent_doc = None
    parent_password = None
    
    if data.link_to_parent_id:
        # Link to existing parent
        await db.parents.update_one(
            {"id": data.link_to_parent_id},
            {"$push": {"student_ids": student_id}}
        )
        parent_doc = await db.parents.find_one({"id": data.link_to_parent_id}, {"_id": 0})
    elif data.parent:
        # Create new parent
        parent_id = str(uuid.uuid4())
        parent_password = f"P{random.randint(100000, 999999)}"
        
        parent_doc = {
            "id": parent_id,
            "school_id": school_id,
            "full_name": data.parent.get("full_name"),
            "phone": data.parent.get("phone"),
            "email": data.parent.get("email"),
            "national_id": data.parent.get("national_id"),
            "relation": data.parent.get("relationship", "father"),
            "address": data.parent.get("address"),
            "student_ids": [student_id],
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.parents.insert_one(parent_doc)
        
        # Create parent user account
        parent_user = {
            "id": str(uuid.uuid4()),
            "email": data.parent.get("email") or f"parent_{parent_id[:8]}@{school_code.lower()}.edu.sa",
            "password_hash": hash_password(parent_password),
            "full_name": data.parent.get("full_name"),
            "role": "parent",
            "is_active": True,
            "is_suspended": False,
            "tenant_id": school_id,
            "school_id": school_id,
            "parent_id": parent_id,
            "student_ids": [student_id],
            "permissions": ["view_child_data", "view_grades", "view_attendance"],
            "preferred_language": "ar",
            "preferred_theme": "light",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.users.insert_one(parent_user)
    
    # Update student with parent info
    if parent_doc:
        parent_user_doc = await db.users.find_one(
            {"parent_id": parent_doc.get("id"), "role": "parent"},
            {"_id": 0, "id": 1}
        )
        await db.students.update_one(
            {"id": student_id},
            {"$set": {
                "parent_id": parent_user_doc.get("id") if parent_user_doc else parent_doc.get("id"),
                "parent_name": parent_doc.get("full_name"),
                "parent_phone": parent_doc.get("phone"),
            }}
        )
    
    # Update class student count
    if data.class_id:
        await db.classes.update_one(
            {"id": data.class_id},
            {"$inc": {"student_count": 1}}
        )
    
    # Update school student count
    await db.schools.update_one(
        {"id": school_id},
        {"$inc": {"current_students": 1}}
    )
    
    # Create student user account
    student_password = f"S{random.randint(100000, 999999)}"
    student_email = data.email or f"student_{student_id[:8]}@{school_code.lower()}.edu.sa"
    
    student_user = {
        "id": str(uuid.uuid4()),
        "email": student_email,
        "password_hash": hash_password(student_password),
        "full_name": data.full_name,
        "role": "student",
        "is_active": True,
        "is_suspended": False,
        "tenant_id": school_id,
        "school_id": school_id,
        "student_id": student_id,
        "permissions": ["view_schedule", "view_grades", "view_attendance"],
        "preferred_language": "ar",
        "preferred_theme": "light",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.users.insert_one(student_user)
    
    # Generate welcome message
    welcome_message = f"""مرحباً في نظام نَسَّق!
    
🎓 بيانات الطالب:
الاسم: {data.full_name}
رقم الطالب: {student_number}
البريد: {student_email}
كلمة المرور: {student_password}

👨‍👩‍👧 بيانات ولي الأمر:
الاسم: {parent_doc.get('full_name') if parent_doc else 'غير محدد'}
البريد: {parent_doc.get('email') if parent_doc else 'غير محدد'}
كلمة المرور: {parent_password if parent_password else 'موجودة مسبقاً'}

🔗 رابط تسجيل الدخول: {os.environ.get('FRONTEND_URL', '')}
"""
    
    # Generate QR Code for student
    qr_code = generate_student_qr_code(student_id, data.full_name, student_number)
    
    return {
        "success": True,
        "student": {
            "id": student_id,
            "student_id": student_number,  # Alias for student_number
            "student_number": student_number,
            "full_name": data.full_name,
            "email": student_email,
            "temp_password": student_password,
            "class_name": class_doc.get("name") if class_doc else None,
            "grade": class_doc.get("grade") if class_doc else None,
            "section": class_doc.get("section") if class_doc else None,
            "qr_code": qr_code,  # Base64 encoded QR code image
        },
        "parent": {
            "id": parent_doc.get("id") if parent_doc else None,
            "full_name": parent_doc.get("full_name") if parent_doc else None,
            "email": parent_doc.get("email") if parent_doc else None,
            "phone": parent_doc.get("phone") if parent_doc else None,
            "temp_password": parent_password,
            "is_new": parent_password is not None,
        } if parent_doc else None,
        "welcome_message": welcome_message,
        "siblings": {
            "count": 0,
            "list": [],
        }
    }




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
        "name_en": class_data.name_en,
        "school_id": class_data.school_id,
        "grade_level": class_data.grade_level,
        "section": class_data.section,
        "capacity": class_data.capacity,
        "current_students": 0,
        "homeroom_teacher_id": class_data.homeroom_teacher_id,
        "is_active": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.classes.insert_one(class_doc)
    
    # Get homeroom teacher name
    teacher_name = None
    if class_data.homeroom_teacher_id:
        teacher = await db.teachers.find_one({"id": class_data.homeroom_teacher_id}, {"_id": 0})
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
        "name": subject_data.name,
        "name_en": subject_data.name_en,
        "school_id": subject_data.school_id,
        "code": subject_data.code,
        "description": subject_data.description,
        "weekly_hours": subject_data.weekly_hours,
        "grade_levels": subject_data.grade_levels,
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
        except Exception:
            pass
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
    return d

@router.post("/academic-years", response_model=AcademicYearResponse)
async def create_academic_year(
    data: AcademicYearBase,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN]))
):
    """Create a new academic year"""
    academic_year_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    
    school_id = current_user.get("tenant_id") or data.school_id
    if not school_id:
        raise HTTPException(status_code=400, detail="لم يتم تحديد المدرسة")
    
    if data.is_current:
        await db.academic_years.update_many(
            {"school_id": school_id, "is_current": True},
            {"$set": {"is_current": False}}
        )
    
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
    
    await db.academic_years.insert_one(academic_year_doc)
    
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
    
    academic_years = await db.academic_years.find(query, {"_id": 0}).sort("start_date", -1).to_list(100)
    return [AcademicYearResponse(**normalize_academic_year(ay)) for ay in academic_years]

@router.get("/academic-years/{academic_year_id}", response_model=AcademicYearResponse)
async def get_academic_year(
    academic_year_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get a single academic year"""
    academic_year = await db.academic_years.find_one({"id": academic_year_id}, {"_id": 0})
    if not academic_year:
        raise HTTPException(status_code=404, detail="العام الدراسي غير موجود")
    return AcademicYearResponse(**normalize_academic_year(academic_year))

@router.put("/academic-years/{academic_year_id}", response_model=AcademicYearResponse)
async def update_academic_year(
    academic_year_id: str,
    data: AcademicYearBase,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN]))
):
    """Update an academic year"""
    academic_year = await db.academic_years.find_one({"id": academic_year_id})
    if not academic_year:
        raise HTTPException(status_code=404, detail="العام الدراسي غير موجود")
    
    school_id = current_user.get("tenant_id") or data.school_id or academic_year.get("school_id")
    
    if data.is_current:
        await db.academic_years.update_many(
            {"school_id": school_id, "is_current": True, "id": {"$ne": academic_year_id}},
            {"$set": {"is_current": False}}
        )
    
    update_data = {
        "name": data.name,
        "name_ar": data.name,
        "name_en": data.name_en,
        "start_date": data.start_date,
        "end_date": data.end_date,
        "is_current": data.is_current,
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.academic_years.update_one({"id": academic_year_id}, {"$set": update_data})
    
    updated = await db.academic_years.find_one({"id": academic_year_id}, {"_id": 0})
    return AcademicYearResponse(**normalize_academic_year(updated))

@router.delete("/academic-years/{academic_year_id}")
async def delete_academic_year(
    academic_year_id: str,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN]))
):
    """Delete an academic year"""
    result = await db.academic_years.delete_one({"id": academic_year_id})
    if result.deleted_count == 0:
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
    school_id: str

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
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN]))
):
    """Create a new term/semester"""
    term_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    
    # If setting as current, unset other current terms for this school
    if data.is_current:
        await db.terms.update_many(
            {"school_id": data.school_id, "is_current": True},
            {"$set": {"is_current": False}}
        )
    
    term_doc = {
        "id": term_id,
        "name": data.name,
        "name_en": data.name_en,
        "academic_year_id": data.academic_year_id,
        "start_date": data.start_date,
        "end_date": data.end_date,
        "is_current": data.is_current,
        "school_id": data.school_id,
        "created_at": now,
        "updated_at": now,
        "created_by": current_user.get("id")
    }
    
    await db.terms.insert_one(term_doc)
    
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
    
    terms = await db.terms.find(query, {"_id": 0}).sort("start_date", -1).to_list(100)
    return [TermResponse(**t) for t in terms]

@router.get("/terms/{term_id}", response_model=TermResponse)
async def get_term(
    term_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get a single term"""
    term = await db.terms.find_one({"id": term_id}, {"_id": 0})
    if not term:
        raise HTTPException(status_code=404, detail="الفصل الدراسي غير موجود")
    return TermResponse(**term)

@router.put("/terms/{term_id}", response_model=TermResponse)
async def update_term(
    term_id: str,
    data: TermBase,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN]))
):
    """Update a term"""
    term = await db.terms.find_one({"id": term_id})
    if not term:
        raise HTTPException(status_code=404, detail="الفصل الدراسي غير موجود")
    
    # If setting as current, unset other current terms
    if data.is_current:
        await db.terms.update_many(
            {"school_id": data.school_id, "is_current": True, "id": {"$ne": term_id}},
            {"$set": {"is_current": False}}
        )
    
    update_data = {
        "name": data.name,
        "name_en": data.name_en,
        "academic_year_id": data.academic_year_id,
        "start_date": data.start_date,
        "end_date": data.end_date,
        "is_current": data.is_current,
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.terms.update_one({"id": term_id}, {"$set": update_data})
    
    updated = await db.terms.find_one({"id": term_id}, {"_id": 0})
    return TermResponse(**updated)

@router.delete("/terms/{term_id}")
async def delete_term(
    term_id: str,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN]))
):
    """Delete a term"""
    result = await db.terms.delete_one({"id": term_id})
    if result.deleted_count == 0:
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
    
    await db.grade_levels.insert_one(grade_doc)
    
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
    
    grade_levels = await db.grade_levels.find(query, {"_id": 0}).sort("order", 1).to_list(100)
    return [GradeLevelResponse(**gl) for gl in grade_levels]

@router.get("/grade-levels/{grade_id}", response_model=GradeLevelResponse)
async def get_grade_level(
    grade_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get a single grade level"""
    grade = await db.grade_levels.find_one({"id": grade_id}, {"_id": 0})
    if not grade:
        raise HTTPException(status_code=404, detail="المرحلة الدراسية غير موجودة")
    return GradeLevelResponse(**grade)

@router.put("/grade-levels/{grade_id}", response_model=GradeLevelResponse)
async def update_grade_level(
    grade_id: str,
    data: GradeLevelBase,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN]))
):
    """Update a grade level"""
    grade = await db.grade_levels.find_one({"id": grade_id})
    if not grade:
        raise HTTPException(status_code=404, detail="المرحلة الدراسية غير موجودة")
    
    update_data = {
        "name": data.name,
        "name_en": data.name_en,
        "order": data.order,
        "is_active": data.is_active,
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.grade_levels.update_one({"id": grade_id}, {"$set": update_data})
    
    updated = await db.grade_levels.find_one({"id": grade_id}, {"_id": 0})
    return GradeLevelResponse(**updated)

@router.delete("/grade-levels/{grade_id}")
async def delete_grade_level(
    grade_id: str,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN]))
):
    """Delete a grade level"""
    result = await db.grade_levels.delete_one({"id": grade_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="المرحلة الدراسية غير موجودة")
    return {"message": "تم حذف المرحلة الدراسية بنجاح"}





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
        existing = await db.educational_stages.find_one({"code": stage["code"], "is_global": True})
        if not existing:
            stage["id"] = str(uuid.uuid4())
            stage["tenant_id"] = None
            stage["is_global"] = True
            stage["is_active"] = True
            stage["created_at"] = datetime.now(timezone.utc).isoformat()
            stage["created_by"] = current_user["id"]
            await db.educational_stages.insert_one(stage)
            count += 1
    
    return {"message": f"تم إضافة {count} مرحلة تعليمية", "added": count}


@router.get("/academic/stages")
async def get_educational_stages(
    school_id: Optional[str] = None,
    include_global: bool = True,
    current_user: dict = Depends(get_current_user)
):
    """Get educational stages"""
    query = {"is_active": True}
    
    if school_id:
        if include_global:
            query["$or"] = [{"tenant_id": school_id}, {"is_global": True}]
        else:
            query["tenant_id"] = school_id
    else:
        query["is_global"] = True
    
    stages = await db.educational_stages.find(query, {"_id": 0}).sort("order", 1).to_list(100)
    return {"stages": stages, "total": len(stages)}


@router.post("/academic/grades/seed-defaults")
async def seed_default_grades(
    school_id: str,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN]))
):
    """Seed default grades for a school"""
    stages = await db.educational_stages.find(
        {"$or": [{"tenant_id": school_id}, {"is_global": True}], "is_active": True},
        {"_id": 0}
    ).to_list(100)
    
    grade_names_ar = {1: "الأول", 2: "الثاني", 3: "الثالث", 4: "الرابع", 5: "الخامس", 6: "السادس"}
    
    count = 0
    for stage in stages:
        stage_code = stage.get("code")
        grades_count = stage.get("grades_count", 3)
        
        for i in range(1, grades_count + 1):
            existing = await db.grades.find_one({
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
                await db.grades.insert_one(grade_doc)
                count += 1
    
    return {"message": f"تم إضافة {count} صف دراسي", "added": count}


@router.get("/academic/grades")
async def get_grades(
    school_id: str,
    stage_code: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """Get grades for a school"""
    query = {"tenant_id": school_id, "is_active": True}
    if stage_code:
        query["stage_code"] = stage_code
    
    grades = await db.grades.find(query, {"_id": 0}).sort("display_order", 1).to_list(100)
    return {"grades": grades, "total": len(grades)}


@router.post("/academic/grades")
async def create_grade(
    data: GradeCreate,
    school_id: str,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN]))
):
    """Create a new grade"""
    # Get stage info
    stage = await db.educational_stages.find_one({
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
    
    await db.grades.insert_one(grade_doc)
    grade_doc.pop("_id", None)
    return grade_doc


@router.post("/academic/sections")
async def create_section(
    data: SectionCreate,
    school_id: str,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN]))
):
    """Create a new section/class"""
    # Get grade info
    grade = await db.grades.find_one({"id": data.grade_id, "tenant_id": school_id}, {"_id": 0})
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
        "current_count": 0,
        "homeroom_teacher_id": data.homeroom_teacher_id,
        "classroom_id": data.classroom_id,
        "is_active": True,
        "academic_year": data.academic_year,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by": current_user["id"]
    }
    
    await db.sections.insert_one(section_doc)
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
    query = {"tenant_id": school_id, "is_active": True}
    if grade_id:
        query["grade_id"] = grade_id
    if stage_code:
        query["stage_code"] = stage_code
    
    sections = await db.sections.find(query, {"_id": 0}).sort("full_name_ar", 1).to_list(1000)
    return {"sections": sections, "total": len(sections)}


@router.put("/academic/sections/{section_id}")
async def update_section(
    section_id: str,
    updates: dict,
    current_user: dict = Depends(require_roles([UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN]))
):
    """Update a section"""
    protected = ["id", "tenant_id", "created_at", "created_by"]
    for field in protected:
        updates.pop(field, None)
    
    updates["updated_at"] = datetime.now(timezone.utc).isoformat()
    updates["updated_by"] = current_user["id"]
    
    await db.sections.update_one({"id": section_id}, {"$set": updates})
    return await db.sections.find_one({"id": section_id}, {"_id": 0})


@router.post("/academic/sections/{section_id}/assign-teacher")
async def assign_homeroom_teacher(
    section_id: str,
    teacher_id: str,
    current_user: dict = Depends(require_roles([UserRole.SCHOOL_PRINCIPAL]))
):
    """Assign homeroom teacher to section"""
    now = datetime.now(timezone.utc).isoformat()
    
    await db.sections.update_one(
        {"id": section_id},
        {"$set": {
            "homeroom_teacher_id": teacher_id,
            "homeroom_assigned_at": now,
            "homeroom_assigned_by": current_user["id"]
        }}
    )
    
    return await db.sections.find_one({"id": section_id}, {"_id": 0})


@router.post("/academic/classrooms")
async def create_classroom(
    data: ClassroomCreate,
    school_id: str,
    current_user: dict = Depends(require_roles([UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN]))
):
    """Create a physical classroom"""
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
    
    await db.physical_classrooms.insert_one(classroom_doc)
    classroom_doc.pop("_id", None)
    return classroom_doc


@router.get("/academic/classrooms")
async def get_classrooms(
    school_id: str,
    room_type: Optional[str] = None,
    available_only: bool = False,
    current_user: dict = Depends(get_current_user)
):
    """Get physical classrooms"""
    query = {"tenant_id": school_id}
    if room_type:
        query["room_type"] = room_type
    if available_only:
        query["is_available"] = True
    
    classrooms = await db.physical_classrooms.find(query, {"_id": 0}).sort("name", 1).to_list(1000)
    return {"classrooms": classrooms, "total": len(classrooms)}


@router.put("/academic/classrooms/{classroom_id}")
async def update_classroom(
    classroom_id: str,
    updates: dict,
    current_user: dict = Depends(require_roles([UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN]))
):
    """Update a classroom"""
    protected = ["id", "tenant_id", "created_at", "created_by"]
    for field in protected:
        updates.pop(field, None)
    
    updates["updated_at"] = datetime.now(timezone.utc).isoformat()
    updates["updated_by"] = current_user["id"]
    
    await db.physical_classrooms.update_one({"id": classroom_id}, {"$set": updates})
    return await db.physical_classrooms.find_one({"id": classroom_id}, {"_id": 0})


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
        existing = await db.subjects.find_one({"code": subject["code"], "is_global": True})
        if not existing:
            subject["id"] = str(uuid.uuid4())
            subject["tenant_id"] = None
            subject["is_global"] = True
            subject["is_active"] = True
            subject["created_at"] = datetime.now(timezone.utc).isoformat()
            subject["created_by"] = current_user["id"]
            await db.subjects.insert_one(subject)
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
    query = {"is_active": True}
    
    if school_id:
        if include_global:
            query["$or"] = [{"tenant_id": school_id}, {"is_global": True}]
        else:
            query["tenant_id"] = school_id
    else:
        query["is_global"] = True
    
    if category:
        query["category"] = category
    
    subjects = await db.subjects.find(query, {"_id": 0}).sort("name_ar", 1).to_list(1000)
    
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
    subject_doc = {
        "id": str(uuid.uuid4()),
        "tenant_id": school_id,
        "name_ar": data.name_ar,
        "name_en": data.name_en,
        "code": data.code,
        "category": data.category,
        "default_periods": data.default_periods,
        "stages": data.stages,
        "is_global": school_id is None,
        "is_active": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by": current_user["id"]
    }
    
    await db.subjects.insert_one(subject_doc)
    subject_doc.pop("_id", None)
    return subject_doc


@router.get("/academic/structure/{school_id}")
async def get_academic_structure(
    school_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get complete academic structure for a school"""
    stages = await db.educational_stages.find(
        {"$or": [{"tenant_id": school_id}, {"is_global": True}], "is_active": True},
        {"_id": 0}
    ).sort("order", 1).to_list(100)
    
    grades = await db.grades.find({"tenant_id": school_id, "is_active": True}, {"_id": 0}).to_list(100)
    sections = await db.sections.find({"tenant_id": school_id, "is_active": True}, {"_id": 0}).to_list(1000)
    classrooms = await db.physical_classrooms.find({"tenant_id": school_id}, {"_id": 0}).to_list(1000)
    subjects = await db.subjects.find(
        {"$or": [{"tenant_id": school_id}, {"is_global": True}], "is_active": True},
        {"_id": 0}
    ).to_list(1000)
    
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
    
    stages = await db.school_stages.find({"school_id": school_id}, {"_id": 0}).sort("order", 1).to_list(50)
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
    
    await db.school_stages.insert_one(stage)
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
    grades_count = await db.school_grades.count_documents({"stage_id": stage_id, "school_id": school_id})
    if grades_count > 0:
        raise HTTPException(status_code=400, detail=f"لا يمكن حذف المرحلة لأنها تحتوي على {grades_count} صفوف")
    
    await db.school_stages.delete_one({"id": stage_id, "school_id": school_id})
    
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
    await db.audit_logs.insert_one(audit_log)
    
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
    
    result = await db.school_stages.update_one(
        {"id": stage_id, "school_id": school_id},
        {"$set": update_data}
    )
    
    if result.matched_count == 0:
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
    await db.audit_logs.insert_one(audit_log)
    
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
    
    grades = await db.school_grades.find({"school_id": school_id}, {"_id": 0}).to_list(100)
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
    
    await db.school_grades.insert_one(grade)
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
    classes_count = await db.classes.count_documents({"grade_id": grade_id, "school_id": school_id})
    if classes_count > 0:
        raise HTTPException(status_code=400, detail=f"لا يمكن حذف الصف لأنه يحتوي على {classes_count} فصل")
    
    await db.school_grades.delete_one({"id": grade_id, "school_id": school_id})
    
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
    await db.audit_logs.insert_one(audit_log)
    
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
    
    result = await db.school_grades.update_one(
        {"id": grade_id, "school_id": school_id},
        {"$set": update_data}
    )
    
    if result.matched_count == 0:
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
    await db.audit_logs.insert_one(audit_log)
    
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
    
    sections = await db.school_sections.find({"school_id": school_id}, {"_id": 0}).to_list(200)
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
    
    await db.school_sections.insert_one(section)
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
    
    await db.school_sections.delete_one({"id": section_id, "school_id": school_id})
    
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
    
    terms = await db.academic_terms.find({"school_id": school_id}, {"_id": 0}).sort("start_date", 1).to_list(10)
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
    
    await db.academic_terms.insert_one(term)
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
    
    await db.academic_terms.update_one(
        {"id": term_id, "school_id": school_id},
        {
            "$set": {
                "name": data.name,
                "name_en": data.name_en,
                "start_date": data.start_date,
                "end_date": data.end_date,
                "is_active": data.is_active,
                "updated_at": datetime.now(timezone.utc).isoformat()
            }
        }
    )
    
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
    
    await db.academic_terms.delete_one({"id": term_id, "school_id": school_id})
    
    return {"message": "تم حذف الفصل الدراسي"}





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
    await db.school_constraints.insert_one(constraint_doc)
    
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
    constraint = await db.school_constraints.find_one(
        {"id": constraint_id, "school_id": school_id},
        {"_id": 0}
    )
    
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
    
    await db.school_constraints.update_one(
        {"id": constraint_id, "school_id": school_id}, 
        {"$set": update_data}
    )
    
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
    constraint = await db.school_constraints.find_one(
        {"id": constraint_id, "school_id": school_id}, 
        {"_id": 0}
    )
    
    if not constraint:
        raise HTTPException(status_code=404, detail="القيد غير موجود")
    
    # Soft delete
    await db.school_constraints.update_one(
        {"id": constraint_id, "school_id": school_id},
        {"$set": {"is_active": False, "deleted_at": datetime.now(timezone.utc).isoformat()}}
    )
    
    return {"message": "تم حذف القيد بنجاح"}

@router.get("/school/constraints")
async def get_school_constraints(
    current_user: dict = Depends(get_current_user),
    x_school_context: str = Header(default=None, alias="X-School-Context")
):
    """Get all constraints for the school - جلب جميع القيود للمدرسة"""
    school_id = await get_school_id_from_context(current_user, x_school_context)
    
    # Get school-specific constraints first
    school_constraints = await db.school_constraints.find(
        {"school_id": school_id},
        {"_id": 0}
    ).to_list(100)
    
    # If no school-specific constraints, get reference constraints as starting point
    if not school_constraints:
        ref_constraints = await db.admin_constraints.find(
            {"is_active": True},
            {"_id": 0}
        ).to_list(100)
        
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
            await db.school_constraints.insert_one(school_constraint)
            school_constraint.pop("_id", None)
            school_constraints.append(school_constraint)
    
    return school_constraints


@router.get("/teachers/options/grades")
async def get_teacher_grades_options(current_user: dict = Depends(get_current_user)):
    """Get available grade levels from reference database or school classes"""
    
    grades = await db.academic_grades.find(
        {"is_active": True},
        {"_id": 0}
    ).sort("order", 1).to_list(100)
    
    if grades:
        stages = await db.academic_stages.find({"is_active": True}, {"_id": 0}).sort("order", 1).to_list(10)
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
    
    school_id = current_user.get("school_id") or current_user.get("tenant_id")
    query = {"school_id": school_id} if school_id else {}
    classes = await db.classes.find(query, {"_id": 0, "name": 1, "name_ar": 1, "grade": 1, "grade_level": 1}).to_list(500)
    
    import re
    grade_map = {}
    GRADE_ORDER = {
        'الأول': 1, 'الثاني': 2, 'الثالث': 3, 'الرابع': 4,
        'الخامس': 5, 'السادس': 6, 'السابع': 7, 'الثامن': 8,
        'التاسع': 9, 'العاشر': 10, 'الحادي عشر': 11, 'الثاني عشر': 12,
    }
    for cls in classes:
        cls_name = cls.get("name") or cls.get("name_ar") or ""
        match = re.match(r'(الصف\s+\S+)', cls_name)
        if match:
            grade_name = match.group(1)
            if grade_name not in grade_map:
                order_num = 99
                for ar_name, num in GRADE_ORDER.items():
                    if ar_name in grade_name:
                        order_num = num
                        break
                grade_id = f"grade-{order_num}"
                grade_map[grade_name] = {
                    "id": grade_id,
                    "name": grade_name,
                    "name_ar": grade_name,
                    "name_en": f"Grade {order_num}" if order_num != 99 else grade_name,
                    "grade": order_num,
                }
    
    sorted_grades = sorted(grade_map.values(), key=lambda g: g["grade"])
    return {"grades": sorted_grades}

@router.get("/teachers/options/academic-degrees")
async def get_academic_degrees_options(current_user: dict = Depends(get_current_user)):
    """Get available academic degrees from DB or defaults"""
    db_degrees = await db.lookup_options.find(
        {"type": "academic_degree", "is_active": {"$ne": False}},
        {"_id": 0}
    ).to_list(20)
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
    ranks = await db.lookup_options.find(
        {"type": "teacher_rank", "is_active": {"$ne": False}},
        {"_id": 0}
    ).sort("order", 1).to_list(100)
    
    if not ranks:
        ranks = await db.teacher_ranks.find({"is_active": True}, {"_id": 0}).sort("order", 1).to_list(100)
    
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
    db_types = await db.lookup_options.find(
        {"type": "contract_type", "is_active": {"$ne": False}},
        {"_id": 0}
    ).to_list(20)
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
    db_nations = await db.lookup_options.find(
        {"type": "nationality", "is_active": {"$ne": False}},
        {"_id": 0}
    ).to_list(100)
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
    current_user: dict = Depends(get_current_user)
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
    existing = await db.users.find_one({"email": email})
    if existing:
        raise HTTPException(status_code=400, detail="البريد الإلكتروني مسجل مسبقاً")
    
    # Get school info
    school = await db.schools.find_one({"id": school_id}, {"_id": 0, "code": 1})
    school_code = school.get("code", "NSS") if school else "NSS"
    
    # Generate IDs and password
    teacher_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    temp_password = f"T{random.randint(100000, 999999)}"
    
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
    
    await db.teachers.insert_one(teacher_doc)
    await db.users.insert_one(user_doc)
    
    # Update school teacher count
    await db.schools.update_one(
        {"id": school_id},
        {"$inc": {"current_teachers": 1}}
    )
    
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

@router.post("/teachers", response_model=TeacherResponse)
async def create_teacher(
    teacher_data: TeacherCreate,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.SCHOOL_SUB_ADMIN]))
):
    """Create a new teacher"""
    # Check if email already exists
    existing = await db.users.find_one({"email": teacher_data.email})
    if existing:
        raise HTTPException(status_code=400, detail="البريد الإلكتروني مسجل مسبقاً")
    
    # Create user account for teacher
    user_id = str(uuid.uuid4())
    teacher_id = str(uuid.uuid4())
    
    user_doc = {
        "id": user_id,
        "email": teacher_data.email,
        "password_hash": hash_password("Teacher@123"),  # Default password
        "full_name": teacher_data.full_name,
        "full_name_en": teacher_data.full_name_en,
        "role": UserRole.TEACHER.value,
        "tenant_id": teacher_data.school_id,
        "phone": teacher_data.phone,
        "avatar_url": None,
        "is_active": True,
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
    
    await db.users.insert_one(user_doc)
    await db.teachers.insert_one(teacher_doc)
    
    # Update school teacher count
    await db.schools.update_one(
        {"id": teacher_data.school_id},
        {"$inc": {"current_teachers": 1}}
    )

    try:
        from routes.school_settings_mod import _ensure_teacher_linked_to_all_classes
        await _ensure_teacher_linked_to_all_classes(teacher_data.school_id, teacher_id)
    except Exception as e:
        logger.warning(f"Auto-assign teacher {teacher_id} to classes failed: {e}")
    
    return TeacherResponse(**teacher_doc)

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
    
    teachers = await db.teachers.find(query, {"_id": 0}).to_list(1000)
    
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

@router.get("/teachers/{teacher_id}", response_model=TeacherResponse)
async def get_teacher(teacher_id: str, current_user: dict = Depends(get_current_user)):
    """Get teacher by ID"""
    teacher = await db.teachers.find_one({"id": teacher_id}, {"_id": 0})
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
    
    result = await db.teachers.update_one(
        {"id": teacher_id},
        {"$set": update_fields}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="المعلم غير موجود")
    return {"message": "تم تحديث بيانات المعلم", "success": True}

@router.delete("/teachers/{teacher_id}")
async def delete_teacher(
    teacher_id: str,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN]))
):
    """Delete teacher — full removal from system"""
    teacher = await db.teachers.find_one({"id": teacher_id}, {"_id": 0})
    if not teacher:
        raise HTTPException(status_code=404, detail="المعلم غير موجود")
    
    school_id = teacher.get("school_id")
    user_id = teacher.get("user_id")

    cleanup = {}
    await db.teachers.delete_one({"id": teacher_id})

    await db.schools.update_one(
        {"id": school_id},
        {"$inc": {"current_teachers": -1}}
    )

    r = await db.teacher_assignments.delete_many({"teacher_id": teacher_id})
    cleanup["teacher_assignments"] = r.deleted_count
    r = await db.teacher_class_assignments.delete_many({"teacher_id": teacher_id})
    cleanup["teacher_class_assignments"] = r.deleted_count
    r = await db.teacher_subjects.delete_many({"teacher_id": teacher_id})
    cleanup["teacher_subjects"] = r.deleted_count
    r = await db.teacher_attendance.delete_many({"teacher_id": teacher_id})
    cleanup["teacher_attendance"] = r.deleted_count
    r = await db.timetable_sessions.delete_many({"teacher_id": teacher_id})
    cleanup["timetable_sessions"] = r.deleted_count
    r = await db.class_sessions.delete_many({"teacher_id": teacher_id})
    cleanup["class_sessions"] = r.deleted_count
    r = await db.session_event_log.delete_many({"teacher_id": teacher_id})
    cleanup["session_event_log"] = r.deleted_count
    r = await db.user_relationships.delete_many({"$or": [{"source_id": teacher_id}, {"target_id": teacher_id}]})
    cleanup["user_relationships"] = r.deleted_count

    if user_id:
        await db.users.delete_one({"id": user_id})
        await db.user_roles.delete_many({"user_id": user_id})
        await db.user_identities.delete_many({"user_id": user_id})
        cleanup["user_account"] = 1

    return {"message": "تم حذف المعلم وجميع بياناته من النظام بالكامل", "success": True, "cleanup": cleanup}


@router.delete("/parents/{parent_id}")
async def delete_parent(
    parent_id: str,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN]))
):
    """Delete parent — full removal from system"""
    tenant_id = current_user.get("tenant_id")
    parent = await db.parents.find_one({"id": parent_id, "tenant_id": tenant_id}, {"_id": 0})
    if not parent:
        raise HTTPException(status_code=404, detail="ولي الأمر غير موجود")

    user_id = parent.get("user_id")

    cleanup = {}
    await db.parents.delete_one({"id": parent_id})

    r = await db.guardian_links.delete_many({"parent_id": parent_id})
    cleanup["guardian_links"] = r.deleted_count
    r = await db.user_relationships.delete_many({"$or": [{"source_id": parent_id}, {"target_id": parent_id}]})
    cleanup["user_relationships"] = r.deleted_count

    await db.students.update_many(
        {"parent_ids": parent_id},
        {"$pull": {"parent_ids": parent_id}}
    )

    if user_id:
        await db.users.delete_one({"id": user_id})
        await db.user_roles.delete_many({"user_id": user_id})
        await db.user_identities.delete_many({"user_id": user_id})
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
    talents = await db.global_talents.find(query, {"_id": 0}).sort("name_ar", 1).to_list(500)
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
    existing = await db.global_talents.find_one({
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
    await db.global_talents.insert_one(talent_doc)
    talent_doc.pop("_id", None)
    return talent_doc
