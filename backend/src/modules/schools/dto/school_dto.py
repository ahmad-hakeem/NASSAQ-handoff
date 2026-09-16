"""
NASSAQ - School Models & DTOs
All school/tenant-related Pydantic models for CRUD, info updates, status, and credentials.
"""
from pydantic import BaseModel, Field, ConfigDict, EmailStr, field_validator, model_validator
from typing import List, Optional, Union
from datetime import datetime
from src.common.dto.enums import SchoolStatus
from src.common.utils.school_type import normalize_school_type


def _normalize_school_type_field(cls, v):  # noqa: N805
    return normalize_school_type(v)


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
    logo_url: Optional[str] = None
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

    @model_validator(mode="after")
    def _principal_mobile_alias(self):
        if self.principal_mobile is not None and self.principal_phone is None:
            self.principal_phone = self.principal_mobile
        if self.principal_phone is not None:
            self.principal_mobile = self.principal_phone
        return self


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
    country: str = "SA"
    logo_url: Optional[str] = None
    status: SchoolStatus
    student_capacity: int = 500
    current_students: int = 0
    current_teachers: int = 0
    student_count: int = 0
    teacher_count: int = 0
    class_count: int = 0
    parent_count: int = 0
    created_at: Union[str, datetime]
    updated_at: Optional[Union[str, datetime]] = None
    school_type: Optional[str] = "public"
    stage: Optional[str] = "primary"
    language: Optional[str] = "ar"
    calendar_system: Optional[str] = "hijri_gregorian"
    educational_pathway: Optional[str] = None
    principal_name: Optional[str] = None
    principal_email: Optional[str] = None
    principal_phone: Optional[str] = None
    principal_mobile: Optional[str] = None
    entity_kind: str = "standard_school"
    can_preview_as_principal: bool = True
    preview_block_reason: Optional[str] = None
    setup_score: int = 0

    @model_validator(mode="after")
    def _principal_mobile_alias(self):
        if self.principal_mobile is not None and self.principal_phone is None:
            self.principal_phone = self.principal_mobile
        if self.principal_phone is not None:
            self.principal_mobile = self.principal_phone
        return self


class SchoolPaginatedResponse(BaseModel):
    model_config = ConfigDict(extra="ignore", from_attributes=True)
    schools: List[SchoolResponse]
    total: int
    page: int
    limit: int
    total_pages: int
    cities: Optional[List[str]] = None


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
    principal_phone: Optional[str] = None
    principal_mobile: Optional[str] = None
    educational_pathway: Optional[str] = None

    _normalize_school_type = field_validator("school_type", mode="before")(
        _normalize_school_type_field
    )

    @model_validator(mode="after")
    def _principal_mobile_alias(self):
        if self.principal_mobile is not None and self.principal_phone is None:
            self.principal_phone = self.principal_mobile
        if self.principal_phone is not None:
            self.principal_mobile = self.principal_phone
        return self


class SchoolInfoUpdate(BaseModel):
    name: Optional[str] = None
    name_ar: Optional[str] = None
    name_en: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    city: Optional[str] = None
    region: Optional[str] = None
    address: Optional[str] = None
    type: Optional[str] = None
    stage: Optional[str] = None
    principal_name: Optional[str] = None
    principal_phone: Optional[str] = None
    principal_mobile: Optional[str] = None
    educational_pathway: Optional[str] = None

    @field_validator("type", mode="before")
    @classmethod
    def _normalize_type(cls, v):
        return normalize_school_type(v)

    @model_validator(mode="after")
    def _principal_mobile_alias(self):
        if self.principal_mobile is not None and self.principal_phone is None:
            self.principal_phone = self.principal_mobile
        if self.principal_phone is not None:
            self.principal_mobile = self.principal_phone
        return self


class SchoolStatusChangeRequest(BaseModel):
    reason: Optional[str] = Field(default="إيقاف إداري مؤقت", description="سبب التغيير")


class SchoolCredentialsRequest(BaseModel):
    email: str = Field(..., min_length=5, description="البريد الإلكتروني لمدير المدرسة")
    name: Optional[str] = None
    password: Optional[str] = Field(None, min_length=8, description="كلمة المرور الجديدة (اختياري - يُولَّد تلقائياً إن لم تُحدَّد)")
