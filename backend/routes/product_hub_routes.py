"""
Product Intelligence Hub — مركز ذكاء المنتج
Internal governance, issue tracking, and AI-assisted analysis system.

API Contracts:
- POST   /issues                    — Create issue (any authenticated user)
- GET    /issues                    — List issues (own for users, all for admin)
- GET    /issues/{id}               — Issue detail (own for users, any for admin)
- PATCH  /issues/{id}               — Update issue fields (platform_admin only).
                                       Requires UPDATE_ISSUE permission.
                                       Writes an IssueVersion row whose revision is
                                       computed atomically (MAX subquery INSERT) and
                                       guaranteed unique by uq_issue_versions_issue_revision.
                                       Returns 404 for both non-existent and unauthorized
                                       callers so the API does not confirm issue existence.
- GET    /issues/{id}/versions      — Paginated edit history ordered by revision desc
                                       (platform_admin only). Returns 404 for both
                                       non-existent issues and unauthorized callers.
                                       Response: {versions, total, skip, limit, issue_id}
                                       Each version carries: id, issue_id, revision,
                                       tenant_id, changed_by_user_id, changed_by_name,
                                       changed_at, changed_fields, previous_values, new_values
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
- POST   /issues/bulk-update        — Bulk status/priority/team update (main_admin only).
                                       Pre-validates all issue_ids exist before any write;
                                       returns 422 with missing_ids if any are absent.
- GET    /dashboard                 — Dashboard analytics (admin only)
- GET    /config                    — Hub configuration (any authenticated)

Collections:
- product_issues: Main issue storage
- issue_activity_log: Activity timeline + event log + audit trail
- issue_comments: Discussion threads
- issue_duplicates_map: Duplicate detection results
- issue_versions: Immutable edit history; (issue_id, revision) unique; tenant_id nullable
"""

from fastapi import APIRouter, HTTPException, Depends, Query, Body, UploadFile, File, BackgroundTasks
from typing import Optional, List
from datetime import datetime, timezone, timedelta
import asyncio
import re
import uuid
import logging
import json
from sqlalchemy import text as _sa_text
from pg_models import IssueVersion as _IssueVersionModel

from dependencies import db, get_current_user, require_roles, UserRole
from engines.product_hub_rbac import (
    HubAction, HubRole, is_platform_admin, check_permission,
    enforce_permission, enforce_ownership_or_admin,
    check_resource_ownership, can_access_comments, redact_issue_for_role,
    require_hub_action, get_user_id, resolve_hub_role,
    is_main_admin, is_super_admin, MAIN_ADMIN_EMAILS,
)
from engines.sql_utils import gd_find, gd_find_one, gd_insert, gd_insert_many, gd_update_one, gd_update_many, gd_count, gd_delete_one, gd_delete_many, gd_distinct, _gd_aggregate

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
    IssueCreate, IssueUpdate, IssueComment, CommentUpdate, StatusUpdate,
    AssignIssue, FeedbackResponse, TitleUpdate, PriorityUpdate,
    BulkUpdateRequest, BulkDeleteRequest,
    ISSUE_TYPE_LABELS, ISSUE_TYPE_COMPAT, DYNAMIC_FIELDS_BY_TYPE,
    ACCOUNT_TYPE_OPTIONS, SECTION_OPTIONS,
    VALID_ISSUE_TYPES, VALID_ACCOUNT_TYPES, VALID_SECTIONS, VALID_TEAMS,
    IssueType, IssuePriority, IssueStatus,
    CommentType, AuditRole,
    ALLOWED_EVIDENCE_IMAGE_TYPES, MAX_EVIDENCE_IMAGE_SIZE_MB,
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

        all_issues = await gd_find(db.session, "product_issues", {"status": {"$nin": ["rejected"]}}, order_by="created_at", desc_order=True, limit=50)

        existing_summaries = []
        for ex in all_issues[:30]:
            existing_summaries.append(
                f"[{ex.get('id','')}] {ex.get('title','')} | {ex.get('section','')} > {ex.get('page','')} | {ex.get('current_behavior','')[:100]}"
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

        response = await asyncio.to_thread(
            client.chat.completions.create,
            model="gpt-5-mini",
            messages=[
                {"role": "system", "content": "You are a product intelligence AI. Respond ONLY with valid JSON."},
                {"role": "user", "content": prompt}
            ],
            max_completion_tokens=600,
            reasoning_effort="minimal",
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


# ---------------------------------------------------------------------------
# Hakim engineering-prompt generation (Replit execution-ready structure)
# ---------------------------------------------------------------------------
# Source of truth for the prompt the team copies into the coding platform.
# Hakim transforms the issue (in any language) into a strict, root-cause-
# oriented, implementation-ready engineering prompt written in professional
# English. The structure below is canonical and enforced by validation; the
# LLM produces the rich content, and a deterministic builder guarantees the
# same structure whenever the LLM is unavailable or returns invalid output.

# Exact section order — do NOT reorder without updating validation + builders.
ENGINEERING_PROMPT_SECTIONS = [
    "Objective",
    "Investigation Steps",
    "Execution Logic",
    "Constraints / Guardrails",
    "Expected Output",
    "QA / Verification",
    "Important implementation note",
]

# Minimum characters of content required inside each section for the LLM
# output to be accepted (otherwise we fall back to the deterministic build).
_MIN_SECTION_CONTENT_CHARS = 20

# Markers from the previous descriptive format. If any survive in the output
# we reject it so the old weak structure can never be reused underneath.
_LEGACY_PROMPT_MARKERS = (
    "[ISSUE TYPE]",
    "[CURRENT BEHAVIOR]",
    "[EXPECTED BEHAVIOR]",
    "EXECUTION INSTRUCTIONS",
    "HAKIM AI ANALYSIS",
)


def _section_header(name: str) -> str:
    return f"## {name}"


# Matches an ATX heading start with CommonMark-permitted leading indentation
# (any amount; we escape conservatively) followed by space/tab or end-of-line.
_HEADER_LINE_RE = re.compile(r"(?m)^([ \t]*)(#{1,6})(?=[ \t]|$)")

# Free-text fact keys that carry user/LLM-derived content and are interpolated
# into the prompt markdown. These MUST be sanitized; structural/control fields
# (issue_number, issue_type_code, has_attachments) are deliberately excluded.
_SANITIZE_FACT_KEYS = (
    "issue_type", "title", "priority", "section", "page", "account_type",
    "current_behavior", "expected_behavior", "steps", "reproducibility",
    "error_msg", "url", "device", "browser", "impact_text", "technical_notes",
    "team", "team_reasoning", "priority_reasoning",
)


def _sanitize_fact(value) -> str:
    """Neutralize user-controlled text so it cannot break the canonical structure.

    - Escapes any line that starts with markdown header marks (``#``..``######``)
      so reporter text can never inject an extra ``##`` section header.
    - Swaps the ASCII space inside any legacy-format marker for a non-breaking
      space (visually identical) so embedded marker literals cannot trip the
      validator and force a fallback or reject a legitimate prompt.
    """
    text = str(value).replace("\r\n", "\n").replace("\r", "\n")
    text = _HEADER_LINE_RE.sub(r"\1\\\2", text)
    for marker in _LEGACY_PROMPT_MARKERS:
        text = re.sub(re.escape(marker), marker.replace(" ", "\u00a0"), text, flags=re.IGNORECASE)
    return text


def _collect_issue_facts(issue: dict) -> dict:
    """Normalise the issue document into the facts the prompt builders read."""
    hakim = issue.get("hakim_analysis", {}) or {}
    impact_list = issue.get("impact", []) or []
    facts = {
        "issue_number": issue.get("issue_number", ""),
        "issue_type_code": issue.get("issue_type", ""),
        "issue_type": ISSUE_TYPE_LABELS.get(issue.get("issue_type", ""), issue.get("issue_type", "")),
        "title": issue.get("title") or hakim.get("suggested_title", ""),
        "priority": PRIORITY_LABELS.get(issue.get("priority", ""), issue.get("priority", "")),
        "section": issue.get("section", "") or "N/A",
        "page": issue.get("page", "") or "N/A",
        "account_type": issue.get("account_type", "") or "N/A",
        "current_behavior": issue.get("current_behavior", "") or "N/A",
        "expected_behavior": issue.get("expected_behavior", "") or "N/A",
        "steps": issue.get("steps_to_reproduce", "") or "",
        "reproducibility": issue.get("reproducibility", "") or "N/A",
        "error_msg": issue.get("error_message", "") or "",
        "url": issue.get("url", "") or "",
        "device": issue.get("device", "") or "",
        "browser": issue.get("browser", "") or "",
        "impact_text": ", ".join(impact_list) if impact_list else (hakim.get("impact_assessment", "") or "N/A"),
        "technical_notes": hakim.get("technical_notes", "") or "",
        "team": hakim.get("suggested_team", "") or "N/A",
        "team_reasoning": hakim.get("team_reasoning", "") or "",
        "priority_reasoning": hakim.get("priority_reasoning", "") or "",
        "has_attachments": bool(issue.get("attachments") or issue.get("evidence") or issue.get("screenshots")),
    }
    for key in _SANITIZE_FACT_KEYS:
        facts[key] = _sanitize_fact(facts[key])
    return facts


_ENGINEERING_SYSTEM_PROMPT = (
    "You are Hakim (حكيم), the senior engineering intelligence assistant for NASSAQ "
    "(نَسَّق), a multi-tenant school management platform.\n\n"
    "Your job: transform a product/issue report into a single, strict, "
    "implementation-ready engineering prompt that an engineer pastes directly into "
    "a coding agent to fix the issue with zero rewriting.\n\n"
    "NASSAQ stack & rules you MUST encode into every prompt:\n"
    "- Frontend: React (CRACO) + Tailwind, RTL Arabic UI, brand design tokens.\n"
    "- Backend: FastAPI (Python) + PostgreSQL + SQLAlchemy (async), Pydantic schemas.\n"
    "- Strict multi-tenancy: tenant_id/school_id isolation must be preserved.\n"
    "- RBAC and role hierarchy must be preserved; never weaken role/permission checks.\n"
    "- One source of truth per concern; backend/data rules are authoritative over UI.\n"
    "- Prefer the smallest safe vertical slice; no fake/cosmetic fixes.\n\n"
    "Engineering standards every prompt MUST enforce:\n"
    "- Full-stack-first reasoning: inspect actual routes, models/tables/enums, API "
    "endpoints/services, guards/middleware/role checks, and feature flags/config.\n"
    "- Determine ROOT CAUSE before implementing; do not stop at describing symptoms.\n"
    "- Avoid UI-only fixes when backend/data rules may be the real cause.\n"
    "- Be regression-aware: protect existing working flows.\n\n"
    "OUTPUT FORMAT — absolutely mandatory:\n"
    "- Write the ENTIRE prompt in clear, professional English, even when the issue "
    "input is in Arabic. Understand the Arabic business meaning, then express it in "
    "English. Do not translate literally; capture intent.\n"
    "- Output ONLY the prompt. No preamble, no meta commentary, no code fences "
    "around the whole thing.\n"
    "- Start the output DIRECTLY with the line '## Objective'. Do NOT add any title, "
    "H1 banner, or any text before it.\n"
    "- Use EXACTLY these seven section headers, each as its own line, written exactly "
    "as shown (## then the title), in THIS order, once each, and do NOT add any other "
    "'#' or '##' header beyond these seven:\n"
    "  ## Objective\n"
    "  ## Investigation Steps\n"
    "  ## Execution Logic\n"
    "  ## Constraints / Guardrails\n"
    "  ## Expected Output\n"
    "  ## QA / Verification\n"
    "  ## Important implementation note\n"
    "- Within a section you may use bullet/numbered lists for content, but do not "
    "introduce additional '##' top-level headers.\n"
    "- Every section must contain substantive, issue-specific content (no empty "
    "sections, no generic boilerplate that could apply to any bug).\n"
    "- Scale depth to complexity: a simple issue yields a concise but complete "
    "prompt; a complex issue yields deeper investigation and QA detail.\n"
    "- Map the issue metadata into the structure: current behavior feeds Objective "
    "and Investigation Steps; expected behavior feeds Objective, Execution Logic, "
    "and QA; page/section/account/role/context enrich Investigation Steps and QA; "
    "attachments/screenshots guide visual or flow-specific validation.\n"
    "- Investigation Steps must instruct inspecting real routes, models/tables/enums, "
    "API endpoints/services, guards/middleware/role checks, and feature flags before "
    "any code change, and must require confirming the root cause first.\n"
    "- QA / Verification must include concrete, role-aware and tenancy-aware "
    "regression scenarios.\n"
)


def _build_engineering_user_prompt(facts: dict) -> str:
    parts = []
    parts.append(
        "Transform the following NASSAQ issue report into the strict engineering "
        "prompt described in your instructions. Preserve the business meaning; "
        "output professional English only.\n"
    )
    parts.append("=== ISSUE REPORT ===")
    if facts["issue_number"]:
        parts.append(f"Issue Number: {facts['issue_number']}")
    parts.append(f"Issue Type: {facts['issue_type']} ({facts['issue_type_code']})")
    parts.append(f"Title: {facts['title']}")
    parts.append(f"Priority: {facts['priority']}")
    if facts["priority_reasoning"]:
        parts.append(f"Priority Reasoning: {facts['priority_reasoning']}")
    parts.append(f"Section: {facts['section']}")
    parts.append(f"Page: {facts['page']}")
    parts.append(f"Account Type / Role context: {facts['account_type']}")
    if facts["url"]:
        parts.append(f"URL: {facts['url']}")
    if facts["device"]:
        parts.append(f"Device: {facts['device']}")
    if facts["browser"]:
        parts.append(f"Browser: {facts['browser']}")
    parts.append("")
    parts.append(f"Current Behavior (as reported):\n{facts['current_behavior']}")
    parts.append("")
    parts.append(f"Expected Behavior (as reported):\n{facts['expected_behavior']}")
    if facts["steps"]:
        parts.append("")
        parts.append(f"Steps to Reproduce:\n{facts['steps']}")
    parts.append("")
    parts.append(f"Reproducibility: {facts['reproducibility']}")
    if facts["error_msg"]:
        parts.append(f"Error Message:\n{facts['error_msg']}")
    parts.append(f"Impact: {facts['impact_text']}")
    if facts["technical_notes"]:
        parts.append(f"Hakim Technical Notes (prior analysis): {facts['technical_notes']}")
    parts.append(f"Suggested Owning Team: {facts['team']}")
    if facts["team_reasoning"]:
        parts.append(f"Team Reasoning: {facts['team_reasoning']}")
    if facts["has_attachments"]:
        parts.append(
            "Attachments/screenshots are present — include visual/flow-specific "
            "validation steps in QA / Verification."
        )
    parts.append("=== END ISSUE REPORT ===")
    return "\n".join(parts)


# CommonMark ATX heading: 0-3 leading spaces, 1-6 '#', then space/tab+title or EOL.
_HEADER_RE = re.compile(r"^ {0,3}(#{1,6})(?:[ \t]+(.*?))?[ \t]*$")


def _validate_engineering_prompt(text: str) -> bool:
    """Strictly enforce the canonical structure.

    Requirements:
    - No legacy descriptive-format markers anywhere.
    - Output starts directly with the first required header (no preamble, no H1).
    - EXACTLY the seven required ``## `` headers, each once, in exact order, with
      no other top-level (``#``/``##``) headers. ``###`` and deeper are allowed
      only as in-section subheaders.
    - Each section holds substantive content.
    """
    if not text or not text.strip():
        return False
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    upper = text.upper()
    for marker in _LEGACY_PROMPT_MARKERS:
        if marker.upper() in upper:
            return False

    required = [s.lower() for s in ENGINEERING_PROMPT_SECTIONS]
    lines = text.split("\n")

    h2_headers = []  # (name_lower, line_index)
    seen_first_header = False
    for idx, line in enumerate(lines):
        m = _HEADER_RE.match(line)
        if not m:
            # Reject any non-blank content before the first required header.
            if not seen_first_header and line.strip():
                return False
            continue
        level = len(m.group(1))
        name = (m.group(2) or "").strip()
        if level == 1:
            return False  # no H1 titles/banners allowed
        if level == 2:
            seen_first_header = True
            h2_headers.append((name.lower(), idx))
        else:
            # ###+ subheaders are content, but only inside a section.
            if not seen_first_header:
                return False

    # Exactly the seven required H2 headers, in order, once each — nothing else.
    if [h[0] for h in h2_headers] != required:
        return False

    for i, (_name, line_idx) in enumerate(h2_headers):
        start = line_idx + 1
        end = h2_headers[i + 1][1] if i + 1 < len(h2_headers) else len(lines)
        content = "\n".join(lines[start:end]).strip()
        if len(content) < _MIN_SECTION_CONTENT_CHARS:
            return False
    return True


def _fallback_engineering_prompt(facts: dict) -> str:
    """Deterministic builder that always satisfies the canonical structure.

    Used when the LLM is unavailable or returns output that fails validation.
    It still produces a real, root-cause-oriented engineering prompt (never the
    old descriptive format), mapping the issue metadata into the structure.
    """
    page = facts["page"]
    section = facts["section"]
    issue_type = facts["issue_type"]
    account = facts["account_type"]

    # Output MUST start directly with the first required header (no preamble/H1).
    lines = []

    # Objective
    lines.append(_section_header("Objective"))
    ref = f" (Issue #{facts['issue_number']}, priority: {facts['priority']})" if facts["issue_number"] else ""
    lines.append(f"Title: {facts['title']}.")
    lines.append(
        f"Resolve the reported {issue_type}{ref} on the \"{page}\" page "
        f"(section: {section}, account/role context: {account})."
    )
    lines.append(f"- Reported current behavior: {facts['current_behavior']}")
    lines.append(f"- Required expected behavior: {facts['expected_behavior']}")
    lines.append(
        "Deliver a root-cause fix that makes the actual behavior match the expected "
        "behavior without weakening RBAC or tenant isolation."
    )
    lines.append("")

    # Investigation Steps
    lines.append(_section_header("Investigation Steps"))
    lines.append("Before writing any code, confirm the root cause by inspecting the real system:")
    lines.append(f"1. Reproduce the issue on the \"{page}\" page for an `{account}` account.")
    lines.append("2. Inspect the actual backend routes/services that power this page (FastAPI routers under `backend/routes/`).")
    lines.append("3. Inspect the relevant SQLAlchemy models/tables/enums and Pydantic schemas in `shared_models.py`.")
    lines.append("4. Inspect guards/middleware and role/permission checks (RBAC) and tenant scoping on those routes.")
    lines.append("5. Check any feature flags or config-driven behavior that could change the outcome.")
    if facts["steps"]:
        lines.append(f"6. Follow the reporter's reproduction steps:\n{facts['steps']}")
    if facts["error_msg"]:
        lines.append(f"7. Trace this error to its source:\n{facts['error_msg']}")
    lines.append("Determine the true root cause before implementing; do not stop at the symptom.")
    lines.append("")

    # Execution Logic
    lines.append(_section_header("Execution Logic"))
    lines.append("Implement the smallest safe vertical slice that fixes the confirmed root cause:")
    lines.append("- Fix the authoritative source of truth (backend/data rules) first; do not apply a UI-only patch when a backend/data rule is wrong.")
    lines.append(f"- Make the behavior on \"{page}\" match the expected behavior described above.")
    lines.append("- Keep one source of truth per concern; avoid duplicating logic across frontend and backend.")
    lines.append("- Preserve RTL Arabic UI and existing brand design tokens for any frontend change.")
    if facts["technical_notes"]:
        lines.append(f"- Prior Hakim technical analysis to consider: {facts['technical_notes']}")
    lines.append("")

    # Constraints / Guardrails
    lines.append(_section_header("Constraints / Guardrails"))
    lines.append("- Preserve multi-tenancy: every data access must stay scoped by tenant_id/school_id.")
    lines.append("- Preserve RBAC and role hierarchy; never weaken or bypass permission checks.")
    lines.append("- Do not break existing working flows (regression-aware).")
    lines.append("- No fake or cosmetic fixes; no relabeling without fixing the underlying behavior.")
    lines.append("- Schema changes only via Alembic; no destructive DB operations.")
    lines.append("- API errors must return safe Arabic messages (no raw exception strings).")
    lines.append("- Use NassaqAlertDialog for user-facing warnings/errors/confirms.")
    lines.append("")

    # Expected Output
    lines.append(_section_header("Expected Output"))
    lines.append("- A root-cause summary explaining why the issue happened.")
    lines.append("- The exact files changed and why.")
    lines.append(f"- The \"{page}\" behavior now matching: {facts['expected_behavior']}")
    lines.append("- Confirmation that RBAC and tenant isolation are intact.")
    lines.append("")

    # QA / Verification
    lines.append(_section_header("QA / Verification"))
    lines.append(f"- Verify the fix end-to-end on \"{page}\" as an `{account}` account.")
    lines.append("- Verify the expected behavior is met and the reported current behavior no longer occurs.")
    lines.append("- Role-aware regression: confirm other roles still see only what they are entitled to.")
    lines.append("- Tenancy regression: confirm no cross-tenant data leakage on the affected endpoints.")
    if facts["has_attachments"]:
        lines.append("- Visually validate against the attached screenshots/flows.")
    lines.append(f"- Reproducibility was reported as: {facts['reproducibility']} — confirm it is now resolved.")
    lines.append("")

    # Important implementation note
    lines.append(_section_header("Important implementation note"))
    lines.append(
        "Do not consider this complete until the root cause is fixed at the "
        "source-of-truth level (backend/data first), RBAC and tenant isolation are "
        "preserved, existing flows are not regressed, and the fix is verified "
        "end-to-end — not just visually adjusted."
    )

    return "\n".join(lines)


def _llm_generate_engineering_prompt(facts: dict) -> Optional[str]:
    """Ask Hakim to produce the engineering prompt. Returns None on any failure."""
    try:
        from openai import OpenAI
        import os
        api_key = os.environ.get("AI_INTEGRATIONS_OPENAI_API_KEY", "")
        base_url = os.environ.get("AI_INTEGRATIONS_OPENAI_BASE_URL", "")
        if not api_key:
            return None

        client = OpenAI(api_key=api_key, base_url=base_url if base_url else None)
        response = client.chat.completions.create(
            model="gpt-5-mini",
            messages=[
                {"role": "system", "content": _ENGINEERING_SYSTEM_PROMPT},
                {"role": "user", "content": _build_engineering_user_prompt(facts)},
            ],
            max_completion_tokens=4096,
            reasoning_effort="minimal",
            timeout=60,
        )
        text = (response.choices[0].message.content or "").strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        return text or None
    except Exception as e:
        logger.warning(f"Hakim engineering-prompt generation failed: {e}")
        return None


async def _generate_prompt(issue: dict) -> str:
    """Generate the Replit-ready engineering prompt for an issue.

    Source of truth for the prompt the team copies into the coding platform.
    Tries Hakim (LLM) first, validates the structure, and falls back to a
    deterministic builder that always satisfies the canonical structure.
    """
    facts = _collect_issue_facts(issue)
    llm_text = await asyncio.to_thread(_llm_generate_engineering_prompt, facts)
    if llm_text and _validate_engineering_prompt(llm_text):
        return llm_text
    return _fallback_engineering_prompt(facts)


async def _next_issue_number() -> int:
    from db import engine as async_engine
    from sqlalchemy import text
    async with async_engine.connect() as conn:
        result = await conn.execute(text("SELECT nextval('product_issue_number_seq')"))
        return result.scalar()


async def _ensure_issue_counter():
    from db import engine as async_engine
    from sqlalchemy import text
    async with async_engine.connect() as conn:
        result = await conn.execute(text(
            "SELECT COALESCE(MAX(issue_number), 0) FROM product_issues"
        ))
        current_max = result.scalar() or 0
        if current_max > 0:
            await conn.execute(text("SELECT setval('product_issue_number_seq', :val)"), {"val": current_max})
            await conn.commit()


async def _ensure_data_integrity():
    results = {"backfilled_is_deleted": 0, "fixed_missing_numbers": 0, "resequenced": 0}

    backfill = await gd_update_many(db.session, "product_issues", {"is_deleted": {"$exists": False}}, {"is_deleted": False})
    results["backfilled_is_deleted"] = backfill

    missing_num = await gd_find(db.session, "product_issues", {"issue_number": {"$exists": False}}, limit=1000)
    for doc in missing_num:
        next_num = await _next_issue_number()
        await gd_update_one(db.session, "product_issues", {"id": doc["id"]}, {"issue_number": next_num})
        results["fixed_missing_numbers"] += 1

    pipeline = [
        {"$group": {"_id": "$issue_number", "count": {"$sum": 1}, "ids": {"$push": "$id"}}},
        {"$match": {"count": {"$gt": 1}}}
    ]
    dupes = await _gd_aggregate(db.session, "product_issues", pipeline)
    for dupe in dupes:
        for extra_id in dupe["ids"][1:]:
            next_num = await _next_issue_number()
            await gd_update_one(db.session, "product_issues", {"id": extra_id}, {"issue_number": next_num})
            results["resequenced"] += 1

    return results


async def _get_issue_or_404(issue_id: str) -> dict:
    issue = await gd_find_one(db.session, "product_issues", {"id": issue_id, "is_deleted": {"$ne": True}})
    if not issue:
        _hub_error(404, "ISSUE_NOT_FOUND", "المشكلة غير موجودة", {"issue_id": issue_id})
    return issue


@router.get("/config")
async def get_hub_config(current_user: dict = Depends(get_current_user)):
    admin = is_platform_admin(current_user)
    main_admin = is_main_admin(current_user)

    reporters = []
    if admin:
        pipeline = [
            {"$group": {"_id": "$created_by", "name": {"$first": "$employee_name"}}},
            {"$sort": {"name": 1}},
        ]
        reporters = [
            {"value": r["_id"], "label": r["name"] or r["_id"]}
            for r in await _gd_aggregate(db.session, "product_issues", pipeline)
        ]

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
        "reporters": reporters,
        "is_admin": admin,
        "is_main_admin": main_admin,
        "permissions": {
            "can_assign": main_admin,
            "can_change_status": main_admin,
            "can_view_prompt": main_admin,
            "can_view_analytics": main_admin,
            "can_update_priority": main_admin,
            "can_update_title": main_admin,
            "can_approve_closure": main_admin,
            "can_delete": main_admin,
            "can_reanalyze": main_admin,
            "can_view_hakim_insights": main_admin,
            "can_view_duplicates": main_admin,
        },
    }


@router.post("/upload-evidence")
async def upload_evidence(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
):
    """Upload an image evidence (screenshot) for a Create Challenge submission.

    Returns a base64 data URL the client stores in `attachments[]` on the
    challenge payload. Authorization mirrors challenge-creation rights via the
    MANAGE_ATTACHMENTS hub action. v1 accepts PNG/JPEG/WEBP only and enforces a
    server-side size cap of MAX_EVIDENCE_IMAGE_SIZE_MB.
    """
    enforce_permission(current_user, HubAction.MANAGE_ATTACHMENTS)

    import base64
    max_bytes = MAX_EVIDENCE_IMAGE_SIZE_MB * 1024 * 1024

    fname = (file.filename or "").lower()
    ext = fname[fname.rfind("."):] if "." in fname else ""
    ext_to_type = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
    }
    inferred = ext_to_type.get(ext)
    ctype = (file.content_type or "").lower()
    if ctype in ("", "application/octet-stream") and inferred:
        ctype = inferred
    if ctype not in ALLOWED_EVIDENCE_IMAGE_TYPES:
        _hub_error(400, "INVALID_FILE_TYPE", "صيغة الملف غير مدعومة — استخدم PNG أو JPG أو WEBP")
    final_ctype = inferred or ctype

    chunks: list[bytes] = []
    total = 0
    CHUNK = 64 * 1024
    while True:
        chunk = await file.read(CHUNK)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            _hub_error(
                400,
                "FILE_TOO_LARGE",
                f"حجم لقطة الشاشة يتجاوز {MAX_EVIDENCE_IMAGE_SIZE_MB} ميغابايت",
            )
        chunks.append(chunk)
    content = b"".join(chunks)
    if not content:
        _hub_error(400, "EMPTY_FILE", "الملف فارغ")

    # Verify the bytes are actually a real image of an allowed format.
    # This blocks MIME-spoofing where a renamed binary is uploaded as .png.
    try:
        from PIL import Image, UnidentifiedImageError
        from io import BytesIO
        with Image.open(BytesIO(content)) as img:
            img.verify()
        pil_format_to_mime = {"PNG": "image/png", "JPEG": "image/jpeg", "WEBP": "image/webp"}
        with Image.open(BytesIO(content)) as img2:
            actual_mime = pil_format_to_mime.get((img2.format or "").upper())
    except (UnidentifiedImageError, Exception):
        _hub_error(400, "INVALID_IMAGE", "الملف ليس صورة صالحة")
    if not actual_mime or actual_mime not in ALLOWED_EVIDENCE_IMAGE_TYPES:
        _hub_error(400, "INVALID_IMAGE", "الملف ليس صورة بصيغة مدعومة")
    # Trust the verified format over any client-supplied or extension-inferred type.
    final_ctype = actual_mime

    encoded = base64.b64encode(content).decode("utf-8")
    return {
        "success": True,
        "file_url": f"data:{final_ctype};base64,{encoded}",
        "file_name": file.filename,
        "content_type": final_ctype,
        "size": len(content),
    }


async def _enrich_created_issue(issue_id: str, actor: dict, user_provided_title: bool) -> None:
    """Run the heavy Hakim AI work for a freshly created issue, off the request path.

    The Hakim analysis + engineering-prompt generation are two sequential LLM
    calls that used to run synchronously inside ``create_issue`` and pushed the
    POST to ~38s. The dev proxy / production load balancer severs the connection
    long before that, so the browser never received the 200 and showed a false
    "فشل في إرسال التحدي" toast even though the issue was already saved. We now
    return immediately and enrich here, after the response is sent.

    This runs with its OWN SQLAlchemy session because the request-scoped session
    bound by ``pg_session_middleware`` is already closed by the time a background
    task executes. It is best-effort and fail-safe: any error is logged and
    swallowed so a failed enrichment never crashes the worker, and the issue can
    still be re-analyzed via ``POST /issues/{id}/reanalyze``.
    """
    from db import async_session_factory
    try:
        async with async_session_factory() as session:
            db.set_session(session)
            try:
                issue = await gd_find_one(
                    db.session, "product_issues", {"id": issue_id, "is_deleted": {"$ne": True}}
                )
                if not issue:
                    logger.info(f"[ProductHub] Skip AI enrichment — issue {issue_id[:8]} missing/deleted")
                    return

                now = datetime.now(timezone.utc)
                hakim_analysis = await _run_hakim_analysis(issue)
                suggested_title = hakim_analysis.get("suggested_title", "")
                suggested_priority = hakim_analysis.get("suggested_priority", "medium")
                suggested_team = hakim_analysis.get("suggested_team")

                # Reflect AI results on the in-memory doc so the engineering
                # prompt is generated against the enriched facts. These in-memory
                # mutations feed prompt generation only — what we actually persist
                # is decided below against a fresh re-fetch.
                issue["hakim_analysis"] = hakim_analysis
                if not user_provided_title and suggested_title:
                    issue["title"] = suggested_title
                if suggested_priority and suggested_priority != "medium":
                    issue["priority"] = suggested_priority
                if suggested_team:
                    issue["assigned_team"] = suggested_team
                generated_prompt = await _generate_prompt(issue)

                # Re-fetch immediately before writing. The LLM calls above take
                # tens of seconds, during which an admin may have edited the
                # issue. Base every conditional override on the CURRENT persisted
                # state so enrichment never clobbers a human edit.
                current = await gd_find_one(
                    db.session, "product_issues", {"id": issue_id, "is_deleted": {"$ne": True}}
                )
                if not current:
                    logger.info(f"[ProductHub] Skip AI enrichment write — issue {issue_id[:8]} missing/deleted")
                    return

                existing_ai = current.get("ai") if isinstance(current.get("ai"), dict) else {}
                updates: dict = {
                    "hakim_analysis": hakim_analysis,
                    "ai_suggested_priority": suggested_priority,
                    "ai": {
                        **existing_ai,
                        "suggested_title": suggested_title,
                        "duplicate_detected": bool(hakim_analysis.get("duplicate_ids")),
                        "duplicate_candidates": [
                            {"issue_id": did, "confidence": 0.0}
                            for did in hakim_analysis.get("duplicate_ids", [])[:3]
                        ],
                        "suggested_team": suggested_team,
                        "priority_reasoning": hakim_analysis.get("priority_reasoning", ""),
                        "team_reasoning": hakim_analysis.get("team_reasoning", ""),
                        "technical_notes": hakim_analysis.get("technical_notes", ""),
                        "impact_assessment": hakim_analysis.get("impact_assessment", ""),
                    },
                    "updated_at": now.isoformat(),
                }

                # Only override creation-time defaults — never clobber an admin edit.
                default_title = f"مشكلة في {current.get('page')}"
                if not user_provided_title and suggested_title and current.get("title") == default_title:
                    updates["title"] = suggested_title

                if current.get("priority") == "medium" and suggested_priority and suggested_priority != "medium":
                    updates["priority"] = suggested_priority
                    sla = calculate_sla(suggested_priority, now)
                    updates["sla_deadline"] = sla["sla_deadline"]
                    updates["sla_status"] = sla["sla_status"]

                if not current.get("assigned_team") and suggested_team:
                    updates["assigned_team"] = suggested_team
                    updates["assignment"] = {**(current.get("assignment") or {}), "team": suggested_team}

                # Keep an admin-regenerated prompt if one now exists; otherwise
                # persist the one we just generated.
                if current.get("generated_prompt"):
                    updates["ai"]["generated_prompt"] = current.get("generated_prompt")
                else:
                    updates["generated_prompt"] = generated_prompt
                    updates["ai"]["generated_prompt"] = generated_prompt

                await gd_update_one(db.session, "product_issues", {"id": issue_id}, updates)

                if hakim_analysis.get("duplicate_ids"):
                    for dup_id in hakim_analysis["duplicate_ids"][:3]:
                        try:
                            already = await gd_find_one(
                                db.session, "issue_duplicates_map",
                                {"issue_id": issue_id, "duplicate_of": dup_id},
                            )
                            if already:
                                continue
                            target = await gd_find_one(
                                db.session, "product_issues",
                                {"id": dup_id, "is_deleted": {"$ne": True}},
                            )
                            if not target:
                                logger.warning(f"[ProductHub] Skipping duplicate entry: issue {dup_id} not found in product_issues")
                                continue
                            await gd_insert(db.session, "issue_duplicates_map", {
                                "id": str(uuid.uuid4()),
                                "issue_id": issue_id,
                                "duplicate_of": dup_id,
                                "confidence": 0.0,
                                "detected_by": "hakim",
                                "created_at": now.isoformat(),
                            })
                            await audit_duplicate_detected(issue_id, actor, dup_id)
                        except Exception as dup_err:
                            logger.warning(f"[ProductHub] Failed to record duplicate for {dup_id}: {dup_err}")

                await handle_hakim_analysis(issue_id, actor, hakim_analysis, source="auto_on_create")
                await audit_ai_analyzed(issue_id, actor, hakim_analysis)
                await handle_prompt_generated(issue_id, actor)
                await audit_prompt_generated(issue_id, actor)

                await session.commit()
                logger.info(f"[ProductHub] AI enrichment complete for issue {issue_id[:8]}")
            except Exception:
                await session.rollback()
                raise
            finally:
                db.set_session(None)
    except Exception as e:
        logger.warning(f"[ProductHub] Background AI enrichment failed for issue {issue_id[:8]}: {e}")


@router.post("/issues")
async def create_issue(
    data: IssueCreate,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
):
    now = datetime.now(timezone.utc)
    user_id = get_user_id(current_user)

    issue = data.to_issue_document(user_id, current_user)
    issue_id = issue["id"]
    issue["issue_number"] = await _next_issue_number()

    # Insert with safe defaults and return fast. The heavy AI work (Hakim
    # analysis + engineering-prompt generation) is offloaded to a post-response
    # background task — see _enrich_created_issue for the full rationale.
    user_provided_title = bool(data.title and data.title.strip())
    issue["title"] = data.title.strip() if user_provided_title else f"مشكلة في {data.page}"
    issue["priority"] = "medium"
    issue["ai_suggested_priority"] = "medium"

    sla = calculate_sla(issue["priority"], now)
    issue["sla_deadline"] = sla["sla_deadline"]
    issue["sla_status"] = sla["sla_status"]

    issue["system"]["last_status_changed_at"] = now.isoformat()

    await gd_insert(db.session, "product_issues", {**issue, "_id": issue_id})

    await handle_issue_created(issue_id, issue, current_user)
    await audit_issue_created(issue_id, current_user, issue)

    # Commit the creation NOW so the row is durable and visible before the
    # background enrichment task runs. Under BaseHTTPMiddleware, the response's
    # BackgroundTasks execute concurrently with pg_session_middleware's own
    # post-response commit, so without this explicit commit the task's fresh
    # session can race ahead and not yet see the freshly-inserted issue —
    # causing it to skip enrichment entirely.
    await db.session.commit()

    issue.pop("_id", None)
    logger.info(f"[ProductHub] Issue created: #{issue['issue_number']} ({issue_id[:8]}) — AI enrichment scheduled")

    # Sanitized actor copy (identity/role only — no token/password fields) for
    # the background task's event/audit writes.
    actor = {
        "id": user_id,
        "full_name": current_user.get("full_name", ""),
        "role": current_user.get("role", ""),
        "email": current_user.get("email", ""),
    }
    background_tasks.add_task(_enrich_created_issue, issue_id, actor, user_provided_title)

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

    query: dict = {"is_deleted": {"$ne": True}}
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
        import re as _re
        safe_search = _re.escape(search)
        query["$or"] = [
            {"title": {"$regex": safe_search, "$options": "i"}},
            {"current_behavior": {"$regex": safe_search, "$options": "i"}},
            {"employee_name": {"$regex": safe_search, "$options": "i"}},
            {"page": {"$regex": safe_search, "$options": "i"}},
        ]

    total = await gd_count(db.session, "product_issues", query)
    skip = (page - 1) * limit
    issues = await gd_find(db.session, "product_issues", query, order_by="created_at", desc_order=True, offset=skip, limit=limit)

    issue_ids = [i.get("id") for i in issues if i.get("id")]
    comment_counts = {}
    recent_comments_map = {}
    if issue_ids:
        pipeline = [
            {"$match": {"issue_id": {"$in": issue_ids}}},
            {"$group": {"_id": "$issue_id", "count": {"$sum": 1}}}
        ]
        count_results = await _gd_aggregate(db.session, "issue_comments", pipeline)
        for doc in count_results:
            comment_counts[doc["_id"]] = doc["count"]

        recent_pipeline = [
            {"$match": {"issue_id": {"$in": issue_ids}}},
            {"$sort": {"timestamp": -1}},
            {"$group": {
                "_id": "$issue_id",
                "comments": {"$push": {
                    "user_name": "$user_name",
                    "content": "$content",
                    "timestamp": "$timestamp",
                    "created_by": "$created_by",
                }},
            }},
        ]
        recent_results = await _gd_aggregate(db.session, "issue_comments", recent_pipeline)
        for doc in recent_results:
            recent_comments_map[doc["_id"]] = doc["comments"][:3]

    for issue in issues:
        enrich_sla_state(issue)
        redact_issue_for_role(issue, current_user)
        issue["comment_count"] = comment_counts.get(issue.get("id"), 0)
        issue["recent_comments"] = recent_comments_map.get(issue.get("id"), [])

    return {"issues": issues, "total": total, "page": page, "limit": limit}


@router.get("/issues/{issue_id}")
async def get_issue(issue_id: str, current_user: dict = Depends(get_current_user)):
    admin = is_platform_admin(current_user)

    issue = await _get_issue_or_404(issue_id)

    if not admin:
        enforce_ownership_or_admin(current_user, issue, HubAction.VIEW_OWN_ISSUE)

    activity = await gd_find(db.session, "issue_activity_log", {"issue_id": issue_id}, order_by="timestamp", desc_order=True, limit=100)

    comments = await gd_find(db.session, "issue_comments", {"issue_id": issue_id}, order_by="timestamp", desc_order=False, limit=200)

    duplicates = []
    if is_main_admin(current_user):
        duplicates = await gd_find(db.session, "issue_duplicates_map", {"$or": [{"issue_id": issue_id}, {"duplicate_of": issue_id}]}, limit=20)

    enrich_sla_state(issue)
    await check_sla_warning(issue_id, issue, current_user)

    issue["activity_log"] = activity
    issue["comments"] = comments if can_access_comments(current_user, issue) else []
    issue["duplicates"] = duplicates
    issue["is_admin"] = admin
    issue["valid_transitions"] = list(VALID_STATUS_TRANSITIONS.get(issue.get("status", "new"), set()))

    main_admin = is_main_admin(current_user)
    permissions = {
        "can_change_status": main_admin,
        "can_assign": main_admin,
        "can_view_prompt": main_admin,
        "can_update_title": main_admin,
        "can_update_priority": main_admin,
        "can_approve_closure": main_admin,
        "can_delete": main_admin,
        "can_reanalyze": main_admin,
        "can_view_hakim_insights": main_admin,
        "can_view_duplicates": main_admin,
        "can_view_analytics": main_admin,
        "can_comment": can_access_comments(current_user, issue),
        "can_submit_feedback": (
            issue.get("status") == "done"
            and (admin or check_resource_ownership(current_user, issue))
        ),
        "is_main_admin": main_admin,
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
    if not is_platform_admin(current_user):
        _hub_error(403, "FORBIDDEN", "هذه العملية مقصورة على مديري المنصة فقط")
    enforce_permission(current_user, HubAction.UPDATE_ISSUE)
    issue = await _get_issue_or_404(issue_id)
    issue_tenant = issue.get("school_id") or issue.get("tenant_id")
    user_tenant = current_user.get("school_id") or current_user.get("tenant_id")
    if issue_tenant and user_tenant and issue_tenant != user_tenant:
        _hub_error(404, "NOT_FOUND", "التحدي غير موجود")

    changes = {}
    update_fields = [
        "current_behavior", "expected_behavior", "steps_to_reproduce",
        "error_message", "additional_details", "reproducibility",
    ]
    for field in update_fields:
        value = getattr(data, field, None)
        if value is not None:
            changes[field] = value.strip() if isinstance(value, str) else value

    if data.title is not None:
        changes["title"] = data.title
    if data.impact is not None:
        changes["impact"] = data.impact
    if data.related_to is not None:
        changes["technical.related_to"] = data.related_to

    if not changes:
        _hub_error(422, "NO_CHANGES", "لم يتم إرسال أي تعديلات")

    _VERSION_FIELDS = {
        "title", "current_behavior", "expected_behavior",
        "steps_to_reproduce", "error_message", "additional_details",
        "reproducibility", "impact",
    }
    previous_values = {k: issue.get(k) for k in changes if k in _VERSION_FIELDS}
    new_values = {k: changes[k] for k in changes if k in _VERSION_FIELDS}

    now = _now_iso()
    changes["updated_at"] = now
    changes["system.updated_at"] = now

    if "current_behavior" in changes:
        changes["description.current_behavior"] = changes["current_behavior"]
    if "expected_behavior" in changes:
        changes["description.expected_behavior"] = changes["expected_behavior"]
    if "reproducibility" in changes:
        changes["description.reproducible"] = changes["reproducibility"]

    if new_values:
        rev_row = await db.session.execute(
            _sa_text("SELECT COALESCE(MAX(revision), 0) + 1 FROM issue_versions WHERE issue_id = :iid"),
            {"iid": issue_id},
        )
        next_revision = rev_row.scalar() or 1
        version_obj = _IssueVersionModel(
            id=str(uuid.uuid4()),
            issue_id=issue_id,
            revision=next_revision,
            tenant_id=current_user.get("tenant_id") or current_user.get("school_id"),
            changed_by_user_id=get_user_id(current_user),
            changed_by_name=current_user.get("full_name", current_user.get("email", "")),
            changed_fields=list(new_values.keys()),
            previous_values=previous_values,
            new_values=new_values,
        )
        db.session.add(version_obj)

    await gd_update_one(db.session, "product_issues", {"id": issue_id}, changes)
    await handle_issue_updated(issue_id, current_user, changes)
    await audit_issue_updated(issue_id, current_user, changes)

    return {"success": True, "updated_fields": list(changes.keys())}


@router.get("/issues/{issue_id}/versions")
async def get_issue_versions(
    issue_id: str,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    current_user: dict = Depends(get_current_user),
):
    if not is_platform_admin(current_user):
        _hub_error(403, "FORBIDDEN", "هذه العملية مقصورة على مديري المنصة فقط")
    issue = await _get_issue_or_404(issue_id)
    issue_tenant = issue.get("school_id") or issue.get("tenant_id")
    user_tenant = current_user.get("school_id") or current_user.get("tenant_id")
    if issue_tenant and user_tenant and issue_tenant != user_tenant:
        _hub_error(404, "NOT_FOUND", "التحدي غير موجود")

    total = await gd_count(db.session, "issue_versions", {"issue_id": issue_id})

    versions = await gd_find(
        db.session, "issue_versions",
        {"issue_id": issue_id},
        order_by="revision", desc_order=True, limit=limit, offset=skip,
    )

    return {
        "versions": versions,
        "total": total,
        "skip": skip,
        "limit": limit,
        "issue_id": issue_id,
    }


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

    main_admin_override = is_main_admin(current_user) and new_status in {"in_progress", "done"}
    if not main_admin_override and not validate_status_transition(current_status, new_status):
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

    result = await gd_update_one(db.session, "product_issues", {"id": issue_id, "status": current_status}, update_fields)
    if result == 0:
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
        assignee = await gd_find_one(db.session, "users", {"id": data.assigned_to})
        if not assignee:
            _hub_error(422, "ASSIGNEE_NOT_FOUND", "المستخدم المعيّن غير موجود",
                       {"assigned_to": data.assigned_to})

    now = _now_iso()
    await gd_update_one(db.session, "product_issues", {"id": issue_id}, {
            "assigned_team": data.assigned_team,
            "assigned_to": data.assigned_to,
            "assigned_at": now,
            "updated_at": now,
            "assignment.team": data.assigned_team.lower() if data.assigned_team else None,
            "assignment.assigned_to": data.assigned_to,
            "system.updated_at": now,
        })

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
    if not can_access_comments(current_user, issue):
        raise HTTPException(status_code=403, detail={"success": False, "error_code": "FORBIDDEN_COMMENTS", "message": "ليس لديك صلاحية الوصول للتعليقات"})

    user_role = current_user.get("role", "")
    resolved_role = "platform_admin" if user_role == "platform_admin" else "internal_user"

    await _validate_mentions(data.mentions or [], current_user)

    safe_comment_type = data.comment_type or "general"
    if safe_comment_type != "general" and not is_main_admin(current_user):
        safe_comment_type = "general"

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
        "type": safe_comment_type,
        "mentions": data.mentions or [],
        "timestamp": _now_iso(),
        "edited": False,
    }

    await gd_insert(db.session, "issue_comments", comment)
    await handle_comment_added(issue_id, current_user, comment["id"])
    await audit_comment_added(issue_id, current_user, comment["id"], data.comment_type)
    comment.pop("_id", None)
    return comment


@router.put("/issues/{issue_id}/comments/{comment_id}")
async def edit_comment(
    issue_id: str,
    comment_id: str,
    data: CommentUpdate,
    current_user: dict = Depends(get_current_user),
):
    raise HTTPException(status_code=403, detail={"success": False, "error_code": "FORBIDDEN", "message": "تعديل التعليقات غير مسموح"})


@router.delete("/issues/{issue_id}/comments/{comment_id}")
async def delete_comment(
    issue_id: str,
    comment_id: str,
    current_user: dict = Depends(get_current_user),
):
    raise HTTPException(status_code=403, detail={"success": False, "error_code": "FORBIDDEN", "message": "حذف التعليقات غير مسموح"})


@router.get("/issues/{issue_id}/comments")
async def get_comments(
    issue_id: str,
    current_user: dict = Depends(get_current_user),
):
    issue = await _get_issue_or_404(issue_id)
    if not can_access_comments(current_user, issue):
        raise HTTPException(status_code=403, detail={"success": False, "error_code": "FORBIDDEN_COMMENTS", "message": "ليس لديك صلاحية الوصول للتعليقات"})

    comments = await gd_find(db.session, "issue_comments", {"issue_id": issue_id}, order_by="timestamp", desc_order=False, limit=200)

    return {"comments": comments, "total": len(comments)}


async def _get_allowed_mention_ids(current_user: dict) -> set:
    caller_email = (current_user.get("email") or "").lower()
    caller_is_main = is_main_admin(current_user)

    if caller_is_main:
        all_admins = await gd_find(db.session, "users", {"is_active": True, "role": {"$in": [
                "platform_admin", "platform_operations_manager",
                "platform_technical_admin", "platform_support_specialist",
            ]}},
            limit=200)
        ids = {u["id"] for u in all_admins if u.get("id")}
        own_id = get_user_id(current_user)
        ids.discard(own_id)
        return ids

    if is_platform_admin(current_user):
        main_users = await gd_find(db.session, "users", {"is_active": True, "email": {"$in": list(MAIN_ADMIN_EMAILS)}},
            limit=10)
        return {u["id"] for u in main_users if u.get("id")}

    return set()


async def _validate_mentions(mention_ids: list, current_user: dict):
    if not mention_ids:
        return
    allowed = await _get_allowed_mention_ids(current_user)
    for mid in mention_ids:
        if mid not in allowed:
            _hub_error(403, "UNAUTHORIZED_MENTION", "لا يُسمح لك بالإشارة إلى هذا المستخدم")


@router.get("/mentionable-users")
async def get_mentionable_users(
    current_user: dict = Depends(get_current_user),
):
    if not is_platform_admin(current_user):
        _hub_error(403, "FORBIDDEN", "غير مسموح")

    allowed_ids = await _get_allowed_mention_ids(current_user)
    if not allowed_ids:
        return {"users": []}

    users = await gd_find(db.session, "users", {"is_active": True, "id": {"$in": list(allowed_ids)}}, order_by="full_name", desc_order=False, limit=200)

    return {"users": [
        {"id": u.get("id", ""), "name": u.get("full_name", ""), "email": u.get("email", ""), "role": u.get("role", ""), "avatar": u.get("avatar_url")}
        for u in users if u.get("id")
    ]}


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
        "feedback_response": json.dumps({
            "resolved": data.resolved,
            "comment": data.comment,
            "responded_by": get_user_id(current_user),
            "responded_by_name": current_user.get("full_name", ""),
            "responded_at": now,
        }, ensure_ascii=False),
        "feedback_requested": False,
        "updated_at": now,
        "system.updated_at": now,
        "system.last_status_changed_at": now,
    }

    if not data.resolved:
        update_fields["resolved_at"] = None
        update_fields["sla_warning_emitted"] = False

    result = await gd_update_one(db.session, "product_issues", {"id": issue_id, "status": "done"}, update_fields)

    if result == 0:
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
    update_set = {
        "generated_prompt": prompt,
        "ai.generated_prompt": prompt,
        "updated_at": now,
        "system.updated_at": now,
    }

    current_status = issue.get("status", "new")
    if current_status != "in_progress":
        update_set["status"] = "in_progress"
        update_set["system.last_status_changed_at"] = now

    await gd_update_one(db.session, "product_issues", {"id": issue_id}, update_set)

    if current_status != "in_progress":
        await handle_status_changed(issue_id, current_user, current_status, "in_progress", "")
        await audit_status_changed(issue_id, current_user, current_status, "in_progress", "Auto: prompt generated")

    await handle_prompt_generated(issue_id, current_user)
    await audit_prompt_generated(issue_id, current_user)

    return {"success": True, "prompt": prompt, "issue_id": issue_id, "new_status": "in_progress"}


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


@router.delete("/issues/{issue_id}")
async def delete_issue(
    issue_id: str,
    current_user: dict = Depends(get_current_user),
):
    enforce_permission(current_user, HubAction.DELETE_ISSUE)

    issue = await _get_issue_or_404(issue_id)

    now = _now_iso()
    await gd_update_one(db.session, "product_issues", {"id": issue_id}, {"is_deleted": True, "deleted_at": now, "deleted_by": get_user_id(current_user)})
    logger.info(
        "[ProductHub] Issue %s deleted by %s",
        issue_id[:8], current_user.get("email", "unknown"),
    )
    try:
        await audit_issue_updated(issue_id, current_user, {"action": "delete_issue", "deleted_at": now})
    except Exception as exc:
        logger.warning("[ProductHub] audit_issue_updated failed (non-fatal) issue=%s err=%s", issue_id, exc)
    return {"success": True, "issue_id": issue_id}


UNDO_EXPIRY_MINUTES = 30
TRACKED_SNAPSHOT_FIELDS = ["status", "priority", "assigned_team", "is_deleted", "resolved_at", "feedback_requested", "title"]


async def _capture_before_states(issue_ids: list) -> dict:
    issues = await gd_find(db.session, "product_issues", {"id": {"$in": issue_ids}, "is_deleted": {"$ne": True}}, limit=200)
    return {iss["id"]: {k: iss.get(k) for k in TRACKED_SNAPSHOT_FIELDS} for iss in issues}


async def _resolve_performed_by(user: dict) -> Optional[str]:
    """Return a users.id that is guaranteed to exist in the DB, or None.

    get_user_id may return a value that is absent from users.id for certain
    platform-admin token shapes, which would fire a FK violation on
    bulk_action_history.performed_by → users.id.  We look up the row first
    and fall back to None (nullable FK with ondelete=SET NULL) rather than
    inserting an invalid reference.
    """
    raw_id = get_user_id(user)
    if not raw_id:
        return None
    try:
        row = await gd_find_one(db.session, "users", {"id": raw_id})
        return raw_id if row else None
    except Exception:
        return None


async def _save_action_history(action_type: str, user: dict, issue_ids: list, before_states: dict, after_state: dict) -> Optional[str]:
    performed_by = await _resolve_performed_by(user)
    record = {
        "action_type": action_type,
        "performed_by": performed_by,
        "performed_by_name": user.get("full_name", user.get("email", "unknown")),
        "issue_ids": issue_ids,
        "old_values": before_states,
        "is_undone": False,
    }
    try:
        inserted_id = await gd_insert(db.session, "bulk_action_history", record)
        return inserted_id
    except Exception as exc:
        logger.warning(
            "[ProductHub] _save_action_history failed (non-fatal) action=%s user=%s err=%s",
            action_type, user.get("email", "unknown"), exc,
        )
        return None


@router.post("/issues/bulk-update")
async def bulk_update_issues(
    data: BulkUpdateRequest,
    current_user: dict = Depends(get_current_user),
):
    if not is_main_admin(current_user):
        _hub_error(403, "FORBIDDEN", "هذه العملية متاحة فقط للمسؤولين الرئيسيين")

    if not data.status and not data.priority and not data.assigned_team:
        _hub_error(422, "NO_CHANGES", "يجب تحديد حقل واحد على الأقل للتعديل")

    valid_statuses = {e.value for e in IssueStatus}
    valid_priorities = {e.value for e in IssuePriority}
    if data.status and data.status not in valid_statuses:
        _hub_error(422, "INVALID_STATUS", f"حالة غير صالحة: {data.status}", {"valid": sorted(valid_statuses)})
    if data.priority and data.priority not in valid_priorities:
        _hub_error(422, "INVALID_PRIORITY", f"أولوية غير صالحة: {data.priority}", {"valid": sorted(valid_priorities)})

    existing_ids = set(await gd_distinct(db.session, "product_issues", "id", {"id": {"$in": data.issue_ids}, "is_deleted": {"$ne": True}}))
    missing_ids = [iid for iid in data.issue_ids if iid not in existing_ids]
    if missing_ids:
        _hub_error(422, "ISSUES_NOT_FOUND", f"تحديات غير موجودة أو محذوفة: {len(missing_ids)} من أصل {len(data.issue_ids)}", {"missing_ids": missing_ids[:20]})

    before_states = await _capture_before_states(data.issue_ids)

    now = _now_iso()
    update_fields = {"updated_at": now, "system.updated_at": now}
    after_snapshot = {}

    if data.status:
        update_fields["status"] = data.status
        update_fields["system.last_status_changed_at"] = now
        after_snapshot["status"] = data.status
        if data.status == "done":
            update_fields["resolved_at"] = now
            update_fields["feedback_requested"] = True
            after_snapshot["resolved_at"] = now
            after_snapshot["feedback_requested"] = True
    if data.priority:
        update_fields["priority"] = data.priority
        after_snapshot["priority"] = data.priority
    if data.assigned_team:
        update_fields["assigned_team"] = data.assigned_team
        after_snapshot["assigned_team"] = data.assigned_team

    result = await gd_update_many(db.session, "product_issues", {"id": {"$in": data.issue_ids}, "is_deleted": {"$ne": True}}, update_fields)

    action_id = await _save_action_history("bulk_edit", current_user, data.issue_ids, before_states, after_snapshot)

    for issue_id in data.issue_ids:
        changes_log = {}
        if data.status:
            changes_log["status"] = data.status
        if data.priority:
            changes_log["priority"] = data.priority
        if data.assigned_team:
            changes_log["assigned_team"] = data.assigned_team
        try:
            await audit_issue_updated(issue_id, current_user, {"action": "bulk_update", **changes_log})
        except Exception as exc:
            logger.warning("[ProductHub] audit_issue_updated failed (non-fatal) issue=%s err=%s", issue_id, exc)

    logger.info(
        "[ProductHub] Bulk update %d/%d issues by %s",
        result, len(data.issue_ids), current_user.get("email", "unknown"),
    )
    return {
        "success": True,
        "modified_count": result,
        "requested_count": len(data.issue_ids),
        "action_id": action_id,
    }


@router.post("/issues/bulk-delete")
async def bulk_delete_issues(
    data: BulkDeleteRequest,
    current_user: dict = Depends(get_current_user),
):
    if not is_main_admin(current_user):
        _hub_error(403, "FORBIDDEN", "هذه العملية متاحة فقط للمسؤولين الرئيسيين")

    before_states = await _capture_before_states(data.issue_ids)

    now = _now_iso()
    result = await gd_update_many(db.session, "product_issues", {"id": {"$in": data.issue_ids}, "is_deleted": {"$ne": True}}, {"is_deleted": True, "deleted_at": now, "deleted_by": get_user_id(current_user)})

    logger.info(
        "[ProductHub] Bulk delete %d/%d issues by %s ids=%s",
        result, len(data.issue_ids), current_user.get("email", "unknown"), data.issue_ids,
    )

    action_id = await _save_action_history("bulk_delete", current_user, data.issue_ids, before_states, {"is_deleted": True})

    for issue_id in data.issue_ids:
        try:
            await audit_issue_updated(issue_id, current_user, {"action": "bulk_delete", "deleted_at": now})
        except Exception as exc:
            logger.warning("[ProductHub] audit_issue_updated failed (non-fatal) issue=%s err=%s", issue_id, exc)

    return {
        "success": True,
        "deleted_count": result,
        "requested_count": len(data.issue_ids),
        "action_id": action_id,
    }


@router.get("/action-history")
async def get_action_history(
    current_user: dict = Depends(get_current_user),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    if not is_main_admin(current_user):
        _hub_error(403, "FORBIDDEN", "هذه العملية متاحة فقط للمسؤولين الرئيسيين")

    now = datetime.now(timezone.utc).isoformat()

    records = await gd_find(db.session, "bulk_action_history", {}, order_by="timestamp", desc_order=True, offset=offset, limit=limit)

    total = await gd_count(db.session, "bulk_action_history", {})

    for r in records:
        if r.get("status") == "active" and r.get("is_undoable"):
            if r.get("undo_expiry", "") < now:
                r["is_undoable"] = False
                r["status"] = "expired"

    return {
        "success": True,
        "records": records,
        "total": total,
    }


@router.post("/action-history/{action_id}/undo")
async def undo_action(
    action_id: str,
    current_user: dict = Depends(get_current_user),
):
    if not is_main_admin(current_user):
        _hub_error(403, "FORBIDDEN", "هذه العملية متاحة فقط للمسؤولين الرئيسيين")

    record = await gd_find_one(db.session, "bulk_action_history", {"id": action_id})
    if not record:
        _hub_error(404, "NOT_FOUND", "العملية غير موجودة")

    if record.get("is_undone"):
        _hub_error(400, "NOT_UNDOABLE", "تم التراجع عن هذه العملية مسبقاً")

    now_dt = datetime.now(timezone.utc)

    before_states = record.get("old_values", {})
    action_type = record.get("action_type", "")
    restored_count = 0
    now = _now_iso()

    if action_type == "bulk_delete":
        for issue_id, prev in before_states.items():
            res = await gd_update_one(db.session, "product_issues", {"id": issue_id}, {"is_deleted": False, "deleted_at": None, "deleted_by": None, "updated_at": now})
            if res > 0:
                restored_count += 1
            await audit_issue_updated(issue_id, current_user, {"action": "undo_bulk_delete"})

    elif action_type == "bulk_edit":
        for issue_id, prev in before_states.items():
            restore_fields = {k: v for k, v in prev.items() if v is not None}
            restore_fields["updated_at"] = now
            res = await gd_update_one(db.session, "product_issues", {"id": issue_id, "is_deleted": {"$ne": True}}, restore_fields)
            if res > 0:
                restored_count += 1
            await audit_issue_updated(issue_id, current_user, {"action": "undo_bulk_edit", "restored_fields": list(restore_fields.keys())})

    else:
        _hub_error(400, "UNSUPPORTED", f"نوع العملية غير مدعوم للتراجع: {action_type}")

    await gd_update_one(db.session, "bulk_action_history", {"id": action_id}, {
            "is_undone": True,
            "undone_at": now,
        })

    logger.info(f"[ProductHub] Undo {action_type} ({action_id[:8]}): restored {restored_count} issues by {current_user.get('email', 'unknown')}")
    return {
        "success": True,
        "action_id": action_id,
        "restored_count": restored_count,
        "action_type": action_type,
    }


@router.post("/issues/{issue_id}/reanalyze")
async def reanalyze_issue(
    issue_id: str,
    current_user: dict = Depends(get_current_user),
):
    enforce_permission(current_user, HubAction.REANALYZE_ISSUE)
    issue = await _get_issue_or_404(issue_id)
    hakim_analysis = await _run_hakim_analysis(issue)
    await gd_update_one(db.session, "product_issues", {"id": issue_id}, {"hakim_analysis": hakim_analysis, "updated_at": _now_iso()})
    await handle_hakim_analysis(issue_id, current_user, hakim_analysis, source="manual_reanalyze")
    await audit_ai_analyzed(issue_id, current_user, hakim_analysis)
    return {
        "success": True,
        "issue_id": issue_id,
        "hakim_analysis": hakim_analysis,
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

    duplicates = await gd_find(db.session, "issue_duplicates_map", {"$or": [{"issue_id": issue_id}, {"duplicate_of": issue_id}]}, limit=50)

    return {"duplicates": duplicates, "total": len(duplicates), "issue_id": issue_id}


@router.post("/issues/resequence")
async def resequence_issue_numbers(current_user: dict = Depends(get_current_user)):
    if not is_main_admin(current_user):
        raise HTTPException(status_code=403, detail="Main admin only")
    issues = await gd_find(db.session, "product_issues", {"is_deleted": {"$ne": True}}, order_by="created_at", desc_order=False, limit=10000)
    updates = []
    for idx, issue in enumerate(issues, start=1):
        if issue.get("issue_number") != idx:
            updates.append({"id": issue["id"], "old": issue.get("issue_number"), "new": idx})
            await gd_update_one(db.session, "product_issues", {"id": issue["id"]}, {"issue_number": idx})
    from db import engine as _engine
    from sqlalchemy import text
    async with _engine.connect() as conn:
        await conn.execute(text("SELECT setval('product_issue_number_seq', :val)"), {"val": len(issues)})
        await conn.commit()
    return {"resequenced": len(updates), "total_active": len(issues), "changes": updates}


@router.get("/dashboard")
async def get_dashboard(current_user: dict = Depends(get_current_user)):
    enforce_permission(current_user, HubAction.VIEW_FULL_ANALYTICS)

    now = datetime.now(timezone.utc)
    week_ago = (now - timedelta(days=7)).isoformat()

    active_filter = {"$match": {"is_deleted": {"$ne": True}}}

    pipeline_status = [
        active_filter,
        {"$group": {"_id": "$status", "count": {"$sum": 1}}}
    ]
    status_counts_raw = await _gd_aggregate(db.session, "product_issues", pipeline_status)
    status_counts = {s["_id"]: s["count"] for s in status_counts_raw}

    total = sum(status_counts.values())
    total_open = sum(status_counts.get(s, 0) for s in OPEN_STATUSES)

    pipeline_type = [active_filter, {"$group": {"_id": "$issue_type", "count": {"$sum": 1}}}]
    type_counts_raw = await _gd_aggregate(db.session, "product_issues", pipeline_type)
    by_type = [{"type": t["_id"], "label": ISSUE_TYPE_LABELS.get(t["_id"], t["_id"]), "count": t["count"]} for t in type_counts_raw]

    pipeline_priority = [active_filter, {"$group": {"_id": "$priority", "count": {"$sum": 1}}}]
    priority_counts_raw = await _gd_aggregate(db.session, "product_issues", pipeline_priority)
    by_priority = [{"priority": p["_id"], "label": PRIORITY_LABELS.get(p["_id"], p["_id"] or ""), "count": p["count"]} for p in priority_counts_raw]

    pipeline_team = [
        {"$match": {"assigned_team": {"$ne": None}, "is_deleted": {"$ne": True}}},
        {"$group": {"_id": "$assigned_team", "count": {"$sum": 1}}}
    ]
    team_counts_raw = await _gd_aggregate(db.session, "product_issues", pipeline_team)
    by_team = [{"team": t["_id"], "count": t["count"]} for t in team_counts_raw]

    new_this_week = await gd_count(db.session, "product_issues", {"created_at": {"$gte": week_ago}, "is_deleted": {"$ne": True}})
    critical_open = await gd_count(db.session, "product_issues", {"priority": "critical", "status": {"$in": list(OPEN_STATUSES)}, "is_deleted": {"$ne": True}})
    sla_exceeded = await gd_count(db.session, "product_issues", {
        "sla_deadline": {"$lte": now.isoformat()},
        "status": {"$in": list(OPEN_STATUSES)},
        "is_deleted": {"$ne": True},
    })

    resolved = await gd_find(db.session, "product_issues", {"resolved_at": {"$ne": None}, "is_deleted": {"$ne": True}}, limit=500)
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
        active_filter,
        {"$group": {"_id": "$section", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 10}
    ]
    top_sections = await _gd_aggregate(db.session, "product_issues", pipeline_section)

    dup_count = await gd_count(db.session, "issue_duplicates_map", {})

    pipeline_contributors = [
        active_filter,
        {"$group": {"_id": {"name": "$employee_name", "user_id": "$created_by"}, "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 10}
    ]
    contributors_raw = await _gd_aggregate(db.session, "product_issues", pipeline_contributors)
    top_contributors = [{"name": c["_id"]["name"], "count": c["count"]} for c in contributors_raw]

    pipeline_accuracy = [
        {"$match": {"status": {"$in": ["done", "user_feedback_confirmed", "rejected"]}, "is_deleted": {"$ne": True}}},
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
    accuracy_raw = await _gd_aggregate(db.session, "product_issues", pipeline_accuracy)
    most_accurate = [
        {"name": a["name"], "total": a["total"], "valid": a["valid"],
         "accuracy": round(a.get("accuracy", 0), 1)}
        for a in accuracy_raw if a.get("total", 0) >= 2
    ]

    pipeline_dept = [
        active_filter,
        {"$group": {"_id": "$account_type", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 10}
    ]
    dept_raw = await _gd_aggregate(db.session, "product_issues", pipeline_dept)
    by_department = [{"department": d["_id"], "count": d["count"]} for d in dept_raw]

    hakim_analyzed = await gd_count(db.session, "product_issues", {"hakim_analysis": {"$exists": True, "$ne": {}}, "is_deleted": {"$ne": True}})
    hakim_priority_changed = await gd_count(db.session, "product_issues", {
        "hakim_analysis.suggested_priority": {"$exists": True},
        "$expr": {"$ne": ["$priority", "$hakim_analysis.suggested_priority"]},
        "is_deleted": {"$ne": True},
    })
    pipeline_hakim_teams = [
        {"$match": {"hakim_analysis.suggested_team": {"$exists": True, "$ne": None}, "is_deleted": {"$ne": True}}},
        {"$group": {"_id": "$hakim_analysis.suggested_team", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 5}
    ]
    hakim_teams_raw = await _gd_aggregate(db.session, "product_issues", pipeline_hakim_teams)
    hakim_top_teams = [{"team": t["_id"], "count": t["count"]} for t in hakim_teams_raw]

    recent_hakim = await gd_find(db.session, "product_issues", {"hakim_analysis.impact_assessment": {"$exists": True, "$ne": ""}, "is_deleted": {"$ne": True}}, order_by="created_at", desc_order=True, limit=5)
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

    resolved_statuses = {"done", "user_feedback_confirmed"}
    total_resolved = sum(status_counts.get(s, 0) for s in resolved_statuses)
    total_rejected = status_counts.get("rejected", 0)
    under_review = status_counts.get("under_review", 0)
    qa_validation = status_counts.get("qa_validation", 0)
    new_count = status_counts.get("new", 0)
    resolution_rate = round((total_resolved / max(1, total)) * 100, 1)

    return {
        "total_issues": total,
        "total_open": total_open,
        "total_resolved": total_resolved,
        "total_rejected": total_rejected,
        "resolution_rate": resolution_rate,
        "new_count": new_count,
        "under_review": under_review,
        "qa_validation": qa_validation,
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
    await gd_update_one(db.session, "product_issues", {"id": issue_id}, {"title": title, "updated_at": now, "system.updated_at": now})
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

    await gd_update_one(db.session, "product_issues", {"id": issue_id}, update_fields)
    changes = {"priority": {"from": old_priority, "to": priority}}
    await handle_issue_updated(issue_id, current_user, changes)
    await audit_issue_updated(issue_id, current_user, changes)

    return {"success": True}


@router.post("/hakim-generate-expected")
async def hakim_generate_expected(
    data: dict = Body(...),
    current_user: dict = Depends(get_current_user),
):
    title = (data.get("title") or "").strip()
    current_behavior = (data.get("current_behavior") or "").strip()
    issue_type = (data.get("issue_type") or "").strip()
    page = (data.get("page") or "").strip()

    if not current_behavior or len(current_behavior) < 10:
        _hub_error(422, "CURRENT_BEHAVIOR_TOO_SHORT", "يجب وصف الوضع الحالي أولاً (10 أحرف على الأقل)")

    try:
        from openai import OpenAI
        import os
        api_key = os.environ.get("AI_INTEGRATIONS_OPENAI_API_KEY", "")
        base_url = os.environ.get("AI_INTEGRATIONS_OPENAI_BASE_URL", "")
        if not api_key:
            return {"generated_text": "", "success": False}

        client = OpenAI(api_key=api_key, base_url=base_url if base_url else None)

        context_parts = []
        if title:
            context_parts.append(f"عنوان التحدي: {title}")
        if issue_type:
            type_label = ISSUE_TYPE_LABELS.get(issue_type, issue_type)
            context_parts.append(f"نوع التحدي: {type_label}")
        if page:
            context_parts.append(f"الصفحة: {page}")
        context_parts.append(f"الوضع الحالي: {current_behavior}")

        context = "\n".join(context_parts)

        response = client.chat.completions.create(
            model="gpt-5-mini",
            messages=[
                {"role": "system", "content": """أنت حكيم، مساعد ذكاء المنتج في نظام نَسَّق التعليمي.
مهمتك: بناءً على وصف الوضع الحالي والمشكلة، اكتب وصفاً واضحاً ودقيقاً للوضع المتوقع (النتيجة المرجوة).

قواعد:
- صِغ النتيجة المتوقعة كخطوات واضحة وقابلة للتنفيذ
- استخدم صيغة "يجب أن..." أو "المتوقع أن..."
- كن محدداً وعملياً — لا تكتب عبارات عامة
- اكتب بالعربية بأسلوب تقني مهني
- اجعل الوصف بين 2-4 جمل
- لا تكرر وصف المشكلة — ركز على الحل المطلوب
- أرجع النص المولّد فقط بدون مقدمات أو شرح"""},
                {"role": "user", "content": context}
            ],
            max_completion_tokens=400,
            reasoning_effort="minimal",
        )

        generated = response.choices[0].message.content.strip()
        return {"generated_text": generated, "success": True}
    except Exception as e:
        logger.warning(f"[Hakim] Expected behavior generation failed: {e}")
        return {"generated_text": "", "success": False}


@router.post("/hakim-generate-title")
async def hakim_generate_title(
    data: dict = Body(...),
    current_user: dict = Depends(get_current_user),
):
    current_behavior = (data.get("current_behavior") or "").strip()[:5000]
    expected_behavior = (data.get("expected_behavior") or "").strip()[:5000]
    additional_info = (data.get("additional_info") or "").strip()[:2000]
    issue_type = (data.get("issue_type") or "").strip()[:100]
    page = (data.get("page") or "").strip()[:200]

    if not current_behavior or len(current_behavior) < 10:
        _hub_error(422, "INSUFFICIENT_DATA", "يرجى استكمال الوضع الحالي والوضع المتوقع لإنشاء عنوان دقيق")
    if not expected_behavior or len(expected_behavior) < 10:
        _hub_error(422, "INSUFFICIENT_DATA", "يرجى استكمال الوضع الحالي والوضع المتوقع لإنشاء عنوان دقيق")

    try:
        from openai import OpenAI
        import os, json as _json
        api_key = os.environ.get("AI_INTEGRATIONS_OPENAI_API_KEY", "")
        base_url = os.environ.get("AI_INTEGRATIONS_OPENAI_BASE_URL", "")
        if not api_key:
            return {"titles": [], "success": False}

        client = OpenAI(api_key=api_key, base_url=base_url if base_url else None)

        context_parts = []
        if issue_type:
            type_label = ISSUE_TYPE_LABELS.get(issue_type, issue_type)
            context_parts.append(f"نوع التحدي: {type_label}")
        if page:
            context_parts.append(f"الصفحة: {page}")
        context_parts.append(f"الوضع الحالي: {current_behavior}")
        context_parts.append(f"الوضع المتوقع: {expected_behavior}")
        if additional_info:
            context_parts.append(f"معلومات إضافية: {additional_info}")

        context = "\n".join(context_parts)

        response = client.chat.completions.create(
            model="gpt-5-mini",
            messages=[
                {"role": "system", "content": """أنت حكيم، مساعد ذكاء المنتج في نظام نَسَّق التعليمي.
مهمتك: بناءً على تفاصيل التحدي، أنشئ 3 عناوين احترافية مختلفة.

قواعد صارمة للعنوان:
- قصير ومركز: من 3 إلى 5 كلمات فقط
- واضح وسهل الفهم بدون غموض
- يعكس القيمة أو الهدف وليس المشكلة فقط
- استخدم لغة إيجابية وبنّاءة
- لا تستخدم كلمات سلبية مثل: "مشكلة"، "خطأ"، "فشل"، "عطل"، "خلل"
- استخدم تعبيرات مثل: "تحسين تجربة..."، "تطوير أداء..."، "تحسين..."، "فرصة تحسين..."
- اكتب بالعربية فقط
- قابل للعرض في كارت بدون قص

أرجع النتيجة كـ JSON array فقط بدون أي نص إضافي:
["عنوان 1", "عنوان 2", "عنوان 3"]"""},
                {"role": "user", "content": context}
            ],
            max_completion_tokens=400,
            reasoning_effort="minimal",
        )

        raw = response.choices[0].message.content.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        titles = _json.loads(raw)
        if not isinstance(titles, list):
            titles = [str(titles)]
        titles = [t.strip() for t in titles if isinstance(t, str) and t.strip()][:3]
        return {"titles": titles, "success": True}
    except Exception as e:
        logger.warning(f"[Hakim] Title generation failed: {e}")
        return {"titles": [], "success": False}


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
            "title": "إعادة صياغة عنوان التحدي ليكون مختصراً وواضحاً ودقيقاً، بحد أقصى جملة واحدة قصيرة تصف المشكلة أو الطلب",
            "current_behavior": "تحسين وصف الوضع الحالي/المشكلة ليكون أوضح وأكثر تحديداً تقنياً",
            "expected_behavior": "تحسين وصف الوضع المتوقع/الحل المطلوب ليكون أوضح وقابلاً للتنفيذ",
            "additional_info": "تحسين المعلومات الإضافية لتكون أكثر فائدة للفريق التقني",
        }
        field_instruction = field_prompts.get(field_type, "تحسين النص ليكون أوضح وأكثر تحديداً")

        response = client.chat.completions.create(
            model="gpt-5-mini",
            messages=[
                {"role": "system", "content": f"""أنت حكيم، مساعد ذكاء المنتج في نظام نَسَّق. مهمتك: {field_instruction}.

قواعد:
- حافظ على المعنى الأصلي
- اجعل النص أوضح وأكثر تنظيماً
- أضف تفاصيل تقنية إن أمكن
- اكتب بالعربية
- لا تضف معلومات من عندك
- أرجع النص المحسّن فقط بدون مقدمات"""},
                {"role": "user", "content": text}
            ],
            max_completion_tokens=500,
            reasoning_effort="minimal",
        )

        improved = response.choices[0].message.content.strip()
        return {"improved_text": improved, "original_text": text}
    except Exception as e:
        logger.warning(f"[Hakim] Text improvement failed: {e}")
        return {"improved_text": text, "original_text": text}
