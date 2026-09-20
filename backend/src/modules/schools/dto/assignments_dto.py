"""
NASSAQ - Teacher Assignments DTOs
Pydantic models for teacher-class and teacher-subject assignments, academic hierarchy creation, and teaching load updates.
"""
from pydantic import BaseModel, Field
from typing import Optional, List


class TeacherClassAssignmentCreate(BaseModel):
    teacher_id: str
    class_id: str
    academic_year_id: Optional[str] = None
    subject_id: Optional[str] = None


class TeacherClassBulkUnassignTeacher(BaseModel):
    teacher_id: str = Field(..., min_length=1)


class TeacherClassBulkUnassignAll(BaseModel):
    pass


class TeacherClassAssignmentResponse(BaseModel):
    id: str
    teacher_id: str
    class_id: str
    school_id: str
    academic_year_id: Optional[str] = None
    teacher_name: Optional[str] = None
    class_name: Optional[str] = None
    created_at: Optional[str] = None


class TeacherSubjectAssignmentCreate(BaseModel):
    teacher_id: str = Field(..., min_length=1)
    subject_id: str = Field(..., min_length=1)


class TeachingLoadUpdate(BaseModel):
    teacher_id: str
    weekly_periods: int


class TeacherAvailability(BaseModel):
    teacher_id: str
    available_days: List[str] = []
    available_periods: Optional[List[int]] = None


class EducationalStageCreate(BaseModel):
    name: str
    name_en: Optional[str] = None
    order: int = 1


class GradeCreate(BaseModel):
    name: str
    name_en: Optional[str] = None
    stage_id: Optional[str] = None


class SectionCreate(BaseModel):
    name: str
    grade_id: Optional[str] = None
    class_id: Optional[str] = None


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
