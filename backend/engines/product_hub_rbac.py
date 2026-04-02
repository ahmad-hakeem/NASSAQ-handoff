"""
Product Intelligence Hub — RBAC Middleware
نظام الصلاحيات لمركز ذكاء المنتج

Enforces governance rules at backend level:
- Action-based permission matrix
- Resource ownership validation
- Permission denial audit logging
- Structured error responses
"""

from enum import Enum
from typing import Optional
from fastapi import HTTPException, Depends
from dependencies import get_current_user
import logging

logger = logging.getLogger("nassaq.product_hub.rbac")

MAIN_ADMIN_EMAILS = {"zalat@nassaqapp.com", "hakim@nassaqapp.com"}
SUPER_ADMIN_EMAIL = "zalat@nassaqapp.com"


def _get_email(user: dict) -> str:
    return (user.get("email") or "").lower().strip()


def is_main_admin(user: dict) -> bool:
    return _get_email(user) in MAIN_ADMIN_EMAILS


def is_super_admin(user: dict) -> bool:
    return _get_email(user) == SUPER_ADMIN_EMAIL


class HubAction(str, Enum):
    CREATE_ISSUE = "create_issue"
    VIEW_OWN_ISSUE = "view_own_issue"
    VIEW_ANY_ISSUE = "view_any_issue"
    LIST_OWN_ISSUES = "list_own_issues"
    LIST_ALL_ISSUES = "list_all_issues"
    UPDATE_ISSUE = "update_issue"
    DELETE_ISSUE = "delete_issue"
    ASSIGN_ISSUE = "assign_issue"
    CHANGE_STATUS = "change_status"
    SET_FINAL_STATUS = "set_final_status"
    REOPEN_ISSUE = "reopen_issue"
    VIEW_PROMPT = "view_prompt"
    COPY_PROMPT = "copy_prompt"
    GENERATE_PROMPT = "generate_prompt"
    REANALYZE_ISSUE = "reanalyze_issue"
    VIEW_HAKIM_INSIGHTS = "view_hakim_insights"
    VIEW_FULL_ANALYTICS = "view_full_analytics"
    ADD_COMMENT = "add_comment"
    VIEW_COMMENTS = "view_comments"
    SUBMIT_FEEDBACK = "submit_feedback"
    VIEW_ACTIVITY_LOG = "view_activity_log"
    VIEW_DUPLICATES = "view_duplicates"
    MANAGE_ATTACHMENTS = "manage_attachments"
    UPDATE_TITLE = "update_title"
    UPDATE_PRIORITY = "update_priority"
    APPROVE_CLOSURE = "approve_closure"


class HubRole(str, Enum):
    PLATFORM_ADMIN = "platform_admin"
    INTERNAL_USER = "internal_user"


PERMISSION_MATRIX = {
    HubAction.CREATE_ISSUE:       {HubRole.INTERNAL_USER: True,  HubRole.PLATFORM_ADMIN: True},
    HubAction.VIEW_OWN_ISSUE:     {HubRole.INTERNAL_USER: True,  HubRole.PLATFORM_ADMIN: True},
    HubAction.VIEW_ANY_ISSUE:     {HubRole.INTERNAL_USER: False, HubRole.PLATFORM_ADMIN: True},
    HubAction.LIST_OWN_ISSUES:    {HubRole.INTERNAL_USER: True,  HubRole.PLATFORM_ADMIN: True},
    HubAction.LIST_ALL_ISSUES:    {HubRole.INTERNAL_USER: False, HubRole.PLATFORM_ADMIN: True},
    HubAction.UPDATE_ISSUE:       {HubRole.INTERNAL_USER: False, HubRole.PLATFORM_ADMIN: True},
    HubAction.DELETE_ISSUE:       {HubRole.INTERNAL_USER: False, HubRole.PLATFORM_ADMIN: True},
    HubAction.ASSIGN_ISSUE:       {HubRole.INTERNAL_USER: False, HubRole.PLATFORM_ADMIN: True},
    HubAction.CHANGE_STATUS:      {HubRole.INTERNAL_USER: False, HubRole.PLATFORM_ADMIN: True},
    HubAction.SET_FINAL_STATUS:   {HubRole.INTERNAL_USER: False, HubRole.PLATFORM_ADMIN: True},
    HubAction.REOPEN_ISSUE:       {HubRole.INTERNAL_USER: False, HubRole.PLATFORM_ADMIN: True},
    HubAction.VIEW_PROMPT:        {HubRole.INTERNAL_USER: False, HubRole.PLATFORM_ADMIN: True},
    HubAction.COPY_PROMPT:        {HubRole.INTERNAL_USER: False, HubRole.PLATFORM_ADMIN: True},
    HubAction.GENERATE_PROMPT:    {HubRole.INTERNAL_USER: False, HubRole.PLATFORM_ADMIN: True},
    HubAction.REANALYZE_ISSUE:    {HubRole.INTERNAL_USER: False, HubRole.PLATFORM_ADMIN: True},
    HubAction.VIEW_HAKIM_INSIGHTS:{HubRole.INTERNAL_USER: False, HubRole.PLATFORM_ADMIN: True},
    HubAction.VIEW_FULL_ANALYTICS:{HubRole.INTERNAL_USER: False, HubRole.PLATFORM_ADMIN: True},
    HubAction.ADD_COMMENT:        {HubRole.INTERNAL_USER: True,  HubRole.PLATFORM_ADMIN: True},
    HubAction.VIEW_COMMENTS:      {HubRole.INTERNAL_USER: True,  HubRole.PLATFORM_ADMIN: True},
    HubAction.SUBMIT_FEEDBACK:    {HubRole.INTERNAL_USER: True,  HubRole.PLATFORM_ADMIN: True},
    HubAction.VIEW_ACTIVITY_LOG:  {HubRole.INTERNAL_USER: True,  HubRole.PLATFORM_ADMIN: True},
    HubAction.VIEW_DUPLICATES:    {HubRole.INTERNAL_USER: False, HubRole.PLATFORM_ADMIN: True},
    HubAction.MANAGE_ATTACHMENTS: {HubRole.INTERNAL_USER: True,  HubRole.PLATFORM_ADMIN: True},
    HubAction.UPDATE_TITLE:       {HubRole.INTERNAL_USER: False, HubRole.PLATFORM_ADMIN: True},
    HubAction.UPDATE_PRIORITY:    {HubRole.INTERNAL_USER: False, HubRole.PLATFORM_ADMIN: True},
    HubAction.APPROVE_CLOSURE:    {HubRole.INTERNAL_USER: False, HubRole.PLATFORM_ADMIN: True},
}

FORBIDDEN_SUPER_ADMIN_MSG = "This action is restricted to the authorized super-admin accounts only."

ERROR_MESSAGES = {
    HubAction.ASSIGN_ISSUE:       FORBIDDEN_SUPER_ADMIN_MSG,
    HubAction.CHANGE_STATUS:      FORBIDDEN_SUPER_ADMIN_MSG,
    HubAction.SET_FINAL_STATUS:   FORBIDDEN_SUPER_ADMIN_MSG,
    HubAction.VIEW_PROMPT:        FORBIDDEN_SUPER_ADMIN_MSG,
    HubAction.COPY_PROMPT:        FORBIDDEN_SUPER_ADMIN_MSG,
    HubAction.GENERATE_PROMPT:    FORBIDDEN_SUPER_ADMIN_MSG,
    HubAction.REANALYZE_ISSUE:    FORBIDDEN_SUPER_ADMIN_MSG,
    HubAction.VIEW_HAKIM_INSIGHTS:FORBIDDEN_SUPER_ADMIN_MSG,
    HubAction.VIEW_FULL_ANALYTICS:FORBIDDEN_SUPER_ADMIN_MSG,
    HubAction.UPDATE_TITLE:       FORBIDDEN_SUPER_ADMIN_MSG,
    HubAction.UPDATE_PRIORITY:    FORBIDDEN_SUPER_ADMIN_MSG,
    HubAction.APPROVE_CLOSURE:    FORBIDDEN_SUPER_ADMIN_MSG,
    HubAction.REOPEN_ISSUE:       FORBIDDEN_SUPER_ADMIN_MSG,
    HubAction.UPDATE_ISSUE:       FORBIDDEN_SUPER_ADMIN_MSG,
    HubAction.DELETE_ISSUE:       FORBIDDEN_SUPER_ADMIN_MSG,
    HubAction.VIEW_ANY_ISSUE:     "ليس لديك صلاحية لعرض هذا التعليق",
    HubAction.VIEW_DUPLICATES:    FORBIDDEN_SUPER_ADMIN_MSG,
}

ERROR_CODES = {
    HubAction.ASSIGN_ISSUE:       "FORBIDDEN_SUPER_ADMIN_ACTION",
    HubAction.CHANGE_STATUS:      "FORBIDDEN_SUPER_ADMIN_ACTION",
    HubAction.SET_FINAL_STATUS:   "FORBIDDEN_SUPER_ADMIN_ACTION",
    HubAction.VIEW_PROMPT:        "FORBIDDEN_SUPER_ADMIN_ACTION",
    HubAction.COPY_PROMPT:        "FORBIDDEN_SUPER_ADMIN_ACTION",
    HubAction.GENERATE_PROMPT:    "FORBIDDEN_SUPER_ADMIN_ACTION",
    HubAction.REANALYZE_ISSUE:    "FORBIDDEN_SUPER_ADMIN_ACTION",
    HubAction.VIEW_HAKIM_INSIGHTS:"FORBIDDEN_SUPER_ADMIN_ACTION",
    HubAction.VIEW_FULL_ANALYTICS:"FORBIDDEN_SUPER_ADMIN_ACTION",
    HubAction.UPDATE_TITLE:       "FORBIDDEN_SUPER_ADMIN_ACTION",
    HubAction.UPDATE_PRIORITY:    "FORBIDDEN_SUPER_ADMIN_ACTION",
    HubAction.APPROVE_CLOSURE:    "FORBIDDEN_SUPER_ADMIN_ACTION",
    HubAction.REOPEN_ISSUE:       "FORBIDDEN_SUPER_ADMIN_ACTION",
    HubAction.UPDATE_ISSUE:       "FORBIDDEN_SUPER_ADMIN_ACTION",
    HubAction.DELETE_ISSUE:       "FORBIDDEN_SUPER_ADMIN_ACTION",
    HubAction.VIEW_ANY_ISSUE:     "FORBIDDEN_VIEW",
    HubAction.VIEW_DUPLICATES:    "FORBIDDEN_SUPER_ADMIN_ACTION",
}


def resolve_hub_role(user: dict) -> HubRole:
    if user.get("role") == "platform_admin":
        return HubRole.PLATFORM_ADMIN
    return HubRole.INTERNAL_USER


def is_platform_admin(user: dict) -> bool:
    return resolve_hub_role(user) == HubRole.PLATFORM_ADMIN


def check_permission(user: dict, action: HubAction) -> bool:
    role = resolve_hub_role(user)
    return PERMISSION_MATRIX.get(action, {}).get(role, False)


MAIN_ADMIN_ONLY_ACTIONS = {
    HubAction.DELETE_ISSUE,
    HubAction.UPDATE_ISSUE,
    HubAction.ASSIGN_ISSUE,
    HubAction.CHANGE_STATUS,
    HubAction.SET_FINAL_STATUS,
    HubAction.REOPEN_ISSUE,
    HubAction.APPROVE_CLOSURE,
    HubAction.UPDATE_TITLE,
    HubAction.UPDATE_PRIORITY,
    HubAction.VIEW_PROMPT,
    HubAction.COPY_PROMPT,
    HubAction.GENERATE_PROMPT,
    HubAction.REANALYZE_ISSUE,
    HubAction.VIEW_HAKIM_INSIGHTS,
    HubAction.VIEW_FULL_ANALYTICS,
    HubAction.VIEW_DUPLICATES,
}


def enforce_permission(user: dict, action: HubAction):
    if not check_permission(user, action):
        _deny(user, action)

    if action in MAIN_ADMIN_ONLY_ACTIONS:
        if not is_main_admin(user):
            _deny(user, action)


def _deny(user: dict, action: HubAction, custom_message: str = None):
    user_id = user.get("id", user.get("user_id", "unknown"))
    logger.warning(
        f"[RBAC] Permission denied: user={user_id} email={_get_email(user)} action={action.value}"
    )
    raise HTTPException(
        status_code=403,
        detail={
            "success": False,
            "error_code": ERROR_CODES.get(action, "FORBIDDEN_ACTION"),
            "message": custom_message or ERROR_MESSAGES.get(action, "ليس لديك صلاحية لتنفيذ هذا الإجراء"),
            "details": {"action": action.value},
        }
    )


def check_resource_ownership(user: dict, issue: dict) -> bool:
    if is_platform_admin(user):
        return True
    user_id = user.get("id", user.get("user_id", ""))
    return issue.get("created_by") == user_id


def can_access_comments(user: dict, issue: dict) -> bool:
    if is_platform_admin(user):
        return True
    if is_main_admin(user):
        return True
    user_id = user.get("id", user.get("user_id", ""))
    return issue.get("created_by") == user_id


def enforce_ownership_or_admin(user: dict, issue: dict, action: HubAction):
    if not check_resource_ownership(user, issue):
        user_id = user.get("id", user.get("user_id", "unknown"))
        logger.warning(
            f"[RBAC] Ownership denied: user={user_id} action={action.value} issue={issue.get('id','')[:8]}"
        )
        raise HTTPException(
            status_code=403,
            detail={
                "success": False,
                "error_code": "FORBIDDEN_NOT_OWNER",
                "message": ERROR_MESSAGES.get(action, "ليس لديك صلاحية لتنفيذ هذا الإجراء على هذه المشكلة"),
                "details": {"action": action.value},
            }
        )


def require_hub_action(action: HubAction):
    async def dependency(current_user: dict = Depends(get_current_user)):
        enforce_permission(current_user, action)
        return current_user
    return dependency


def get_user_id(user: dict) -> str:
    return user.get("id", user.get("user_id", ""))


ADMIN_REDACTED_FIELDS = {"generated_prompt", "hakim_analysis"}


def redact_issue_for_role(issue: dict, user: dict) -> dict:
    if is_main_admin(user):
        return issue
    for field in ADMIN_REDACTED_FIELDS:
        issue.pop(field, None)
    return issue
