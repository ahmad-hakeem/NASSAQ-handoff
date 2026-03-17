"""
NASSAQ - Common Models
Shared models used across the application
"""
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Any
from datetime import datetime, timezone
import uuid


class StatusCheck(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    client_name: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class StatusCheckCreate(BaseModel):
    client_name: str


class PaginatedResponse(BaseModel):
    items: List[Any]
    total: int
    skip: int
    limit: int
    has_more: bool = False


class BulkOperationResult(BaseModel):
    success_count: int = 0
    failed_count: int = 0
    errors: List[dict] = []


class AuditLogEntry(BaseModel):
    id: str
    action: str
    action_by: str
    action_by_name: Optional[str] = None
    target_type: str
    target_id: str
    target_name: Optional[str] = None
    details: Optional[dict] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    tenant_id: Optional[str] = None
    timestamp: str


class MessageResponse(BaseModel):
    message: str
    message_ar: Optional[str] = None
    message_en: Optional[str] = None


class ErrorResponse(BaseModel):
    detail: str
    code: Optional[str] = None
    field: Optional[str] = None


class TimeSlot(BaseModel):
    id: str
    name: str
    name_en: Optional[str] = None
    start_time: str  # HH:MM format
    end_time: str
    order: int = 0
    is_break: bool = False
    school_id: Optional[str] = None
    is_active: bool = True


class TimeSlotCreate(BaseModel):
    name: str
    name_en: Optional[str] = None
    start_time: str
    end_time: str
    order: int = 0
    is_break: bool = False


class DayOfWeek(BaseModel):
    code: str  # SUN, MON, TUE, WED, THU, FRI, SAT
    name_ar: str
    name_en: str
    order: int
    is_working_day: bool = True
