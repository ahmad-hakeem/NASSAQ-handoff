"""
NASSAQ Route Module: Notification engine endpoints
Auto-consolidated during Phase 8 modularization.
"""
from fastapi import APIRouter, HTTPException, Depends, status, Header, Query, Body, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import Response
from starlette.responses import StreamingResponse
from pydantic import BaseModel, Field, ConfigDict, EmailStr, model_validator
from typing import List, Optional, Any, Dict
from datetime import datetime, timezone, timedelta
from bson_compat import ObjectId
import uuid, os, logging, json, random, re, io, base64
from enum import Enum

from dependencies import (
    db, get_current_user, require_roles, UserRole, SchoolStatus,
    hash_password, verify_password, create_access_token,
    JWT_SECRET, JWT_ALGORITHM, ACCESS_TOKEN_EXPIRE, security, logger,
    audit_engine, AuditAction, AuditSeverity,
    smart_scheduling_engine, TimetableRunStatus, TimetableStatus,
    ConflictType, ConflictSeverity, PreValidationResult, GenerationResult,
    hakim_engine, reporting_engine, export_engine, session_engine,
    REPORT_TYPES, generate_student_qr_code
)

router = APIRouter()



# ============== NOTIFICATION ENGINE ==============
# Data Models

class NotificationType(str, Enum):
    SYSTEM = "system"
    ATTENDANCE = "attendance"
    SCHEDULE = "schedule"
    ASSESSMENT = "assessment"
    BEHAVIOUR = "behaviour"
    COMMUNICATION = "communication"
    ANNOUNCEMENT = "announcement"

class NotificationPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class NotificationCreate(BaseModel):
    title: str
    title_en: Optional[str] = None
    message: str
    message_en: Optional[str] = None
    notification_type: NotificationType = NotificationType.SYSTEM
    priority: NotificationPriority = NotificationPriority.MEDIUM
    recipient_id: Optional[str] = None  # Single recipient
    recipient_role: Optional[str] = None  # Role-based (all users with this role)
    related_entity: Optional[str] = None  # e.g., "student", "class", "assessment"
    related_entity_id: Optional[str] = None
    action_url: Optional[str] = None  # URL to navigate when clicked

class NotificationResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    title: str
    title_en: Optional[str] = None
    message: str
    message_en: Optional[str] = None
    notification_type: str
    priority: str
    related_entity: Optional[str] = None
    related_entity_id: Optional[str] = None
    action_url: Optional[str] = None
    read_status: bool
    read_at: Optional[str] = None
    created_at: str
    sender_name: Optional[str] = None

class NotificationBulkCreate(BaseModel):
    title: str
    title_en: Optional[str] = None
    message: str
    message_en: Optional[str] = None
    notification_type: NotificationType = NotificationType.SYSTEM
    priority: NotificationPriority = NotificationPriority.MEDIUM
    recipient_ids: List[str] = []  # List of user IDs
    recipient_role: Optional[str] = None  # Send to all users with this role
    related_entity: Optional[str] = None
    related_entity_id: Optional[str] = None
    action_url: Optional[str] = None

# Helper function to create notification
async def create_notification_internal(
    title: str,
    message: str,
    recipient_id: str,
    notification_type: str = "system",
    priority: str = "medium",
    sender_id: Optional[str] = None,
    related_entity: Optional[str] = None,
    related_entity_id: Optional[str] = None,
    action_url: Optional[str] = None,
    title_en: Optional[str] = None,
    message_en: Optional[str] = None,
    school_id: Optional[str] = None
):
    """Internal helper to create notifications from other engines"""
    notification_id = str(uuid.uuid4())
    notification_doc = {
        "id": notification_id,
        "title": title,
        "title_en": title_en,
        "message": message,
        "message_en": message_en,
        "notification_type": notification_type,
        "priority": priority,
        "recipient_id": recipient_id,
        "sender_id": sender_id,
        "related_entity": related_entity,
        "related_entity_id": related_entity_id,
        "action_url": action_url,
        "school_id": school_id,
        "read_status": False,
        "read_at": None,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.notifications.insert_one(notification_doc)
    return notification_id

# Notification APIs

@router.post("/notifications")
async def create_notification(
    notification: NotificationCreate,
    current_user: dict = Depends(get_current_user)
):
    """Create a single notification"""
    if current_user['role'] not in ['platform_admin', 'school_principal', 'school_sub_admin', 'school_admin', 'teacher']:
        raise HTTPException(status_code=403, detail="Not authorized to create notifications")
    
    notification_id = str(uuid.uuid4())
    notification_doc = {
        "id": notification_id,
        "title": notification.title,
        "title_en": notification.title_en,
        "message": notification.message,
        "message_en": notification.message_en,
        "notification_type": notification.notification_type.value,
        "priority": notification.priority.value,
        "recipient_id": notification.recipient_id,
        "recipient_role": notification.recipient_role,
        "sender_id": current_user['id'],
        "related_entity": notification.related_entity,
        "related_entity_id": notification.related_entity_id,
        "action_url": notification.action_url,
        "school_id": current_user.get('tenant_id'),
        "read_status": False,
        "read_at": None,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.notifications.insert_one(notification_doc)
    
    return {"success": True, "notification_id": notification_id, "message": "Notification created successfully"}

@router.post("/notifications/bulk")
async def create_bulk_notifications(
    data: NotificationBulkCreate,
    current_user: dict = Depends(get_current_user)
):
    """Create notifications for multiple recipients or role-based"""
    if current_user['role'] not in ['platform_admin', 'school_principal', 'school_sub_admin', 'school_admin']:
        raise HTTPException(status_code=403, detail="Not authorized to create bulk notifications")
    
    recipient_ids = data.recipient_ids.copy()
    
    # If role-based, find all users with that role
    if data.recipient_role:
        query = {"role": data.recipient_role}
        if current_user.get('tenant_id'):
            query['tenant_id'] = current_user['tenant_id']
        users = await db.users.find(query, {"_id": 0, "id": 1}).to_list(1000)
        recipient_ids.extend([u['id'] for u in users])
    
    # Remove duplicates
    recipient_ids = list(set(recipient_ids))
    
    created_count = 0
    for recipient_id in recipient_ids:
        notification_id = str(uuid.uuid4())
        notification_doc = {
            "id": notification_id,
            "title": data.title,
            "title_en": data.title_en,
            "message": data.message,
            "message_en": data.message_en,
            "notification_type": data.notification_type.value,
            "priority": data.priority.value,
            "recipient_id": recipient_id,
            "recipient_role": data.recipient_role,
            "sender_id": current_user['id'],
            "related_entity": data.related_entity,
            "related_entity_id": data.related_entity_id,
            "action_url": data.action_url,
            "school_id": current_user.get('tenant_id'),
            "read_status": False,
            "read_at": None,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        await db.notifications.insert_one(notification_doc)
        created_count += 1
    
    return {"success": True, "created_count": created_count, "message": f"{created_count} notifications created"}

@router.get("/notifications", response_model=List[NotificationResponse])
async def get_my_notifications(
    notification_type: Optional[str] = None,
    read_status: Optional[bool] = None,
    limit: int = 50,
    skip: int = 0,
    current_user: dict = Depends(get_current_user)
):
    """Get notifications for current user"""
    tenant_id = current_user.get("tenant_id")
    query = {
        "$or": [
            {"recipient_id": current_user['id']},
            {"recipient_role": current_user['role']}
        ]
    }
    if tenant_id:
        query["school_id"] = tenant_id
    
    if notification_type:
        query['notification_type'] = notification_type
    if read_status is not None:
        query['read_status'] = read_status
    
    notifications = await db.notifications.find(
        query, 
        {"_id": 0}
    ).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
    
    result = []
    for n in notifications:
        sender_name = None
        if n.get('sender_id'):
            sender = await db.users.find_one({"id": n['sender_id']}, {"_id": 0, "full_name": 1})
            sender_name = sender.get('full_name') if sender else None
        
        result.append(NotificationResponse(
            id=n['id'],
            title=n['title'],
            title_en=n.get('title_en'),
            message=n['message'],
            message_en=n.get('message_en'),
            notification_type=n['notification_type'],
            priority=n['priority'],
            related_entity=n.get('related_entity'),
            related_entity_id=n.get('related_entity_id'),
            action_url=n.get('action_url'),
            read_status=n.get('read_status', False),
            read_at=n.get('read_at'),
            created_at=n['created_at'],
            sender_name=sender_name
        ))
    
    return result

@router.get("/notifications/unread-count")
async def get_unread_count(current_user: dict = Depends(get_current_user)):
    """Get count of unread notifications"""
    count = await db.notifications.count_documents({
        "$or": [
            {"recipient_id": current_user['id']},
            {"recipient_role": current_user['role']}
        ],
        "read_status": False
    })
    return {"unread_count": count}

@router.put("/notifications/{notification_id}/read")
async def mark_notification_as_read(
    notification_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Mark a notification as read"""
    notification = await db.notifications.find_one({"id": notification_id}, {"_id": 0})
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    
    # Verify the notification belongs to the user
    if notification.get('recipient_id') != current_user['id'] and notification.get('recipient_role') != current_user['role']:
        raise HTTPException(status_code=403, detail="Not authorized to access this notification")
    
    await db.notifications.update_one(
        {"id": notification_id},
        {"$set": {
            "read_status": True,
            "read_at": datetime.now(timezone.utc).isoformat()
        }}
    )
    
    return {"success": True, "message": "Notification marked as read"}

@router.put("/notifications/mark-all-read")
async def mark_all_notifications_as_read(current_user: dict = Depends(get_current_user)):
    """Mark all notifications as read for current user"""
    result = await db.notifications.update_many(
        {
            "$or": [
                {"recipient_id": current_user['id']},
                {"recipient_role": current_user['role']}
            ],
            "read_status": False
        },
        {"$set": {
            "read_status": True,
            "read_at": datetime.now(timezone.utc).isoformat()
        }}
    )
    
    return {"success": True, "marked_count": result.modified_count}

@router.delete("/notifications/{notification_id}")
async def delete_notification(
    notification_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Delete a notification"""
    notification = await db.notifications.find_one({"id": notification_id}, {"_id": 0})
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    
    # Verify the notification belongs to the user or user is admin
    if notification.get('recipient_id') != current_user['id'] and current_user['role'] not in ['platform_admin', 'school_principal']:
        raise HTTPException(status_code=403, detail="Not authorized to delete this notification")
    
    await db.notifications.delete_one({"id": notification_id})
    
    return {"success": True, "message": "Notification deleted"}

@router.get("/notifications/analytics")
async def get_notification_analytics(
    current_user: dict = Depends(get_current_user)
):
    """Get notification analytics (admin only)"""
    if current_user['role'] not in ['platform_admin', 'school_principal']:
        raise HTTPException(status_code=403, detail="Not authorized to view analytics")
    
    query = {}
    if current_user.get('tenant_id'):
        query['school_id'] = current_user['tenant_id']
    
    total = await db.notifications.count_documents(query)
    
    read_query = {**query, "read_status": True}
    read_count = await db.notifications.count_documents(read_query)
    
    unread_query = {**query, "read_status": False}
    unread_count = await db.notifications.count_documents(unread_query)
    
    # By type
    by_type = {}
    for ntype in ["system", "attendance", "schedule", "assessment", "behaviour", "communication", "announcement"]:
        type_query = {**query, "notification_type": ntype}
        by_type[ntype] = await db.notifications.count_documents(type_query)
    
    # By priority
    by_priority = {}
    for priority in ["low", "medium", "high", "critical"]:
        priority_query = {**query, "priority": priority}
        by_priority[priority] = await db.notifications.count_documents(priority_query)
    
    read_rate = round((read_count / total) * 100, 2) if total > 0 else 0
    
    return {
        "total_notifications": total,
        "read_count": read_count,
        "unread_count": unread_count,
        "read_rate": read_rate,
        "by_type": by_type,
        "by_priority": by_priority
    }


@router.post("/notifications/schedule")
async def schedule_notification(
    data: dict = Body(...),
    current_user: dict = Depends(get_current_user)
):
    """Schedule a notification for future delivery"""
    if current_user['role'] not in ['platform_admin', 'school_principal', 'school_sub_admin', 'school_admin']:
        raise HTTPException(status_code=403, detail="غير مصرح")

    schedule_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    tenant_id = current_user.get("tenant_id")

    scheduled_doc = {
        "id": schedule_id,
        "title": data.get("title"),
        "title_en": data.get("title_en"),
        "message": data.get("message"),
        "message_en": data.get("message_en"),
        "notification_type": data.get("notification_type", "announcement"),
        "priority": data.get("priority", "medium"),
        "recipient_ids": data.get("recipient_ids", []),
        "recipient_role": data.get("recipient_role"),
        "scheduled_at": data.get("scheduled_at"),
        "is_sent": False,
        "school_id": tenant_id,
        "created_by": current_user["id"],
        "created_at": now
    }

    await db.scheduled_notifications.insert_one(scheduled_doc)
    scheduled_doc.pop("_id", None)
    return {"success": True, "schedule_id": schedule_id, "message": "تم جدولة الإشعار بنجاح"}


@router.get("/notifications/scheduled")
async def get_scheduled_notifications(
    current_user: dict = Depends(get_current_user)
):
    """Get scheduled notifications"""
    if current_user['role'] not in ['platform_admin', 'school_principal', 'school_sub_admin', 'school_admin']:
        raise HTTPException(status_code=403, detail="غير مصرح")

    tenant_id = current_user.get("tenant_id")
    query = {"is_sent": False}
    if tenant_id:
        query["school_id"] = tenant_id

    notifications = await db.scheduled_notifications.find(
        query, {"_id": 0}
    ).sort("scheduled_at", 1).to_list(100)

    return {"scheduled": notifications, "total": len(notifications)}


@router.delete("/notifications/scheduled/{schedule_id}")
async def cancel_scheduled_notification(
    schedule_id: str,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN]))
):
    """Cancel a scheduled notification"""
    tenant_id = current_user.get("tenant_id")
    query = {"id": schedule_id}
    if tenant_id:
        query["school_id"] = tenant_id

    result = await db.scheduled_notifications.delete_one(query)
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="الإشعار المجدول غير موجود")
    return {"success": True, "message": "تم إلغاء الإشعار المجدول"}


@router.post("/notifications/preferences")
async def set_notification_preferences(
    data: dict = Body(...),
    current_user: dict = Depends(get_current_user)
):
    """Set notification preferences for user"""
    prefs = {
        "user_id": current_user["id"],
        "school_id": current_user.get("tenant_id"),
        "email_enabled": data.get("email_enabled", True),
        "push_enabled": data.get("push_enabled", True),
        "sms_enabled": data.get("sms_enabled", False),
        "quiet_hours_start": data.get("quiet_hours_start"),
        "quiet_hours_end": data.get("quiet_hours_end"),
        "disabled_types": data.get("disabled_types", []),
        "updated_at": datetime.now(timezone.utc).isoformat()
    }

    await db.notification_preferences.update_one(
        {"user_id": current_user["id"]},
        {"$set": prefs},
        upsert=True
    )

    return {"success": True, "message": "تم حفظ تفضيلات الإشعارات"}


@router.get("/notifications/preferences")
async def get_notification_preferences(
    current_user: dict = Depends(get_current_user)
):
    """Get notification preferences for user"""
    prefs = await db.notification_preferences.find_one(
        {"user_id": current_user["id"]}, {"_id": 0}
    )
    if not prefs:
        prefs = {
            "user_id": current_user["id"],
            "email_enabled": True,
            "push_enabled": True,
            "sms_enabled": False,
            "quiet_hours_start": None,
            "quiet_hours_end": None,
            "disabled_types": [],
            "is_default": True
        }
    return prefs

