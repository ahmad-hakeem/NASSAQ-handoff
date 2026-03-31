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
- Rejection, info-request, under-review, archive are type-agnostic

Status Lifecycle:
  pending_review ──► under_review ──► approved
       │                  │               │
       ├──► approved      ├──► rejected   ├──► archived
       ├──► rejected      ├──► info_required
       ├──► info_required  
       ├──► cancelled     
       │
  info_required ──► pending_review (via submit-info)
       │
       ├──► rejected
       ├──► cancelled
       │
  rejected ──► archived
  approved ──► archived
"""

from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime, timezone
from dataclasses import dataclass, field
import uuid
import logging

logger = logging.getLogger("nassaq.approval")


def _get_db():
    from dependencies import db
    return db


VALID_STATUSES = {
    "pending_review",
    "under_review",
    "info_required",
    "approved",
    "rejected",
    "cancelled",
    "archived",
}

PENDING_STATUSES = {"pending", "pending_review", "info_required", "more_info_requested", "under_review"}
TERMINAL_STATUSES = {"approved", "rejected"}
CLOSED_STATUSES = {"approved", "rejected", "cancelled", "archived"}

VALID_TRANSITIONS: Dict[str, set] = {
    "pending_review": {"under_review", "approved", "rejected", "info_required", "cancelled"},
    "pending":        {"under_review", "approved", "rejected", "info_required", "cancelled"},
    "under_review":   {"approved", "rejected", "info_required"},
    "info_required":  {"pending_review", "rejected", "cancelled"},
    "more_info_requested": {"pending_review", "rejected", "cancelled"},
    "approved":       {"archived"},
    "rejected":       {"archived"},
    "cancelled":      {"archived"},
    "archived":       set(),
}


def validate_transition(current_status: str, target_status: str) -> Tuple[bool, str]:
    allowed = VALID_TRANSITIONS.get(current_status, set())
    if target_status not in allowed:
        return False, f"لا يمكن الانتقال من '{current_status}' إلى '{target_status}'"
    return True, ""


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

    async def verify_after_approve(self, request: dict, result: ApprovalResult) -> Optional[str]:
        return None

    def get_display_fields(self) -> list:
        return ["full_name", "email", "phone", "created_at"]


async def _emit_event(database, event_type: str, request_id: str, request_type: str, *,
                       reviewer_id: str = None, status_before: str = None,
                       status_after: str = None, result: str = "success",
                       error_code: str = None, details: dict = None):
    event = {
        "id": str(uuid.uuid4()),
        "event_type": event_type,
        "entity_type": "approval_request",
        "request_id": request_id,
        "request_type": request_type,
        "reviewer_id": reviewer_id,
        "status_before": status_before,
        "status_after": status_after,
        "result": result,
        "error_code": error_code,
        "details": details or {},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    try:
        await database.approval_events.insert_one(event)
    except Exception as e:
        logger.error(f"Failed to emit approval event {event_type}: {e}")


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

    async def _get_request(self, request_id: str):
        database = _get_db()
        request = await database.registration_requests.find_one({"id": request_id}, {"_id": 0})
        return database, request

    def _user_id(self, user: dict) -> str:
        return user.get("id", user.get("user_id", ""))

    async def _write_audit(self, database, action: str, current_user: dict,
                            request: dict, request_type: str, extra_details: dict = None):
        audit_log = {
            "id": str(uuid.uuid4()),
            "action": action,
            "action_by": self._user_id(current_user),
            "action_by_name": current_user.get("full_name", ""),
            "action_by_role": current_user.get("role", ""),
            "target_type": "registration_request",
            "target_id": request.get("id", ""),
            "target_name": request.get("full_name") or request.get("school_name", ""),
            "details": {
                "request_type": request_type,
                "status_before": request.get("status"),
                **(extra_details or {}),
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        await database.audit_logs.insert_one(audit_log)

    async def approve(self, request_id: str, current_user: dict, notes: str = "") -> ApprovalResult:
        database, request = await self._get_request(request_id)
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

        current_status = request.get("status", "")
        valid, err_msg = validate_transition(current_status, "approved")
        if not valid:
            return ApprovalResult(success=False, message=err_msg, request_type=request_type)

        validation_error = await handler.validate_before_approve(request)
        if validation_error:
            await _emit_event(database, "approval_request_validation_failed", request_id, request_type,
                              reviewer_id=self._user_id(current_user),
                              status_before=current_status, result="failed",
                              error_code="validation_failed", details={"reason": validation_error})
            return ApprovalResult(success=False, message=validation_error, request_type=request_type)

        await _emit_event(database, "approval_activation_started", request_id, request_type,
                          reviewer_id=self._user_id(current_user), status_before=current_status)

        try:
            result = await handler.create_entities(request, current_user)
        except Exception as exc:
            logger.error(f"Activation failed for request {request_id}: {exc}")
            await _emit_event(database, "approval_activation_failed", request_id, request_type,
                              reviewer_id=self._user_id(current_user),
                              status_before=current_status, result="error",
                              error_code="activation_exception", details={"error": str(exc)})
            return ApprovalResult(success=False, message="فشل في تفعيل الكيان — يرجى المحاولة لاحقاً", request_type=request_type)

        if not result.success:
            await _emit_event(database, "approval_activation_failed", request_id, request_type,
                              reviewer_id=self._user_id(current_user),
                              status_before=current_status, result="failed",
                              error_code="handler_failed", details={"message": result.message})
            return result

        verification_error = await handler.verify_after_approve(request, result)
        if verification_error:
            logger.error(f"Post-approval verification failed for {request_id}: {verification_error}")
            await _emit_event(database, "approval_activation_failed", request_id, request_type,
                              reviewer_id=self._user_id(current_user),
                              status_before=current_status, result="failed",
                              error_code="verification_failed", details={"reason": verification_error})
            return ApprovalResult(
                success=False,
                message=f"فشل التحقق بعد الموافقة: {verification_error}",
                request_type=request_type,
            )

        now = datetime.now(timezone.utc).isoformat()
        linked_fields = {f"linked_{k}": v for k, v in result.created_entities.items()}
        linked_fields["linked_entity_type"] = request_type
        if result.created_entities.get("school_id"):
            linked_fields["linked_entity_id"] = result.created_entities["school_id"]
        elif result.created_entities.get("user_id"):
            linked_fields["linked_entity_id"] = result.created_entities["user_id"]

        update_result = await database.registration_requests.update_one(
            {"id": request_id, "status": current_status},
            {
                "$set": {
                    "status": "approved",
                    "review_notes": notes,
                    "approved_by": self._user_id(current_user),
                    "approved_by_name": current_user.get("full_name"),
                    "approved_at": now,
                    "reviewed_at": now,
                    "reviewed_by": self._user_id(current_user),
                    "updated_at": now,
                    **linked_fields,
                }
            },
        )
        if update_result.modified_count == 0:
            logger.warning(f"Concurrent transition detected for request {request_id}")
            await _emit_event(database, "approval_activation_failed", request_id, request_type,
                              reviewer_id=self._user_id(current_user),
                              status_before=current_status, result="failed",
                              error_code="concurrent_transition")
            return ApprovalResult(
                success=False,
                message="الطلب تغيّرت حالته — يرجى تحديث الصفحة والمحاولة مرة أخرى",
                request_type=request_type,
            )

        await self._write_audit(database, f"request_approved_{request_type}", current_user,
                                 request, request_type, {**result.created_entities, "notes": notes})
        await _emit_event(database, "approval_request_approved", request_id, request_type,
                          reviewer_id=self._user_id(current_user),
                          status_before=current_status, status_after="approved")
        await _emit_event(database, "approval_activation_completed", request_id, request_type,
                          reviewer_id=self._user_id(current_user),
                          status_after="approved",
                          details={"entities": list(result.created_entities.keys())})

        logger.info(
            f"Request approved: type={request_type}, id={request_id}, "
            f"entities={list(result.created_entities.keys())}"
        )
        return result

    async def reject(self, request_id: str, reason: str, current_user: dict) -> dict:
        database, request = await self._get_request(request_id)
        if not request:
            return {"success": False, "detail": "طلب التسجيل غير موجود"}

        current_status = request.get("status", "")
        valid, err_msg = validate_transition(current_status, "rejected")
        if not valid:
            return {"success": False, "detail": err_msg}

        now = datetime.now(timezone.utc).isoformat()
        request_type = request.get("account_type", "unknown")

        update_result = await database.registration_requests.update_one(
            {"id": request_id, "status": current_status},
            {
                "$set": {
                    "status": "rejected",
                    "rejection_reason": reason,
                    "review_notes": reason,
                    "rejected_by": self._user_id(current_user),
                    "rejected_by_name": current_user.get("full_name"),
                    "rejected_at": now,
                    "reviewed_at": now,
                    "reviewed_by": self._user_id(current_user),
                    "updated_at": now,
                }
            },
        )
        if update_result.modified_count == 0:
            return {"success": False, "detail": "الطلب تغيّرت حالته — يرجى تحديث الصفحة والمحاولة مرة أخرى"}

        await self._write_audit(database, f"request_rejected_{request_type}", current_user,
                                 request, request_type, {"reason": reason})
        await _emit_event(database, "approval_request_rejected", request_id, request_type,
                          reviewer_id=self._user_id(current_user),
                          status_before=current_status, status_after="rejected",
                          details={"reason": reason})

        logger.info(f"Request rejected: type={request_type}, id={request_id}")
        return {"success": True, "message": "تم رفض الطلب بنجاح", "rejection_reason": reason}

    async def request_info(self, request_id: str, message: str, current_user: dict) -> dict:
        database, request = await self._get_request(request_id)
        if not request:
            return {"success": False, "detail": "طلب التسجيل غير موجود"}

        current_status = request.get("status", "")
        valid, err_msg = validate_transition(current_status, "info_required")
        if not valid:
            return {"success": False, "detail": err_msg}

        now = datetime.now(timezone.utc).isoformat()
        request_type = request.get("account_type", "unknown")

        update_result = await database.registration_requests.update_one(
            {"id": request_id, "status": current_status},
            {
                "$set": {
                    "status": "info_required",
                    "additional_info_request": message,
                    "info_requested_by": self._user_id(current_user),
                    "info_requested_by_name": current_user.get("full_name"),
                    "info_requested_at": now,
                    "updated_at": now,
                }
            },
        )
        if update_result.modified_count == 0:
            return {"success": False, "detail": "الطلب تغيّرت حالته — يرجى تحديث الصفحة والمحاولة مرة أخرى"}

        await self._write_audit(database, f"request_info_requested_{request_type}", current_user,
                                 request, request_type, {"message": message})
        await _emit_event(database, "approval_request_info_requested", request_id, request_type,
                          reviewer_id=self._user_id(current_user),
                          status_before=current_status, status_after="info_required")

        return {"success": True, "message": "تم إرسال طلب المعلومات الإضافية"}

    async def mark_under_review(self, request_id: str, notes: str, current_user: dict) -> dict:
        database, request = await self._get_request(request_id)
        if not request:
            return {"success": False, "detail": "طلب التسجيل غير موجود"}

        current_status = request.get("status", "")
        valid, err_msg = validate_transition(current_status, "under_review")
        if not valid:
            return {"success": False, "detail": err_msg}

        now = datetime.now(timezone.utc).isoformat()
        request_type = request.get("account_type", "unknown")

        update_result = await database.registration_requests.update_one(
            {"id": request_id, "status": current_status},
            {
                "$set": {
                    "status": "under_review",
                    "review_notes": notes,
                    "under_review_by": self._user_id(current_user),
                    "under_review_by_name": current_user.get("full_name"),
                    "under_review_at": now,
                    "updated_at": now,
                }
            },
        )
        if update_result.modified_count == 0:
            return {"success": False, "detail": "الطلب تغيّرت حالته — يرجى تحديث الصفحة والمحاولة مرة أخرى"}

        await self._write_audit(database, f"request_under_review_{request_type}", current_user,
                                 request, request_type, {"notes": notes})
        await _emit_event(database, "approval_request_under_review", request_id, request_type,
                          reviewer_id=self._user_id(current_user),
                          status_before=current_status, status_after="under_review",
                          details={"notes": notes})

        logger.info(f"Request under review: type={request_type}, id={request_id}")
        return {"success": True, "message": "تم وضع الطلب تحت المراجعة"}

    async def archive(self, request_id: str, current_user: dict) -> dict:
        database, request = await self._get_request(request_id)
        if not request:
            return {"success": False, "detail": "طلب التسجيل غير موجود"}

        current_status = request.get("status", "")
        valid, err_msg = validate_transition(current_status, "archived")
        if not valid:
            return {"success": False, "detail": err_msg}

        now = datetime.now(timezone.utc).isoformat()
        request_type = request.get("account_type", "unknown")

        update_result = await database.registration_requests.update_one(
            {"id": request_id, "status": current_status},
            {
                "$set": {
                    "status": "archived",
                    "archived_by": self._user_id(current_user),
                    "archived_by_name": current_user.get("full_name"),
                    "archived_at": now,
                    "updated_at": now,
                }
            },
        )
        if update_result.modified_count == 0:
            return {"success": False, "detail": "الطلب تغيّرت حالته — يرجى تحديث الصفحة والمحاولة مرة أخرى"}

        await self._write_audit(database, f"request_archived_{request_type}", current_user,
                                 request, request_type)
        await _emit_event(database, "approval_request_archived", request_id, request_type,
                          reviewer_id=self._user_id(current_user),
                          status_before=current_status, status_after="archived")

        logger.info(f"Request archived: type={request_type}, id={request_id}")
        return {"success": True, "message": "تم أرشفة الطلب"}

    async def cancel(self, request_id: str, reason: str, current_user: dict) -> dict:
        database, request = await self._get_request(request_id)
        if not request:
            return {"success": False, "detail": "طلب التسجيل غير موجود"}

        current_status = request.get("status", "")
        valid, err_msg = validate_transition(current_status, "cancelled")
        if not valid:
            return {"success": False, "detail": err_msg}

        now = datetime.now(timezone.utc).isoformat()
        request_type = request.get("account_type", "unknown")

        update_result = await database.registration_requests.update_one(
            {"id": request_id, "status": current_status},
            {
                "$set": {
                    "status": "cancelled",
                    "cancellation_reason": reason,
                    "cancelled_by": self._user_id(current_user),
                    "cancelled_by_name": current_user.get("full_name"),
                    "cancelled_at": now,
                    "updated_at": now,
                }
            },
        )
        if update_result.modified_count == 0:
            return {"success": False, "detail": "الطلب تغيّرت حالته — يرجى تحديث الصفحة والمحاولة مرة أخرى"}

        await self._write_audit(database, f"request_cancelled_{request_type}", current_user,
                                 request, request_type, {"reason": reason})
        await _emit_event(database, "approval_request_cancelled", request_id, request_type,
                          reviewer_id=self._user_id(current_user),
                          status_before=current_status, status_after="cancelled",
                          details={"reason": reason})

        logger.info(f"Request cancelled: type={request_type}, id={request_id}")
        return {"success": True, "message": "تم إلغاء الطلب"}

    async def get_queue(self, filters: dict = None) -> dict:
        database = _get_db()
        query = {}
        filters = filters or {}

        if filters.get("status"):
            query["status"] = filters["status"]
        if filters.get("account_type"):
            query["account_type"] = filters["account_type"]
        if filters.get("request_type"):
            query["account_type"] = filters["request_type"]
        if filters.get("source"):
            query["source"] = filters["source"]

        requests = await database.registration_requests.find(query, {"_id": 0}).sort("created_at", -1).to_list(1000)
        return {"requests": requests, "total": len(requests)}

    async def get_request_details(self, request_id: str) -> Optional[dict]:
        database = _get_db()
        request = await database.registration_requests.find_one({"id": request_id}, {"_id": 0})
        if not request:
            return None

        events = await database.approval_events.find(
            {"request_id": request_id}, {"_id": 0}
        ).sort("timestamp", -1).to_list(50)

        audit_entries = await database.audit_logs.find(
            {"target_id": request_id, "target_type": "registration_request"}, {"_id": 0}
        ).sort("timestamp", -1).to_list(50)

        request["review_history"] = audit_entries
        request["lifecycle_events"] = events
        return request


approval_engine = ApprovalEngine()
