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
from engines.sql_utils import gd_find, gd_find_one, gd_insert, gd_insert_many, gd_update_one, gd_update_many, gd_count, gd_delete_one, gd_delete_many, gd_distinct, gd_upsert, _gd_aggregate

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


async def _resolve_recipient_ids(db, audience: str, school_id: Optional[str], audience_ids: List[str]) -> List[str]:
    """Resolve target user_ids for a given audience scope.

    For the ``custom`` audience the supplied IDs are validated against the
    sender's tenant scope so a school principal/admin cannot inject
    notifications into other tenants.
    """
    if audience == "custom":
        clean_ids = [uid for uid in (audience_ids or []) if uid]
        if not clean_ids:
            return []
        scope = {"id": {"$in": clean_ids}, "is_active": True}
        if school_id:
            scope["tenant_id"] = school_id
        users = await gd_find(db.session, "users", scope, limit=10000)
        return [u["id"] for u in users if u.get("id")]

    base = {"is_active": True}
    if school_id:
        base["tenant_id"] = school_id

    if audience == "all":
        users = await gd_find(db.session, "users", base, limit=10000)
    elif audience == "teachers":
        users = await gd_find(db.session, "users", {**base, "role": {"$in": ["teacher", "independent_teacher", "school_teacher"]}}, limit=10000)
    elif audience == "students":
        users = await gd_find(db.session, "users", {**base, "role": "student"}, limit=10000)
    elif audience == "parents":
        users = await gd_find(db.session, "users", {**base, "role": "parent"}, limit=10000)
    else:
        users = []

    return [u["id"] for u in users if u.get("id")]


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
        total_sent = await gd_count(db.session, "messages", {**query, "status": "sent"})
        total_scheduled = await gd_count(db.session, "messages", {**query, "status": "scheduled"})
        total_drafts = await gd_count(db.session, "messages", {**query, "status": "draft"})
        
        # Count templates
        total_templates = await gd_count(db.session, "message_templates", query)
        
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
            recipient_count = await gd_count(db.session, "users", {"tenant_id": school_id}) if school_id else await gd_count(db.session, "users", {})
        elif message.audience == "teachers":
            recipient_count = await gd_count(db.session, "teachers", {"school_id": school_id}) if school_id else await gd_count(db.session, "teachers", {})
        elif message.audience == "students":
            recipient_count = await gd_count(db.session, "students", {"school_id": school_id}) if school_id else await gd_count(db.session, "students", {})
        elif message.audience == "parents":
            recipient_count = await gd_count(db.session, "users", {"role": "parent", "tenant_id": school_id}) if school_id else await gd_count(db.session, "users", {"role": "parent"})
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
        
        await gd_insert(db.session, "messages", message_doc)
        
        # Create per-user in-app notifications if sent immediately
        if status == "sent":
            recipient_ids = await _resolve_recipient_ids(
                db, message.audience, school_id, message.audience_ids or []
            )
            for uid in recipient_ids:
                await gd_insert(db.session, "notifications", {
                    "id": str(uuid.uuid4()),
                    "user_id": uid,
                    "tenant_id": school_id,
                    "title": message.title,
                    "message": message.content,
                    "type": "announcement",
                    "priority": "normal",
                    "is_read": False,
                    "extra_data": {
                        "message_id": message_id,
                        "audience": message.audience,
                    },
                })
            # Update actual sent_count to reflect per-user fan-out
            await gd_update_one(db.session, "messages", {"id": message_id}, {"sent_count": len(recipient_ids)})
            recipient_count = len(recipient_ids)
        
        if status == "sent" and message.audience == "parents":
            try:
                import asyncio
                from engines.portfolio_evidence_engine import PortfolioEvidenceEngine
                _pe = PortfolioEvidenceEngine(db)
                asyncio.create_task(_pe.capture_evidence(
                    teacher_id=current_user["id"],
                    school_id=school_id or "",
                    evidence_type="parent_communication_log",
                    title_ar=f"تواصل مع أولياء الأمور: {message.title}",
                    title_en=f"Parent Communication: {message.title}",
                    description_ar=f"رسالة إلى {recipient_count} ولي أمر",
                    description_en=f"Message to {recipient_count} parents",
                    source="auto", source_entity_type="message",
                    source_entity_id=message_id,
                    metadata={"recipient_count": recipient_count, "audience": "parents"},
                ))
            except Exception as _pe_err:
                import logging
                logging.getLogger(__name__).debug("Portfolio evidence (parent_comm) failed: %s", _pe_err)

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
        
        messages = await gd_find(db.session, "messages", query, order_by="created_at", desc_order=True, offset=skip, limit=limit)
        
        total = await gd_count(db.session, "messages", query)
        
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
        
        templates = await gd_find(db.session, "message_templates", query, limit=100)
        
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
            teachers = await gd_count(db.session, "teachers", {"school_id": school_id, "is_active": True})
            students = await gd_count(db.session, "students", {"school_id": school_id, "is_active": True})
            parents = await gd_count(db.session, "users", {"role": "parent", "tenant_id": school_id, "is_active": True})
            total = teachers + students + parents
        else:
            # Platform-wide for admins
            total = await gd_count(db.session, "users", {"is_active": True})
            teachers = await gd_count(db.session, "teachers", {"is_active": True})
            students = await gd_count(db.session, "students", {"is_active": True})
            parents = await gd_count(db.session, "users", {"role": "parent", "is_active": True})
        
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
        all_users = await gd_count(db.session, "users", {"is_active": True})
        schools = await gd_count(db.session, "schools", {})
        teachers = await gd_count(db.session, "users", {"role": {"$in": ["teacher", "independent_teacher"]}, "is_active": True})
        students = await gd_count(db.session, "users", {"role": "student", "is_active": True})
        principals = await gd_count(db.session, "users", {"role": "school_principal", "is_active": True})
        parents = await gd_count(db.session, "users", {"role": "parent", "is_active": True})
        
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
        messages = await gd_find(db.session, "messages", {"status": "scheduled"}, order_by="scheduled_at", desc_order=False, limit=50)
        
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
        messages = await gd_find(db.session, "messages", {"status": "sent"}, order_by="sent_at", desc_order=True, limit=50)
        
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
            recipient_count = await gd_count(db.session, "users", {"is_active": True})
        elif message.audience == "teachers":
            recipient_count = await gd_count(db.session, "users", {"role": {"$in": ["teacher", "independent_teacher"]}, "is_active": True})
        elif message.audience == "students":
            recipient_count = await gd_count(db.session, "users", {"role": "student", "is_active": True})
        elif message.audience == "schools":
            recipient_count = await gd_count(db.session, "users", {"role": "school_principal", "is_active": True})
        
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
        
        await gd_insert(db.session, "messages", message_doc)
        
        # Fan-out per-user notifications (platform-wide broadcast)
        recipient_ids = await _resolve_recipient_ids(db, message.audience, None, message.audience_ids or [])
        for uid in recipient_ids:
            await gd_insert(db.session, "notifications", {
                "id": str(uuid.uuid4()),
                "user_id": uid,
                "title": message.title,
                "message": message.content,
                "type": "broadcast",
                "priority": "normal",
                "is_read": False,
                "extra_data": {"message_id": message_id, "audience": message.audience},
            })
        actual_count = len(recipient_ids)
        await gd_update_one(db.session, "messages", {"id": message_id}, {"sent_count": actual_count})
        
        return {
            "success": True,
            "message_id": message_id,
            "recipients_count": actual_count,
            "message": f"تم إرسال الرسالة إلى {actual_count} مستخدم"
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
        
        messages = await gd_find(db.session, "messages", query, order_by="sent_at", desc_order=True, limit=50)
        
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
        
        msg = await gd_find_one(db.session, "messages", {"id": message_id})
        if msg:
            read_by = msg.get("read_by") or []
            if user_id not in read_by:
                read_by.append(user_id)
                await gd_update_one(db.session, "messages", {"id": message_id}, {"read_by": read_by})
        
        return {"success": True, "message": "تم تعيين الرسالة كمقروءة"}
    
    @router.put("/{message_id}")
    async def update_scheduled_message(
        message_id: str,
        data: dict,
        current_user: dict = Depends(require_roles([UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN]))
    ):
        """Update a scheduled message"""
        query = {"id": message_id}
        if current_user['role'] != 'platform_admin':
            tenant_id = current_user.get("tenant_id")
            if tenant_id:
                query["school_id"] = tenant_id

        message = await gd_find_one(db.session, "messages", query)
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
        
        await gd_update_one(db.session, "messages", {"id": message_id}, update_fields)
        
        return {"success": True, "message": "تم تحديث الرسالة المجدولة"}
    
    @router.post("/{message_id}/send-now")
    async def send_scheduled_message_now(
        message_id: str,
        current_user: dict = Depends(require_roles([UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN]))
    ):
        """Send a scheduled message immediately"""
        query = {"id": message_id}
        if current_user['role'] != 'platform_admin':
            tenant_id = current_user.get("tenant_id")
            if tenant_id:
                query["school_id"] = tenant_id

        message = await gd_find_one(db.session, "messages", query)
        if not message:
            raise HTTPException(status_code=404, detail="الرسالة غير موجودة")
        
        if message.get("status") != "scheduled":
            raise HTTPException(status_code=400, detail="هذه الرسالة ليست مجدولة")
        
        now = datetime.now(timezone.utc).isoformat()
        
        # Update status to sent
        await gd_update_one(db.session, "messages", {"id": message_id}, {
                "status": "sent",
                "sent_at": now,
                "sent_count": message.get("recipient_count", 0)
            })
        
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
        await gd_insert(db.session, "notifications", notification_doc)
        
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
        query = {"id": message_id}
        if current_user['role'] != 'platform_admin':
            tenant_id = current_user.get("tenant_id")
            if tenant_id:
                query["school_id"] = tenant_id

        result = await gd_delete_one(db.session, "messages", query)
        
        if result == 0:
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
        
        await gd_insert(db.session, "message_templates", template)
        template.pop("_id", None)
        
        return {"success": True, "template": template}
    
    return router
