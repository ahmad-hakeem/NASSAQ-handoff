"""
NASSAQ - System and School Settings DTOs
Pydantic models for general platform settings, maintenance, legal policies, contact info, security, and school timetable configuration.
"""
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict, Any


class GeneralSettings(BaseModel):
    """الإعدادات العامة"""
    platform_name: str = "نَسَّق"
    platform_name_en: str = "NASSAQ"
    browser_title: str = "نَسَّق | NASSAQ"
    default_language: str = "ar"  # ar or en
    date_system: str = "both"  # hijri, gregorian, both
    timezone: str = "Asia/Riyadh"


class MaintenanceSettings(BaseModel):
    """إعدادات الصيانة"""
    maintenance_mode: bool = False
    registration_open: bool = True
    maintenance_message_ar: str = "نحيطكم علمًا أن النظام يخضع حاليًا لأعمال صيانة وتحسينات تقنية."
    maintenance_message_en: str = "The system is currently undergoing maintenance."
    registration_closed_message_ar: str = "نود إبلاغكم بأن التسجيل في المنصة مغلق حاليًا."
    registration_closed_message_en: str = "Registration is currently closed."


class TermsVersion(BaseModel):
    """إصدار الشروط والأحكام"""
    id: str
    version_number: int
    content_ar: str
    content_en: str = ""
    created_at: str
    created_by: str
    created_by_name: str
    is_published: bool = False
    published_at: Optional[str] = None


class PrivacyVersion(BaseModel):
    """إصدار سياسة الخصوصية"""
    id: str
    version_number: int
    content_ar: str
    content_en: str = ""
    created_at: str
    created_by: str
    created_by_name: str
    is_published: bool = False
    published_at: Optional[str] = None


class ContactInfo(BaseModel):
    """بيانات التواصل"""
    email: str = ""
    phone: str = ""
    working_hours_ar: str = ""
    working_hours_en: str = ""
    address_ar: str = ""
    address_en: str = ""
    social_twitter: str = ""
    social_linkedin: str = ""
    social_instagram: str = ""
    social_facebook: str = ""
    social_youtube: str = ""


class SecuritySettings(BaseModel):
    """إعدادات الأمان"""
    model_config = ConfigDict(extra="forbid")

    session_duration_minutes: int = 60
    max_concurrent_sessions: int = 3
    min_password_length: int = 8
    require_uppercase: int = 1
    require_lowercase: int = 1
    require_numbers: int = 1
    require_special_chars: int = 1


class WorkDaysConfig(BaseModel):
    """إعدادات أيام العمل والأسبوع"""
    sunday: bool = True
    monday: bool = True
    tuesday: bool = True
    wednesday: bool = True
    thursday: bool = True
    friday: bool = False
    saturday: bool = False


class OfficialHoliday(BaseModel):
    """إجازة رسمية"""
    name: str
    start_date: str
    end_date: Optional[str] = None


class ExceptionDay(BaseModel):
    """يوم استثنائي"""
    date: str
    reason: str
    is_holiday: bool = True


class SchoolTiming(BaseModel):
    """توقيت اليوم الدراسي"""
    start: str = "07:00"
    end: str = "14:00"


class BreakPeriod(BaseModel):
    """فترة استراحة أو صلاة"""
    id: Optional[str] = None
    name: Optional[str] = None
    start: Optional[str] = None
    end: Optional[str] = None
    type: Optional[str] = None
    custom_type: Optional[str] = None
    duration: Optional[int] = None
    after_period: Optional[int] = None
    day: Optional[str] = None


class ActivityDay(BaseModel):
    """يوم نشاط مدرسي"""
    date: str
    name: Optional[str] = None
    notes: Optional[str] = None


class UpdatePeriodsRequest(BaseModel):
    """تحديث عدد الحصص اليومية"""
    periods_per_day: int


class SchoolSettingsResponse(BaseModel):
    """استجابة إعدادات المدرسة الشاملة"""
    school_info: dict
    work_days: dict
    official_holidays: List[dict]
    exception_days: List[dict]
    periods_per_day: int
    timing: dict
    breaks: List[dict]
    activity_days: List[dict]
    teaching_loads: dict
    teacher_availability: dict
    constraints: List[dict]
    educational_stages: List[dict]
    grades: List[dict]
    sections: List[dict]
    academic_terms: List[dict]
