"""
NASSAQ - School Models
All school/tenant-related Pydantic models
"""
from pydantic import BaseModel, Field, ConfigDict, EmailStr, field_validator
from typing import List, Optional
from src.common.dto.enums import SchoolStatus
from src.common.utils.school_type import normalize_school_type


class SchoolBase(BaseModel):
    name: str
    name_en: Optional[str] = None
    code: str
    email: EmailStr
    phone: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    region: Optional[str] = None
    country: str = "SA"
    logo_url: Optional[str] = None
    status: SchoolStatus = SchoolStatus.PENDING
    student_capacity: int = 0
    current_students: int = 0
    current_teachers: int = 0


def _normalize_school_type_field(cls, v):  # noqa: N805
    return normalize_school_type(v)


class SchoolCreate(BaseModel):
    name: str
    name_en: Optional[str] = None
    code: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    region: Optional[str] = None
    country: str = "SA"
    student_capacity: int = 500
    language: Optional[str] = "ar"
    calendar_system: Optional[str] = "hijri_gregorian"
    school_type: Optional[str] = "public"
    stage: Optional[str] = "primary"
    principal_name: Optional[str] = None
    principal_email: Optional[EmailStr] = None
    principal_phone: Optional[str] = None
    principal_mobile: Optional[str] = None
    educational_pathway: Optional[str] = None

    _normalize_school_type = field_validator("school_type", mode="before")(
        _normalize_school_type_field
    )


class SchoolResponse(BaseModel):
    model_config = ConfigDict(extra="ignore", from_attributes=True)
    id: str
    name: str
    name_en: Optional[str] = None
    code: str
    email: str
    phone: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    region: Optional[str] = None
    country: str
    logo_url: Optional[str] = None
    status: SchoolStatus
    student_capacity: int
    current_students: int
    current_teachers: int
    created_at: str
    entity_kind: str = "standard_school"
    can_preview_as_principal: bool = True
    preview_block_reason: Optional[str] = None


class SchoolUpdate(BaseModel):
    name: Optional[str] = None
    name_en: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    region: Optional[str] = None
    logo_url: Optional[str] = None
    student_capacity: Optional[int] = None
    language: Optional[str] = None
    calendar_system: Optional[str] = None
    school_type: Optional[str] = None
    stage: Optional[str] = None
    principal_mobile: Optional[str] = None
    educational_pathway: Optional[str] = None

    _normalize_school_type = field_validator("school_type", mode="before")(
        _normalize_school_type_field
    )
