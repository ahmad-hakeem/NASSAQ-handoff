"""
School Notification Routes - مسارات إشعارات المدرسة
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from enum import Enum
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/notifications", tags=["Notifications"])

class RecipientType(str, Enum):
    all_students = "all_students"
    all_teachers = "all_teachers"
    all_parents = "all_parents"
    grade_students = "grade_students"
    grade_parents = "grade_parents"
    class_students = "class_students"
    class_parents = "class_parents"
    specific_users = "specific_users"

class NotificationPriority(str, Enum):
    low = "low"
    normal = "normal"
    high = "high"
    urgent = "urgent"

class NotificationType(str, Enum):
    announcement = "announcement"
    reminder = "reminder"
    alert = "alert"
    event = "event"
    emergency = "emergency"
    circular = "circular"
    other = "other"
    circular_ack = "circular_ack"

class SendNotificationRequest(BaseModel):
    title_ar: str = Field(..., min_length=1)
    title_en: Optional[str] = None
    message_ar: str = Field(..., min_length=1)
    message_en: Optional[str] = None
    recipient_type: RecipientType
    recipient_filter: Optional[Dict[str, Any]] = None
    notification_type: NotificationType = NotificationType.announcement
    priority: NotificationPriority = NotificationPriority.normal
    send_push: bool = True
    send_sms: bool = False
    send_email: bool = False
    scheduled_at: Optional[str] = None

def get_notification_engine(db):
    from engines.school_notification_engine import SchoolNotificationEngine
    return SchoolNotificationEngine(db)

def create_notification_routes(db, get_current_user):
    engine = get_notification_engine(db)
    
    @router.get("/options/recipient-types")
    async def get_recipient_types():
        return {"types": await engine.get_recipient_types()}
    
    @router.get("/options/notification-types")
    async def get_notification_types():
        return {"types": await engine.get_notification_types()}
    
    @router.get("/options/priorities")
    async def get_priorities():
        return {"priorities": await engine.get_priorities()}
    
    @router.post("/send")
    async def send_notification(
        request: SendNotificationRequest,
        current_user: dict = Depends(get_current_user)
    ):
        tenant_id = current_user.get("tenant_id")
        if not tenant_id:
            raise HTTPException(status_code=400, detail="Tenant ID required")
        
        allowed_roles = ["platform_admin", "school_principal", "school_sub_admin", "school_admin"]
        if current_user.get("role") not in allowed_roles:
            raise HTTPException(status_code=403, detail="Permission denied")
        
        from engines.school_notification_engine import (
            SendNotificationRequest as EngineRequest,
            RecipientType as EngineRecipient,
            NotificationPriority as EnginePriority,
            NotificationType as EngineNotifType
        )
        
        engine_request = EngineRequest(
            title_ar=request.title_ar,
            title_en=request.title_en,
            message_ar=request.message_ar,
            message_en=request.message_en,
            recipient_type=EngineRecipient(request.recipient_type.value),
            recipient_filter=request.recipient_filter,
            notification_type=EngineNotifType(request.notification_type.value),
            priority=EnginePriority(request.priority.value),
            send_push=request.send_push,
            send_sms=request.send_sms,
            send_email=request.send_email,
            scheduled_at=request.scheduled_at,
        )
        
        result = await engine.send_notification(
            engine_request,
            tenant_id,
            str(current_user.get("_id", current_user.get("id", "system")))
        )
        
        if not result.get("success"):
            raise HTTPException(status_code=400, detail=result.get("error"))
        return result
    
    @router.get("/")
    async def list_notifications(
        notification_type: Optional[str] = Query(None),
        skip: int = Query(0, ge=0),
        limit: int = Query(50, ge=1, le=100),
        current_user: dict = Depends(get_current_user)
    ):
        tenant_id = current_user.get("tenant_id")
        if not tenant_id:
            raise HTTPException(status_code=400, detail="Tenant ID required")
        return await engine.list_notifications(tenant_id, notification_type, skip, limit)
    
    @router.get("/{notification_id}")
    async def get_notification(
        notification_id: str,
        current_user: dict = Depends(get_current_user)
    ):
        tenant_id = current_user.get("tenant_id")
        if not tenant_id:
            raise HTTPException(status_code=400, detail="Tenant ID required")
        result = await engine.get_notification(notification_id, tenant_id)
        if not result:
            raise HTTPException(status_code=404, detail="Notification not found")
        return result
    
    return router
