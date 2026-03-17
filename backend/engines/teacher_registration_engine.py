"""
NASSAQ Teacher Registration Engine
محرك طلبات تسجيل المعلمين المستقلين لمنصة نَسَّق

Handles:
- Teacher self-registration requests
- Multi-step registration wizard data
- Teacher ranks and professional info
- School data for non-registered schools
- Teacher referral/invite system
- Unified identity (teacher + parent)
- Request review workflow
"""

from typing import Optional, List, Dict, Any
from datetime import datetime, timezone, timedelta
from enum import Enum
import uuid
import secrets
import hashlib
import logging

logger = logging.getLogger("nassaq.teacher_registration")


class TeacherRank(str, Enum):
    """رتب المعلمين"""
    EXPERT = "expert"           # معلم خبير
    ADVANCED = "advanced"       # معلم متقدم
    PRACTITIONER = "practitioner"  # معلم ممارس
    ASSISTANT = "assistant"     # معلم مساعد


class EducationLevel(str, Enum):
    """المراحل التعليمية"""
    KINDERGARTEN = "kindergarten"   # رياض الأطفال
    PRIMARY = "primary"             # ابتدائي
    INTERMEDIATE = "intermediate"   # متوسط
    SECONDARY = "secondary"         # ثانوي
    ALL = "all"                     # جميع المراحل


class AcademicDegree(str, Enum):
    """المؤهلات العلمية"""
    HIGH_SCHOOL = "high_school"     # ثانوية عامة
    DIPLOMA = "diploma"             # دبلوم
    BACHELOR = "bachelor"           # بكالوريوس
    MASTER = "master"               # ماجستير
    PHD = "phd"                     # دكتوراه


class SchoolType(str, Enum):
    """أنواع المدارس"""
    PUBLIC = "public"       # حكومية
    PRIVATE = "private"     # خاصة
    INTERNATIONAL = "international"  # عالمية


class RequestStatus(str, Enum):
    """حالات الطلب"""
    PENDING = "pending"                 # قيد المراجعة
    APPROVED = "approved"               # مقبول
    REJECTED = "rejected"               # مرفوض
    MORE_INFO_REQUIRED = "more_info"    # يحتاج معلومات إضافية
    EXPIRED = "expired"                 # منتهي الصلاحية


class InviteStatus(str, Enum):
    """حالات الدعوة"""
    SENT = "sent"           # مرسلة
    OPENED = "opened"       # تم فتحها
    REGISTERED = "registered"  # تم التسجيل
    EXPIRED = "expired"     # منتهية


class TeacherRegistrationEngine:
    """
    Teacher Self-Registration Engine for NASSAQ
    Manages the complete teacher registration workflow
    """
    
    def __init__(self, db):
        self.db = db
        self.requests_collection = db.teacher_registration_requests
        self.invites_collection = db.teacher_invites
        self.schools_pending_collection = db.pending_schools
        self.audit_collection = db.audit_logs
        
        # Review timeout in hours
        self.REVIEW_TIMEOUT_HOURS = 24
    
    # ============== REGISTRATION REQUEST ==============
    
    async def create_registration_request(
        self,
        # Step 1: Basic Info
        full_name: str,
        national_id: str,
        phone: str,
        email: str,
        # Step 2: Professional Info
        subject: str,
        education_level: str,
        years_of_experience: int,
        academic_degree: str,
        # Step 3: Teacher Rank
        teacher_rank: str,
        # Step 4: School Data
        school_name: str,
        school_country: str,
        school_city: str,
        school_type: str,
        # Metadata
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        referred_by: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Create a new teacher registration request"""
        
        # Check for existing request with same email or phone
        existing_email = await self.requests_collection.find_one({
            "email": email,
            "status": {"$in": ["pending", "more_info"]}
        })
        if existing_email:
            raise ValueError("يوجد طلب معلق بنفس البريد الإلكتروني")
        
        existing_phone = await self.requests_collection.find_one({
            "phone": phone,
            "status": {"$in": ["pending", "more_info"]}
        })
        if existing_phone:
            raise ValueError("يوجد طلب معلق بنفس رقم الهاتف")
        
        # Check if user already exists (for unified identity)
        existing_user = await self.db.users.find_one({
            "$or": [
                {"email": email},
                {"phone": phone}
            ]
        })
        
        has_existing_account = existing_user is not None
        existing_role = existing_user.get("role") if existing_user else None
        
        # Generate request ID and tracking code
        request_id = str(uuid.uuid4())
        tracking_code = self._generate_tracking_code()
        
        now = datetime.now(timezone.utc)
        review_deadline = now + timedelta(hours=self.REVIEW_TIMEOUT_HOURS)
        
        request_doc = {
            "id": request_id,
            "tracking_code": tracking_code,
            
            # Step 1: Basic Info
            "full_name": full_name,
            "national_id": national_id,
            "phone": phone,
            "email": email,
            
            # Step 2: Professional Info
            "subject": subject,
            "education_level": education_level,
            "years_of_experience": years_of_experience,
            "academic_degree": academic_degree,
            
            # Step 3: Teacher Rank
            "teacher_rank": teacher_rank,
            
            # Step 4: School Data
            "school_name": school_name,
            "school_country": school_country,
            "school_city": school_city,
            "school_type": school_type,
            
            # Status
            "status": RequestStatus.PENDING.value,
            "review_deadline": review_deadline.isoformat(),
            
            # Unified Identity
            "has_existing_account": has_existing_account,
            "existing_role": existing_role,
            "existing_user_id": existing_user.get("id") if existing_user else None,
            
            # Referral
            "referred_by": referred_by,
            
            # Tracking
            "ip_address": ip_address,
            "user_agent": user_agent,
            "device_fingerprint": self._generate_device_fingerprint(ip_address, user_agent),
            
            # Timestamps
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
            
            # Admin notes
            "admin_notes": [],
            "more_info_requests": []
        }
        
        await self.requests_collection.insert_one(request_doc)
        
        # Log to audit
        await self._log_audit(
            action="teacher_registration_request_created",
            entity_type="registration_request",
            entity_id=request_id,
            details={"email": email, "tracking_code": tracking_code}
        )
        
        # Send real-time notification to platform admins
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
        
        # Save school data for future outreach
        await self._save_pending_school(
            school_name=school_name,
            country=school_country,
            city=school_city,
            school_type=school_type,
            submitted_by_request=request_id
        )
        
        # Update referral if exists
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
        """Get registration request status"""
        query = {}
        
        if tracking_code:
            query["tracking_code"] = tracking_code
        elif request_id:
            query["id"] = request_id
        elif device_fingerprint:
            query["device_fingerprint"] = device_fingerprint
        else:
            return None
        
        request = await self.requests_collection.find_one(query, {"_id": 0})
        
        if not request:
            return None
        
        # Calculate remaining time
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
        """Get pending registration requests for admin review"""
        query = {}
        
        if status:
            query["status"] = status
        else:
            query["status"] = {"$in": [
                RequestStatus.PENDING.value,
                RequestStatus.MORE_INFO_REQUIRED.value
            ]}
        
        requests = await self.requests_collection.find(
            query,
            {"_id": 0}
        ).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
        
        return requests
    
    async def approve_request(
        self,
        request_id: str,
        approved_by: str,
        generate_password: bool = True
    ) -> Dict[str, Any]:
        """Approve a registration request and create user account"""
        request = await self.requests_collection.find_one(
            {"id": request_id},
            {"_id": 0}
        )
        
        if not request:
            raise ValueError("الطلب غير موجود")
        
        if request["status"] == RequestStatus.APPROVED.value:
            raise ValueError("تم قبول هذا الطلب مسبقاً")
        
        now = datetime.now(timezone.utc)
        
        # Generate credentials
        temp_password = secrets.token_urlsafe(12) if generate_password else None
        
        # Check for unified identity
        if request.get("has_existing_account") and request.get("existing_user_id"):
            # Add teacher role to existing user
            user_id = request["existing_user_id"]
            
            await self.db.users.update_one(
                {"id": user_id},
                {
                    "$addToSet": {"roles": "teacher"},
                    "$set": {
                        "teacher_info": {
                            "subject": request["subject"],
                            "education_level": request["education_level"],
                            "years_of_experience": request["years_of_experience"],
                            "academic_degree": request["academic_degree"],
                            "teacher_rank": request["teacher_rank"],
                            "teacher_id": self._generate_teacher_id()
                        },
                        "updated_at": now.isoformat()
                    }
                }
            )
            
            created_user = await self.db.users.find_one({"id": user_id}, {"_id": 0})
        else:
            # Create new user
            import bcrypt
            user_id = str(uuid.uuid4())
            teacher_id = self._generate_teacher_id()
            
            user_doc = {
                "id": user_id,
                "email": request["email"],
                "password_hash": bcrypt.hashpw(temp_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8'),
                "full_name": request["full_name"],
                "phone": request["phone"],
                "national_id": request["national_id"],
                "role": "teacher",
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
                "is_active": True,
                "account_status": "active",
                "preferred_language": "ar",
                "created_at": now.isoformat(),
                "updated_at": now.isoformat(),
                "created_from_request": request_id
            }
            
            await self.db.users.insert_one(user_doc)
            created_user = {k: v for k, v in user_doc.items() if k != "password_hash"}
        
        # Update request status
        await self.requests_collection.update_one(
            {"id": request_id},
            {
                "$set": {
                    "status": RequestStatus.APPROVED.value,
                    "approved_at": now.isoformat(),
                    "approved_by": approved_by,
                    "created_user_id": user_id,
                    "updated_at": now.isoformat()
                }
            }
        )
        
        # Log audit
        await self._log_audit(
            action="teacher_registration_approved",
            entity_type="registration_request",
            entity_id=request_id,
            performed_by=approved_by,
            details={"user_id": user_id}
        )
        
        # Update referral reward if applicable
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
        """Reject a registration request"""
        request = await self.requests_collection.find_one(
            {"id": request_id},
            {"_id": 0}
        )
        
        if not request:
            raise ValueError("الطلب غير موجود")
        
        now = datetime.now(timezone.utc)
        
        await self.requests_collection.update_one(
            {"id": request_id},
            {
                "$set": {
                    "status": RequestStatus.REJECTED.value,
                    "rejected_at": now.isoformat(),
                    "rejected_by": rejected_by,
                    "rejection_reason": reason,
                    "updated_at": now.isoformat()
                }
            }
        )
        
        # Log audit
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
        """Request more information from applicant"""
        request = await self.requests_collection.find_one(
            {"id": request_id},
            {"_id": 0}
        )
        
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
        
        await self.requests_collection.update_one(
            {"id": request_id},
            {
                "$set": {
                    "status": RequestStatus.MORE_INFO_REQUIRED.value,
                    "updated_at": now.isoformat()
                },
                "$push": {
                    "more_info_requests": more_info_request
                }
            }
        )
        
        return {
            "message": "تم إرسال طلب المعلومات الإضافية",
            "info_request_id": more_info_request["id"]
        }
    
    # ============== TEACHER INVITE SYSTEM ==============
    
    async def create_invite(
        self,
        inviter_id: str,
        invitee_name: str,
        invitee_email: str,
        invitee_phone: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a teacher invite"""
        # Check if already invited
        existing = await self.invites_collection.find_one({
            "invitee_email": invitee_email,
            "status": {"$in": [InviteStatus.SENT.value, InviteStatus.OPENED.value]}
        })
        
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
        
        await self.invites_collection.insert_one(invite_doc)
        
        return {
            "invite_id": invite_id,
            "invite_code": invite_code,
            "invite_url": f"/register?invite={invite_code}",
            "message": "تم إرسال الدعوة بنجاح"
        }
    
    async def get_invite_by_code(self, invite_code: str) -> Optional[Dict[str, Any]]:
        """Get invite by code"""
        invite = await self.invites_collection.find_one(
            {"invite_code": invite_code},
            {"_id": 0}
        )
        
        if invite:
            # Mark as opened
            if invite["status"] == InviteStatus.SENT.value:
                await self.invites_collection.update_one(
                    {"id": invite["id"]},
                    {
                        "$set": {
                            "status": InviteStatus.OPENED.value,
                            "opened_at": datetime.now(timezone.utc).isoformat()
                        }
                    }
                )
        
        return invite
    
    async def get_user_invites(
        self,
        user_id: str
    ) -> List[Dict[str, Any]]:
        """Get all invites sent by a user"""
        invites = await self.invites_collection.find(
            {"inviter_id": user_id},
            {"_id": 0}
        ).sort("created_at", -1).to_list(100)
        
        return invites
    
    async def get_invite_stats(self, user_id: str) -> Dict[str, Any]:
        """Get invite statistics for a user"""
        invites = await self.get_user_invites(user_id)
        
        total = len(invites)
        sent = len([i for i in invites if i["status"] == InviteStatus.SENT.value])
        opened = len([i for i in invites if i["status"] == InviteStatus.OPENED.value])
        registered = len([i for i in invites if i["status"] == InviteStatus.REGISTERED.value])
        
        return {
            "total_invites": total,
            "sent": sent,
            "opened": opened,
            "registered": registered,
            "reward_months_earned": registered  # 1 month per successful referral
        }
    
    # ============== PENDING SCHOOLS ==============
    
    async def _save_pending_school(
        self,
        school_name: str,
        country: str,
        city: str,
        school_type: str,
        submitted_by_request: str
    ):
        """Save school data for future outreach"""
        # Check if school already exists
        existing = await self.schools_pending_collection.find_one({
            "name": school_name,
            "city": city
        })
        
        if existing:
            # Update teacher count
            await self.schools_pending_collection.update_one(
                {"id": existing["id"]},
                {
                    "$inc": {"teacher_requests_count": 1},
                    "$addToSet": {"submitted_by_requests": submitted_by_request}
                }
            )
        else:
            # Create new pending school
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
            await self.schools_pending_collection.insert_one(school_doc)
    
    async def get_pending_schools(
        self,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get pending schools for outreach"""
        schools = await self.schools_pending_collection.find(
            {"registered": False},
            {"_id": 0}
        ).sort("teacher_requests_count", -1).limit(limit).to_list(limit)
        
        return schools
    
    # ============== HELPER METHODS ==============
    
    def _generate_tracking_code(self) -> str:
        """Generate unique tracking code"""
        return f"TR-{secrets.token_hex(4).upper()}"
    
    def _generate_teacher_id(self) -> str:
        """Generate unique teacher ID"""
        import random
        return f"TCH-{random.randint(100000, 999999)}"
    
    def _generate_device_fingerprint(
        self,
        ip_address: Optional[str],
        user_agent: Optional[str]
    ) -> str:
        """Generate device fingerprint for tracking"""
        data = f"{ip_address or ''}-{user_agent or ''}"
        return hashlib.sha256(data.encode()).hexdigest()[:32]
    
    def _format_remaining_time(self, seconds: int) -> str:
        """Format remaining time in Arabic"""
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    
    async def _update_referral_status(
        self,
        invite_id: str,
        request_id: str
    ):
        """Update referral when referred user registers"""
        await self.invites_collection.update_one(
            {"id": invite_id},
            {
                "$set": {
                    "status": InviteStatus.REGISTERED.value,
                    "registered_at": datetime.now(timezone.utc).isoformat(),
                    "registered_request_id": request_id
                }
            }
        )
    
    async def _grant_referral_reward(self, invite_id: str):
        """Grant reward to inviter"""
        invite = await self.invites_collection.find_one(
            {"id": invite_id},
            {"_id": 0}
        )
        
        if invite:
            inviter_id = invite["inviter_id"]
            
            # Add free month to inviter
            await self.db.users.update_one(
                {"id": inviter_id},
                {
                    "$inc": {"free_months_balance": 1},
                    "$push": {
                        "rewards": {
                            "type": "referral",
                            "amount": 1,
                            "unit": "month",
                            "reason": "successful_teacher_referral",
                            "granted_at": datetime.now(timezone.utc).isoformat()
                        }
                    }
                }
            )
    
    async def _log_audit(
        self,
        action: str,
        entity_type: str,
        entity_id: str,
        performed_by: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        """Log audit entry"""
        audit_doc = {
            "id": str(uuid.uuid4()),
            "action": action,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "performed_by": performed_by,
            "details": details or {},
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        await self.audit_collection.insert_one(audit_doc)


# Export
__all__ = [
    "TeacherRegistrationEngine",
    "TeacherRank",
    "EducationLevel",
    "AcademicDegree",
    "SchoolType",
    "RequestStatus",
    "InviteStatus"
]
