"""
NASSAQ Teacher Registration Engine
محرك طلبات تسجيل المعلمين المستقلين لمنصة نَسَّق
"""

from typing import Optional, List, Dict, Any
from datetime import datetime, timezone, timedelta
from enum import Enum
import os
import uuid
import secrets
import hashlib
import logging

from sqlalchemy import select

from engines.sql_utils import (
    model_to_dict, apply_updates,
    gd_find, gd_find_one, gd_insert, gd_update_one, gd_count,
)

logger = logging.getLogger("nassaq.teacher_registration")


class TeacherRank(str, Enum):
    EXPERT = "expert"
    ADVANCED = "advanced"
    PRACTITIONER = "practitioner"
    ASSISTANT = "assistant"


class EducationLevel(str, Enum):
    KINDERGARTEN = "kindergarten"
    PRIMARY = "primary"
    INTERMEDIATE = "intermediate"
    SECONDARY = "secondary"
    ALL = "all"


class AcademicDegree(str, Enum):
    HIGH_SCHOOL = "high_school"
    DIPLOMA = "diploma"
    BACHELOR = "bachelor"
    MASTER = "master"
    PHD = "phd"


class SchoolType(str, Enum):
    PUBLIC = "public"
    PRIVATE = "private"
    INTERNATIONAL = "international"


class RequestStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    MORE_INFO_REQUIRED = "more_info"
    EXPIRED = "expired"


class InviteStatus(str, Enum):
    SENT = "sent"
    OPENED = "opened"
    REGISTERED = "registered"
    EXPIRED = "expired"


class TeacherRegistrationEngine:
    def __init__(self, db):
        self.db = db
        self.REVIEW_TIMEOUT_HOURS = 24

    @property
    def session(self):
        return self.db.session

    async def create_registration_request(
        self,
        full_name: str,
        national_id: str,
        phone: str,
        email: str,
        subject: str,
        education_level: str,
        years_of_experience: int,
        academic_degree: str,
        teacher_rank: str,
        school_name: str,
        school_country: str,
        school_city: str,
        school_type: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        referred_by: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        from pg_models import User

        pending_statuses = [RequestStatus.PENDING.value, RequestStatus.MORE_INFO_REQUIRED.value]

        existing_email = await gd_find_one(self.session, "teacher_registration_requests", {"email": email})
        if existing_email and existing_email.get("status") in pending_statuses:
            raise ValueError("يوجد طلب معلق بنفس البريد الإلكتروني")

        existing_phone = await gd_find_one(self.session, "teacher_registration_requests", {"phone": phone})
        if existing_phone and existing_phone.get("status") in pending_statuses:
            raise ValueError("يوجد طلب معلق بنفس رقم الهاتف")

        from sqlalchemy import or_
        stmt = select(User).where(
            or_(User.email == email, User.phone == phone)
        ).limit(1)
        result = await self.session.execute(stmt)
        existing_user = result.scalars().first()

        has_existing_account = existing_user is not None
        existing_role = existing_user.role if existing_user else None
        existing_user_id = existing_user.id if existing_user else None

        request_id = str(uuid.uuid4())
        tracking_code = self._generate_tracking_code()

        now = datetime.now(timezone.utc)
        review_deadline = now + timedelta(hours=self.REVIEW_TIMEOUT_HOURS)

        request_doc = {
            "id": request_id,
            "tracking_code": tracking_code,
            "full_name": full_name,
            "national_id": national_id,
            "phone": phone,
            "email": email,
            "subject": subject,
            "education_level": education_level,
            "years_of_experience": years_of_experience,
            "academic_degree": academic_degree,
            "teacher_rank": teacher_rank,
            "school_name": school_name,
            "school_country": school_country,
            "school_city": school_city,
            "school_type": school_type,
            "status": RequestStatus.PENDING.value,
            "review_deadline": review_deadline.isoformat(),
            "has_existing_account": has_existing_account,
            "existing_role": existing_role,
            "existing_user_id": existing_user_id,
            "referred_by": referred_by,
            "ip_address": ip_address,
            "user_agent": user_agent,
            "device_fingerprint": self._generate_device_fingerprint(ip_address, user_agent),
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
            "admin_notes": [],
            "more_info_requests": []
        }

        await gd_insert(self.session, "teacher_registration_requests", request_doc)

        await self._log_audit(
            action="teacher_registration_request_created",
            entity_type="registration_request",
            entity_id=request_id,
            details={"email": email, "tracking_code": tracking_code}
        )

        try:
            from routes.websocket_routes import get_connection_manager, send_realtime_notification
            ws_manager = get_connection_manager()
            await send_realtime_notification(
                manager=ws_manager,
                db=self.db,
                notification_type="teacher_request",
                message_ar=f"طلب تسجيل جديد من {full_name} - {email}",
                message_en=f"New registration request from {full_name} - {email}",
                target_roles=["platform_admin", "platform_operations_manager"],
                extra_data={
                    "request_id": request_id,
                    "tracking_code": tracking_code,
                    "teacher_name": full_name,
                    "teacher_email": email,
                    "action_url": "/admin/users?tab=requests"
                },
                save_to_db=True
            )
        except Exception as e:
            logger.warning(f"Failed to send real-time notification: {e}")

        await self._save_pending_school(
            school_name=school_name,
            country=school_country,
            city=school_city,
            school_type=school_type,
            submitted_by_request=request_id
        )

        if referred_by:
            await self._update_referral_status(referred_by, request_id)

        return {
            "id": request_id,
            "tracking_code": tracking_code,
            "status": RequestStatus.PENDING.value,
            "review_deadline": review_deadline.isoformat(),
            "message": "تم استلام طلبك بنجاح وهو قيد المراجعة"
        }

    async def get_request_status(
        self,
        tracking_code: Optional[str] = None,
        request_id: Optional[str] = None,
        device_fingerprint: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        filters = {}
        if tracking_code:
            filters["tracking_code"] = tracking_code
        elif request_id:
            filters["id"] = request_id
        elif device_fingerprint:
            filters["device_fingerprint"] = device_fingerprint
        else:
            return None

        request = await gd_find_one(self.session, "teacher_registration_requests", filters)
        if not request:
            return None

        deadline = datetime.fromisoformat(request["review_deadline"].replace('Z', '+00:00'))
        now = datetime.now(timezone.utc)
        remaining = deadline - now
        remaining_seconds = max(0, int(remaining.total_seconds()))

        return {
            "id": request["id"],
            "tracking_code": request["tracking_code"],
            "full_name": request["full_name"],
            "status": request["status"],
            "review_deadline": request["review_deadline"],
            "remaining_seconds": remaining_seconds,
            "remaining_formatted": self._format_remaining_time(remaining_seconds),
            "created_at": request["created_at"],
            "more_info_requests": request.get("more_info_requests", []),
            "admin_notes": request.get("admin_notes", [])
        }

    async def get_pending_requests(
        self,
        status: Optional[str] = None,
        limit: int = 100,
        skip: int = 0
    ) -> List[Dict[str, Any]]:
        if status:
            all_requests = await gd_find(self.session, "teacher_registration_requests", {"status": status}, order_by="created_at", desc_order=True, limit=limit + skip)
        else:
            all_requests = await gd_find(self.session, "teacher_registration_requests", {}, order_by="created_at", desc_order=True, limit=limit + skip + 500)
            all_requests = [r for r in all_requests if r.get("status") in [RequestStatus.PENDING.value, RequestStatus.MORE_INFO_REQUIRED.value]]

        return all_requests[skip:skip + limit]

    async def approve_request(
        self,
        request_id: str,
        approved_by: str,
        generate_password: bool = True
    ) -> Dict[str, Any]:
        from pg_models import User

        request = await gd_find_one(self.session, "teacher_registration_requests", {"id": request_id})
        if not request:
            raise ValueError("الطلب غير موجود")
        if request["status"] == RequestStatus.APPROVED.value:
            raise ValueError("تم قبول هذا الطلب مسبقاً")

        now = datetime.now(timezone.utc)
        temp_password = secrets.token_urlsafe(12) if generate_password else None

        if request.get("has_existing_account") and request.get("existing_user_id"):
            user_id = request["existing_user_id"]
            stmt = select(User).where(User.id == user_id).limit(1)
            result = await self.session.execute(stmt)
            user_obj = result.scalars().first()
            if user_obj:
                roles = user_obj.linked_roles or []
                if "teacher" not in roles:
                    roles.append("teacher")
                user_obj.linked_roles = roles
                user_obj.updated_at = now
                if hasattr(user_obj, "data"):
                    current = dict(user_obj.data) if user_obj.data else {}
                    current["teacher_info"] = {
                        "subject": request["subject"],
                        "education_level": request["education_level"],
                        "years_of_experience": request["years_of_experience"],
                        "academic_degree": request["academic_degree"],
                        "teacher_rank": request["teacher_rank"],
                        "teacher_id": self._generate_teacher_id()
                    }
                    user_obj.data = current
                await self.session.flush()
            created_user = model_to_dict(user_obj) if user_obj else {}
        else:
            import bcrypt
            user_id = str(uuid.uuid4())
            teacher_id = self._generate_teacher_id()

            user_obj = User(
                id=user_id,
                email=request["email"],
                password_hash=bcrypt.hashpw(temp_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8'),
                full_name=request["full_name"],
                phone=request["phone"],
                role="teacher",
                is_active=True,
                created_at=now,
                updated_at=now,
            )

            extra = {
                "national_id": request["national_id"],
                "roles": ["teacher"],
                "teacher_id": teacher_id,
                "teacher_info": {
                    "subject": request["subject"],
                    "education_level": request["education_level"],
                    "years_of_experience": request["years_of_experience"],
                    "academic_degree": request["academic_degree"],
                    "teacher_rank": request["teacher_rank"],
                    "teacher_id": teacher_id
                },
                "account_type": "independent_teacher",
                "account_status": "active",
                "preferred_language": "ar",
                "created_from_request": request_id
            }
            if hasattr(user_obj, "data"):
                user_obj.data = extra

            self.session.add(user_obj)
            await self.session.flush()
            created_user = model_to_dict(user_obj)

        await gd_update_one(self.session, "teacher_registration_requests", {"id": request_id}, {
            "status": RequestStatus.APPROVED.value,
            "approved_at": now.isoformat(),
            "approved_by": approved_by,
            "created_user_id": user_id,
            "updated_at": now.isoformat()
        })

        await self._log_audit(
            action="teacher_registration_approved",
            entity_type="registration_request",
            entity_id=request_id,
            performed_by=approved_by,
            details={"user_id": user_id}
        )

        if request.get("referred_by"):
            await self._grant_referral_reward(request["referred_by"])

        return {
            "message": "تم قبول الطلب وإنشاء الحساب بنجاح",
            "user_id": user_id,
            "temp_password": temp_password,
            "email": request["email"],
            "is_unified_identity": request.get("has_existing_account", False)
        }

    async def reject_request(
        self,
        request_id: str,
        rejected_by: str,
        reason: str
    ) -> Dict[str, Any]:
        request = await gd_find_one(self.session, "teacher_registration_requests", {"id": request_id})
        if not request:
            raise ValueError("الطلب غير موجود")

        now = datetime.now(timezone.utc)

        await gd_update_one(self.session, "teacher_registration_requests", {"id": request_id}, {
            "status": RequestStatus.REJECTED.value,
            "rejected_at": now.isoformat(),
            "rejected_by": rejected_by,
            "rejection_reason": reason,
            "updated_at": now.isoformat()
        })

        await self._log_audit(
            action="teacher_registration_rejected",
            entity_type="registration_request",
            entity_id=request_id,
            performed_by=rejected_by,
            details={"reason": reason}
        )

        return {"message": "تم رفض الطلب"}

    async def request_more_info(
        self,
        request_id: str,
        requested_by: str,
        questions: List[str]
    ) -> Dict[str, Any]:
        request = await gd_find_one(self.session, "teacher_registration_requests", {"id": request_id})
        if not request:
            raise ValueError("الطلب غير موجود")

        now = datetime.now(timezone.utc)

        more_info_request = {
            "id": str(uuid.uuid4()),
            "questions": questions,
            "requested_by": requested_by,
            "requested_at": now.isoformat(),
            "answered": False
        }

        existing_requests = request.get("more_info_requests", [])
        if isinstance(existing_requests, list):
            existing_requests.append(more_info_request)
        else:
            existing_requests = [more_info_request]

        await gd_update_one(self.session, "teacher_registration_requests", {"id": request_id}, {
            "status": RequestStatus.MORE_INFO_REQUIRED.value,
            "updated_at": now.isoformat(),
            "more_info_requests": existing_requests
        })

        return {
            "message": "تم إرسال طلب المعلومات الإضافية",
            "info_request_id": more_info_request["id"]
        }

    async def create_invite(
        self,
        inviter_id: str,
        invitee_name: str,
        invitee_email: str,
        invitee_phone: Optional[str] = None
    ) -> Dict[str, Any]:
        all_invites = await gd_find(self.session, "teacher_invites", {"invitee_email": invitee_email}, limit=10)
        existing = next((i for i in all_invites if i.get("status") in [InviteStatus.SENT.value, InviteStatus.OPENED.value]), None)

        if existing:
            raise ValueError("تم دعوة هذا المعلم مسبقاً")

        invite_id = str(uuid.uuid4())
        invite_code = secrets.token_urlsafe(16)
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(days=30)

        invite_doc = {
            "id": invite_id,
            "invite_code": invite_code,
            "inviter_id": inviter_id,
            "invitee_name": invitee_name,
            "invitee_email": invitee_email,
            "invitee_phone": invitee_phone,
            "status": InviteStatus.SENT.value,
            "created_at": now.isoformat(),
            "expires_at": expires_at.isoformat(),
            "opened_at": None,
            "registered_at": None,
            "registered_user_id": None
        }

        await gd_insert(self.session, "teacher_invites", invite_doc)

        return {
            "invite_id": invite_id,
            "invite_code": invite_code,
            "invite_url": f"{os.environ.get('FRONTEND_URL', 'https://nassaq.com')}/register?invite={invite_code}",
            "message": "تم إرسال الدعوة بنجاح"
        }

    async def get_invite_by_code(self, invite_code: str) -> Optional[Dict[str, Any]]:
        invite = await gd_find_one(self.session, "teacher_invites", {"invite_code": invite_code})
        if invite and invite.get("status") == InviteStatus.SENT.value:
            await gd_update_one(self.session, "teacher_invites", {"id": invite["id"]}, {
                "status": InviteStatus.OPENED.value,
                "opened_at": datetime.now(timezone.utc).isoformat()
            })
        return invite

    async def get_user_invites(self, user_id: str) -> List[Dict[str, Any]]:
        return await gd_find(self.session, "teacher_invites", {"inviter_id": user_id}, order_by="created_at", desc_order=True, limit=100)

    async def get_invite_stats(self, user_id: str) -> Dict[str, Any]:
        invites = await self.get_user_invites(user_id)

        total = len(invites)
        sent = len([i for i in invites if i.get("status") == InviteStatus.SENT.value])
        opened = len([i for i in invites if i.get("status") == InviteStatus.OPENED.value])
        registered = len([i for i in invites if i.get("status") == InviteStatus.REGISTERED.value])

        return {
            "total_invites": total,
            "sent": sent,
            "opened": opened,
            "registered": registered,
            "reward_months_earned": registered
        }

    async def _save_pending_school(
        self,
        school_name: str,
        country: str,
        city: str,
        school_type: str,
        submitted_by_request: str
    ):
        existing = await gd_find_one(self.session, "pending_schools", {"name": school_name, "city": city})

        if existing:
            count = existing.get("teacher_requests_count", 0) + 1
            submitted = existing.get("submitted_by_requests", [])
            if isinstance(submitted, list) and submitted_by_request not in submitted:
                submitted.append(submitted_by_request)
            await gd_update_one(self.session, "pending_schools", {"id": existing["id"]}, {
                "teacher_requests_count": count,
                "submitted_by_requests": submitted
            })
        else:
            school_doc = {
                "id": str(uuid.uuid4()),
                "name": school_name,
                "country": country,
                "city": city,
                "school_type": school_type,
                "teacher_requests_count": 1,
                "submitted_by_requests": [submitted_by_request],
                "contacted": False,
                "registered": False,
                "created_at": datetime.now(timezone.utc).isoformat()
            }
            await gd_insert(self.session, "pending_schools", school_doc)

    async def get_pending_schools(self, limit: int = 100) -> List[Dict[str, Any]]:
        schools = await gd_find(self.session, "pending_schools", {"registered": False}, order_by="teacher_requests_count", desc_order=True, limit=limit)
        return schools

    def _generate_tracking_code(self) -> str:
        return f"TR-{secrets.token_hex(4).upper()}"

    def _generate_teacher_id(self) -> str:
        import random
        return f"TCH-{random.randint(100000, 999999)}"

    def _generate_device_fingerprint(self, ip_address: Optional[str], user_agent: Optional[str]) -> str:
        data = f"{ip_address or ''}-{user_agent or ''}"
        return hashlib.sha256(data.encode()).hexdigest()[:32]

    def _format_remaining_time(self, seconds: int) -> str:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"

    async def _update_referral_status(self, invite_id: str, request_id: str):
        await gd_update_one(self.session, "teacher_invites", {"id": invite_id}, {
            "status": InviteStatus.REGISTERED.value,
            "registered_at": datetime.now(timezone.utc).isoformat(),
            "registered_request_id": request_id
        })

    async def _grant_referral_reward(self, invite_id: str):
        from pg_models import User
        invite = await gd_find_one(self.session, "teacher_invites", {"id": invite_id})

        if invite:
            inviter_id = invite["inviter_id"]
            stmt = select(User).where(User.id == inviter_id).limit(1)
            result = await self.session.execute(stmt)
            user_obj = result.scalars().first()
            if user_obj and hasattr(user_obj, "data"):
                current = dict(user_obj.data) if user_obj.data else {}
                current["free_months_balance"] = current.get("free_months_balance", 0) + 1
                rewards = current.get("rewards", [])
                if not isinstance(rewards, list):
                    rewards = []
                rewards.append({
                    "type": "referral",
                    "amount": 1,
                    "unit": "month",
                    "reason": "successful_teacher_referral",
                    "granted_at": datetime.now(timezone.utc).isoformat()
                })
                current["rewards"] = rewards
                user_obj.data = current
                await self.session.flush()

    async def _log_audit(
        self,
        action: str,
        entity_type: str,
        entity_id: str,
        performed_by: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        from pg_models import AuditLog
        log_obj = AuditLog(
            id=str(uuid.uuid4()),
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            performed_by=performed_by,
            created_at=datetime.now(timezone.utc),
        )
        if hasattr(log_obj, "data"):
            log_obj.data = {"details": details or {}}
        self.session.add(log_obj)
        await self.session.flush()


__all__ = [
    "TeacherRegistrationEngine",
    "TeacherRank",
    "EducationLevel",
    "AcademicDegree",
    "SchoolType",
    "RequestStatus",
    "InviteStatus"
]
