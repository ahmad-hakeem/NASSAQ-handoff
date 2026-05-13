"""IT Phase 2 §6.x — Workspace audit-log view (Task #248).

Two IT-only endpoints, workspace-pinned, read-only:

  * ``GET /independent-teacher/audit-logs``
      List the caller's own workspace audit rows newest-first, with
      action category mapping, Arabic labels, and optional category /
      action / date-range filters. Cursor-paginated by ``timestamp``.

  * ``GET /independent-teacher/audit-logs/{id}``
      Detail view for a single row. Cross-workspace ids return **404**
      per spec §8 inv. 3 — never 200, never 403 — so the API does not
      confirm the existence of foreign-tenant rows.

The ``details`` JSONB is recursively stripped of sensitive keys
(token hashes, passwords, MFA secrets, raw IPs, etc.) before
serialisation. Severity is preserved as-is.

Category filtering is pushed all the way to SQL (regex / IN /
prefix-LIKE on the ``action`` column) so it composes correctly with
pagination over deep history — Python-side post-filtering would
silently drop matching rows that fall outside the first window.

No MFA step-up: read-only, low-sensitivity (the IT is reading
their own workspace history).
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, desc, not_, or_, select

from auth_scope import (
    INDEPENDENT_TEACHER_DENIED_AR,
    independent_workspace_id,
    is_independent_teacher,
    require_request_school_id,
)
from dependencies import db, get_current_user
from engines.sql_utils import gd_find_one
from pg_models import AuditLog


logger = logging.getLogger("nassaq.it_audit")

router = APIRouter(
    prefix="/independent-teacher/audit-logs",
    tags=["IT Audit Log"],
)


_MSG_NOT_FOUND = "السجل غير موجود"
_MSG_BAD_CURSOR = "مؤشر الصفحة غير صالح"
_MSG_BAD_DATE = "صيغة التاريخ غير صالحة"


# -- Details sanitization ------------------------------------------------
#
# Two-layer defense:
#
#   (1) Whitelist (default-deny): only keys in ``_DETAILS_ALLOWED_KEYS``
#       survive. Any key not in this set — including secret-like names
#       we never anticipated — is dropped. Applied recursively so nested
#       dicts/lists get the same treatment.
#
#   (2) IP masking: keys that carry a client/server IP get truncated to
#       a /24 (IPv4) or /48 (IPv6) before serialization, regardless of
#       whether they appear at the top level or nested. Bare strings are
#       returned untouched (they aren't a known IP slot).
#
# The whitelist is intentionally generous for safe operational metadata
# (entity ids, counters, status fields, timestamps) but excludes any
# free-form text or auth/identity tokens.
_DETAILS_ALLOWED_KEYS = frozenset({
    # Tenant/workspace context (non-PII identifiers).
    "school_id", "tenant_id", "workspace_school_id", "user_id",
    "student_id", "class_id", "subject_id", "teacher_id", "parent_id",
    "parent_user_id", "parent_user_materialised", "matched_by",
    "invitation_id", "session_id", "factor_id", "challenge_id",
    "lesson_plan_id", "assessment_id", "submission_id",
    "schedule_session_id", "assignment_id", "calendar_event_id",
    "collaborator_id", "host_school_id",
    # Counters & lifecycle metadata.
    "inserted", "updated", "deleted", "skipped", "succeeded", "failed",
    "attempted", "rows_processed", "row_count", "row_index",
    "total", "count", "bytes", "ttl_hours", "imports_today",
    "lesson_plans_today", "page", "limit", "version",
    # Status / lifecycle string enums.
    "status", "previous_status", "next_status", "outcome",
    "reason_code", "result", "scope", "kind", "type",
    "factor_kind", "channel", "method",
    # Entity addressing.
    "entity_type", "entity_id", "target_type", "target_id",
    # Timestamps (no IPs / contact data).
    "expires_at", "scheduled_at", "created_at", "updated_at",
    "archived_at", "reactivated_at", "deleted_at", "consumed_at",
    "started_at", "completed_at", "next_retry_at",
    # Lightweight booleans.
    "dry_run", "restored", "retried",
    "email_collision_fallback",
    # Categorical detail.
    "category",
    # Network metadata that we ourselves mask before returning.
    "ip", "client_ip", "ip_address", "remote_ip", "peer_ip",
    "x_forwarded_for", "xff",
})

_IP_KEYS = frozenset({
    "ip", "client_ip", "ip_address", "remote_ip", "peer_ip",
    "x_forwarded_for", "xff",
})


def _mask_ip(value: Any) -> Optional[str]:
    """Mask an IPv4/IPv6 address to a /24 or /48 respectively.

    Returns ``None`` for falsy/unparseable inputs (caller will drop the
    key). We deliberately don't try to be clever about XFF chains —
    just take the leftmost token, mask it, and discard the rest.
    """
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    # XFF chain: keep just the first hop.
    s = s.split(",", 1)[0].strip()
    if ":" in s and s.count(":") >= 2:
        # IPv6 — keep the first 3 hextets, mask the rest as ``::xxxx``.
        parts = s.split(":")
        head = ":".join(p for p in parts[:3] if p) or "::"
        return f"{head}::xxxx"
    if s.count(".") == 3:
        a, b, c, _ = s.split(".", 3)
        return f"{a}.{b}.{c}.x"
    return None  # unrecognised shape → drop


def _strip_sensitive(value: Any) -> Any:
    """Whitelist-sanitize an arbitrary JSONB payload.

    - Dicts: drop any key not in ``_DETAILS_ALLOWED_KEYS``; mask known
      IP slots; recurse into surviving values.
    - Lists: recurse into each item.
    - Scalars: returned as-is (bytes/datetimes get caller-side handling).
    """
    if isinstance(value, dict):
        out: Dict[str, Any] = {}
        for k, v in value.items():
            key = str(k).strip().lower()
            if key not in _DETAILS_ALLOWED_KEYS:
                continue
            if key in _IP_KEYS:
                masked = _mask_ip(v)
                if masked is not None:
                    out[key] = masked
                continue
            out[key] = _strip_sensitive(v)
        return out
    if isinstance(value, list):
        return [_strip_sensitive(item) for item in value]
    return value


# -- Action category mapping --------------------------------------------
#
# Categories are coarse on purpose — used by the FE as filter chips,
# not as a billing-grade taxonomy. Five stable keys per spec:
#   auth, lifecycle, collaborators, data-write, other

_CATEGORY_KEYS = ("auth", "lifecycle", "collaborators", "data-write", "other")

_CATEGORY_LABELS_AR: Dict[str, str] = {
    "auth": "المصادقة",
    "lifecycle": "دورة حياة المساحة",
    "collaborators": "المتعاونون",
    "data-write": "تعديلات البيانات",
    "other": "أخرى",
}

# Auth: dotted prefixes ``auth.*`` and ``mfa.*``.
_AUTH_PREFIXES = ("auth.", "mfa.")

# Lifecycle: explicit IT lifecycle action codes (uppercase).
_LIFECYCLE_ACTIONS = frozenset({
    "INDEPENDENT_TEACHER_BOOTSTRAP",
    "INDEPENDENT_TEACHER_EXPORT",
    "INDEPENDENT_TEACHER_EXPORT_DOWNLOADED",
    "INDEPENDENT_TEACHER_SOFT_DELETE",
    "INDEPENDENT_TEACHER_REACTIVATE",
    "INDEPENDENT_TEACHER_PENDING_HARD_DELETE",
    "INDEPENDENT_TEACHER_HARD_DELETED",
})

# Collaborators: any INDEPENDENT_TEACHER_COLLAB_* action.
_COLLAB_PREFIX = "INDEPENDENT_TEACHER_COLLAB_"

# Data-write: bulk import + dotted academic / attendance / behaviour /
# schedule / settings / data / session / user families.
_DATA_WRITE_EXACT = frozenset({
    "INDEPENDENT_TEACHER_BULK_IMPORT_STUDENTS",
})
_DATA_WRITE_DOTTED_PREFIXES = (
    "academic.", "attendance.", "behaviour.", "schedule.",
    "data.", "session.", "user.", "settings.", "system.",
)


def _category_for(action: str) -> str:
    """Pure-Python mirror of the SQL classification used for serialisation."""
    if not action:
        return "other"
    a = action.strip()
    a_low = a.lower()
    if any(a_low.startswith(p) for p in _AUTH_PREFIXES):
        return "auth"
    if a in _LIFECYCLE_ACTIONS:
        return "lifecycle"
    if a.startswith(_COLLAB_PREFIX):
        return "collaborators"
    if a in _DATA_WRITE_EXACT:
        return "data-write"
    if any(a_low.startswith(p) for p in _DATA_WRITE_DOTTED_PREFIXES):
        return "data-write"
    return "other"


def _sql_category_clause(category: str):
    """Build a SQL WHERE fragment that matches rows of the given category.

    Returns a SQLAlchemy expression suitable for ``where(...)``. Pushes
    the filter to the database so cursor pagination over deep history
    stays correct.
    """
    col = AuditLog.action

    auth_clause = or_(*(col.ilike(f"{p}%") for p in _AUTH_PREFIXES))
    lifecycle_clause = col.in_(tuple(_LIFECYCLE_ACTIONS))
    collab_clause = col.like(f"{_COLLAB_PREFIX}%")
    data_write_clause = or_(
        col.in_(tuple(_DATA_WRITE_EXACT)),
        *(col.ilike(f"{p}%") for p in _DATA_WRITE_DOTTED_PREFIXES),
    )

    if category == "auth":
        return auth_clause
    if category == "lifecycle":
        return lifecycle_clause
    if category == "collaborators":
        return collab_clause
    if category == "data-write":
        return data_write_clause
    if category == "other":
        # NULL action defensively bucketed as "other" too.
        return and_(
            or_(col.is_(None), not_(auth_clause)),
            or_(col.is_(None), not_(lifecycle_clause)),
            or_(col.is_(None), not_(collab_clause)),
            or_(col.is_(None), not_(data_write_clause)),
        )
    return None


# Arabic labels for action codes the IT surface emits.
_ACTION_LABELS_AR: Dict[str, str] = {
    "auth.login": "تسجيل دخول",
    "auth.logout": "تسجيل خروج",
    "auth.login_failed": "محاولة دخول فاشلة",
    "auth.password_changed": "تغيير كلمة المرور",
    "auth.password_reset": "إعادة تعيين كلمة المرور",
    "INDEPENDENT_TEACHER_BOOTSTRAP": "تهيئة مساحة العمل",
    "INDEPENDENT_TEACHER_EXPORT": "تصدير بيانات المساحة",
    "INDEPENDENT_TEACHER_EXPORT_DOWNLOADED": "تنزيل ملف التصدير",
    "INDEPENDENT_TEACHER_SOFT_DELETE": "أرشفة المساحة",
    "INDEPENDENT_TEACHER_REACTIVATE": "إعادة تفعيل المساحة",
    "INDEPENDENT_TEACHER_PENDING_HARD_DELETE": "انتهاء مهلة الاسترجاع",
    "INDEPENDENT_TEACHER_HARD_DELETED": "حذف نهائي للمساحة",
    "INDEPENDENT_TEACHER_COLLAB_INVITED": "دعوة متعاون",
    "INDEPENDENT_TEACHER_COLLAB_CANCELLED": "إلغاء دعوة متعاون",
    "INDEPENDENT_TEACHER_COLLAB_ACCEPTED": "قبول دعوة متعاون",
    "INDEPENDENT_TEACHER_COLLAB_REVOKED": "إلغاء وصول متعاون",
    "INDEPENDENT_TEACHER_BULK_IMPORT_STUDENTS": "استيراد طلاب",
    "academic.grade_recorded": "تسجيل درجة",
    "academic.grade_updated": "تعديل درجة",
    "academic.grades_bulk_recorded": "تسجيل درجات بالجملة",
    "academic.assessment_created": "إنشاء تقييم",
    "academic.assessment_published": "نشر تقييم",
    "attendance.recorded": "تسجيل حضور",
    "attendance.bulk_recorded": "تسجيل حضور بالجملة",
    "behaviour.note_created": "ملاحظة سلوكية",
    "behaviour.recorded": "تسجيل سلوك",
    "schedule.modified": "تعديل الجدول",
    "schedule.published": "نشر الجدول",
    "settings.updated": "تعديل الإعدادات",
    "data.exported": "تصدير بيانات",
    "data.imported": "استيراد بيانات",
}


def _humanise(action: str) -> str:
    if not action:
        return ""
    if action in _ACTION_LABELS_AR:
        return _ACTION_LABELS_AR[action]
    return action.replace("_", " ").replace(".", " · ")


# -- Gates ---------------------------------------------------------------


async def _require_independent_teacher(
    current_user: dict = Depends(get_current_user),
) -> dict:
    if not is_independent_teacher(current_user):
        raise HTTPException(status_code=403, detail=INDEPENDENT_TEACHER_DENIED_AR)
    return current_user


def _workspace_id(current_user: dict) -> str:
    return independent_workspace_id(current_user) or require_request_school_id(current_user)


# -- Datetime helpers ----------------------------------------------------


def _parse_iso_aware(raw: str, *, msg: str) -> datetime:
    try:
        ts = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        raise HTTPException(status_code=422, detail=msg)
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts


# -- Serialisation -------------------------------------------------------


def _serialize(row: Dict[str, Any]) -> Dict[str, Any]:
    if not row:
        return {}
    action = str(row.get("action") or "")
    raw_details = row.get("details") or {}
    details = _strip_sensitive(raw_details) if isinstance(raw_details, (dict, list)) else {}

    ts = row.get("timestamp")
    if isinstance(ts, datetime):
        ts_iso = ts.isoformat()
    else:
        ts_iso = ts if isinstance(ts, str) else None

    return {
        "id": row.get("id"),
        "action": action,
        "action_label_ar": _humanise(action),
        "category": _category_for(action),
        "severity": row.get("severity") or "low",
        "timestamp": ts_iso,
        "actor_name": row.get("actor_name"),
        "actor_role": row.get("actor_role"),
        "performed_by": row.get("performed_by"),
        "entity_type": row.get("entity_type"),
        "entity_id": row.get("entity_id"),
        "details": details,
    }


def _row_to_dict(row: AuditLog) -> Dict[str, Any]:
    return {
        "id": row.id,
        "action": row.action,
        "severity": row.severity,
        "timestamp": row.timestamp,
        "actor_name": row.actor_name,
        "actor_role": row.actor_role,
        "performed_by": row.performed_by,
        "entity_type": row.entity_type,
        "entity_id": row.entity_id,
        "details": row.details,
        "school_id": row.school_id,
    }


# -- Endpoints -----------------------------------------------------------


@router.get("")
async def list_audit_logs(
    category: Optional[str] = Query(default=None, max_length=32),
    action: Optional[str] = Query(default=None, max_length=128),
    from_: Optional[str] = Query(default=None, alias="from", max_length=32, description="ISO date/time; rows at or after this instant"),
    to: Optional[str] = Query(default=None, max_length=32, description="ISO date/time; rows strictly before this instant"),
    cursor: Optional[str] = Query(default=None, max_length=64, description="ISO timestamp; rows strictly older than this"),
    limit: int = Query(default=25, ge=1, le=100),
    current_user: dict = Depends(_require_independent_teacher),
):
    workspace_id = _workspace_id(current_user)

    conditions = [AuditLog.school_id == workspace_id]

    if action:
        conditions.append(AuditLog.action == action.strip())

    if category and category in _CATEGORY_KEYS:
        clause = _sql_category_clause(category)
        if clause is not None:
            conditions.append(clause)

    if from_:
        ts_from = _parse_iso_aware(from_, msg=_MSG_BAD_DATE)
        conditions.append(AuditLog.timestamp >= ts_from)
    if to:
        ts_to = _parse_iso_aware(to, msg=_MSG_BAD_DATE)
        conditions.append(AuditLog.timestamp < ts_to)

    if cursor:
        ts_cur = _parse_iso_aware(cursor, msg=_MSG_BAD_CURSOR)
        conditions.append(AuditLog.timestamp < ts_cur)

    stmt = (
        select(AuditLog)
        .where(and_(*conditions))
        .order_by(desc(AuditLog.timestamp))
        .limit(limit + 1)  # over-fetch one to compute next_cursor
    )

    result = await db.session.execute(stmt)
    rows = list(result.scalars().all())

    page = rows[:limit]
    serialized = [_serialize(_row_to_dict(r)) for r in page]

    next_cursor: Optional[str] = None
    if len(rows) > limit and page:
        last_ts = page[-1].timestamp
        if isinstance(last_ts, datetime):
            next_cursor = last_ts.isoformat()
        elif isinstance(last_ts, str):
            next_cursor = last_ts

    return {
        "logs": serialized,
        "next_cursor": next_cursor,
        "categories": [
            {"key": k, "label_ar": _CATEGORY_LABELS_AR[k]} for k in _CATEGORY_KEYS
        ],
    }


@router.get("/{log_id}")
async def get_audit_log(
    log_id: str,
    current_user: dict = Depends(_require_independent_teacher),
):
    workspace_id = _workspace_id(current_user)

    # Cross-workspace ids → 404 (spec §8 inv. 3). Pinning ``school_id``
    # ensures a foreign tenant's row is indistinguishable from a missing
    # one, so the API does not confirm row existence.
    row = await gd_find_one(
        db.session,
        "audit_logs",
        {"id": log_id, "school_id": workspace_id},
    )
    if not row:
        raise HTTPException(status_code=404, detail=_MSG_NOT_FOUND)

    return {"log": _serialize(row)}


__all__ = ["router"]
