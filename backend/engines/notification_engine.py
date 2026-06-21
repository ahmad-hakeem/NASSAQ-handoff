"""
NASSAQ Notification Engine
محرك الإشعارات لمنصة نَسَّق

Handles:
- In-app notifications
- Notification templates
- Recipient resolution
- Read/unread tracking
- Priority handling
- Event-triggered notifications
"""

from typing import Optional, List, Dict, Any
from datetime import datetime, timezone, timedelta
from enum import Enum
import uuid

from sqlalchemy import select, and_, or_, func, update as sa_update, delete as sa_delete, desc as sa_desc

from pg_models import Notification, User, AuditLog
from engines.sql_utils import (
    model_to_dict, models_to_dicts,
    gd_find, gd_find_one, gd_insert, gd_update_one,
)


class NotificationType(str, Enum):
    INFO = "info"
    WARNING = "warning"
    SUCCESS = "success"
    ERROR = "error"
    ALERT = "alert"


class NotificationPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class NotificationCategory(str, Enum):
    ATTENDANCE = "attendance"
    ACADEMIC = "academic"
    BEHAVIOUR = "behaviour"
    SCHEDULE = "schedule"
    ANNOUNCEMENT = "announcement"
    SYSTEM = "system"
    REMINDER = "reminder"


def _notif_to_api(row) -> dict:
    d = model_to_dict(row)
    d.pop("_id", None)
    d["recipient_id"] = d.pop("user_id", "")
    if "extra_data" in d:
        d["metadata"] = d.pop("extra_data", {})
    return d


class NotificationEngine:
    """
    Core Notification Engine for NASSAQ
    Manages in-app notifications and alerts
    """

    def __init__(self, db):
        self.db = db

    @property
    def session(self):
        return self.db.session

    async def create_notification(
        self,
        tenant_id: str,
        recipient_id: str,
        title: str,
        message: str,
        notification_type: str = NotificationType.INFO.value,
        category: str = NotificationCategory.SYSTEM.value,
        priority: str = NotificationPriority.MEDIUM.value,
        **kwargs
    ) -> Dict[str, Any]:
        """Create a single notification"""
        notification_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)

        meta = kwargs.get("metadata", {})
        meta.update({
            "category": category,
            "action_type": kwargs.get("action_type"),
            "entity_type": kwargs.get("entity_type"),
            "entity_id": kwargs.get("entity_id"),
            "sender_id": kwargs.get("sender_id"),
            "expires_at": kwargs.get("expires_at"),
        })

        obj = Notification(
            id=notification_id,
            tenant_id=tenant_id,
            user_id=recipient_id,
            title=title,
            message=message,
            type=notification_type,
            priority=priority,
            is_read=False,
            read_at=None,
            action_url=kwargs.get("action_url"),
            extra_data=meta,
            # Task #1006 — persist the student reference so parents can
            # filter their notification inbox by child.
            student_id=kwargs.get("student_id"),
            created_at=now,
        )
        self.session.add(obj)
        await self.session.flush()

        notification_doc = {
            "id": notification_id,
            "tenant_id": tenant_id,
            "recipient_id": recipient_id,
            "title": title,
            "title_en": kwargs.get("title_en"),
            "message": message,
            "message_en": kwargs.get("message_en"),
            "type": notification_type,
            "category": category,
            "priority": priority,
            "is_read": False,
            "read_at": None,
            "action_url": kwargs.get("action_url"),
            "action_type": kwargs.get("action_type"),
            "entity_type": kwargs.get("entity_type"),
            "entity_id": kwargs.get("entity_id"),
            "sender_id": kwargs.get("sender_id"),
            "expires_at": kwargs.get("expires_at"),
            "created_at": now.isoformat(),
            "metadata": kwargs.get("metadata", {})
        }
        return notification_doc

    async def create_bulk_notifications(
        self,
        tenant_id: str,
        recipient_ids: List[str],
        title: str,
        message: str,
        notification_type: str = NotificationType.INFO.value,
        category: str = NotificationCategory.ANNOUNCEMENT.value,
        priority: str = NotificationPriority.MEDIUM.value,
        **kwargs
    ) -> Dict[str, Any]:
        """Create notifications for multiple recipients"""
        results = {
            "created": 0,
            "failed": 0,
            "notification_ids": []
        }

        for recipient_id in recipient_ids:
            try:
                notification = await self.create_notification(
                    tenant_id=tenant_id,
                    recipient_id=recipient_id,
                    title=title,
                    message=message,
                    notification_type=notification_type,
                    category=category,
                    priority=priority,
                    **kwargs
                )
                results["created"] += 1
                results["notification_ids"].append(notification["id"])
            except Exception as e:
                import logging
                logging.getLogger("nassaq.notifications").error(f"Failed to create notification for {recipient_id}: {e}")
                results["failed"] += 1

        return results

    async def send_to_role(
        self,
        tenant_id: str,
        role: str,
        title: str,
        message: str,
        **kwargs
    ) -> Dict[str, Any]:
        """Send notification to all users with a specific role"""
        stmt = select(User.id).where(
            and_(
                User.school_id == tenant_id,
                User.role == role,
                User.status == "active",
            )
        )
        result = await self.session.execute(stmt)
        recipient_ids = [row[0] for row in result.all()]

        return await self.create_bulk_notifications(
            tenant_id=tenant_id,
            recipient_ids=recipient_ids,
            title=title,
            message=message,
            **kwargs
        )

    async def send_to_section(
        self,
        tenant_id: str,
        section_id: str,
        include_teachers: bool = True,
        include_students: bool = True,
        include_parents: bool = False,
        title: str = "",
        message: str = "",
        **kwargs
    ) -> Dict[str, Any]:
        """Send notification to users in a section"""
        recipient_ids = []

        if include_students:
            stmt = select(User.id).where(
                and_(
                    User.school_id == tenant_id,
                    User.role == "student",
                    User.status == "active",
                )
            )
            result = await self.session.execute(stmt)
            recipient_ids.extend([row[0] for row in result.all()])

        if include_teachers:
            section = await gd_find_one(self.session, "sections", {"id": section_id})
            if section and section.get("homeroom_teacher_id"):
                recipient_ids.append(section["homeroom_teacher_id"])

        if include_parents:
            stmt = select(User.id).where(
                and_(
                    User.school_id == tenant_id,
                    User.role == "student",
                )
            )
            result = await self.session.execute(stmt)
            student_ids = [row[0] for row in result.all()]

            if student_ids:
                relationships = await gd_find(
                    self.session, "user_relationships",
                    {"tenant_id": tenant_id, "relationship_type": "parent"}
                )
                for r in relationships:
                    if r.get("student_id") in student_ids and r.get("user_id"):
                        recipient_ids.append(r["user_id"])

        recipient_ids = list(set(recipient_ids))

        return await self.create_bulk_notifications(
            tenant_id=tenant_id,
            recipient_ids=recipient_ids,
            title=title,
            message=message,
            **kwargs
        )

    async def get_user_notifications(
        self,
        tenant_id: str,
        user_id: str,
        unread_only: bool = False,
        category: Optional[str] = None,
        limit: int = 50,
        skip: int = 0
    ) -> List[Dict[str, Any]]:
        """Get notifications for a user"""
        conditions = [
            Notification.tenant_id == tenant_id,
            Notification.user_id == user_id,
        ]

        if unread_only:
            conditions.append(Notification.is_read == False)

        stmt = (
            select(Notification)
            .where(and_(*conditions))
            .order_by(sa_desc(Notification.created_at))
            .offset(skip)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        notifications = [_notif_to_api(row) for row in result.scalars().all()]

        if category:
            notifications = [
                n for n in notifications
                if (n.get("metadata") or {}).get("category") == category
                or n.get("category") == category
            ]

        return notifications

    async def get_notification_by_id(
        self,
        notification_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get notification by ID"""
        stmt = select(Notification).where(Notification.id == notification_id).limit(1)
        result = await self.session.execute(stmt)
        row = result.scalars().first()
        if not row:
            return None
        return _notif_to_api(row)

    async def get_unread_count(
        self,
        tenant_id: str,
        user_id: str
    ) -> int:
        """Get count of unread notifications"""
        stmt = select(func.count(Notification.id)).where(
            and_(
                Notification.tenant_id == tenant_id,
                Notification.user_id == user_id,
                Notification.is_read == False,
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar() or 0

    async def mark_as_read(
        self,
        notification_id: str,
        user_id: str
    ) -> Dict[str, Any]:
        """Mark a notification as read"""
        now = datetime.now(timezone.utc)

        stmt = (
            sa_update(Notification)
            .where(and_(Notification.id == notification_id, Notification.user_id == user_id))
            .values(is_read=True, read_at=now)
        )
        result = await self.session.execute(stmt)
        await self.session.flush()

        return {"success": result.rowcount > 0}

    async def mark_all_as_read(
        self,
        tenant_id: str,
        user_id: str,
        category: Optional[str] = None
    ) -> Dict[str, Any]:
        """Mark all notifications as read"""
        now = datetime.now(timezone.utc)

        conditions = [
            Notification.tenant_id == tenant_id,
            Notification.user_id == user_id,
            Notification.is_read == False,
        ]

        stmt = (
            sa_update(Notification)
            .where(and_(*conditions))
            .values(is_read=True, read_at=now)
        )
        result = await self.session.execute(stmt)
        await self.session.flush()

        return {"marked_count": result.rowcount}

    async def delete_notification(
        self,
        notification_id: str,
        user_id: str
    ) -> bool:
        """Delete a notification"""
        stmt = sa_delete(Notification).where(
            and_(Notification.id == notification_id, Notification.user_id == user_id)
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.rowcount > 0

    async def delete_old_notifications(
        self,
        tenant_id: str,
        days_old: int = 30
    ) -> int:
        """Delete notifications older than specified days"""
        cutoff = datetime.now(timezone.utc) - timedelta(days=days_old)

        stmt = sa_delete(Notification).where(
            and_(
                Notification.tenant_id == tenant_id,
                Notification.created_at < cutoff,
                Notification.is_read == True,
            )
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.rowcount

    async def create_template(
        self,
        tenant_id: str,
        code: str,
        title_template: str,
        message_template: str,
        created_by: str,
        **kwargs
    ) -> Dict[str, Any]:
        """Create a notification template"""
        template_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        template_doc = {
            "id": template_id,
            "tenant_id": tenant_id,
            "code": code,
            "title_template": title_template,
            "title_template_en": kwargs.get("title_template_en"),
            "message_template": message_template,
            "message_template_en": kwargs.get("message_template_en"),
            "category": kwargs.get("category", NotificationCategory.SYSTEM.value),
            "default_type": kwargs.get("default_type", NotificationType.INFO.value),
            "default_priority": kwargs.get("default_priority", NotificationPriority.MEDIUM.value),
            "is_active": True,
            "created_at": now,
            "created_by": created_by
        }

        await gd_insert(self.session, "notification_templates", template_doc)
        return template_doc

    async def get_template(
        self,
        tenant_id: str,
        code: str
    ) -> Optional[Dict[str, Any]]:
        """Get a notification template by code"""
        return await gd_find_one(
            self.session, "notification_templates",
            {"tenant_id": tenant_id, "code": code, "is_active": "true"}
        )

    async def send_from_template(
        self,
        tenant_id: str,
        template_code: str,
        recipient_ids: List[str],
        variables: Dict[str, str],
        **kwargs
    ) -> Dict[str, Any]:
        """Send notifications using a template"""
        template = await self.get_template(tenant_id, template_code)

        if not template:
            raise ValueError(f"القالب '{template_code}' غير موجود")

        title = template.get("title_template", "")
        message = template.get("message_template", "")

        for key, value in variables.items():
            title = title.replace(f"{{{key}}}", str(value))
            message = message.replace(f"{{{key}}}", str(value))

        return await self.create_bulk_notifications(
            tenant_id=tenant_id,
            recipient_ids=recipient_ids,
            title=title,
            message=message,
            notification_type=kwargs.get("notification_type", template.get("default_type")),
            category=kwargs.get("category", template.get("category")),
            priority=kwargs.get("priority", template.get("default_priority")),
            **kwargs
        )

    async def set_user_preferences(
        self,
        tenant_id: str,
        user_id: str,
        preferences: Dict[str, bool]
    ) -> Dict[str, Any]:
        """Set notification preferences for a user"""
        now = datetime.now(timezone.utc).isoformat()

        existing = await gd_find_one(
            self.session, "notification_preferences",
            {"tenant_id": tenant_id, "user_id": user_id}
        )

        if existing:
            await gd_update_one(
                self.session, "notification_preferences",
                {"id": existing["id"]},
                {"preferences": preferences, "updated_at": now}
            )
            existing["preferences"] = preferences
            existing.pop("_id", None)
            return existing

        pref_id = str(uuid.uuid4())
        pref_doc = {
            "id": pref_id,
            "tenant_id": tenant_id,
            "user_id": user_id,
            "preferences": preferences,
            "created_at": now
        }

        await gd_insert(self.session, "notification_preferences", pref_doc)
        return pref_doc

    async def get_user_preferences(
        self,
        tenant_id: str,
        user_id: str
    ) -> Dict[str, bool]:
        """Get notification preferences for a user"""
        pref = await gd_find_one(
            self.session, "notification_preferences",
            {"tenant_id": tenant_id, "user_id": user_id}
        )

        if pref:
            return pref.get("preferences", {})

        return {
            "attendance_alerts": True,
            "academic_updates": True,
            "behaviour_notes": True,
            "schedule_changes": True,
            "announcements": True,
            "system_notifications": True,
            "reminders": True
        }

    async def trigger_attendance_alert(
        self,
        tenant_id: str,
        student_id: str,
        student_name: str,
        absence_type: str,
        date: str,
        parent_ids: List[str]
    ) -> Dict[str, Any]:
        """Trigger attendance notification"""
        title = f"تنبيه حضور - {student_name}"
        message = f"تم تسجيل {absence_type} للطالب {student_name} بتاريخ {date}"

        return await self.create_bulk_notifications(
            tenant_id=tenant_id,
            recipient_ids=parent_ids,
            title=title,
            message=message,
            notification_type=NotificationType.ALERT.value,
            category=NotificationCategory.ATTENDANCE.value,
            priority=NotificationPriority.HIGH.value,
            entity_type="attendance",
            entity_id=student_id,
            student_id=student_id,
        )

    async def trigger_grade_posted(
        self,
        tenant_id: str,
        student_id: str,
        assessment_title: str,
        score: float,
        max_score: float,
        parent_ids: List[str]
    ) -> Dict[str, Any]:
        """Trigger grade posted notification"""
        percentage = round((score / max_score * 100) if max_score > 0 else 0, 1)

        title = f"درجة جديدة - {assessment_title}"
        message = f"تم رصد درجة {score}/{max_score} ({percentage}%) في {assessment_title}"

        recipients = [student_id] + parent_ids

        return await self.create_bulk_notifications(
            tenant_id=tenant_id,
            recipient_ids=recipients,
            title=title,
            message=message,
            notification_type=NotificationType.INFO.value,
            category=NotificationCategory.ACADEMIC.value,
            priority=NotificationPriority.MEDIUM.value,
            entity_type="assessment",
            student_id=student_id,
            metadata={
                "score": score,
                "max_score": max_score,
                "percentage": percentage
            }
        )

    async def trigger_behaviour_note(
        self,
        tenant_id: str,
        student_id: str,
        student_name: str,
        behaviour_type: str,
        is_positive: bool,
        parent_ids: List[str]
    ) -> Dict[str, Any]:
        """Trigger behaviour note notification"""
        emoji = "⭐" if is_positive else "⚠️"
        title = f"{emoji} ملاحظة سلوكية - {student_name}"
        message = f"تم تسجيل ملاحظة سلوكية: {behaviour_type}"

        return await self.create_bulk_notifications(
            tenant_id=tenant_id,
            recipient_ids=parent_ids,
            title=title,
            message=message,
            notification_type=NotificationType.SUCCESS.value if is_positive else NotificationType.WARNING.value,
            category=NotificationCategory.BEHAVIOUR.value,
            priority=NotificationPriority.MEDIUM.value if is_positive else NotificationPriority.HIGH.value,
            entity_type="behaviour",
            entity_id=student_id,
            student_id=student_id,
        )

    async def get_notification_stats(
        self,
        tenant_id: str,
        days: int = 30
    ) -> Dict[str, Any]:
        """Get notification statistics"""
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        stmt = select(Notification).where(
            and_(Notification.tenant_id == tenant_id, Notification.created_at >= cutoff)
        )
        result = await self.session.execute(stmt)
        notifications = [_notif_to_api(r) for r in result.scalars().all()]

        total = len(notifications)
        read = len([n for n in notifications if n.get("is_read")])
        unread = total - read

        by_category = {}
        for n in notifications:
            cat = (n.get("metadata") or {}).get("category", "unknown")
            by_category[cat] = by_category.get(cat, 0) + 1

        by_type = {}
        for n in notifications:
            t = n.get("type", "unknown")
            by_type[t] = by_type.get(t, 0) + 1

        read_rate = round((read / total * 100) if total > 0 else 0, 2)

        return {
            "tenant_id": tenant_id,
            "period_days": days,
            "total_notifications": total,
            "read": read,
            "unread": unread,
            "read_rate": read_rate,
            "by_category": by_category,
            "by_type": by_type
        }


__all__ = [
    "NotificationEngine",
    "NotificationType",
    "NotificationPriority",
    "NotificationCategory"
]
