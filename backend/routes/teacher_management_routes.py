"""
Teacher Management Routes - مسارات إدارة المعلمين
API endpoints for teacher management by school principals
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional, List
from pydantic import BaseModel, Field, EmailStr
from enum import Enum
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/teachers", tags=["Teachers"])

# ==================== Enums ====================

class Gender(str, Enum):
    male = "male"
    female = "female"

class TeacherRank(str, Enum):
    teacher = "teacher"
    senior_teacher = "senior_teacher"
    expert = "expert"
    department_head = "department_head"
    assistant = "assistant"
    advanced = "advanced"
    practitioner = "practitioner"

class ContractType(str, Enum):
    permanent = "permanent"
    contract = "contract"
    part_time = "part_time"

# ==================== Request Models ====================

class TeacherBasicInfoRequest(BaseModel):
    full_name_ar: str = Field(..., min_length=3)
    full_name_en: Optional[str] = None
    national_id: str = Field(..., min_length=10, max_length=10)
    date_of_birth: Optional[str] = None
    gender: Gender
    nationality: str = Field(default="SA")
    phone: str
    email: EmailStr

class TeacherQualificationsRequest(BaseModel):
    academic_degree: str
    specialization: Optional[str] = None
    university: Optional[str] = None
    graduation_year: Optional[int] = None
    years_of_experience: int = Field(ge=0)
    teacher_rank: TeacherRank
    certifications: Optional[List[str]] = None

class TeacherSubjectsRequest(BaseModel):
    subject_ids: List[str]
    grade_ids: List[str]
    primary_subject_id: str
    max_periods_per_week: int = Field(default=24, ge=1, le=30)

class TeacherScheduleRequest(BaseModel):
    contract_type: ContractType = ContractType.permanent
    available_days: List[str] = ["sunday", "monday", "tuesday", "wednesday", "thursday"]
    preferred_periods: Optional[List[int]] = None
    notes: Optional[str] = None

class CreateTeacherFullRequest(BaseModel):
    basic_info: TeacherBasicInfoRequest
    qualifications: TeacherQualificationsRequest
    subjects: TeacherSubjectsRequest
    schedule: Optional[TeacherScheduleRequest] = None

class ValidateRequest(BaseModel):
    value: str

# ==================== Helper ====================

def get_teacher_engine(db):
    from engines.teacher_management_engine import TeacherManagementEngine
    return TeacherManagementEngine(db)

# ==================== Routes ====================

def create_teacher_management_routes(db, get_current_user):
    """Create routes with database dependency"""
    
    engine = get_teacher_engine(db)
    
    # ==================== Options ====================
    
    @router.get("/options/subjects")
    async def get_subjects(current_user: dict = Depends(get_current_user)):
        tenant_id = current_user.get("tenant_id")
        if not tenant_id:
            raise HTTPException(status_code=400, detail="Tenant ID required")
        subjects = await engine.get_subjects(tenant_id)
        return {"subjects": subjects}
    
    @router.get("/options/grades")
    async def get_grades(current_user: dict = Depends(get_current_user)):
        tenant_id = current_user.get("tenant_id")
        if not tenant_id:
            raise HTTPException(status_code=400, detail="Tenant ID required")
        grades = await engine.get_grades(tenant_id)
        return {"grades": grades}
    
    @router.get("/options/academic-degrees")
    async def get_academic_degrees():
        degrees = await engine.get_academic_degrees()
        return {"degrees": degrees}
    
    @router.get("/options/teacher-ranks")
    async def get_teacher_ranks():
        ranks = await engine.get_teacher_ranks()
        return {"ranks": ranks}
    
    @router.get("/options/contract-types")
    async def get_contract_types():
        types = await engine.get_contract_types()
        return {"types": types}
    
    @router.get("/options/nationalities")
    async def get_nationalities():
        nationalities = await engine.get_nationalities()
        return {"nationalities": nationalities}
    
    # ==================== Validation ====================
    
    @router.post("/validate/national-id")
    async def validate_national_id(
        request: ValidateRequest,
        current_user: dict = Depends(get_current_user)
    ):
        tenant_id = current_user.get("tenant_id")
        if not tenant_id:
            raise HTTPException(status_code=400, detail="Tenant ID required")
        result = await engine.validate_national_id(request.value, tenant_id)
        return result
    
    @router.post("/validate/email")
    async def validate_email(
        request: ValidateRequest,
        current_user: dict = Depends(get_current_user)
    ):
        tenant_id = current_user.get("tenant_id")
        if not tenant_id:
            raise HTTPException(status_code=400, detail="Tenant ID required")
        result = await engine.validate_email(request.value, tenant_id)
        return result
    
    # ==================== CRUD ====================
    
    @router.post("/create")
    async def create_teacher(
        request: CreateTeacherFullRequest,
        current_user: dict = Depends(get_current_user)
    ):
        tenant_id = current_user.get("tenant_id")
        if not tenant_id:
            raise HTTPException(status_code=400, detail="Tenant ID required")
        
        allowed_roles = ["platform_admin", "school_principal", "school_admin", "school_sub_admin"]
        if current_user.get("role") not in allowed_roles:
            raise HTTPException(status_code=403, detail="Permission denied")
        
        from engines.teacher_management_engine import (
            CreateTeacherRequest,
            TeacherBasicInfo,
            TeacherQualifications,
            TeacherSubjectsAssignment,
            TeacherSchedulePreferences,
            Gender as EngineGender,
            TeacherRank as EngineRank,
            ContractType as EngineContract
        )
        
        basic_info = TeacherBasicInfo(
            full_name_ar=request.basic_info.full_name_ar,
            full_name_en=request.basic_info.full_name_en,
            national_id=request.basic_info.national_id,
            date_of_birth=request.basic_info.date_of_birth,
            gender=EngineGender(request.basic_info.gender.value),
            nationality=request.basic_info.nationality,
            phone=request.basic_info.phone,
            email=request.basic_info.email,
        )
        
        qualifications = TeacherQualifications(
            academic_degree=request.qualifications.academic_degree,
            specialization=request.qualifications.specialization,
            university=request.qualifications.university,
            graduation_year=request.qualifications.graduation_year,
            years_of_experience=request.qualifications.years_of_experience,
            teacher_rank=EngineRank(request.qualifications.teacher_rank.value),
            certifications=request.qualifications.certifications,
        )
        
        subjects = TeacherSubjectsAssignment(
            subject_ids=request.subjects.subject_ids,
            grade_ids=request.subjects.grade_ids,
            primary_subject_id=request.subjects.primary_subject_id,
            max_periods_per_week=request.subjects.max_periods_per_week,
        )
        
        schedule = None
        if request.schedule:
            schedule = TeacherSchedulePreferences(
                contract_type=EngineContract(request.schedule.contract_type.value),
                available_days=request.schedule.available_days,
                preferred_periods=request.schedule.preferred_periods,
                notes=request.schedule.notes,
            )
        
        engine_request = CreateTeacherRequest(
            basic_info=basic_info,
            qualifications=qualifications,
            subjects=subjects,
            schedule=schedule,
        )
        
        result = await engine.create_teacher(
            engine_request,
            tenant_id,
            str(current_user.get("_id", current_user.get("id", "system")))
        )
        
        if not result.get("success"):
            raise HTTPException(status_code=400, detail=result.get("error", "Failed to create teacher"))
        
        try:
            teacher_id = result.get("teacher", {}).get("id") or result.get("teacher_id")
            if teacher_id:
                from routes.school_settings_mod import _ensure_teacher_linked_to_all_classes
                await _ensure_teacher_linked_to_all_classes(tenant_id, teacher_id)
        except Exception as e:
            logger.warning(f"Auto-assign teacher {teacher_id if 'teacher_id' in dir() else '?'} to classes failed: {e}")
        
        return result
    
    @router.get("/")
    async def list_teachers(
        subject_id: Optional[str] = Query(None),
        grade_id: Optional[str] = Query(None),
        status: Optional[str] = Query(None),
        search: Optional[str] = Query(None),
        skip: int = Query(0, ge=0),
        limit: int = Query(50, ge=1, le=100),
        current_user: dict = Depends(get_current_user)
    ):
        tenant_id = current_user.get("tenant_id")
        if not tenant_id:
            raise HTTPException(status_code=400, detail="Tenant ID required")
        
        result = await engine.list_teachers(
            tenant_id,
            subject_id=subject_id,
            grade_id=grade_id,
            status=status,
            search=search,
            skip=skip,
            limit=limit
        )
        return result
    
    @router.get("/{teacher_id}")
    async def get_teacher(
        teacher_id: str,
        current_user: dict = Depends(get_current_user)
    ):
        tenant_id = current_user.get("tenant_id")
        if not tenant_id:
            raise HTTPException(status_code=400, detail="Tenant ID required")
        
        teacher = await engine.get_teacher(teacher_id, tenant_id)
        if not teacher:
            raise HTTPException(status_code=404, detail="Teacher not found")
        return teacher
    
    return router
