"""
NASSAQ Route Module: Notification engine endpoints
Auto-consolidated during Phase 8 modularization.
"""
from fastapi import APIRouter, HTTPException, Depends, status, Header, Query, Body, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import Response
from starlette.responses import StreamingResponse
from pydantic import BaseModel, Field, ConfigDict, EmailStr, model_validator
from typing import List, Optional, Any, Dict
from datetime import datetime, timezone, timedelta
import uuid, os, logging, json, random, re, io, base64
from enum import Enum

from engines.sql_utils import gd_find, gd_find_one, gd_insert, gd_insert_many, gd_update_one, gd_update_many, gd_count, gd_delete_one, gd_delete_many, gd_distinct, gd_upsert, _gd_aggregate
from utils.parent_resolution import (
    PARENT_NOT_FOUND_AR,
    resolve_student_parent_user_id,
)
from dependencies import (
    db, get_current_user, require_roles, UserRole, SchoolStatus,
    hash_password, verify_password, create_access_token,
    JWT_SECRET, JWT_ALGORITHM, ACCESS_TOKEN_EXPIRE, security, logger,
    audit_engine, AuditAction, AuditSeverity,
    smart_scheduling_engine, TimetableRunStatus, TimetableStatus,
    ConflictType, ConflictSeverity, PreValidationResult, GenerationResult,
    hakim_engine, reporting_engine, export_engine, session_engine,
    REPORT_TYPES, generate_student_qr_code
)

router = APIRouter()



# ============== NOTIFICATION ENGINE ==============
# Data Models

class NotificationType(str, Enum):
    SYSTEM = "system"
    ATTENDANCE = "attendance"
    SCHEDULE = "schedule"
    ASSESSMENT = "assessment"
    BEHAVIOUR = "behaviour"
    COMMUNICATION = "communication"
    ANNOUNCEMENT = "announcement"

class NotificationPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class NotificationCreate(BaseModel):
    title: str
    title_en: Optional[str] = None
    message: str
    message_en: Optional[str] = None
    notification_type: NotificationType = NotificationType.SYSTEM
    priority: NotificationPriority = NotificationPriority.MEDIUM
    recipient_id: Optional[str] = None  # Single recipient
    recipient_role: Optional[str] = None  # Role-based (all users with this role)
    related_entity: Optional[str] = None  # e.g., "student", "class", "assessment"
    related_entity_id: Optional[str] = None
    action_url: Optional[str] = None  # URL to navigate when clicked
    # Optional Communication-Center template id. When set and the
    # template is in TEMPLATE_RECIPIENT_RULES, the recipient role/cohort
    # is validated server-side so a tampered FE cannot widen the cohort
    # (e.g. Homework Reminder → parents only). Templates not listed in
    # the rules dict remain unrestricted (legacy behaviour preserved).
    template_id: Optional[str] = None

class NotificationResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    title: str
    title_en: Optional[str] = None
    message: str
    message_en: Optional[str] = None
    notification_type: str
    priority: str
    related_entity: Optional[str] = None
    related_entity_id: Optional[str] = None
    action_url: Optional[str] = None
    read_status: bool
    read_at: Optional[str] = None
    created_at: str
    sender_name: Optional[str] = None
    # Acknowledgement metadata. Populated for any notification flow that
    # needs an explicit "تم الاطلاع" beat — currently the relocation
    # alerts surfaced via /school/settings/unavailability — but the fields
    # are generic so future flows can reuse the same pipe without a new
    # migration. Defaults are False/None so legacy records keep working.
    is_acknowledged: Optional[bool] = False
    acknowledged_at: Optional[str] = None
    # Relocation-specific helpers — surfaced so the frontend can render the
    # ack button and the alternative-location link without hitting another
    # endpoint. Populated only when the notification stems from a class
    # unavailability with an alternative location.
    unavailability_id: Optional[str] = None
    alternative_location: Optional[str] = None

class NotificationBulkCreate(BaseModel):
    title: str
    title_en: Optional[str] = None
    message: str
    message_en: Optional[str] = None
    notification_type: NotificationType = NotificationType.SYSTEM
    priority: NotificationPriority = NotificationPriority.MEDIUM
    recipient_ids: List[str] = []  # List of user IDs
    recipient_role: Optional[str] = None  # Send to all users with this role
    related_entity: Optional[str] = None
    related_entity_id: Optional[str] = None
    action_url: Optional[str] = None

# Helper function to create notification
async def create_notification_internal(
    title: str,
    message: str,
    recipient_id: str,
    notification_type: str = "system",
    priority: str = "medium",
    sender_id: Optional[str] = None,
    related_entity: Optional[str] = None,
    related_entity_id: Optional[str] = None,
    action_url: Optional[str] = None,
    title_en: Optional[str] = None,
    message_en: Optional[str] = None,
    school_id: Optional[str] = None,
    extra_data: Optional[Dict[str, Any]] = None,
    category: Optional[str] = None,
    cta_url: Optional[str] = None,
):
    """Internal helper to create notifications from other engines.

    ``extra_data`` lets callers attach flow-specific fields (e.g. the
    ``unavailability_id`` for relocation notifications) without growing the
    function signature for every new use case. The fields are merged into
    the notification document and end up in the JSONB ``data`` column, so
    they're transparently available on read via ``gd_find``.

    ``category`` (Task #249) buckets rows for the IT inbox and the
    per-category channel-preferences matrix. Defaults to ``general``.
    ``cta_url`` is the workspace-relative deep-link the inbox uses for
    "open" navigation; distinct from ``action_url`` so school-tenant
    flows aren't disturbed."""
    notification_id = str(uuid.uuid4())
    sender_name_resolved = None
    if sender_id:
        sender_user = await gd_find_one(db.session, "users", {"id": sender_id})
        if sender_user:
            sender_name_resolved = sender_user.get("full_name", "")

    notification_doc = {
        "id": notification_id,
        "user_id": recipient_id,
        "title": title,
        "title_en": title_en,
        "message": message,
        "message_en": message_en,
        "type": notification_type,
        "priority": priority,
        "action_url": action_url,
        "related_entity": related_entity,
        "related_entity_id": related_entity_id,
        "sender_id": sender_id,
        "sender_name": sender_name_resolved,
        "tenant_id": school_id,
        "is_read": False,
        "read_at": None,
        # Default ack metadata so every notification has a consistent shape
        # on read; flows that don't require acknowledgement just leave the
        # fields untouched.
        "is_acknowledged": False,
        "acknowledged_at": None,
        "category": (category or "general"),
        "cta_url": cta_url,
        "created_at": datetime.now(timezone.utc),
    }
    if extra_data:
        # Caller-provided fields win over defaults so a flow can override
        # e.g. ``is_acknowledged`` if it ever needs to seed pre-acked rows.
        for k, v in extra_data.items():
            notification_doc[k] = v
    await gd_insert(db.session, "notifications", notification_doc)

    # Real-time push so the recipient's red badge updates immediately
    # without a page refresh. Wrapped in try/except: a transient WS issue
    # must NOT roll back the persisted notification — the row is the
    # source of truth, the socket is just a nudge. Any connected tab(s)
    # for this user receive a ``new_notification`` event carrying enough
    # of the payload to render an inline preview before the next poll.
    try:
        from routes.websocket_routes import get_connection_manager
        ws_manager = get_connection_manager()
        if ws_manager.is_user_online(recipient_id):
            await ws_manager.send_personal_message({
                "type": "new_notification",
                "notification_id": notification_id,
                "title": title,
                "title_en": title_en,
                "message": message,
                "message_en": message_en,
                "notification_type": notification_type,
                "priority": priority,
                "action_url": action_url,
                "related_entity": related_entity,
                "related_entity_id": related_entity_id,
                "created_at": notification_doc["created_at"].isoformat(),
            }, recipient_id)
    except Exception as ws_err:  # noqa: BLE001 — never fail the write on a push glitch
        logger.warning(
            "WS push failed for notification %s → user %s: %s",
            notification_id, recipient_id, ws_err,
        )

    return notification_id

# Notification APIs

# --- IT send hardening (Task #198 §5.6) -------------------------------
# Independent-Teacher callers may send notifications, but ONLY to the
# two cohorts surfaced by /independent-teacher/communication/recipients.
# Server-side enforcement (the frontend's reduced UI is convenience):
#   * `recipient_role` is rejected outright (no role-broadcast allowed).
#   * Every `recipient_id` must resolve to a user inside the IT's
#     workspace via either students.user_id == uid (cohort: my_students)
#     or guardian_links(parent_ref=uid, tenant_id=workspace, is_active).
# Mismatches return 403 — writes must surface the rejection.
_IT_RECIPIENT_ROLE_BLOCKED_AR = "لا يمكن للمعلم المستقل البث حسب الدور."
_IT_RECIPIENT_OUT_OF_SCOPE_AR = "المستلم غير ضمن مساحتك."

# --- Communication-Center template → recipient cohort rules -----------
# Maps the FE template id (TeacherCommunicationPage.jsx TEMPLATES.id) to
# the set of user roles that are valid recipients for that template.
# Templates not listed here are unrestricted (legacy behaviour). The
# FE filter in renderRecipientCategoriesGrid is convenience UX; this
# dict is the fail-closed server-side boundary per spec.
TEMPLATE_RECIPIENT_RULES: Dict[str, set] = {
    "homework": {"parent"},
}
_TEMPLATE_COHORT_MISMATCH_AR = "هذا القالب لا يسمح بهذه الفئة من المستلمين."


async def _enforce_template_recipient_rule(
    template_id: Optional[str],
    *,
    recipient_role: Optional[str] = None,
    recipient_id: Optional[str] = None,
) -> None:
    """Reject sends whose recipient cohort does not match the rule for
    ``template_id``. Safe Arabic message, HTTP 403 (writes must surface
    the rejection — same convention used by the IT path above).

    Resolution order:
      * If ``template_id`` is missing or unknown → no-op.
      * If ``recipient_role`` is supplied → must be in the allowed set.
      * If ``recipient_id`` is supplied → look up the user's ``role``
        and check membership.
    """
    if not template_id:
        return
    allowed = TEMPLATE_RECIPIENT_RULES.get(template_id)
    if allowed is None:
        return
    # Validate EVERY supplied selector independently. An earlier draft
    # short-circuited on `recipient_role` when allowed, but the route
    # then delivered to `recipient_id` (single-recipient branch), so a
    # request like `recipient_role='parent', recipient_id=<vp-user>`
    # could deliver to a non-parent. Both must independently satisfy
    # the allowed set; absent selectors are skipped here and rejected
    # later by the route's normal "no recipient" handling.
    if recipient_role is not None and recipient_role not in allowed:
        raise HTTPException(status_code=403, detail=_TEMPLATE_COHORT_MISMATCH_AR)
    if recipient_id:
        # Strict: the recipient_id MUST resolve to a real user whose
        # role is in the allowed set. No student/parent_id fallback —
        # that admitted any user id that happened to appear in the
        # parent_id column even if their own users.role was not parent.
        # The FE always sends a parent user id for the parents cohort.
        user = await gd_find_one(db.session, "users", {"id": recipient_id})
        if not (user and user.get("role") in allowed):
            raise HTTPException(status_code=403, detail=_TEMPLATE_COHORT_MISMATCH_AR)


async def _it_validate_recipients_or_403(current_user: dict, recipient_ids: List[str]) -> None:
    """Reject any recipient that is not in the IT's spec §5.6 cohorts.

    Allow-set is computed exactly like
    ``GET /independent-teacher/communication/recipients`` — i.e. via
    teacher → classes (homeroom UNION teacher_assignments) → students,
    then for parents via ``guardian_links`` (and the legacy
    ``students.parent_id`` fallback). Reusing the same builder keeps the
    picker and the send path in lock-step. 403 (not 404) — writes must
    surface the rejection per spec §5.6.
    """
    from auth_scope import is_independent_teacher, independent_workspace_id
    from routes.independent_teacher_communication_routes import (
        _resolve_workspace_teacher_id,
        _resolve_my_students_recipients,
        _resolve_my_parents_recipients,
    )
    if not is_independent_teacher(current_user):
        return
    cleaned = [rid for rid in (recipient_ids or []) if rid]
    if not cleaned:
        return
    school_id = independent_workspace_id(current_user)
    if not school_id:
        raise HTTPException(status_code=403, detail=_IT_RECIPIENT_OUT_OF_SCOPE_AR)
    try:
        teacher_id = await _resolve_workspace_teacher_id(
            current_user["id"], school_id,
        )
    except HTTPException:
        raise HTTPException(status_code=403, detail=_IT_RECIPIENT_OUT_OF_SCOPE_AR)
    students = await _resolve_my_students_recipients(school_id, teacher_id)
    parents = await _resolve_my_parents_recipients(school_id, teacher_id)
    allowed = {item["user_id"] for item in students} | {item["user_id"] for item in parents}
    for rid in cleaned:
        if rid not in allowed:
            raise HTTPException(status_code=403, detail=_IT_RECIPIENT_OUT_OF_SCOPE_AR)


@router.post("/notifications")
async def create_notification(
    notification: NotificationCreate,
    current_user: dict = Depends(get_current_user)
):
    """Create a single notification"""
    if current_user['role'] not in ['platform_admin', 'school_principal', 'school_sub_admin', 'school_admin', 'teacher', 'independent_teacher']:
        raise HTTPException(status_code=403, detail="Not authorized to create notifications")

    # Pin persisted tenant_id to itw_{user_id} even when the caller's
    # users.tenant_id is stale/null. Mirrors the bulk path so single
    # and bulk send paths agree on workspace tagging. (Was previously
    # mis-indented under the auth raise above and therefore unreachable.)
    if current_user.get('role') == 'independent_teacher':
        from auth_scope import independent_workspace_id as _itw
        _wsid = _itw(current_user)
        if _wsid:
            current_user = {**current_user, 'tenant_id': _wsid}

    # Communication-Center template → recipient cohort guard. Runs for
    # every caller (school + IT) so a tampered FE cannot widen the
    # cohort declared by the template (e.g. Homework Reminder → parents).
    await _enforce_template_recipient_rule(
        notification.template_id,
        recipient_role=notification.recipient_role,
        recipient_id=notification.recipient_id,
    )

    # Safety net for the removed "Student Counselor under Management"
    # sub-flow: the only payload shape that variant produced was a
    # teacher-issued role broadcast carrying a per-student tag
    # (`recipient_role` + `related_entity == 'student'`). The Management
    # cohort now auto-resolves to the general admin notice with no
    # related_entity, so a teacher request that still carries this
    # combination must be a tampered/legacy client — reject 403.
    if (
        current_user.get('role') == 'teacher'
        and notification.recipient_role
        and notification.related_entity == 'student'
    ):
        raise HTTPException(
            status_code=403,
            detail="هذا المسار لم يعد متاحًا لإشعارات المعلم.",
        )

    # Task #463 — student-targeted send. The Teacher Communication
    # Center "Homework Reminder" (and any other parent-cohort
    # template) now sends `related_entity='student'` +
    # `related_entity_id=<student.id>` instead of pushing the
    # mutable `students.parent_id` as `recipient_id`. Resolve the
    # parent users.id via guardian_links (canonical) with a strict
    # `students.parent_id → users.id` fallback. No silent
    # email/phone/name fallback (threat-model: known weak parent
    # linkage paths).
    resolved_user_id_from_student: Optional[str] = None
    if (
        not notification.recipient_id
        and not notification.recipient_role
        and notification.related_entity == 'student'
        and notification.related_entity_id
    ):
        tenant_id = current_user.get('tenant_id')
        if not tenant_id:
            logger.warning(
                "parent resolver: missing tenant_id (template=%s, caller=%s, student=%s)",
                notification.template_id,
                current_user.get('id'),
                notification.related_entity_id,
            )
            raise HTTPException(status_code=404, detail=PARENT_NOT_FOUND_AR)
        try:
            resolved_user_id_from_student = await resolve_student_parent_user_id(
                notification.related_entity_id, tenant_id,
            )
        except HTTPException:
            raise
        except Exception:
            # Never expose raw exception strings — keep the user-facing
            # message as the safe Arabic 404 while logging context.
            logger.exception(
                "parent resolver failed (template=%s, caller=%s, tenant=%s, student=%s)",
                notification.template_id,
                current_user.get('id'),
                tenant_id,
                notification.related_entity_id,
            )
            raise HTTPException(status_code=404, detail=PARENT_NOT_FOUND_AR)
        if not resolved_user_id_from_student:
            logger.warning(
                "template guard: no linked parent (template=%s, caller=%s, tenant=%s, student=%s)",
                notification.template_id,
                current_user.get('id'),
                tenant_id,
                notification.related_entity_id,
            )
            raise HTTPException(status_code=404, detail=PARENT_NOT_FOUND_AR)

    # Communication-Center template → recipient cohort guard. Re-run
    # against the canonical resolved parent user (when present) so the
    # cohort rule is enforced on the actual delivery target. The
    # earlier top-of-function call already covered the legacy
    # recipient_id / recipient_role paths.
    if resolved_user_id_from_student:
        await _enforce_template_recipient_rule(
            notification.template_id,
            recipient_id=resolved_user_id_from_student,
        )

    # IT hardening — Task #198 §5.6.
    if current_user.get('role') == 'independent_teacher':
        if notification.recipient_role:
            raise HTTPException(status_code=403, detail=_IT_RECIPIENT_ROLE_BLOCKED_AR)
        target_id = resolved_user_id_from_student or notification.recipient_id
        if target_id:
            await _it_validate_recipients_or_403(current_user, [target_id])

    if notification.recipient_role and not notification.recipient_id:
        query = {"role": notification.recipient_role}
        tenant_id = current_user.get('tenant_id')
        if tenant_id:
            query['tenant_id'] = tenant_id
        role_users = await gd_find(db.session, "users", query, limit=1000)
        if not role_users:
            raise HTTPException(status_code=404, detail="لم يتم العثور على مستخدمين بهذا الدور")

        created_ids = []
        for role_user in role_users:
            notification_id = str(uuid.uuid4())
            notification_doc = {
                "id": notification_id,
                "user_id": role_user["id"],
                "title": notification.title,
                "message": notification.message,
                "type": notification.notification_type.value if notification.notification_type else None,
                "priority": notification.priority.value if notification.priority else "normal",
                "action_url": notification.action_url,
                "related_entity": notification.related_entity,
                "related_entity_id": notification.related_entity_id,
                "sender_id": current_user['id'],
                "sender_name": current_user.get('full_name', ''),
                "tenant_id": tenant_id,
                "is_read": False,
                "read_at": None,
                "created_at": datetime.now(timezone.utc),
            }
            await gd_insert(db.session, "notifications", notification_doc)
            created_ids.append(notification_id)

        return {"success": True, "notification_id": created_ids[0] if created_ids else None, "created_count": len(created_ids), "message": f"تم إرسال {len(created_ids)} إشعار بنجاح"}

    # Prefer the canonical resolver result over any caller-supplied
    # `recipient_id`. The legacy email/phone/name fallback chain is
    # removed — Task #463 + threat-model: mutable parent fields are a
    # documented weak linkage path and must never be used to widen
    # the cohort silently.
    resolved_user_id = resolved_user_id_from_student or notification.recipient_id
    if resolved_user_id:
        user_exists = await gd_find_one(db.session, "users", {"id": resolved_user_id})
        if not user_exists:
            raise HTTPException(status_code=404, detail="المستخدم غير موجود")
    else:
        raise HTTPException(status_code=400, detail="يجب تحديد المستلم أو الدور")

    notification_id = str(uuid.uuid4())
    notification_doc = {
        "id": notification_id,
        "user_id": resolved_user_id,
        "title": notification.title,
        "message": notification.message,
        "type": notification.notification_type.value if notification.notification_type else None,
        "priority": notification.priority.value if notification.priority else "normal",
        "action_url": notification.action_url,
        "related_entity": notification.related_entity,
        "related_entity_id": notification.related_entity_id,
        "sender_id": current_user['id'],
        "sender_name": current_user.get('full_name', ''),
        "tenant_id": current_user.get('tenant_id'),
        "is_read": False,
        "read_at": None,
        "created_at": datetime.now(timezone.utc),
    }
    
    await gd_insert(db.session, "notifications", notification_doc)
    
    return {"success": True, "notification_id": notification_id, "message": "Notification created successfully"}

@router.post("/notifications/bulk")
async def create_bulk_notifications(
    data: NotificationBulkCreate,
    current_user: dict = Depends(get_current_user)
):
    """Create notifications for multiple recipients or role-based"""
    if current_user['role'] not in ['platform_admin', 'school_principal', 'school_sub_admin', 'school_admin', 'independent_teacher']:
        raise HTTPException(status_code=403, detail="Not authorized to create bulk notifications")

    # IT hardening — Task #198 §5.6.
    if current_user.get('role') == 'independent_teacher':
        if data.recipient_role:
            raise HTTPException(status_code=403, detail=_IT_RECIPIENT_ROLE_BLOCKED_AR)
        await _it_validate_recipients_or_403(current_user, data.recipient_ids)
        # Tag the persisted rows with the IT workspace id even when the
        # caller's `users.tenant_id` has not yet been backfilled — keeps
        # downstream tenant scoping (notification list, audit) honest.
        from auth_scope import independent_workspace_id as _itw
        _wsid = _itw(current_user)
        if _wsid:
            current_user = {**current_user, 'tenant_id': _wsid}

    recipient_ids = data.recipient_ids.copy()
    
    # If role-based, find all users with that role
    if data.recipient_role:
        query = {"role": data.recipient_role}
        if current_user.get('tenant_id'):
            query['tenant_id'] = current_user['tenant_id']
        users = await gd_find(db.session, "users", query, limit=1000)
        recipient_ids.extend([u['id'] for u in users])
    
    # Remove duplicates
    recipient_ids = list(set(recipient_ids))
    
    created_count = 0
    for recipient_id in recipient_ids:
        notification_id = str(uuid.uuid4())
        notification_doc = {
            "id": notification_id,
            "user_id": recipient_id,
            "title": data.title,
            "message": data.message,
            "type": data.notification_type.value if data.notification_type else None,
            "priority": data.priority.value if data.priority else "normal",
            "action_url": data.action_url,
            "sender_id": current_user['id'],
            "sender_name": current_user.get('full_name', ''),
            "tenant_id": current_user.get('tenant_id'),
            "is_read": False,
            "read_at": None,
            "created_at": datetime.now(timezone.utc),
        }
        await gd_insert(db.session, "notifications", notification_doc)
        created_count += 1
    
    return {"success": True, "created_count": created_count, "message": f"{created_count} notifications created"}

@router.get("/notifications", response_model=List[NotificationResponse])
async def get_my_notifications(
    notification_type: Optional[str] = None,
    read_status: Optional[bool] = None,
    limit: int = 50,
    skip: int = 0,
    current_user: dict = Depends(get_current_user)
):
    """Get notifications for current user"""
    query = {"user_id": current_user['id']}

    if notification_type:
        query['type'] = notification_type
    if read_status is not None:
        query['is_read'] = read_status
    
    notifications = await gd_find(db.session, "notifications", query, order_by="created_at", desc_order=True, offset=skip, limit=limit)
    
    result = []
    for n in notifications:
        result.append(NotificationResponse(
            id=n['id'],
            title=n.get('title', ''),
            title_en=n.get('title_en'),
            message=n.get('message', ''),
            message_en=n.get('message_en'),
            notification_type=n.get('type', 'system'),
            priority=n.get('priority', 'normal'),
            related_entity=n.get('related_entity'),
            related_entity_id=n.get('related_entity_id'),
            action_url=n.get('action_url'),
            read_status=n.get('is_read', False),
            read_at=n.get('read_at'),
            created_at=n['created_at'],
            sender_name=n.get('sender_name'),
            is_acknowledged=bool(n.get('is_acknowledged', False)),
            acknowledged_at=n.get('acknowledged_at'),
            unavailability_id=n.get('unavailability_id'),
            alternative_location=n.get('alternative_location'),
        ))

    return result

@router.get("/notifications/unread-count")
async def get_unread_count(current_user: dict = Depends(get_current_user)):
    """Get count of unread notifications"""
    count = await gd_count(db.session, "notifications", {
        "user_id": current_user['id'],
        "is_read": False
    })
    return {"unread_count": count}

@router.put("/notifications/{notification_id}/read")
async def mark_notification_as_read(
    notification_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Mark a notification as read"""
    notification = await gd_find_one(db.session, "notifications", {"id": notification_id})
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    
    # Verify the notification belongs to the user
    if notification.get('user_id') != current_user['id']:
        raise HTTPException(status_code=403, detail="Not authorized to access this notification")
    
    await gd_update_one(db.session, "notifications", {"id": notification_id}, {
            "is_read": True,
            "read_at": datetime.now(timezone.utc)
        })
    
    return {"success": True, "message": "Notification marked as read"}

@router.put("/notifications/mark-all-read")
async def mark_all_notifications_as_read(current_user: dict = Depends(get_current_user)):
    """Mark all notifications as read for current user"""
    result = await gd_update_many(db.session, "notifications", {
            "user_id": current_user['id'],
            "is_read": False
        }, {
            "is_read": True,
            "read_at": datetime.now(timezone.utc)
        })
    
    return {"success": True, "marked_count": result}

@router.delete("/notifications/{notification_id}")
async def delete_notification(
    notification_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Delete a notification"""
    notification = await gd_find_one(db.session, "notifications", {"id": notification_id})
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    
    # Verify the notification belongs to the user or user is admin
    if notification.get('user_id') != current_user['id'] and current_user['role'] not in ['platform_admin', 'school_principal']:
        raise HTTPException(status_code=403, detail="Not authorized to delete this notification")
    
    await gd_delete_one(db.session, "notifications", {"id": notification_id})
    
    return {"success": True, "message": "Notification deleted"}

class CircularAckRequest(BaseModel):
    circularId: Optional[str] = None
    userId: Optional[str] = None

@router.post("/notifications/{notification_id}/acknowledge")
async def acknowledge_circular(
    notification_id: str,
    payload: Optional[CircularAckRequest] = None,
    current_user: dict = Depends(get_current_user)
):
    """Acknowledge receipt of a notification (تأكيد الاستلام والقراءة).

    Used primarily for Circulars (تعميم) but works for any notification the
    user owns. Sets ``is_acknowledged=True`` and ``acknowledged_at`` on the
    recipient's notification row, also marks it as read, and (for circulars)
    fires a ``circular_ack`` back to the original sender so the admin sees
    real-time receipt confirmation.
    """
    # Optional payload kept for backwards-compat with older clients that send
    # {circularId, userId}; if present, validate it lines up with the request.
    if payload and payload.circularId and payload.circularId != notification_id:
        raise HTTPException(status_code=400, detail="Mismatched circular identifier")
    if payload and payload.userId and payload.userId != current_user['id']:
        raise HTTPException(status_code=400, detail="Mismatched user identifier")

    original = await gd_find_one(db.session, "notifications", {"id": notification_id})
    if not original:
        raise HTTPException(status_code=404, detail="Notification not found")

    if original.get('user_id') != current_user['id']:
        raise HTTPException(status_code=403, detail="Not authorized to acknowledge this notification")

    original_tenant = original.get('tenant_id')
    user_tenant = current_user.get('tenant_id')
    if original_tenant and user_tenant and original_tenant != user_tenant:
        raise HTTPException(status_code=403, detail="Cross-tenant acknowledgment not allowed")

    now_iso = datetime.now(timezone.utc).isoformat()

    # Idempotent: if already acknowledged we still return success and reuse
    # the prior timestamp instead of overwriting it.
    newly_acked = not original.get('is_acknowledged')
    if newly_acked:
        await gd_update_one(
            db.session,
            "notifications",
            {"id": notification_id},
            {
                "is_acknowledged": True,
                "acknowledged_at": now_iso,
                "is_read": True,
                "read_at": original.get('read_at') or now_iso,
            },
        )

    # Notify the original sender for circulars only (avoids spamming senders
    # of routine in-app notifications). Skip self-acks. Only fire on the
    # first ack transition so repeated clicks don't spam the admin.
    is_circular = original.get('type') == 'circular'
    sender_id = original.get('sender_id')
    if newly_acked and is_circular and sender_id and sender_id != current_user['id']:
        teacher_name = current_user.get('full_name') or current_user.get('name') or ''
        original_title_ar = original.get('title') or ''
        original_title_en = original.get('title_en') or original_title_ar
        try:
            await create_notification_internal(
                title="تأكيد استلام تعميم",
                message=f"المعلم {teacher_name} أكد استلام التعميم: {original_title_ar}",
                recipient_id=sender_id,
                notification_type="circular_ack",
                priority="medium",
                sender_id=current_user['id'],
                related_entity="notification",
                related_entity_id=notification_id,
                title_en="Circular Acknowledgement",
                message_en=f"Teacher {teacher_name} acknowledged the circular: {original_title_en}",
                school_id=current_user.get('tenant_id'),
            )
        except Exception as ack_err:
            # Don't fail the user's ack just because the back-channel notice
            # to the admin failed; log and continue.
            logger.warning("circular_ack notify-back failed: %s", ack_err)

    return {
        "success": True,
        "message": "Notification acknowledged",
        "acknowledged_at": original.get('acknowledged_at') or now_iso,
    }

@router.get("/notifications/sent-circulars")
async def list_sent_circulars(
    limit: int = 50,
    current_user: dict = Depends(get_current_user),
):
    """Admin view of circulars (تعميمات) the current user has sent.

    Groups the per-recipient fan-out rows by ``broadcast_id`` and returns
    one summary per circular with acknowledgment counts so the Communication
    Center can render the "حالة الاستلام" metric on each sent card.
    """
    if current_user['role'] not in ['platform_admin', 'school_principal', 'school_sub_admin', 'school_admin']:
        raise HTTPException(status_code=403, detail="غير مصرح")

    tenant_id = current_user.get('tenant_id')
    query = {"type": "circular", "sender_id": current_user['id']}
    if tenant_id:
        query["tenant_id"] = tenant_id

    rows = await gd_find(
        db.session, "notifications", query,
        order_by="created_at", desc_order=True, limit=max(limit * 50, 500),
    )

    # Group by broadcast_id (falls back to row id for legacy single-recipient
    # circulars that predate the engine fan-out).
    groups: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        bid = r.get('broadcast_id') or r.get('id')
        g = groups.setdefault(bid, {
            "broadcast_id": bid,
            "title": r.get('title') or '',
            "title_en": r.get('title_en') or r.get('title') or '',
            "message": r.get('message') or '',
            "message_en": r.get('message_en') or r.get('message') or '',
            "priority": r.get('priority') or 'normal',
            "recipient_type": r.get('recipient_type'),
            "created_at": r.get('created_at'),
            "sent_at": r.get('sent_at') or r.get('created_at'),
            "recipient_count": 0,
            "acknowledged_count": 0,
            "read_count": 0,
        })
        g["recipient_count"] += 1
        if r.get('is_acknowledged'):
            g["acknowledged_count"] += 1
        if r.get('is_read'):
            g["read_count"] += 1
        # Keep the earliest sent_at across the broadcast
        if r.get('created_at') and (not g.get('created_at') or r['created_at'] < g['created_at']):
            g['created_at'] = r['created_at']
            g['sent_at'] = r.get('sent_at') or r['created_at']

    summaries = sorted(groups.values(), key=lambda g: g.get('sent_at') or '', reverse=True)[:limit]
    for g in summaries:
        rc = g["recipient_count"] or 1
        g["acknowledged_rate"] = round((g["acknowledged_count"] / rc) * 100, 1)
    return {"circulars": summaries, "total": len(summaries)}


@router.get("/notifications/circular/{broadcast_id}/acknowledgements")
async def get_circular_acknowledgements(
    broadcast_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Per-recipient acknowledgment list for a given circular broadcast.

    Returns each targeted teacher / user with their ``acknowledged`` flag and
    timestamp so the admin can see at a glance who has read the circular.
    """
    if current_user['role'] not in ['platform_admin', 'school_principal', 'school_sub_admin', 'school_admin']:
        raise HTTPException(status_code=403, detail="غير مصرح")

    tenant_id = current_user.get('tenant_id')
    query = {"$or": [{"broadcast_id": broadcast_id}, {"id": broadcast_id}]}
    if tenant_id:
        query["tenant_id"] = tenant_id

    rows = await gd_find(db.session, "notifications", query, order_by="created_at", desc_order=False, limit=2000)

    # Authorisation: caller must own the circular (be the sender) or be a
    # platform admin. Drop rows from other senders accidentally caught by id
    # collision (extremely unlikely but defensive).
    sender_ids = {r.get('sender_id') for r in rows if r.get('sender_id')}
    if current_user['role'] != 'platform_admin' and sender_ids and current_user['id'] not in sender_ids:
        raise HTTPException(status_code=403, detail="Not authorized to view this circular")

    user_ids = list({r.get('user_id') for r in rows if r.get('user_id')})
    name_map: Dict[str, Dict[str, Any]] = {}
    if user_ids:
        users = await gd_find(db.session, "users", {"id": {"$in": user_ids}}, limit=len(user_ids))
        for u in users:
            name_map[u['id']] = {
                "name": u.get('full_name') or u.get('name') or u.get('email') or '',
                "email": u.get('email'),
                "role": u.get('role'),
            }

    recipients = []
    ack_count = 0
    for r in rows:
        uid = r.get('user_id')
        info = name_map.get(uid, {})
        acked = bool(r.get('is_acknowledged'))
        if acked:
            ack_count += 1
        recipients.append({
            "user_id": uid,
            "name": info.get('name') or r.get('recipient_name') or '',
            "email": info.get('email'),
            "role": info.get('role') or r.get('recipient_role'),
            "acknowledged": acked,
            "acknowledged_at": r.get('acknowledged_at'),
            "is_read": bool(r.get('is_read')),
            "read_at": r.get('read_at'),
        })

    total = len(recipients)
    return {
        "broadcast_id": broadcast_id,
        "title": rows[0].get('title') if rows else '',
        "recipients": recipients,
        "acknowledged_count": ack_count,
        "total": total,
        "acknowledged_rate": round((ack_count / total) * 100, 1) if total else 0,
    }


@router.get("/notifications/analytics")
async def get_notification_analytics(
    current_user: dict = Depends(get_current_user)
):
    """Get notification analytics (admin only)"""
    if current_user['role'] not in ['platform_admin', 'school_principal']:
        raise HTTPException(status_code=403, detail="Not authorized to view analytics")
    
    query = {}
    if current_user.get('tenant_id'):
        query['tenant_id'] = current_user['tenant_id']
    
    total = await gd_count(db.session, "notifications", query)
    
    read_query = {**query, "is_read": True}
    read_count = await gd_count(db.session, "notifications", read_query)
    
    unread_query = {**query, "is_read": False}
    unread_count = await gd_count(db.session, "notifications", unread_query)
    
    # By type
    by_type = {}
    for ntype in ["system", "attendance", "schedule", "assessment", "behaviour", "communication", "announcement"]:
        type_query = {**query, "type": ntype}
        by_type[ntype] = await gd_count(db.session, "notifications", type_query)
    
    # By priority
    by_priority = {}
    for priority in ["low", "medium", "high", "critical"]:
        priority_query = {**query, "priority": priority}
        by_priority[priority] = await gd_count(db.session, "notifications", priority_query)
    
    read_rate = round((read_count / total) * 100, 2) if total > 0 else 0
    
    return {
        "total_notifications": total,
        "read_count": read_count,
        "unread_count": unread_count,
        "read_rate": read_rate,
        "by_type": by_type,
        "by_priority": by_priority
    }


@router.post("/notifications/schedule")
async def schedule_notification(
    data: dict = Body(...),
    current_user: dict = Depends(get_current_user)
):
    """Schedule a notification for future delivery"""
    if current_user['role'] not in ['platform_admin', 'school_principal', 'school_sub_admin', 'school_admin']:
        raise HTTPException(status_code=403, detail="غير مصرح")

    schedule_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    tenant_id = current_user.get("tenant_id")

    scheduled_doc = {
        "id": schedule_id,
        "title": data.get("title"),
        "title_en": data.get("title_en"),
        "message": data.get("message"),
        "message_en": data.get("message_en"),
        "notification_type": data.get("notification_type", "announcement"),
        "priority": data.get("priority", "medium"),
        "recipient_ids": data.get("recipient_ids", []),
        "recipient_role": data.get("recipient_role"),
        "scheduled_at": data.get("scheduled_at"),
        "is_sent": False,
        "school_id": tenant_id,
        "created_by": current_user["id"],
        "created_at": now
    }

    await gd_insert(db.session, "scheduled_notifications", scheduled_doc)
    scheduled_doc.pop("_id", None)
    return {"success": True, "schedule_id": schedule_id, "message": "تم جدولة الإشعار بنجاح"}


@router.get("/notifications/scheduled")
async def get_scheduled_notifications(
    current_user: dict = Depends(get_current_user)
):
    """Get scheduled notifications"""
    if current_user['role'] not in ['platform_admin', 'school_principal', 'school_sub_admin', 'school_admin']:
        raise HTTPException(status_code=403, detail="غير مصرح")

    tenant_id = current_user.get("tenant_id")
    query = {"is_sent": False}
    if tenant_id:
        query["school_id"] = tenant_id

    notifications = await gd_find(db.session, "scheduled_notifications", query, order_by="scheduled_at", desc_order=False, limit=100)

    return {"scheduled": notifications, "total": len(notifications)}


@router.delete("/notifications/scheduled/{schedule_id}")
async def cancel_scheduled_notification(
    schedule_id: str,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN]))
):
    """Cancel a scheduled notification"""
    tenant_id = current_user.get("tenant_id")
    query = {"id": schedule_id}
    if tenant_id:
        query["school_id"] = tenant_id

    result = await gd_delete_one(db.session, "scheduled_notifications", query)
    if result == 0:
        raise HTTPException(status_code=404, detail="الإشعار المجدول غير موجود")
    return {"success": True, "message": "تم إلغاء الإشعار المجدول"}


@router.post("/notifications/preferences")
async def set_notification_preferences(
    data: dict = Body(...),
    current_user: dict = Depends(get_current_user)
):
    """Set notification preferences for user"""
    prefs = {
        "user_id": current_user["id"],
        "school_id": current_user.get("tenant_id"),
        "email_enabled": data.get("email_enabled", True),
        "push_enabled": data.get("push_enabled", True),
        "sms_enabled": data.get("sms_enabled", False),
        "quiet_hours_start": data.get("quiet_hours_start"),
        "quiet_hours_end": data.get("quiet_hours_end"),
        "disabled_types": data.get("disabled_types", []),
        "updated_at": datetime.now(timezone.utc).isoformat()
    }

    await gd_upsert(db.session, "notification_preferences", {"user_id": current_user["id"]}, prefs)

    return {"success": True, "message": "تم حفظ تفضيلات الإشعارات"}


@router.get("/notifications/preferences")
async def get_notification_preferences(
    current_user: dict = Depends(get_current_user)
):
    """Get notification preferences for user"""
    prefs = await gd_find_one(db.session, "notification_preferences", {"user_id": current_user["id"]})
    if not prefs:
        prefs = {
            "user_id": current_user["id"],
            "email_enabled": True,
            "push_enabled": True,
            "sms_enabled": False,
            "quiet_hours_start": None,
            "quiet_hours_end": None,
            "disabled_types": [],
            "is_default": True
        }
    return prefs

