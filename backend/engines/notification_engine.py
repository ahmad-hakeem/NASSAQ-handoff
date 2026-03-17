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


class NotificationEngine:
    """
    Core Notification Engine for NASSAQ
    Manages in-app notifications and alerts
    """
    
    def __init__(self, db):
        self.db = db
        self.notifications_collection = db.notifications
        self.templates_collection = db.notification_templates
        self.preferences_collection = db.notification_preferences
        self.audit_collection = db.audit_logs
    
    # ============== NOTIFICATION CREATION ==============
    
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
        now = datetime.now(timezone.utc).isoformat()
        
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
            "created_at": now,
            "metadata": kwargs.get("metadata", {})
        }
        
        await self.notifications_collection.insert_one(notification_doc)
        
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
        now = datetime.now(timezone.utc).isoformat()
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
        # Get users with the role
        users = await self.db.users.find(
            {
                "tenant_id": tenant_id,
                "role": role,
                "account_status": "active"
            },
            {"id": 1, "_id": 0}
        ).to_list(10000)
        
        recipient_ids = [u["id"] for u in users]
        
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
        
        # Get students in section
        if include_students:
            students = await self.db.users.find(
                {
                    "tenant_id": tenant_id,
                    "section_id": section_id,
                    "role": "student",
                    "account_status": "active"
                },
                {"id": 1, "_id": 0}
            ).to_list(1000)
            recipient_ids.extend([s["id"] for s in students])
        
        # Get section's homeroom teacher
        if include_teachers:
            section = await self.db.sections.find_one(
                {"id": section_id},
                {"homeroom_teacher_id": 1, "_id": 0}
            )
            if section and section.get("homeroom_teacher_id"):
                recipient_ids.append(section["homeroom_teacher_id"])
        
        # Get parents if requested
        if include_parents:
            students = await self.db.users.find(
                {
                    "tenant_id": tenant_id,
                    "section_id": section_id,
                    "role": "student"
                },
                {"id": 1, "_id": 0}
            ).to_list(1000)
            
            student_ids = [s["id"] for s in students]
            
            # Find parent relationships
            relationships = await self.db.user_relationships.find(
                {
                    "tenant_id": tenant_id,
                    "student_id": {"$in": student_ids},
                    "relationship_type": "parent"
                },
                {"user_id": 1, "_id": 0}
            ).to_list(5000)
            
            recipient_ids.extend([r["user_id"] for r in relationships])
        
        # Remove duplicates
        recipient_ids = list(set(recipient_ids))
        
        return await self.create_bulk_notifications(
            tenant_id=tenant_id,
            recipient_ids=recipient_ids,
            title=title,
            message=message,
            **kwargs
        )
    
    # ============== NOTIFICATION RETRIEVAL ==============
    
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
        query = {
            "tenant_id": tenant_id,
            "recipient_id": user_id
        }
        
        if unread_only:
            query["is_read"] = False
        
        if category:
            query["category"] = category
        
        # Filter out expired notifications
        now = datetime.now(timezone.utc).isoformat()
        query["$or"] = [
            {"expires_at": None},
            {"expires_at": {"$gt": now}}
        ]
        
        notifications = await self.notifications_collection.find(
            query,
            {"_id": 0}
        ).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
        
        return notifications
    
    async def get_notification_by_id(
        self,
        notification_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get notification by ID"""
        return await self.notifications_collection.find_one(
            {"id": notification_id},
            {"_id": 0}
        )
    
    async def get_unread_count(
        self,
        tenant_id: str,
        user_id: str
    ) -> int:
        """Get count of unread notifications"""
        now = datetime.now(timezone.utc).isoformat()
        
        count = await self.notifications_collection.count_documents({
            "tenant_id": tenant_id,
            "recipient_id": user_id,
            "is_read": False,
            "$or": [
                {"expires_at": None},
                {"expires_at": {"$gt": now}}
            ]
        })
        
        return count
    
    # ============== NOTIFICATION ACTIONS ==============
    
    async def mark_as_read(
        self,
        notification_id: str,
        user_id: str
    ) -> Dict[str, Any]:
        """Mark a notification as read"""
        now = datetime.now(timezone.utc).isoformat()
        
        result = await self.notifications_collection.update_one(
            {
                "id": notification_id,
                "recipient_id": user_id
            },
            {
                "$set": {
                    "is_read": True,
                    "read_at": now
                }
            }
        )
        
        return {"success": result.modified_count > 0}
    
    async def mark_all_as_read(
        self,
        tenant_id: str,
        user_id: str,
        category: Optional[str] = None
    ) -> Dict[str, Any]:
        """Mark all notifications as read"""
        now = datetime.now(timezone.utc).isoformat()
        
        query = {
            "tenant_id": tenant_id,
            "recipient_id": user_id,
            "is_read": False
        }
        
        if category:
            query["category"] = category
        
        result = await self.notifications_collection.update_many(
            query,
            {
                "$set": {
                    "is_read": True,
                    "read_at": now
                }
            }
        )
        
        return {
            "marked_count": result.modified_count
        }
    
    async def delete_notification(
        self,
        notification_id: str,
        user_id: str
    ) -> bool:
        """Delete a notification"""
        result = await self.notifications_collection.delete_one({
            "id": notification_id,
            "recipient_id": user_id
        })
        
        return result.deleted_count > 0
    
    async def delete_old_notifications(
        self,
        tenant_id: str,
        days_old: int = 30
    ) -> int:
        """Delete notifications older than specified days"""
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days_old)).isoformat()
        
        result = await self.notifications_collection.delete_many({
            "tenant_id": tenant_id,
            "created_at": {"$lt": cutoff},
            "is_read": True
        })
        
        return result.deleted_count
    
    # ============== NOTIFICATION TEMPLATES ==============
    
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
        
        await self.templates_collection.insert_one(template_doc)
        
        return template_doc
    
    async def get_template(
        self,
        tenant_id: str,
        code: str
    ) -> Optional[Dict[str, Any]]:
        """Get a notification template by code"""
        return await self.templates_collection.find_one(
            {
                "tenant_id": tenant_id,
                "code": code,
                "is_active": True
            },
            {"_id": 0}
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
        
        # Replace variables in template
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
    
    # ============== USER PREFERENCES ==============
    
    async def set_user_preferences(
        self,
        tenant_id: str,
        user_id: str,
        preferences: Dict[str, bool]
    ) -> Dict[str, Any]:
        """Set notification preferences for a user"""
        now = datetime.now(timezone.utc).isoformat()
        
        existing = await self.preferences_collection.find_one({
            "tenant_id": tenant_id,
            "user_id": user_id
        })
        
        if existing:
            await self.preferences_collection.update_one(
                {"id": existing["id"]},
                {
                    "$set": {
                        "preferences": preferences,
                        "updated_at": now
                    }
                }
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
        
        await self.preferences_collection.insert_one(pref_doc)
        
        return pref_doc
    
    async def get_user_preferences(
        self,
        tenant_id: str,
        user_id: str
    ) -> Dict[str, bool]:
        """Get notification preferences for a user"""
        pref = await self.preferences_collection.find_one(
            {
                "tenant_id": tenant_id,
                "user_id": user_id
            },
            {"_id": 0}
        )
        
        if pref:
            return pref.get("preferences", {})
        
        # Return default preferences
        return {
            "attendance_alerts": True,
            "academic_updates": True,
            "behaviour_notes": True,
            "schedule_changes": True,
            "announcements": True,
            "system_notifications": True,
            "reminders": True
        }
    
    # ============== EVENT TRIGGERS ==============
    
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
            entity_id=student_id
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
            entity_id=student_id
        )
    
    # ============== ANALYTICS ==============
    
    async def get_notification_stats(
        self,
        tenant_id: str,
        days: int = 30
    ) -> Dict[str, Any]:
        """Get notification statistics"""
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        
        notifications = await self.notifications_collection.find(
            {
                "tenant_id": tenant_id,
                "created_at": {"$gte": cutoff}
            },
            {"_id": 0}
        ).to_list(100000)
        
        total = len(notifications)
        read = len([n for n in notifications if n.get("is_read")])
        unread = total - read
        
        # Group by category
        by_category = {}
        for n in notifications:
            cat = n.get("category", "unknown")
            by_category[cat] = by_category.get(cat, 0) + 1
        
        # Group by type
        by_type = {}
        for n in notifications:
            t = n.get("type", "unknown")
            by_type[t] = by_type.get(t, 0) + 1
        
        # Read rate
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


# Export
__all__ = [
    "NotificationEngine",
    "NotificationType",
    "NotificationPriority",
    "NotificationCategory"
]
