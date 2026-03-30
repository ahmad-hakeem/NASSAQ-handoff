"""
NASSAQ Unified Approval Engine
محرك الموافقات الموحد لمنصة نَسَّق

A centralized, extensible approval framework that handles any registration
request type through a handler registry pattern.

Supported request types (extensible):
- school: New school registration
- teacher / independent_teacher: Independent teacher registration
- parent: Parent account request (future)
- staff: Staff member request (future)
- organization: External organization (future)
- partner: External partner (future)

Architecture:
- ApprovalEngine: Central dispatcher with handler registry
- ApprovalHandler: Protocol for type-specific approval logic
- Each handler implements approve() which creates the active entity
- Rejection and info-request are type-agnostic (handled by engine)
"""

from typing import Optional, Dict, Any, Callable, Awaitable
from datetime import datetime, timezone
from dataclasses import dataclass, field
import uuid
import logging

logger = logging.getLogger("nassaq.approval")


def _get_db():
    from dependencies import db
    return db


PENDING_STATUSES = {"pending", "pending_review", "info_required", "more_info_requested"}
TERMINAL_STATUSES = {"approved", "rejected"}


@dataclass
class ApprovalResult:
    success: bool
    message: str
    request_type: str
    created_entities: Dict[str, Any] = field(default_factory=dict)
    credentials: Optional[Dict[str, str]] = None
    message_template: Optional[str] = None


class ApprovalHandler:
    request_type: str
    display_name: str
    display_name_ar: str

    async def validate_before_approve(self, request: dict) -> Optional[str]:
        return None

    async def create_entities(self, request: dict, approved_by: dict) -> ApprovalResult:
        raise NotImplementedError

    def get_display_fields(self) -> list:
        return ["full_name", "email", "phone", "created_at"]


class ApprovalEngine:
    def __init__(self):
        self._handlers: Dict[str, ApprovalHandler] = {}

    def register(self, handler: ApprovalHandler):
        self._handlers[handler.request_type] = handler
        logger.info(f"Registered approval handler: {handler.request_type} ({handler.display_name_ar})")

    def get_handler(self, request_type: str) -> Optional[ApprovalHandler]:
        return self._handlers.get(request_type)

    def get_registered_types(self) -> list:
        return [
            {
                "type": h.request_type,
                "name": h.display_name,
                "name_ar": h.display_name_ar,
                "display_fields": h.get_display_fields(),
            }
            for h in self._handlers.values()
        ]

    async def approve(self, request_id: str, current_user: dict) -> ApprovalResult:
        database = _get_db()
        request = await database.registration_requests.find_one({"id": request_id}, {"_id": 0})
        if not request:
            return ApprovalResult(success=False, message="طلب التسجيل غير موجود", request_type="unknown")

        request_type = request.get("account_type", "")
        handler = self.get_handler(request_type)
        if not handler:
            return ApprovalResult(
                success=False,
                message=f"نوع الطلب '{request_type}' غير مدعوم حالياً",
                request_type=request_type,
            )

        status = request.get("status", "")
        if status not in PENDING_STATUSES:
            return ApprovalResult(
                success=False,
                message="هذا الطلب تم معالجته مسبقاً",
                request_type=request_type,
            )

        validation_error = await handler.validate_before_approve(request)
        if validation_error:
            return ApprovalResult(success=False, message=validation_error, request_type=request_type)

        result = await handler.create_entities(request, current_user)
        if not result.success:
            return result

        now = datetime.now(timezone.utc).isoformat()
        await database.registration_requests.update_one(
            {"id": request_id},
            {
                "$set": {
                    "status": "approved",
                    "approved_by": current_user.get("id", current_user.get("user_id")),
                    "approved_by_name": current_user.get("full_name"),
                    "approved_at": now,
                    "updated_at": now,
                    **{f"linked_{k}": v for k, v in result.created_entities.items()},
                }
            },
        )

        audit_log = {
            "id": str(uuid.uuid4()),
            "action": f"request_approved_{request_type}",
            "action_by": current_user.get("id", current_user.get("user_id")),
            "action_by_name": current_user.get("full_name", ""),
            "target_type": "registration_request",
            "target_id": request_id,
            "target_name": request.get("full_name") or request.get("school_name", ""),
            "details": {
                "request_type": request_type,
                **result.created_entities,
            },
            "timestamp": now,
        }
        await database.audit_logs.insert_one(audit_log)

        logger.info(
            f"Request approved: type={request_type}, id={request_id}, "
            f"entities={list(result.created_entities.keys())}"
        )
        return result

    async def reject(self, request_id: str, reason: str, current_user: dict) -> dict:
        database = _get_db()
        request = await database.registration_requests.find_one({"id": request_id}, {"_id": 0})
        if not request:
            return {"success": False, "detail": "طلب التسجيل غير موجود"}

        if request.get("status") in TERMINAL_STATUSES:
            return {"success": False, "detail": "لا يمكن رفض طلب تم معالجته مسبقاً"}

        now = datetime.now(timezone.utc).isoformat()
        request_type = request.get("account_type", "unknown")

        await database.registration_requests.update_one(
            {"id": request_id},
            {
                "$set": {
                    "status": "rejected",
                    "rejection_reason": reason,
                    "rejected_by": current_user.get("id", current_user.get("user_id")),
                    "rejected_by_name": current_user.get("full_name"),
                    "rejected_at": now,
                    "updated_at": now,
                }
            },
        )

        audit_log = {
            "id": str(uuid.uuid4()),
            "action": f"request_rejected_{request_type}",
            "action_by": current_user.get("id", current_user.get("user_id")),
            "action_by_name": current_user.get("full_name", ""),
            "target_type": "registration_request",
            "target_id": request_id,
            "target_name": request.get("full_name") or request.get("school_name", ""),
            "details": {"request_type": request_type, "reason": reason},
            "timestamp": now,
        }
        await database.audit_logs.insert_one(audit_log)

        logger.info(f"Request rejected: type={request_type}, id={request_id}")
        return {"success": True, "message": "تم رفض الطلب بنجاح", "rejection_reason": reason}

    async def request_info(self, request_id: str, message: str, current_user: dict) -> dict:
        database = _get_db()
        request = await database.registration_requests.find_one({"id": request_id}, {"_id": 0})
        if not request:
            return {"success": False, "detail": "طلب التسجيل غير موجود"}

        if request.get("status") in TERMINAL_STATUSES:
            return {"success": False, "detail": "لا يمكن طلب معلومات لطلب تم معالجته"}

        now = datetime.now(timezone.utc).isoformat()
        request_type = request.get("account_type", "unknown")

        await database.registration_requests.update_one(
            {"id": request_id},
            {
                "$set": {
                    "status": "info_required",
                    "additional_info_request": message,
                    "info_requested_by": current_user.get("id", current_user.get("user_id")),
                    "info_requested_by_name": current_user.get("full_name"),
                    "info_requested_at": now,
                    "updated_at": now,
                }
            },
        )

        audit_log = {
            "id": str(uuid.uuid4()),
            "action": f"request_info_requested_{request_type}",
            "action_by": current_user.get("id", current_user.get("user_id")),
            "action_by_name": current_user.get("full_name", ""),
            "target_type": "registration_request",
            "target_id": request_id,
            "target_name": request.get("full_name") or request.get("school_name", ""),
            "details": {"request_type": request_type, "message": message},
            "timestamp": now,
        }
        await database.audit_logs.insert_one(audit_log)

        return {"success": True, "message": "تم إرسال طلب المعلومات الإضافية"}


approval_engine = ApprovalEngine()
