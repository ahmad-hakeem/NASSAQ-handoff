"""
NASSAQ - Constraints & Duties DTOs
Pydantic models for timetable hard/soft constraints, custom constraints, patterns, and non-teaching duties.
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any


class AdminConstraint(BaseModel):
    id: Optional[str] = None
    type: str
    teacher_id: Optional[str] = None
    day: Optional[str] = None
    period: Optional[int] = None
    description: Optional[str] = None


class SoftConstraintToggleRequest(BaseModel):
    is_active: Optional[bool] = None
    weight: Optional[int] = Field(None, ge=1, le=10)
    target_subject_ids: Optional[List[str]] = None


class HardConstraintToggleRequest(BaseModel):
    is_active: bool


class CustomSoftConstraintCreate(BaseModel):
    name_ar: str = Field(..., min_length=1)
    description_ar: Optional[str] = ""
    pattern: Optional[str] = ""
    pattern_code: Optional[str] = "custom"
    weight: int = Field(5, ge=1, le=10)
    target_subject_ids: Optional[List[str]] = []
    applies_to: Optional[str] = "school"


class CustomSoftConstraintUpdate(BaseModel):
    name_ar: Optional[str] = None
    description_ar: Optional[str] = None
    pattern: Optional[str] = None
    pattern_code: Optional[str] = None
    weight: Optional[int] = Field(None, ge=1, le=10)
    target_subject_ids: Optional[List[str]] = None
    applies_to: Optional[str] = None
    is_active: Optional[bool] = None


class ConstraintPatternCreate(BaseModel):
    name_ar: str = Field(..., min_length=1)
    name_en: Optional[str] = ""
    description_ar: Optional[str] = ""
    category: Optional[str] = "distribution"
    template: Optional[dict] = {}


class OtherDutyCreate(BaseModel):
    teacher_id: str = Field(..., min_length=1)
    duty_name: str = Field(..., min_length=1)
    teacher_name: Optional[str] = ""
    equivalent_periods: int = Field(1, ge=0)
    notes: Optional[str] = ""


class OtherDutyUpdate(BaseModel):
    duty_name: Optional[str] = None
    equivalent_periods: Optional[int] = Field(None, ge=0)
    notes: Optional[str] = None


class WorkloadOverrideRequest(BaseModel):
    weekly_periods: int = Field(..., ge=0)
    reason: Optional[str] = ""
