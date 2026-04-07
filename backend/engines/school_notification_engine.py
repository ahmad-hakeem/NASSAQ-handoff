"""
School Notification Engine - محرك إشعارات المدرسة
Handles sending notifications to students, teachers, and parents
"""
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from enum import Enum

from sqlalchemy import select, and_, func, desc as sa_desc

from pg_models import Notification, Student, Teacher, Parent
from engines.sql_utils import (
    model_to_dict, models_to_dicts, dict_to_model, apply_updates,
    gd_insert, gd_insert_many, gd_find, gd_count,
)

logger = logging.getLogger(__name__)

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

class SchoolNotificationEngine:
    """Engine for school notifications"""

    def __init__(self, db):
        self.db = db

    @property
    def session(self):
        return self.db.session

    def _generate_notification_id(self) -> str:
        """Generate unique notification ID"""
        timestamp = datetime.now().strftime("%y%m%d%H%M%S")
        import secrets
        return f"NTF-{timestamp}-{secrets.token_hex(3).upper()}"

    async def send_notification(
        self,
        request: SendNotificationRequest,
        tenant_id: str,
        sent_by: str
    ) -> Dict[str, Any]:
        """Send notification to recipients"""
        try:
            notification_id = self._generate_notification_id()
            now = datetime.now(timezone.utc)

            recipients = await self._resolve_recipients(
                request.recipient_type,
                request.recipient_filter,
                tenant_id
            )

            if not recipients:
                return {
                    "success": False,
                    "error": "لا يوجد مستلمين للإشعار",
                    "error_en": "No recipients found"
                }

            notification_doc = {
                "notification_id": notification_id,
                "tenant_id": tenant_id,
                "title_ar": request.title_ar,
                "title_en": request.title_en,
                "message_ar": request.message_ar,
                "message_en": request.message_en,
                "recipient_type": request.recipient_type.value,
                "recipient_filter": request.recipient_filter,
                "recipient_count": len(recipients),
                "notification_type": request.notification_type.value,
                "priority": request.priority.value,
                "send_push": request.send_push,
                "send_sms": request.send_sms,
                "send_email": request.send_email,
                "scheduled_at": request.scheduled_at,
                "status": "sent" if not request.scheduled_at else "scheduled",
                "sent_at": now.isoformat() if not request.scheduled_at else None,
                "sent_by": sent_by,
                "created_at": now.isoformat(),
            }

            obj = dict_to_model(Notification, {
                "id": notification_id,
                "tenant_id": tenant_id,
                "user_id": sent_by,
                "title": request.title_ar,
                "message": request.message_ar,
                "type": request.notification_type.value,
                "priority": request.priority.value,
                "is_read": False,
                "extra_data": notification_doc,
            })
            self.session.add(obj)
            await self.session.flush()

            if not request.scheduled_at:
                await self._create_recipient_logs(notification_id, recipients, tenant_id, now)

            return {
                "success": True,
                "notification_id": notification_id,
                "recipient_count": len(recipients),
                "message": f"تم إرسال الإشعار إلى {len(recipients)} مستلم",
                "message_en": f"Notification sent to {len(recipients)} recipients"
            }

        except Exception as e:
            logger.error(f"Error sending notification: {e}")
            return {"success": False, "error": str(e)}

    async def _resolve_recipients(
        self,
        recipient_type: RecipientType,
        recipient_filter: Optional[Dict[str, Any]],
        tenant_id: str
    ) -> List[Dict[str, Any]]:
        """Resolve recipients based on type and filter"""
        recipients = []

        if recipient_type == RecipientType.all_students:
            stmt = select(Student).where(
                and_(Student.school_id == tenant_id, Student.is_active == True)
            )
            result = await self.session.execute(stmt)
            recipients = [{"id": s.id, "type": "student", "name": s.full_name} for s in result.scalars().all()]

        elif recipient_type == RecipientType.all_teachers:
            stmt = select(Teacher).where(
                and_(Teacher.school_id == tenant_id, Teacher.is_active == True)
            )
            result = await self.session.execute(stmt)
            recipients = [{"id": t.id, "type": "teacher", "name": t.full_name} for t in result.scalars().all()]

        elif recipient_type == RecipientType.all_parents:
            stmt = select(Parent).where(
                and_(Parent.school_id == tenant_id, Parent.is_active == True)
            )
            result = await self.session.execute(stmt)
            recipients = [{"id": p.id, "type": "parent", "name": p.full_name} for p in result.scalars().all()]

        elif recipient_type == RecipientType.grade_students:
            grade_id = recipient_filter.get("grade_id") if recipient_filter else None
            if grade_id:
                stmt = select(Student).where(
                    and_(Student.school_id == tenant_id, Student.grade == grade_id, Student.is_active == True)
                )
                result = await self.session.execute(stmt)
                recipients = [{"id": s.id, "type": "student", "name": s.full_name} for s in result.scalars().all()]

        elif recipient_type == RecipientType.class_students:
            class_id = recipient_filter.get("class_id") if recipient_filter else None
            if class_id:
                stmt = select(Student).where(
                    and_(Student.school_id == tenant_id, Student.class_id == class_id, Student.is_active == True)
                )
                result = await self.session.execute(stmt)
                recipients = [{"id": s.id, "type": "student", "name": s.full_name} for s in result.scalars().all()]

        elif recipient_type == RecipientType.specific_users:
            user_ids = recipient_filter.get("user_ids", []) if recipient_filter else []
            for uid in user_ids:
                recipients.append({"id": uid, "type": "user", "name": ""})

        return recipients

    async def _create_recipient_logs(
        self,
        notification_id: str,
        recipients: List[Dict[str, Any]],
        tenant_id: str,
        sent_at: datetime
    ):
        """Create log entries for each recipient"""
        logs = []
        for recipient in recipients:
            logs.append({
                "notification_id": notification_id,
                "tenant_id": tenant_id,
                "recipient_id": recipient["id"],
                "recipient_type": recipient["type"],
                "recipient_name": recipient.get("name"),
                "status": "delivered",
                "read": False,
                "sent_at": sent_at.isoformat(),
            })

        if logs:
            await gd_insert_many(self.session, "notification_logs", logs)

    async def get_notification(self, notification_id: str, tenant_id: str) -> Optional[Dict[str, Any]]:
        """Get notification by ID"""
        stmt = select(Notification).where(
            and_(Notification.id == notification_id, Notification.tenant_id == tenant_id)
        ).limit(1)
        result = await self.session.execute(stmt)
        row = result.scalars().first()
        if not row:
            return None
        d = model_to_dict(row)
        d.pop("_id", None)
        return d

    async def list_notifications(
        self,
        tenant_id: str,
        notification_type: Optional[str] = None,
        skip: int = 0,
        limit: int = 50
    ) -> Dict[str, Any]:
        """List notifications"""
        conditions = [Notification.tenant_id == tenant_id]
        if notification_type:
            conditions.append(Notification.type == notification_type)

        count_stmt = select(func.count(Notification.id)).where(and_(*conditions))
        total = (await self.session.execute(count_stmt)).scalar() or 0

        stmt = (
            select(Notification)
            .where(and_(*conditions))
            .order_by(sa_desc(Notification.created_at))
            .offset(skip)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        notifications = []
        for row in result.scalars().all():
            d = model_to_dict(row)
            d.pop("_id", None)
            notifications.append(d)

        return {"notifications": notifications, "total": total}

    async def get_recipient_types(self) -> List[Dict[str, str]]:
        """Get recipient types"""
        return [
            {"code": "all_students", "name_ar": "جميع الطلاب", "name_en": "All Students"},
            {"code": "all_teachers", "name_ar": "جميع المعلمين", "name_en": "All Teachers"},
            {"code": "all_parents", "name_ar": "جميع أولياء الأمور", "name_en": "All Parents"},
            {"code": "grade_students", "name_ar": "طلاب صف معين", "name_en": "Grade Students"},
            {"code": "grade_parents", "name_ar": "أولياء أمور صف", "name_en": "Grade Parents"},
            {"code": "class_students", "name_ar": "طلاب فصل معين", "name_en": "Class Students"},
            {"code": "class_parents", "name_ar": "أولياء أمور فصل", "name_en": "Class Parents"},
            {"code": "specific_users", "name_ar": "مستخدمين محددين", "name_en": "Specific Users"},
        ]

    async def get_notification_types(self) -> List[Dict[str, str]]:
        """Get notification types"""
        return [
            {"code": "announcement", "name_ar": "إعلان", "name_en": "Announcement"},
            {"code": "reminder", "name_ar": "تذكير", "name_en": "Reminder"},
            {"code": "alert", "name_ar": "تنبيه", "name_en": "Alert"},
            {"code": "event", "name_ar": "حدث", "name_en": "Event"},
            {"code": "emergency", "name_ar": "طوارئ", "name_en": "Emergency"},
        ]

    async def get_priorities(self) -> List[Dict[str, str]]:
        """Get notification priorities"""
        return [
            {"code": "low", "name_ar": "منخفضة", "name_en": "Low"},
            {"code": "normal", "name_ar": "عادية", "name_en": "Normal"},
            {"code": "high", "name_ar": "عالية", "name_en": "High"},
            {"code": "urgent", "name_ar": "عاجلة", "name_en": "Urgent"},
        ]
