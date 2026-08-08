"""
Independent-Teacher — Workspace lifecycle (export + soft-delete).

Spec: docs/specs/2026-05-12-independent-teacher-phased-spec.md §6.8.
Task: #211 (IT-P2 §6.8).

Four HTTP surfaces:

  * ``POST /independent-teacher/workspace/export``
      IT-only, Tier-A MFA. Returns a 24h signed download URL pointing
      at the public bytes endpoint below. The URL token is bound to
      ``(workspace_school_id, user_id)`` so a leaked link cannot be
      replayed against a different workspace or by a different user.
      Stamps ``schools.last_export_at`` so the soft-delete confirm
      step can enforce the "must export within 24h" pre-condition.

  * ``GET  /public/workspace-export/{token}``
      Authenticated download endpoint. Verifies the JWT signature +
      purpose + ``ws``/``uid`` claims, then streams a JSON-zip bundle
      of the workspace's whitelisted tables. IP rate-limited via the
      existing ``rate_store``.

      Identity binding (§369): ALL downloads require a valid Bearer
      access token whose ``sub`` claim matches ``payload["uid"]``.
      No unauthenticated path exists.  The token-verification helper
      ``_authenticate_export_download`` intentionally skips
      ``is_active`` and the IT-archived-workspace gate because the
      erasure flow deactivates the user in the same transaction that
      mints the exit-artefact token; the export token's own single-use
      + expiry + uid/ws binding are sufficient guards.  See helper
      docstring for full rationale.

  * ``POST /independent-teacher/workspace/soft-delete``
      IT-only, Tier-A MFA. Pre-conditions:
        - Caller has exported within the last 24h (412 otherwise).
        - The submitted ``confirm_workspace_name`` matches the school
          row's name verbatim (422 otherwise).
      Effect: flips ``schools.status`` 'active' → 'archived' and sets
      ``schools.archived_at = now()``. NO row deletes. The user can
      no longer log in (auth_routes_mod login gate rejects archived
      workspaces with a safe Arabic message); reactivation within 30
      days flips the workspace back to 'active'.

  * ``POST /independent-teacher/workspace/reactivate``
      IT-only. Allowed when ``status='archived'`` AND
      ``archived_at`` is within the 30-day reactivation window AND
      ``pending_hard_delete`` is FALSE. Returns 410 Gone otherwise.

Hard-delete is intentionally NOT exposed by this router. Platform-
admin out-of-band tooling picks rows up by ``pending_hard_delete``;
the on-login lazy sweep below sets that flag once an archived
workspace passes the 30-day window. This way the destructive
operation is gated by a separate trust boundary and never callable
from the IT surface.

§8 invariant 3 (cross-workspace by-id 404): every IT-reachable read
in this router is pinned to the caller's workspace via
``require_request_school_id`` + ``independent_workspace_id``. The
public download endpoint resolves the workspace from the JWT, never
from a path parameter, so there is no cross-tenant by-id surface.
"""
from __future__ import annotations

import io
import json
import logging
import zipfile
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field

from auth_scope import (
    INDEPENDENT_TEACHER_DENIED_AR,
    independent_workspace_id,
    is_independent_teacher,
    require_request_school_id,
)
import jwt as _jwt

from dependencies import (
    JWT_ALGORITHM,
    JWT_SECRET,
    audit_engine,
    db,
    get_current_user,
    require_recent_mfa_403,
)
from engines.sql_utils import gd_count, gd_find, gd_find_one, gd_update_one
from sqlalchemy import select as _sa_select
from sqlalchemy.exc import ProgrammingError as _PgProgrammingError
from pg_models import School as _SchoolModel
from quotas.independent_teacher import (
    MAX_LESSON_PLANS_PER_DAY as _Q_MAX_LESSON_PLANS,
    MAX_STUDENTS as _Q_MAX_STUDENTS,
)
from middleware.rate_limiter import rate_store
from utils.tokens import (
    WORKSPACE_EXPORT_TOKEN_TTL,
    mint_workspace_export_token,
    token_hash as _token_hash,
    verify_workspace_export_token,
)
from middleware.rbac import Permission, RBACMiddleware
from utils.trusted_proxy import extract_client_ip
from engines.email_service import (
    send_workspace_archived_email,
    send_workspace_auto_export_email,
    send_workspace_erasure_final_export_email,
    send_workspace_reactivation_reminder_email,
)
from services.email_client import send_email_off_loop
import os


logger = logging.getLogger("nassaq.it_workspace_lifecycle")

router = APIRouter()


# -- Audit actions --------------------------------------------------------

AUDIT_EXPORT = "INDEPENDENT_TEACHER_EXPORT"
AUDIT_EXPORT_DOWNLOADED = "INDEPENDENT_TEACHER_EXPORT_DOWNLOADED"
AUDIT_SOFT_DELETE = "INDEPENDENT_TEACHER_SOFT_DELETE"
AUDIT_REACTIVATE = "INDEPENDENT_TEACHER_REACTIVATE"
AUDIT_PENDING_HARD_DELETE = "INDEPENDENT_TEACHER_PENDING_HARD_DELETE"
# Task #276 — IT account-erasure (GDPR right-to-be-forgotten).
AUDIT_ERASURE_REQUESTED = "INDEPENDENT_TEACHER_ERASURE_REQUESTED"
AUDIT_ERASURE_COMPLETED = "INDEPENDENT_TEACHER_ERASURE_COMPLETED"


# -- Safe Arabic copy -----------------------------------------------------

_MSG_INTERNAL = "تعذّر تنفيذ العملية — حاول لاحقًا."
_MSG_WORKSPACE_NOT_FOUND = "لم يتم العثور على مساحة العمل."
_MSG_EXPORT_REQUIRED = "يجب تصدير بياناتك خلال آخر ٢٤ ساعة قبل الأرشفة."
_MSG_NAME_MISMATCH = "اسم المساحة المُدخل لا يطابق الاسم المسجّل."
_MSG_ALREADY_ARCHIVED = "تم أرشفة المساحة بالفعل."
_MSG_NOT_ARCHIVED = "هذه المساحة ليست مؤرشفة."
_MSG_REACTIVATE_EXPIRED = "انتهت مهلة الاسترجاع (٣٠ يومًا). تواصل مع الدعم."
_MSG_DOWNLOAD_INVALID = "رابط التنزيل غير صالح أو منتهي الصلاحية."
_MSG_DOWNLOAD_IDENTITY = "لا يحق لك تنزيل هذا الملف."
_MSG_DOWNLOAD_AUTH_REQUIRED = "يجب تسجيل الدخول لتنزيل ملف التصدير."
_MSG_RATE_LIMITED = "عدد المحاولات تجاوز الحد المسموح. حاول لاحقًا."
_MSG_ERASURE_PENDING = "تم تسجيل طلب الحذف النهائي مسبقًا — لا يمكن إعادة التفعيل."
_MSG_ALREADY_ERASURE = "تم تسجيل طلب الحذف النهائي مسبقًا."
_MSG_NOT_ACKNOWLEDGED = "يجب تأكيد فهم العواقب قبل المتابعة."


def _erasure_window_days() -> int:
    """Read the configured erasure grace window. Default 7 days. Clamped
    to [1, 90] so a misconfigured env var cannot skip the grace period
    or stretch it indefinitely.
    """
    raw = os.getenv("WORKSPACE_ERASURE_WINDOW_DAYS", "7")
    try:
        v = int(raw)
    except (TypeError, ValueError):
        v = 7
    if v < 1:
        v = 1
    if v > 90:
        v = 90
    return v

# Reactivation window — fixed at 30 days per §6.8. Past this window
# the on-login sweep flips ``pending_hard_delete=TRUE`` and the
# reactivate endpoint 410s.
_REACTIVATE_WINDOW = timedelta(days=30)

# Public download rate-limit: 30 attempts / 5 minutes per IP. Generous
# enough for legitimate "download interrupted, try again" flows but
# kills brute enumeration of `jti` values in leaked tokens.
_DOWNLOAD_RATE_MAX = 30
_DOWNLOAD_RATE_WINDOW = 300

# Workspace-scoped tables we export. Each entry is
# ``(table_name, scope_column)``. The scope column is filtered against
# the workspace school id; rows that don't carry the scope column are
# never exported here. Anything not on this list is OUT OF SCOPE for
# the right-to-export contract — when in doubt, omit. Adding a new
# table requires a new task + spec update.
_EXPORT_TABLES: List[tuple[str, str]] = [
    ("schools", "id"),
    ("teachers", "school_id"),
    ("classes", "school_id"),
    ("subjects", "school_id"),
    ("students", "school_id"),
    ("parents", "school_id"),
    ("guardian_links", "tenant_id"),
    ("schedule_sessions", "school_id"),
    ("attendance", "school_id"),
    ("assessments", "school_id"),
    ("behaviour_records", "school_id"),
    ("events", "tenant_id"),
    ("parent_invitations", "workspace_school_id"),
]

# Sensitive columns that must never appear in the export bundle even
# when the row itself is in scope. The export is a right-to-export
# artefact, not a credential dump — password hashes, MFA secrets,
# session jti fields stay server-side.
_REDACTED_COLUMNS = {
    "password_hash", "reset_token_hash", "reset_token_expires_at",
    "webauthn_public_key", "webauthn_credential_id", "webauthn_sign_count",
    "totp_secret", "totp_secret_encrypted",
    "token_hash",
}


# -- Request models -------------------------------------------------------

class SoftDeleteRequest(BaseModel):
    confirm_workspace_name: str = Field(min_length=1, max_length=200)


class RequestErasureRequest(BaseModel):
    confirm_workspace_name: str = Field(min_length=1, max_length=200)
    acknowledged: bool = Field(default=False)


# -- Helpers --------------------------------------------------------------

def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _utcnow_iso() -> str:
    return _utcnow().isoformat()


async def _require_independent_teacher(
    current_user: dict = Depends(get_current_user),
) -> dict:
    if not is_independent_teacher(current_user):
        raise HTTPException(status_code=403, detail=INDEPENDENT_TEACHER_DENIED_AR)
    return current_user


_recent_mfa_403_dep = require_recent_mfa_403()


async def _require_workspace_export_perm(
    current_user: dict = Depends(get_current_user),
) -> dict:
    if not RBACMiddleware.has_permission(current_user, Permission.WORKSPACE_EXPORT.value):
        raise HTTPException(status_code=403, detail=INDEPENDENT_TEACHER_DENIED_AR)
    return current_user


async def _require_workspace_soft_delete_perm(
    current_user: dict = Depends(get_current_user),
) -> dict:
    if not RBACMiddleware.has_permission(current_user, Permission.WORKSPACE_SOFT_DELETE.value):
        raise HTTPException(status_code=403, detail=INDEPENDENT_TEACHER_DENIED_AR)
    return current_user


def _coerce_dt(v: Any) -> Optional[datetime]:
    if v is None:
        return None
    if isinstance(v, datetime):
        return v if v.tzinfo else v.replace(tzinfo=timezone.utc)
    if isinstance(v, str):
        try:
            dt = datetime.fromisoformat(v.replace("Z", "+00:00"))
        except ValueError:
            return None
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    return None


def _json_default(o: Any) -> Any:
    if isinstance(o, (datetime,)):
        return o.isoformat()
    if isinstance(o, bytes):
        # Defensive: webauthn columns are redacted, but any stray
        # bytes column (e.g. binary qr_code) needs a JSON-safe form.
        return None
    try:
        return str(o)
    except Exception:  # noqa: BLE001
        return None


def _redact(row: Dict[str, Any]) -> Dict[str, Any]:
    return {k: v for k, v in row.items() if k not in _REDACTED_COLUMNS}


async def _build_export_bundle(workspace_id: str) -> bytes:
    """Read every whitelisted table for ``workspace_id`` and return a
    zip archive of one ``<table>.json`` file per table.

    Memory note: NASSAQ's IT workspaces are bounded by the per-user
    quotas in ``backend.quotas.independent_teacher`` (unlimited classes,
    ≤ 200 students, etc.), so the entire workspace fits comfortably in
    memory. If a future tier raises those caps we'll switch to a
    streaming archive — for now in-memory keeps the route trivially
    transactional.
    """
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        manifest: Dict[str, Any] = {
            "workspace_school_id": workspace_id,
            "generated_at": _utcnow_iso(),
            "schema_version": 1,
            "tables": {},
        }
        for table_name, scope_col in _EXPORT_TABLES:
            try:
                rows = await gd_find(db.session, table_name, {scope_col: workspace_id})
            except Exception as exc:  # noqa: BLE001
                # A missing table or column is not fatal — skip it and
                # record the omission in the manifest so the recipient
                # can tell the difference between "no data" and "not
                # exported". We never want a partial workspace to leak
                # because one optional table got renamed.
                logger.warning(
                    "workspace export: table=%s scope=%s skipped: %s",
                    table_name, scope_col, exc,
                )
                manifest["tables"][table_name] = {"count": 0, "skipped": True}
                continue
            redacted = [_redact(r) for r in rows]
            payload = json.dumps(
                redacted, ensure_ascii=False, default=_json_default,
            ).encode("utf-8")
            zf.writestr(f"{table_name}.json", payload)
            manifest["tables"][table_name] = {"count": len(redacted)}
        zf.writestr(
            "manifest.json",
            json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8"),
        )
    return buf.getvalue()


# -- Endpoint: GET /independent-teacher/workspace/lifecycle --------------
#
# Read-only view of the four §6.8 lifecycle columns so the FE can
# render the soft-delete gating affordance (button greyed-out until
# last_export_at is within 24h) on mount, without leaking any of the
# token-state columns. Same workspace-scope guard as the write paths.

async def _load_quota_snapshot(workspace_id: str) -> Optional[Dict[str, Any]]:
    """Read-only workspace_quota snapshot for the §6.8 lifecycle hub.

    Mirrors the fields exposed by the bulk-import ``_quota_view`` so the FE
    "إعدادات المساحة" hub (Task #252) can render progress bars without a
    second source of truth. Returns ``None`` on any read failure — the
    lifecycle endpoint must not fail if the quota row is absent.
    """
    try:
        quota = await gd_find_one(
            db.session, "workspace_quota", {"workspace_school_id": workspace_id},
        )
        if not quota:
            quota = {}
        # Per-day counters reset at UTC midnight; mirror the bulk-import +
        # lesson-plans behaviour so the FE chip is consistent across surfaces.
        today = _utcnow().date()

        def _coerce_day(v):
            if v is None:
                return None
            if isinstance(v, datetime):
                return v.date()
            if hasattr(v, "year") and not isinstance(v, str):
                return v
            try:
                return datetime.fromisoformat(str(v)[:10]).date()
            except Exception:  # noqa: BLE001
                return None

        imports_day = _coerce_day(quota.get("imports_today_date"))
        imports_today = (
            int(quota.get("imports_today") or 0) if imports_day == today else 0
        )
        plans_day = _coerce_day(quota.get("lesson_plans_today_date"))
        plans_today = (
            int(quota.get("lesson_plans_today") or 0) if plans_day == today else 0
        )

        # Live counts (cheap: one COUNT(*) each) — needed for the
        # "students used / max" + "classes used / max" progress bars.
        # IMPORTANT: align scope + active filter with the canonical
        # enforcement path in `independent_teacher_bulk_import_routes.py`
        # (`{school_id, is_active != False}`) so the hub progress bars
        # never disagree with what bulk-import / the seat counter see.
        try:
            current_students = await gd_count(
                db.session,
                "students",
                {"school_id": workspace_id, "is_active": {"$ne": False}},
            )
        except Exception:  # noqa: BLE001
            current_students = 0
        try:
            current_classes = await gd_count(
                db.session,
                "classes",
                {"school_id": workspace_id, "is_active": {"$ne": False}},
            )
        except Exception:  # noqa: BLE001
            current_classes = 0

        return {
            "max_students": int(quota.get("max_students") or _Q_MAX_STUDENTS),
            "max_classes": None,  # classes are unlimited for IT workspaces
            "max_imports_per_day": int(quota.get("max_imports_per_day") or 5),
            "max_rows_per_import": int(quota.get("max_rows_per_import") or 200),
            "max_lesson_plans_per_day": _Q_MAX_LESSON_PLANS,
            "current_students": current_students,
            "current_classes": current_classes,
            "imports_today": imports_today,
            "lesson_plans_today": plans_today,
        }
    except Exception as exc:  # noqa: BLE001
        logger.debug("_load_quota_snapshot failed for %s: %s", workspace_id, exc)
        return None


def _build_lifecycle_payload(
    workspace_id: str,
    school: Dict[str, Any],
    quota: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Shared builder for the IT workspace lifecycle view + the post-login
    reactivation banner. Used by ``GET /independent-teacher/workspace/lifecycle``
    and embedded into ``/auth/login`` + ``/auth/mfa/verify`` token responses
    so the dashboard can paint the banner in the same frame as the rest of
    the page (Task #231).
    """

    def _iso(v):
        if not v:
            return None
        return v.isoformat() if hasattr(v, "isoformat") else str(v)

    # Reactivation banner gate: surface a one-time post-login banner
    # whenever the user has reactivated since their last dismissal.
    # Re-arms automatically on every fresh archive→reactivate cycle.
    last_reactivated_at = _coerce_dt(school.get("last_reactivated_at"))
    dismissed_at = _coerce_dt(school.get("reactivation_banner_dismissed_at"))
    archive_cycle_archived_at = _coerce_dt(school.get("last_archive_cycle_archived_at"))
    banner = None
    if last_reactivated_at is not None and (
        dismissed_at is None or dismissed_at < last_reactivated_at
    ):
        if archive_cycle_archived_at is not None:
            would_have_been_deleted_at = archive_cycle_archived_at + _REACTIVATE_WINDOW
            remaining = would_have_been_deleted_at - last_reactivated_at
            days_remaining_at_reactivation = max(0, int(remaining.total_seconds() // 86400))
            banner = {
                "archived_at": archive_cycle_archived_at.isoformat(),
                "reactivated_at": last_reactivated_at.isoformat(),
                "would_have_been_deleted_at": would_have_been_deleted_at.isoformat(),
                "reactivation_window_days": _REACTIVATE_WINDOW.days,
                "days_remaining_at_reactivation": days_remaining_at_reactivation,
            }
        else:
            # Defensive fallback for legacy rows reactivated before the
            # archive-cycle column existed; show a minimal banner.
            banner = {
                "archived_at": None,
                "reactivated_at": last_reactivated_at.isoformat(),
                "would_have_been_deleted_at": None,
                "reactivation_window_days": _REACTIVATE_WINDOW.days,
                "days_remaining_at_reactivation": None,
            }

    payload = {
        "workspace_id": workspace_id,
        "name_ar": school.get("name_ar"),
        "name_en": school.get("name_en"),
        "last_export_at": _iso(school.get("last_export_at")),
        "archived_at": _iso(school.get("archived_at")),
        "pending_hard_delete": bool(school.get("pending_hard_delete")),
        "reactivation_banner": banner,
    }
    # Task #252 (additive): the §6.8 "إعدادات المساحة" hub renders progress
    # bars from this snapshot. Field is omitted when unavailable so legacy
    # callers see the same payload shape they did before.
    if quota is not None:
        payload["quota"] = quota
    return payload


async def fetch_workspace_lifecycle_for_user(user: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Best-effort post-login lifecycle snapshot for an IT user.

    Returns ``None`` when the caller is not an Independent Teacher, when no
    workspace row resolves, or when the lookup fails for any reason — the
    login flow must never break because of a banner-gating side-channel.
    Used by ``/auth/login`` + ``/auth/mfa/verify`` (Task #231).
    """
    try:
        workspace_id = independent_workspace_id(user)
        if not workspace_id:
            return None
        school = await gd_find_one(db.session, "schools", {"id": workspace_id})
        if not school:
            return None
        return _build_lifecycle_payload(workspace_id, school)
    except Exception as exc:  # pragma: no cover — defensive
        logger.debug("fetch_workspace_lifecycle_for_user skipped: %s", exc)
        return None


@router.get("/independent-teacher/workspace/lifecycle")
async def read_workspace_lifecycle(
    current_user: dict = Depends(_require_independent_teacher),
):
    workspace_id = independent_workspace_id(current_user) or require_request_school_id(current_user)
    school = await gd_find_one(db.session, "schools", {"id": workspace_id})
    if not school:
        raise HTTPException(status_code=404, detail=_MSG_WORKSPACE_NOT_FOUND)
    # Task #252 — embed the workspace_quota snapshot so the §6.8 hub can
    # paint progress bars in one round trip. Failures fall back to None;
    # the FE treats absent quota as "unknown" and hides the bar.
    quota = await _load_quota_snapshot(workspace_id)
    return _build_lifecycle_payload(workspace_id, school, quota=quota)


# -- Endpoint: GET /independent-teacher/workspace/quota-history -----------
#
# Task #253 — daily-usage time series powering the workspace-hub
# QuotaBar spark-lines. Returns the last N (default 14, max 30) UTC
# days of per-metric usage so the IT user can see whether they're
# trending toward a cap before they hit it.
#
# Series shape (all four arrays are the same length as ``days``):
#   * ``students`` — cumulative active-student count at end-of-day
#     (rows where ``school_id == ws AND created_at <= EOD``). Mirrors
#     the "current_students / max_students" progress bar.
#   * ``classes`` — cumulative class count at end-of-day, same scope.
#   * ``imports`` — per-day count of bulk-import audit events
#     (``INDEPENDENT_TEACHER_BULK_IMPORT_STUDENTS``); mirrors the
#     daily ``imports_today`` counter that resets at UTC midnight.
#   * ``lesson_plans`` — per-day count of saved generations from the
#     ``lesson_plans`` table; mirrors ``lesson_plans_today``.
#
# Pure read; no MFA. Workspace-pinned via the same scope helpers as
# every other route in this router so cross-workspace callers can't
# probe foreign tenant counts.

async def _load_quota_history(workspace_id: str, days: int) -> Dict[str, Any]:
    """Build a ``days``-long daily series for the workspace-hub spark-lines.

    Each metric is computed from existing tables; no new history table.
    Failures degrade to zero-filled arrays so a single broken metric
    never wedges the others. Day labels are ISO ``YYYY-MM-DD`` UTC dates,
    oldest → newest, length == ``days``.
    """
    from sqlalchemy import select, func
    from pg_models import Student, Class, AuditLog, LessonPlan

    today = _utcnow().date()
    start = today - timedelta(days=days - 1)
    start_dt = datetime.combine(start, datetime.min.time(), tzinfo=timezone.utc)
    day_list = [(start + timedelta(days=i)).isoformat() for i in range(days)]
    day_index = {d: i for i, d in enumerate(day_list)}

    out: Dict[str, Any] = {
        "days": day_list,
        "students": [0] * days,
        "classes": [0] * days,
        "imports": [0] * days,
        "lesson_plans": [0] * days,
    }

    session = db.session

    async def _cumulative(model, scope_col, scope_val, ts_col):
        """Cumulative end-of-day count series.

        ``prior`` is the row count strictly before ``start_dt``; we then
        walk forward adding the per-day row counts so each cell is the
        cumulative total at that day's end.
        """
        try:
            prior_stmt = select(func.count()).select_from(model).where(
                scope_col == scope_val, ts_col < start_dt,
            )
            prior = int((await session.execute(prior_stmt)).scalar() or 0)
            per_day_stmt = select(
                func.date(ts_col).label("d"), func.count().label("c"),
            ).where(
                scope_col == scope_val, ts_col >= start_dt,
            ).group_by(func.date(ts_col))
            rows = (await session.execute(per_day_stmt)).all()
            added: Dict[str, int] = {}
            for r in rows:
                key = r[0].isoformat() if hasattr(r[0], "isoformat") else str(r[0])
                added[key] = int(r[1])
            running = prior
            series = [0] * days
            for i, d in enumerate(day_list):
                running += added.get(d, 0)
                series[i] = running
            return series
        except Exception as exc:  # noqa: BLE001
            logger.debug("quota-history cumulative %s failed: %s", model.__tablename__, exc)
            return [0] * days

    async def _per_day(model, scope_col, scope_val, ts_col, extra=None):
        try:
            conds = [scope_col == scope_val, ts_col >= start_dt]
            if extra is not None:
                conds.append(extra)
            stmt = select(
                func.date(ts_col).label("d"), func.count().label("c"),
            ).where(*conds).group_by(func.date(ts_col))
            rows = (await session.execute(stmt)).all()
            series = [0] * days
            for r in rows:
                key = r[0].isoformat() if hasattr(r[0], "isoformat") else str(r[0])
                idx = day_index.get(key)
                if idx is not None:
                    series[idx] = int(r[1])
            return series
        except Exception as exc:  # noqa: BLE001
            logger.debug("quota-history per-day %s failed: %s", model.__tablename__, exc)
            return [0] * days

    out["students"] = await _cumulative(
        Student, Student.school_id, workspace_id, Student.created_at,
    )
    out["classes"] = await _cumulative(
        Class, Class.school_id, workspace_id, Class.created_at,
    )
    out["imports"] = await _per_day(
        AuditLog, AuditLog.school_id, workspace_id, AuditLog.timestamp,
        extra=(AuditLog.action == "INDEPENDENT_TEACHER_BULK_IMPORT_STUDENTS"),
    )
    out["lesson_plans"] = await _per_day(
        LessonPlan, LessonPlan.workspace_school_id, workspace_id, LessonPlan.created_at,
    )
    return out


@router.get("/independent-teacher/workspace/quota-history")
async def read_quota_history(
    days: int = Query(default=14, ge=1, le=30),
    current_user: dict = Depends(_require_independent_teacher),
):
    workspace_id = independent_workspace_id(current_user) or require_request_school_id(current_user)
    school = await gd_find_one(db.session, "schools", {"id": workspace_id})
    if not school:
        raise HTTPException(status_code=404, detail=_MSG_WORKSPACE_NOT_FOUND)
    history = await _load_quota_history(workspace_id, days)
    return {"workspace_id": workspace_id, "days_requested": days, **history}


# -- Endpoint: POST /independent-teacher/workspace/lifecycle/reactivation-banner/dismiss

@router.post("/independent-teacher/workspace/lifecycle/reactivation-banner/dismiss")
async def dismiss_reactivation_banner(
    current_user: dict = Depends(_require_independent_teacher),
):
    """Stamp ``reactivation_banner_dismissed_at = now`` so the post-
    login dashboard banner stops surfacing for the current archive
    cycle. Idempotent: stamping again on an already-dismissed row is
    a no-op from the user's perspective. A future archive→reactivate
    cycle re-arms the banner because the gate compares the stamp
    against ``last_reactivated_at``.
    """
    workspace_id = independent_workspace_id(current_user) or require_request_school_id(current_user)
    school = await gd_find_one(db.session, "schools", {"id": workspace_id})
    if not school:
        raise HTTPException(status_code=404, detail=_MSG_WORKSPACE_NOT_FOUND)
    now = _utcnow()
    try:
        async with db.session.begin_nested():
            await gd_update_one(
                db.session, "schools", {"id": workspace_id},
                {"reactivation_banner_dismissed_at": now.isoformat()},
            )
    except Exception as exc:  # noqa: BLE001
        logger.warning("dismiss_reactivation_banner failed: %s", exc)
        raise HTTPException(status_code=500, detail=_MSG_INTERNAL)
    return {"ok": True, "dismissed_at": now.isoformat()}


# -- Endpoint: POST /independent-teacher/workspace/export -----------------

@router.post("/independent-teacher/workspace/export")
async def create_workspace_export(
    request: Request,
    current_user: dict = Depends(_require_independent_teacher),
    _mfa: dict = Depends(_recent_mfa_403_dep),
    _perm: dict = Depends(_require_workspace_export_perm),
):
    school_id = require_request_school_id(current_user)
    workspace_id = independent_workspace_id(current_user) or school_id

    school = await gd_find_one(db.session, "schools", {"id": workspace_id})
    if not school:
        raise HTTPException(status_code=404, detail=_MSG_WORKSPACE_NOT_FOUND)

    raw_token, raw_hash, expires_at = mint_workspace_export_token(
        workspace_id, current_user["id"],
    )
    # Task #450 — capture the JTI of the bearer token that minted this
    # download so the public download endpoint can verify the redeemer is
    # the same session.  Any other bearer token must pass full session-
    # invalidation checks at download time.
    initiator_jti = _extract_bearer_jti(request)
    now = _utcnow()
    try:
        async with db.session.begin_nested():
            # Persist the token hash + clear any prior consumed_at so the
            # public download endpoint can enforce single-use semantics.
            # Minting a new token explicitly invalidates any prior
            # outstanding download URL — only the most recent token is
            # honoured at any time.
            await gd_update_one(
                db.session, "schools", {"id": workspace_id},
                {
                    "last_export_at": now.isoformat(),
                    "last_export_token_hash": raw_hash,
                    "last_export_consumed_at": None,
                    "last_export_initiator_jti": initiator_jti,
                },
            )
            await audit_engine.log(
                action=AUDIT_EXPORT,
                performed_by=current_user["id"],
                tenant_id=workspace_id,
                entity_type="school",
                entity_id=workspace_id,
                details={
                    "school_id": workspace_id,
                    "tenant_id": workspace_id,
                    "user_id": current_user["id"],
                    "expires_at": expires_at.isoformat(),
                    "ttl_hours": int(WORKSPACE_EXPORT_TOKEN_TTL.total_seconds() // 3600),
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
            "create_workspace_export failed user=%s: %s",
            current_user.get("id"), exc,
        )
        raise HTTPException(status_code=500, detail=_MSG_INTERNAL)

    return {
        "download_url": f"/api/public/workspace-export/{raw_token}",
        "expires_at": expires_at.isoformat(),
        "ttl_hours": int(WORKSPACE_EXPORT_TOKEN_TTL.total_seconds() // 3600),
    }


# -- Endpoint: GET /public/workspace-export/{token} -----------------------


def _extract_bearer_jti(request: Request) -> Optional[str]:
    """Decode the request's Authorization Bearer access token and return its
    ``jti`` claim, or ``None`` if no/invalid token is present.

    Used at export-mint time to bind the freshly issued single-use download
    URL to the exact session that initiated the action (Task #450).  No
    authentication side-effects — the caller is already authenticated by
    ``Depends(get_current_user)`` upstream; this helper only extracts the
    JTI for persistence.
    """
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None
    raw = auth_header[len("Bearer "):].strip()
    if not raw:
        return None
    try:
        decoded = _jwt.decode(raw, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except _jwt.PyJWTError:
        return None
    jti = decoded.get("jti")
    return str(jti) if jti else None


async def _authenticate_export_download(
    request: Request, *, initiator_jti: Optional[str],
) -> str:
    """Authenticate the caller for the workspace export download endpoint.

    Task #450 hardening — session invalidation must hold on the public
    download path.  Behaviour:

    * Requires a valid Bearer access token (type, signature, expiry, revocation).
    * Checks ``is_locked``: a security lockout (distinct from normal
      deactivation) always blocks the download.
    * Enforces ``is_active`` and ``last_password_change`` (token ``iat``)
      checks — equivalent to the gates in ``get_current_user`` — for every
      bearer token whose JTI does NOT match the recorded ``initiator_jti``
      for this export.  That means any bearer token other than the one that
      minted the URL is rejected once archive/erasure has bumped
      ``last_password_change`` / cleared ``is_active``.
    * The single, narrow bypass: when the bearer token's JTI exactly matches
      ``initiator_jti`` (the JTI captured at mint time on the schools row),
      we skip ``is_active`` and ``last_password_change`` so the legitimate
      teacher who just initiated the lifecycle action can redeem the exit
      artefact with the same session — even though that session has been
      invalidated for every other API surface.  The export token's own
      single-use + 24h expiry + uid/ws binding bound that window.

    Returns the validated ``user_id`` string on success.
    Raises ``HTTPException`` (401/403) for any auth failure — never returns
    without a verified identity.
    """
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=403, detail=_MSG_DOWNLOAD_AUTH_REQUIRED)
    raw = auth_header[len("Bearer "):].strip()
    if not raw:
        raise HTTPException(status_code=403, detail=_MSG_DOWNLOAD_AUTH_REQUIRED)

    try:
        decoded = _jwt.decode(raw, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except _jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="رمز المصادقة غير صالح أو منتهي الصلاحية.")

    if decoded.get("type") != "access":
        raise HTTPException(status_code=401, detail="نوع رمز المصادقة غير مقبول.")

    user_id = decoded.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="رمز المصادقة غير صالح.")

    jti = decoded.get("jti")
    if jti:
        try:
            revoked = await gd_find_one(db.session, "revoked_tokens", {"jti": jti})
            if revoked:
                raise HTTPException(status_code=401, detail="تم إلغاء الجلسة.")
        except HTTPException:
            raise
        except Exception:
            pass

    user = await gd_find_one(db.session, "users", {"id": user_id})
    if not user:
        raise HTTPException(status_code=401, detail="المستخدم غير موجود.")
    if user.get("is_locked", False):
        raise HTTPException(status_code=401, detail="الحساب مُعلَّق بسبب مخاوف أمنية.")

    # -- Session-invalidation gate (Task #450) -------------------------------
    # The narrow exemption from is_active / last_password_change is granted
    # ONLY to the exact bearer-token JTI that minted this export.  Any other
    # bearer token presented at the download endpoint must satisfy the same
    # checks as ``get_current_user`` — so a stolen or otherwise-replayed
    # session that did not initiate the lifecycle action cannot redeem the
    # URL after archive/erasure has invalidated it everywhere else.
    is_initiator = bool(
        initiator_jti and jti and str(jti) == str(initiator_jti)
    )
    if not is_initiator:
        if not user.get("is_active", True):
            raise HTTPException(status_code=401, detail="تم إلغاء الجلسة.")
        last_pw_change = user.get("last_password_change")
        token_iat = decoded.get("iat")
        if last_pw_change:
            if token_iat is None:
                raise HTTPException(status_code=401, detail="تم إلغاء الجلسة.")
            try:
                _lpc_str = (
                    last_pw_change
                    if isinstance(last_pw_change, str)
                    else str(last_pw_change)
                ).replace("Z", "+00:00")
                pw_change_ts = datetime.fromisoformat(_lpc_str).timestamp()
                if float(token_iat) < pw_change_ts:
                    raise HTTPException(status_code=401, detail="تم إلغاء الجلسة.")
            except HTTPException:
                raise
            except Exception:
                # Fail closed when we cannot parse the boundary — better to
                # force a fresh login than risk honoring a stale token.
                raise HTTPException(status_code=401, detail="تم إلغاء الجلسة.")

    return str(user_id)


@router.get("/public/workspace-export/{token}")
async def download_workspace_export(token: str, request: Request):
    client_ip = extract_client_ip(request)
    limited, _, retry_after = await rate_store.is_rate_limited(
        f"{client_ip}:workspace_export_download",
        _DOWNLOAD_RATE_MAX,
        _DOWNLOAD_RATE_WINDOW,
    )
    if limited:
        raise HTTPException(
            status_code=429,
            detail=_MSG_RATE_LIMITED,
            headers={"Retry-After": str(retry_after)},
        )

    payload = verify_workspace_export_token(token)
    if not payload:
        raise HTTPException(status_code=404, detail=_MSG_DOWNLOAD_INVALID)
    workspace_id = payload["ws"]
    user_id = payload["uid"]

    # Re-check the workspace still exists and isn't already
    # hard-deletion-pending; archived is FINE — the export is the user's
    # exit artefact, they need it to remain reachable while the
    # reactivation window is open.
    school = await gd_find_one(db.session, "schools", {"id": workspace_id})
    if not school or school.get("pending_hard_delete"):
        raise HTTPException(status_code=404, detail=_MSG_DOWNLOAD_INVALID)

    # -- Identity binding (§369 + Task #450) ---------------------------------
    # All downloads require a valid, user-bound Bearer access token.  Task
    # #450 additionally binds the bypass of the session-invalidation checks
    # (is_active / last_password_change) to the exact bearer-token JTI that
    # was captured on the schools row at mint time.  Any OTHER bearer token
    # — including a different stolen session from the same user — must pass
    # full session-invalidation checks and will be rejected after the
    # archive/erasure path has bumped ``last_password_change`` / cleared
    # ``is_active``.  Raises 401/403 on any auth failure.
    initiator_jti = school.get("last_export_initiator_jti")
    caller_user_id = await _authenticate_export_download(
        request, initiator_jti=initiator_jti,
    )
    if caller_user_id != str(user_id):
        raise HTTPException(status_code=403, detail=_MSG_DOWNLOAD_IDENTITY)
    # ------------------------------------------------------------------------

    # Single-use enforcement: the token hash must match the most
    # recent mint AND must not have been consumed yet. Atomically
    # flip ``last_export_consumed_at`` BEFORE building the bundle so
    # parallel requests racing on the same URL serialise on the row
    # update — only the first wins, every other request 404s.
    submitted_hash = _token_hash(token)
    if (school.get("last_export_token_hash") or "") != submitted_hash:
        raise HTTPException(status_code=404, detail=_MSG_DOWNLOAD_INVALID)
    if school.get("last_export_consumed_at"):
        raise HTTPException(status_code=404, detail=_MSG_DOWNLOAD_INVALID)
    try:
        async with db.session.begin_nested():
            # Task #356 / race-condition hardening: lock the schools row with
            # SELECT ... FOR UPDATE so that concurrent requests using the same
            # single-use export URL serialise here. After acquiring the lock,
            # re-verify that the hash still matches AND last_export_consumed_at
            # is still NULL — only the first request past this gate commits;
            # all subsequent requests with the same token get 404.
            locked_school_result = await db.session.execute(
                _sa_select(_SchoolModel)
                .where(_SchoolModel.id == workspace_id)
                .limit(1)
                .with_for_update()
            )
            school_locked = locked_school_result.scalars().first()
            if (
                not school_locked
                or (school_locked.last_export_token_hash or "") != submitted_hash
                or school_locked.last_export_consumed_at is not None
            ):
                raise HTTPException(status_code=404, detail=_MSG_DOWNLOAD_INVALID)

            school_locked.last_export_consumed_at = _utcnow()
            await db.session.flush()
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("workspace export consume update failed: %s", exc)
        raise HTTPException(status_code=404, detail=_MSG_DOWNLOAD_INVALID)

    bundle = await _build_export_bundle(workspace_id)

    try:
        await audit_engine.log(
            action=AUDIT_EXPORT_DOWNLOADED,
            performed_by=user_id,
            tenant_id=workspace_id,
            entity_type="school",
            entity_id=workspace_id,
            details={
                "school_id": workspace_id,
                "tenant_id": workspace_id,
                "user_id": user_id,
                "bytes": len(bundle),
                "client_ip": client_ip,
            },
            ip_address=client_ip,
            user_agent=request.headers.get("user-agent"),
        )
    except Exception:  # noqa: BLE001
        logger.debug("workspace export download audit failed", exc_info=True)

    filename = f"nassaq-workspace-{workspace_id}.zip"
    return Response(
        content=bundle,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",
        },
    )


# -- Endpoint: POST /independent-teacher/workspace/soft-delete ------------

@router.post("/independent-teacher/workspace/soft-delete")
async def soft_delete_workspace(
    payload: SoftDeleteRequest,
    request: Request,
    current_user: dict = Depends(_require_independent_teacher),
    _mfa: dict = Depends(_recent_mfa_403_dep),
    _perm: dict = Depends(_require_workspace_soft_delete_perm),
):
    school_id = require_request_school_id(current_user)
    workspace_id = independent_workspace_id(current_user) or school_id

    school = await gd_find_one(db.session, "schools", {"id": workspace_id})
    if not school:
        raise HTTPException(status_code=404, detail=_MSG_WORKSPACE_NOT_FOUND)

    if (school.get("status") or "").lower() == "archived":
        raise HTTPException(status_code=409, detail=_MSG_ALREADY_ARCHIVED)

    last_export_at = _coerce_dt(school.get("last_export_at"))
    if last_export_at is None or (_utcnow() - last_export_at) > WORKSPACE_EXPORT_TOKEN_TTL:
        raise HTTPException(status_code=412, detail=_MSG_EXPORT_REQUIRED)

    submitted = (payload.confirm_workspace_name or "").strip()
    expected = (school.get("name") or "").strip()
    if not submitted or submitted != expected:
        raise HTTPException(status_code=422, detail=_MSG_NAME_MISMATCH)

    now = _utcnow()
    # Mint a fresh export token at archive time so the email link works
    # even if the user already consumed the original download. Replacing
    # the prior hash + clearing consumed_at matches the documented
    # "minting a new token invalidates any prior outstanding URL"
    # contract; the workspace stays downloadable until pending_hard_delete
    # flips, which only happens after the 30-day reactivation window.
    fresh_token, fresh_hash, fresh_expires_at = mint_workspace_export_token(
        workspace_id, current_user["id"],
    )
    # Task #450 — see /workspace/export for rationale.  Captured BEFORE we
    # bump last_password_change so the bearer presented at download time
    # (the same one the user holds right now) is recognised as the
    # initiator and may bypass is_active / last_password_change checks.
    initiator_jti = _extract_bearer_jti(request)
    try:
        async with db.session.begin_nested():
            await gd_update_one(
                db.session, "schools", {"id": workspace_id},
                {
                    "status": "archived",
                    "archived_at": now.isoformat(),
                    "updated_at": now.isoformat(),
                    "last_export_at": now.isoformat(),
                    "last_export_token_hash": fresh_hash,
                    "last_export_consumed_at": None,
                    "last_export_initiator_jti": initiator_jti,
                    "reactivation_reminder_sent_at": None,
                },
            )
            # IT §6.8 session invalidation: bump last_password_change so
            # every already-issued access token and refresh token is
            # immediately rejected by the iat-vs-last_password_change check
            # in get_current_user() and /auth/refresh. This cuts off any
            # session that was active at the moment of soft-delete without
            # needing a per-JTI revocation sweep.
            await gd_update_one(
                db.session, "users", {"id": current_user["id"]},
                {"last_password_change": now.isoformat()},
            )
            await audit_engine.log(
                action=AUDIT_SOFT_DELETE,
                performed_by=current_user["id"],
                tenant_id=workspace_id,
                entity_type="school",
                entity_id=workspace_id,
                details={
                    "school_id": workspace_id,
                    "tenant_id": workspace_id,
                    "user_id": current_user["id"],
                    "archived_at": now.isoformat(),
                    "reactivation_window_days": _REACTIVATE_WINDOW.days,
                    "last_export_at": last_export_at.isoformat(),
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
            "soft_delete_workspace failed user=%s: %s",
            current_user.get("id"), exc,
        )
        raise HTTPException(status_code=500, detail=_MSG_INTERNAL)

    reactivation_deadline = now + _REACTIVATE_WINDOW
    download_url = f"/api/public/workspace-export/{fresh_token}"

    # Best-effort archive notification email. Failure must NOT undo the
    # archive — the workspace is already in the 'archived' state and
    # the in-app dialog has surfaced the deadline. We log + continue.
    try:
        from routes.independent_teacher_notifications_routes import should_send_channel
        recipient = (current_user.get("email") or "").strip()
        email_allowed = await should_send_channel(
            current_user, "workspace_lifecycle", "email",
        )
        if (
            email_allowed
            and recipient
            and "@" in recipient
            and "@invite.nassaq.invalid" not in recipient
        ):
            await send_email_off_loop(
                send_workspace_archived_email,
                to_email=recipient,
                user_name=current_user.get("full_name") or recipient,
                workspace_name=(school.get("name") or "").strip() or workspace_id,
                reactivation_deadline=reactivation_deadline.isoformat(),
                reactivation_window_days=_REACTIVATE_WINDOW.days,
                download_url=download_url,
                download_expires_at=fresh_expires_at.isoformat(),
            )
    except Exception as exc:  # noqa: BLE001
        logger.warning("workspace archived email dispatch failed: %s", exc)

    # Task #249 — also surface the lifecycle event in the IT inbox so
    # the user has an in-app trail of archive/reactivate events even
    # when their email channel is suppressed.
    try:
        from routes.notification_routes_mod import create_notification_internal
        from routes.independent_teacher_notifications_routes import should_send_channel
        if await should_send_channel(current_user, "workspace_lifecycle", "in_app"):
            await create_notification_internal(
                title="تم أرشفة مساحة العمل",
                message=(
                    "تم أرشفة مساحة عملك. يمكنك إعادة التفعيل خلال "
                    f"{_REACTIVATE_WINDOW.days} يومًا."
                ),
                title_en="Workspace archived",
                message_en=(
                    "Your workspace was archived. "
                    f"You can reactivate within {_REACTIVATE_WINDOW.days} days."
                ),
                recipient_id=current_user["id"],
                notification_type="workspace_archived",
                priority="high",
                related_entity="school",
                related_entity_id=workspace_id,
                school_id=workspace_id,
                category="workspace_lifecycle",
                cta_url="/account-settings",
                extra_data={
                    "archived_at": now.isoformat(),
                    "reactivation_deadline": reactivation_deadline.isoformat(),
                },
            )
    except Exception as exc:  # noqa: BLE001
        logger.debug("workspace archived inbox notify failed: %s", exc)

    return {
        "ok": True,
        "status": "archived",
        "archived_at": now.isoformat(),
        "reactivation_window_days": _REACTIVATE_WINDOW.days,
        "reactivation_deadline": reactivation_deadline.isoformat(),
        "download_url": download_url,
        "download_expires_at": fresh_expires_at.isoformat(),
    }


# -- Endpoint: POST /independent-teacher/workspace/request-erasure -------
#
# Task #276 — IT account erasure (GDPR right-to-be-forgotten).
#
# Distinct from soft-delete: this CTA is shown alongside the archive
# button in the IT danger-zone hub, and is a ONE-WAY operation. We
# stamp ``erasure_requested_at`` + ``pending_hard_delete=TRUE`` +
# ``status='archived'`` immediately, so the on-login gate locks the
# user out and the reactivate endpoint 410s with a distinct message.
# A daily background sweep (``app.lifecycle._sweep_erasure_purges``)
# physically purges the workspace using the shared
# ``purge_workspace_cascade`` helper once the configured window
# elapses (env ``WORKSPACE_ERASURE_WINDOW_DAYS``, default 7 days).

@router.post("/independent-teacher/workspace/request-erasure")
async def request_workspace_erasure(
    payload: RequestErasureRequest,
    request: Request,
    current_user: dict = Depends(_require_independent_teacher),
    _mfa: dict = Depends(_recent_mfa_403_dep),
    _perm: dict = Depends(_require_workspace_soft_delete_perm),
):
    school_id = require_request_school_id(current_user)
    workspace_id = independent_workspace_id(current_user) or school_id

    school = await gd_find_one(db.session, "schools", {"id": workspace_id})
    if not school:
        raise HTTPException(status_code=404, detail=_MSG_WORKSPACE_NOT_FOUND)

    if school.get("erasure_requested_at"):
        raise HTTPException(status_code=409, detail=_MSG_ALREADY_ERASURE)

    if not bool(payload.acknowledged):
        raise HTTPException(status_code=422, detail=_MSG_NOT_ACKNOWLEDGED)

    submitted = (payload.confirm_workspace_name or "").strip()
    expected = (school.get("name") or "").strip()
    if not submitted or submitted != expected:
        raise HTTPException(status_code=422, detail=_MSG_NAME_MISMATCH)

    now = _utcnow()
    window_days = _erasure_window_days()
    erasure_deadline = now + timedelta(days=window_days)

    # Forensics snapshot — captured BEFORE the archive flip so the
    # row counts reflect the live state at the moment of the request.
    forensics_snapshot = await _build_erasure_forensics_snapshot(
        workspace_id, school,
    )

    # Mint a fresh single-use export token so the email link works
    # even if the user already consumed any prior download. This is
    # the user's last chance to grab their data before the sweep
    # purges the workspace.
    fresh_token, fresh_hash, fresh_expires_at = mint_workspace_export_token(
        workspace_id, current_user["id"],
    )

    # Task #450 — capture initiator JTI BEFORE the session-invalidation
    # bump below so the same bearer the user holds may redeem the export.
    initiator_jti = _extract_bearer_jti(request)
    try:
        async with db.session.begin_nested():
            await gd_update_one(
                db.session, "schools", {"id": workspace_id},
                {
                    "status": "archived",
                    "archived_at": now.isoformat(),
                    "updated_at": now.isoformat(),
                    "pending_hard_delete": True,
                    "erasure_requested_at": now.isoformat(),
                    "erasure_window_days": window_days,
                    "last_export_at": now.isoformat(),
                    "last_export_token_hash": fresh_hash,
                    "last_export_consumed_at": None,
                    "last_export_initiator_jti": initiator_jti,
                    "reactivation_reminder_sent_at": None,
                },
            )
            # IT §6.8 session invalidation (erasure path): deactivate the
            # user account immediately (erasure is one-way and claims to lock
            # the workspace instantly) and bump last_password_change to
            # invalidate all outstanding access + refresh tokens. Both checks
            # fire on every subsequent API call and on the next refresh
            # attempt, so the user cannot continue using the workspace via
            # already-issued credentials.
            await gd_update_one(
                db.session, "users", {"id": current_user["id"]},
                {
                    "is_active": False,
                    "last_password_change": now.isoformat(),
                },
            )
            await audit_engine.log(
                action=AUDIT_ERASURE_REQUESTED,
                performed_by=current_user["id"],
                tenant_id=workspace_id,
                entity_type="school",
                entity_id=workspace_id,
                details={
                    "school_id": workspace_id,
                    "tenant_id": workspace_id,
                    "user_id": current_user["id"],
                    "requested_at": now.isoformat(),
                    "erasure_window_days": window_days,
                    "erasure_deadline": erasure_deadline.isoformat(),
                    "snapshot": forensics_snapshot,
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
            "request_workspace_erasure failed user=%s: %s",
            current_user.get("id"), exc,
        )
        raise HTTPException(status_code=500, detail=_MSG_INTERNAL)

    download_url = f"/api/public/workspace-export/{fresh_token}"

    # Best-effort final-export email. Failure must NOT undo the
    # erasure request — the in-app dialog already surfaced the
    # download URL and deadline.
    try:
        from routes.independent_teacher_notifications_routes import should_send_channel
        recipient = (current_user.get("email") or "").strip()
        email_allowed = await should_send_channel(
            current_user, "workspace_lifecycle", "email",
        )
        if (
            email_allowed
            and recipient
            and "@" in recipient
            and "@invite.nassaq.invalid" not in recipient
        ):
            await send_email_off_loop(
                send_workspace_erasure_final_export_email,
                to_email=recipient,
                user_name=current_user.get("full_name") or recipient,
                workspace_name=(school.get("name") or "").strip() or workspace_id,
                erasure_deadline=erasure_deadline.isoformat(),
                erasure_window_days=window_days,
            )
    except Exception as exc:  # noqa: BLE001
        logger.warning("workspace erasure email dispatch failed: %s", exc)

    return {
        "ok": True,
        "status": "archived",
        "pending_hard_delete": True,
        "erasure_requested_at": now.isoformat(),
        "erasure_deadline": erasure_deadline.isoformat(),
        "erasure_window_days": window_days,
        "download_url": download_url,
        "download_expires_at": fresh_expires_at.isoformat(),
    }


def _iso_or_none(v):
    if not v:
        return None
    return v.isoformat() if hasattr(v, "isoformat") else str(v)


async def _build_erasure_forensics_snapshot(
    workspace_id: str, school: dict,
) -> dict:
    """Capture a per-table row-count forensics snapshot mirroring the
    ``_EXPORT_TABLES`` scope. Stored on the
    ``INDEPENDENT_TEACHER_ERASURE_REQUESTED`` audit row so downstream
    forensics can compare these against the
    ``INDEPENDENT_TEACHER_ERASURE_COMPLETED`` ``deleted_counts``
    written by the daily sweep. Schema-drift tolerant: tables/columns
    that no longer exist are recorded under ``skipped_tables`` so a
    stale whitelist entry never blocks an erasure request.
    """
    counts: Dict[str, int] = {}
    skipped: List[str] = []
    for table_name, scope_col in _EXPORT_TABLES:
        key = f"{table_name}.{scope_col}"
        try:
            n = await gd_count(
                db.session, table_name, {scope_col: workspace_id},
            )
            counts[key] = int(n or 0)
        except _PgProgrammingError as exc:
            pgcode = getattr(getattr(exc, "orig", None), "sqlstate", None)
            if pgcode in {"42P01", "42703"}:
                skipped.append(key)
                continue
            raise
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "erasure snapshot: count failed for %s: %s", key, exc,
            )
            skipped.append(key)
    return {
        "school": {
            "id": school.get("id"),
            "name": school.get("name"),
            "status": school.get("status"),
            "archived_at": _iso_or_none(school.get("archived_at")),
            "last_export_at": _iso_or_none(school.get("last_export_at")),
            "created_at": _iso_or_none(school.get("created_at")),
        },
        "table_row_counts": counts,
        "skipped_tables": skipped,
        "export_tables_whitelist": [
            f"{t}.{c}" for t, c in _EXPORT_TABLES
        ],
        "redacted_columns_whitelist": sorted(_REDACTED_COLUMNS),
    }


# -- Endpoint: POST /independent-teacher/workspace/reactivate -------------

@router.post("/independent-teacher/workspace/reactivate")
async def reactivate_workspace(
    request: Request,
    current_user: dict = Depends(_require_independent_teacher),
    _mfa: dict = Depends(_recent_mfa_403_dep),
):
    school_id = require_request_school_id(current_user)
    workspace_id = independent_workspace_id(current_user) or school_id

    school = await gd_find_one(db.session, "schools", {"id": workspace_id})
    if not school:
        raise HTTPException(status_code=404, detail=_MSG_WORKSPACE_NOT_FOUND)

    if (school.get("status") or "").lower() != "archived":
        raise HTTPException(status_code=409, detail=_MSG_NOT_ARCHIVED)

    if school.get("pending_hard_delete"):
        # Erasure-flow workspaces ALSO carry pending_hard_delete=TRUE,
        # but the user-facing message must be different — they are not
        # past a reactivation deadline, they have explicitly requested
        # erasure and must be told the request cannot be undone.
        if school.get("erasure_requested_at"):
            raise HTTPException(status_code=410, detail=_MSG_ERASURE_PENDING)
        raise HTTPException(status_code=410, detail=_MSG_REACTIVATE_EXPIRED)

    archived_at = _coerce_dt(school.get("archived_at"))
    if archived_at is None or (_utcnow() - archived_at) > _REACTIVATE_WINDOW:
        raise HTTPException(status_code=410, detail=_MSG_REACTIVATE_EXPIRED)

    now = _utcnow()
    try:
        async with db.session.begin_nested():
            # Copy ``archived_at`` into ``last_archive_cycle_archived_at``
            # before nulling it so the post-login banner can render the
            # "your workspace was archived on X" sentence and compute
            # how many days were left when the user came back. Also
            # stamp ``last_reactivated_at`` so the lifecycle GET can
            # compare it against ``reactivation_banner_dismissed_at``
            # and re-arm the banner on every fresh cycle.
            await gd_update_one(
                db.session, "schools", {"id": workspace_id},
                {
                    "status": "active",
                    "archived_at": None,
                    "updated_at": now.isoformat(),
                    "reactivation_reminder_sent_at": None,
                    "last_reactivated_at": now.isoformat(),
                    "last_archive_cycle_archived_at": archived_at.isoformat(),
                },
            )
            await audit_engine.log(
                action=AUDIT_REACTIVATE,
                performed_by=current_user["id"],
                tenant_id=workspace_id,
                entity_type="school",
                entity_id=workspace_id,
                details={
                    "school_id": workspace_id,
                    "tenant_id": workspace_id,
                    "user_id": current_user["id"],
                    "previous_archived_at": archived_at.isoformat(),
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
            "reactivate_workspace failed user=%s: %s",
            current_user.get("id"), exc,
        )
        raise HTTPException(status_code=500, detail=_MSG_INTERNAL)

    return {"ok": True, "status": "active"}


# -- Lazy on-login sweep helper ------------------------------------------
#
# Called from auth_routes_mod.login on the IT login path. Cheap: a
# single workspace lookup + at-most-one row update. NOT a background
# job — we want the flag to flip the first time the user touches the
# system after the 30-day window so platform-admin tooling sees a
# consistent state without scheduled jobs.

async def maybe_flip_pending_hard_delete(workspace_id: str) -> bool:
    """Flip ``pending_hard_delete`` true when the archived workspace
    is past its reactivation window. Returns True if the flag flipped
    on this call. Best-effort — never raises.
    """
    if not workspace_id:
        return False
    try:
        school = await gd_find_one(db.session, "schools", {"id": workspace_id})
        if not school:
            return False
        if school.get("pending_hard_delete"):
            return False
        if (school.get("status") or "").lower() != "archived":
            return False
        archived_at = _coerce_dt(school.get("archived_at"))
        if archived_at is None:
            return False
        if (_utcnow() - archived_at) <= _REACTIVATE_WINDOW:
            return False
        await gd_update_one(
            db.session, "schools", {"id": workspace_id},
            {"pending_hard_delete": True, "updated_at": _utcnow_iso()},
        )
        try:
            await audit_engine.log(
                action=AUDIT_PENDING_HARD_DELETE,
                performed_by=None,
                tenant_id=workspace_id,
                entity_type="school",
                entity_id=workspace_id,
                details={
                    "school_id": workspace_id,
                    "tenant_id": workspace_id,
                    "trigger": "lazy_on_login_sweep",
                    "archived_at": archived_at.isoformat(),
                },
            )
        except Exception:  # noqa: BLE001
            logger.debug("pending_hard_delete audit failed", exc_info=True)
        return True
    except Exception as exc:  # noqa: BLE001
        logger.debug("maybe_flip_pending_hard_delete: %s", exc)
        return False


# -- Endpoints: GET/PUT /independent-teacher/workspace/auto-export/settings -

# Task #275 — opt-in weekly auto-export. The toggle lives on the IT
# §6.8 hub. Intentionally NOT MFA-gated: this is a configuration toggle,
# not a destructive action; the user already authorised the resulting
# scheduled export by enabling it. The actual sweep that mints the
# token + sends the email lives in ``app/lifecycle.py`` so a single
# hourly loop covers all workspaces.
#
# Day-of-week convention: ``0=Sunday`` … ``6=Saturday`` (matches JS
# ``Date.getDay()`` so the FE doesn't have to translate). Hour is
# 0-23 in **UTC**.

_DOW_MIN, _DOW_MAX = 0, 6
_HOUR_MIN, _HOUR_MAX = 0, 23
_MSG_AUTO_EXPORT_BAD_DOW = "يوم الأسبوع غير صالح."
_MSG_AUTO_EXPORT_BAD_HOUR = "الساعة غير صالحة."

_DEFAULT_AUTO_EXPORT_DOW = 0   # Sunday
_DEFAULT_AUTO_EXPORT_HOUR = 2  # 02:00 UTC


class AutoExportSettingsRequest(BaseModel):
    enabled: bool
    day_of_week: Optional[int] = Field(default=None, ge=_DOW_MIN, le=_DOW_MAX)
    hour: Optional[int] = Field(default=None, ge=_HOUR_MIN, le=_HOUR_MAX)


def _next_run_at(
    now: datetime, dow: int, hour: int,
) -> datetime:
    """Return the next UTC datetime matching ``dow`` (0=Sun) at ``hour:00``.
    If today matches ``dow`` and ``now.hour < hour``, returns today; else
    the next matching weekday at the top of ``hour``.
    """
    # Python: Monday=0..Sunday=6; convert to our 0=Sunday convention.
    today_dow = (now.weekday() + 1) % 7
    days_ahead = (dow - today_dow) % 7
    candidate = now.replace(hour=hour, minute=0, second=0, microsecond=0)
    if days_ahead == 0 and candidate <= now:
        days_ahead = 7
    return candidate + timedelta(days=days_ahead)


def _serialise_auto_export(quota: Dict[str, Any]) -> Dict[str, Any]:
    enabled = bool(quota.get("auto_export_enabled"))
    dow_raw = quota.get("auto_export_dow")
    hr_raw = quota.get("auto_export_hour")
    dow = int(dow_raw) if dow_raw is not None else _DEFAULT_AUTO_EXPORT_DOW
    hour = int(hr_raw) if hr_raw is not None else _DEFAULT_AUTO_EXPORT_HOUR
    last_run = _coerce_dt(quota.get("auto_export_last_run_at"))
    next_run = _next_run_at(_utcnow(), dow, hour) if enabled else None
    return {
        "enabled": enabled,
        "day_of_week": dow,
        "hour": hour,
        "last_run_at": last_run.isoformat() if last_run else None,
        "last_status": quota.get("auto_export_last_status"),
        "next_run_at": next_run.isoformat() if next_run else None,
    }


@router.get("/independent-teacher/workspace/auto-export/settings")
async def read_auto_export_settings(
    current_user: dict = Depends(_require_independent_teacher),
):
    workspace_id = independent_workspace_id(current_user) or require_request_school_id(current_user)
    quota = await gd_find_one(
        db.session, "workspace_quota", {"workspace_school_id": workspace_id},
    )
    if not quota:
        # No quota row yet (legacy bootstrap): return defaults.
        quota = {}
    return _serialise_auto_export(quota)


@router.put("/independent-teacher/workspace/auto-export/settings")
async def update_auto_export_settings(
    payload: AutoExportSettingsRequest,
    current_user: dict = Depends(_require_independent_teacher),
):
    workspace_id = independent_workspace_id(current_user) or require_request_school_id(current_user)
    dow = payload.day_of_week if payload.day_of_week is not None else _DEFAULT_AUTO_EXPORT_DOW
    hour = payload.hour if payload.hour is not None else _DEFAULT_AUTO_EXPORT_HOUR
    if not (_DOW_MIN <= dow <= _DOW_MAX):
        raise HTTPException(status_code=422, detail=_MSG_AUTO_EXPORT_BAD_DOW)
    if not (_HOUR_MIN <= hour <= _HOUR_MAX):
        raise HTTPException(status_code=422, detail=_MSG_AUTO_EXPORT_BAD_HOUR)

    quota = await gd_find_one(
        db.session, "workspace_quota", {"workspace_school_id": workspace_id},
    )
    updates = {
        "auto_export_enabled": bool(payload.enabled),
        "auto_export_dow": dow,
        "auto_export_hour": hour,
        "updated_at": _utcnow_iso(),
    }
    try:
        async with db.session.begin_nested():
            if quota:
                await gd_update_one(
                    db.session, "workspace_quota",
                    {"workspace_school_id": workspace_id}, updates,
                )
            else:
                # Defensive insert: bootstrap should always seed the row,
                # but legacy workspaces predate the quota table.
                from engines.sql_utils import gd_insert as _gd_insert
                await _gd_insert(
                    db.session, "workspace_quota",
                    {"workspace_school_id": workspace_id, **updates},
                )
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.warning("update_auto_export_settings failed: %s", exc)
        raise HTTPException(status_code=500, detail=_MSG_INTERNAL)

    fresh = await gd_find_one(
        db.session, "workspace_quota", {"workspace_school_id": workspace_id},
    ) or {}
    return _serialise_auto_export(fresh)


__all__ = ["router", "maybe_flip_pending_hard_delete"]
