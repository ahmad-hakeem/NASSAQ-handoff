"""
NASSAQ - Registration Models
Registration requests and related models
"""
from pydantic import BaseModel, Field, ConfigDict, EmailStr
from typing import List, Optional
from .enums import RegistrationStatus


class RegistrationRequestBase(BaseModel):
    # School Data
    school_name: str
    school_name_en: Optional[str] = None
    school_type: str = "public"  # public, private, international
    education_level: str = "primary"  # nursery, kindergarten, primary, middle, high
    region: str
    city: str
    address: Optional[str] = None
    postal_code: Optional[str] = None
    
    # Principal Data
    principal_name: str
    principal_email: EmailStr
    principal_phone: str
    
    # License Data
    education_license_number: Optional[str] = None
    commercial_registration: Optional[str] = None
    
    # Additional
    student_count: int = 0
    teacher_count: int = 0
    notes: Optional[str] = None


class RegistrationRequestCreate(RegistrationRequestBase):
    pass


class RegistrationRequestResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    school_name: str
    school_name_en: Optional[str] = None
    school_type: str
    education_level: str
    region: str
    city: str
    address: Optional[str] = None
    postal_code: Optional[str] = None
    
    principal_name: str
    principal_email: str
    principal_phone: str
    
    education_license_number: Optional[str] = None
    commercial_registration: Optional[str] = None
    
    student_count: int = 0
    teacher_count: int = 0
    notes: Optional[str] = None
    
    status: RegistrationStatus
    rejection_reason: Optional[str] = None
    additional_info_request: Optional[str] = None
    assigned_to: Optional[str] = None
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[str] = None
    
    created_at: str
    updated_at: str


class RegistrationApproval(BaseModel):
    generate_credentials: bool = True
    custom_school_code: Optional[str] = None
    notes: Optional[str] = None


class RegistrationRejection(BaseModel):
    reason: str
    notes: Optional[str] = None


class RegistrationMoreInfo(BaseModel):
    request_message: str
    fields_required: List[str] = []


class TeacherRegistrationRequest(BaseModel):
    full_name: str
    full_name_en: Optional[str] = None
    email: EmailStr
    phone: str
    national_id: Optional[str] = None
    gender: str  # male, female
    date_of_birth: Optional[str] = None
    nationality: str = "SA"
    
    # Professional Info
    specialization: str
    qualification: str
    years_of_experience: int = 0
    current_school: Optional[str] = None
    
    # Documents
    cv_url: Optional[str] = None
    certificates_urls: List[str] = []
    
    # Target Schools (can apply to multiple)
    target_regions: List[str] = []
    target_school_types: List[str] = []  # public, private
    
    notes: Optional[str] = None
