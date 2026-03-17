"""
NASSAQ - Dashboard Models
Dashboard and statistics related models
"""
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Any


class DashboardStats(BaseModel):
    total_schools: int = 0
    total_students: int = 0
    total_teachers: int = 0
    active_schools: int = 0
    pending_schools: int = 0
    suspended_schools: int = 0
    setup_schools: int = 0
    total_users: int = 0
    pending_requests: int = 0
    active_users: int = 0
    total_classes: int = 0
    total_subjects: int = 0
    total_operations: int = 0
    teachers_without_classes: int = 0
    incomplete_schedules: int = 0
    schools_without_principal: int = 0
    students_missing_data: int = 0
    teachers_without_rank: int = 0


class AIOperationResult(BaseModel):
    success: bool
    message: str
    message_en: str
    health_score: Optional[int] = None
    issues_found: int = 0
    recommendations: int = 0
    details: Optional[dict] = None


class HakimMessage(BaseModel):
    message: str
    context: Optional[str] = None
    user_role: Optional[str] = None
    tenant_id: Optional[str] = None


class HakimResponse(BaseModel):
    response: str
    suggestions: List[str] = []


class AlertItem(BaseModel):
    id: str
    type: str  # warning, error, info, success
    title: str
    title_ar: Optional[str] = None
    title_en: Optional[str] = None
    time: str
    time_ar: Optional[str] = None
    time_en: Optional[str] = None


class MetricValue(BaseModel):
    value: int
    change: Optional[str] = None
    changeType: Optional[str] = None  # up, down, same
    status: Optional[str] = None  # normal, warning, critical


class AttendanceBreakdown(BaseModel):
    present: int = 0
    absent: int = 0
    excused: int = 0
    total: int = 0


class SchoolDashboardData(BaseModel):
    metrics: dict
    attendance: dict
    interventions: dict
    alerts: List[AlertItem]


class PlatformActivityData(BaseModel):
    date: str
    active_users: int = 0
    new_users: int = 0
    operations: int = 0
