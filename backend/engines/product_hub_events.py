"""
Product Intelligence Hub — Event Flow Engine
محرك الأحداث لمركز ذكاء المنتج
"""

from enum import Enum
from typing import Optional, Dict, Any
from datetime import datetime, timezone, timedelta
import uuid
import logging

from sqlalchemy import select, update as sa_update

from pg_models import IssueActivityLog, ProductIssue
from engines.sql_utils import dict_to_model

logger = logging.getLogger("nassaq.product_hub.events")


class HubEvent(str, Enum):
    ISSUE_CREATED = "issue_created"
    ISSUE_UPDATED = "issue_updated"
    HAKIM_ANALYSIS_STARTED = "hakim_analysis_started"
    HAKIM_ANALYSIS_COMPLETED = "hakim_analysis_completed"
    DUPLICATE_DETECTED = "duplicate_detected"
    PROMPT_GENERATED = "prompt_generated"
    ISSUE_ASSIGNED = "issue_assigned"
    STATUS_CHANGED = "status_changed"
    SLA_WARNING_TRIGGERED = "sla_warning_triggered"
    ISSUE_MARKED_DONE = "issue_marked_done"
    FEEDBACK_LOOP_SENT = "feedback_loop_sent"
    USER_CONFIRMED_RESOLVED = "user_confirmed_resolved"
    USER_REJECTED_RESOLUTION = "user_rejected_resolution"
    ISSUE_REOPENED = "issue_reopened"
    COMMENT_ADDED = "comment_added"
    ATTACHMENT_ADDED = "attachment_added"


STATUS_LABELS = {
    "new": "جديد",
    "under_review": "تحت المراجعة",
    "in_progress": "قيد التنفيذ",
    "qa_validation": "تحقق الجودة",
    "done": "مكتمل",
    "rejected": "مرفوض",
    "user_feedback_confirmed": "أكده المستخدم",
}

VALID_STATUS_TRANSITIONS = {
    "new": {"under_review"},
    "under_review": {"in_progress", "rejected"},
    "in_progress": {"qa_validation"},
    "qa_validation": {"done", "in_progress"},
    "done": {"user_feedback_confirmed", "under_review"},
    "rejected": {"under_review"},
    "user_feedback_confirmed": set(),
}

FINAL_STATUSES = {"done", "rejected", "user_feedback_confirmed"}
OPEN_STATUSES = {"new", "under_review", "in_progress", "qa_validation"}

STATUS_PROGRESS = {
    "new": 10,
    "under_review": 25,
    "in_progress": 55,
    "qa_validation": 80,
    "done": 100,
    "rejected": 100,
    "user_feedback_confirmed": 100,
}

SLA_HOURS = {
    "critical": 24,
    "high": 72,
    "medium": 120,
    "low": None,
}

PRIORITY_LABELS = {
    "critical": "حرج",
    "high": "عالي",
    "medium": "متوسط",
    "low": "منخفض",
}


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def _get_user_id(user: dict) -> str:
    return user.get("id", user.get("user_id", ""))


def _get_session():
    from dependencies import db
    return db.session


async def emit_event(
    event: HubEvent,
    issue_id: str,
    user: dict,
    details: Optional[Dict[str, Any]] = None,
) -> None:
    session = _get_session()
    entry = {
        "id": str(uuid.uuid4()),
        "issue_id": issue_id,
        "action": event.value,
        "performed_by": _get_user_id(user),
        "performed_by_name": user.get("full_name", ""),
        "details": {
            "event_type": event.value,
            "entity_type": "product_issue",
            "performed_by_role": user.get("role", ""),
            **(details or {}),
        },
        "timestamp": datetime.now(timezone.utc),
    }
    obj = dict_to_model(IssueActivityLog, entry)
    session.add(obj)
    await session.flush()
    logger.info(f"[Event] {event.value} on issue={issue_id[:8]} by={_get_user_id(user)[:8]}")


def validate_status_transition(current_status: str, new_status: str) -> bool:
    allowed = VALID_STATUS_TRANSITIONS.get(current_status, set())
    return new_status in allowed


def get_transition_error(current_status: str, new_status: str) -> str:
    return (
        f"لا يمكن الانتقال من '{STATUS_LABELS.get(current_status, current_status)}' "
        f"إلى '{STATUS_LABELS.get(new_status, new_status)}'"
    )


def calculate_sla(priority: str, created_at: datetime) -> dict:
    sla_h = SLA_HOURS.get(priority)
    if not sla_h:
        return {"sla_deadline": None, "sla_status": None}
    deadline = created_at + timedelta(hours=sla_h)
    now = datetime.now(timezone.utc)
    return {
        "sla_deadline": deadline.isoformat(),
        "sla_status": "within" if deadline > now else "exceeded",
    }


def enrich_sla_state(issue: dict) -> dict:
    if issue.get("sla_deadline") and issue.get("status") not in FINAL_STATUSES:
        try:
            deadline = datetime.fromisoformat(issue["sla_deadline"].replace("Z", "+00:00"))
            now = datetime.now(timezone.utc)
            issue["sla_remaining_hours"] = max(0, round((deadline - now).total_seconds() / 3600, 2))
            issue["sla_status"] = "within" if deadline > now else "exceeded"
        except (ValueError, TypeError) as e:
            logging.getLogger("nassaq.product_hub").debug("SLA parse error: %s", e)
    issue["progress_percent"] = STATUS_PROGRESS.get(issue.get("status", "new"), 0)
    return issue


async def handle_issue_created(issue_id: str, issue: dict, user: dict) -> None:
    await emit_event(HubEvent.ISSUE_CREATED, issue_id, user, {
        "issue_type": issue.get("issue_type"),
        "priority": issue.get("priority"),
        "section": issue.get("section"),
        "page": issue.get("page"),
    })


async def handle_hakim_analysis(issue_id: str, user: dict, analysis: dict, source: str = "auto") -> None:
    await emit_event(HubEvent.HAKIM_ANALYSIS_STARTED, issue_id, user, {"source": source})

    await emit_event(HubEvent.HAKIM_ANALYSIS_COMPLETED, issue_id, user, {
        "suggested_title": analysis.get("suggested_title", ""),
        "suggested_priority": analysis.get("suggested_priority", ""),
        "suggested_team": analysis.get("suggested_team", ""),
        "duplicate_count": len(analysis.get("duplicate_ids", [])),
    })

    if analysis.get("duplicate_ids"):
        for dup_id in analysis["duplicate_ids"][:3]:
            await emit_event(HubEvent.DUPLICATE_DETECTED, issue_id, user, {
                "duplicate_of": dup_id,
                "detected_by": "hakim_ai",
            })


async def handle_prompt_generated(issue_id: str, user: dict) -> None:
    await emit_event(HubEvent.PROMPT_GENERATED, issue_id, user)


async def handle_status_changed(
    issue_id: str,
    user: dict,
    from_status: str,
    to_status: str,
    note: str = "",
) -> None:
    event = HubEvent.STATUS_CHANGED
    details = {"from": from_status, "to": to_status, "note": note}

    if to_status == "done":
        event = HubEvent.ISSUE_MARKED_DONE
        details["feedback_requested"] = True

    if to_status == "under_review" and from_status in ("done", "rejected"):
        event = HubEvent.ISSUE_REOPENED
        details["reason"] = note or "أعيد فتح المشكلة"

    await emit_event(event, issue_id, user, details)

    if to_status == "done":
        await emit_event(HubEvent.FEEDBACK_LOOP_SENT, issue_id, user, {
            "message": "تم حل المشكلة — هل تم حلها فعلاً؟",
        })


async def handle_feedback_response(
    issue_id: str,
    user: dict,
    resolved: bool,
    comment: str = "",
) -> None:
    if resolved:
        await emit_event(HubEvent.USER_CONFIRMED_RESOLVED, issue_id, user, {
            "comment": comment,
            "new_status": "user_feedback_confirmed",
        })
    else:
        await emit_event(HubEvent.USER_REJECTED_RESOLUTION, issue_id, user, {
            "comment": comment,
            "new_status": "under_review",
            "reopened": True,
        })


async def handle_issue_assigned(
    issue_id: str,
    user: dict,
    team: str,
    assigned_to: Optional[str] = None,
    note: str = "",
) -> None:
    await emit_event(HubEvent.ISSUE_ASSIGNED, issue_id, user, {
        "team": team,
        "assigned_to": assigned_to,
        "note": note,
    })


async def handle_comment_added(issue_id: str, user: dict, comment_id: str) -> None:
    await emit_event(HubEvent.COMMENT_ADDED, issue_id, user, {
        "comment_id": comment_id,
    })


async def handle_attachment_added(issue_id: str, user: dict, filename: str) -> None:
    await emit_event(HubEvent.ATTACHMENT_ADDED, issue_id, user, {
        "filename": filename,
    })


async def handle_issue_updated(issue_id: str, user: dict, changes: dict) -> None:
    await emit_event(HubEvent.ISSUE_UPDATED, issue_id, user, {
        "fields_changed": list(changes.keys()),
        "changes": changes,
    })


async def check_sla_warning(issue_id: str, issue: dict, user: dict) -> bool:
    if issue.get("sla_warning_emitted"):
        return False
    if issue.get("sla_deadline") and issue.get("status") in OPEN_STATUSES:
        try:
            deadline = datetime.fromisoformat(issue["sla_deadline"].replace("Z", "+00:00"))
            now = datetime.now(timezone.utc)
            if deadline <= now:
                await emit_event(HubEvent.SLA_WARNING_TRIGGERED, issue_id, user, {
                    "sla_deadline": issue["sla_deadline"],
                    "priority": issue.get("priority"),
                    "hours_exceeded": round((now - deadline).total_seconds() / 3600, 1),
                })
                session = _get_session()
                stmt = (
                    sa_update(ProductIssue)
                    .where(ProductIssue.id == issue_id)
                    .values(sla_warning_emitted=True)
                )
                await session.execute(stmt)
                await session.flush()
                return True
        except (ValueError, TypeError) as e:
            logging.getLogger("nassaq.product_hub").debug("SLA warning check error: %s", e)
    return False
