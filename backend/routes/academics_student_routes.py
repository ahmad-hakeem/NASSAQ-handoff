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
        "user_id": None,
        "full_name": student_data.full_name,
        "full_name_en": getattr(student_data, 'full_name_en', None),
        "email": student_data.email,
        "phone": student_data.phone,
        "school_id": getattr(student_data, 'school_id', None) or current_user.get("tenant_id"),
        "class_id": student_data.class_id,
        "student_number": student_data.student_number,
        "date_of_birth": getattr(student_data, 'date_of_birth', None),
        "gender": getattr(student_data, 'gender', None),
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
    
    await db.schools.update_one(
        {"id": student_doc["school_id"]},
        {"$inc": {"current_students": 1}}
    )
    
    if student_data.class_id:
        await db.classes.update_one(
            {"id": student_data.class_id},
            {"$inc": {"current_students": 1}}
        )
    
    await audit_engine.log(
        action=AuditAction.USER_CREATED.value,
        performed_by=current_user.get("id"),
        tenant_id=student_doc["school_id"],
        entity_type="student",
        entity_id=student_id,
        details={
            "full_name": student_data.full_name,
            "school_id": student_doc["school_id"],
            "class_id": student_data.class_id,
        },
        actor_name=current_user.get("full_name"),
        actor_role=current_user.get("role"),
        actor_email=current_user.get("email"),
    )
    
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
    
    await audit_engine.log(
        action=AuditAction.USER_UPDATED.value,
        performed_by=current_user.get("id"),
        tenant_id=school_id,
        entity_type="student",
        entity_id=student_id,
        details={"updated_fields": list(update_fields.keys())},
        actor_name=current_user.get("full_name"),
        actor_role=current_user.get("role"),
        actor_email=current_user.get("email"),
    )
    
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

    await audit_engine.log(
        action=AuditAction.USER_DELETED.value,
        performed_by=current_user.get("id"),
        tenant_id=school_id,
        entity_type="student",
        entity_id=student_id,
        details={
            "full_name": student.get("full_name"),
            "school_id": school_id,
            "class_id": class_id,
        },
        actor_name=current_user.get("full_name"),
        actor_role=current_user.get("role"),
        actor_email=current_user.get("email"),
    )

    cleanup = {}
    await db.attendance.delete_many({"student_id": student_id})
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




