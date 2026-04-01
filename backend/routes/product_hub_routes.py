"""
Product Intelligence Hub — مركز ذكاء المنتج
Internal governance, issue tracking, and AI-assisted analysis system.

API Contracts:
- POST   /issues                    — Create issue (any authenticated user)
- GET    /issues                    — List issues (own for users, all for admin)
- GET    /issues/{id}               — Issue detail (own for users, any for admin)
- PATCH  /issues/{id}               — Update issue fields (admin only)
- PUT    /issues/{id}/status        — Change status (admin only)
- PUT    /issues/{id}/assign        — Assign team (admin only)
- PUT    /issues/{id}/title         — Update title (admin only)
- PUT    /issues/{id}/priority      — Update priority (admin only)
- POST   /issues/{id}/comments      — Add comment (owner + admin)
- GET    /issues/{id}/comments      — Get comments (owner + admin)
- POST   /issues/{id}/feedback      — Submit feedback (owner + admin)
- GET    /issues/{id}/prompt        — Get generated prompt (admin only)
- POST   /issues/{id}/generate-prompt — Regenerate prompt (admin only)
- GET    /issues/{id}/hakim-insights — Get Hakim analysis (admin only)
- GET    /issues/{id}/activity-log  — Get activity log (owner + admin)
- GET    /issues/{id}/duplicates    — Get duplicate matches (admin only)
- GET    /dashboard                 — Dashboard analytics (admin only)
- GET    /config                    — Hub configuration (any authenticated)

Collections:
- product_issues: Main issue storage
- issue_activity_log: Activity timeline + event log + audit trail
- issue_comments: Discussion threads
- issue_duplicates_map: Duplicate detection results
"""

from fastapi import APIRouter, HTTPException, Depends, Query, Body
from typing import Optional, List
from datetime import datetime, timezone, timedelta
import uuid
import logging
import json

from dependencies import db, get_current_user, require_roles, UserRole
from engines.product_hub_rbac import (
    HubAction, HubRole, is_platform_admin, check_permission,
    enforce_permission, enforce_ownership_or_admin,
    check_resource_ownership, redact_issue_for_role,
    require_hub_action, get_user_id, resolve_hub_role,
    is_main_admin, is_super_admin,
)
from engines.product_hub_events import (
    HubEvent, emit_event,
    validate_status_transition, get_transition_error,
    calculate_sla, enrich_sla_state,
    handle_issue_created, handle_hakim_analysis,
    handle_prompt_generated, handle_status_changed,
    handle_feedback_response, handle_issue_assigned,
    handle_comment_added, handle_attachment_added,
    handle_issue_updated, check_sla_warning,
    VALID_STATUS_TRANSITIONS, FINAL_STATUSES, OPEN_STATUSES,
    STATUS_LABELS, PRIORITY_LABELS, SLA_HOURS, STATUS_PROGRESS,
)
from engines.product_hub_audit import (
    AuditAction, write_audit_log,
    audit_issue_created, audit_issue_updated,
    audit_status_changed, audit_issue_assigned,
    audit_ai_analyzed, audit_duplicate_detected,
    audit_prompt_generated, audit_comment_added,
    audit_attachment_added, audit_feedback_confirmed,
    get_audit_trail, get_full_timeline,
)
from models.product_hub_models import (
    IssueCreate, IssueUpdate, IssueComment, StatusUpdate,
    AssignIssue, FeedbackResponse, TitleUpdate, PriorityUpdate,
    ISSUE_TYPE_LABELS, ISSUE_TYPE_COMPAT, DYNAMIC_FIELDS_BY_TYPE,
    ACCOUNT_TYPE_OPTIONS, SECTION_OPTIONS,
    VALID_ISSUE_TYPES, VALID_ACCOUNT_TYPES, VALID_SECTIONS, VALID_TEAMS,
    IssueType, IssuePriority, IssueStatus,
    CommentType, AuditRole,
)

logger = logging.getLogger("nassaq.product_hub")

router = APIRouter(prefix="/product-hub", tags=["Product Intelligence Hub"])


def _hub_error(status_code: int, error_code: str, message: str, details: dict = None):
    raise HTTPException(
        status_code=status_code,
        detail={
            "success": False,
            "error_code": error_code,
            "message": message,
            "details": details or {},
        }
    )


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


async def _run_hakim_analysis(issue: dict) -> dict:
    try:
        from openai import OpenAI
        import os
        api_key = os.environ.get("AI_INTEGRATIONS_OPENAI_API_KEY", "")
        base_url = os.environ.get("AI_INTEGRATIONS_OPENAI_BASE_URL", "")
        if not api_key:
            return _fallback_analysis(issue)

        client = OpenAI(api_key=api_key, base_url=base_url if base_url else None)

        all_issues = await db.product_issues.find(
            {"status": {"$nin": ["rejected"]}},
            {"_id": 0, "id": 1, "title": 1, "issue_type": 1, "section": 1, "page": 1,
             "current_behavior": 1, "status": 1}
        ).sort("created_at", -1).to_list(50)

        existing_summaries = []
        for ex in all_issues[:30]:
            existing_summaries.append(
                f"[{ex.get('id','')[:8]}] {ex.get('title','')} | {ex.get('section','')} > {ex.get('page','')} | {ex.get('current_behavior','')[:100]}"
            )

        prompt = f"""You are Hakim (حكيم), an AI product intelligence assistant for NASSAQ school management system.

Analyze this issue submission and provide structured intelligence:

Issue Type: {issue.get('issue_type', '')}
Section: {issue.get('section', '')}
Page: {issue.get('page', '')}
Current Behavior: {issue.get('current_behavior', '')}
Expected Behavior: {issue.get('expected_behavior', '')}
Steps to Reproduce: {issue.get('steps_to_reproduce', '')}
Error Message: {issue.get('error_message', '')}
Account Type: {issue.get('account_type', '')}

Existing issues in system:
{chr(10).join(existing_summaries) if existing_summaries else 'No existing issues'}

Respond in this exact JSON format (Arabic text preferred):
{{
  "suggested_title": "concise Arabic title for the issue",
  "suggested_priority": "critical|high|medium|low",
  "priority_reasoning": "brief reasoning in Arabic",
  "suggested_team": "Frontend|Backend|DevOps|Design|QA|Product",
  "team_reasoning": "brief reasoning in Arabic",
  "duplicate_ids": ["list of similar issue IDs if any"],
  "duplicate_note": "note about duplicates in Arabic or empty string",
  "technical_notes": "technical analysis in Arabic",
  "impact_assessment": "impact assessment in Arabic"
}}"""

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a product intelligence AI. Respond ONLY with valid JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=600,
        )

        text = response.choices[0].message.content.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        analysis = json.loads(text)

        for key, default in [
            ("suggested_title", ""), ("suggested_priority", "medium"),
            ("suggested_team", "Backend"), ("duplicate_ids", []),
            ("duplicate_note", ""), ("technical_notes", ""),
            ("impact_assessment", ""), ("priority_reasoning", ""),
            ("team_reasoning", ""),
        ]:
            analysis.setdefault(key, default)
        return analysis

    except Exception as e:
        logger.warning(f"Hakim AI analysis failed: {e}")
        return _fallback_analysis(issue)


def _fallback_analysis(issue: dict) -> dict:
    type_to_team = {
        "bug": "Backend", "error": "Backend", "ui_issue": "Frontend",
        "ux_issue": "Design", "performance_issue": "DevOps", "content_issue": "Product",
        "feature_request": "Product", "improvement_suggestion": "Product",
        "permission_issue": "Backend", "workflow_issue": "Backend",
        "integration_issue": "Backend", "other": "Product",
        "performance": "DevOps", "content": "Product",
        "improvement": "Product", "permission": "Backend",
        "workflow": "Backend", "integration": "Backend",
    }
    type_to_priority = {
        "bug": "high", "error": "high", "performance_issue": "high",
        "permission_issue": "medium", "integration_issue": "medium",
        "performance": "high", "permission": "medium", "integration": "medium",
    }
    return {
        "suggested_title": f"{ISSUE_TYPE_LABELS.get(issue.get('issue_type', ''), 'مشكلة')} في {issue.get('page', 'الصفحة')}",
        "suggested_priority": type_to_priority.get(issue.get("issue_type", ""), "medium"),
        "priority_reasoning": "تقدير أولي بناءً على نوع المشكلة",
        "suggested_team": type_to_team.get(issue.get("issue_type", ""), "Product"),
        "team_reasoning": "فريق مقترح بناءً على نوع المشكلة",
        "duplicate_ids": [],
        "duplicate_note": "",
        "technical_notes": "",
        "impact_assessment": "",
    }


async def _generate_prompt(issue: dict) -> str:
    hakim = issue.get("hakim_analysis", {})
    return f"""[ISSUE TYPE] {ISSUE_TYPE_LABELS.get(issue.get('issue_type', ''), issue.get('issue_type', ''))}
[TITLE] {issue.get('title', hakim.get('suggested_title', ''))}
[CONTEXT] Section: {issue.get('section', '')} | Page: {issue.get('page', '')} | Account: {issue.get('account_type', '')}
[CURRENT BEHAVIOR] {issue.get('current_behavior', '')}
[EXPECTED BEHAVIOR] {issue.get('expected_behavior', '')}
[REPRODUCTION STEPS] {issue.get('steps_to_reproduce', 'N/A')}
[REPRODUCIBILITY] {issue.get('reproducibility', 'N/A')}
[IMPACT] {hakim.get('impact_assessment', 'N/A')}
[PRIORITY] {PRIORITY_LABELS.get(issue.get('priority', ''), issue.get('priority', ''))} — {hakim.get('priority_reasoning', '')}
[TECHNICAL NOTES] {hakim.get('technical_notes', 'N/A')}
[HAKIM NOTES] Team: {hakim.get('suggested_team', 'N/A')} | {hakim.get('team_reasoning', '')}
[ERROR] {issue.get('error_message', 'N/A')}
[URL] {issue.get('url', 'N/A')}
[DEVICE] {issue.get('device', 'N/A')} | Browser: {issue.get('browser', 'N/A')}"""


async def _next_issue_number() -> int:
    last = await db.product_issues.find_one(
        {}, {"issue_number": 1}, sort=[("issue_number", -1)]
    )
    return (last.get("issue_number", 0) if last else 0) + 1


async def _get_issue_or_404(issue_id: str) -> dict:
    issue = await db.product_issues.find_one({"id": issue_id}, {"_id": 0})
    if not issue:
        _hub_error(404, "ISSUE_NOT_FOUND", "المشكلة غير موجودة", {"issue_id": issue_id})
    return issue


@router.get("/config")
async def get_hub_config(current_user: dict = Depends(get_current_user)):
    admin = is_platform_admin(current_user)
    main_admin = is_main_admin(current_user)
    super_admin = is_super_admin(current_user)
    return {
        "issue_types": [{"value": k, "label": v} for k, v in ISSUE_TYPE_LABELS.items()],
        "statuses": [{"value": k, "label": v} for k, v in STATUS_LABELS.items()],
        "priorities": [{"value": k, "label": v} for k, v in PRIORITY_LABELS.items()],
        "sections": SECTION_OPTIONS,
        "account_types": ACCOUNT_TYPE_OPTIONS,
        "dynamic_fields": DYNAMIC_FIELDS_BY_TYPE,
        "sla_hours": SLA_HOURS,
        "status_progress": STATUS_PROGRESS,
        "valid_transitions": {k: list(v) for k, v in VALID_STATUS_TRANSITIONS.items()},
        "teams": sorted(VALID_TEAMS),
        "is_admin": admin,
        "is_main_admin": main_admin,
        "is_super_admin": super_admin,
        "permissions": {
            "can_assign": main_admin,
            "can_change_status": main_admin,
            "can_view_prompt": admin,
            "can_view_analytics": admin,
            "can_update_priority": main_admin,
            "can_update_title": main_admin,
            "can_approve_closure": super_admin,
        },
    }


@router.post("/issues")
async def create_issue(data: IssueCreate, current_user: dict = Depends(get_current_user)):
    now = datetime.now(timezone.utc)
    user_id = get_user_id(current_user)

    issue = data.to_issue_document(user_id, current_user)
    issue_id = issue["id"]
    issue["issue_number"] = await _next_issue_number()

    hakim_analysis = await _run_hakim_analysis(issue)
    issue["hakim_analysis"] = hakim_analysis
    issue["ai"] = {
        "suggested_title": hakim_analysis.get("suggested_title", ""),
        "duplicate_detected": bool(hakim_analysis.get("duplicate_ids")),
        "duplicate_candidates": [
            {"issue_id": did, "confidence": 0.0}
            for did in hakim_analysis.get("duplicate_ids", [])[:3]
        ],
        "suggested_team": hakim_analysis.get("suggested_team"),
        "generated_prompt": None,
        "priority_reasoning": hakim_analysis.get("priority_reasoning", ""),
        "team_reasoning": hakim_analysis.get("team_reasoning", ""),
        "technical_notes": hakim_analysis.get("technical_notes", ""),
        "impact_assessment": hakim_analysis.get("impact_assessment", ""),
    }

    issue["title"] = hakim_analysis.get("suggested_title", f"مشكلة في {data.page}")
    issue["priority"] = hakim_analysis.get("suggested_priority", "medium")
    issue["ai_suggested_priority"] = hakim_analysis.get("suggested_priority", "medium")
    issue["assigned_team"] = hakim_analysis.get("suggested_team")
    issue["assignment"]["team"] = hakim_analysis.get("suggested_team")

    sla = calculate_sla(issue["priority"], now)
    issue["sla_deadline"] = sla["sla_deadline"]
    issue["sla_status"] = sla["sla_status"]

    issue["generated_prompt"] = await _generate_prompt(issue)
    issue["ai"]["generated_prompt"] = issue["generated_prompt"]

    if hakim_analysis.get("duplicate_ids"):
        for dup_id in hakim_analysis["duplicate_ids"][:3]:
            dup_entry = {
                "id": str(uuid.uuid4()),
                "issue_id": issue_id,
                "duplicate_of": dup_id,
                "confidence": 0.0,
                "detected_by": "hakim",
                "created_at": now.isoformat(),
            }
            await db.issue_duplicates_map.insert_one(dup_entry)
            await audit_duplicate_detected(issue_id, current_user, dup_id)

    issue["system"]["last_status_changed_at"] = now.isoformat()

    await db.product_issues.insert_one({**issue, "_id": issue_id})

    await handle_issue_created(issue_id, issue, current_user)
    await audit_issue_created(issue_id, current_user, issue)

    await handle_hakim_analysis(issue_id, current_user, hakim_analysis, source="auto_on_create")
    await audit_ai_analyzed(issue_id, current_user, hakim_analysis)

    await handle_prompt_generated(issue_id, current_user)
    await audit_prompt_generated(issue_id, current_user)

    logger.info(f"[ProductHub] Issue created: #{issue['issue_number']} ({issue_id[:8]})")
    issue.pop("_id", None)

    redact_issue_for_role(issue, current_user)
    enrich_sla_state(issue)
    return issue


@router.get("/issues")
async def list_issues(
    status: Optional[str] = None,
    issue_type: Optional[str] = None,
    priority: Optional[str] = None,
    section: Optional[str] = None,
    assigned_team: Optional[str] = None,
    created_by: Optional[str] = None,
    search: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    current_user: dict = Depends(get_current_user),
):
    admin = is_platform_admin(current_user)
    user_id = get_user_id(current_user)

    query: dict = {}
    if not admin:
        query["created_by"] = user_id

    if status:
        if "," in status:
            query["status"] = {"$in": status.split(",")}
        else:
            query["status"] = status
    if issue_type:
        mapped_type = ISSUE_TYPE_COMPAT.get(issue_type, issue_type)
        query["issue_type"] = mapped_type
    if priority:
        query["priority"] = priority
    if section:
        query["section"] = section
    if assigned_team:
        query["assigned_team"] = assigned_team
    if created_by and admin:
        query["created_by"] = created_by
    if date_from:
        query.setdefault("created_at", {})["$gte"] = date_from
    if date_to:
        query.setdefault("created_at", {})["$lte"] = date_to + "T23:59:59"
    if search:
        query["$or"] = [
            {"title": {"$regex": search, "$options": "i"}},
            {"current_behavior": {"$regex": search, "$options": "i"}},
            {"employee_name": {"$regex": search, "$options": "i"}},
            {"page": {"$regex": search, "$options": "i"}},
        ]

    total = await db.product_issues.count_documents(query)
    skip = (page - 1) * limit
    issues = await db.product_issues.find(
        query, {"_id": 0}
    ).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)

    for issue in issues:
        enrich_sla_state(issue)
        redact_issue_for_role(issue, current_user)

    return {"issues": issues, "total": total, "page": page, "limit": limit}


@router.get("/issues/{issue_id}")
async def get_issue(issue_id: str, current_user: dict = Depends(get_current_user)):
    admin = is_platform_admin(current_user)

    issue = await _get_issue_or_404(issue_id)

    if not admin:
        enforce_ownership_or_admin(current_user, issue, HubAction.VIEW_OWN_ISSUE)

    activity = await db.issue_activity_log.find(
        {"issue_id": issue_id}, {"_id": 0}
    ).sort("timestamp", -1).to_list(100)

    comments = await db.issue_comments.find(
        {"issue_id": issue_id}, {"_id": 0}
    ).sort("timestamp", 1).to_list(200)

    duplicates = []
    if admin:
        duplicates = await db.issue_duplicates_map.find(
            {"$or": [{"issue_id": issue_id}, {"duplicate_of": issue_id}]}, {"_id": 0}
        ).to_list(20)

    enrich_sla_state(issue)
    await check_sla_warning(issue_id, issue, current_user)

    issue["activity_log"] = activity
    issue["comments"] = comments
    issue["duplicates"] = duplicates
    issue["is_admin"] = admin
    issue["valid_transitions"] = list(VALID_STATUS_TRANSITIONS.get(issue.get("status", "new"), set()))

    main_admin = is_main_admin(current_user)
    super_admin = is_super_admin(current_user)
    permissions = {
        "can_change_status": main_admin,
        "can_assign": main_admin,
        "can_view_prompt": admin,
        "can_update_title": main_admin,
        "can_update_priority": main_admin,
        "can_approve_closure": super_admin,
        "can_comment": admin or check_resource_ownership(current_user, issue),
        "can_submit_feedback": (
            issue.get("status") == "done"
            and (admin or check_resource_ownership(current_user, issue))
        ),
        "is_main_admin": main_admin,
        "is_super_admin": super_admin,
    }
    issue["permissions"] = permissions

    redact_issue_for_role(issue, current_user)
    return issue


@router.patch("/issues/{issue_id}")
async def update_issue(
    issue_id: str,
    data: IssueUpdate,
    current_user: dict = Depends(get_current_user),
):
    enforce_permission(current_user, HubAction.UPDATE_ISSUE)
    issue = await _get_issue_or_404(issue_id)

    changes = {}
    update_fields = [
        "current_behavior", "expected_behavior", "steps_to_reproduce",
        "error_message", "additional_details", "reproducibility",
    ]
    for field in update_fields:
        value = getattr(data, field, None)
        if value is not None:
            changes[field] = value.strip() if isinstance(value, str) else value

    if data.impact is not None:
        changes["impact"] = data.impact
    if data.related_to is not None:
        changes["technical.related_to"] = data.related_to

    if not changes:
        _hub_error(422, "NO_CHANGES", "لم يتم إرسال أي تعديلات")

    now = _now_iso()
    changes["updated_at"] = now
    changes["system.updated_at"] = now

    if "current_behavior" in changes:
        changes["description.current_behavior"] = changes["current_behavior"]
    if "expected_behavior" in changes:
        changes["description.expected_behavior"] = changes["expected_behavior"]
    if "reproducibility" in changes:
        changes["description.reproducible"] = changes["reproducibility"]

    await db.product_issues.update_one({"id": issue_id}, {"$set": changes})
    await handle_issue_updated(issue_id, current_user, changes)
    await audit_issue_updated(issue_id, current_user, changes)

    return {"success": True, "updated_fields": list(changes.keys())}


@router.put("/issues/{issue_id}/status")
async def update_issue_status(
    issue_id: str,
    data: StatusUpdate,
    current_user: dict = Depends(get_current_user),
):
    enforce_permission(current_user, HubAction.CHANGE_STATUS)

    issue = await _get_issue_or_404(issue_id)
    current_status = issue.get("status", "new")
    new_status = data.status

    if new_status in FINAL_STATUSES:
        enforce_permission(current_user, HubAction.SET_FINAL_STATUS)

    if current_status in FINAL_STATUSES and new_status == "under_review":
        enforce_permission(current_user, HubAction.REOPEN_ISSUE)

    if not validate_status_transition(current_status, new_status):
        _hub_error(400, "INVALID_TRANSITION", get_transition_error(current_status, new_status), {
            "current_status": current_status,
            "requested_status": new_status,
            "allowed_transitions": list(VALID_STATUS_TRANSITIONS.get(current_status, set())),
        })

    now = _now_iso()
    update_fields = {
        "status": new_status,
        "updated_at": now,
        "system.updated_at": now,
        "system.last_status_changed_at": now,
    }

    if new_status == "done":
        update_fields["resolved_at"] = now
        update_fields["feedback_requested"] = True

    if new_status == "under_review" and current_status in {"done", "rejected"}:
        update_fields["resolved_at"] = None
        update_fields["feedback_requested"] = False
        update_fields["feedback_response"] = None
        update_fields["sla_warning_emitted"] = False

    result = await db.product_issues.update_one(
        {"id": issue_id, "status": current_status},
        {"$set": update_fields}
    )
    if result.modified_count == 0:
        _hub_error(409, "CONCURRENT_MODIFICATION", "الحالة تغيّرت — يرجى تحديث الصفحة")

    await handle_status_changed(issue_id, current_user, current_status, new_status, data.note or "")
    await audit_status_changed(issue_id, current_user, current_status, new_status, data.note or "")

    logger.info(f"[ProductHub] Issue {issue_id[:8]}: {current_status} → {new_status}")
    return {"success": True, "status": new_status, "previous_status": current_status}


@router.put("/issues/{issue_id}/assign")
async def assign_issue(
    issue_id: str,
    data: AssignIssue,
    current_user: dict = Depends(get_current_user),
):
    enforce_permission(current_user, HubAction.ASSIGN_ISSUE)

    issue = await _get_issue_or_404(issue_id)

    if data.assigned_to:
        assignee = await db.users.find_one({"id": data.assigned_to}, {"_id": 0, "id": 1, "full_name": 1})
        if not assignee:
            _hub_error(422, "ASSIGNEE_NOT_FOUND", "المستخدم المعيّن غير موجود",
                       {"assigned_to": data.assigned_to})

    now = _now_iso()
    await db.product_issues.update_one(
        {"id": issue_id},
        {"$set": {
            "assigned_team": data.assigned_team,
            "assigned_to": data.assigned_to,
            "assigned_at": now,
            "updated_at": now,
            "assignment.team": data.assigned_team.lower() if data.assigned_team else None,
            "assignment.assigned_to": data.assigned_to,
            "system.updated_at": now,
        }}
    )

    await handle_issue_assigned(
        issue_id, current_user, data.assigned_team,
        data.assigned_to, data.note or ""
    )
    await audit_issue_assigned(
        issue_id, current_user, data.assigned_team,
        data.assigned_to, data.note or ""
    )

    return {"success": True, "assigned_team": data.assigned_team}


@router.post("/issues/{issue_id}/comments")
async def add_comment(
    issue_id: str,
    data: IssueComment,
    current_user: dict = Depends(get_current_user),
):
    issue = await _get_issue_or_404(issue_id)
    enforce_ownership_or_admin(current_user, issue, HubAction.ADD_COMMENT)

    user_role = current_user.get("role", "")
    resolved_role = "platform_admin" if user_role == "platform_admin" else "internal_user"

    comment = {
        "id": str(uuid.uuid4()),
        "issue_id": issue_id,
        "comment": data.content,
        "content": data.content,
        "created_by": get_user_id(current_user),
        "user_id": get_user_id(current_user),
        "user_name": current_user.get("full_name", ""),
        "role": resolved_role,
        "user_role": user_role,
        "type": data.comment_type,
        "timestamp": _now_iso(),
    }

    await db.issue_comments.insert_one(comment)
    await handle_comment_added(issue_id, current_user, comment["id"])
    await audit_comment_added(issue_id, current_user, comment["id"], data.comment_type)
    comment.pop("_id", None)
    return comment


@router.get("/issues/{issue_id}/comments")
async def get_comments(
    issue_id: str,
    current_user: dict = Depends(get_current_user),
):
    issue = await _get_issue_or_404(issue_id)
    if not is_platform_admin(current_user):
        enforce_ownership_or_admin(current_user, issue, HubAction.VIEW_COMMENTS)

    comments = await db.issue_comments.find(
        {"issue_id": issue_id}, {"_id": 0}
    ).sort("timestamp", 1).to_list(200)

    return {"comments": comments, "total": len(comments)}


@router.post("/issues/{issue_id}/feedback")
async def submit_feedback(
    issue_id: str,
    data: FeedbackResponse,
    current_user: dict = Depends(get_current_user),
):
    issue = await _get_issue_or_404(issue_id)
    enforce_ownership_or_admin(current_user, issue, HubAction.SUBMIT_FEEDBACK)

    if issue.get("status") != "done":
        _hub_error(400, "INVALID_FEEDBACK_STATE",
                   "لا يمكن إرسال ملاحظات إلا على المشاكل المكتملة",
                   {"current_status": issue.get("status")})

    now = _now_iso()
    new_status = "user_feedback_confirmed" if data.resolved else "under_review"

    update_fields = {
        "status": new_status,
        "feedback_response": {
            "resolved": data.resolved,
            "comment": data.comment,
            "responded_by": get_user_id(current_user),
            "responded_by_name": current_user.get("full_name", ""),
            "responded_at": now,
        },
        "feedback_requested": False,
        "updated_at": now,
        "system.updated_at": now,
        "system.last_status_changed_at": now,
    }

    if not data.resolved:
        update_fields["resolved_at"] = None
        update_fields["sla_warning_emitted"] = False

    result = await db.product_issues.update_one(
        {"id": issue_id, "status": "done"},
        {"$set": update_fields}
    )

    if result.modified_count == 0:
        _hub_error(409, "CONCURRENT_MODIFICATION",
                   "تم تعديل حالة المشكلة بواسطة مستخدم آخر — يرجى إعادة تحميل الصفحة",
                   {"expected_status": "done"})

    await handle_feedback_response(issue_id, current_user, data.resolved, data.comment or "")
    await audit_feedback_confirmed(issue_id, current_user, data.resolved, data.comment or "")

    return {"success": True, "new_status": new_status}


@router.get("/issues/{issue_id}/prompt")
async def get_issue_prompt(
    issue_id: str,
    current_user: dict = Depends(get_current_user),
):
    enforce_permission(current_user, HubAction.VIEW_PROMPT)

    issue = await _get_issue_or_404(issue_id)
    prompt = issue.get("generated_prompt") or await _generate_prompt(issue)

    return {"success": True, "prompt": prompt, "issue_id": issue_id}


@router.post("/issues/{issue_id}/generate-prompt")
async def regenerate_prompt(
    issue_id: str,
    current_user: dict = Depends(get_current_user),
):
    enforce_permission(current_user, HubAction.GENERATE_PROMPT)

    issue = await _get_issue_or_404(issue_id)
    prompt = await _generate_prompt(issue)

    now = _now_iso()
    await db.product_issues.update_one(
        {"id": issue_id},
        {"$set": {
            "generated_prompt": prompt,
            "ai.generated_prompt": prompt,
            "updated_at": now,
            "system.updated_at": now,
        }}
    )
    await handle_prompt_generated(issue_id, current_user)
    await audit_prompt_generated(issue_id, current_user)

    return {"success": True, "prompt": prompt, "issue_id": issue_id}


@router.get("/issues/{issue_id}/hakim-insights")
async def get_hakim_insights(
    issue_id: str,
    current_user: dict = Depends(get_current_user),
):
    enforce_permission(current_user, HubAction.VIEW_HAKIM_INSIGHTS)

    issue = await _get_issue_or_404(issue_id)

    return {
        "success": True,
        "issue_id": issue_id,
        "hakim_analysis": issue.get("hakim_analysis", {}),
        "suggested_title": issue.get("hakim_analysis", {}).get("suggested_title", ""),
        "suggested_priority": issue.get("hakim_analysis", {}).get("suggested_priority", ""),
        "suggested_team": issue.get("hakim_analysis", {}).get("suggested_team", ""),
        "priority_reasoning": issue.get("hakim_analysis", {}).get("priority_reasoning", ""),
        "team_reasoning": issue.get("hakim_analysis", {}).get("team_reasoning", ""),
        "technical_notes": issue.get("hakim_analysis", {}).get("technical_notes", ""),
        "impact_assessment": issue.get("hakim_analysis", {}).get("impact_assessment", ""),
        "duplicate_ids": issue.get("hakim_analysis", {}).get("duplicate_ids", []),
        "duplicate_note": issue.get("hakim_analysis", {}).get("duplicate_note", ""),
    }


@router.get("/issues/{issue_id}/activity-log")
async def get_activity_log(
    issue_id: str,
    current_user: dict = Depends(get_current_user),
):
    issue = await _get_issue_or_404(issue_id)
    if not is_platform_admin(current_user):
        enforce_ownership_or_admin(current_user, issue, HubAction.VIEW_ACTIVITY_LOG)

    timeline = await get_full_timeline(issue_id)

    return {
        "activity_log": timeline["timeline"],
        "total": timeline["total"],
        "issue_id": issue_id,
        "actors": timeline["actors"],
        "actions_summary": timeline["actions_summary"],
    }


@router.get("/issues/{issue_id}/duplicates")
async def get_duplicates(
    issue_id: str,
    current_user: dict = Depends(get_current_user),
):
    enforce_permission(current_user, HubAction.VIEW_DUPLICATES)

    await _get_issue_or_404(issue_id)

    duplicates = await db.issue_duplicates_map.find(
        {"$or": [{"issue_id": issue_id}, {"duplicate_of": issue_id}]}, {"_id": 0}
    ).to_list(50)

    return {"duplicates": duplicates, "total": len(duplicates), "issue_id": issue_id}


@router.get("/dashboard")
async def get_dashboard(current_user: dict = Depends(get_current_user)):
    enforce_permission(current_user, HubAction.VIEW_FULL_ANALYTICS)

    now = datetime.now(timezone.utc)
    week_ago = (now - timedelta(days=7)).isoformat()

    pipeline_status = [
        {"$group": {"_id": "$status", "count": {"$sum": 1}}}
    ]
    status_counts_raw = await db.product_issues.aggregate(pipeline_status).to_list(20)
    status_counts = {s["_id"]: s["count"] for s in status_counts_raw}

    total = sum(status_counts.values())
    total_open = sum(status_counts.get(s, 0) for s in OPEN_STATUSES)

    pipeline_type = [{"$group": {"_id": "$issue_type", "count": {"$sum": 1}}}]
    type_counts_raw = await db.product_issues.aggregate(pipeline_type).to_list(20)
    by_type = [{"type": t["_id"], "label": ISSUE_TYPE_LABELS.get(t["_id"], t["_id"]), "count": t["count"]} for t in type_counts_raw]

    pipeline_priority = [{"$group": {"_id": "$priority", "count": {"$sum": 1}}}]
    priority_counts_raw = await db.product_issues.aggregate(pipeline_priority).to_list(10)
    by_priority = [{"priority": p["_id"], "label": PRIORITY_LABELS.get(p["_id"], p["_id"] or ""), "count": p["count"]} for p in priority_counts_raw]

    pipeline_team = [
        {"$match": {"assigned_team": {"$ne": None}}},
        {"$group": {"_id": "$assigned_team", "count": {"$sum": 1}}}
    ]
    team_counts_raw = await db.product_issues.aggregate(pipeline_team).to_list(10)
    by_team = [{"team": t["_id"], "count": t["count"]} for t in team_counts_raw]

    new_this_week = await db.product_issues.count_documents({"created_at": {"$gte": week_ago}})
    critical_open = await db.product_issues.count_documents(
        {"priority": "critical", "status": {"$in": list(OPEN_STATUSES)}}
    )
    sla_exceeded = await db.product_issues.count_documents({
        "sla_deadline": {"$lte": now.isoformat()},
        "status": {"$in": list(OPEN_STATUSES)},
    })

    resolved = await db.product_issues.find(
        {"resolved_at": {"$ne": None}},
        {"created_at": 1, "resolved_at": 1, "_id": 0}
    ).to_list(500)
    avg_resolution = 0
    if resolved:
        total_hours = 0
        count = 0
        for r in resolved:
            try:
                created = datetime.fromisoformat(r["created_at"].replace("Z", "+00:00"))
                res = datetime.fromisoformat(r["resolved_at"].replace("Z", "+00:00"))
                total_hours += (res - created).total_seconds() / 3600
                count += 1
            except (ValueError, TypeError, KeyError):
                pass
        if count:
            avg_resolution = round(total_hours / count, 1)

    pipeline_section = [
        {"$group": {"_id": "$section", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 10}
    ]
    top_sections = await db.product_issues.aggregate(pipeline_section).to_list(10)

    dup_count = await db.issue_duplicates_map.count_documents({})

    pipeline_contributors = [
        {"$group": {"_id": {"name": "$employee_name", "user_id": "$created_by"}, "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 10}
    ]
    contributors_raw = await db.product_issues.aggregate(pipeline_contributors).to_list(10)
    top_contributors = [{"name": c["_id"]["name"], "count": c["count"]} for c in contributors_raw]

    pipeline_accuracy = [
        {"$match": {"status": {"$in": ["done", "user_feedback_confirmed", "rejected"]}}},
        {"$group": {
            "_id": "$employee_name",
            "total": {"$sum": 1},
            "valid": {"$sum": {"$cond": [{"$ne": ["$status", "rejected"]}, 1, 0]}},
        }},
        {"$project": {
            "name": "$_id",
            "total": 1,
            "valid": 1,
            "accuracy": {"$multiply": [{"$divide": ["$valid", "$total"]}, 100]},
        }},
        {"$sort": {"accuracy": -1}},
        {"$limit": 10}
    ]
    accuracy_raw = await db.product_issues.aggregate(pipeline_accuracy).to_list(10)
    most_accurate = [
        {"name": a["name"], "total": a["total"], "valid": a["valid"],
         "accuracy": round(a.get("accuracy", 0), 1)}
        for a in accuracy_raw if a.get("total", 0) >= 2
    ]

    pipeline_dept = [
        {"$group": {"_id": "$account_type", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 10}
    ]
    dept_raw = await db.product_issues.aggregate(pipeline_dept).to_list(10)
    by_department = [{"department": d["_id"], "count": d["count"]} for d in dept_raw]

    hakim_analyzed = await db.product_issues.count_documents({"hakim_analysis": {"$exists": True, "$ne": {}}})
    hakim_priority_changed = await db.product_issues.count_documents({
        "hakim_analysis.suggested_priority": {"$exists": True},
        "$expr": {"$ne": ["$priority", "$hakim_analysis.suggested_priority"]}
    })
    pipeline_hakim_teams = [
        {"$match": {"hakim_analysis.suggested_team": {"$exists": True, "$ne": None}}},
        {"$group": {"_id": "$hakim_analysis.suggested_team", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 5}
    ]
    hakim_teams_raw = await db.product_issues.aggregate(pipeline_hakim_teams).to_list(5)
    hakim_top_teams = [{"team": t["_id"], "count": t["count"]} for t in hakim_teams_raw]

    recent_hakim = await db.product_issues.find(
        {"hakim_analysis.impact_assessment": {"$exists": True, "$ne": ""}},
        {"_id": 0, "id": 1, "title": 1, "issue_number": 1, "priority": 1,
         "hakim_analysis.impact_assessment": 1, "hakim_analysis.suggested_priority": 1,
         "hakim_analysis.suggested_team": 1, "hakim_analysis.priority_reasoning": 1}
    ).sort("created_at", -1).limit(5).to_list(5)
    hakim_recent_insights = []
    for ri in recent_hakim:
        ha = ri.get("hakim_analysis", {})
        hakim_recent_insights.append({
            "id": ri.get("id"),
            "title": ri.get("title"),
            "issue_number": ri.get("issue_number"),
            "priority": ri.get("priority"),
            "impact": ha.get("impact_assessment", ""),
            "suggested_team": ha.get("suggested_team", ""),
            "priority_reasoning": ha.get("priority_reasoning", ""),
        })

    return {
        "total_issues": total,
        "total_open": total_open,
        "critical_open": critical_open,
        "new_this_week": new_this_week,
        "in_progress": status_counts.get("in_progress", 0),
        "avg_resolution_hours": avg_resolution,
        "sla_exceeded": sla_exceeded,
        "duplicates_detected": dup_count,
        "by_status": status_counts,
        "by_type": by_type,
        "by_priority": by_priority,
        "by_team": by_team,
        "top_sections": [{"section": s["_id"], "count": s["count"]} for s in top_sections],
        "top_contributors": top_contributors,
        "most_accurate_reporters": most_accurate,
        "by_department": by_department,
        "hakim_stats": {
            "total_analyzed": hakim_analyzed,
            "duplicates_detected": dup_count,
            "priority_overridden": hakim_priority_changed,
            "top_teams": hakim_top_teams,
            "recent_insights": hakim_recent_insights,
        },
        "is_admin": True,
    }


@router.put("/issues/{issue_id}/title")
async def update_issue_title(
    issue_id: str,
    data: dict,
    current_user: dict = Depends(get_current_user),
):
    enforce_permission(current_user, HubAction.UPDATE_TITLE)

    issue = await _get_issue_or_404(issue_id)

    title = data.get("title", "").strip()
    if not title:
        _hub_error(422, "TITLE_REQUIRED", "العنوان مطلوب")
    if len(title) > 500:
        _hub_error(422, "TITLE_TOO_LONG", "العنوان طويل جداً")

    old_title = issue.get("title", "")
    now = _now_iso()
    await db.product_issues.update_one(
        {"id": issue_id},
        {"$set": {"title": title, "updated_at": now, "system.updated_at": now}}
    )
    changes = {"title": {"from": old_title, "to": title}}
    await handle_issue_updated(issue_id, current_user, changes)
    await audit_issue_updated(issue_id, current_user, changes)

    return {"success": True}


@router.put("/issues/{issue_id}/priority")
async def update_issue_priority(
    issue_id: str,
    data: dict,
    current_user: dict = Depends(get_current_user),
):
    enforce_permission(current_user, HubAction.UPDATE_PRIORITY)

    issue = await _get_issue_or_404(issue_id)

    priority = data.get("priority", "")
    if priority not in PRIORITY_LABELS:
        _hub_error(422, "INVALID_PRIORITY", "أولوية غير صالحة",
                   {"valid_values": list(PRIORITY_LABELS.keys())})

    old_priority = issue.get("priority", "")
    now = _now_iso()
    update_fields = {
        "priority": priority,
        "updated_at": now,
        "system.updated_at": now,
    }

    sla = calculate_sla(priority, datetime.now(timezone.utc))
    if sla["sla_deadline"]:
        update_fields["sla_deadline"] = sla["sla_deadline"]
        update_fields["sla_status"] = sla["sla_status"]
        update_fields["sla_warning_emitted"] = False

    await db.product_issues.update_one({"id": issue_id}, {"$set": update_fields})
    changes = {"priority": {"from": old_priority, "to": priority}}
    await handle_issue_updated(issue_id, current_user, changes)
    await audit_issue_updated(issue_id, current_user, changes)

    return {"success": True}


@router.post("/hakim-improve-text")
async def hakim_improve_text(
    data: dict = Body(...),
    current_user: dict = Depends(get_current_user),
):
    text = (data.get("text") or "").strip()
    field_type = data.get("field_type", "general")
    if not text or len(text) < 5:
        _hub_error(422, "TEXT_TOO_SHORT", "النص قصير جداً للتحسين")

    try:
        from openai import OpenAI
        import os
        api_key = os.environ.get("AI_INTEGRATIONS_OPENAI_API_KEY", "")
        base_url = os.environ.get("AI_INTEGRATIONS_OPENAI_BASE_URL", "")
        if not api_key:
            return {"improved_text": text, "suggestions": []}

        client = OpenAI(api_key=api_key, base_url=base_url if base_url else None)

        field_prompts = {
            "current_behavior": "تحسين وصف الوضع الحالي/المشكلة ليكون أوضح وأكثر تحديداً تقنياً",
            "expected_behavior": "تحسين وصف الوضع المتوقع/الحل المطلوب ليكون أوضح وقابلاً للتنفيذ",
            "additional_info": "تحسين المعلومات الإضافية لتكون أكثر فائدة للفريق التقني",
        }
        field_instruction = field_prompts.get(field_type, "تحسين النص ليكون أوضح وأكثر تحديداً")

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": f"""أنت حكيم، مساعد ذكاء المنتج في نظام نسّق. مهمتك: {field_instruction}.

قواعد:
- حافظ على المعنى الأصلي
- اجعل النص أوضح وأكثر تنظيماً
- أضف تفاصيل تقنية إن أمكن
- اكتب بالعربية
- لا تضف معلومات من عندك
- أرجع النص المحسّن فقط بدون مقدمات"""},
                {"role": "user", "content": text}
            ],
            max_tokens=500,
            temperature=0.3,
        )

        improved = response.choices[0].message.content.strip()
        return {"improved_text": improved, "original_text": text}
    except Exception as e:
        logger.warning(f"[Hakim] Text improvement failed: {e}")
        return {"improved_text": text, "original_text": text}
