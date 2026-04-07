"""
Product Intelligence Hub — Audit Logging System
نظام التدقيق والتتبع لمركز ذكاء المنتج
"""

from typing import Optional, Dict, Any
from datetime import datetime, timezone
from enum import Enum
import uuid
import logging

from sqlalchemy import select, and_, desc

from pg_models import IssueActivityLog
from engines.sql_utils import model_to_dict, models_to_dicts, dict_to_model

logger = logging.getLogger("nassaq.product_hub.audit")


class AuditAction(str, Enum):
    CREATED = "created"
    UPDATED = "updated"
    STATUS_CHANGED = "status_changed"
    ASSIGNED = "assigned"
    AI_ANALYZED = "ai_analyzed"
    DUPLICATE_DETECTED = "duplicate_detected"
    PROMPT_GENERATED = "prompt_generated"
    COMMENT_ADDED = "comment_added"
    ATTACHMENT_ADDED = "attachment_added"
    CLOSED = "closed"
    REOPENED = "reopened"
    FEEDBACK_CONFIRMED = "feedback_confirmed"


AUDIT_ACTION_LABELS = {
    "created": "إنشاء المشكلة",
    "updated": "تحديث المشكلة",
    "status_changed": "تغيير الحالة",
    "assigned": "تعيين الفريق",
    "ai_analyzed": "تحليل حكيم الذكي",
    "duplicate_detected": "اكتشاف تكرار",
    "prompt_generated": "توليد الأمر",
    "comment_added": "إضافة تعليق",
    "attachment_added": "إضافة مرفق",
    "closed": "إغلاق المشكلة",
    "reopened": "إعادة فتح المشكلة",
    "feedback_confirmed": "تأكيد ملاحظات المستخدم",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _resolve_role(user: dict) -> str:
    role = user.get("role", "")
    return "platform_admin" if role == "platform_admin" else "internal_user"


def _get_user_id(user: dict) -> str:
    return user.get("id", user.get("user_id", ""))


def _get_session():
    from dependencies import db
    return db.session


async def write_audit_log(
    issue_id: str,
    action: AuditAction,
    user: dict,
    notes: str = "",
    metadata: Optional[Dict[str, Any]] = None,
) -> dict:
    entry_id = str(uuid.uuid4())
    now = _now_iso()
    entry = {
        "id": entry_id,
        "issue_id": issue_id,
        "action": action.value,
        "performed_by": _get_user_id(user),
        "performed_by_name": user.get("full_name", ""),
        "timestamp": now,
        "details": {
            "role": _resolve_role(user),
            "notes": notes,
            "metadata": metadata or {},
        },
    }

    session = _get_session()
    obj = dict_to_model(IssueActivityLog, entry)
    session.add(obj)
    await session.flush()

    logger.info(
        f"[Audit] {action.value} on issue={issue_id[:8]} "
        f"by={_get_user_id(user)[:8]} role={_resolve_role(user)}"
    )
    return {
        "id": entry_id,
        "issue_id": issue_id,
        "action": action.value,
        "performed_by": _get_user_id(user),
        "performed_by_name": user.get("full_name", ""),
        "role": _resolve_role(user),
        "timestamp": now,
        "notes": notes,
        "metadata": metadata or {},
    }


async def audit_issue_created(issue_id: str, user: dict, issue_data: dict):
    await write_audit_log(
        issue_id, AuditAction.CREATED, user,
        notes=f"تم إنشاء المشكلة: {issue_data.get('title', '')}",
        metadata={
            "issue_type": issue_data.get("issue_type", ""),
            "section": issue_data.get("section", ""),
            "page": issue_data.get("page", ""),
            "employee_name": issue_data.get("employee_name", ""),
        }
    )


async def audit_issue_updated(issue_id: str, user: dict, changes: dict):
    fields = list(changes.keys())
    await write_audit_log(
        issue_id, AuditAction.UPDATED, user,
        notes=f"تم تحديث الحقول: {', '.join(fields)}",
        metadata={"fields_changed": fields, "changes": changes}
    )


async def audit_status_changed(
    issue_id: str, user: dict,
    from_status: str, to_status: str, note: str = "",
):
    action = AuditAction.STATUS_CHANGED
    notes = f"تغيير الحالة من {from_status} إلى {to_status}"

    if to_status in ("done", "rejected"):
        action = AuditAction.CLOSED
        notes = f"تم إغلاق المشكلة بحالة: {to_status}"

    if from_status in ("done", "rejected") and to_status == "under_review":
        action = AuditAction.REOPENED
        notes = "تم إعادة فتح المشكلة"

    if note:
        notes += f" — {note}"

    await write_audit_log(
        issue_id, action, user,
        notes=notes,
        metadata={
            "from_status": from_status,
            "to_status": to_status,
            "note": note,
        }
    )


async def audit_issue_assigned(
    issue_id: str, user: dict,
    team: str, assigned_to: Optional[str] = None, note: str = "",
):
    await write_audit_log(
        issue_id, AuditAction.ASSIGNED, user,
        notes=f"تم تعيين الفريق: {team}" + (f" — {note}" if note else ""),
        metadata={"team": team, "assigned_to": assigned_to, "note": note}
    )


async def audit_ai_analyzed(issue_id: str, user: dict, analysis: dict):
    await write_audit_log(
        issue_id, AuditAction.AI_ANALYZED, user,
        notes="اكتمل تحليل حكيم الذكي",
        metadata={
            "suggested_title": analysis.get("suggested_title", ""),
            "suggested_priority": analysis.get("suggested_priority", ""),
            "suggested_team": analysis.get("suggested_team", ""),
            "duplicate_count": len(analysis.get("duplicate_ids", [])),
        }
    )


async def audit_duplicate_detected(
    issue_id: str, user: dict, duplicate_of: str, confidence: Any = None,
):
    await write_audit_log(
        issue_id, AuditAction.DUPLICATE_DETECTED, user,
        notes=f"تم اكتشاف تكرار محتمل مع المشكلة: {duplicate_of[:8]}",
        metadata={"duplicate_of": duplicate_of, "confidence": str(confidence or "")}
    )


async def audit_prompt_generated(issue_id: str, user: dict):
    await write_audit_log(
        issue_id, AuditAction.PROMPT_GENERATED, user,
        notes="تم توليد الأمر البرمجي",
    )


async def audit_comment_added(issue_id: str, user: dict, comment_id: str, comment_type: str = "general"):
    await write_audit_log(
        issue_id, AuditAction.COMMENT_ADDED, user,
        notes="تم إضافة تعليق",
        metadata={"comment_id": comment_id, "comment_type": comment_type}
    )


async def audit_attachment_added(issue_id: str, user: dict, filename: str):
    await write_audit_log(
        issue_id, AuditAction.ATTACHMENT_ADDED, user,
        notes=f"تم إضافة مرفق: {filename}",
        metadata={"filename": filename}
    )


async def audit_feedback_confirmed(issue_id: str, user: dict, resolved: bool, comment: str = ""):
    await write_audit_log(
        issue_id, AuditAction.FEEDBACK_CONFIRMED, user,
        notes="أكد المستخدم حل المشكلة" if resolved else "رفض المستخدم الحل",
        metadata={"resolved": resolved, "comment": comment}
    )


async def get_audit_trail(issue_id: str, limit: int = 200) -> list:
    session = _get_session()
    stmt = (
        select(IssueActivityLog)
        .where(IssueActivityLog.issue_id == issue_id)
        .order_by(desc(IssueActivityLog.timestamp))
        .limit(limit)
    )
    result = await session.execute(stmt)
    return models_to_dicts(result.scalars().all())


async def get_full_timeline(issue_id: str) -> dict:
    entries = await get_audit_trail(issue_id, limit=500)
    return {
        "issue_id": issue_id,
        "total": len(entries),
        "timeline": entries,
        "actors": list({e.get("performed_by", "") for e in entries}),
        "actions_summary": _summarize_actions(entries),
    }


def _summarize_actions(entries: list) -> dict:
    summary = {}
    for e in entries:
        action = e.get("action") or e.get("event_type", "unknown")
        summary[action] = summary.get(action, 0) + 1
    return summary
