"""
School Notification Engine - محرك إشعارات المدرسة
Handles sending notifications to students, teachers, and parents
"""
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from enum import Enum

from sqlalchemy import select, and_, or_, func, desc as sa_desc
from sqlalchemy.orm import aliased

from pg_models import Notification, Student, Teacher, Parent, User
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

            # Fan-out: insert one notification row per recipient user so each
            # one shows up in their own inbox. The inbox endpoint
            # (GET /notifications) filters by notifications.user_id, so a
            # single broadcast row keyed to the admin would be invisible to
            # everyone else (this was the "black hole" bug).
            delivered_count = 0
            if not request.scheduled_at:
                import secrets as _secrets
                for rec in recipients:
                    rec_user_id = rec.get("user_id")
                    if not rec_user_id:
                        continue
                    per_user_id = f"{notification_id}-{_secrets.token_hex(3).upper()}"
                    self.session.add(dict_to_model(Notification, {
                        "id": per_user_id,
                        "tenant_id": tenant_id,
                        "user_id": rec_user_id,
                        "title": request.title_ar,
                        "message": request.message_ar,
                        "type": request.notification_type.value,
                        "priority": request.priority.value,
                        "is_read": False,
                        "extra_data": {
                            **notification_doc,
                            "broadcast_id": notification_id,
                            "recipient_user_id": rec_user_id,
                            "recipient_role": rec.get("type"),
                            "recipient_name": rec.get("name"),
                            "sender_id": sent_by,
                        },
                    }))
                    delivered_count += 1
                await self.session.flush()

                await self._create_recipient_logs(notification_id, recipients, tenant_id, now)
            else:
                # Scheduled broadcasts keep an audit row owned by the sender;
                # the scheduler is responsible for fanning out at delivery time.
                self.session.add(dict_to_model(Notification, {
                    "id": notification_id,
                    "tenant_id": tenant_id,
                    "user_id": sent_by,
                    "title": request.title_ar,
                    "message": request.message_ar,
                    "type": request.notification_type.value,
                    "priority": request.priority.value,
                    "is_read": False,
                    "extra_data": notification_doc,
                }))
                await self.session.flush()

            return {
                "success": True,
                "notification_id": notification_id,
                "recipient_count": len(recipients),
                "delivered_count": delivered_count,
                "message": f"تم إرسال الإشعار إلى {delivered_count or len(recipients)} مستلم",
                "message_en": f"Notification sent to {delivered_count or len(recipients)} recipients"
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
        """Resolve recipients to ``users.id`` for the notifications fan-out.

        Every entry in the returned list carries ``user_id`` (the FK target on
        ``notifications.user_id``) so the caller can insert per-user rows that
        the inbox query (``WHERE user_id = current_user.id``) actually reads.

        Fail-closed on missing ``tenant_id``: every cohort below is a
        ``users``/``students``/``parents`` lookup that joins on tenant. If a
        caller (or upstream route) ever forgets to pass a tenant id, the
        SQLAlchemy ``== None`` comparison would silently match either nothing
        or the wrong rows depending on the column nullability — neither of
        which is acceptable for a multi-tenant cohort builder. Returning an
        empty list keeps the cross-tenant leak from B-3 closed regardless of
        what the route layer does. (Task #177.)
        """
        recipients: List[Dict[str, Any]] = []
        if not tenant_id:
            return recipients

        async def _users_for_role(roles: List[str]) -> List[Dict[str, Any]]:
            stmt = select(User).where(
                and_(
                    User.tenant_id == tenant_id,
                    User.role.in_(roles),
                    User.is_active.is_(True),
                )
            )
            result = await self.session.execute(stmt)
            return [
                {"user_id": u.id, "id": u.id, "type": u.role, "name": u.full_name, "email": u.email}
                for u in result.scalars().all()
            ]

        async def _user_ids_from_emails(emails: List[str], roles: List[str]) -> Dict[str, Dict[str, Any]]:
            clean = [e for e in emails if e]
            if not clean:
                return {}
            stmt = select(User).where(
                and_(
                    User.tenant_id == tenant_id,
                    User.role.in_(roles),
                    User.email.in_(clean),
                    User.is_active.is_(True),
                )
            )
            result = await self.session.execute(stmt)
            return {u.email: {"user_id": u.id, "id": u.id, "type": u.role, "name": u.full_name} for u in result.scalars().all()}

        if recipient_type == RecipientType.all_teachers:
            # "جميع المعلمين" = the school's ACTIVE teacher records resolved to
            # their active user accounts — the same cohort every admin surface
            # counts (master grid, teacher management, dashboards all count
            # ``teachers`` rows with ``is_active``). Matching on ``users.role``
            # alone over-counted: an active user account with a teacher-type
            # role but NO ``teachers`` row (orphaned/test account) is not a
            # teacher of the school, so it must be neither notified nor counted
            # (the publish toast used to say "109 معلماً" for a school with 108
            # teachers). Teacher rows without a linked active user account have
            # no inbox to deliver to, so they are correctly absent and the
            # returned count reflects real recipients only. The final
            # user_id dedup below collapses multiple teacher rows that point
            # at the same user account.
            #
            # The tenant proof is the school-pinned ``teachers`` row, NOT the
            # nullable ``users.tenant_id``: legacy teacher accounts were
            # provisioned without a tenant, and requiring equality silently
            # dropped them from the fan-out — a school with 9 teachers both
            # notified and reported only 8. A user row that carries a
            # DIFFERENT tenant is still rejected (fail closed).
            #
            # ``teachers.user_id`` carries no uniqueness constraint, so an
            # UNPINNED (NULL-tenant) account could in principle hold active
            # teacher rows in two schools. Such an account has no trustworthy
            # owner, so it is excluded from BOTH schools' broadcasts rather
            # than leaking one school's announcement into the other. Accounts
            # pinned by ``users.tenant_id`` are unaffected by this guard.
            _OtherTeacher = aliased(Teacher)
            other_school_claim = (
                select(_OtherTeacher.id)
                .where(
                    and_(
                        _OtherTeacher.user_id == User.id,
                        _OtherTeacher.is_active.is_(True),
                        _OtherTeacher.school_id.isnot(None),
                        _OtherTeacher.school_id != tenant_id,
                    )
                )
                .exists()
            )
            stmt = (
                select(User)
                .join(Teacher, Teacher.user_id == User.id)
                .where(
                    and_(
                        Teacher.school_id == tenant_id,
                        Teacher.is_active.is_(True),
                        or_(
                            User.tenant_id == tenant_id,
                            and_(User.tenant_id.is_(None), ~other_school_claim),
                        ),
                        User.is_active.is_(True),
                    )
                )
            )
            result = await self.session.execute(stmt)
            recipients = [
                {"user_id": u.id, "id": u.id, "type": u.role, "name": u.full_name, "email": u.email}
                for u in result.scalars().all()
            ]

        elif recipient_type == RecipientType.all_students:
            recipients = await _users_for_role(["student"])

        elif recipient_type == RecipientType.all_parents:
            recipients = await _users_for_role(["parent"])

        elif recipient_type == RecipientType.grade_students:
            grade_id = recipient_filter.get("grade_id") if recipient_filter else None
            if grade_id:
                stmt = select(Student).where(
                    and_(Student.school_id == tenant_id, Student.grade == grade_id, Student.is_active == True)
                )
                result = await self.session.execute(stmt)
                students = list(result.scalars().all())
                emails = [s.email for s in students if s.email]
                by_email = await _user_ids_from_emails(emails, ["student"])
                for s in students:
                    u = by_email.get(s.email) if s.email else None
                    if u:
                        recipients.append({**u, "name": u.get("name") or s.full_name})

        elif recipient_type == RecipientType.grade_parents:
            grade_id = recipient_filter.get("grade_id") if recipient_filter else None
            if grade_id:
                stmt = select(Student).where(
                    and_(Student.school_id == tenant_id, Student.grade == grade_id, Student.is_active == True)
                )
                result = await self.session.execute(stmt)
                students = list(result.scalars().all())
                emails = [s.parent_email for s in students if s.parent_email]
                by_email = await _user_ids_from_emails(emails, ["parent"])
                seen = set()
                for u in by_email.values():
                    if u["user_id"] in seen:
                        continue
                    seen.add(u["user_id"])
                    recipients.append(u)

        elif recipient_type == RecipientType.class_students:
            class_id = recipient_filter.get("class_id") if recipient_filter else None
            if class_id:
                stmt = select(Student).where(
                    and_(Student.school_id == tenant_id, Student.class_id == class_id, Student.is_active == True)
                )
                result = await self.session.execute(stmt)
                students = list(result.scalars().all())
                emails = [s.email for s in students if s.email]
                by_email = await _user_ids_from_emails(emails, ["student"])
                for s in students:
                    u = by_email.get(s.email) if s.email else None
                    if u:
                        recipients.append({**u, "name": u.get("name") or s.full_name})

        elif recipient_type == RecipientType.class_parents:
            class_id = recipient_filter.get("class_id") if recipient_filter else None
            if class_id:
                stmt = select(Student).where(
                    and_(Student.school_id == tenant_id, Student.class_id == class_id, Student.is_active == True)
                )
                result = await self.session.execute(stmt)
                students = list(result.scalars().all())
                emails = [s.parent_email for s in students if s.parent_email]
                by_email = await _user_ids_from_emails(emails, ["parent"])
                seen = set()
                for u in by_email.values():
                    if u["user_id"] in seen:
                        continue
                    seen.add(u["user_id"])
                    recipients.append(u)

        elif recipient_type == RecipientType.specific_users:
            user_ids = recipient_filter.get("user_ids", []) if recipient_filter else []
            clean_ids = [uid for uid in user_ids if uid]
            if clean_ids:
                stmt = select(User).where(
                    and_(
                        User.tenant_id == tenant_id,
                        User.id.in_(clean_ids),
                        User.is_active.is_(True),
                    )
                )
                result = await self.session.execute(stmt)
                recipients = [
                    {"user_id": u.id, "id": u.id, "type": u.role, "name": u.full_name, "email": u.email}
                    for u in result.scalars().all()
                ]

        # De-duplicate on user_id in case the same user appears via multiple roles.
        seen_uids = set()
        deduped: List[Dict[str, Any]] = []
        for r in recipients:
            uid = r.get("user_id")
            if not uid or uid in seen_uids:
                continue
            seen_uids.add(uid)
            deduped.append(r)
        return deduped

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
            {"code": "circular", "name_ar": "تعميم", "name_en": "Circular"},
            {"code": "other", "name_ar": "أخرى", "name_en": "Other"},
        ]

    async def get_priorities(self) -> List[Dict[str, str]]:
        """Get notification priorities"""
        return [
            {"code": "low", "name_ar": "منخفضة", "name_en": "Low"},
            {"code": "normal", "name_ar": "عادية", "name_en": "Normal"},
            {"code": "high", "name_ar": "عالية", "name_en": "High"},
            {"code": "urgent", "name_ar": "عاجلة", "name_en": "Urgent"},
        ]
