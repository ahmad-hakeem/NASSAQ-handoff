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
import uuid, os, logging, json, random, re, io, base64
from enum import Enum

from engines.sql_utils import gd_find, gd_find_one, gd_insert, gd_insert_many, gd_update_one, gd_update_many, gd_count, gd_delete_one, gd_delete_many, gd_distinct, gd_upsert, _gd_aggregate
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
    sender_name_resolved = None
    if sender_id:
        sender_user = await gd_find_one(db.session, "users", {"id": sender_id})
        if sender_user:
            sender_name_resolved = sender_user.get("full_name", "")

    notification_doc = {
        "id": notification_id,
        "user_id": recipient_id,
        "title": title,
        "title_en": title_en,
        "message": message,
        "message_en": message_en,
        "type": notification_type,
        "priority": priority,
        "action_url": action_url,
        "related_entity": related_entity,
        "related_entity_id": related_entity_id,
        "sender_id": sender_id,
        "sender_name": sender_name_resolved,
        "tenant_id": school_id,
        "is_read": False,
        "read_at": None,
        "created_at": datetime.now(timezone.utc),
    }
    await gd_insert(db.session, "notifications", notification_doc)
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
    
    if notification.recipient_role and not notification.recipient_id:
        query = {"role": notification.recipient_role}
        tenant_id = current_user.get('tenant_id')
        if tenant_id:
            query['tenant_id'] = tenant_id
        role_users = await gd_find(db.session, "users", query, limit=1000)
        if not role_users:
            raise HTTPException(status_code=404, detail="لم يتم العثور على مستخدمين بهذا الدور")

        created_ids = []
        for role_user in role_users:
            notification_id = str(uuid.uuid4())
            notification_doc = {
                "id": notification_id,
                "user_id": role_user["id"],
                "title": notification.title,
                "message": notification.message,
                "type": notification.notification_type.value if notification.notification_type else None,
                "priority": notification.priority.value if notification.priority else "normal",
                "action_url": notification.action_url,
                "related_entity": notification.related_entity,
                "related_entity_id": notification.related_entity_id,
                "sender_id": current_user['id'],
                "sender_name": current_user.get('full_name', ''),
                "tenant_id": tenant_id,
                "is_read": False,
                "read_at": None,
                "created_at": datetime.now(timezone.utc),
            }
            await gd_insert(db.session, "notifications", notification_doc)
            created_ids.append(notification_id)

        return {"success": True, "notification_id": created_ids[0] if created_ids else None, "created_count": len(created_ids), "message": f"تم إرسال {len(created_ids)} إشعار بنجاح"}

    resolved_user_id = notification.recipient_id
    if resolved_user_id:
        user_exists = await gd_find_one(db.session, "users", {"id": resolved_user_id})
        if not user_exists:
            student = await gd_find_one(db.session, "students", {"id": resolved_user_id})
            if not student:
                student = await gd_find_one(db.session, "students", {"parent_id": resolved_user_id})
            if student:
                parent_user = None
                if student.get("parent_email"):
                    parent_user = await gd_find_one(db.session, "users", {"email": student["parent_email"], "role": "parent"})
                if not parent_user and student.get("parent_phone"):
                    parent_user = await gd_find_one(db.session, "users", {"phone": student["parent_phone"], "role": "parent"})
                if not parent_user and student.get("parent_name"):
                    parent_user = await gd_find_one(db.session, "users", {"full_name": student["parent_name"], "role": "parent"})
                if parent_user:
                    resolved_user_id = parent_user["id"]
                else:
                    raise HTTPException(status_code=404, detail="لم يتم العثور على حساب ولي الأمر")
            else:
                raise HTTPException(status_code=404, detail="المستخدم غير موجود")
    else:
        raise HTTPException(status_code=400, detail="يجب تحديد المستلم أو الدور")

    notification_id = str(uuid.uuid4())
    notification_doc = {
        "id": notification_id,
        "user_id": resolved_user_id,
        "title": notification.title,
        "message": notification.message,
        "type": notification.notification_type.value if notification.notification_type else None,
        "priority": notification.priority.value if notification.priority else "normal",
        "action_url": notification.action_url,
        "related_entity": notification.related_entity,
        "related_entity_id": notification.related_entity_id,
        "sender_id": current_user['id'],
        "sender_name": current_user.get('full_name', ''),
        "tenant_id": current_user.get('tenant_id'),
        "is_read": False,
        "read_at": None,
        "created_at": datetime.now(timezone.utc),
    }
    
    await gd_insert(db.session, "notifications", notification_doc)
    
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
        users = await gd_find(db.session, "users", query, limit=1000)
        recipient_ids.extend([u['id'] for u in users])
    
    # Remove duplicates
    recipient_ids = list(set(recipient_ids))
    
    created_count = 0
    for recipient_id in recipient_ids:
        notification_id = str(uuid.uuid4())
        notification_doc = {
            "id": notification_id,
            "user_id": recipient_id,
            "title": data.title,
            "message": data.message,
            "type": data.notification_type.value if data.notification_type else None,
            "priority": data.priority.value if data.priority else "normal",
            "action_url": data.action_url,
            "sender_id": current_user['id'],
            "sender_name": current_user.get('full_name', ''),
            "tenant_id": current_user.get('tenant_id'),
            "is_read": False,
            "read_at": None,
            "created_at": datetime.now(timezone.utc),
        }
        await gd_insert(db.session, "notifications", notification_doc)
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
    query = {"user_id": current_user['id']}

    if notification_type:
        query['type'] = notification_type
    if read_status is not None:
        query['is_read'] = read_status
    
    notifications = await gd_find(db.session, "notifications", query, order_by="created_at", desc_order=True, offset=skip, limit=limit)
    
    result = []
    for n in notifications:
        result.append(NotificationResponse(
            id=n['id'],
            title=n.get('title', ''),
            title_en=n.get('title_en'),
            message=n.get('message', ''),
            message_en=n.get('message_en'),
            notification_type=n.get('type', 'system'),
            priority=n.get('priority', 'normal'),
            related_entity=n.get('related_entity'),
            related_entity_id=n.get('related_entity_id'),
            action_url=n.get('action_url'),
            read_status=n.get('is_read', False),
            read_at=n.get('read_at'),
            created_at=n['created_at'],
            sender_name=n.get('sender_name')
        ))
    
    return result

@router.get("/notifications/unread-count")
async def get_unread_count(current_user: dict = Depends(get_current_user)):
    """Get count of unread notifications"""
    count = await gd_count(db.session, "notifications", {
        "user_id": current_user['id'],
        "is_read": False
    })
    return {"unread_count": count}

@router.put("/notifications/{notification_id}/read")
async def mark_notification_as_read(
    notification_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Mark a notification as read"""
    notification = await gd_find_one(db.session, "notifications", {"id": notification_id})
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    
    # Verify the notification belongs to the user
    if notification.get('user_id') != current_user['id']:
        raise HTTPException(status_code=403, detail="Not authorized to access this notification")
    
    await gd_update_one(db.session, "notifications", {"id": notification_id}, {
            "is_read": True,
            "read_at": datetime.now(timezone.utc)
        })
    
    return {"success": True, "message": "Notification marked as read"}

@router.put("/notifications/mark-all-read")
async def mark_all_notifications_as_read(current_user: dict = Depends(get_current_user)):
    """Mark all notifications as read for current user"""
    result = await gd_update_many(db.session, "notifications", {
            "user_id": current_user['id'],
            "is_read": False
        }, {
            "is_read": True,
            "read_at": datetime.now(timezone.utc)
        })
    
    return {"success": True, "marked_count": result}

@router.delete("/notifications/{notification_id}")
async def delete_notification(
    notification_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Delete a notification"""
    notification = await gd_find_one(db.session, "notifications", {"id": notification_id})
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    
    # Verify the notification belongs to the user or user is admin
    if notification.get('user_id') != current_user['id'] and current_user['role'] not in ['platform_admin', 'school_principal']:
        raise HTTPException(status_code=403, detail="Not authorized to delete this notification")
    
    await gd_delete_one(db.session, "notifications", {"id": notification_id})
    
    return {"success": True, "message": "Notification deleted"}

class CircularAckRequest(BaseModel):
    circularId: str
    userId: str

@router.post("/notifications/{notification_id}/acknowledge")
async def acknowledge_circular(
    notification_id: str,
    payload: CircularAckRequest,
    current_user: dict = Depends(get_current_user)
):
    """Acknowledge receipt of a Ministry Circular (تعميم).
    Triggers a circular_ack notification back to the original sender (Manager/Admin)."""
    if payload.circularId != notification_id or payload.userId != current_user['id']:
        raise HTTPException(status_code=400, detail="Mismatched circular or user identifier")

    original = await gd_find_one(db.session, "notifications", {"id": notification_id})
    if not original:
        raise HTTPException(status_code=404, detail="Circular not found")

    if original.get('type') != 'circular':
        raise HTTPException(status_code=400, detail="Notification is not a circular")

    if original.get('user_id') != current_user['id']:
        raise HTTPException(status_code=403, detail="Not authorized to acknowledge this circular")

    original_tenant = original.get('tenant_id')
    user_tenant = current_user.get('tenant_id')
    if original_tenant and user_tenant and original_tenant != user_tenant:
        raise HTTPException(status_code=403, detail="Cross-tenant acknowledgment not allowed")

    sender_id = original.get('sender_id')
    if not sender_id:
        raise HTTPException(status_code=400, detail="Original sender not found")

    teacher_name = current_user.get('full_name') or current_user.get('name') or ''
    original_title_ar = original.get('title') or ''
    original_title_en = original.get('title_en') or original_title_ar

    ack_title_ar = "تأكيد استلام تعميم"
    ack_title_en = "Circular Acknowledgement"
    ack_message_ar = f"المعلم {teacher_name} أكد استلام التعميم: {original_title_ar}"
    ack_message_en = f"Teacher {teacher_name} acknowledged the circular: {original_title_en}"

    await create_notification_internal(
        title=ack_title_ar,
        message=ack_message_ar,
        recipient_id=sender_id,
        notification_type="circular_ack",
        priority="medium",
        sender_id=current_user['id'],
        related_entity="notification",
        related_entity_id=notification_id,
        title_en=ack_title_en,
        message_en=ack_message_en,
        school_id=current_user.get('tenant_id'),
    )

    return {"success": True, "message": "Circular acknowledged"}

@router.get("/notifications/analytics")
async def get_notification_analytics(
    current_user: dict = Depends(get_current_user)
):
    """Get notification analytics (admin only)"""
    if current_user['role'] not in ['platform_admin', 'school_principal']:
        raise HTTPException(status_code=403, detail="Not authorized to view analytics")
    
    query = {}
    if current_user.get('tenant_id'):
        query['tenant_id'] = current_user['tenant_id']
    
    total = await gd_count(db.session, "notifications", query)
    
    read_query = {**query, "is_read": True}
    read_count = await gd_count(db.session, "notifications", read_query)
    
    unread_query = {**query, "is_read": False}
    unread_count = await gd_count(db.session, "notifications", unread_query)
    
    # By type
    by_type = {}
    for ntype in ["system", "attendance", "schedule", "assessment", "behaviour", "communication", "announcement"]:
        type_query = {**query, "type": ntype}
        by_type[ntype] = await gd_count(db.session, "notifications", type_query)
    
    # By priority
    by_priority = {}
    for priority in ["low", "medium", "high", "critical"]:
        priority_query = {**query, "priority": priority}
        by_priority[priority] = await gd_count(db.session, "notifications", priority_query)
    
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

    await gd_insert(db.session, "scheduled_notifications", scheduled_doc)
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

    notifications = await gd_find(db.session, "scheduled_notifications", query, order_by="scheduled_at", desc_order=False, limit=100)

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

    result = await gd_delete_one(db.session, "scheduled_notifications", query)
    if result == 0:
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

    await gd_upsert(db.session, "notification_preferences", {"user_id": current_user["id"]}, prefs)

    return {"success": True, "message": "تم حفظ تفضيلات الإشعارات"}


@router.get("/notifications/preferences")
async def get_notification_preferences(
    current_user: dict = Depends(get_current_user)
):
    """Get notification preferences for user"""
    prefs = await gd_find_one(db.session, "notification_preferences", {"user_id": current_user["id"]})
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

