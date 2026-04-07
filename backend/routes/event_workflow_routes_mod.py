"""
NASSAQ Route Module: Event & Workflow Engine
System events, triggers, workflow definitions, and automation rules.
"""
from fastapi import APIRouter, HTTPException, Depends, Query, Body
from pydantic import BaseModel
from typing import Optional, List, Dict
from datetime import datetime, timezone, timedelta
from enum import Enum
import uuid

from dependencies import (
    db, get_current_user, require_roles, UserRole, logger
)
from engines.sql_utils import gd_find, gd_find_one, gd_insert, gd_insert_many, gd_update_one, gd_update_many, gd_count, gd_delete_one, gd_delete_many, gd_distinct, _gd_inc


router = APIRouter()


class EventTypeEnum(str, Enum):
    STUDENT_ENROLLED = "student_enrolled"
    STUDENT_TRANSFERRED = "student_transferred"
    STUDENT_GRADUATED = "student_graduated"
    ATTENDANCE_ABSENT = "attendance_absent"
    ATTENDANCE_STREAK = "attendance_streak"
    GRADE_SUBMITTED = "grade_submitted"
    GRADE_FAILED = "grade_failed"
    BEHAVIOUR_INCIDENT = "behaviour_incident"
    BEHAVIOUR_ESCALATED = "behaviour_escalated"
    TIMETABLE_PUBLISHED = "timetable_published"
    ASSESSMENT_CREATED = "assessment_created"
    PARENT_NOTIFIED = "parent_notified"
    TEACHER_ASSIGNED = "teacher_assigned"
    SYSTEM_ALERT = "system_alert"
    CUSTOM = "custom"


class WorkflowStatusEnum(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    DISABLED = "disabled"


class EventCreate(BaseModel):
    event_type: str
    title: str
    description: Optional[str] = None
    entity_type: Optional[str] = None
    entity_id: Optional[str] = None
    metadata: Optional[Dict] = None
    severity: str = "info"


class WorkflowRuleCreate(BaseModel):
    name: str
    name_en: Optional[str] = None
    trigger_event: str
    conditions: Optional[Dict] = None
    actions: List[Dict]
    is_active: bool = True
    description: Optional[str] = None


@router.post("/events")
async def create_event(
    data: EventCreate,
    current_user: dict = Depends(get_current_user)
):
    """Record a system event"""
    school_id = current_user.get("tenant_id")
    event_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    event_doc = {
        "id": event_id,
        "tenant_id": school_id,
        "event_type": data.event_type,
        "title": data.title,
        "description": data.description,
        "entity_type": data.entity_type,
        "entity_id": data.entity_id,
        "metadata": data.metadata or {},
        "severity": data.severity,
        "triggered_by": current_user["id"],
        "triggered_by_name": current_user.get("full_name"),
        "processed": False,
        "created_at": now
    }

    await gd_insert(db.session, "system_events", event_doc)

    await _process_workflow_triggers(school_id, data.event_type, event_doc)

    event_doc.pop("_id", None)
    return event_doc


@router.get("/events")
async def get_events(
    event_type: Optional[str] = None,
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    severity: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 50,
    skip: int = 0,
    current_user: dict = Depends(get_current_user)
):
    """Get system events with filters"""
    school_id = current_user.get("tenant_id")
    query = {"tenant_id": school_id}

    if event_type:
        query["event_type"] = event_type
    if entity_type:
        query["entity_type"] = entity_type
    if entity_id:
        query["entity_id"] = entity_id
    if severity:
        query["severity"] = severity
    if start_date:
        query.setdefault("created_at", {})["$gte"] = start_date
    if end_date:
        query.setdefault("created_at", {})["$lte"] = end_date

    events = await gd_find(db.session, "system_events", query, order_by="created_at", desc_order=True, offset=skip, limit=limit)

    total = await gd_count(db.session, "system_events", query)

    return {"events": events, "total": total}


@router.get("/events/statistics")
async def get_event_statistics(
    period: str = "week",
    current_user: dict = Depends(get_current_user)
):
    """Get event statistics"""
    school_id = current_user.get("tenant_id")
    now = datetime.now(timezone.utc)

    if period == "day":
        start = (now - timedelta(days=1)).isoformat()
    elif period == "week":
        start = (now - timedelta(days=7)).isoformat()
    elif period == "month":
        start = (now - timedelta(days=30)).isoformat()
    else:
        start = (now - timedelta(days=365)).isoformat()

    query = {"tenant_id": school_id, "created_at": {"$gte": start}}
    events = await gd_find(db.session, "system_events", query, limit=10000)

    by_type = {}
    for e in events:
        et = e.get("event_type", "unknown")
        by_type[et] = by_type.get(et, 0) + 1

    by_severity = {}
    for e in events:
        sev = e.get("severity", "info")
        by_severity[sev] = by_severity.get(sev, 0) + 1

    daily = {}
    for e in events:
        d = e.get("created_at", "")[:10]
        daily[d] = daily.get(d, 0) + 1

    return {
        "period": period,
        "total_events": len(events),
        "by_type": dict(sorted(by_type.items(), key=lambda x: x[1], reverse=True)),
        "by_severity": by_severity,
        "daily_trend": dict(sorted(daily.items())),
        "most_common": max(by_type, key=by_type.get) if by_type else None
    }


@router.get("/events/{event_id}")
async def get_event(
    event_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get a specific event"""
    school_id = current_user.get("tenant_id")
    event = await gd_find_one(db.session, "system_events", {"id": event_id, "tenant_id": school_id})
    if not event:
        raise HTTPException(status_code=404, detail="الحدث غير موجود")
    return event


@router.post("/workflows/rules")
async def create_workflow_rule(
    data: WorkflowRuleCreate,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN]))
):
    """Create an automation workflow rule"""
    school_id = current_user.get("tenant_id")
    rule_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    rule_doc = {
        "id": rule_id,
        "tenant_id": school_id,
        "name": data.name,
        "name_en": data.name_en,
        "trigger_event": data.trigger_event,
        "conditions": data.conditions or {},
        "actions": data.actions,
        "is_active": data.is_active,
        "description": data.description,
        "execution_count": 0,
        "last_executed_at": None,
        "created_by": current_user["id"],
        "created_at": now,
        "updated_at": now
    }

    await gd_insert(db.session, "workflow_rules", rule_doc)
    rule_doc.pop("_id", None)
    return rule_doc


@router.get("/workflows/rules")
async def get_workflow_rules(
    trigger_event: Optional[str] = None,
    is_active: Optional[bool] = None,
    current_user: dict = Depends(get_current_user)
):
    """Get workflow rules"""
    school_id = current_user.get("tenant_id")
    query = {"tenant_id": school_id}
    if trigger_event:
        query["trigger_event"] = trigger_event
    if is_active is not None:
        query["is_active"] = is_active

    rules = await gd_find(db.session, "workflow_rules", query, order_by="created_at", desc_order=True, limit=100)
    return {"rules": rules, "total": len(rules)}


@router.put("/workflows/rules/{rule_id}")
async def update_workflow_rule(
    rule_id: str,
    data: dict = Body(...),
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN]))
):
    """Update a workflow rule"""
    school_id = current_user.get("tenant_id")
    rule = await gd_find_one(db.session, "workflow_rules", {"id": rule_id, "tenant_id": school_id})
    if not rule:
        raise HTTPException(status_code=404, detail="القاعدة غير موجودة")

    updates = {"updated_at": datetime.now(timezone.utc).isoformat()}
    for field in ["name", "name_en", "trigger_event", "conditions", "actions", "is_active", "description"]:
        if field in data:
            updates[field] = data[field]

    await gd_update_one(db.session, "workflow_rules", {"id": rule_id}, updates)
    return {"message": "تم تحديث القاعدة بنجاح", "id": rule_id}


@router.delete("/workflows/rules/{rule_id}")
async def delete_workflow_rule(
    rule_id: str,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN]))
):
    """Delete a workflow rule"""
    school_id = current_user.get("tenant_id")
    result = await gd_delete_one(db.session, "workflow_rules", {"id": rule_id, "tenant_id": school_id})
    if result == 0:
        raise HTTPException(status_code=404, detail="القاعدة غير موجودة")
    return {"message": "تم حذف القاعدة بنجاح"}


@router.post("/workflows/rules/{rule_id}/toggle")
async def toggle_workflow_rule(
    rule_id: str,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN]))
):
    """Toggle a workflow rule on/off"""
    school_id = current_user.get("tenant_id")
    rule = await gd_find_one(db.session, "workflow_rules", {"id": rule_id, "tenant_id": school_id})
    if not rule:
        raise HTTPException(status_code=404, detail="القاعدة غير موجودة")

    new_status = not rule.get("is_active", True)
    await gd_update_one(db.session, "workflow_rules", {"id": rule_id}, {"is_active": new_status, "updated_at": datetime.now(timezone.utc).isoformat()})
    return {"message": "تم تغيير حالة القاعدة", "is_active": new_status}


@router.get("/workflows/executions")
async def get_workflow_executions(
    rule_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
    current_user: dict = Depends(get_current_user)
):
    """Get workflow execution history"""
    school_id = current_user.get("tenant_id")
    query = {"tenant_id": school_id}
    if rule_id:
        query["rule_id"] = rule_id
    if status:
        query["status"] = status

    executions = await gd_find(db.session, "workflow_executions", query, order_by="executed_at", desc_order=True, limit=limit)

    return {"executions": executions, "total": len(executions)}


@router.get("/workflows/templates")
async def get_workflow_templates(
    current_user: dict = Depends(get_current_user)
):
    """Get pre-built workflow templates"""
    templates = [
        {
            "id": "absent-3-days",
            "name": "تنبيه غياب 3 أيام متتالية",
            "name_en": "3-day absence alert",
            "trigger_event": "attendance_absent",
            "conditions": {"consecutive_days": 3},
            "actions": [
                {"type": "notify_parent", "message": "ابنكم/ابنتكم تغيب {consecutive_days} أيام متتالية"},
                {"type": "notify_principal", "priority": "high"}
            ]
        },
        {
            "id": "grade-below-60",
            "name": "تنبيه درجة أقل من 60%",
            "name_en": "Grade below 60% alert",
            "trigger_event": "grade_submitted",
            "conditions": {"percentage_below": 60},
            "actions": [
                {"type": "notify_teacher", "message": "الطالب حصل على درجة أقل من 60%"},
                {"type": "flag_at_risk"}
            ]
        },
        {
            "id": "behaviour-escalation",
            "name": "تصعيد سلوك تلقائي",
            "name_en": "Auto behaviour escalation",
            "trigger_event": "behaviour_incident",
            "conditions": {"negative_count_in_30_days": 5},
            "actions": [
                {"type": "escalate_to_principal"},
                {"type": "notify_parent", "priority": "critical"}
            ]
        },
        {
            "id": "perfect-attendance",
            "name": "مكافأة حضور كامل",
            "name_en": "Perfect attendance reward",
            "trigger_event": "attendance_streak",
            "conditions": {"streak_days": 30},
            "actions": [
                {"type": "award_points", "points": 50},
                {"type": "notify_parent", "message": "مبروك! ابنكم/ابنتكم حقق حضور كامل لمدة 30 يوم"}
            ]
        },
        {
            "id": "new-student-welcome",
            "name": "ترحيب بالطالب الجديد",
            "name_en": "New student welcome",
            "trigger_event": "student_enrolled",
            "conditions": {},
            "actions": [
                {"type": "send_welcome_message"},
                {"type": "assign_orientation_schedule"},
                {"type": "notify_class_teacher"}
            ]
        }
    ]
    return {"templates": templates, "total": len(templates)}


async def _process_workflow_triggers(school_id: str, event_type: str, event_data: dict):
    """Process matching workflow rules for an event"""
    rules = await gd_find(db.session, "workflow_rules", {"tenant_id": school_id, "trigger_event": event_type, "is_active": True}, limit=50)

    for rule in rules:
        exec_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        execution = {
            "id": exec_id,
            "tenant_id": school_id,
            "rule_id": rule["id"],
            "rule_name": rule.get("name"),
            "event_id": event_data.get("id"),
            "event_type": event_type,
            "status": "completed",
            "actions_executed": len(rule.get("actions", [])),
            "executed_at": now
        }

        await gd_insert(db.session, "workflow_executions", execution)

        rule_doc = await gd_find_one(db.session, "workflow_rules", {"id": rule["id"]})
        cur_count = int(rule_doc.get("execution_count", 0) or 0) if rule_doc else 0
        await gd_update_one(db.session, "workflow_rules", {"id": rule["id"]}, {"execution_count": cur_count + 1, "last_executed_at": now})
