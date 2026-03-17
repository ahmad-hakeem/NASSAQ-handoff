"""
Student Management Routes - مسارات إدارة الطلاب
API endpoints for student management operations
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import Optional
from pydantic import BaseModel, Field, EmailStr
from enum import Enum
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/students", tags=["Students"])

# ==================== Pydantic Models ====================

class Gender(str, Enum):
    male = "male"
    female = "female"

class ParentRelation(str, Enum):
    father = "father"
    mother = "mother"
    guardian = "guardian"
    other = "other"

class StudentBasicInfoRequest(BaseModel):
    full_name_ar: str = Field(..., min_length=3, max_length=100)
    full_name_en: Optional[str] = Field(None, max_length=100)
    national_id: str = Field(..., min_length=10, max_length=10)
    date_of_birth: str = Field(...)
    gender: Gender
    nationality: str = Field(default="SA")
    grade_id: str = Field(...)
    section_id: str = Field(...)

class ParentContactInfoRequest(BaseModel):
    parent_name_ar: str = Field(..., min_length=3, max_length=100)
    parent_name_en: Optional[str] = Field(None, max_length=100)
    parent_national_id: Optional[str] = Field(None)
    parent_phone: str = Field(...)
    parent_email: Optional[EmailStr] = None
    parent_relation: ParentRelation
    emergency_contact: Optional[str] = None
    emergency_phone: Optional[str] = None
    address: Optional[str] = None

class StudentHealthInfoRequest(BaseModel):
    blood_type: Optional[str] = None
    has_chronic_conditions: bool = False
    chronic_conditions: Optional[str] = None
    has_allergies: bool = False
    allergies: Optional[str] = None
    has_disabilities: bool = False
    disabilities: Optional[str] = None
    current_medications: Optional[str] = None
    requires_special_care: bool = False
    special_care_notes: Optional[str] = None
    emergency_medical_notes: Optional[str] = None

class CreateStudentFullRequest(BaseModel):
    basic_info: StudentBasicInfoRequest
    parent_info: ParentContactInfoRequest
    health_info: Optional[StudentHealthInfoRequest] = None
    save_as_draft: bool = False

class SaveDraftRequest(BaseModel):
    basic_info: Optional[dict] = None
    parent_info: Optional[dict] = None
    health_info: Optional[dict] = None
    current_step: int = 1

class ValidateNationalIdRequest(BaseModel):
    national_id: str

class ValidateParentPhoneRequest(BaseModel):
    phone: str

# ==================== Helper function to get engine ====================

def get_student_engine(db):
    """Get StudentManagementEngine instance"""
    from engines.student_management_engine import StudentManagementEngine
    return StudentManagementEngine(db)

# ==================== Routes ====================

def create_student_routes(db, get_current_user):
    """Create routes with database dependency"""
    
    engine = get_student_engine(db)
    
    # ==================== Options/Lookups ====================
    
    @router.get("/options/grades")
    async def get_grades(current_user: dict = Depends(get_current_user)):
        """Get available grades for the school"""
        tenant_id = current_user.get("tenant_id")
        if not tenant_id:
            raise HTTPException(status_code=400, detail="Tenant ID required")
        
        grades = await engine.get_grades(tenant_id)
        return {"grades": grades}
    
    @router.get("/options/sections")
    async def get_sections(
        grade_id: Optional[str] = Query(None),
        current_user: dict = Depends(get_current_user)
    ):
        """Get available sections for the school"""
        tenant_id = current_user.get("tenant_id")
        if not tenant_id:
            raise HTTPException(status_code=400, detail="Tenant ID required")
        
        sections = await engine.get_sections(tenant_id, grade_id)
        return {"sections": sections}
    
    @router.get("/options/nationalities")
    async def get_nationalities():
        """Get list of nationalities"""
        nationalities = await engine.get_nationalities()
        return {"nationalities": nationalities}
    
    @router.get("/options/blood-types")
    async def get_blood_types():
        """Get list of blood types"""
        blood_types = await engine.get_blood_types()
        return {"blood_types": blood_types}
    
    @router.get("/options/parent-relations")
    async def get_parent_relations():
        """Get list of parent relations"""
        relations = await engine.get_parent_relations()
        return {"relations": relations}
    
    # ==================== Validation ====================
    
    @router.post("/validate/national-id")
    async def validate_national_id(
        request: ValidateNationalIdRequest,
        current_user: dict = Depends(get_current_user)
    ):
        """Validate if national ID is unique"""
        tenant_id = current_user.get("tenant_id")
        if not tenant_id:
            raise HTTPException(status_code=400, detail="Tenant ID required")
        
        result = await engine.validate_national_id(request.national_id, tenant_id)
        return result
    
    @router.post("/validate/parent-phone")
    async def validate_parent_phone(
        request: ValidateParentPhoneRequest,
        current_user: dict = Depends(get_current_user)
    ):
        """Check if parent exists by phone number"""
        tenant_id = current_user.get("tenant_id")
        if not tenant_id:
            raise HTTPException(status_code=400, detail="Tenant ID required")
        
        result = await engine.validate_parent_phone(request.phone, tenant_id)
        return result
    
    # ==================== CRUD ====================
    
    @router.post("/create")
    async def create_student(
        request: CreateStudentFullRequest,
        current_user: dict = Depends(get_current_user)
    ):
        """Create a new student with full information"""
        tenant_id = current_user.get("tenant_id")
        if not tenant_id:
            raise HTTPException(status_code=400, detail="Tenant ID required")
        
        # Check permissions
        allowed_roles = ["platform_admin", "school_principal", "school_sub_admin"]
        if current_user.get("role") not in allowed_roles:
            raise HTTPException(status_code=403, detail="Permission denied")
        
        # Convert request to engine format
        from engines.student_management_engine import (
            CreateStudentRequest, 
            StudentBasicInfo, 
            ParentContactInfo,
            StudentHealthInfo,
            Gender as EngineGender,
            ParentRelation as EngineParentRelation
        )
        
        basic_info = StudentBasicInfo(
            full_name_ar=request.basic_info.full_name_ar,
            full_name_en=request.basic_info.full_name_en,
            national_id=request.basic_info.national_id,
            date_of_birth=request.basic_info.date_of_birth,
            gender=EngineGender(request.basic_info.gender.value),
            nationality=request.basic_info.nationality,
            grade_id=request.basic_info.grade_id,
            section_id=request.basic_info.section_id,
        )
        
        parent_info = ParentContactInfo(
            parent_name_ar=request.parent_info.parent_name_ar,
            parent_name_en=request.parent_info.parent_name_en,
            parent_national_id=request.parent_info.parent_national_id,
            parent_phone=request.parent_info.parent_phone,
            parent_email=request.parent_info.parent_email,
            parent_relation=EngineParentRelation(request.parent_info.parent_relation.value),
            emergency_contact=request.parent_info.emergency_contact,
            emergency_phone=request.parent_info.emergency_phone,
            address=request.parent_info.address,
        )
        
        health_info = None
        if request.health_info:
            health_info = StudentHealthInfo(
                blood_type=request.health_info.blood_type,
                has_chronic_conditions=request.health_info.has_chronic_conditions,
                chronic_conditions=request.health_info.chronic_conditions,
                has_allergies=request.health_info.has_allergies,
                allergies=request.health_info.allergies,
                has_disabilities=request.health_info.has_disabilities,
                disabilities=request.health_info.disabilities,
                current_medications=request.health_info.current_medications,
                requires_special_care=request.health_info.requires_special_care,
                special_care_notes=request.health_info.special_care_notes,
                emergency_medical_notes=request.health_info.emergency_medical_notes,
            )
        
        engine_request = CreateStudentRequest(
            basic_info=basic_info,
            parent_info=parent_info,
            health_info=health_info,
            save_as_draft=request.save_as_draft
        )
        
        result = await engine.create_student(
            engine_request,
            tenant_id,
            str(current_user.get("_id", current_user.get("id", "system")))
        )
        
        if not result.get("success"):
            raise HTTPException(
                status_code=400,
                detail=result.get("error", "Failed to create student")
            )
        
        return result
    
    @router.get("/")
    async def list_students(
        grade_id: Optional[str] = Query(None),
        section_id: Optional[str] = Query(None),
        search: Optional[str] = Query(None),
        skip: int = Query(0, ge=0),
        limit: int = Query(50, ge=1, le=100),
        current_user: dict = Depends(get_current_user)
    ):
        """List students with filters"""
        tenant_id = current_user.get("tenant_id")
        if not tenant_id:
            raise HTTPException(status_code=400, detail="Tenant ID required")
        
        result = await engine.list_students(
            tenant_id,
            grade_id=grade_id,
            section_id=section_id,
            search=search,
            skip=skip,
            limit=limit
        )
        
        return result
    
    @router.get("/{student_id}")
    async def get_student(
        student_id: str,
        current_user: dict = Depends(get_current_user)
    ):
        """Get student by ID"""
        tenant_id = current_user.get("tenant_id")
        if not tenant_id:
            raise HTTPException(status_code=400, detail="Tenant ID required")
        
        student = await engine.get_student(student_id, tenant_id)
        if not student:
            raise HTTPException(status_code=404, detail="Student not found")
        
        return student
    
    # ==================== Drafts ====================
    
    @router.post("/drafts")
    async def save_draft(
        request: SaveDraftRequest,
        draft_id: Optional[str] = Query(None),
        current_user: dict = Depends(get_current_user)
    ):
        """Save student creation draft"""
        tenant_id = current_user.get("tenant_id")
        if not tenant_id:
            raise HTTPException(status_code=400, detail="Tenant ID required")
        
        from engines.student_management_engine import StudentDraft
        
        draft = StudentDraft(
            basic_info=request.basic_info,
            parent_info=request.parent_info,
            health_info=request.health_info,
            current_step=request.current_step
        )
        
        result = await engine.save_draft(
            draft,
            tenant_id,
            str(current_user.get("_id", current_user.get("id", "system"))),
            draft_id
        )
        
        return result
    
    @router.get("/drafts/list")
    async def list_drafts(
        current_user: dict = Depends(get_current_user)
    ):
        """List all student drafts"""
        tenant_id = current_user.get("tenant_id")
        if not tenant_id:
            raise HTTPException(status_code=400, detail="Tenant ID required")
        
        drafts = await engine.list_drafts(
            tenant_id,
            created_by=str(current_user.get("_id", current_user.get("id")))
        )
        
        return {"drafts": drafts}
    
    @router.get("/drafts/{draft_id}")
    async def get_draft(
        draft_id: str,
        current_user: dict = Depends(get_current_user)
    ):
        """Get specific draft"""
        tenant_id = current_user.get("tenant_id")
        if not tenant_id:
            raise HTTPException(status_code=400, detail="Tenant ID required")
        
        draft = await engine.get_draft(draft_id, tenant_id)
        if not draft:
            raise HTTPException(status_code=404, detail="Draft not found")
        
        return draft
    
    @router.delete("/drafts/{draft_id}")
    async def delete_draft(
        draft_id: str,
        current_user: dict = Depends(get_current_user)
    ):
        """Delete a draft"""
        tenant_id = current_user.get("tenant_id")
        if not tenant_id:
            raise HTTPException(status_code=400, detail="Tenant ID required")
        
        result = await engine.delete_draft(draft_id, tenant_id)
        if not result:
            raise HTTPException(status_code=404, detail="Draft not found")
        
        return {"success": True, "message": "Draft deleted"}
    
    return router
