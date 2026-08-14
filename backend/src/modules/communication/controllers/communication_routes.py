"""
NASSAQ - Communication Routes
Communication and messaging endpoints
"""
from fastapi import APIRouter, HTTPException, Depends, Header
from typing import Optional, List
from datetime import datetime, timezone
from pydantic import BaseModel
import uuid
import logging
from engines.sql_utils import gd_find, gd_find_one, gd_insert, gd_insert_many, gd_update_one, gd_update_many, gd_count, gd_delete_one, gd_delete_many, gd_distinct, gd_upsert, _gd_aggregate
from src.core.guards.tenant_guard import independent_workspace_id, AI_INSIGHTS_SCOPE_DENIED_AR
from src.common.utils.tenant_scope import resolve_school_id

logger = logging.getLogger("nassaq.communication_routes")


def _comm_read_scope(current_user: dict, x_school_context: Optional[str]) -> Optional[str]:
    """Resolve the strict school_id to scope a Communication Center *read* by.

    Mirrors ``notification_routes_mod._notification_read_scope`` so the
    Communication Center tabs (صندوق الوارد / المرسلة / المجدولة) close the
    same cross-tenant preview leak that Task #788 fixed on the notifications
    surface:

    * Platform admins and active preview/impersonation sessions are routed
      through :func:`resolve_school_id`. During a valid preview (token minted
      by ``/role-switch/switch`` — carries ``is_impersonating`` and a pinned
      ``tenant_id``) this returns the previewed school id, so reads are scoped
      strictly to that tenant and a brand-new school shows empty tabs. A plain
      platform-admin token carrying a stale ``X-School-Context`` header (e.g.
      after a refresh replaced the short-lived impersonation token) FAILS
      CLOSED with 403 instead of silently returning cross-tenant rows. A
      native admin with no school context gets ``None`` (their existing
      platform-wide view).
    * Genuine school users (principals/admins) and Independent Teachers fall
      through to :func:`_resolve_caller_workspace`, so they resolve to their
      own workspace exactly as before — no behavioural change.
    """
    if (
        current_user.get("is_impersonating")
        or current_user.get("is_switched")
        or current_user.get("role") == "platform_admin"
    ):
        return resolve_school_id(current_user, x_school_context)
    return _resolve_caller_workspace(current_user)


def _resolve_caller_workspace(current_user: dict) -> Optional[str]:
    """Resolve the caller's tenant/workspace id for messaging cohort scoping.

    Returns the persisted ``tenant_id`` for school-affiliated users, the
    synthetic ``itw_{user_id}`` workspace id for independent teachers
    (covering both pre- and post-bootstrap states), or ``None`` for
    platform admins who may legitimately broadcast cross-tenant.

    Non-platform callers MUST always resolve to a non-empty workspace; the
    ``send_message`` route enforces that with a 403 to avoid the
    "tenant_id is None -> unscoped recipient query" leak that previously
    let an Independent Teacher's broadcast reach every other independent
    teacher's students/parents (Task #177, B-3).
    """
    return current_user.get("tenant_id") or independent_workspace_id(current_user)


class MessageCreate(BaseModel):
    title: str
    content: str
    audience: str  # all, teachers, students, parents, custom
    audience_ids: Optional[List[str]] = []
    scheduled_at: Optional[str] = None
    channels: List[str] = ["in_app"]  # in_app, email, sms


class MessageResponse(BaseModel):
    id: str
    title: str
    content: str
    audience: str
    status: str  # draft, scheduled, sent
    sent_count: int
    created_at: str
    scheduled_at: Optional[str] = None
    sent_at: Optional[str] = None


async def _resolve_recipient_ids(
    db,
    audience: str,
    school_id: Optional[str],
    audience_ids: List[str],
    *,
    allow_platform_wide: bool = False,
) -> List[str]:
    """Resolve target user_ids for a given audience scope.

    For the ``custom`` audience the supplied IDs are validated against the
    sender's tenant scope so a school principal/admin cannot inject
    notifications into other tenants.

    When ``allow_platform_wide`` is False (the default), a missing
    ``school_id`` is treated as a fail-closed authorization error and the
    helper returns an empty recipient list. This prevents an Independent
    Teacher (or any school-scoped role whose tenant cannot be resolved)
    from broadcasting cross-tenant via an unscoped recipient query — the
    leak that motivated Task #177 / B-3. Only PLATFORM_ADMIN-driven
    broadcasts pass ``allow_platform_wide=True``.
    """
    if not school_id and not allow_platform_wide:
        # Fail-closed: never fall through to a tenant-unscoped users query
        # for a non-platform caller.
        return []

    if audience == "custom":
        clean_ids = [uid for uid in (audience_ids or []) if uid]
        if not clean_ids:
            return []
        # Don't filter by is_active here — historically some users have a NULL
        # is_active flag and would silently drop out of the recipient list,
        # producing a "message sent" response with no actual notification.
        scope = {"id": {"$in": clean_ids}, "is_active": {"$ne": False}}
        if school_id:
            scope["tenant_id"] = school_id
        users = await gd_find(db.session, "users", scope, limit=10000)
        return [u["id"] for u in users if u.get("id")]

    base = {"is_active": True}
    if school_id:
        base["tenant_id"] = school_id

    if audience == "all":
        users = await gd_find(db.session, "users", base, limit=10000)
    elif audience == "teachers":
        users = await gd_find(db.session, "users", {**base, "role": {"$in": ["teacher", "independent_teacher", "school_teacher"]}}, limit=10000)
    elif audience == "students":
        users = await gd_find(db.session, "users", {**base, "role": "student"}, limit=10000)
    elif audience == "parents":
        users = await gd_find(db.session, "users", {**base, "role": "parent"}, limit=10000)
    elif audience == "schools":
        users = await gd_find(db.session, "users", {**base, "role": {"$in": ["school_principal", "school_admin"]}}, limit=10000)
    else:
        users = []

    return [u["id"] for u in users if u.get("id")]


def create_communication_routes(db, get_current_user, require_roles, UserRole):
    """Create communication router"""
    router = APIRouter(prefix="/communication", tags=["Communication"])
    
    @router.get("/stats")
    async def get_communication_stats(
        x_school_context: Optional[str] = Header(default=None, alias="X-School-Context"),
        current_user: dict = Depends(require_roles([UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN]))
    ):
        """Get communication statistics"""
        # Strict, fail-closed school scope. A plain platform-admin token with a
        # stale X-School-Context header raises 403 here instead of counting
        # every tenant's messages into a previewed school.
        school_id = _comm_read_scope(current_user, x_school_context)
        
        query = {}
        if school_id:
            query["school_id"] = school_id
        
        # Count messages
        total_sent = await gd_count(db.session, "messages", {**query, "status": "sent"})
        total_scheduled = await gd_count(db.session, "messages", {**query, "status": "scheduled"})
        total_drafts = await gd_count(db.session, "messages", {**query, "status": "draft"})
        
        # Count templates
        total_templates = await gd_count(db.session, "message_templates", query)
        
        # Received = notifications delivered to the current user. While a
        # platform admin previews/impersonates a school, strictly scope to
        # that school so the admin's own native-context notifications aren't
        # counted into the previewed school. Genuine school logins keep
        # user-only counting because legacy rows may have a NULL tenant_id
        # (mirrors notification_routes_mod._preview_tenant_scope).
        user_id = current_user.get("id")
        if user_id:
            received_query = {"user_id": user_id}
            is_preview = current_user.get("is_impersonating") or current_user.get("is_switched")
            if school_id and is_preview:
                received_query["tenant_id"] = school_id
            total_received = await gd_count(db.session, "notifications", received_query)
        else:
            total_received = 0

        return {
            "sent": total_sent,
            "scheduled": total_scheduled,
            "drafts": total_drafts,
            "templates": total_templates,
            "sent_messages": total_sent,
            "scheduled_messages": total_scheduled,
            "draft_messages": total_drafts,
            "received_messages": total_received,
        }
    
    @router.post("")
    async def send_message(
        message: MessageCreate,
        current_user: dict = Depends(require_roles([UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN]))
    ):
        """Send or schedule a message"""
        is_platform_admin = current_user.get("role") == UserRole.PLATFORM_ADMIN.value
        school_id = _resolve_caller_workspace(current_user)

        # Fail-closed: any non-platform caller (school principal/admin and,
        # in the future, an Independent Teacher granted NOTIFICATIONS_SEND)
        # must resolve to a concrete workspace id. Otherwise the audience
        # cohort below would fall through to a tenant-unscoped query and
        # leak across tenants — exactly the B-3 hotfix this task closes.
        if not school_id and not is_platform_admin:
            raise HTTPException(status_code=403, detail=AI_INSIGHTS_SCOPE_DENIED_AR)

        now = datetime.now(timezone.utc).isoformat()
        message_id = str(uuid.uuid4())

        # Determine status
        status = "sent"
        if message.scheduled_at:
            status = "scheduled"

        # Count recipients. We always pass the resolved school_id when the
        # caller is non-platform; the `if school_id else <unscoped>` ternary
        # used to silently broaden these counts when tenant resolution
        # failed.
        recipient_count = 0
        if message.audience == "all":
            recipient_count = await gd_count(db.session, "users", {"tenant_id": school_id}) if school_id else await gd_count(db.session, "users", {})
        elif message.audience == "teachers":
            recipient_count = await gd_count(db.session, "teachers", {"school_id": school_id}) if school_id else await gd_count(db.session, "teachers", {})
        elif message.audience == "students":
            recipient_count = await gd_count(db.session, "students", {"school_id": school_id}) if school_id else await gd_count(db.session, "students", {})
        elif message.audience == "parents":
            recipient_count = await gd_count(db.session, "users", {"role": "parent", "tenant_id": school_id}) if school_id else await gd_count(db.session, "users", {"role": "parent"})
        elif message.audience == "custom":
            recipient_count = len(message.audience_ids)
        
        message_doc = {
            "id": message_id,
            "title": message.title,
            "content": message.content,
            "audience": message.audience,
            "audience_ids": message.audience_ids,
            "channels": message.channels,
            "status": status,
            "sent_count": recipient_count if status == "sent" else 0,
            "recipient_count": recipient_count,
            "school_id": school_id,
            "created_by": current_user["id"],
            "created_at": now,
            "scheduled_at": message.scheduled_at,
            "sent_at": now if status == "sent" else None
        }
        
        await gd_insert(db.session, "messages", message_doc)
        
        # Create per-user in-app notifications if sent immediately
        if status == "sent":
            recipient_ids = await _resolve_recipient_ids(
                db, message.audience, school_id, message.audience_ids or [],
                allow_platform_wide=is_platform_admin,
            )
            for uid in recipient_ids:
                await gd_insert(db.session, "notifications", {
                    "id": str(uuid.uuid4()),
                    "user_id": uid,
                    "tenant_id": school_id,
                    "title": message.title,
                    "message": message.content,
                    "type": "announcement",
                    "priority": "normal",
                    "is_read": False,
                    "extra_data": {
                        "message_id": message_id,
                        "audience": message.audience,
                    },
                })
            # Update actual sent_count to reflect per-user fan-out
            await gd_update_one(db.session, "messages", {"id": message_id}, {"sent_count": len(recipient_ids)})
            recipient_count = len(recipient_ids)
        
        if status == "sent" and message.audience == "parents":
            try:
                from engines.portfolio_evidence_engine import PortfolioEvidenceEngine
                _pe = PortfolioEvidenceEngine(db)
                # Awaited inline so it shares the request's DB session safely.
                await _pe.capture_evidence(
                    teacher_id=current_user["id"],
                    school_id=school_id or "",
                    evidence_type="parent_communication_log",
                    title_ar=f"تواصل مع أولياء الأمور: {message.title}",
                    title_en=f"Parent Communication: {message.title}",
                    description_ar=f"رسالة إلى {recipient_count} ولي أمر",
                    description_en=f"Message to {recipient_count} parents",
                    source="auto", source_entity_type="message",
                    source_entity_id=message_id,
                    metadata={"recipient_count": recipient_count, "audience": "parents"},
                )
            except Exception as _pe_err:
                import logging
                logging.getLogger(__name__).debug("Portfolio evidence (parent_comm) failed: %s", _pe_err)

        return {
            "message": "تم إرسال الرسالة بنجاح" if status == "sent" else "تمت جدولة الرسالة بنجاح",
            "id": message_id,
            "status": status,
            "recipient_count": recipient_count
        }
    
    @router.get("")
    async def get_messages(
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 20,
        x_school_context: Optional[str] = Header(default=None, alias="X-School-Context"),
        current_user: dict = Depends(require_roles([UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN]))
    ):
        """Get list of messages"""
        # Strict, fail-closed school scope (see _comm_read_scope): a previewed
        # brand-new school returns no sent/scheduled/draft rows, and a plain
        # admin token + stale X-School-Context header raises 403.
        school_id = _comm_read_scope(current_user, x_school_context)
        
        query = {}
        if school_id:
            query["school_id"] = school_id
        if status:
            query["status"] = status
        
        messages = await gd_find(db.session, "messages", query, order_by="created_at", desc_order=True, offset=skip, limit=limit)
        
        total = await gd_count(db.session, "messages", query)
        
        return {
            "messages": messages,
            "total": total,
            "skip": skip,
            "limit": limit
        }
    
    @router.get("/templates")
    async def get_message_templates(
        x_school_context: Optional[str] = Header(default=None, alias="X-School-Context"),
        current_user: dict = Depends(require_roles([UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN]))
    ):
        """Get message templates"""
        # Fail-closed school scope so a previewed school never inherits another
        # tenant's saved templates (and a plain admin + stale header → 403).
        school_id = _comm_read_scope(current_user, x_school_context)
        
        # Default templates if none exist
        default_templates = [
            {
                "id": "1",
                "name": "إشعار عام",
                "name_en": "General Announcement",
                "content_template": "تحية طيبة،\n\n{message}\n\nمع تحياتنا،\nإدارة المدرسة",
                "icon": "bell"
            },
            {
                "id": "2",
                "name": "تذكير بموعد",
                "name_en": "Event Reminder",
                "content_template": "تذكير: {event_name}\nالتاريخ: {date}\nالوقت: {time}\n\nيرجى الحضور في الموعد المحدد.",
                "icon": "clock"
            },
            {
                "id": "3",
                "name": "تحديث النظام",
                "name_en": "System Update",
                "content_template": "عزيزي المستخدم،\n\nنود إعلامكم بتحديث جديد في النظام:\n{update_details}\n\nشكراً لتعاونكم.",
                "icon": "refresh"
            },
            {
                "id": "4",
                "name": "طلب معلومات",
                "name_en": "Information Request",
                "content_template": "السلام عليكم،\n\nنرجو منكم تزويدنا بالمعلومات التالية:\n{required_info}\n\nوذلك في موعد أقصاه {deadline}.",
                "icon": "mail"
            }
        ]
        
        query = {}
        if school_id:
            query["school_id"] = school_id
        
        templates = await gd_find(db.session, "message_templates", query, limit=100)
        
        if not templates:
            return default_templates
        
        return templates
    
    @router.get("/audience")
    async def get_audience_stats(
        x_school_context: Optional[str] = Header(default=None, alias="X-School-Context"),
        current_user: dict = Depends(require_roles([UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN]))
    ):
        """Get audience statistics for messaging"""
        # Fail-closed school scope so a preview reflects the previewed school's
        # audience counts (and a plain admin + stale header → 403) rather than
        # leaking a platform-wide total.
        school_id = _comm_read_scope(current_user, x_school_context)
        
        if school_id:
            teachers = await gd_count(db.session, "teachers", {"school_id": school_id, "is_active": True})
            students = await gd_count(db.session, "students", {"school_id": school_id, "is_active": True})
            parents = await gd_count(db.session, "users", {"role": "parent", "tenant_id": school_id, "is_active": True})
            total = teachers + students + parents
        else:
            # Platform-wide for admins
            total = await gd_count(db.session, "users", {"is_active": True})
            teachers = await gd_count(db.session, "teachers", {"is_active": True})
            students = await gd_count(db.session, "students", {"is_active": True})
            parents = await gd_count(db.session, "users", {"role": "parent", "is_active": True})
        
        return [
            {"id": "all", "name": "الجميع", "name_en": "Everyone", "count": total, "icon": "users"},
            {"id": "teachers", "name": "المعلمين", "name_en": "Teachers", "count": teachers, "icon": "user-check"},
            {"id": "students", "name": "الطلاب", "name_en": "Students", "count": students, "icon": "graduation-cap"},
            {"id": "parents", "name": "أولياء الأمور", "name_en": "Parents", "count": parents, "icon": "users"}
        ]
    
    @router.get("/audience-counts")
    async def get_audience_counts(
        current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))
    ):
        """Get audience counts for broadcast messaging"""
        all_users = await gd_count(db.session, "users", {"is_active": True})
        schools = await gd_count(db.session, "schools", {})
        teachers = await gd_count(db.session, "users", {"role": {"$in": ["teacher", "independent_teacher"]}, "is_active": True})
        students = await gd_count(db.session, "users", {"role": "student", "is_active": True})
        principals = await gd_count(db.session, "users", {"role": "school_principal", "is_active": True})
        parents = await gd_count(db.session, "users", {"role": "parent", "is_active": True})
        
        return {
            "all": all_users,
            "schools": schools,
            "teachers": teachers,
            "students": students,
            "principals": principals,
            "parents": parents
        }
    
    @router.get("/scheduled")
    async def get_scheduled_messages(
        current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))
    ):
        """Get scheduled messages"""
        messages = await gd_find(db.session, "messages", {"status": "scheduled"}, order_by="scheduled_at", desc_order=False, limit=50)
        
        return {
            "messages": [
                {
                    "id": str(m.get("id", m.get("_id"))),
                    "title": m.get("title", ""),
                    "message": m.get("content", ""),
                    "target_audience": m.get("audience", "all"),
                    "scheduled_at": m.get("scheduled_at", ""),
                    "status": m.get("status", "scheduled"),
                    "created_at": m.get("created_at", ""),
                }
                for m in messages
            ],
            "total": len(messages)
        }
    
    @router.get("/sent")
    async def get_sent_messages(
        current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))
    ):
        """Get sent messages history"""
        messages = await gd_find(db.session, "messages", {"status": "sent"}, order_by="sent_at", desc_order=True, limit=50)
        
        return {
            "messages": [
                {
                    "id": str(m.get("id", m.get("_id"))),
                    "title": m.get("title", ""),
                    "message": m.get("content", "")[:100] + "..." if len(m.get("content", "")) > 100 else m.get("content", ""),
                    "target_audience": m.get("audience", "all"),
                    "status": m.get("status", "sent"),
                    "sent_at": m.get("sent_at", ""),
                    "sent_by_name": m.get("sent_by_name", ""),
                }
                for m in messages
            ],
            "total": len(messages)
        }
    
    from src.core.guards.tenant_guard import require_full_school_tenant as _require_full_school_tenant

    @router.post("/broadcast", dependencies=[Depends(_require_full_school_tenant)])
    async def send_broadcast_message(
        message: MessageCreate,
        # Phase 0 §4.B-2 — IT gate runs first via router dep above so the
        # canonical Arabic 403 is returned instead of "Insufficient
        # permissions" from the role check.
        current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN])),
    ):
        """Send broadcast message to all users"""
        now = datetime.now(timezone.utc).isoformat()
        message_id = str(uuid.uuid4())
        
        # Count recipients
        recipient_count = 0
        if message.audience == "all":
            recipient_count = await gd_count(db.session, "users", {"is_active": True})
        elif message.audience == "teachers":
            recipient_count = await gd_count(db.session, "users", {"role": {"$in": ["teacher", "independent_teacher"]}, "is_active": True})
        elif message.audience == "students":
            recipient_count = await gd_count(db.session, "users", {"role": "student", "is_active": True})
        elif message.audience == "schools":
            recipient_count = await gd_count(db.session, "users", {"role": "school_principal", "is_active": True})
        
        message_doc = {
            "id": message_id,
            "title": message.title,
            "content": message.content,
            "audience": message.audience,
            "channels": message.channels,
            "status": "sent",
            "sent_count": recipient_count,
            "created_at": now,
            "sent_at": now,
            "sent_by": current_user.get("id"),
            "sent_by_name": current_user.get("full_name", "")
        }
        
        await gd_insert(db.session, "messages", message_doc)
        
        # Fan-out per-user notifications (platform-wide broadcast).
        # PLATFORM_ADMIN explicitly opts into the cross-tenant cohort here;
        # every other entry point passes a concrete workspace id.
        recipient_ids = await _resolve_recipient_ids(
            db, message.audience, None, message.audience_ids or [],
            allow_platform_wide=True,
        )
        for uid in recipient_ids:
            await gd_insert(db.session, "notifications", {
                "id": str(uuid.uuid4()),
                "user_id": uid,
                "title": message.title,
                "message": message.content,
                "type": "broadcast",
                "priority": "normal",
                "is_read": False,
                "extra_data": {"message_id": message_id, "audience": message.audience},
            })
        actual_count = len(recipient_ids)
        await gd_update_one(db.session, "messages", {"id": message_id}, {"sent_count": actual_count})
        
        return {
            "success": True,
            "message_id": message_id,
            "recipients_count": actual_count,
            "message": f"تم إرسال الرسالة إلى {actual_count} مستخدم"
        }
    
    @router.get("/received")
    async def get_received_messages(
        x_school_context: Optional[str] = Header(default=None, alias="X-School-Context"),
        current_user: dict = Depends(get_current_user)
    ):
        """Get received messages for current user"""
        user_id = current_user.get("id")
        user_role = current_user.get("role")

        # Resolve the caller's workspace. School users and Independent Teachers
        # resolve to their own workspace (unchanged); platform-admin/preview
        # sessions route through the fail-closed scope so a previewed brand-new
        # school shows an empty inbox and a plain admin token + stale
        # X-School-Context header raises 403 instead of leaking every tenant's
        # sent messages.
        school_id = _comm_read_scope(current_user, x_school_context)

        # Non-platform-admin callers must always resolve to a workspace.
        # Fail closed if we cannot determine one to prevent cross-tenant leaks.
        if not school_id and user_role != "platform_admin":
            raise HTTPException(status_code=403, detail="تعذّر تحديد مساحة العمل")

        # Build query based on user's role and school.
        #
        # IMPORTANT tenant-isolation invariant:
        # A school/workspace inbox must only show messages that are explicitly
        # stored for that workspace. Historical platform-wide rows
        # (`school_id is None`) are announcements/broadcast history, not
        # personal inbox items for every future workspace. Including
        # `school_id=None` here caused newly-created schools to inherit old
        # Communication Centre messages immediately after signup.
        query = {"status": "sent"}
        
        if school_id:
            query["school_id"] = school_id
        
        # Filter by audience
        audience_filter = ["all"]
        if user_role in ["teacher", "independent_teacher", "school_teacher"]:
            audience_filter.append("teachers")
        elif user_role == "student":
            audience_filter.append("students")
        elif user_role == "parent":
            audience_filter.append("parents")

        # Pull the broadcast audiences in one query and any custom-targeted
        # message in another, then merge.  We can't express JSON-array
        # containment cleanly through the gd_find filter helpers, so we
        # post-filter the small set of custom messages in Python.  Without
        # this, direct messages sent from the platform/school admin to a
        # specific user (audience="custom" with audience_ids=[user_id])
        # never appear in the recipient's inbox.
        broadcast_query = {**query, "audience": {"$in": audience_filter}}
        custom_query = {**query, "audience": "custom"}

        broadcast_msgs = await gd_find(db.session, "messages", broadcast_query, order_by="sent_at", desc_order=True, limit=50)
        custom_msgs = await gd_find(db.session, "messages", custom_query, order_by="sent_at", desc_order=True, limit=200)
        custom_msgs = [m for m in custom_msgs if user_id in (m.get("audience_ids") or [])]

        seen_ids = set()
        messages = []
        for m in (broadcast_msgs + custom_msgs):
            mid = m.get("id")
            if mid in seen_ids:
                continue
            seen_ids.add(mid)
            messages.append(m)
        messages.sort(key=lambda m: m.get("sent_at") or "", reverse=True)
        messages = messages[:50]
        
        # Add read status
        for msg in messages:
            read_by = msg.get("read_by", [])
            msg["is_read"] = user_id in read_by
        
        return {
            "messages": messages,
            "total": len(messages),
            "unread_count": len([m for m in messages if not m.get("is_read")])
        }
    
    @router.put("/{message_id}/read")
    async def mark_message_read(
        message_id: str,
        current_user: dict = Depends(get_current_user)
    ):
        """Mark message as read"""
        user_id = current_user.get("id")
        user_role = current_user.get("role")

        # Resolve the caller's workspace using the canonical helper so that
        # independent-teacher accounts get their synthetic workspace id.
        caller_workspace = _resolve_caller_workspace(current_user)

        # Non-platform-admin callers must always resolve to a workspace.
        if not caller_workspace and user_role != "platform_admin":
            raise HTTPException(status_code=403, detail="تعذّر تحديد مساحة العمل")

        msg = await gd_find_one(db.session, "messages", {"id": message_id})
        if not msg:
            # Return success silently so callers cannot enumerate foreign ids.
            return {"success": True, "message": "تم تعيين الرسالة كمقروءة"}

        # --- Object-level authorization ---
        # The caller must be a valid recipient of this message.
        # 1. Tenant check: message must belong to the caller's workspace.
        #    Platform-wide `school_id=None` rows are not personal inbox items;
        #    allowing them here makes every new workspace inherit historical
        #    messages and bypasses tenant segmentation.
        msg_school_id = msg.get("school_id")
        if user_role != "platform_admin":
            if msg_school_id != caller_workspace:
                raise HTTPException(status_code=403, detail="غير مصرح لك بالوصول إلى هذه الرسالة")

        # 2. Audience check: the caller's role or user id must be in the intended audience.
        audience = msg.get("audience")
        audience_ids = msg.get("audience_ids") or []
        role_audience_map = {
            "teacher": "teachers",
            "independent_teacher": "teachers",
            "school_teacher": "teachers",
            "student": "students",
            "parent": "parents",
        }
        caller_audience_label = role_audience_map.get(user_role)
        is_valid_recipient = (
            audience == "all"
            or (caller_audience_label and audience == caller_audience_label)
            or (audience == "custom" and user_id in audience_ids)
            or user_role in ("school_principal", "school_admin", "platform_admin")
        )
        if not is_valid_recipient:
            raise HTTPException(status_code=403, detail="غير مصرح لك بالوصول إلى هذه الرسالة")

        read_by = msg.get("read_by") or []
        if user_id not in read_by:
            read_by.append(user_id)
            await gd_update_one(db.session, "messages", {"id": message_id}, {"read_by": read_by})

        return {"success": True, "message": "تم تعيين الرسالة كمقروءة"}
    
    @router.put("/{message_id}")
    async def update_scheduled_message(
        message_id: str,
        data: dict,
        current_user: dict = Depends(require_roles([UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN]))
    ):
        """Update a scheduled message"""
        query = {"id": message_id}
        if current_user['role'] != 'platform_admin':
            tenant_id = current_user.get("tenant_id")
            if tenant_id:
                query["school_id"] = tenant_id

        message = await gd_find_one(db.session, "messages", query)
        if not message:
            raise HTTPException(status_code=404, detail="الرسالة غير موجودة")
        
        if message.get("status") != "scheduled":
            raise HTTPException(status_code=400, detail="يمكن تعديل الرسائل المجدولة فقط")
        
        # Update allowed fields
        update_fields = {}
        if "title" in data:
            update_fields["title"] = data["title"]
        if "content" in data:
            update_fields["content"] = data["content"]
        if "audience" in data:
            update_fields["audience"] = data["audience"]
        if "scheduled_at" in data:
            update_fields["scheduled_at"] = data["scheduled_at"]
        
        update_fields["updated_at"] = datetime.now(timezone.utc).isoformat()
        
        await gd_update_one(db.session, "messages", {"id": message_id}, update_fields)
        
        return {"success": True, "message": "تم تحديث الرسالة المجدولة"}
    
    @router.post("/{message_id}/send-now")
    async def send_scheduled_message_now(
        message_id: str,
        current_user: dict = Depends(require_roles([UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN]))
    ):
        """Send a scheduled message immediately"""
        query = {"id": message_id}
        if current_user['role'] != 'platform_admin':
            tenant_id = current_user.get("tenant_id")
            if tenant_id:
                query["school_id"] = tenant_id

        message = await gd_find_one(db.session, "messages", query)
        if not message:
            raise HTTPException(status_code=404, detail="الرسالة غير موجودة")
        
        if message.get("status") != "scheduled":
            raise HTTPException(status_code=400, detail="هذه الرسالة ليست مجدولة")
        
        now = datetime.now(timezone.utc).isoformat()
        
        # Update status to sent
        await gd_update_one(db.session, "messages", {"id": message_id}, {
                "status": "sent",
                "sent_at": now,
                "sent_count": message.get("recipient_count", 0)
            })
        
        # Create notification
        notification_doc = {
            "id": str(uuid.uuid4()),
            "message_id": message_id,
            "title": message.get("title"),
            "content": message.get("content"),
            "type": "announcement",
            "school_id": message.get("school_id"),
            "audience": message.get("audience"),
            "created_at": now,
            "read_by": []
        }
        await gd_insert(db.session, "notifications", notification_doc)
        
        return {
            "success": True,
            "message": "تم إرسال الرسالة بنجاح",
            "sent_count": message.get("recipient_count", 0)
        }
    
    @router.delete("/{message_id}")
    async def delete_message(
        message_id: str,
        current_user: dict = Depends(require_roles([UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN]))
    ):
        """Delete a message"""
        query = {"id": message_id}
        if current_user['role'] != 'platform_admin':
            tenant_id = current_user.get("tenant_id")
            if tenant_id:
                query["school_id"] = tenant_id

        result = await gd_delete_one(db.session, "messages", query)
        
        if result == 0:
            raise HTTPException(status_code=404, detail="الرسالة غير موجودة")
        
        return {"success": True, "message": "تم حذف الرسالة"}
    
    @router.post("/templates")
    async def create_message_template(
        data: dict,
        current_user: dict = Depends(require_roles([UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN]))
    ):
        """Create a message template"""
        school_id = current_user.get("tenant_id")
        
        template = {
            "id": str(uuid.uuid4()),
            "name": data.get("name"),
            "name_en": data.get("name_en", data.get("name")),
            "content_template": data.get("content_template"),
            "icon": data.get("icon", "mail"),
            "school_id": school_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "created_by": current_user.get("id")
        }
        
        await gd_insert(db.session, "message_templates", template)
        template.pop("_id", None)
        
        return {"success": True, "template": template}
    
    return router
