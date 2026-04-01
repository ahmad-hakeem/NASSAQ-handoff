"""
Product Intelligence Hub — مركز ذكاء المنتج
Internal governance, issue tracking, and AI-assisted analysis system.

Collections:
- product_issues: Main issue storage
- issue_activity_log: Activity timeline
- issue_comments: Internal discussion threads
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone, timedelta
from enum import Enum
import uuid
import logging
import json

from dependencies import db, get_current_user, require_roles, UserRole

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

STATUS_LABELS = {
    "new": "جديد",
    "under_review": "تحت المراجعة",
    "in_progress": "قيد التنفيذ",
    "qa_validation": "تحقق الجودة",
    "done": "مكتمل",
    "rejected": "مرفوض",
    "user_feedback_confirmed": "أكده المستخدم",
}

PRIORITY_LABELS = {
    "critical": "حرج",
    "high": "عالي",
    "medium": "متوسط",
    "low": "منخفض",
}

SLA_HOURS = {
    "critical": 24,
    "high": 72,
    "medium": 120,
    "low": None,
}

STATUS_PROGRESS = {
    "new": 10,
    "under_review": 25,
    "in_progress": 55,
    "qa_validation": 80,
    "done": 100,
    "rejected": 100,
    "user_feedback_confirmed": 100,
}

FINAL_STATUSES = {"done", "rejected", "user_feedback_confirmed"}

PLATFORM_ADMIN_EMAILS = {"zalat@nassaqapp.com", "hakim@nassaqapp.com"}

VALID_STATUS_TRANSITIONS = {
    "new": {"under_review", "in_progress", "rejected"},
    "under_review": {"in_progress", "rejected", "done"},
    "in_progress": {"qa_validation", "under_review", "done"},
    "qa_validation": {"done", "in_progress"},
    "done": {"user_feedback_confirmed", "under_review"},
    "rejected": {"under_review"},
    "user_feedback_confirmed": set(),
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

ADMIN_ONLY_FIELDS = {"generated_prompt"}
ADMIN_ONLY_HAKIM_FIELDS = set()


def _redact_for_non_admin(issue: dict) -> dict:
    for f in ADMIN_ONLY_FIELDS:
        issue.pop(f, None)
    return issue


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


class IssueComment(BaseModel):
    content: str


class StatusUpdate(BaseModel):
    status: str
    note: Optional[str] = None


class AssignIssue(BaseModel):
    assigned_team: str
    assigned_to: Optional[str] = None
    note: Optional[str] = None


class FeedbackResponse(BaseModel):
    resolved: bool
    comment: Optional[str] = None


def _is_platform_admin(user: dict) -> bool:
    return user.get("role") == "platform_admin"


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


async def _log_activity(issue_id: str, action: str, user: dict, details: dict = None):
    entry = {
        "id": str(uuid.uuid4()),
        "issue_id": issue_id,
        "action": action,
        "action_by": user.get("id", user.get("user_id", "")),
        "action_by_name": user.get("full_name", ""),
        "action_by_role": user.get("role", ""),
        "details": details or {},
        "timestamp": _now_iso(),
    }
    await db.issue_activity_log.insert_one(entry)


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
            messages=[{"role": "system", "content": "You are a product intelligence AI. Respond ONLY with valid JSON."}, {"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=600,
        )

        text = response.choices[0].message.content.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        analysis = json.loads(text)

        analysis.setdefault("suggested_title", "")
        analysis.setdefault("suggested_priority", "medium")
        analysis.setdefault("suggested_team", "Backend")
        analysis.setdefault("duplicate_ids", [])
        analysis.setdefault("duplicate_note", "")
        analysis.setdefault("technical_notes", "")
        analysis.setdefault("impact_assessment", "")
        analysis.setdefault("priority_reasoning", "")
        analysis.setdefault("team_reasoning", "")
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


@router.get("/config")
async def get_hub_config(current_user: dict = Depends(get_current_user)):
    return {
        "issue_types": [{"value": k, "label": v} for k, v in ISSUE_TYPE_LABELS.items()],
        "statuses": [{"value": k, "label": v} for k, v in STATUS_LABELS.items()],
        "priorities": [{"value": k, "label": v} for k, v in PRIORITY_LABELS.items()],
        "sections": SECTION_OPTIONS,
        "account_types": ACCOUNT_TYPE_OPTIONS,
        "dynamic_fields": DYNAMIC_FIELDS_BY_TYPE,
        "sla_hours": SLA_HOURS,
        "status_progress": STATUS_PROGRESS,
        "teams": ["Frontend", "Backend", "DevOps", "Design", "QA", "Product"],
        "is_admin": _is_platform_admin(current_user),
    }


@router.post("/issues")
async def create_issue(data: IssueCreate, current_user: dict = Depends(get_current_user)):
    if not data.employee_name or not data.employee_name.strip():
        raise HTTPException(status_code=422, detail="اسم الموظف مطلوب")
    if data.issue_type not in VALID_ISSUE_TYPES:
        raise HTTPException(status_code=422, detail=f"نوع المشكلة غير صالح: {data.issue_type}")
    if data.account_type not in VALID_ACCOUNT_TYPES:
        raise HTTPException(status_code=422, detail=f"نوع الحساب غير صالح: {data.account_type}")

    now = datetime.now(timezone.utc)
    issue_id = str(uuid.uuid4())

    issue = {
        "id": issue_id,
        "issue_number": await _next_issue_number(),
        "issue_type": data.issue_type,
        "status": "new",
        "priority": None,
        "title": None,
        "employee_name": data.employee_name.strip(),
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
            "employee_name": data.employee_name.strip(),
            "employee_id": data.employee_id,
            "user_id": current_user.get("id", current_user.get("user_id", "")),
            "created_at": now.isoformat(),
            "created_date": now.strftime("%Y-%m-%d"),
            "created_time": now.strftime("%H:%M:%S"),
        },
        "sla_deadline": None,
        "sla_status": None,
        "feedback_requested": False,
        "feedback_response": None,
        "created_by": current_user.get("id", current_user.get("user_id", "")),
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

    sla_h = SLA_HOURS.get(issue["priority"])
    if sla_h:
        issue["sla_deadline"] = (now + timedelta(hours=sla_h)).isoformat()
        issue["sla_status"] = "within"

    issue["generated_prompt"] = await _generate_prompt(issue)

    if hakim_analysis.get("duplicate_ids"):
        for dup_id in hakim_analysis["duplicate_ids"][:3]:
            await db.issue_duplicates_map.insert_one({
                "id": str(uuid.uuid4()),
                "issue_id": issue_id,
                "duplicate_of": dup_id,
                "detected_by": "hakim_ai",
                "timestamp": now.isoformat(),
            })

    await db.product_issues.insert_one({**issue, "_id": issue_id})
    await _log_activity(issue_id, "issue_created", current_user, {
        "issue_type": data.issue_type,
        "priority": issue["priority"],
    })

    logger.info(f"[ProductHub] Issue created: #{issue['issue_number']} ({issue_id[:8]})")
    issue.pop("_id", None)
    return issue


async def _next_issue_number() -> int:
    last = await db.product_issues.find_one(
        {}, {"issue_number": 1}, sort=[("issue_number", -1)]
    )
    return (last.get("issue_number", 0) if last else 0) + 1


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
    is_admin = _is_platform_admin(current_user)
    user_id = current_user.get("id", current_user.get("user_id", ""))

    query: dict = {}
    if not is_admin:
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
    if created_by:
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
    issues = await db.product_issues.find(query, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)

    now = datetime.now(timezone.utc)
    for issue in issues:
        if issue.get("sla_deadline") and issue.get("status") not in FINAL_STATUSES:
            deadline = datetime.fromisoformat(issue["sla_deadline"].replace("Z", "+00:00"))
            issue["sla_remaining_hours"] = max(0, (deadline - now).total_seconds() / 3600)
            issue["sla_status"] = "within" if deadline > now else "exceeded"

    if not is_admin:
        issues = [_redact_for_non_admin(i) for i in issues]

    return {"issues": issues, "total": total, "page": page, "limit": limit}


@router.get("/issues/{issue_id}")
async def get_issue(issue_id: str, current_user: dict = Depends(get_current_user)):
    is_admin = _is_platform_admin(current_user)
    user_id = current_user.get("id", current_user.get("user_id", ""))

    issue = await db.product_issues.find_one({"id": issue_id}, {"_id": 0})
    if not issue:
        raise HTTPException(status_code=404, detail="المشكلة غير موجودة")

    if not is_admin and issue.get("created_by") != user_id:
        raise HTTPException(status_code=403, detail="ليس لديك صلاحية لعرض هذه المشكلة")

    activity = await db.issue_activity_log.find(
        {"issue_id": issue_id}, {"_id": 0}
    ).sort("timestamp", -1).to_list(100)

    comments = await db.issue_comments.find(
        {"issue_id": issue_id}, {"_id": 0}
    ).sort("timestamp", 1).to_list(200)

    duplicates = await db.issue_duplicates_map.find(
        {"$or": [{"issue_id": issue_id}, {"duplicate_of": issue_id}]}, {"_id": 0}
    ).to_list(20)

    now = datetime.now(timezone.utc)
    if issue.get("sla_deadline") and issue.get("status") not in FINAL_STATUSES:
        deadline = datetime.fromisoformat(issue["sla_deadline"].replace("Z", "+00:00"))
        issue["sla_remaining_hours"] = max(0, (deadline - now).total_seconds() / 3600)
        issue["sla_status"] = "within" if deadline > now else "exceeded"

    issue["activity_log"] = activity
    issue["comments"] = comments
    issue["duplicates"] = duplicates
    issue["is_admin"] = is_admin

    if not is_admin:
        _redact_for_non_admin(issue)

    return issue


@router.put("/issues/{issue_id}/status")
async def update_issue_status(
    issue_id: str,
    data: StatusUpdate,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN])),
):
    issue = await db.product_issues.find_one({"id": issue_id}, {"_id": 0})
    if not issue:
        raise HTTPException(status_code=404, detail="المشكلة غير موجودة")

    new_status = data.status
    current_status = issue.get("status", "new")

    allowed = VALID_STATUS_TRANSITIONS.get(current_status, set())
    if new_status not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"لا يمكن الانتقال من '{STATUS_LABELS.get(current_status, current_status)}' إلى '{STATUS_LABELS.get(new_status, new_status)}'"
        )

    update_fields = {
        "status": new_status,
        "updated_at": _now_iso(),
    }

    if new_status == "done":
        update_fields["resolved_at"] = _now_iso()
        update_fields["feedback_requested"] = True

    result = await db.product_issues.update_one(
        {"id": issue_id, "status": current_status},
        {"$set": update_fields}
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=409, detail="الحالة تغيّرت — يرجى تحديث الصفحة")

    await _log_activity(issue_id, "status_changed", current_user, {
        "from": current_status,
        "to": new_status,
        "note": data.note or "",
    })

    logger.info(f"[ProductHub] Issue {issue_id[:8]}: {current_status} → {new_status}")
    return {"success": True, "status": new_status}


@router.put("/issues/{issue_id}/assign")
async def assign_issue(
    issue_id: str,
    data: AssignIssue,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN])),
):
    issue = await db.product_issues.find_one({"id": issue_id}, {"_id": 0})
    if not issue:
        raise HTTPException(status_code=404, detail="المشكلة غير موجودة")

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

    await _log_activity(issue_id, "issue_assigned", current_user, {
        "team": data.assigned_team,
        "assigned_to": data.assigned_to,
        "note": data.note or "",
    })

    return {"success": True, "assigned_team": data.assigned_team}


@router.post("/issues/{issue_id}/comments")
async def add_comment(
    issue_id: str,
    data: IssueComment,
    current_user: dict = Depends(get_current_user),
):
    issue = await db.product_issues.find_one({"id": issue_id}, {"_id": 0})
    if not issue:
        raise HTTPException(status_code=404, detail="المشكلة غير موجودة")

    user_id = current_user.get("id", current_user.get("user_id", ""))
    if not _is_platform_admin(current_user) and issue.get("created_by") != user_id:
        raise HTTPException(status_code=403, detail="ليس لديك صلاحية للتعليق على هذه المشكلة")

    comment = {
        "id": str(uuid.uuid4()),
        "issue_id": issue_id,
        "content": data.content,
        "user_id": current_user.get("id", current_user.get("user_id", "")),
        "user_name": current_user.get("full_name", ""),
        "user_role": current_user.get("role", ""),
        "timestamp": _now_iso(),
    }

    await db.issue_comments.insert_one(comment)
    await _log_activity(issue_id, "comment_added", current_user)
    comment.pop("_id", None)
    return comment


@router.post("/issues/{issue_id}/feedback")
async def submit_feedback(
    issue_id: str,
    data: FeedbackResponse,
    current_user: dict = Depends(get_current_user),
):
    issue = await db.product_issues.find_one({"id": issue_id}, {"_id": 0})
    if not issue:
        raise HTTPException(status_code=404, detail="المشكلة غير موجودة")

    user_id = current_user.get("id", current_user.get("user_id", ""))
    if not _is_platform_admin(current_user) and issue.get("created_by") != user_id:
        raise HTTPException(status_code=403, detail="فقط صاحب البلاغ يمكنه إرسال ملاحظات")

    if issue.get("status") != "done":
        raise HTTPException(status_code=400, detail="لا يمكن إرسال ملاحظات إلا على المشاكل المكتملة")

    now = _now_iso()
    if data.resolved:
        new_status = "user_feedback_confirmed"
    else:
        new_status = "under_review"

    await db.product_issues.update_one(
        {"id": issue_id},
        {"$set": {
            "status": new_status,
            "feedback_response": {
                "resolved": data.resolved,
                "comment": data.comment,
                "responded_by": current_user.get("id", ""),
                "responded_at": now,
            },
            "feedback_requested": False,
            "updated_at": now,
        }}
    )

    await _log_activity(issue_id, "feedback_submitted", current_user, {
        "resolved": data.resolved,
        "comment": data.comment,
        "new_status": new_status,
    })

    return {"success": True, "new_status": new_status}


@router.get("/issues/{issue_id}/prompt")
async def get_issue_prompt(
    issue_id: str,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN])),
):
    issue = await db.product_issues.find_one({"id": issue_id}, {"_id": 0})
    if not issue:
        raise HTTPException(status_code=404, detail="المشكلة غير موجودة")

    prompt = issue.get("generated_prompt") or await _generate_prompt(issue)
    return {"prompt": prompt, "issue_id": issue_id}


@router.get("/dashboard")
async def get_dashboard(current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))):
    now = datetime.now(timezone.utc)
    week_ago = (now - timedelta(days=7)).isoformat()

    pipeline_status = [
        {"$group": {"_id": "$status", "count": {"$sum": 1}}}
    ]
    status_counts_raw = await db.product_issues.aggregate(pipeline_status).to_list(20)
    status_counts = {s["_id"]: s["count"] for s in status_counts_raw}

    total = sum(status_counts.values())
    open_statuses = {"new", "under_review", "in_progress", "qa_validation"}
    total_open = sum(status_counts.get(s, 0) for s in open_statuses)

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
    critical_open = await db.product_issues.count_documents({"priority": "critical", "status": {"$in": list(open_statuses)}})
    sla_exceeded = await db.product_issues.count_documents({
        "sla_deadline": {"$lte": now.isoformat()},
        "status": {"$in": list(open_statuses)},
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
            except:
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
    most_accurate = [{"name": a["name"], "total": a["total"], "valid": a["valid"], "accuracy": round(a.get("accuracy", 0), 1)} for a in accuracy_raw if a.get("total", 0) >= 2]

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
        "is_admin": _is_platform_admin(current_user),
    }


@router.put("/issues/{issue_id}/title")
async def update_issue_title(
    issue_id: str,
    data: dict,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN])),
):
    issue = await db.product_issues.find_one({"id": issue_id})
    if not issue:
        raise HTTPException(status_code=404, detail="المشكلة غير موجودة")
    
    title = data.get("title", "").strip()
    if not title:
        raise HTTPException(status_code=422, detail="العنوان مطلوب")
    
    await db.product_issues.update_one(
        {"id": issue_id},
        {"$set": {"title": title, "updated_at": _now_iso()}}
    )
    await _log_activity(issue_id, "title_updated", current_user, {"title": title})
    return {"success": True}


@router.put("/issues/{issue_id}/priority")
async def update_issue_priority(
    issue_id: str,
    data: dict,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN])),
):
    issue = await db.product_issues.find_one({"id": issue_id})
    if not issue:
        raise HTTPException(status_code=404, detail="المشكلة غير موجودة")
    
    priority = data.get("priority", "")
    if priority not in PRIORITY_LABELS:
        raise HTTPException(status_code=422, detail="أولوية غير صالحة")
    
    update_fields = {"priority": priority, "updated_at": _now_iso()}
    sla_h = SLA_HOURS.get(priority)
    if sla_h:
        update_fields["sla_deadline"] = (datetime.now(timezone.utc) + timedelta(hours=sla_h)).isoformat()
        update_fields["sla_status"] = "within"
    
    await db.product_issues.update_one({"id": issue_id}, {"$set": update_fields})
    await _log_activity(issue_id, "priority_changed", current_user, {"priority": priority})
    return {"success": True}
