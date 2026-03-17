"""
NASSAQ - Communication Routes
Communication and messaging endpoints
"""
from fastapi import APIRouter, HTTPException, Depends
from typing import Optional, List
from datetime import datetime, timezone
from pydantic import BaseModel
import uuid
import logging

logger = logging.getLogger("nassaq.communication_routes")


class MessageCreate(BaseModel):
    title: str
    content: str
    audience: str  # all, teachers, students, parents, custom
    audience_ids: Optional[List[str]] = []
    scheduled_at: Optional[str] = None
    channels: List[str] = ["in_app"]  # in_app, email, sms


class MessageResponse(BaseModel):
    id: str
    title: str
    content: str
    audience: str
    status: str  # draft, scheduled, sent
    sent_count: int
    created_at: str
    scheduled_at: Optional[str] = None
    sent_at: Optional[str] = None


def create_communication_routes(db, get_current_user, require_roles, UserRole):
    """Create communication router"""
    router = APIRouter(prefix="/communication", tags=["Communication"])
    
    @router.get("/stats")
    async def get_communication_stats(
        current_user: dict = Depends(get_current_user)
    ):
        """Get communication statistics"""
        school_id = current_user.get("tenant_id")
        
        query = {}
        if school_id:
            query["school_id"] = school_id
        
        # Count messages
        total_sent = await db.messages.count_documents({**query, "status": "sent"})
        total_scheduled = await db.messages.count_documents({**query, "status": "scheduled"})
        total_drafts = await db.messages.count_documents({**query, "status": "draft"})
        
        # Count templates
        total_templates = await db.message_templates.count_documents(query)
        
        return {
            "sent": total_sent,
            "scheduled": total_scheduled,
            "drafts": total_drafts,
            "templates": total_templates
        }
    
    @router.post("")
    async def send_message(
        message: MessageCreate,
        current_user: dict = Depends(require_roles([UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN]))
    ):
        """Send or schedule a message"""
        school_id = current_user.get("tenant_id")
        
        now = datetime.now(timezone.utc).isoformat()
        message_id = str(uuid.uuid4())
        
        # Determine status
        status = "sent"
        if message.scheduled_at:
            status = "scheduled"
        
        # Count recipients
        recipient_count = 0
        if message.audience == "all":
            recipient_count = await db.users.count_documents({"tenant_id": school_id}) if school_id else await db.users.count_documents({})
        elif message.audience == "teachers":
            recipient_count = await db.teachers.count_documents({"school_id": school_id}) if school_id else await db.teachers.count_documents({})
        elif message.audience == "students":
            recipient_count = await db.students.count_documents({"school_id": school_id}) if school_id else await db.students.count_documents({})
        elif message.audience == "parents":
            recipient_count = await db.users.count_documents({"role": "parent", "tenant_id": school_id}) if school_id else await db.users.count_documents({"role": "parent"})
        elif message.audience == "custom":
            recipient_count = len(message.audience_ids)
        
        message_doc = {
            "id": message_id,
            "title": message.title,
            "content": message.content,
            "audience": message.audience,
            "audience_ids": message.audience_ids,
            "channels": message.channels,
            "status": status,
            "sent_count": recipient_count if status == "sent" else 0,
            "recipient_count": recipient_count,
            "school_id": school_id,
            "created_by": current_user["id"],
            "created_at": now,
            "scheduled_at": message.scheduled_at,
            "sent_at": now if status == "sent" else None
        }
        
        await db.messages.insert_one(message_doc)
        
        # Create notifications for recipients if sent immediately
        if status == "sent":
            # Create in-app notifications
            notification_doc = {
                "id": str(uuid.uuid4()),
                "message_id": message_id,
                "title": message.title,
                "content": message.content,
                "type": "announcement",
                "school_id": school_id,
                "audience": message.audience,
                "created_at": now,
                "read_by": []
            }
            await db.notifications.insert_one(notification_doc)
        
        return {
            "message": "تم إرسال الرسالة بنجاح" if status == "sent" else "تمت جدولة الرسالة بنجاح",
            "id": message_id,
            "status": status,
            "recipient_count": recipient_count
        }
    
    @router.get("")
    async def get_messages(
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 20,
        current_user: dict = Depends(get_current_user)
    ):
        """Get list of messages"""
        school_id = current_user.get("tenant_id")
        
        query = {}
        if school_id:
            query["school_id"] = school_id
        if status:
            query["status"] = status
        
        messages = await db.messages.find(
            query,
            {"_id": 0}
        ).sort("created_at", -1).skip(skip).limit(limit).to_list(length=limit)
        
        total = await db.messages.count_documents(query)
        
        return {
            "messages": messages,
            "total": total,
            "skip": skip,
            "limit": limit
        }
    
    @router.get("/templates")
    async def get_message_templates(
        current_user: dict = Depends(get_current_user)
    ):
        """Get message templates"""
        school_id = current_user.get("tenant_id")
        
        # Default templates if none exist
        default_templates = [
            {
                "id": "1",
                "name": "إشعار عام",
                "name_en": "General Announcement",
                "content_template": "تحية طيبة،\n\n{message}\n\nمع تحياتنا،\nإدارة المدرسة",
                "icon": "bell"
            },
            {
                "id": "2",
                "name": "تذكير بموعد",
                "name_en": "Event Reminder",
                "content_template": "تذكير: {event_name}\nالتاريخ: {date}\nالوقت: {time}\n\nيرجى الحضور في الموعد المحدد.",
                "icon": "clock"
            },
            {
                "id": "3",
                "name": "تحديث النظام",
                "name_en": "System Update",
                "content_template": "عزيزي المستخدم،\n\nنود إعلامكم بتحديث جديد في النظام:\n{update_details}\n\nشكراً لتعاونكم.",
                "icon": "refresh"
            },
            {
                "id": "4",
                "name": "طلب معلومات",
                "name_en": "Information Request",
                "content_template": "السلام عليكم،\n\nنرجو منكم تزويدنا بالمعلومات التالية:\n{required_info}\n\nوذلك في موعد أقصاه {deadline}.",
                "icon": "mail"
            }
        ]
        
        query = {}
        if school_id:
            query["school_id"] = school_id
        
        templates = await db.message_templates.find(query, {"_id": 0}).to_list(100)
        
        if not templates:
            return default_templates
        
        return templates
    
    @router.get("/audience")
    async def get_audience_stats(
        current_user: dict = Depends(get_current_user)
    ):
        """Get audience statistics for messaging"""
        school_id = current_user.get("tenant_id")
        
        if school_id:
            teachers = await db.teachers.count_documents({"school_id": school_id, "is_active": True})
            students = await db.students.count_documents({"school_id": school_id, "is_active": True})
            parents = await db.users.count_documents({"role": "parent", "tenant_id": school_id, "is_active": True})
            total = teachers + students + parents
        else:
            # Platform-wide for admins
            total = await db.users.count_documents({"is_active": True})
            teachers = await db.teachers.count_documents({"is_active": True})
            students = await db.students.count_documents({"is_active": True})
            parents = await db.users.count_documents({"role": "parent", "is_active": True})
        
        return [
            {"id": "all", "name": "الجميع", "name_en": "Everyone", "count": total, "icon": "users"},
            {"id": "teachers", "name": "المعلمين", "name_en": "Teachers", "count": teachers, "icon": "user-check"},
            {"id": "students", "name": "الطلاب", "name_en": "Students", "count": students, "icon": "graduation-cap"},
            {"id": "parents", "name": "أولياء الأمور", "name_en": "Parents", "count": parents, "icon": "users"}
        ]
    
    @router.get("/audience-counts")
    async def get_audience_counts(
        current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))
    ):
        """Get audience counts for broadcast messaging"""
        all_users = await db.users.count_documents({"is_active": True})
        schools = await db.schools.count_documents({})
        teachers = await db.users.count_documents({"role": {"$in": ["teacher", "independent_teacher"]}, "is_active": True})
        students = await db.users.count_documents({"role": "student", "is_active": True})
        principals = await db.users.count_documents({"role": "school_principal", "is_active": True})
        parents = await db.users.count_documents({"role": "parent", "is_active": True})
        
        return {
            "all": all_users,
            "schools": schools,
            "teachers": teachers,
            "students": students,
            "principals": principals,
            "parents": parents
        }
    
    @router.get("/scheduled")
    async def get_scheduled_messages(
        current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))
    ):
        """Get scheduled messages"""
        messages = await db.messages.find(
            {"status": "scheduled"}
        ).sort("scheduled_at", 1).to_list(50)
        
        return {
            "messages": [
                {
                    "id": str(m.get("id", m.get("_id"))),
                    "title": m.get("title", ""),
                    "message": m.get("content", ""),
                    "target_audience": m.get("audience", "all"),
                    "scheduled_at": m.get("scheduled_at", ""),
                    "status": m.get("status", "scheduled"),
                    "created_at": m.get("created_at", ""),
                }
                for m in messages
            ],
            "total": len(messages)
        }
    
    @router.get("/sent")
    async def get_sent_messages(
        current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))
    ):
        """Get sent messages history"""
        messages = await db.messages.find(
            {"status": "sent"}
        ).sort("sent_at", -1).limit(50).to_list(50)
        
        return {
            "messages": [
                {
                    "id": str(m.get("id", m.get("_id"))),
                    "title": m.get("title", ""),
                    "message": m.get("content", "")[:100] + "..." if len(m.get("content", "")) > 100 else m.get("content", ""),
                    "target_audience": m.get("audience", "all"),
                    "status": m.get("status", "sent"),
                    "sent_at": m.get("sent_at", ""),
                    "sent_by_name": m.get("sent_by_name", ""),
                }
                for m in messages
            ],
            "total": len(messages)
        }
    
    @router.post("/broadcast")
    async def send_broadcast_message(
        message: MessageCreate,
        current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))
    ):
        """Send broadcast message to all users"""
        now = datetime.now(timezone.utc).isoformat()
        message_id = str(uuid.uuid4())
        
        # Count recipients
        recipient_count = 0
        if message.audience == "all":
            recipient_count = await db.users.count_documents({"is_active": True})
        elif message.audience == "teachers":
            recipient_count = await db.users.count_documents({"role": {"$in": ["teacher", "independent_teacher"]}, "is_active": True})
        elif message.audience == "students":
            recipient_count = await db.users.count_documents({"role": "student", "is_active": True})
        elif message.audience == "schools":
            recipient_count = await db.users.count_documents({"role": "school_principal", "is_active": True})
        
        message_doc = {
            "id": message_id,
            "title": message.title,
            "content": message.content,
            "audience": message.audience,
            "channels": message.channels,
            "status": "sent",
            "sent_count": recipient_count,
            "created_at": now,
            "sent_at": now,
            "sent_by": current_user.get("id"),
            "sent_by_name": current_user.get("full_name", "")
        }
        
        await db.messages.insert_one(message_doc)
        
        # Create notifications for recipients (simplified)
        # In production, this should be a background task
        
        return {
            "success": True,
            "message_id": message_id,
            "recipients_count": recipient_count,
            "message": f"تم إرسال الرسالة إلى {recipient_count} مستخدم"
        }
    
    @router.get("/received")
    async def get_received_messages(
        current_user: dict = Depends(get_current_user)
    ):
        """Get received messages for current user"""
        user_id = current_user.get("id")
        user_role = current_user.get("role")
        school_id = current_user.get("tenant_id")
        
        # Build query based on user's role and school
        query = {"status": "sent"}
        
        if school_id:
            query["$or"] = [
                {"school_id": school_id},
                {"school_id": None}  # Platform-wide messages
            ]
        
        # Filter by audience
        audience_filter = ["all"]
        if user_role in ["teacher", "independent_teacher", "school_teacher"]:
            audience_filter.append("teachers")
        elif user_role == "student":
            audience_filter.append("students")
        elif user_role == "parent":
            audience_filter.append("parents")
        
        query["audience"] = {"$in": audience_filter}
        
        messages = await db.messages.find(query, {"_id": 0}).sort("sent_at", -1).to_list(50)
        
        # Add read status
        for msg in messages:
            read_by = msg.get("read_by", [])
            msg["is_read"] = user_id in read_by
        
        return {
            "messages": messages,
            "total": len(messages),
            "unread_count": len([m for m in messages if not m.get("is_read")])
        }
    
    @router.put("/{message_id}/read")
    async def mark_message_read(
        message_id: str,
        current_user: dict = Depends(get_current_user)
    ):
        """Mark message as read"""
        user_id = current_user.get("id")
        
        await db.messages.update_one(
            {"id": message_id},
            {"$addToSet": {"read_by": user_id}}
        )
        
        return {"success": True, "message": "تم تعيين الرسالة كمقروءة"}
    
    @router.put("/{message_id}")
    async def update_scheduled_message(
        message_id: str,
        data: dict,
        current_user: dict = Depends(require_roles([UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN]))
    ):
        """Update a scheduled message"""
        # Find the message
        message = await db.messages.find_one({"id": message_id})
        if not message:
            raise HTTPException(status_code=404, detail="الرسالة غير موجودة")
        
        if message.get("status") != "scheduled":
            raise HTTPException(status_code=400, detail="يمكن تعديل الرسائل المجدولة فقط")
        
        # Update allowed fields
        update_fields = {}
        if "title" in data:
            update_fields["title"] = data["title"]
        if "content" in data:
            update_fields["content"] = data["content"]
        if "audience" in data:
            update_fields["audience"] = data["audience"]
        if "scheduled_at" in data:
            update_fields["scheduled_at"] = data["scheduled_at"]
        
        update_fields["updated_at"] = datetime.now(timezone.utc).isoformat()
        
        await db.messages.update_one({"id": message_id}, {"$set": update_fields})
        
        return {"success": True, "message": "تم تحديث الرسالة المجدولة"}
    
    @router.post("/{message_id}/send-now")
    async def send_scheduled_message_now(
        message_id: str,
        current_user: dict = Depends(require_roles([UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN]))
    ):
        """Send a scheduled message immediately"""
        # Find the message
        message = await db.messages.find_one({"id": message_id})
        if not message:
            raise HTTPException(status_code=404, detail="الرسالة غير موجودة")
        
        if message.get("status") != "scheduled":
            raise HTTPException(status_code=400, detail="هذه الرسالة ليست مجدولة")
        
        now = datetime.now(timezone.utc).isoformat()
        
        # Update status to sent
        await db.messages.update_one(
            {"id": message_id},
            {"$set": {
                "status": "sent",
                "sent_at": now,
                "sent_count": message.get("recipient_count", 0)
            }}
        )
        
        # Create notification
        notification_doc = {
            "id": str(uuid.uuid4()),
            "message_id": message_id,
            "title": message.get("title"),
            "content": message.get("content"),
            "type": "announcement",
            "school_id": message.get("school_id"),
            "audience": message.get("audience"),
            "created_at": now,
            "read_by": []
        }
        await db.notifications.insert_one(notification_doc)
        
        return {
            "success": True,
            "message": "تم إرسال الرسالة بنجاح",
            "sent_count": message.get("recipient_count", 0)
        }
    
    @router.delete("/{message_id}")
    async def delete_message(
        message_id: str,
        current_user: dict = Depends(require_roles([UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN]))
    ):
        """Delete a message"""
        result = await db.messages.delete_one({"id": message_id})
        
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="الرسالة غير موجودة")
        
        return {"success": True, "message": "تم حذف الرسالة"}
    
    @router.post("/templates")
    async def create_message_template(
        data: dict,
        current_user: dict = Depends(require_roles([UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN]))
    ):
        """Create a message template"""
        school_id = current_user.get("tenant_id")
        
        template = {
            "id": str(uuid.uuid4()),
            "name": data.get("name"),
            "name_en": data.get("name_en", data.get("name")),
            "content_template": data.get("content_template"),
            "icon": data.get("icon", "mail"),
            "school_id": school_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "created_by": current_user.get("id")
        }
        
        await db.message_templates.insert_one(template)
        template.pop("_id", None)
        
        return {"success": True, "template": template}
    
    return router
