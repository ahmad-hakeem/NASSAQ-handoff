"""
NASSAQ - Academic Models
Teachers, Students, Classes, Subjects related models
"""
from pydantic import BaseModel, Field, ConfigDict, EmailStr
from typing import List, Optional


class TeacherBase(BaseModel):
    full_name: str
    full_name_en: Optional[str] = None
    email: EmailStr
    phone: Optional[str] = None
    school_id: str
    specialization: str
    years_of_experience: int = 0
    qualification: Optional[str] = None
    gender: Optional[str] = None


class TeacherCreate(TeacherBase):
    pass


class TeacherResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    full_name: str
    full_name_en: Optional[str] = None
    email: str
    phone: Optional[str] = None
    school_id: str
    specialization: str
    years_of_experience: int
    qualification: Optional[str] = None
    gender: Optional[str] = None
    is_active: bool = True
    created_at: str


class StudentBase(BaseModel):
    full_name: str
    full_name_en: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    school_id: str
    class_id: Optional[str] = None
    student_number: str
    date_of_birth: Optional[str] = None
    gender: Optional[str] = None
    parent_phone: Optional[str] = None
    parent_name: Optional[str] = None


class StudentCreate(StudentBase):
    pass


class StudentResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    full_name: str
    full_name_en: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    school_id: str
    class_id: Optional[str] = None
    class_name: Optional[str] = None
    student_number: str
    date_of_birth: Optional[str] = None
    gender: Optional[str] = None
    parent_phone: Optional[str] = None
    parent_name: Optional[str] = None
    is_active: bool = True
    created_at: str


class ClassBase(BaseModel):
    name: str
    name_en: Optional[str] = None
    school_id: str
    grade_level: str
    section: Optional[str] = None
    capacity: int = 30
    homeroom_teacher_id: Optional[str] = None


class ClassCreate(ClassBase):
    pass


class ClassResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    name: str
    name_en: Optional[str] = None
    school_id: str
    grade_level: str
    section: Optional[str] = None
    capacity: int
    current_students: int = 0
    homeroom_teacher_id: Optional[str] = None
    homeroom_teacher_name: Optional[str] = None
    is_active: bool = True
    created_at: str


class SubjectBase(BaseModel):
    name: str
    name_en: Optional[str] = None
    code: str
    description: Optional[str] = None


class SubjectCreate(BaseModel):
    name_ar: str
    name_en: Optional[str] = None
    code: str
    category: str = "core"
    default_periods: int = 4
    stages: List[str] = []


class SubjectResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    name: str
    name_en: Optional[str] = None
    code: str
    description: Optional[str] = None
    is_active: bool = True
    created_at: str


class TeacherAssignment(BaseModel):
    teacher_id: str
    subject_id: str
    class_id: str
    periods_per_week: int = 4
