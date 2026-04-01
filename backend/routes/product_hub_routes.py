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
- issue_activity_log: Activity timeline + event log
- issue_comments: Discussion threads
- issue_duplicates_map: Duplicate detection results
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone, timedelta
from enum import Enum
import uuid
import logging
import json

from dependencies import db, get_current_user, require_roles, UserRole
from engines.product_hub_rbac import (
    HubAction, HubRole, is_platform_admin, check_permission,
    enforce_permission, enforce_ownership_or_admin,
    check_resource_ownership, redact_issue_for_role,
    require_hub_action, get_user_id, resolve_hub_role,
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

logger = logging.getLogger("nassaq.product_hub")

router = APIRouter(prefix="/product-hub", tags=["Product Intelligence Hub"])


class IssueType(str, Enum):
    BUG = "bug"
    ERROR = "error"
    UI_ISSUE = "ui_issue"
    UX_ISSUE = "ux_issue"
    PERFORMANCE = "performance"
    CONTENT = "content"
    FEATURE_REQUEST = "feature_request"
    IMPROVEMENT = "improvement"
    PERMISSION = "permission"
    WORKFLOW = "workflow"
    INTEGRATION = "integration"
    OTHER = "other"


class IssuePriority(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class IssueStatus(str, Enum):
    NEW = "new"
    UNDER_REVIEW = "under_review"
    IN_PROGRESS = "in_progress"
    QA_VALIDATION = "qa_validation"
    DONE = "done"
    REJECTED = "rejected"
    USER_FEEDBACK_CONFIRMED = "user_feedback_confirmed"


ISSUE_TYPE_LABELS = {
    "bug": "خطأ برمجي",
    "error": "خطأ تقني",
    "ui_issue": "مشكلة واجهة",
    "ux_issue": "مشكلة تجربة مستخدم",
    "performance": "مشكلة أداء",
    "content": "مشكلة محتوى",
    "feature_request": "طلب ميزة",
    "improvement": "اقتراح تحسين",
    "permission": "مشكلة صلاحيات",
    "workflow": "مشكلة سير عمل",
    "integration": "مشكلة تكامل",
    "other": "أخرى",
}

DYNAMIC_FIELDS_BY_TYPE = {
    "bug": ["steps_to_reproduce", "reproducibility", "error_message"],
    "error": ["error_message", "error_code", "steps_to_reproduce"],
    "ui_issue": ["screen_area", "affected_elements"],
    "ux_issue": ["user_journey", "pain_point"],
    "performance": ["load_time", "affected_operation"],
    "content": ["content_location", "content_type"],
    "feature_request": ["use_case", "business_value"],
    "improvement": ["improvement_area", "expected_impact"],
    "permission": ["affected_role", "expected_access"],
    "workflow": ["workflow_name", "broken_step"],
    "integration": ["integration_name", "api_endpoint"],
    "other": ["additional_details"],
}

ACCOUNT_TYPE_OPTIONS = [
    "platform_admin", "school_principal", "school_sub_admin",
    "teacher", "student", "parent", "visitor"
]

SECTION_OPTIONS = [
    "لوحة القيادة", "إدارة المدارس", "إدارة المستخدمين",
    "الجداول والمواعيد", "الحضور والغياب", "التقييمات",
    "التقارير", "الإعدادات", "التسجيل", "حكيم الذكي",
    "بوابة الطالب", "بوابة ولي الأمر", "بوابة المعلم",
    "التواصل", "الأمان", "أخرى"
]

VALID_ISSUE_TYPES = set(ISSUE_TYPE_LABELS.keys())
VALID_ACCOUNT_TYPES = set(ACCOUNT_TYPE_OPTIONS)
VALID_SECTIONS = set(SECTION_OPTIONS)
VALID_TEAMS = {"Frontend", "Backend", "DevOps", "Design", "QA", "Product"}


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


class IssueCreate(BaseModel):
    issue_type: str
    employee_name: str
    employee_id: Optional[str] = None
    account_type: str
    section: str
    page: str
    current_behavior: str
    expected_behavior: str
    steps_to_reproduce: Optional[str] = None
    reproducibility: Optional[str] = None
    error_message: Optional[str] = None
    error_code: Optional[str] = None
    screen_area: Optional[str] = None
    affected_elements: Optional[str] = None
    user_journey: Optional[str] = None
    pain_point: Optional[str] = None
    load_time: Optional[str] = None
    affected_operation: Optional[str] = None
    content_location: Optional[str] = None
    content_type: Optional[str] = None
    use_case: Optional[str] = None
    business_value: Optional[str] = None
    improvement_area: Optional[str] = None
    expected_impact: Optional[str] = None
    affected_role: Optional[str] = None
    expected_access: Optional[str] = None
    workflow_name: Optional[str] = None
    broken_step: Optional[str] = None
    integration_name: Optional[str] = None
    api_endpoint: Optional[str] = None
    additional_details: Optional[str] = None
    url: Optional[str] = None
    device: Optional[str] = None
    browser: Optional[str] = None
    attachments: Optional[List[str]] = None

    @field_validator("issue_type")
    @classmethod
    def validate_issue_type(cls, v):
        if v not in VALID_ISSUE_TYPES:
            raise ValueError(f"نوع المشكلة غير صالح: {v}")
        return v

    @field_validator("account_type")
    @classmethod
    def validate_account_type(cls, v):
        if v not in VALID_ACCOUNT_TYPES:
            raise ValueError(f"نوع الحساب غير صالح: {v}")
        return v

    @field_validator("employee_name")
    @classmethod
    def validate_employee_name(cls, v):
        if not v or not v.strip():
            raise ValueError("اسم الموظف مطلوب")
        if len(v.strip()) > 200:
            raise ValueError("اسم الموظف طويل جداً")
        return v.strip()

    @field_validator("current_behavior", "expected_behavior")
    @classmethod
    def validate_behavior_fields(cls, v):
        if not v or not v.strip():
            raise ValueError("هذا الحقل مطلوب")
        if len(v.strip()) > 5000:
            raise ValueError("النص طويل جداً")
        return v.strip()

    @field_validator("page", "section")
    @classmethod
    def validate_required_string(cls, v):
        if not v or not v.strip():
            raise ValueError("هذا الحقل مطلوب")
        return v.strip()


class IssueUpdate(BaseModel):
    current_behavior: Optional[str] = None
    expected_behavior: Optional[str] = None
    steps_to_reproduce: Optional[str] = None
    error_message: Optional[str] = None
    additional_details: Optional[str] = None


class IssueComment(BaseModel):
    content: str

    @field_validator("content")
    @classmethod
    def validate_content(cls, v):
        if not v or not v.strip():
            raise ValueError("محتوى التعليق مطلوب")
        if len(v.strip()) > 5000:
            raise ValueError("التعليق طويل جداً")
        return v.strip()


class StatusUpdate(BaseModel):
    status: str
    note: Optional[str] = None

    @field_validator("status")
    @classmethod
    def validate_status(cls, v):
        valid = set(STATUS_LABELS.keys())
        if v not in valid:
            raise ValueError(f"حالة غير صالحة: {v}")
        return v


class AssignIssue(BaseModel):
    assigned_team: str
    assigned_to: Optional[str] = None
    note: Optional[str] = None

    @field_validator("assigned_team")
    @classmethod
    def validate_team(cls, v):
        if v not in VALID_TEAMS:
            raise ValueError(f"فريق غير صالح: {v}")
        return v


class FeedbackResponse(BaseModel):
    resolved: bool
    comment: Optional[str] = None


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
        "ux_issue": "Design", "performance": "DevOps", "content": "Product",
        "feature_request": "Product", "improvement": "Product",
        "permission": "Backend", "workflow": "Backend",
        "integration": "Backend", "other": "Product",
    }
    type_to_priority = {
        "bug": "high", "error": "high", "performance": "high",
        "permission": "medium", "integration": "medium",
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
        "permissions": {
            "can_assign": admin,
            "can_change_status": admin,
            "can_view_prompt": admin,
            "can_view_analytics": admin,
            "can_update_priority": admin,
            "can_update_title": admin,
        },
    }


@router.post("/issues")
async def create_issue(data: IssueCreate, current_user: dict = Depends(get_current_user)):
    now = datetime.now(timezone.utc)
    issue_id = str(uuid.uuid4())
    user_id = get_user_id(current_user)

    issue = {
        "id": issue_id,
        "issue_number": await _next_issue_number(),
        "issue_type": data.issue_type,
        "status": "new",
        "priority": None,
        "title": None,
        "employee_name": data.employee_name,
        "employee_id": data.employee_id,
        "account_type": data.account_type,
        "section": data.section,
        "page": data.page,
        "current_behavior": data.current_behavior,
        "expected_behavior": data.expected_behavior,
        "steps_to_reproduce": data.steps_to_reproduce,
        "reproducibility": data.reproducibility,
        "error_message": data.error_message,
        "error_code": data.error_code,
        "screen_area": data.screen_area,
        "affected_elements": data.affected_elements,
        "user_journey": data.user_journey,
        "pain_point": data.pain_point,
        "load_time": data.load_time,
        "affected_operation": data.affected_operation,
        "content_location": data.content_location,
        "content_type_field": data.content_type,
        "use_case": data.use_case,
        "business_value": data.business_value,
        "improvement_area": data.improvement_area,
        "expected_impact": data.expected_impact,
        "affected_role": data.affected_role,
        "expected_access": data.expected_access,
        "workflow_name": data.workflow_name,
        "broken_step": data.broken_step,
        "integration_name": data.integration_name,
        "api_endpoint": data.api_endpoint,
        "additional_details": data.additional_details,
        "url": data.url,
        "device": data.device,
        "browser": data.browser,
        "attachments": data.attachments or [],
        "assigned_team": None,
        "assigned_to": None,
        "assigned_to_name": None,
        "assigned_at": None,
        "hakim_analysis": {},
        "generated_prompt": None,
        "duplicate_of": None,
        "submission_metadata": {
            "employee_name": data.employee_name,
            "employee_id": data.employee_id,
            "user_id": user_id,
            "created_at": now.isoformat(),
            "created_date": now.strftime("%Y-%m-%d"),
            "created_time": now.strftime("%H:%M:%S"),
        },
        "sla_deadline": None,
        "sla_status": None,
        "feedback_requested": False,
        "feedback_response": None,
        "created_by": user_id,
        "created_by_name": current_user.get("full_name", ""),
        "created_by_role": current_user.get("role", ""),
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
        "resolved_at": None,
    }

    hakim_analysis = await _run_hakim_analysis(issue)
    issue["hakim_analysis"] = hakim_analysis
    issue["title"] = hakim_analysis.get("suggested_title", f"مشكلة في {data.page}")
    issue["priority"] = hakim_analysis.get("suggested_priority", "medium")
    issue["assigned_team"] = hakim_analysis.get("suggested_team")

    sla = calculate_sla(issue["priority"], now)
    issue["sla_deadline"] = sla["sla_deadline"]
    issue["sla_status"] = sla["sla_status"]

    issue["generated_prompt"] = await _generate_prompt(issue)

    if hakim_analysis.get("duplicate_ids"):
        for dup_id in hakim_analysis["duplicate_ids"][:3]:
            await db.issue_duplicates_map.insert_one({
                "id": str(uuid.uuid4()),
                "issue_id": issue_id,
                "duplicate_of": dup_id,
                "detected_by": "hakim_ai",
                "confidence": "ai_suggested",
                "timestamp": now.isoformat(),
            })

    await db.product_issues.insert_one({**issue, "_id": issue_id})

    await handle_issue_created(issue_id, issue, current_user)
    await handle_hakim_analysis(issue_id, current_user, hakim_analysis, source="auto_on_create")
    await handle_prompt_generated(issue_id, current_user)

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
        query["issue_type"] = issue_type
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

    permissions = {
        "can_change_status": admin,
        "can_assign": admin,
        "can_view_prompt": admin,
        "can_update_title": admin,
        "can_update_priority": admin,
        "can_comment": admin or check_resource_ownership(current_user, issue),
        "can_submit_feedback": (
            issue.get("status") == "done"
            and (admin or check_resource_ownership(current_user, issue))
        ),
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
    for field in ["current_behavior", "expected_behavior", "steps_to_reproduce", "error_message", "additional_details"]:
        value = getattr(data, field, None)
        if value is not None:
            changes[field] = value.strip()

    if not changes:
        _hub_error(422, "NO_CHANGES", "لم يتم إرسال أي تعديلات")

    changes["updated_at"] = _now_iso()
    await db.product_issues.update_one({"id": issue_id}, {"$set": changes})
    await handle_issue_updated(issue_id, current_user, changes)

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

    update_fields = {
        "status": new_status,
        "updated_at": _now_iso(),
    }

    if new_status == "done":
        update_fields["resolved_at"] = _now_iso()
        update_fields["feedback_requested"] = True

    if new_status == "under_review" and current_status in {"done", "rejected"}:
        update_fields["resolved_at"] = None
        update_fields["feedback_requested"] = False
        update_fields["feedback_response"] = None

    result = await db.product_issues.update_one(
        {"id": issue_id, "status": current_status},
        {"$set": update_fields}
    )
    if result.modified_count == 0:
        _hub_error(409, "CONCURRENT_MODIFICATION", "الحالة تغيّرت — يرجى تحديث الصفحة")

    await handle_status_changed(issue_id, current_user, current_status, new_status, data.note or "")

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

    now = _now_iso()
    await db.product_issues.update_one(
        {"id": issue_id},
        {"$set": {
            "assigned_team": data.assigned_team,
            "assigned_to": data.assigned_to,
            "assigned_at": now,
            "updated_at": now,
        }}
    )

    await handle_issue_assigned(
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

    comment = {
        "id": str(uuid.uuid4()),
        "issue_id": issue_id,
        "content": data.content,
        "user_id": get_user_id(current_user),
        "user_name": current_user.get("full_name", ""),
        "user_role": current_user.get("role", ""),
        "timestamp": _now_iso(),
    }

    await db.issue_comments.insert_one(comment)
    await handle_comment_added(issue_id, current_user, comment["id"])
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
    }

    if not data.resolved:
        update_fields["resolved_at"] = None

    result = await db.product_issues.update_one(
        {"id": issue_id, "status": "done"},
        {"$set": update_fields}
    )

    if result.modified_count == 0:
        _hub_error(409, "CONCURRENT_MODIFICATION",
                   "تم تعديل حالة المشكلة بواسطة مستخدم آخر — يرجى إعادة تحميل الصفحة",
                   {"expected_status": "done"})

    await handle_feedback_response(issue_id, current_user, data.resolved, data.comment or "")

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

    await db.product_issues.update_one(
        {"id": issue_id},
        {"$set": {"generated_prompt": prompt, "updated_at": _now_iso()}}
    )
    await handle_prompt_generated(issue_id, current_user)

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

    activity = await db.issue_activity_log.find(
        {"issue_id": issue_id}, {"_id": 0}
    ).sort("timestamp", -1).to_list(200)

    return {"activity_log": activity, "total": len(activity), "issue_id": issue_id}


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
    await db.product_issues.update_one(
        {"id": issue_id},
        {"$set": {"title": title, "updated_at": _now_iso()}}
    )
    await handle_issue_updated(issue_id, current_user, {"title": {"from": old_title, "to": title}})

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
    update_fields = {"priority": priority, "updated_at": _now_iso()}

    sla = calculate_sla(priority, datetime.now(timezone.utc))
    if sla["sla_deadline"]:
        update_fields["sla_deadline"] = sla["sla_deadline"]
        update_fields["sla_status"] = sla["sla_status"]

    await db.product_issues.update_one({"id": issue_id}, {"$set": update_fields})
    await handle_issue_updated(issue_id, current_user, {
        "priority": {"from": old_priority, "to": priority}
    })

    return {"success": True}
