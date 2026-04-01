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
    ASSIGN_ISSUE = "assign_issue"
    CHANGE_STATUS = "change_status"
    SET_FINAL_STATUS = "set_final_status"
    REOPEN_ISSUE = "reopen_issue"
    VIEW_PROMPT = "view_prompt"
    COPY_PROMPT = "copy_prompt"
    GENERATE_PROMPT = "generate_prompt"
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
    HubAction.ASSIGN_ISSUE:       {HubRole.INTERNAL_USER: False, HubRole.PLATFORM_ADMIN: True},
    HubAction.CHANGE_STATUS:      {HubRole.INTERNAL_USER: False, HubRole.PLATFORM_ADMIN: True},
    HubAction.SET_FINAL_STATUS:   {HubRole.INTERNAL_USER: False, HubRole.PLATFORM_ADMIN: True},
    HubAction.REOPEN_ISSUE:       {HubRole.INTERNAL_USER: False, HubRole.PLATFORM_ADMIN: True},
    HubAction.VIEW_PROMPT:        {HubRole.INTERNAL_USER: False, HubRole.PLATFORM_ADMIN: True},
    HubAction.COPY_PROMPT:        {HubRole.INTERNAL_USER: False, HubRole.PLATFORM_ADMIN: True},
    HubAction.GENERATE_PROMPT:    {HubRole.INTERNAL_USER: False, HubRole.PLATFORM_ADMIN: True},
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

ERROR_MESSAGES = {
    HubAction.ASSIGN_ISSUE:       "هذا الإجراء مقصور على المديرين الأساسيين فقط",
    HubAction.CHANGE_STATUS:      "هذا الإجراء مقصور على المديرين الأساسيين فقط",
    HubAction.SET_FINAL_STATUS:   "هذا الإجراء مقصور على المديرين الأساسيين فقط",
    HubAction.VIEW_PROMPT:        "فقط مدير المنصة يمكنه عرض البرومبت",
    HubAction.COPY_PROMPT:        "فقط مدير المنصة يمكنه نسخ البرومبت",
    HubAction.GENERATE_PROMPT:    "فقط مدير المنصة يمكنه إنشاء البرومبت",
    HubAction.VIEW_HAKIM_INSIGHTS:"فقط مدير المنصة يمكنه عرض تحليلات حكيم",
    HubAction.VIEW_FULL_ANALYTICS:"فقط مدير المنصة يمكنه عرض التحليلات الكاملة",
    HubAction.UPDATE_TITLE:       "هذا الإجراء مقصور على المديرين الأساسيين فقط",
    HubAction.UPDATE_PRIORITY:    "هذا الإجراء مقصور على المديرين الأساسيين فقط",
    HubAction.APPROVE_CLOSURE:    "هذا الإجراء مقصور على المدير الرئيسي فقط",
    HubAction.REOPEN_ISSUE:       "هذا الإجراء مقصور على المديرين الأساسيين فقط",
    HubAction.UPDATE_ISSUE:       "هذا الإجراء مقصور على المديرين الأساسيين فقط",
    HubAction.VIEW_ANY_ISSUE:     "ليس لديك صلاحية لعرض هذا التعليق",
    HubAction.VIEW_DUPLICATES:    "فقط مدير المنصة يمكنه عرض التكرارات",
}

ERROR_CODES = {
    HubAction.ASSIGN_ISSUE:       "FORBIDDEN_ASSIGN",
    HubAction.CHANGE_STATUS:      "FORBIDDEN_STATUS_CHANGE",
    HubAction.SET_FINAL_STATUS:   "FORBIDDEN_FINAL_STATUS",
    HubAction.VIEW_PROMPT:        "FORBIDDEN_PROMPT_VIEW",
    HubAction.COPY_PROMPT:        "FORBIDDEN_PROMPT_COPY",
    HubAction.GENERATE_PROMPT:    "FORBIDDEN_PROMPT_GENERATE",
    HubAction.VIEW_HAKIM_INSIGHTS:"FORBIDDEN_HAKIM_VIEW",
    HubAction.VIEW_FULL_ANALYTICS:"FORBIDDEN_ANALYTICS",
    HubAction.UPDATE_TITLE:       "FORBIDDEN_TITLE_UPDATE",
    HubAction.UPDATE_PRIORITY:    "FORBIDDEN_PRIORITY_UPDATE",
    HubAction.APPROVE_CLOSURE:    "FORBIDDEN_CLOSURE",
    HubAction.REOPEN_ISSUE:       "FORBIDDEN_REOPEN",
    HubAction.UPDATE_ISSUE:       "FORBIDDEN_UPDATE",
    HubAction.VIEW_ANY_ISSUE:     "FORBIDDEN_VIEW",
    HubAction.VIEW_DUPLICATES:    "FORBIDDEN_DUPLICATES_VIEW",
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
    HubAction.ASSIGN_ISSUE,
    HubAction.CHANGE_STATUS,
    HubAction.SET_FINAL_STATUS,
    HubAction.REOPEN_ISSUE,
    HubAction.UPDATE_ISSUE,
    HubAction.UPDATE_TITLE,
    HubAction.UPDATE_PRIORITY,
}

SUPER_ADMIN_ONLY_ACTIONS = {
    HubAction.APPROVE_CLOSURE,
}


def enforce_permission(user: dict, action: HubAction):
    if not check_permission(user, action):
        _deny(user, action)

    if action in SUPER_ADMIN_ONLY_ACTIONS:
        if not is_super_admin(user):
            _deny(user, action, "هذا الإجراء مقصور على المدير الرئيسي فقط (zalat@nassaqapp.com)")

    if action in MAIN_ADMIN_ONLY_ACTIONS:
        if not is_main_admin(user):
            _deny(user, action, "هذا الإجراء مقصور على المديرين الأساسيين فقط")


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
    if is_platform_admin(user):
        return issue
    for field in ADMIN_REDACTED_FIELDS:
        issue.pop(field, None)
    return issue
