"""
NASSAQ — Automated Scheduled Message & Notification Dispatch Service.

Handles automated background polling, processing, and fan-out of scheduled
communications (messages and notifications) when their scheduled_at time is reached.
"""

import uuid
import logging
from typing import Any, Optional, List, Dict
from datetime import datetime, timezone

from dependencies import db as default_db
from engines.sql_utils import gd_find, gd_find_one, gd_insert, gd_update_one

logger = logging.getLogger("nassaq.scheduler")


def is_scheduled_time_due(scheduled_at_raw: Any, now_utc: Optional[datetime] = None) -> bool:
    """Return True if the scheduled time has arrived or passed."""
    if not scheduled_at_raw:
        return False

    if now_utc is None:
        now_utc = datetime.now(timezone.utc)

    try:
        # Numeric epoch timestamp
        if isinstance(scheduled_at_raw, (int, float)):
            if scheduled_at_raw > 1e11:  # milliseconds
                dt = datetime.fromtimestamp(scheduled_at_raw / 1000.0, tz=timezone.utc)
            else:
                dt = datetime.fromtimestamp(scheduled_at_raw, tz=timezone.utc)
            return dt <= now_utc

        s = str(scheduled_at_raw).strip()
        if not s:
            return False

        # Normalize trailing Z
        if s.endswith("Z") or s.endswith("z"):
            s = s[:-1] + "+00:00"

        # If date is YYYY-MM-DDTHH:MM (from datetime-local), normalize seconds
        if len(s) == 16 and "T" in s:
            s = s + ":00"

        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            # Naive datetime: compare with naive UTC and naive local
            return dt <= now_utc.replace(tzinfo=None) or dt <= now_utc
        else:
            return dt <= now_utc
    except Exception as parse_err:
        logger.debug(f"Could not parse scheduled_at '{scheduled_at_raw}' as datetime: {parse_err}")
        # Fallback string comparison for standard ISO representations
        try:
            return str(scheduled_at_raw) <= now_utc.isoformat()
        except Exception:
            return False


async def _resolve_recipients_for_scheduler(
    database,
    audience: str,
    school_id: Optional[str],
    audience_ids: List[str],
    *,
    allow_platform_wide: bool = False,
) -> List[str]:
    """Helper to resolve recipient IDs during automated scheduler dispatch."""
    from src.modules.communication.controllers.communication_routes import _resolve_recipient_ids
    return await _resolve_recipient_ids(
        database,
        audience,
        school_id,
        audience_ids,
        allow_platform_wide=allow_platform_wide,
    )


async def dispatch_single_scheduled_message(
    database,
    message_id: str,
    *,
    now_iso: Optional[str] = None,
    caller_is_platform_admin: bool = False,
) -> Dict[str, Any]:
    """Dispatch a single scheduled message, creating per-user notifications and updating status to sent."""
    if not now_iso:
        now_iso = datetime.now(timezone.utc).isoformat()

    message = await gd_find_one(database.session, "messages", {"id": message_id})
    if not message:
        return {"success": False, "error": "Message not found"}

    if message.get("status") != "scheduled":
        return {"success": False, "error": f"Message status is '{message.get('status')}', expected 'scheduled'"}

    school_id = message.get("school_id")
    audience = message.get("audience", "all")
    audience_ids = message.get("audience_ids") or []
    created_by = message.get("created_by")
    title = message.get("title", "")
    content = message.get("content", "")

    # Check creator role for platform-wide broadcast permission
    allow_platform = caller_is_platform_admin
    if not allow_platform and created_by:
        creator = await gd_find_one(database.session, "users", {"id": created_by})
        if creator and creator.get("role") == "platform_admin":
            allow_platform = True

    recipient_ids = await _resolve_recipients_for_scheduler(
        database,
        audience,
        school_id,
        audience_ids,
        allow_platform_wide=allow_platform or not school_id,
    )

    # Fan out per-user notifications
    for uid in recipient_ids:
        await gd_insert(database.session, "notifications", {
            "id": str(uuid.uuid4()),
            "user_id": uid,
            "tenant_id": school_id,
            "title": title,
            "message": content,
            "type": "announcement",
            "priority": "normal",
            "is_read": False,
            "extra_data": {
                "message_id": message_id,
                "audience": audience,
                "dispatched_by": "automated_scheduler",
            },
            "created_at": now_iso,
        })

    # Update message record atomically
    await gd_update_one(database.session, "messages", {"id": message_id}, {
        "status": "sent",
        "sent_at": now_iso,
        "sent_count": len(recipient_ids),
        "recipient_count": len(recipient_ids),
    })

    # Capture portfolio evidence if audience is parents
    if audience == "parents" and created_by:
        try:
            from engines.portfolio_evidence_engine import PortfolioEvidenceEngine
            _pe = PortfolioEvidenceEngine(database)
            await _pe.capture_evidence(
                teacher_id=created_by,
                school_id=school_id or "",
                evidence_type="parent_communication_log",
                title_ar=f"تواصل مع أولياء الأمور: {title}",
                title_en=f"Parent Communication: {title}",
                description_ar=f"رسالة إلى {len(recipient_ids)} ولي أمر",
                description_en=f"Message to {len(recipient_ids)} parents",
                source="auto",
                source_entity_type="message",
                source_entity_id=message_id,
                metadata={"recipient_count": len(recipient_ids), "audience": "parents"},
            )
        except Exception as _pe_err:
            logger.debug("Portfolio evidence capture failed during dispatch: %s", _pe_err)

    logger.info(
        f"Scheduled message dispatch: message_id={message_id} ('{title}') -> {len(recipient_ids)} recipient(s)"
    )
    return {
        "success": True,
        "message_id": message_id,
        "sent_count": len(recipient_ids),
    }


async def dispatch_due_scheduled_messages(database=None) -> int:
    """Find all messages with status='scheduled' whose scheduled_at <= now, and dispatch them."""
    if database is None:
        database = default_db

    now_dt = datetime.now(timezone.utc)
    now_iso = now_dt.isoformat()

    scheduled_messages = await gd_find(database.session, "messages", {"status": "scheduled"}, limit=500)
    if not scheduled_messages:
        return 0

    dispatched_count = 0
    for msg in scheduled_messages:
        msg_id = msg.get("id")
        scheduled_at = msg.get("scheduled_at")
        if not msg_id or not scheduled_at:
            continue

        if is_scheduled_time_due(scheduled_at, now_dt):
            try:
                res = await dispatch_single_scheduled_message(database, msg_id, now_iso=now_iso)
                if res.get("success"):
                    dispatched_count += 1
            except Exception as e:
                logger.error(f"Error dispatching scheduled message {msg_id}: {e}", exc_info=True)

    return dispatched_count


async def dispatch_due_scheduled_notifications(database=None) -> int:
    """Find all scheduled notifications with is_sent=False whose scheduled_at <= now, and dispatch them."""
    if database is None:
        database = default_db

    now_dt = datetime.now(timezone.utc)
    now_iso = now_dt.isoformat()

    scheduled_notifs = await gd_find(database.session, "scheduled_notifications", {"is_sent": False}, limit=500)
    if not scheduled_notifs:
        return 0

    dispatched_count = 0
    for sn in scheduled_notifs:
        sn_id = sn.get("id")
        scheduled_at = sn.get("scheduled_at")
        if not sn_id or not scheduled_at:
            continue

        if is_scheduled_time_due(scheduled_at, now_dt):
            try:
                school_id = sn.get("school_id")
                recipient_ids = sn.get("recipient_ids") or []
                recipient_role = sn.get("recipient_role")

                if not recipient_ids and recipient_role:
                    scope = {"is_active": True}
                    if school_id:
                        scope["tenant_id"] = school_id
                    if recipient_role == "all":
                        pass
                    elif recipient_role == "teachers":
                        scope["role"] = {"$in": ["teacher", "independent_teacher", "school_teacher"]}
                    else:
                        scope["role"] = recipient_role
                    users = await gd_find(database.session, "users", scope, limit=10000)
                    recipient_ids = [u["id"] for u in users if u.get("id")]

                for uid in recipient_ids:
                    await gd_insert(database.session, "notifications", {
                        "id": str(uuid.uuid4()),
                        "user_id": uid,
                        "tenant_id": school_id,
                        "title": sn.get("title") or "إشعار جديد",
                        "title_en": sn.get("title_en"),
                        "message": sn.get("message") or "",
                        "message_en": sn.get("message_en"),
                        "type": sn.get("notification_type", "announcement"),
                        "priority": sn.get("priority", "medium"),
                        "is_read": False,
                        "extra_data": {
                            "scheduled_notification_id": sn_id,
                            "dispatched_by": "automated_scheduler",
                        },
                        "created_at": now_iso,
                    })

                await gd_update_one(database.session, "scheduled_notifications", {"id": sn_id}, {
                    "is_sent": True,
                    "sent_at": now_iso,
                    "delivered_count": len(recipient_ids),
                })
                dispatched_count += 1
                logger.info(f"Dispatched scheduled notification {sn_id} to {len(recipient_ids)} recipient(s)")
            except Exception as e:
                logger.error(f"Error dispatching scheduled notification {sn_id}: {e}", exc_info=True)

    return dispatched_count


async def dispatch_all_due_communications(database=None) -> Dict[str, int]:
    """Sweep and dispatch all due scheduled messages and notifications."""
    if database is None:
        database = default_db

    messages_count = await dispatch_due_scheduled_messages(database)
    notifs_count = await dispatch_due_scheduled_notifications(database)
    return {
        "messages_dispatched": messages_count,
        "notifications_dispatched": notifs_count,
        "total_dispatched": messages_count + notifs_count,
    }
