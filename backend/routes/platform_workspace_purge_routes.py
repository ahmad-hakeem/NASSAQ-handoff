"""
Platform-Admin — Hard-delete archived Independent-Teacher workspaces.

Spec: docs/specs/2026-05-12-independent-teacher-phased-spec.md §6.8
(hard-delete trust boundary).
Task: #217.

The IT lifecycle router (``independent_teacher_workspace_lifecycle_routes``)
intentionally does NOT expose hard-delete: it flips workspaces to
``archived`` on user request, and the on-login lazy sweep flips
``schools.pending_hard_delete`` once the 30-day reactivation window
has passed. This router picks those rows up and actually purges them
so the right-to-be-forgotten contract is honoured end-to-end.

Two surfaces:

  * ``GET  /platform/workspaces/pending-hard-delete``
      Lists workspaces ready for purge: ``status='archived'`` AND
      ``pending_hard_delete=TRUE``. Read-only, platform-admin only.

  * ``POST /platform/workspaces/{workspace_id}/hard-delete``
      Cascades-deletes every workspace-scoped child row, then the
      ``schools`` row itself. Requires ``confirm_workspace_id`` in the
      body to match the path param verbatim — guards against a
      mis-clicked button. Writes a single
      ``INDEPENDENT_TEACHER_HARD_DELETED`` audit row carrying the
      per-table delete counts.

Trust boundary: this router lives behind
``require_roles([PLATFORM_ADMIN])`` — IT users (and every other
school role) get a flat 403. Hard-delete is never reachable from the
IT API surface itself.
"""
from __future__ import annotations

import csv
import io
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import and_, desc, or_, select
from sqlalchemy.exc import ProgrammingError

from dependencies import (
    audit_engine,
    db,
    require_roles,
    UserRole,
)
from engines.sql_utils import gd_delete_many, gd_find, gd_find_one
from pg_models import AuditLog


logger = logging.getLogger("nassaq.platform_workspace_purge")

router = APIRouter()


AUDIT_HARD_DELETED = "INDEPENDENT_TEACHER_HARD_DELETED"


_MSG_NOT_FOUND = "لم يتم العثور على مساحة العمل."
_MSG_NOT_PENDING = "هذه المساحة ليست في حالة الحذف النهائي."
_MSG_CONFIRM_MISMATCH = "تأكيد المعرّف لا يطابق المساحة المطلوبة."
_MSG_INTERNAL = "تعذّر تنفيذ العملية — حاول لاحقًا."
_MSG_BAD_DATE = "صيغة التاريخ غير صحيحة."


def _parse_iso_aware(value: str) -> datetime:
    """Parse an ISO-8601 date or datetime string into an aware UTC datetime.

    Accepts plain ``YYYY-MM-DD`` (treated as start-of-day UTC) and full
    ISO timestamps (with or without trailing ``Z``). Raises HTTP 422
    with a safe Arabic message on malformed input.
    """
    raw = (value or "").strip()
    if not raw:
        raise HTTPException(status_code=422, detail=_MSG_BAD_DATE)
    try:
        normalized = raw.replace("Z", "+00:00") if raw.endswith("Z") else raw
        if len(normalized) == 10 and normalized[4] == "-" and normalized[7] == "-":
            dt = datetime.fromisoformat(normalized + "T00:00:00+00:00")
        else:
            dt = datetime.fromisoformat(normalized)
    except (TypeError, ValueError):
        raise HTTPException(status_code=422, detail=_MSG_BAD_DATE)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _escape_like(needle: str) -> str:
    return needle.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _build_purge_filter_conditions(
    q: Optional[str],
    from_: Optional[str],
    to: Optional[str],
) -> list:
    """Shared SQL ``WHERE`` builder used by the JSON list endpoint and
    the CSV export endpoint so the downloaded file always matches what
    the platform admin sees on screen.
    """
    conditions = [AuditLog.action == AUDIT_HARD_DELETED]

    if q:
        needle = q.strip()
        if needle:
            escaped = _escape_like(needle)
            pattern = f"%{escaped}%"
            # Match against the canonical workspace id (entity_id /
            # details.school_id) and the snapshot name fields. Using
            # JSONB ``->>`` keeps the comparison server-side so
            # pagination remains correct.
            details = AuditLog.details
            conditions.append(
                or_(
                    AuditLog.entity_id.ilike(pattern, escape="\\"),
                    details["school_id"].astext.ilike(pattern, escape="\\"),
                    details["tenant_id"].astext.ilike(pattern, escape="\\"),
                    details["snapshot"]["name"].astext.ilike(pattern, escape="\\"),
                    details["snapshot"]["name_ar"].astext.ilike(pattern, escape="\\"),
                    details["snapshot"]["name_en"].astext.ilike(pattern, escape="\\"),
                )
            )

    ts_from = _parse_iso_aware(from_) if from_ else None
    ts_to = _parse_iso_aware(to) if to else None
    if ts_from and ts_to and ts_from >= ts_to:
        raise HTTPException(status_code=422, detail=_MSG_BAD_DATE)
    if ts_from is not None:
        conditions.append(AuditLog.timestamp >= ts_from)
    if ts_to is not None:
        conditions.append(AuditLog.timestamp < ts_to)

    return conditions


# Cascade order: children first, parent last. Each entry is
# ``(table_name, scope_column)``. A missing table or column logs a
# warning and continues — we never want a partial-purge to leave the
# ``schools`` row alive while a sibling table failed; the wrapping
# transaction rolls back on hard errors instead.
#
# Mirrors the export whitelist + adds the workspace-only auxiliary
# tables that the export deliberately omits (quota, collaborators,
# user accounts, school_settings, academic year/term scaffolding).
_PURGE_TABLES: List[tuple[str, str]] = [
    # Cross-workspace co-teaching links — purge by EITHER side so a
    # purged host doesn't leave dangling rows on a still-active
    # collaborator workspace, and vice versa. Done as two passes
    # below because the table has two FK columns.
    ("workspace_collaborators", "host_school_id"),
    ("workspace_collaborators", "collaborator_school_id"),
    # Per-workspace caps + invitation slots.
    ("workspace_quota", "workspace_school_id"),
    ("parent_invitations", "workspace_school_id"),
    # Operational data keyed off ``school_id``.
    ("attendance", "school_id"),
    ("assessments", "school_id"),
    ("behaviour_records", "school_id"),
    ("schedule_sessions", "school_id"),
    # Relational glue keyed off ``tenant_id``.
    ("guardian_links", "tenant_id"),
    ("events", "tenant_id"),
    ("calendar_events", "tenant_id"),
    # Roster + reference data keyed off ``school_id``.
    ("students", "school_id"),
    ("parents", "school_id"),
    ("teachers", "school_id"),
    ("classes", "school_id"),
    ("subjects", "school_id"),
    ("school_settings", "school_id"),
    ("academic_terms", "school_id"),
    ("academic_years", "school_id"),
    # Workspace-scoped user accounts (synthetic ``itw_{user_id}``
    # tenant) — purged last among the children so any FK referencing
    # ``users.id`` from the rows above is gone first.
    ("users", "tenant_id"),
    # Parent row ALWAYS last.
    ("schools", "id"),
]


class HardDeleteRequest(BaseModel):
    confirm_workspace_id: str = Field(min_length=1, max_length=200)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _iso(v: Any) -> Optional[str]:
    if not v:
        return None
    return v.isoformat() if hasattr(v, "isoformat") else str(v)


@router.get("/platform/workspaces/pending-hard-delete")
async def list_pending_hard_delete(
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN])),
):
    rows = await gd_find(
        db.session,
        "schools",
        {"pending_hard_delete": True, "status": "archived"},
    )
    return {
        "count": len(rows),
        "workspaces": [
            {
                "id": r.get("id"),
                "name": r.get("name"),
                "name_ar": r.get("name_ar"),
                "name_en": r.get("name_en"),
                "archived_at": _iso(r.get("archived_at")),
                "last_export_at": _iso(r.get("last_export_at")),
            }
            for r in rows
        ],
    }


@router.get("/platform/workspaces/recent-purges")
async def list_recent_purges(
    limit: int = 50,
    offset: int = 0,
    q: Optional[str] = Query(default=None, max_length=200),
    from_: Optional[str] = Query(default=None, alias="from", max_length=32),
    to: Optional[str] = Query(default=None, max_length=32),
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN])),
):
    # Clamp pagination params so a buggy/abusive client can't pull the
    # entire audit table in one call. Audit rows for hard-delete are
    # rare in practice, so a tight default page size is fine.
    if limit is None or limit < 1:
        limit = 50
    if limit > 200:
        limit = 200
    if offset is None or offset < 0:
        offset = 0

    conditions = _build_purge_filter_conditions(q, from_, to)

    stmt = (
        select(AuditLog)
        .where(and_(*conditions))
        .order_by(desc(AuditLog.timestamp))
        .limit(limit)
        .offset(offset)
    )
    result = await db.session.execute(stmt)
    audit_rows = list(result.scalars().all())

    rows: List[Dict[str, Any]] = [
        {
            "id": r.id,
            "timestamp": r.timestamp,
            "entity_id": r.entity_id,
            "school_id": r.school_id,
            "details": r.details,
            "performed_by": r.performed_by,
            "actor_name": r.actor_name,
            "actor_email": r.actor_email,
        }
        for r in audit_rows
    ]

    items: List[Dict[str, Any]] = []
    for r in rows:
        details = r.get("details") or {}
        snapshot = details.get("snapshot") or {}
        items.append({
            "id": r.get("id"),
            "workspace_id": (
                details.get("school_id")
                or details.get("tenant_id")
                or r.get("entity_id")
                or r.get("school_id")
            ),
            "snapshot": {
                "name": snapshot.get("name"),
                "name_ar": snapshot.get("name_ar"),
                "name_en": snapshot.get("name_en"),
                "status": snapshot.get("status"),
                "archived_at": snapshot.get("archived_at"),
                "last_export_at": snapshot.get("last_export_at"),
            },
            "deleted_counts": details.get("deleted_counts") or {},
            "skipped_tables": details.get("skipped_tables") or [],
            "purged_at": _iso(r.get("timestamp")) or details.get("purged_at"),
            "performed_by": r.get("performed_by"),
            "actor_name": r.get("actor_name"),
            "actor_email": r.get("actor_email"),
        })

    return {
        "count": len(items),
        "limit": limit,
        "offset": offset,
        "purges": items,
    }


async def purge_workspace_cascade(workspace_id: str) -> tuple[Dict[str, int], List[str], int]:
    """Run the workspace child→parent purge cascade.

    Shared helper so both the platform-admin hard-delete endpoint and the
    Task #276 daily erasure sweep follow the exact same delete order +
    schema-drift tolerance. Caller is responsible for the surrounding
    transaction (savepoint), audit logging, and pre-flight gating
    (e.g. checking ``pending_hard_delete`` / ``erasure_requested_at``).

    Returns ``(deleted_counts, skipped_keys, schools_deleted)``. Raises
    on hard DB errors so the caller's savepoint rolls back.
    """
    deleted_counts: Dict[str, int] = {}
    skipped: List[str] = []
    schools_deleted = 0
    for table_name, scope_col in _PURGE_TABLES:
        key = f"{table_name}.{scope_col}"
        is_parent = table_name == "schools"
        try:
            n = await gd_delete_many(
                db.session, table_name, {scope_col: workspace_id},
            )
        except ProgrammingError as exc:
            pgcode = getattr(getattr(exc, "orig", None), "sqlstate", None)
            if is_parent or pgcode not in {"42P01", "42703"}:
                raise
            logger.warning(
                "purge_workspace_cascade: skipping %s scope=%s pgcode=%s: %s",
                table_name, scope_col, pgcode, exc,
            )
            skipped.append(key)
            continue
        if is_parent:
            schools_deleted = int(n or 0)
        if n:
            deleted_counts[key] = deleted_counts.get(key, 0) + int(n)
    if schools_deleted < 1:
        raise RuntimeError(
            f"purge_workspace_cascade: schools row {workspace_id} not deleted",
        )
    return deleted_counts, skipped, schools_deleted


# Hard cap on how many audit rows we'll stream into the CSV in a
# single request — keeps an over-eager click from pulling the entire
# audit table into memory. Hard-delete events are rare in practice so
# this leaves headroom of multiple years before it becomes a concern.
_CSV_MAX_ROWS = 5000

_CSV_FIELDS: List[str] = [
    "workspace_id",
    "snapshot_name",
    "snapshot_name_ar",
    "snapshot_name_en",
    "snapshot_status",
    "archived_at",
    "last_export_at",
    "purged_at",
    "actor_name",
    "actor_email",
    "total_deleted_rows",
    "deleted_counts_json",
    "skipped_tables_json",
]

_MSG_CSV_FAILED = "تعذّر إعداد ملف CSV — حاول لاحقًا."


def _csv_row_for_audit(r: Dict[str, Any]) -> List[str]:
    details = r.get("details") or {}
    snapshot = details.get("snapshot") or {}
    counts = details.get("deleted_counts") or {}
    skipped = details.get("skipped_tables") or []
    workspace_id = (
        details.get("school_id")
        or details.get("tenant_id")
        or r.get("entity_id")
        or r.get("school_id")
        or ""
    )
    total = sum(int(v or 0) for v in counts.values()) if isinstance(counts, dict) else 0
    purged_at = _iso(r.get("timestamp")) or details.get("purged_at") or ""
    return [
        workspace_id or "",
        snapshot.get("name") or "",
        snapshot.get("name_ar") or "",
        snapshot.get("name_en") or "",
        snapshot.get("status") or "",
        snapshot.get("archived_at") or "",
        snapshot.get("last_export_at") or "",
        purged_at,
        r.get("actor_name") or "",
        r.get("actor_email") or "",
        str(total),
        json.dumps(counts, ensure_ascii=False, sort_keys=True),
        json.dumps(skipped, ensure_ascii=False),
    ]


@router.get("/platform/workspaces/recent-purges.csv")
async def export_recent_purges_csv(
    q: Optional[str] = Query(default=None, max_length=200),
    from_: Optional[str] = Query(default=None, alias="from", max_length=32),
    to: Optional[str] = Query(default=None, max_length=32),
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN])),
):
    # Honour the same q/from/to filters as the JSON list endpoint so
    # the downloaded CSV always matches what the admin sees on screen
    # (per follow-up #293). Validation errors (e.g. malformed dates)
    # surface as HTTP 422 from the shared helper.
    conditions = _build_purge_filter_conditions(q, from_, to)

    try:
        stmt = (
            select(AuditLog)
            .where(and_(*conditions))
            .order_by(desc(AuditLog.timestamp))
            .limit(_CSV_MAX_ROWS)
        )
        result = await db.session.execute(stmt)
        audit_rows = list(result.scalars().all())
        rows: List[Dict[str, Any]] = [
            {
                "id": r.id,
                "timestamp": r.timestamp,
                "entity_id": r.entity_id,
                "school_id": r.school_id,
                "details": r.details,
                "performed_by": r.performed_by,
                "actor_name": r.actor_name,
                "actor_email": r.actor_email,
            }
            for r in audit_rows
        ]
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "export_recent_purges_csv: load failed admin=%s: %s",
            current_user.get("id"), exc,
        )
        raise HTTPException(status_code=500, detail=_MSG_CSV_FAILED)

    def _iter_csv():
        # UTF-8 BOM so Excel opens the Arabic columns correctly.
        header_buf = io.StringIO()
        header_buf.write("\ufeff")
        header_writer = csv.writer(header_buf, quoting=csv.QUOTE_MINIMAL)
        header_writer.writerow(_CSV_FIELDS)
        yield header_buf.getvalue().encode("utf-8")

        for r in rows:
            row_buf = io.StringIO()
            row_writer = csv.writer(row_buf, quoting=csv.QUOTE_MINIMAL)
            row_writer.writerow(_csv_row_for_audit(r))
            yield row_buf.getvalue().encode("utf-8")

    filename = (
        f"workspace-purges-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}.csv"
    )
    return StreamingResponse(
        _iter_csv(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/platform/workspaces/{workspace_id}/hard-delete")
async def hard_delete_workspace(
    workspace_id: str,
    payload: HardDeleteRequest,
    request: Request,
    current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN])),
):
    if (payload.confirm_workspace_id or "") != workspace_id:
        raise HTTPException(status_code=422, detail=_MSG_CONFIRM_MISMATCH)

    school = await gd_find_one(db.session, "schools", {"id": workspace_id})
    if not school:
        raise HTTPException(status_code=404, detail=_MSG_NOT_FOUND)

    if not school.get("pending_hard_delete"):
        raise HTTPException(status_code=409, detail=_MSG_NOT_PENDING)

    snapshot = {
        "name": school.get("name"),
        "name_ar": school.get("name_ar"),
        "name_en": school.get("name_en"),
        "status": school.get("status"),
        "archived_at": _iso(school.get("archived_at")),
        "last_export_at": _iso(school.get("last_export_at")),
    }

    deleted_counts: Dict[str, int] = {}
    skipped: List[str] = []

    try:
        async with db.session.begin_nested():
            deleted_counts, skipped, _schools_deleted = await purge_workspace_cascade(
                workspace_id,
            )

            await audit_engine.log(
                action=AUDIT_HARD_DELETED,
                performed_by=current_user["id"],
                tenant_id=workspace_id,
                entity_type="school",
                entity_id=workspace_id,
                details={
                    "school_id": workspace_id,
                    "tenant_id": workspace_id,
                    "snapshot": snapshot,
                    "deleted_counts": deleted_counts,
                    "skipped_tables": skipped,
                    "purged_at": _utcnow().isoformat(),
                },
                actor_name=current_user.get("full_name"),
                actor_role=current_user.get("role"),
                actor_email=current_user.get("email"),
                ip_address=(request.client.host if request.client else None),
                user_agent=request.headers.get("user-agent"),
            )
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "hard_delete_workspace failed workspace=%s admin=%s: %s",
            workspace_id, current_user.get("id"), exc,
        )
        raise HTTPException(status_code=500, detail=_MSG_INTERNAL)

    return {
        "ok": True,
        "workspace_id": workspace_id,
        "deleted_counts": deleted_counts,
        "skipped_tables": skipped,
    }


__all__ = ["router", "purge_workspace_cascade", "_PURGE_TABLES"]
