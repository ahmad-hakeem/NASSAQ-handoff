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

from sqlalchemy import select, and_, desc as sa_desc

from pg_models import RegistrationRequest, ApprovalEvent, AuditLog
from engines.sql_utils import model_to_dict, models_to_dicts, dict_to_model, apply_updates

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
    """Check whether a status transition is allowed."""
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

    async def validate_before_approve(self, request: dict, context: Optional[dict] = None) -> Optional[str]:
        """Hook: validate business rules before approving a request.

        `context` carries reviewer-supplied decisions that are NOT part of the
        original request (e.g. which school an approved teacher joins).
        """
        return None

    async def create_entities(self, request: dict, approved_by: dict,
                              context: Optional[dict] = None) -> ApprovalResult:
        """Hook: create domain entities after approval is granted."""
        raise NotImplementedError

    async def verify_after_approve(self, request: dict, result: ApprovalResult) -> Optional[str]:
        """Hook: verify entity creation succeeded after approval."""
        return None

    def get_display_fields(self) -> list:
        """Hook: return human-readable display fields for the request."""
        return ["full_name", "email", "phone", "created_at"]


def _get_session():
    db = _get_db()
    return db.session


async def _emit_event(database, event_type: str, request_id: str, request_type: str, *,
                       reviewer_id: str = None, status_before: str = None,
                       status_after: str = None, result: str = "success",
                       error_code: str = None, details: dict = None):
    session = database.session
    obj = ApprovalEvent(
        id=str(uuid.uuid4()),
        request_id=request_id,
        event_type=event_type,
        from_status=status_before,
        to_status=status_after,
        performed_by=reviewer_id,
        data={
            "request_type": request_type,
            "result": result,
            "error_code": error_code,
            "entity_type": "approval_request",
            **(details or {}),
        },
        timestamp=datetime.now(timezone.utc),
    )
    try:
        nested = await session.begin_nested()
        try:
            session.add(obj)
            await session.flush()
            await nested.commit()
        except Exception:
            await nested.rollback()
            raise
    except Exception as e:
        logger.error(f"Failed to emit approval event {event_type}: {e}")


class ApprovalEngine:
    def __init__(self):
        self._handlers: Dict[str, ApprovalHandler] = {}

    def register(self, handler: ApprovalHandler) -> None:
        """Register an approval handler for a given request type."""
        self._handlers[handler.request_type] = handler
        logger.info(f"Registered approval handler: {handler.request_type} ({handler.display_name_ar})")

    def get_handler(self, request_type: str) -> Optional[ApprovalHandler]:
        """Look up the registered handler for a request type."""
        return self._handlers.get(request_type)

    def get_registered_types(self) -> list:
        """Return a list of all registered approval types."""
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
        session = database.session
        stmt = select(RegistrationRequest).where(RegistrationRequest.id == request_id).limit(1)
        result = await session.execute(stmt)
        row = result.scalars().first()
        request = model_to_dict(row) if row else None
        if request:
            request.pop("_id", None)
        return database, request

    def _user_id(self, user: dict) -> str:
        return user.get("id", user.get("user_id", ""))

    async def _write_audit(self, database, action: str, current_user: dict,
                            request: dict, request_type: str, extra_details: dict = None):
        session = database.session
        obj = AuditLog(
            id=str(uuid.uuid4()),
            action=action,
            performed_by=self._user_id(current_user),
            actor_name=current_user.get("full_name", ""),
            actor_role=current_user.get("role", ""),
            target_type="registration_request",
            target_id=request.get("id", ""),
            target_name=request.get("full_name") or request.get("school_name", ""),
            details={
                "request_type": request_type,
                "status_before": request.get("status"),
                **(extra_details or {}),
            },
            timestamp=datetime.now(timezone.utc),
        )
        session.add(obj)
        await session.flush()

    async def _update_request(self, database, request_id: str, current_status: str, updates: dict) -> int:
        session = database.session
        stmt = select(RegistrationRequest).where(
            and_(RegistrationRequest.id == request_id, RegistrationRequest.status == current_status)
        ).limit(1)
        result = await session.execute(stmt)
        obj = result.scalars().first()
        if not obj:
            return 0
        apply_updates(obj, updates)
        await session.flush()
        return 1

    async def approve(self, request_id: str, current_user: dict, notes: str = "",
                      context: Optional[dict] = None) -> ApprovalResult:
        """Approve a pending request and trigger entity creation.

        `context` holds decisions the reviewer makes at approval time (see
        ApprovalHandler.validate_before_approve).
        """
        context = context or {}
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

        validation_error = await handler.validate_before_approve(request, context)
        if validation_error:
            await _emit_event(database, "approval_request_validation_failed", request_id, request_type,
                              reviewer_id=self._user_id(current_user),
                              status_before=current_status, result="failed",
                              error_code="validation_failed", details={"reason": validation_error})
            return ApprovalResult(success=False, message=validation_error, request_type=request_type)

        await _emit_event(database, "approval_activation_started", request_id, request_type,
                          reviewer_id=self._user_id(current_user), status_before=current_status)

        try:
            result = await handler.create_entities(request, current_user, context)
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
        # A handler that attached the new entity to an EXISTING school reports it
        # as "school"; mirror it onto the request's own school_id FK so approved
        # requests stay queryable/auditable by school.
        if result.created_entities.get("school"):
            linked_fields["school_id"] = result.created_entities["school"]
        if result.created_entities.get("school_id"):
            linked_fields["linked_entity_id"] = result.created_entities["school_id"]
        elif result.created_entities.get("user_id"):
            linked_fields["linked_entity_id"] = result.created_entities["user_id"]

        update_fields = {
            "status": "approved",
            "review_note": notes,
            "reviewed_at": now,
            "reviewed_by": self._user_id(current_user),
            **linked_fields,
        }

        modified = await self._update_request(database, request_id, current_status, update_fields)
        if modified == 0:
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

    async def _do_status_update(self, request_id: str, target_status: str,
                                 current_user: dict, extra_updates: dict,
                                 audit_action_suffix: str, event_type: str,
                                 extra_audit: dict = None, extra_event: dict = None) -> dict:
        database, request = await self._get_request(request_id)
        if not request:
            return {"success": False, "detail": "طلب التسجيل غير موجود"}

        current_status = request.get("status", "")
        valid, err_msg = validate_transition(current_status, target_status)
        if not valid:
            return {"success": False, "detail": err_msg}

        now = datetime.now(timezone.utc).isoformat()
        request_type = request.get("account_type", "unknown")

        update_fields = {"status": target_status, **extra_updates}
        modified = await self._update_request(database, request_id, current_status, update_fields)
        if modified == 0:
            return {"success": False, "detail": "الطلب تغيّرت حالته — يرجى تحديث الصفحة والمحاولة مرة أخرى"}

        await self._write_audit(database, f"request_{audit_action_suffix}_{request_type}",
                                 current_user, request, request_type, extra_audit)
        await _emit_event(database, event_type, request_id, request_type,
                          reviewer_id=self._user_id(current_user),
                          status_before=current_status, status_after=target_status,
                          details=extra_event)

        logger.info(f"Request {audit_action_suffix}: type={request_type}, id={request_id}")
        return {"success": True}

    async def reject(self, request_id: str, reason: str, current_user: dict) -> dict:
        """Reject a pending request with a reason."""
        result = await self._do_status_update(
            request_id, "rejected", current_user,
            {"review_note": reason, "reviewed_at": datetime.now(timezone.utc).isoformat(),
             "reviewed_by": self._user_id(current_user)},
            "rejected", "approval_request_rejected",
            extra_audit={"reason": reason},
            extra_event={"reason": reason},
        )
        if result.get("success"):
            return {"success": True, "message": "تم رفض الطلب بنجاح", "rejection_reason": reason}
        return result

    async def request_info(self, request_id: str, message: str, current_user: dict) -> dict:
        """Request additional information on a pending request."""
        result = await self._do_status_update(
            request_id, "info_required", current_user,
            {},
            "info_requested", "approval_request_info_requested",
            extra_audit={"message": message},
        )
        if result.get("success"):
            return {"success": True, "message": "تم إرسال طلب المعلومات الإضافية"}
        return result

    async def mark_under_review(self, request_id: str, notes: str, current_user: dict) -> dict:
        """Transition a request to under-review status."""
        result = await self._do_status_update(
            request_id, "under_review", current_user,
            {"review_note": notes},
            "under_review", "approval_request_under_review",
            extra_audit={"notes": notes},
            extra_event={"notes": notes},
        )
        if result.get("success"):
            return {"success": True, "message": "تم وضع الطلب تحت المراجعة"}
        return result

    async def archive(self, request_id: str, current_user: dict) -> dict:
        """Archive a completed or rejected request."""
        result = await self._do_status_update(
            request_id, "archived", current_user,
            {},
            "archived", "approval_request_archived",
        )
        if result.get("success"):
            return {"success": True, "message": "تم أرشفة الطلب"}
        return result

    async def cancel(self, request_id: str, reason: str, current_user: dict) -> dict:
        """Cancel a pending request."""
        result = await self._do_status_update(
            request_id, "cancelled", current_user,
            {},
            "cancelled", "approval_request_cancelled",
            extra_audit={"reason": reason},
            extra_event={"reason": reason},
        )
        if result.get("success"):
            return {"success": True, "message": "تم إلغاء الطلب"}
        return result

    async def get_queue(self, filters: dict = None) -> dict:
        """Return the filtered approval queue for a reviewer."""
        session = _get_session()
        conditions = []
        filters = filters or {}

        if filters.get("status"):
            conditions.append(RegistrationRequest.status == filters["status"])
        if filters.get("account_type"):
            conditions.append(RegistrationRequest.type == filters["account_type"])
        if filters.get("request_type"):
            conditions.append(RegistrationRequest.type == filters["request_type"])

        stmt = select(RegistrationRequest)
        if conditions:
            stmt = stmt.where(and_(*conditions))
        stmt = stmt.order_by(sa_desc(RegistrationRequest.created_at))

        result = await session.execute(stmt)
        requests = []
        for row in result.scalars().all():
            d = model_to_dict(row)
            d.pop("_id", None)
            requests.append(d)
        return {"requests": requests, "total": len(requests)}

    async def get_request_details(self, request_id: str) -> Optional[dict]:
        """Fetch full details of a single approval request."""
        session = _get_session()

        stmt = select(RegistrationRequest).where(RegistrationRequest.id == request_id).limit(1)
        result = await session.execute(stmt)
        row = result.scalars().first()
        if not row:
            return None
        request = model_to_dict(row)
        request.pop("_id", None)

        evt_stmt = (
            select(ApprovalEvent)
            .where(ApprovalEvent.request_id == request_id)
            .order_by(sa_desc(ApprovalEvent.timestamp))
            .limit(50)
        )
        evt_result = await session.execute(evt_stmt)
        events = []
        for e in evt_result.scalars().all():
            d = model_to_dict(e)
            d.pop("_id", None)
            events.append(d)

        audit_stmt = (
            select(AuditLog)
            .where(and_(AuditLog.target_id == request_id, AuditLog.target_type == "registration_request"))
            .order_by(sa_desc(AuditLog.timestamp))
            .limit(50)
        )
        audit_result = await session.execute(audit_stmt)
        audit_entries = []
        for a in audit_result.scalars().all():
            d = model_to_dict(a)
            d.pop("_id", None)
            audit_entries.append(d)

        request["review_history"] = audit_entries
        request["lifecycle_events"] = events
        return request


approval_engine = ApprovalEngine()
